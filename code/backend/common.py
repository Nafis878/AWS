"""Helpers shared by the Lambda handlers."""

import json
import logging
import os
import time
from decimal import Decimal

logger = logging.getLogger("aqmon")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

ALLOWED_PARAMETERS = ("pm25", "pm10", "no2", "o3", "co", "so2")


def to_decimal(value):
    """DynamoDB needs Decimal, not float."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_decimal(v) for v in value]
    return value


def from_decimal(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: from_decimal(v) for k, v in value.items()}
    if isinstance(value, (list, set, tuple)):
        return [from_decimal(v) for v in value]
    return value


def response(status, body):
    # CORS headers are added by the HTTP API CORS configuration.
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(from_decimal(body)),
    }


def claims(event):
    """JWT claims verified by the API Gateway Cognito authorizer."""
    return event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})


def user_groups(event):
    raw = claims(event).get("cognito:groups", "")
    # HTTP API passes the array claim as a string such as "[uploaders]".
    return {g for g in raw.strip("[]").replace(",", " ").split() if g}


def emit_metrics(namespace, dimensions, metrics):
    """Publish custom CloudWatch metrics with Embedded Metric Format (a log line)."""
    payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dimensions)],
                    "Metrics": [{"Name": name, "Unit": "Count"} for name in metrics],
                }
            ],
        },
        **dimensions,
        **metrics,
    }
    print(json.dumps(payload))
