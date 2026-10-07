"""SQS consumer -- processes CSV files that landed in the raw S3 bucket.

Flow: S3 ObjectCreated -> SQS queue -> this Lambda (batches of messages).
For each file: parse + validate, aggregate hourly readings into daily
statistics, store them in DynamoDB, record exceedance alerts, notify SNS and
write a processing summary back to S3.

Error handling:
* An invalid file (ValidationError) is a permanent problem: the upload is
  marked FAILED and the message is NOT retried.
* Any other error is reported as a batch item failure, so SQS retries it;
  after 3 failed receives SQS moves the message to the dead-letter queue.
"""

import json
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

import aq_core
from common import emit_metrics, logger, to_decimal

DAILY_TABLE = os.environ["DAILY_TABLE"]
META_TABLE = os.environ["META_TABLE"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]
MAX_OBJECT_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
LIMITS = {
    "pm25": float(os.environ.get("PM25_DAILY_LIMIT", "25")),
    "pm10": float(os.environ.get("PM10_DAILY_LIMIT", "50")),
}

s3 = boto3.client("s3")
sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
daily_table = dynamodb.Table(DAILY_TABLE)
meta_table = dynamodb.Table(META_TABLE)


def handler(event, context):
    failures = []
    for message in event.get("Records", []):
        try:
            process_message(message)
        except Exception:
            logger.exception("message %s failed; SQS will retry it", message.get("messageId"))
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}


def process_message(message):
    body = json.loads(message["body"])
    if body.get("Event") == "s3:TestEvent":
        logger.info("ignoring S3 test event")
        return
    records = body.get("Records")
    if not records:
        raise ValueError("message is not an S3 event notification")
    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        process_object(bucket, key)


def parse_key(key):
    """raw/<user_id>/<upload_id>.csv -> (user_id, upload_id)"""
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != "raw" or not parts[2].endswith(".csv"):
        raise aq_core.ValidationError(f"unexpected object key {key}")
    return parts[1], parts[2][: -len(".csv")]


