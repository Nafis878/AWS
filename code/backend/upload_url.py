"""POST /uploads -- issue a short-lived presigned S3 POST for one CSV file.

The browser uploads straight to S3, so file bytes never pass through the API
or Lambda. Only users in the Cognito group "uploaders" may upload.
"""

import json
import os
import re
import secrets
from datetime import datetime, timezone

import boto3

from common import claims, logger, response, user_groups

RAW_BUCKET = os.environ["RAW_BUCKET"]
META_TABLE = os.environ["META_TABLE"]
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
URL_EXPIRY_SECONDS = 300
UPLOAD_GROUP = "uploaders"

_FILENAME_RE = re.compile(r"^[A-Za-z0-9._ -]{1,100}\.csv$")

s3 = boto3.client("s3")
meta = boto3.resource("dynamodb").Table(META_TABLE)


def handler(event, context):
    if UPLOAD_GROUP not in user_groups(event):
        return response(403, {"error": f"only members of the '{UPLOAD_GROUP}' group can upload data"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "request body must be JSON"})

    filename = str(body.get("filename", "")).strip()
    size = body.get("size")
    if not _FILENAME_RE.match(filename):
        return response(400, {"error": "filename must be a .csv name of letters, digits, spaces, '.', '_' or '-'"})
    if not isinstance(size, int) or not 0 < size <= MAX_UPLOAD_BYTES:
        return response(400, {"error": f"size must be between 1 and {MAX_UPLOAD_BYTES} bytes"})

    user_id = claims(event)["sub"]
    now = datetime.now(timezone.utc)
    upload_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    key = f"raw/{user_id}/{upload_id}.csv"

    meta.put_item(
        Item={
            "pk": f"USER#{user_id}",
            "sk": f"UPLOAD#{upload_id}",
            "upload_id": upload_id,
            "filename": filename,
            "size": size,
            "s3_key": key,
            "status": "AWAITING_UPLOAD",
            "created_at": now.isoformat(),
            "uploaded_by": claims(event).get("email", user_id),
        }
    )

    post = s3.generate_presigned_post(
        Bucket=RAW_BUCKET,
        Key=key,
        Fields={"Content-Type": "text/csv"},
        Conditions=[{"Content-Type": "text/csv"}, ["content-length-range", 1, MAX_UPLOAD_BYTES]],
        ExpiresIn=URL_EXPIRY_SECONDS,
    )
    logger.info("issued upload url upload_id=%s key=%s size=%s", upload_id, key, size)
    return response(201, {"upload_id": upload_id, "url": post["url"], "fields": post["fields"]})
