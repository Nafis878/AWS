# Architecture (as implemented in `deploy/template.yaml`)

## Components

| Tier | Component | AWS resource name |
|---|---|---|
| Client | Static dashboard (HTML/JS, Chart.js) | `aqmon-site-<account>-<region>` S3 bucket behind CloudFront |
| Edge | CDN, HTTPS | CloudFront distribution "AQMon dashboard" (Origin Access Control) |
| Identity | Sign-up/sign-in, groups | Cognito user pool `aqmon-users`, group `uploaders`, Hosted UI domain `aqmon-<account>` |
| API | HTTP API, JWT authorizer, CORS, throttling (20 req/s, burst 50) | API Gateway HTTP API `aqmon-stack` |
| Compute (sync) | Upload URL issuer | Lambda `aqmon-upload-url` |
| Compute (sync) | Query and analytics API | Lambda `aqmon-query` |
| Storage | Raw CSV files + processing summaries | S3 `aqmon-raw-<account>-<region>` (`raw/`, `processed/`) |
| Messaging | Ingest buffer + dead-letter queue | SQS `aqmon-ingest-queue`, `aqmon-ingest-dlq` |
| Compute (async) | CSV processor | Lambda `aqmon-processor` (SQS trigger, batch 5, max concurrency 5) |
| Database | Daily statistics; stations, uploads, alerts | DynamoDB `aqmon-daily-stats`, `aqmon-meta` (on-demand, PITR) |
| Notification | Alerts, reports, alarm emails | SNS `aqmon-alerts` |
| Scheduling | Daily report trigger | EventBridge rule `aqmon-daily-report` → Lambda `aqmon-daily-summary` |
| Monitoring | Logs, metrics, dashboard, alarms | CloudWatch log groups, `AQMon` custom metrics, `aqmon-dashboard`, alarms `aqmon-dlq-not-empty`, `aqmon-processor-errors` |

## Data flows

1. **Sign-in:** browser → Cognito Hosted UI (authorization code + PKCE) → ID token (JWT).
2. **Upload:** browser `POST /uploads` (JWT) → API Gateway checks the JWT →
   `aqmon-upload-url` checks the `uploaders` group, validates the name and size,
   and records the upload (`AWAITING_UPLOAD`) in `aqmon-meta` → returns a
   presigned S3 POST (5 min, text/csv, ≤5 MB) → the browser uploads **directly
   to S3**.
3. **Processing (asynchronous):** S3 `ObjectCreated` on `raw/*.csv` → SQS
   message → `aqmon-processor`: parse and validate → aggregate hourly values to
   daily mean/max/min → batch-write `aqmon-daily-stats` → update stations and
   alerts in `aqmon-meta` → write `processed/<id>.json` to S3 → SNS email when a
   24-h mean is above its limit (PM2.5 25, PM10 50 µg/m³) → status `PROCESSED`.
4. **Read:** dashboard → `GET /stations|/daily|/summary|/alerts|/uploads` →
   `aqmon-query` → DynamoDB queries → server-side analytics (averages, peaks,
   exceedance days, monthly means, PM2.5 categories) → JSON → Chart.js draws in the browser.
5. **Scheduled:** EventBridge (21:00 UTC daily) → `aqmon-daily-summary` → scans
   the last 24 h of uploads, reads the DLQ depth → SNS report.
6. **Failure path:** processor error → message returned as a batch item
   failure → SQS retries after the 180 s visibility timeout → after 3 receives,
   moved to the DLQ → CloudWatch alarm → SNS email.

## The eight distributed-systems questions

1. **Which components are distributed?** The client (browser + CDN),
   identity (Cognito), API layer (API Gateway), three independent compute
   services (upload-URL, query, processor) plus the scheduled summary,
   messaging (SQS), storage (S3), database (DynamoDB) and notification (SNS).
   Each is a separately managed service, talking to the others over the network.
2. **Why are they separate?** Each has a different workload. Uploads and
   reads are short and synchronous; processing is heavier and asynchronous.
   Raw files (large, write-once) belong in object storage; aggregated results
   (small, queried by key and date) belong in a key-value database. Keeping
   them apart lets each one scale and fail on its own.
