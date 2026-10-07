"""Run the whole application locally against simulated AWS services (moto).

* Serves the frontend from code/frontend on http://localhost:8080/
* Serves the API under /api using the SAME Lambda handlers as the cloud
* Simulates S3 -> SQS -> processor: an upload is stored in the simulated S3
  bucket and the processor handler is invoked with an SQS-style S3 event
* Authentication is bypassed locally (single local user in the uploaders group)

Usage (from the repository root):
    pip install -r requirements-dev.txt
    python code/tools/local_server.py            # empty database
    python code/tools/local_server.py --preload  # process every file in data/sydney first
"""

import argparse
import email.parser
import email.policy
import glob
import http.server
import importlib
import json
import mimetypes
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND = os.path.join(ROOT, "code", "frontend")
sys.path.insert(0, os.path.join(ROOT, "code", "backend"))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

LOCAL_USER = {"sub": "local-user", "email": "local-developer", "cognito:groups": "[uploaders]"}
PORT = 8080
H = {}


def setup_aws():
    os.environ.update(
        {
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ACCESS_KEY_ID": "local",
            "AWS_SECRET_ACCESS_KEY": "local",
            "RAW_BUCKET": "aqmon-raw-local",
            "DAILY_TABLE": "aqmon-daily-stats",
            "META_TABLE": "aqmon-meta",
        }
    )
    os.environ.pop("AWS_SESSION_TOKEN", None)
    boto3.client("s3").create_bucket(Bucket="aqmon-raw-local")
    ddb = boto3.client("dynamodb")
    for name in ("aqmon-daily-stats", "aqmon-meta"):
        ddb.create_table(
            TableName=name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        )
    os.environ["ALERT_TOPIC_ARN"] = boto3.client("sns").create_topic(Name="aqmon-alerts")["TopicArn"]
    os.environ["DLQ_URL"] = boto3.client("sqs").create_queue(QueueName="aqmon-ingest-dlq")["QueueUrl"]
    for name in ("upload_url", "processor", "query", "summary"):
        H[name] = importlib.import_module(name)


def api_event(route, body=None, query=None):
    return {
        "routeKey": route,
        "body": body,
        "queryStringParameters": query or None,
        "requestContext": {"authorizer": {"jwt": {"claims": LOCAL_USER}}},
    }


def process(key):
    """Simulate S3 ObjectCreated -> SQS -> Lambda."""
    s3_event = {"Records": [{"s3": {"bucket": {"name": os.environ["RAW_BUCKET"]}, "object": {"key": urllib.parse.quote_plus(key)}}}]}
    return H["processor"].handler({"Records": [{"messageId": "local", "body": json.dumps(s3_event)}]}, None)


def preload():
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "sydney", "*.csv"))):
        name = os.path.basename(path)
        res = H["upload_url"].handler(api_event("POST /uploads", json.dumps({"filename": name, "size": os.path.getsize(path)})), None)
        key = json.loads(res["body"])["fields"]["key"]
        with open(path, "rb") as f:
            boto3.client("s3").put_object(Bucket=os.environ["RAW_BUCKET"], Key=key, Body=f.read())
        print(f"preloaded {name}: {process(key)}")


class Handler(http.server.BaseHTTPRequestHandler):
    def send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        return self.rfile.read(int(self.headers.get("Content-Length", 0)))

    def lambda_result(self, res):
        self.send(res["statusCode"], res["body"])

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path.startswith("/api/"):
            query = dict(urllib.parse.parse_qsl(url.query))
            return self.lambda_result(H["query"].handler(api_event(f"GET {url.path[4:]}", query=query), None))
        if url.path == "/config.js":
            cfg = {"localMode": True, "apiUrl": f"http://localhost:{PORT}/api", "region": "local"}
            return self.send(200, f"window.AQMON_CONFIG = {json.dumps(cfg)};", "application/javascript")
        rel = "index.html" if url.path == "/" else url.path.lstrip("/")
        path = os.path.normpath(os.path.join(FRONTEND, rel))
        if not path.startswith(FRONTEND) or not os.path.isfile(path):
            return self.send(404, "not found", "text/plain")
        with open(path, "rb") as f:
            self.send(200, f.read(), mimetypes.guess_type(path)[0] or "application/octet-stream")

    def do_POST(self):
        if self.path == "/api/uploads":
            res = H["upload_url"].handler(api_event("POST /uploads", self.body().decode()), None)
            if res["statusCode"] == 201:
                body = json.loads(res["body"])
                body["url"] = f"http://localhost:{PORT}/local-s3"
                res["body"] = json.dumps(body)
            return self.lambda_result(res)
        if self.path == "/local-s3":
            raw = self.body()
            msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(
                f"Content-Type: {self.headers['Content-Type']}\r\n\r\n".encode() + raw
            )
            fields, file_bytes = {}, None
            for part in msg.iter_parts():
                name = part.get_param("name", header="content-disposition")
                if name == "file":
                    file_bytes = part.get_payload(decode=True)
                else:
                    fields[name] = part.get_content().strip()
            boto3.client("s3").put_object(Bucket=os.environ["RAW_BUCKET"], Key=fields["key"], Body=file_bytes)
            print(f"stored {fields['key']} -> processor: {process(fields['key'])}")
            return self.send(204, b"")
        self.send(404, "not found", "text/plain")


def main():
    parser = argparse.ArgumentParser(description="Run AQMon locally")
    parser.add_argument("--preload", action="store_true", help="process all files in data/sydney at startup")
    args = parser.parse_args()
    with mock_aws():
        setup_aws()
        if args.preload:
            preload()
        server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
        print(f"AQMon local: http://localhost:{PORT}/  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
