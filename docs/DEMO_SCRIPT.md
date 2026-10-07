# Demonstration script (about 9 minutes)

**Before recording:**
- Start Learner Lab, if you use it.
- Open these browser tabs: dashboard (signed in as uploader), email inbox,
  CloudWatch dashboard, SQS queue, DynamoDB Explore items, Lambda
  `aqmon-processor` logs, CloudFormation Resources.
- Have a January file ready, e.g. `sydney_7425_2020-01.csv`. Re-uploading a file
  that was uploaded before is fine: processing is idempotent (same DynamoDB keys)
  and it sends the alert email again.
- Close unrelated tabs and hide bookmarks. Make sure no credentials are visible.

| # | Time | What to show | Where to click | What to say (in your own words) | Examiner should notice | Proves |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:45 | Title slide, team | Slides | The problem: Sydney air quality, alerts when the 24-h PM2.5/PM10 limits are breached; real NSW station data from the OpenAQ archive | Clear, real-world problem | Formulation |
| 2 | 0:45–1:45 | Architecture diagram | Slide (E01) | Follow one upload from browser to email alert; name the 10 services and why each is there | Separate tiers, queue, pub/sub | Distributed architecture |
| 3 | 1:45–2:15 | CloudFormation Resources | Stack → Resources | Everything is deployed from one template; repeatable deployment | Real resources, CREATE_COMPLETE | Deployment, new tools |
| 4 | 2:15–3:30 | Live upload | Dashboard → Choose CSV → Upload | The browser gets a presigned URL and uploads straight to S3; the API never handles the file | "queued for processing", status changes to processed | End-to-end flow |
| 5 | 3:30–4:30 | Behind the scenes | SQS Monitoring → Lambda logs → S3 raw/ + processed/ | S3 event → SQS → processor; the logs show the file being processed; the summary is written back | Same timestamps across services | Event-driven processing |
| 6 | 4:30–5:15 | Database | DynamoDB → aqmon-daily-stats → Query `7425#pm25` | Raw hourly data stays in S3; daily aggregates in DynamoDB keyed by station#pollutant and date | Items just written (`source_upload`) | Storage vs processing vs database |
| 7 | 5:15–5:45 | Alert email | Inbox | SNS pub/sub: processor publishes, subscribers receive | Email arrived seconds after upload | Notification |
| 8 | 5:45–7:00 | Analytics | Dashboard: tiles, daily chart, switch to PM10, monthly, exceedances, categories | What the data shows: January 2020 is far above Feb–Jun; the 24 Jan PM10 spike (dust storm) | Real results, interactive charts | Analytics + visualisation |
| 9 | 7:00–7:45 | Security | Sign-in page URL; curl 401; uploaders group | Cognito JWT on every API call, role-based upload, private buckets, least privilege | 401 without a token | Security |
| 10 | 7:45–8:30 | Monitoring + reliability | CloudWatch dashboard; DLQ + alarm (pre-recorded state) | Metrics, custom processing metrics, DLQ keeps failed messages, the alarm emails us | Alarm history, DLQ message | Monitoring, fault tolerance |
| 11 | 8:30–9:00 | Scalability + close | Dashboard SQS widget from the 23-file burst | The queue absorbs bursts, processor concurrency capped at 5, everything else scales on demand; future work | Queue rise and drain | Scalability |

Each member presents the segment they built (COMPLIANCE_MATRIX.md Section 4).

## Slide outline (≤10 slides)

1. Title, team, roles
2. Problem and users
3. Dataset (OpenAQ, 4 stations, Jan–Jun 2020)
4. Architecture diagram
5. Cloud services and why each was chosen (table of 10)
6. Distributed design: event-driven pipeline, queue, DLQ, pub/sub
7. Security design
8. Results (screenshot of the charts + key findings from your live dashboard)
9. Testing and monitoring
10. Challenges, lessons, future work

## Backup plan

If the live upload or email is slow, show the pre-captured E29/E21 screenshots
and the existing job row. Keep the CloudWatch tabs already open on the 3-hour range.
