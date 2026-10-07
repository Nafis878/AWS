"""Read API for the dashboard (HTTP API routes, Cognito JWT required).

GET /stations                       monitoring stations seen in uploaded data
GET /daily?parameter=&from=&to=     daily statistics per station
GET /summary?parameter=&from=&to=   analytics: averages, peaks, exceedances, monthly means, categories
GET /alerts                         exceedance days detected by the processor
GET /uploads                        the caller's uploads and their processing status
"""

import os
import re

import boto3
from boto3.dynamodb.conditions import Key

import aq_core
from common import ALLOWED_PARAMETERS, claims, from_decimal, logger, response

DAILY_TABLE = os.environ["DAILY_TABLE"]
META_TABLE = os.environ["META_TABLE"]
LIMITS = {
    "pm25": float(os.environ.get("PM25_DAILY_LIMIT", "25")),
    "pm10": float(os.environ.get("PM10_DAILY_LIMIT", "50")),
}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

dynamodb = boto3.resource("dynamodb")
daily_table = dynamodb.Table(DAILY_TABLE)
meta_table = dynamodb.Table(META_TABLE)


class BadRequest(Exception):
    pass


def handler(event, context):
    route = event.get("routeKey", "")
    params = event.get("queryStringParameters") or {}
    try:
        if route == "GET /stations":
            return response(200, {"stations": list_stations()})
        if route == "GET /daily":
            parameter, date_from, date_to = read_filters(params)
            return response(200, {"parameter": parameter, "records": daily_records(parameter, date_from, date_to)})
        if route == "GET /summary":
            parameter, date_from, date_to = read_filters(params)
            records = daily_records(parameter, date_from, date_to)
            return response(
                200,
                {
                    "parameter": parameter,
                    "limit": LIMITS.get(parameter),
                    "units": records[0]["units"] if records else None,
                    "stations": aq_core.summarise(records, LIMITS.get(parameter)),
                },
            )
        if route == "GET /alerts":
            return response(200, {"alerts": query_all(meta_table, Key("pk").eq("ALERT"), descending=True)[:200]})
        if route == "GET /uploads":
            user_id = claims(event)["sub"]
            items = query_all(meta_table, Key("pk").eq(f"USER#{user_id}"), descending=True)[:50]
            return response(200, {"uploads": items})
    except BadRequest as err:
        return response(400, {"error": str(err)})
    logger.warning("unknown route %s", route)
    return response(404, {"error": "not found"})


def read_filters(params):
    parameter = params.get("parameter", "pm25").lower()
    if parameter not in ALLOWED_PARAMETERS:
        raise BadRequest(f"parameter must be one of {', '.join(ALLOWED_PARAMETERS)}")
    date_from = params.get("from", "1900-01-01")
    date_to = params.get("to", "2999-12-31")
    if not (_DATE_RE.match(date_from) and _DATE_RE.match(date_to)) or date_from > date_to:
        raise BadRequest("from/to must be YYYY-MM-DD dates with from <= to")
    return parameter, date_from, date_to


def list_stations():
    stations = query_all(meta_table, Key("pk").eq("STATION"))
    for s in stations:
        s["station_id"] = s.pop("sk")
        s.pop("pk", None)
        s["parameters"] = sorted(s.get("parameters", []))
    return stations


def daily_records(parameter, date_from, date_to):
    records = []
    for station in list_stations():
        cond = Key("pk").eq(f"{station['station_id']}#{parameter}") & Key("sk").between(date_from, date_to)
        records.extend(query_all(daily_table, cond))
    for r in records:
        r.pop("pk", None)
        r.pop("sk", None)
    return records


def query_all(table, condition, descending=False):
    items, kwargs = [], {"KeyConditionExpression": condition, "ScanIndexForward": not descending}
    while True:
        page = table.query(**kwargs)
        items.extend(page["Items"])
        if "LastEvaluatedKey" not in page:
            return from_decimal(items)
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
