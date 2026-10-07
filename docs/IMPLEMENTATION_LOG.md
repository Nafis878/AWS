# Implementation log (facts for your reflection; write the reflection yourselves)

Problems, decisions and how they were resolved during the build. Add your own
entries during deployment, e.g. Learner Lab errors and how you fixed them.

| # | Situation | Decision / fix | Why |
|---|---|---|---|
| 1 | Needed a real, citable Sydney dataset reachable without API keys | OpenAQ archive public S3 bucket; scanned location ids to find NSW stations 7425–7428 | No API key or registration; public AWS open data |
| 2 | Sydney stations have gaps in 2021–2022 (e.g. Feb 2022 only 4 days) | Chose Jan–Jun 2020, where the stations have nearly complete daily coverage | Gaps would make the charts and averages misleading |
| 3 | Expected a COVID-lockdown NO₂ drop (Mar–May 2020) | Not claimed: in this data NO₂ rises from Jan to Jun (seasonal winter increase) | Report only what the data shows |
| 4 | Real exceedances found: 65 station-pollutant days, all in January 2020 | Used them as the alert demonstration | Real events (bushfire smoke, 23–24 Jan dust storm) |
| 5 | Very short smoky periods on mostly-missing days could cause false alerts | Exceedance counted only when the day has ≥18 hourly values | Data-quality rule |
| 6 | DynamoDB update failed in testing: `parameters` is a reserved word | Used ExpressionAttributeNames | Found by the automated pipeline test before deployment |
| 7 | Browser file uploads through API Gateway/Lambda would hit payload limits and cost more | Presigned S3 POST with size and content-type conditions | Scales, secure, file bytes never pass through Lambda |
| 8 | Processing time and failures must not affect the user | Asynchronous S3 → SQS → Lambda with partial batch failure reporting and a DLQ | Decoupling and fault isolation |
| 9 | Invalid files would loop forever if retried | Validation errors mark the upload FAILED and are not retried; only unexpected errors retry | Avoid poison-message loops |
| 10 | AWS Academy Learner Lab cannot create IAM roles | Template parameter `LabRoleArn`: roles are created only in normal accounts | Same template works in both |
| 11 | CDN scripts were blocked in the build environment, and a CDN outage would break the demo | Chart.js 4.4.1 (MIT) vendored into `code/frontend/vendor/` | Fewer external dependencies |
| 12 | `sam build` requires the local Python to match the Lambda runtime | Deploy without a build step (no third-party dependencies) | Works in CloudShell and on any laptop |
| 13 | "Works locally" requirement | `local_server.py` runs the same handlers against moto-simulated AWS | Same code locally and in the cloud |
| 14 | Retry demo would take ~18 min with a 60 s timeout | Processor timeout 30 s, visibility timeout 180 s (AWS guidance: 6× the timeout) | DLQ demo in about 10 min |
