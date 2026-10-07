# Compliance matrix and cloud-service plan

Status meanings: **DONE** = implemented and verified. **NEEDS EVIDENCE** = code
written and verified locally (tests and local run), but not yet deployed and
captured in AWS. **NOT STARTED**. **BLOCKED** = waiting on information from the team.

The official marking rubric has not been supplied. The rubric column below uses
the criteria named in the project brief notes; marks are **unknown**.

## 1. Requirement matrix

| ID | Requirement | Implementation | Cloud service/component | Evidence | Status |
|---|---|---|---|---|---|
| R01 | Project formulation | Sydney air-quality monitoring & alerts on real NSW station data | — | Demo intro, README | DONE (definition) |
| R02 | New tools/technologies | SAM infrastructure as code, Cognito PKCE, SQS + DLQ, CloudWatch EMF metrics, moto local simulation, Chart.js | Several | E02, E33, E34 | NEEDS EVIDENCE |
| R03 | ≥8 cloud services | 10 services (Section 3) | See Section 3 | E02–E26 | NEEDS EVIDENCE |
| R04 | Distributed architecture | Client / API / compute / queue / storage / database / notification tiers | All | E01, E02 | NEEDS EVIDENCE |
| R05 | Processing separate from storage | Stateless Lambdas; data only in S3 + DynamoDB | Lambda vs S3/DynamoDB | E08, E03, E05 | NEEDS EVIDENCE |
| R06 | Additional distributed concept | Message queue + DLQ, event-driven S3 events, pub/sub SNS, scheduled events | SQS, S3 events, SNS, EventBridge | E09, E15–E17, E21, E22 | NEEDS EVIDENCE |
| R07 | Cloud storage | Raw CSV + processed summaries | S3 | E03, E04 | NEEDS EVIDENCE |
| R08 | Cloud database | Daily stats + metadata | DynamoDB | E05–E07 | NEEDS EVIDENCE |
| R09 | Client-side visualisation | 4 Chart.js charts + tiles + tables | Frontend | E28 | NEEDS EVIDENCE (verified locally) |
| R10 | Cloud deployment | CloudFront + one CloudFormation stack | CloudFront, CloudFormation | E02, E26, E27 | NOT STARTED |
| R11 | Security | Cognito, JWT authorizer, uploaders group, IAM least privilege, presigned POST limits, validation, TLS-only buckets, encryption, throttling | Cognito, API GW, IAM, S3 | E04, E12, E14, E30–E32 | NEEDS EVIDENCE |
| R12 | Monitoring | Logs, custom metrics, dashboard, 2 alarms | CloudWatch | E10, E24, E25 | NEEDS EVIDENCE |
| R13 | Testing | 20 automated tests + cloud test plan | pytest/moto | TEST_PLAN.md, E33 | IN PROGRESS (local DONE) |
| R14 | Evidence | 36 planned screenshots | — | EVIDENCE_REGISTER.md | NOT STARTED |
| R15 | Submission structure | code/ deploy/ images/ docs/ tests/ README.md readme.txt | GitHub | E35 | IN PROGRESS (images empty) |
| R16 | Demo 8–10 min | DEMO_SCRIPT.md | — | Video | NOT STARTED |
| R17 | Personalised reflection | Team writes; facts in IMPLEMENTATION_LOG.md | — | — | NOT STARTED (team) |
| R18 | Individual contribution | Owner per service (Section 4) | — | Contribution agreement | BLOCKED (team names) |
| R19 | Works locally | local_server.py with simulated AWS; pytest | moto | E33, E34 | DONE (verified here; screenshots pending) |
| R20 | Dataset with link | OpenAQ archive, 4 Sydney stations, Jan–Jun 2020 | S3 public dataset | readme.txt | DONE |
| R21 | README | README.md | — | file | DONE |
| R22 | Repository URL | github.com/Nafis878/AWS | GitHub | readme.txt | DONE |
| R23 | Signed contribution agreement | Team | — | PDF | BLOCKED (team) |
| R24 | Private demo video | Team records from DEMO_SCRIPT.md | — | link in readme.txt | NOT STARTED |
| R25 | ≤10 slides | Outline in DEMO_SCRIPT.md | — | deck | NOT STARTED |
| R26 | Each member explains contribution | Section 4 ownership | — | demo | BLOCKED (team) |
| R27 | Required report sections | Team writes the report | — | — | BLOCKED (brief not supplied) |

## 2. Rubric view (marks unknown)

| Rubric item | Our strategy | Evidence |
|---|---|---|
| Project formulation | Real public dataset, real events (Jan 2020 bushfire smoke and dust storm) visible in the results | E28, demo |
| New tools & technologies | IaC (SAM), OAuth2 PKCE, queue + DLQ, EMF custom metrics, local cloud simulation | E02, E24, E33, E34 |
| Cloud services (≥8) | 10 services, 2 more than required | E02–E26 |
| Distributed architecture | Asynchronous event-driven pipeline, separate tiers, failure isolation | E01, E09, E15–E17 |
| Evidence | 36 targeted screenshots | images/ |
| Demonstration | Live upload → alert email → charts → CloudWatch | DEMO_SCRIPT.md |
| Reflection | Real problems recorded as they happened | IMPLEMENTATION_LOG.md |

## 3. Cloud-service plan

