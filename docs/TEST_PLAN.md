# Test plan

Only record actual results. "Not run" means the test has not been executed yet.

## A. Automated tests (local, simulated AWS with moto) – `pytest -v`

Last run in the development environment: **20 passed, 0 failed** (Python 3.13, moto 5.2.3, pytest 9.1.1).
Re-run it on your own machine and capture E33.

| Test ID | Component | Test | Expected | Actual | Status |
|---|---|---|---|---|---|
| A01 | aq_core | Valid OpenAQ rows parsed; station name cleaned | 2 readings, "Cook And Phillip" | As expected | PASS |
| A02 | aq_core | Bad rows (negative, non-numeric, wrong unit, unknown pollutant) rejected | 4 rejected, 1 kept | As expected | PASS |
| A03–A06 | aq_core | Empty file, wrong columns, header only, no valid rows | ValidationError | As expected | PASS |
| A07 | aq_core | Daily aggregation mean/max/min/count | 20/30/10/3 | As expected | PASS |
| A08 | aq_core | Exceedance needs mean > limit and ≥18 hours | 1, 0, 0 | As expected | PASS |
| A09 | aq_core | PM2.5 category bands | Good/Fair/Poor/Extremely poor | As expected | PASS |
| A10 | aq_core | Station summary analytics | average 20, 1 exceedance day | As expected | PASS |
| A11 | aq_core | Real file sydney_7428_2020-01.csv | pm25/pm10/no2/o3 present, exceedances found | As expected | PASS |
| A12 | upload_url | Non-uploader gets 403 | 403 | As expected | PASS |
| A13–A15 | upload_url | Path traversal name, non-CSV, oversize | 400 | As expected | PASS |
| A16 | Pipeline | upload_url → S3 → processor → DynamoDB → query (5 routes) → summary | PROCESSED, data in every route | As expected | PASS |
| A17 | processor | Invalid CSV marked FAILED, not retried | status FAILED, no batch failure | As expected | PASS |
| A18 | processor | Malformed SQS message returned for retry | batchItemFailures contains it | As expected | PASS |
| A19 | processor | Missing S3 object returned for retry | batchItemFailures contains it | As expected | PASS |
| A20 | query | Bad pollutant/date range → 400; unknown route → 404 | 400/400/404 | As expected | PASS |

## B. Local application run – `python code/tools/local_server.py --preload`

Run in the development environment with headless Chromium:

| Test ID | Test | Expected | Actual | Status |
|---|---|---|---|---|
| L01 | Preload 24 Sydney files | All processed without failures | 24 × `batchItemFailures: []` | PASS |
| L02 | Dashboard renders in light and dark mode | Tiles, 4 charts, tables; no JS errors | Rendered; only a favicon 404 (since fixed) | PASS |
| L03 | Upload sydney_7428_2020-01.csv through the UI | Job processed, 2375 rows, 116 daily records, 13 alerts | Exactly these values | PASS |
| L04 | Mobile width 390 px | No horizontal scroll | scrollWidth = 390 | PASS |

## C. Cloud tests (after deployment) – capture evidence as listed

| Test ID | Component | Test | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|
| C01 | Deployment | `deploy.sh` | CREATE_COMPLETE, URLs printed | | Not run | E02 |
| C02 | Frontend | Open SiteUrl on mobile data | Landing page over HTTPS | | Not run | E27 |
| C03 | Auth | Sign up + verify + sign in | Dashboard, viewer badge | | Not run | E19, E31 |
| C04 | Authorisation | Viewer tries to upload | View-only message (API returns 403) | | Not run | E31 |
| C05 | API security | curl without token | 401 | | Not run | E14 |
| C06 | API | DevTools /summary | 200 + JSON | | Not run | E13 |
| C07 | Storage | Upload Jan CBD file | Object in raw/ | | Not run | E03 |
| C08 | Queue | Same upload | SQS sent/deleted +1 | | Not run | E16 |
| C09 | Processing | Same upload | Log "processed upload_id" | | Not run | E10 |
| C10 | Database | Same upload | Items for 7428#pm25 | | Not run | E06 |
| C11 | Notification | Same upload | Alert email with 13 days | | Not run | E21 |
| C12 | Integration | Charts update after upload | New data plotted | | Not run | E28, E29 |
| C13 | Validation | Upload bad.csv | Job FAILED with reason | | Not run | E30 |
| C14 | Fault tolerance | Poison message | DLQ 1 message, alarm, email | | Not run | E17, E25 |
| C15 | Scheduling | Invoke summary / wait for schedule | Report email | | Not run | E23 |
| C16 | Scalability | Upload 23 files at once | All processed, queue drains, concurrency ≤5 | | Not run | E36 |
| C17 | Monitoring | Dashboard widgets | Non-zero metrics | | Not run | E24 |
| C18 | Data correctness | Compare dashboard peak with DynamoDB item | Same value | | Not run | E06 + E28 |
