"""Pure air-quality processing logic (no AWS calls).

Used by the processor Lambda in the cloud and by local tools/tests, so the
same code is exercised locally and in AWS.
"""

import csv
import io
import math
import re
from collections import defaultdict
from dataclasses import dataclass

REQUIRED_COLUMNS = ["location_id", "location", "datetime", "lat", "lon", "parameter", "units", "value"]
MAX_ROWS = 50_000

# Expected units per pollutant in the OpenAQ archive for NSW stations.
EXPECTED_UNITS = {
    "pm25": "µg/m³",
    "pm10": "µg/m³",
    "no2": "ppm",
    "o3": "ppm",
    "co": "ppm",
    "so2": "ppm",
}

# 24-hour average limits used for exceedance alerts. PM2.5 25 and PM10 50 ug/m3
# are the Australian NEPM 1-day standards; override via the Lambda environment.
DEFAULT_DAILY_LIMITS = {"pm25": 25.0, "pm10": 50.0}

# PM2.5 category bands (ug/m3) applied to daily means for the category chart.
PM25_BANDS = [(25.0, "Good"), (50.0, "Fair"), (100.0, "Poor"), (300.0, "Very poor"), (math.inf, "Extremely poor")]

_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})T\d{2}:\d{2}:\d{2}")


class ValidationError(Exception):
    """The uploaded file is not a usable OpenAQ CSV. Not retryable."""


@dataclass(frozen=True)
class Reading:
    station_id: str
    station_name: str
    lat: float
    lon: float
    parameter: str
    units: str
    date: str  # local calendar date of the measurement, YYYY-MM-DD
    value: float


@dataclass
class ParseResult:
    readings: list
    rows_total: int
    rows_rejected: int


def clean_station_name(name, station_id):
    suffix = f"-{station_id}"
    return name[: -len(suffix)] if name.endswith(suffix) else name


def parse_openaq_csv(text):
    """Parse an OpenAQ archive CSV into validated readings.

    Raises ValidationError when the file structure is wrong. Individual bad
    rows (non-numeric, negative or unknown pollutant) are counted and skipped.
    """
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValidationError("file is empty")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise ValidationError(f"missing required columns: {', '.join(missing)}")

    readings, total, rejected = [], 0, 0
    for row in reader:
        total += 1
        if total > MAX_ROWS:
            raise ValidationError(f"file has more than {MAX_ROWS} rows")
        reading = _parse_row(row)
        if reading is None:
            rejected += 1
        else:
            readings.append(reading)

    if total == 0:
        raise ValidationError("file has a header but no data rows")
    if not readings:
        raise ValidationError(f"none of the {total} rows contained a valid measurement")
    return ParseResult(readings, total, rejected)


def _parse_row(row):
    station_id = (row.get("location_id") or "").strip()
    parameter = (row.get("parameter") or "").strip().lower()
    units = (row.get("units") or "").strip()
    match = _DATE_RE.match((row.get("datetime") or "").strip())
    if not station_id.isdigit() or parameter not in EXPECTED_UNITS or not match:
        return None
    if units != EXPECTED_UNITS[parameter]:
        return None
    try:
        value = float(row["value"])
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return Reading(
        station_id=station_id,
        station_name=clean_station_name((row.get("location") or "").strip(), station_id),
        lat=lat,
        lon=lon,
        parameter=parameter,
        units=units,
        date=match.group(1),
        value=value,
    )


def aggregate_daily(readings):
    """Group readings into one record per station, pollutant and day."""
    groups = defaultdict(list)
    meta = {}
    for r in readings:
        key = (r.station_id, r.parameter, r.date)
        groups[key].append(r.value)
        meta[key] = r

    daily = []
    for key in sorted(groups):
        values = groups[key]
        r = meta[key]
        daily.append(
            {
                "station_id": r.station_id,
                "station_name": r.station_name,
                "lat": r.lat,
                "lon": r.lon,
                "parameter": r.parameter,
                "units": r.units,
                "date": r.date,
                "mean": round(sum(values) / len(values), 4),
                "max": round(max(values), 4),
                "min": round(min(values), 4),
                "count": len(values),
            }
        )
    return daily


def find_exceedances(daily, limits=None, min_hours=18):
    """Days whose 24-hour mean is above the limit.

    Days with fewer than ``min_hours`` hourly values are ignored so a few
    smoky hours on a mostly-missing day do not raise a false alert.
    """
    limits = limits or DEFAULT_DAILY_LIMITS
    out = []
    for d in daily:
        limit = limits.get(d["parameter"])
        if limit is not None and d["count"] >= min_hours and d["mean"] > limit:
            out.append({**d, "limit": limit})
    return out


def pm25_category(value):
    for upper, label in PM25_BANDS:
        if value < upper:
            return label
    return PM25_BANDS[-1][1]


def summarise(daily_records, limit=None):
    """Analytics over daily records of ONE pollutant, grouped by station.

    Returns per-station average, peak day, exceedance days, monthly means and
    (for PM2.5) the category distribution. Used by the query API.
    """
    by_station = defaultdict(list)
    for d in daily_records:
        by_station[d["station_id"]].append(d)

    stations = []
    for station_id, days in sorted(by_station.items()):
        means = [d["mean"] for d in days]
        peak = max(days, key=lambda d: d["mean"])
        monthly = defaultdict(list)
        for d in days:
            monthly[d["date"][:7]].append(d["mean"])
        entry = {
            "station_id": station_id,
            "station_name": days[0].get("station_name", station_id),
            "days": len(days),
            "average": round(sum(means) / len(means), 3),
            "peak_day": peak["date"],
            "peak_value": round(peak["mean"], 3),
            "monthly": {m: round(sum(v) / len(v), 3) for m, v in sorted(monthly.items())},
        }
        if limit is not None:
            entry["exceedance_days"] = sum(1 for d in days if d["mean"] > limit and d.get("count", 24) >= 18)
        if days[0]["parameter"] == "pm25":
            categories = defaultdict(int)
            for d in days:
                categories[pm25_category(d["mean"])] += 1
            entry["categories"] = dict(categories)
        stations.append(entry)
    return stations