**Service 1 – Amazon S3**
- Purpose: object storage for raw data, processing summaries and the website files.
- Does: stores uploaded CSVs under `raw/<user>/<upload>.csv`; the processor writes `processed/<upload>.json`; a second bucket holds the frontend.
- Input: browser presigned POST, processor PutObject. Output: ObjectCreated events to SQS; files to CloudFront.
- Integration: S3 event notification → SQS; Origin Access Control → CloudFront.
- Why appropriate: cheap, durable store for write-once files; direct browser upload keeps file data off the API.
- Implementation: `RawBucket`, `SiteBucket`, bucket policies in template.yaml.
- Verify: objects appear after upload. Screenshots E03, E04.

**Service 2 – AWS Lambda**
- Purpose: all compute, serverless and stateless.
- Does: `aqmon-upload-url` issues upload URLs; `aqmon-processor` parses, aggregates and alerts; `aqmon-query` serves the analytics; `aqmon-daily-summary` builds the report.
- Input: API events, SQS batches, EventBridge events. Output: DynamoDB items, S3 objects, SNS messages, JSON responses.
- Why appropriate: scales with each event, no servers to manage, pay per use.
- Implementation: 4 `AWS::Serverless::Function` resources, code in `code/backend/`.
- Verify: logs show executions. Screenshots E08, E09, E10.

**Service 3 – Amazon API Gateway (HTTP API)**
- Purpose: one secure HTTPS entry point for the frontend.
- Does: routes 6 endpoints to Lambda, validates the Cognito JWT, applies CORS and throttling, writes access logs.
- Input: browser requests with an `Authorization` header. Output: Lambda proxy responses.
- Why appropriate: managed authentication and throttling without custom code.
- Implementation: `Api` (`AWS::Serverless::HttpApi`).
- Verify: 200 with a token, 401 without. Screenshots E11–E14.

**Service 4 – Amazon DynamoDB**
- Purpose: database of processed results and application state.
- Does: `aqmon-daily-stats` (pk `station#pollutant`, sk date); `aqmon-meta` (stations, per-user uploads, alerts).
- Input: processor batch writes, upload records. Output: query results for the API.
- Why appropriate: millisecond key/range queries (one station's pollutant over a date range), on-demand scaling, no server.
- Implementation: `DailyStatsTable`, `MetaTable` (on-demand, point-in-time recovery).
- Verify: Explore items. Screenshots E05–E07.

**Service 5 – Amazon SQS (+ dead-letter queue)**
- Purpose: separates uploads from processing.
- Does: buffers S3 events; delivers batches of 5 to the processor; retries failures; moves a message to `aqmon-ingest-dlq` after 3 failed receives.
- Why appropriate: absorbs bursts, guarantees each message is processed or kept, isolates failures.
- Implementation: `IngestQueue`, `IngestDLQ`, `IngestQueuePolicy`, SQS event on the processor.
- Verify: Monitoring tab counts; poison-message test. Screenshots E15–E17, E36.

**Service 6 – Amazon Cognito**
- Purpose: user identity and roles.
- Does: sign-up, email verification, Hosted UI login (OAuth2 code + PKCE), issues the JWT; the `uploaders` group controls who may upload.
- Why appropriate: managed and secure; no passwords are stored by our code.
- Implementation: `UserPool`, `UploadersGroup`, `UserPoolDomain`, `UserPoolClient`.
- Verify: login works; viewer vs uploader. Screenshots E18, E19, E31.

**Service 7 – Amazon SNS**
- Purpose: pub/sub notifications.
- Does: emails exceedance alerts, daily reports and CloudWatch alarm notifications to subscribers.
- Why appropriate: decouples producers (processor, scheduler, alarms) from receivers; more subscribers can be added without code changes.
- Implementation: `AlertTopic` with an email subscription.
- Verify: emails received. Screenshots E20, E21, E23, E25b.

**Service 8 – Amazon CloudWatch**
- Purpose: observability.
- Does: Lambda and API logs (14-day retention), custom `AQMon` metrics written from the processor logs (EMF), the `aqmon-dashboard`, alarms on the DLQ and processor errors.
- Why appropriate: native metrics for every service in one place.
- Implementation: log groups, `Dashboard`, `DlqAlarm`, `ProcessorErrorAlarm`.
- Verify: dashboard populated; alarm fires in the DLQ test. Screenshots E10, E24, E25.

**Service 9 – Amazon EventBridge**
- Purpose: scheduled processing.
- Does: triggers `aqmon-daily-summary` every day at 21:00 UTC.
- Why appropriate: managed cron, no always-on server.
- Implementation: `Schedule` event on `SummaryFunction` (rule `aqmon-daily-report`).
- Verify: rule enabled; report email. Screenshots E22, E23.

**Service 10 – Amazon CloudFront**
- Purpose: public HTTPS hosting of the dashboard.
- Does: serves the private S3 site bucket through Origin Access Control, redirects HTTP to HTTPS, caches at edge locations and adds security headers.
- Why appropriate: HTTPS with no certificate work, private bucket, global low latency.
- Implementation: `Distribution`, `SiteOriginAccessControl`.
- Verify: live URL works on mobile data. Screenshots E26, E27.

(AWS CloudFormation/SAM and IAM are used for deployment and access control. They
are not counted among the 10, but their evidence is in E02 and E32.)

## 4. Suggested ownership (each member owns and explains a slice)

| Member | Owns | Demo segment |
|---|---|---|
| Member 1 | Architecture, SAM template, deployment, CloudFront | Intro + architecture + deployment |
| Member 2 | Processor Lambda, SQS/DLQ, S3 events | Upload → queue → processing → DLQ |
| Member 3 | DynamoDB design, query API, analytics, frontend charts | Database + dashboard analytics |
| Member 4 | Cognito, API Gateway security, SNS, EventBridge, CloudWatch, tests | Security + alerts + monitoring |

Adjust to the real team size and record it in the contribution agreement.
