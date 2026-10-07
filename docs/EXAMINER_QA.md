# Likely examiner questions – answers based on the actual implementation

Learn the reasoning; don't read these out word for word. File references point to the code.

## Project idea
1. **What problem does it solve?** It turns raw hourly air-quality readings
   into daily statistics, limit-breach alerts and trends for Sydney stations.
   Someone checking pollution exposure, or a council officer, gets an email
   when the 24-h PM2.5 or PM10 limit is breached, and can compare stations and months.
2. **Where does the data come from?** The OpenAQ archive public S3 bucket
   (`openaq-data-archive`): NSW Government stations 7425–7428, Jan–Jun 2020.
   `code/tools/fetch_openaq.py` downloads it unchanged.
3. **Why that period?** Near-complete daily coverage. It includes the end of
   the 2019–20 bushfire season and the 23–24 Jan 2020 dust storm, which show up
   as real exceedances.

## Architecture / distributed systems
4. **Why is this distributed and not one web server?** Upload, processing,
   storage, querying and notification are separate managed services
   communicating over the network and through events. Each scales and fails on
   its own (ARCHITECTURE.md, questions 1–8).
5. **What extra distributed concept did you use?** A message queue with a
   dead-letter queue (SQS), event-driven triggers (S3 events, EventBridge) and
   pub/sub (SNS).
6. **Why put SQS between S3 and Lambda instead of triggering Lambda directly?**
   It buffers bursts, caps concurrency (max 5), retries failed messages
   individually (partial batch response) and keeps poison messages in a DLQ
   instead of losing them.
7. **Is processing synchronous or asynchronous?** Uploads are asynchronous. The
   API returns immediately; the dashboard polls `/uploads` until the job is
   PROCESSED or FAILED.
8. **What happens if the processor crashes halfway through a file?** The
   message isn't deleted. It becomes visible again after 180 s and is retried.
   Writes are idempotent `put_item` on the same keys, so a retry gives the same
   result. After 3 attempts the message goes to the DLQ and the alarm emails us.
9. **What is idempotency here?** Daily records are keyed by station#pollutant
   + date. Processing the same file twice overwrites with identical values and
   creates no duplicates.

## Services
10. **Why Lambda and not EC2?** Work is event-driven and bursty. Lambda scales
    per event with no idle servers or patching; each function has one job.
11. **Why an HTTP API rather than a REST API?** Built-in JWT authorizers for
    Cognito, simpler CORS, lower latency and cost. We don't need REST-API-only
    features such as usage plans.
12. **Why Cognito?** Managed sign-up, email verification, password policy and
    JWTs. Our code never stores passwords. Groups give us authorisation (`uploaders`).
13. **What does EventBridge do?** It triggers the daily operations report at
    21:00 UTC; the report goes out through SNS.
14. **Why CloudFront if S3 can host websites?** HTTPS by default, the bucket
    stays private (Origin Access Control), edge caching and security headers.

## Database and storage
15. **Why DynamoDB and not RDS?** The access pattern is key + range ("station X,
    pollutant Y, dates A–B"), which DynamoDB serves directly with `Query`. It
    needs no server, and on-demand capacity costs nothing when idle.
16. **Explain your key design.** `aqmon-daily-stats`: pk `7428#pm25`, sk
    `2020-01-09`. `aqmon-meta`: pk `STATION`, `USER#<sub>` and `ALERT`, with
    sort keys for the station id, upload id and date. Every dashboard query is
    a `Query`, never a full table scan (only the daily report scans the small meta table).
17. **Why store raw files in S3 and aggregates in DynamoDB?** Raw files are
    large and write-once; they are kept for reprocessing and audit. Aggregates
    are small and queried often. This is the separation of storage from processed data.
18. **How is the data protected?** S3 Block Public Access, TLS-only bucket
    policies, SSE-S3 encryption, versioning on the raw bucket. DynamoDB is
    encrypted at rest with point-in-time recovery.

## API and security
19. **How does a request get authorised?** The browser sends the Cognito ID
    token. API Gateway checks its signature, issuer and audience before
    Lambda runs, so a request without a token gets 401 (E14). The upload
    function also requires the `uploaders` group (403 otherwise).
20. **How do you stop someone uploading huge or harmful files?** The presigned
    POST enforces content type `text/csv` and 1 B–5 MB and expires in 5 min. The
    key is generated server-side under the user's id. The processor validates
    columns, units and values and caps the rows at 50,000. File names are
    validated, and the frontend renders all text with `textContent` (no HTML injection).
21. **Where are the secrets?** There are none in code. Lambda uses IAM roles,
    the Cognito client is public with PKCE, and `config.js` only holds public IDs.
22. **What IAM permissions does the processor have?** Read `raw/*`, write
    `processed/*`, write to two tables, publish to one topic, consume one queue
    (template.yaml `ProcessorRole`). In Learner Lab the platform forces the
    shared LabRole; we say so as a limitation.

## Scalability, performance, cost, reliability
23. **What if 1,000 files are uploaded at once?** S3 and SQS accept them all.
    The processor drains the queue at up to 5 concurrent invocations × 5
    messages. Raise `MaximumConcurrency` to go faster; DynamoDB on-demand absorbs the writes.
24. **Where is the bottleneck?** Deliberately at processor concurrency (to
    protect downstream services). Next would be the API throttle (20 req/s,
    burst 50); both are template settings.
25. **How fast is processing?** Check the processor *Duration* metric on your
    CloudWatch dashboard and quote your measured number. Don't guess.
26. **What does it cost?** Everything is pay-per-use with no always-on servers:
    Lambda, API Gateway, SQS, SNS and DynamoDB on-demand all charge per request.
    At student scale it is a few cents, much of it inside free-tier allowances.
    Check the Billing console for the real amount before quoting it.
27. **How would you make it highly available?** It already uses Multi-AZ
    managed services. For a region outage: DynamoDB global tables, S3
    cross-region replication and a second stack deployed from the same template.

## Monitoring and deployment
28. **How do you know it is working?** CloudWatch dashboard (invocations,
    errors, queue depth, API 4xx/5xx and latency, custom metrics
    FilesProcessed/ExceedancesDetected) plus alarms on DLQ depth and processor errors that email SNS.
29. **How did you deploy?** One SAM/CloudFormation template (`deploy/template.yaml`)
    via `deploy/deploy.sh`. It deploys the stack, generates `config.js` from the
    stack outputs, syncs the site to S3 and invalidates CloudFront.
30. **How did you test?** 20 automated tests (pytest + moto simulating S3,
    SQS, SNS, DynamoDB), including a full pipeline run on a real Sydney file. A
    local server runs the same handlers; then the cloud tests C01–C18.

## Design decisions, problems, future work
31. **What went wrong during development?** See IMPLEMENTATION_LOG.md, e.g.
    the DynamoDB reserved word `parameters` caught by tests, the Learner Lab IAM
    restriction handled with `LabRoleArn`, and data gaps that decided the date range.
32. **Trade-offs?** On-demand DynamoDB is simple but costs more per request at
    very high steady load. Lambda cold starts add latency to the first request.
    Email-only notifications. Polling for job status instead of WebSockets.
33. **Future improvements?** Automatic daily ingestion from live OpenAQ data,
    WebSocket push for job status, SMS/push alerts with per-user station
    subscriptions, forecasting (e.g. SageMaker), and a map view.
34. **What did you personally do?** Each member answers for the slice they own
    (COMPLIANCE_MATRIX.md Section 4) and should be able to walk through that code.
