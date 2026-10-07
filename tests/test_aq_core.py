import os

import pytest

import aq_core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = '"location_id","sensors_id","location","datetime","lat","lon","parameter","units","value"\n'


def row(day, hour, value, parameter="pm25", units="µg/m³", station="7428"):
    return (
        f'{station},1,"Cook And Phillip-{station}","2020-01-{day:02d}T{hour:02d}:00:00+11:00",'
        f'-33.8725,151.213333,"{parameter}","{units}",{value}\n'
    )


def test_parses_valid_rows_and_cleans_station_name():
    result = aq_core.parse_openaq_csv(HEADER + row(1, 1, 10) + row(1, 2, 20))
    assert result.rows_total == 2 and result.rows_rejected == 0
    first = result.readings[0]
    assert first.station_name == "Cook And Phillip"
    assert first.date == "2020-01-01"
    assert first.value == 10.0


def test_rejects_bad_rows_but_keeps_good_ones():
    text = HEADER + row(1, 1, 10) + row(1, 2, -3) + row(1, 3, "abc") + row(1, 4, 5, units="ppm") + row(1, 5, 7, parameter="bc")
    result = aq_core.parse_openaq_csv(text)
    assert result.rows_total == 5
    assert result.rows_rejected == 4
    assert [r.value for r in result.readings] == [10.0]


@pytest.mark.parametrize(
    "text,message",
    [
        ("", "empty"),
        ("a,b,c\n1,2,3\n", "missing required columns"),
        (HEADER, "no data rows"),
        (HEADER + row(1, 1, -1), "none of the 1 rows"),
    ],
)
def test_invalid_files_raise_validation_error(text, message):
    with pytest.raises(aq_core.ValidationError, match=message):
        aq_core.parse_openaq_csv(text)


def test_daily_aggregation():
    text = HEADER + "".join(row(1, h, v) for h, v in [(1, 10), (2, 20), (3, 30)]) + row(2, 1, 5)
    daily = aq_core.aggregate_daily(aq_core.parse_openaq_csv(text).readings)
    assert len(daily) == 2
    day1 = daily[0]
    assert (day1["date"], day1["mean"], day1["max"], day1["min"], day1["count"]) == ("2020-01-01", 20.0, 30.0, 10.0, 3)


def test_exceedance_needs_mean_above_limit_and_enough_hours():
    full_day = [{"parameter": "pm25", "mean": 26.0, "count": 23}]
    partial_day = [{"parameter": "pm25", "mean": 80.0, "count": 5}]
    at_limit = [{"parameter": "pm25", "mean": 25.0, "count": 24}]
    assert len(aq_core.find_exceedances(full_day)) == 1
    assert aq_core.find_exceedances(partial_day) == []
    assert aq_core.find_exceedances(at_limit) == []


def test_pm25_categories():
    assert aq_core.pm25_category(10) == "Good"
    assert aq_core.pm25_category(25) == "Fair"
    assert aq_core.pm25_category(99.9) == "Poor"
    assert aq_core.pm25_category(500) == "Extremely poor"


def test_summarise_by_station():
    daily = [
        {"station_id": "1", "station_name": "A", "parameter": "pm25", "date": "2020-01-01", "mean": 30.0, "count": 24},
        {"station_id": "1", "station_name": "A", "parameter": "pm25", "date": "2020-02-01", "mean": 10.0, "count": 24},
    ]
    [station] = aq_core.summarise(daily, limit=25)
    assert station["average"] == 20.0
    assert station["peak_day"] == "2020-01-01"
    assert station["exceedance_days"] == 1
    assert station["monthly"] == {"2020-01": 30.0, "2020-02": 10.0}
    assert station["categories"] == {"Fair": 1, "Good": 1}


def test_real_sydney_file_january_2020():
    path = os.path.join(ROOT, "data", "sydney", "sydney_7428_2020-01.csv")
    with open(path, encoding="utf-8") as f:
        result = aq_core.parse_openaq_csv(f.read())
    daily = aq_core.aggregate_daily(result.readings)
    assert {d["station_name"] for d in daily} == {"Cook And Phillip"}
    assert {d["parameter"] for d in daily} >= {"pm25", "pm10", "no2", "o3"}
    assert aq_core.find_exceedances(daily), "January 2020 (bushfire smoke) should contain exceedance days"
