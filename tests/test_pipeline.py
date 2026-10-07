"""End-to-end pipeline test against simulated AWS services (moto).

upload_url -> S3 object -> SQS-style event -> processor -> DynamoDB -> query API -> daily summary
"""

import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGION = "us-east-1"
USER = "11111111-2222-3333-4444-555555555555"


def table(ddb, name):
    ddb.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
    )


@pytest.fixture
def aws(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.delenv("AWS_SESSION_TOKEN", raising=False)
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="raw-bucket")
        ddb = boto3.client("dynamodb", region_name=REGION)
        table(ddb, "daily")
        table(ddb, "meta")
        topic = boto3.client("sns", region_name=REGION).create_topic(Name="alerts")["TopicArn"]
        dlq = boto3.client("sqs", region_name=REGION).create_queue(QueueName="dlq")["QueueUrl"]
        for k, v in {
            "RAW_BUCKET": "raw-bucket",
            "DAILY_TABLE": "daily",
            "META_TABLE": "meta",
            "ALERT_TOPIC_ARN": topic,
            "DLQ_URL": dlq,
        }.items():
            monkeypatch.setenv(k, v)
        modules = {name: importlib.reload(importlib.import_module(name)) for name in ("upload_url", "processor", "query", "summary")}
        yield {"s3": s3, "ddb": boto3.resource("dynamodb", region_name=REGION), **modules}


def api_event(route, body=None, groups="[uploaders]", params=None):
    return {
        "routeKey": route,
        "body": json.dumps(body) if body is not None else None,
        "queryStringParameters": params,
        "requestContext": {"authorizer": {"jwt": {"claims": {"sub": USER, "email": "tester@example.com", "cognito:groups": groups}}}},
    }


def sqs_event(key, message_id="m1"):
    s3_event = {"Records": [{"s3": {"bucket": {"name": "raw-bucket"}, "object": {"key": key}}}]}
    return {"Records": [{"messageId": message_id, "body": json.dumps(s3_event)}]}


def create_upload(aws, filename="sydney_7428_2020-01.csv"):
    res = aws["upload_url"].handler(api_event("POST /uploads", {"filename": filename, "size": 1000}), None)
    assert res["statusCode"] == 201, res
    return json.loads(res["body"])


def test_upload_requires_uploaders_group(aws):
    res = aws["upload_url"].handler(api_event("POST /uploads", {"filename": "a.csv", "size": 10}, groups=""), None)
    assert res["statusCode"] == 403


@pytest.mark.parametrize("body", [{"filename": "../evil.csv", "size": 10}, {"filename": "a.exe", "size": 10}, {"filename": "a.csv", "size": 10**9}])
def test_upload_validates_input(aws, body):
    res = aws["upload_url"].handler(api_event("POST /uploads", body), None)
    assert res["statusCode"] == 400


def test_full_pipeline_with_real_sydney_file(aws):
    upload = create_upload(aws)
    key = upload["fields"]["key"]
    assert key == f"raw/{USER}/{upload['upload_id']}.csv"
    assert upload["fields"]["Content-Type"] == "text/csv"

    with open(os.path.join(ROOT, "data", "sydney", "sydney_7428_2020-01.csv"), "rb") as f:
        aws["s3"].put_object(Bucket="raw-bucket", Key=key, Body=f.read())

    result = aws["processor"].handler(sqs_event(key), None)
    assert result == {"batchItemFailures": []}

    meta = aws["ddb"].Table("meta")
    item = meta.get_item(Key={"pk": f"USER#{USER}", "sk": f"UPLOAD#{upload['upload_id']}"})["Item"]
    assert item["status"] == "PROCESSED"
    assert item["daily_records"] > 100
    assert item["exceedances"] > 0

    summary = json.loads(aws["s3"].get_object(Bucket="raw-bucket", Key=f"processed/{upload['upload_id']}.json")["Body"].read())
    assert summary["stations"] == ["Cook And Phillip"]

    q = aws["query"].handler
    stations = json.loads(q(api_event("GET /stations"), None)["body"])["stations"]
    assert stations[0]["station_id"] == "7428" and "pm25" in stations[0]["parameters"]

    daily = json.loads(q(api_event("GET /daily", params={"parameter": "pm25"}), None)["body"])["records"]
    assert daily and all(r["parameter"] == "pm25" for r in daily)

    analytics = json.loads(q(api_event("GET /summary", params={"parameter": "pm25"}), None)["body"])
    assert analytics["limit"] == 25 and analytics["stations"][0]["exceedance_days"] > 0

    alerts = json.loads(q(api_event("GET /alerts"), None)["body"])["alerts"]
    assert len(alerts) == item["exceedances"]

    uploads = json.loads(q(api_event("GET /uploads"), None)["body"])["uploads"]
    assert uploads[0]["status"] == "PROCESSED"

    report = aws["summary"].handler({}, None)
    assert report["uploads_processed"] == 1 and report["stations_known"] == 1 and report["dead_letter_messages"] == 0


def test_invalid_file_is_marked_failed_and_not_retried(aws):
    upload = create_upload(aws, "bad.csv")
    key = upload["fields"]["key"]
    aws["s3"].put_object(Bucket="raw-bucket", Key=key, Body=b"name,age\nbob,3\n")
    assert aws["processor"].handler(sqs_event(key), None) == {"batchItemFailures": []}
    item = aws["ddb"].Table("meta").get_item(Key={"pk": f"USER#{USER}", "sk": f"UPLOAD#{upload['upload_id']}"})["Item"]
    assert item["status"] == "FAILED" and "missing required columns" in item["error"]


def test_malformed_message_is_returned_for_retry(aws):
    event = {"Records": [{"messageId": "poison", "body": '{"hello": "world"}'}]}
    assert aws["processor"].handler(event, None) == {"batchItemFailures": [{"itemIdentifier": "poison"}]}


def test_missing_object_is_returned_for_retry(aws):
    assert aws["processor"].handler(sqs_event(f"raw/{USER}/gone.csv", "m2"), None) == {"batchItemFailures": [{"itemIdentifier": "m2"}]}


def test_query_rejects_bad_parameters(aws):
    q = aws["query"].handler
    assert q(api_event("GET /daily", params={"parameter": "gold"}), None)["statusCode"] == 400
    assert q(api_event("GET /summary", params={"from": "2020-02-01", "to": "2020-01-01"}), None)["statusCode"] == 400
    assert q(api_event("GET /nope"), None)["statusCode"] == 404