3. **How do they communicate?** HTTPS + JWT between browser and API.
   Synchronous Lambda proxy invocation from API Gateway. Presigned HTTPS POST
   from browser to S3. Asynchronous **events**: S3 → SQS → Lambda event source
   mapping. **Pub/sub**: SNS topic → email subscribers. **Scheduled events**:
   EventBridge → Lambda. AWS SDK calls (IAM-signed) from Lambda to DynamoDB, S3 and SNS.
4. **Where does processing happen?** In `aqmon-processor` (parse, validate,
   aggregate, detect exceedances) and `aqmon-query` (analytics on request).
   The browser only draws charts.
5. **Where is data stored?** Raw files and JSON summaries are in S3. Daily
   statistics, stations, upload status and alerts are in DynamoDB. Nothing is
   stored in Lambda: the functions are stateless.
6. **How does the system scale?** Every tier is managed and scales
   horizontally. CloudFront caches the site at edge locations. API Gateway and
   Lambda scale per request. SQS absorbs bursts (standard queues have virtually unlimited throughput). DynamoDB
   on-demand capacity scales with traffic. The processor's concurrency is capped
   at 5 so a burst can't flood the database.
7. **What happens if traffic increases?** Uploads queue up in SQS instead of
   failing, and the processor drains the queue at a controlled rate (5
   concurrent batches of 5 messages). Read traffic scales with Lambda and
   DynamoDB on-demand. API throttling (20 req/s, burst 50) protects the backend
   and the cost; both limits can be raised in the template.
8. **What happens if a component fails?** If the processor fails, the message
   stays in SQS and is retried; after 3 failures it goes to the DLQ (nothing is
   lost), an alarm fires and an email is sent. Invalid files are marked FAILED
   with a reason and are not retried. Reprocessing is idempotent (same
   DynamoDB keys). If the API or query function fails, uploads already in S3/SQS
   are unaffected. S3 versioning and DynamoDB point-in-time recovery protect
   the data. S3, SQS, DynamoDB and Lambda are all Multi-AZ managed services.

## Diagram specification for `images/01_architecture.png`

Draw it in draw.io/diagrams.net (free) using the AWS icon set, or render the
Mermaid diagram in `README.md`. It must contain exactly these boxes and arrows,
so it matches the deployed stack (E02):

**Boxes:** User (browser) · CloudFront · S3 site bucket · Cognito (Hosted UI,
`uploaders` group) · API Gateway HTTP API (JWT authorizer) · Lambda
upload-url · Lambda query · S3 raw bucket (`raw/`, `processed/`) · SQS ingest
queue · SQS DLQ · Lambda processor · DynamoDB (2 tables) · SNS topic · Email
subscribers · EventBridge rule · Lambda daily-summary · CloudWatch (logs,
metrics, dashboard, alarms) · External: OpenAQ public archive (dataset source).

**Arrows (label each):**
1. User → CloudFront "HTTPS"; CloudFront → S3 site "OAC"
2. User ↔ Cognito "sign-in, JWT"
3. User → API Gateway "REST + JWT"; API Gateway → Lambda upload-url; API Gateway → Lambda query
4. Lambda upload-url → User "presigned POST"; User → S3 raw "upload CSV"
5. S3 raw → SQS "ObjectCreated event"; SQS → Lambda processor "batch"; SQS ⇢ DLQ "after 3 failures"
6. Lambda processor → DynamoDB "daily stats, alerts"; → S3 raw "processed/ summary"; → SNS "exceedance alert"
7. Lambda query → DynamoDB "query"
8. EventBridge → Lambda daily-summary "daily cron"; daily-summary → DynamoDB, → SNS
9. SNS → Email subscribers
10. All Lambdas ⇢ CloudWatch "logs/metrics"; DLQ ⇢ CloudWatch alarm → SNS
11. OpenAQ archive ⇢ `data/sydney` CSV files (dashed, "downloaded with fetch_openaq.py")

Group the boxes into labelled zones: *Client*, *API & identity*,
*Asynchronous processing*, *Storage & database*, *Notification & monitoring*.
