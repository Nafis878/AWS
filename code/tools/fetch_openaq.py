"""Download Sydney air-quality data from the public OpenAQ archive on AWS.

Source: s3://openaq-data-archive (public bucket, AWS Registry of Open Data),
path records/csv.gz/locationid=<id>/year=<y>/month=<m>/location-<id>-<yyyymmdd>.csv.gz

The script combines the daily files into one CSV per station per month.
Rows are written unchanged (original OpenAQ columns), so the files are the
raw dataset that users upload through the web application.

Usage:
    python code/tools/fetch_openaq.py --start 2020-01 --end 2020-06 --out data/sydney
"""

import argparse
import csv
import gzip
import io
import os
import re
import urllib.parse
import urllib.request

ARCHIVE = "https://openaq-data-archive.s3.amazonaws.com"

# NSW Government air-quality monitoring stations in Sydney (OpenAQ location ids).
STATIONS = {
    7428: "Cook And Phillip (Sydney CBD)",
    7425: "Parramatta North",
    7426: "Macquarie Park",
    7427: "Rouse Hill",
}


def month_range(start, end):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def list_keys(location_id, year, month):
    prefix = f"records/csv.gz/locationid={location_id}/year={year}/month={month:02d}/"
    query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    with urllib.request.urlopen(f"{ARCHIVE}/?{query}", timeout=60) as resp:
        body = resp.read().decode()
    return sorted(re.findall(r"<Key>([^<]+)</Key>", body))


def read_day(key):
    with urllib.request.urlopen(f"{ARCHIVE}/{key}", timeout=60) as resp:
        text = gzip.decompress(resp.read()).decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default="2020-01", help="first month, YYYY-MM")
    parser.add_argument("--end", default="2020-06", help="last month, YYYY-MM")
    parser.add_argument("--out", default="data/sydney")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for location_id, name in STATIONS.items():
        for year, month in month_range(args.start, args.end):
            keys = list_keys(location_id, year, month)
            if not keys:
                print(f"{location_id} {year}-{month:02d}: no files")
                continue
            header, all_rows = None, []
            for key in keys:
                header, rows = read_day(key)
                all_rows.extend(rows)
            path = os.path.join(args.out, f"sydney_{location_id}_{year}-{month:02d}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(all_rows)
            print(f"{location_id} {name} {year}-{month:02d}: {len(keys)} days, {len(all_rows)} rows -> {path}")


if __name__ == "__main__":
    main()