def process_object(bucket, key):
    started = datetime.now(timezone.utc)
    try:
        user_id, upload_id = parse_key(key)
    except aq_core.ValidationError as err:
        logger.warning("skipping %s: %s", key, err)
        return
    logger.info("processing s3://%s/%s upload_id=%s", bucket, key, upload_id)
    set_status(user_id, upload_id, "PROCESSING", {"processing_started_at": started.isoformat()})

    obj = s3.get_object(Bucket=bucket, Key=key)
    if obj["ContentLength"] > MAX_OBJECT_BYTES:
        fail(user_id, upload_id, f"file is larger than {MAX_OBJECT_BYTES} bytes")
        return
    try:
        text = obj["Body"].read().decode("utf-8")
        parsed = aq_core.parse_openaq_csv(text)
    except (UnicodeDecodeError, aq_core.ValidationError) as err:
        fail(user_id, upload_id, str(err))
        return

    daily = aq_core.aggregate_daily(parsed.readings)
    exceedances = aq_core.find_exceedances(daily, LIMITS)
    store_daily(daily, upload_id)
    store_stations(daily)
    store_alerts(exceedances, upload_id)

    stations = sorted({d["station_name"] for d in daily})
    dates = sorted({d["date"] for d in daily})
    summary = {
        "upload_id": upload_id,
        "source_key": key,
        "rows_total": parsed.rows_total,
        "rows_rejected": parsed.rows_rejected,
        "daily_records": len(daily),
        "exceedances": len(exceedances),
        "stations": stations,
        "date_from": dates[0],
        "date_to": dates[-1],
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    s3.put_object(
        Bucket=bucket,
        Key=f"processed/{upload_id}.json",
        Body=json.dumps(summary, indent=2).encode(),
        ContentType="application/json",
    )
    if exceedances:
        notify(exceedances, summary)
    set_status(user_id, upload_id, "PROCESSED", {k: v for k, v in summary.items() if k != "upload_id"})

    emit_metrics(
        "AQMon",
        {"Service": "processor"},
        {
            "FilesProcessed": 1,
            "RowsProcessed": parsed.rows_total,
            "RowsRejected": parsed.rows_rejected,
            "DailyRecordsWritten": len(daily),
            "ExceedancesDetected": len(exceedances),
        },
    )
    logger.info("processed upload_id=%s %s", upload_id, json.dumps(summary))


def store_daily(daily, upload_id):
    # put_item overwrites the same station/pollutant/day key, so reprocessing
    # a file (e.g. an SQS retry) is idempotent.
    with daily_table.batch_writer() as batch:
        for d in daily:
            batch.put_item(
                Item=to_decimal(
                    {
                        "pk": f"{d['station_id']}#{d['parameter']}",
                        "sk": d["date"],
                        **d,
                        "source_upload": upload_id,
                    }
                )
            )


def store_stations(daily):
    seen = {}
    for d in daily:
        seen.setdefault(d["station_id"], (d, set()))[1].add(d["parameter"])
    for station_id, (d, parameters) in seen.items():
        meta_table.update_item(
            Key={"pk": "STATION", "sk": station_id},
            UpdateExpression="SET #name = :n, #lat = :lat, #lon = :lon ADD #params :p",
            ExpressionAttributeNames={"#name": "station_name", "#lat": "lat", "#lon": "lon", "#params": "parameters"},
            ExpressionAttributeValues=to_decimal(
                {":n": d["station_name"], ":lat": d["lat"], ":lon": d["lon"], ":p": parameters}
            ),
        )


def store_alerts(exceedances, upload_id):
    with meta_table.batch_writer() as batch:
        for e in exceedances:
            batch.put_item(
                Item=to_decimal(
                    {
                        "pk": "ALERT",
                        "sk": f"{e['date']}#{e['station_id']}#{e['parameter']}",
                        "date": e["date"],
                        "station_id": e["station_id"],
                        "station_name": e["station_name"],
                        "parameter": e["parameter"],
                        "mean": e["mean"],
                        "limit": e["limit"],
                        "units": e["units"],
                        "source_upload": upload_id,
                    }
                )
            )


def notify(exceedances, summary):
    lines = [
        f"{e['date']}  {e['station_name']:<20} {e['parameter'].upper():<5} "
        f"24h mean {e['mean']:.1f} {e['units']} (limit {e['limit']:.0f})"
        for e in sorted(exceedances, key=lambda e: (e["date"], e["station_name"], e["parameter"]))
    ]
    shown = lines[:40]
    if len(lines) > len(shown):
        shown.append(f"... and {len(lines) - len(shown)} more")
    message = (
        f"AQMon detected {len(exceedances)} day(s) above the 24-hour air-quality limit "
        f"in upload {summary['upload_id']} ({summary['date_from']} to {summary['date_to']}).\n\n"
        + "\n".join(shown)
    )
    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"AQMon alert: {len(exceedances)} exceedance day(s) detected",
        Message=message,
    )


def set_status(user_id, upload_id, status, fields):
    values = {":s": status, **{f":{k}": v for k, v in fields.items()}}
    names = {"#status": "status", **{f"#{k}": k for k in fields}}
    expr = "SET #status = :s" + "".join(f", #{k} = :{k}" for k in fields)
    meta_table.update_item(
        Key={"pk": f"USER#{user_id}", "sk": f"UPLOAD#{upload_id}"},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=to_decimal(values),
    )


def fail(user_id, upload_id, reason):
    logger.warning("upload_id=%s rejected: %s", upload_id, reason)
    set_status(user_id, upload_id, "FAILED", {"error": reason, "failed_at": datetime.now(timezone.utc).isoformat()})
    emit_metrics("AQMon", {"Service": "processor"}, {"FilesRejected": 1})
