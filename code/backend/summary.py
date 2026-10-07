"""Scheduled daily operations report (EventBridge -> Lambda -> SNS).

Counts the uploads processed and failed and the alerts raised in the last 24
hours, checks the dead-letter queue, and emails the report to SNS subscribers.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key

from common import emit_metrics, from_decimal, logger

META_TABLE = os.environ["META_TABLE"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]
DLQ_URL = os.environ["DLQ_URL"]

sqs = boto3.client("sqs")
sns = boto3.client("sns")
meta_table = boto3.resource("dynamodb").Table(META_TABLE)


def handler(event, context):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat()

    uploads = scan(Attr("pk").begins_with("USER#") & Attr("created_at").gte(since))
    processed = [u for u in uploads if u.get("status") == "PROCESSED"]
    failed = [u for u in uploads if u.get("status") == "FAILED"]
    alerts = sum(int(u.get("exceedances", 0)) for u in processed)
    stations = meta_table.query(KeyConditionExpression=Key("pk").eq("STATION"), Select="COUNT")["Count"]
    dlq_depth = int(
        sqs.get_queue_attributes(QueueUrl=DLQ_URL, AttributeNames=["ApproximateNumberOfMessages"])["Attributes"][
            "ApproximateNumberOfMessages"
        ]
    )

    report = {
        "period_start": since,
        "period_end": now.isoformat(),
        "uploads_received": len(uploads),
        "uploads_processed": len(processed),
        "uploads_failed": len(failed),
        "daily_records_written": sum(int(u.get("daily_records", 0)) for u in processed),
        "exceedance_alerts": alerts,
        "stations_known": stations,
        "dead_letter_messages": dlq_depth,
    }
    lines = [f"{k.replace('_', ' ')}: {v}" for k, v in report.items()]
    if failed:
        lines.append("")
        lines.append("Failed uploads:")
        lines += [f"  {u.get('filename')} - {u.get('error')}" for u in failed[:20]]
    sns.publish(TopicArn=ALERT_TOPIC_ARN, Subject="AQMon daily report", Message="\n".join(lines))
    emit_metrics("AQMon", {"Service": "summary"}, {"DailyReportsSent": 1})
    logger.info("daily report %s", json.dumps(report))
    return report


def scan(filter_expression):
    items, kwargs = [], {"FilterExpression": filter_expression}
    while True:
        page = meta_table.scan(**kwargs)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            return from_decimal(items)
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
