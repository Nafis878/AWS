# Implementation guide – deploy, verify, capture evidence

Work through the steps in order. **Take each screenshot as soon as its step
passes verification.** Don't leave screenshots for the end: Learner Lab
sessions expire and recreating an old state is slow.

Every screenshot rule in this guide:

- It comes from **your** account and shows **your** resource names. Every
  resource starts with `aqmon-`.
- Show the AWS **region selector** (top right) in every console screenshot.
- **Never show:** access keys, secret keys or session tokens (Learner Lab
  "AWS Details" panel, `~/.aws/credentials`), the `Authorization` header or any
  JWT token, passwords, or Cognito verification codes. Partly blur personal
  email addresses (e.g. `na***@gmail.com`).
- Save the screenshots to `images/` with the exact filename given, as PNG, uncropped.

Status values: DONE · IN PROGRESS · NOT STARTED · NEEDS EVIDENCE · FAILED · BLOCKED

---

## PHASE 3 – Account and tools

### STEP 3.1 Open a shell that has AWS credentials
- **Objective:** a terminal with AWS CLI v2 + SAM CLI, logged in to your account.
- **Recommended:** AWS CloudShell (the `>_` icon in the console top bar). It
  already has `aws`, `sam`, `git` and `python3`, and it uses your console login.
  You never handle access keys, which is the safest option.
- **Learner Lab:** click *Start Lab*, wait for the green dot, click *AWS*, then
  open CloudShell. Region must be **us-east-1** (N. Virginia).
- **Fallback (your own laptop):** install AWS CLI v2 and SAM CLI, then run
  `aws configure` (normal account). For Learner Lab, paste the *AWS Details →
  AWS CLI* block into `~/.aws/credentials`. **Never screenshot that panel.**
- **Verify:**
  ```bash
  aws sts get-caller-identity --query Arn --output text
  sam --version
  ```
  Expected: an ARN (Learner Lab: `…assumed-role/voclabs/…`) and a SAM version number.
- **Screenshot:** none. This output contains your account ID and proves nothing for the rubric.

### STEP 3.2 Get the code
```bash
git clone https://github.com/Nafis878/AWS.git aqmon && cd aqmon
```

---

## PHASE 4–14 – Deploy all services (infrastructure as code)

### STEP 4.1 Deploy the stack
- **Objective:** create all 10 services in one CloudFormation stack.
- **Command** (use your real email; it receives the alerts):
  ```bash
  # Normal AWS account
  ALERT_EMAIL=you@example.com ./deploy/deploy.sh
  # AWS Academy Learner Lab
  ALERT_EMAIL=you@example.com LEARNER_LAB=1 ./deploy/deploy.sh
  ```
  This takes about 5–10 minutes; CloudFront is the slowest part.
- **Expected:** the script ends with `Deployed.`, the Dashboard URL
  (`https://<id>.cloudfront.net/`) and the API URL.
- **Verify:** CloudFormation → Stacks → `aqmon-stack` shows status `CREATE_COMPLETE`.
- **If it fails:** open the stack → *Events* tab, find the first `CREATE_FAILED`
  row and send me its *Status reason* text. Learner Lab may block a service; I'll adapt the template.
- **Screenshot E02** `02_cloudformation_stack_resources.png`
  - Where: CloudFormation → Stacks → `aqmon-stack` → **Resources** tab.
  - Must show: stack name, status `CREATE_COMPLETE`, the resource list with
    logical IDs and types (S3, SQS, DynamoDB, Lambda, Cognito, SNS, CloudFront,
    CloudWatch, Events, ApiGatewayV2). Zoom out so as many rows as possible fit.
    If they don't all fit, take a second screenshot `02b_…`.
  - Proves: the whole system is deployed as code in your account; the resource list matches the architecture diagram.

### STEP 4.2 Confirm the SNS subscription
- Open the email *"AWS Notification – Subscription Confirmation"* and click **Confirm subscription**.
- **Verify:** SNS → Topics → `aqmon-alerts` → Subscriptions → status `Confirmed`.
- **Screenshot E20** `20_sns_topic_subscription.png`
  - Must show: topic name `aqmon-alerts`, ARN, Subscriptions tab with protocol
    `EMAIL`, status **Confirmed**, endpoint with the email partly blurred.
  - Proves: SNS notification service is configured.

### STEP 4.3 Create the users
1. Open the Dashboard URL. Click **Sign in / Create account**, then **Sign up**, and verify the emailed code.
2. You are now signed in as a **viewer**. The badge says `viewer` and the upload panel says *view-only*.
   - **Screenshot E31** `31_viewer_role_denied.png`: the live dashboard with
     the address bar (cloudfront.net URL), the `viewer` badge and the
     "Your account is view-only…" message. Proves authorisation by role.
3. In the shell: `./deploy/add_uploader.sh you@example.com`
4. **Sign out, then sign in again** (the token must be refreshed to include the group). The badge now says `uploader`.
- **Screenshot E19** `19_cognito_hosted_login.png`
  - Where: the sign-in page that appears after clicking *Sign in*.
  - Must show: the address bar with `aqmon-<account>.auth.us-east-1.amazoncognito.com` and the login form. **Do not type the password before capturing.**
  - Proves: managed authentication (Cognito Hosted UI).
- **Screenshot E18** `18_cognito_user_pool.png`
  - Where: Cognito → User pools → `aqmon-users` → **Users** tab, then the **Groups** tab → `uploaders`.
  - Must show: pool name, at least one user with status *Confirmed*, and the
    `uploaders` group containing your user. Blur email addresses partly. Two
    screenshots are fine (`18a_…users`, `18b_…group`).

---

## PHASE 4 – Storage (S3) + PHASE 9 – distributed pipeline

### STEP 9.1 First upload (end-to-end proof)
- On the dashboard choose `data/sydney/sydney_7428_2020-01.csv` and click **Upload**.
- **Expected:** progress shows `✓ … stored in S3, queued for processing`.
  Within about 10 s the *Processing jobs* row turns **processed** with Rows
  2375, Daily records 116, Alerts 13. An email *"AQMon alert: 13 exceedance
  day(s) detected"* arrives.
  (These numbers come from the local run on the same file. If the cloud shows
  different numbers, tell me.)
- **Screenshot E29** `29_upload_processing_flow.png`: dashboard with the
  upload progress message and the jobs table row *processed* (address bar visible).
- **Screenshot E21** `21_sns_alert_email.png`: the alert email showing the
  subject, sender (AWS Notifications) and the list of exceedance days. Blur your address.

### STEP 9.2 Upload the remaining 23 files at once (scalability)
- Select all the other files in `data/sydney/` in one go and click **Upload**.
- **Verify:** all rows turn *processed*. Lambda concurrency is capped at 5 by the
  SQS event source, so the queue buffers the burst.
- **Screenshot E36** `36_scalability_burst.png`. Take it about 5 minutes later
  (metrics are delayed). Where: CloudWatch → Dashboards → `aqmon-dashboard`, the
  *Ingest queue (SQS)* and *Lambda invocations* widgets. They must show the spike in
  messages sent/deleted and processor invocations. Set the time range to 1 h.

### STEP 4.4 Storage evidence
- **Screenshot E03** `03_s3_raw_bucket_objects.png`
  - Where: S3 → Buckets → `aqmon-raw-<account>-us-east-1` → `raw/` → `<user-id>/`.
  - Must show: bucket name, the CSV objects with sizes and *Last modified* times
    matching your uploads, region. Then open `processed/` and take
    `03b_s3_processed_summaries.png` showing the `.json` summaries written by the processor.
  - Proves: cloud storage holds the application's data; the app writes to it and the processor writes back.
- **Screenshot E04** `04_s3_bucket_security.png`
  - Where: the same bucket → **Permissions** tab.
  - Must show: *Block all public access: On* and the bucket policy statement
    `DenyInsecureTransport`. A second capture of the **Properties** tab →
    *Default encryption: SSE-S3* and *Bucket Versioning: Enabled* is useful (`04b_…`).

---

## PHASE 5 – Database (DynamoDB)

- **Screenshot E05** `05_dynamodb_tables.png`: DynamoDB → Tables showing
  `aqmon-daily-stats` and `aqmon-meta`, status Active, capacity mode On-demand.
- **Screenshot E06** `06_dynamodb_daily_items.png`
  - Where: DynamoDB → Explore items → `aqmon-daily-stats` → **Query**, `pk` = `7428#pm25`.
  - Must show: table name, the query, items with `sk` dates, `mean`, `max`,
    `min`, `count`, `station_name`, `source_upload`.
  - Proves: processed results are stored in the database, separate from the raw files in S3.
- **Screenshot E07** `07_dynamodb_meta_items.png`: Explore items →
  `aqmon-meta` → Scan. Must show `USER#…/UPLOAD#…` items with `status`
  PROCESSED, `STATION` items and `ALERT` items.
- **Check that the app really reads the database:** the dashboard values must
  match the items. Example: E06 item `sk` 2020-01-09, whose `mean` ≈ 69.07,
  appears as "Highest PM2.5 day 69.1, Cook And Phillip, 2020-01-09" once all
  files are uploaded.

---

## PHASE 6 – Backend (Lambda)

- **Screenshot E08** `08_lambda_functions.png`: Lambda → Functions, filter
  `aqmon`. Must show 4 functions (`aqmon-upload-url`, `aqmon-processor`,
  `aqmon-query`, `aqmon-daily-summary`) and runtime Python 3.12.
- **Screenshot E09** `09_lambda_processor_trigger.png`: Lambda →
  `aqmon-processor` → *Function overview*. Must show the **SQS trigger**
  (`aqmon-ingest-queue`). Also open *Configuration → Triggers* to show batch
  size 5 and maximum concurrency 5.
- **Screenshot E10** `10_cloudwatch_processor_logs.png`: CloudWatch → Log groups
  → `/aws/lambda/aqmon-processor` → latest stream. Must show the lines
  `processing s3://aqmon-raw-…/raw/…csv` and `processed upload_id=…` with the
  JSON summary, plus timestamps.

## PHASE 7 – API (API Gateway)

- **Screenshot E11** `11_api_gateway_routes.png`: API Gateway → APIs →
  `aqmon-stack` (HTTP API) → **Routes**. Must show `GET /stations`, `GET
  /daily`, `GET /summary`, `GET /alerts`, `GET /uploads`, `POST /uploads`.
  Click one route; the right panel must show *Authorization: CognitoJwt (JWT)*.
- **Screenshot E12** `12_api_gateway_authorizer.png`: **Authorization** →
  *Manage authorizers* → `CognitoJwt`. Must show the issuer
  `https://cognito-idp.us-east-1.amazonaws.com/<pool-id>` and the audience.
- **Screenshot E13** `13_api_response_devtools.png`
  - Where: the live dashboard → F12 → **Network** tab → click the `summary?parameter=pm25…` request → *Response* or *Preview*.
  - Must show: request URL (`…execute-api.us-east-1.amazonaws.com/summary…`), **Status 200**, JSON with `stations`, `average`, `exceedance_days`.
  - **Do not show the Headers tab** (it contains the Authorization token).
- **Screenshot E14** `14_api_unauthorised_401.png`
  ```bash
  API=$(aws cloudformation describe-stacks --stack-name aqmon-stack --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
  curl -i "$API/summary?parameter=pm25"
  ```
  Expected: `HTTP/2 401` and `{"message":"Unauthorized"}`. Capture the terminal. Proves the API is not publicly readable.

## PHASE 8 – Messaging (SQS) and failure handling

- **Screenshot E15** `15_sqs_queues.png`: SQS → Queues showing
  `aqmon-ingest-queue` and `aqmon-ingest-dlq`. Then open `aqmon-ingest-queue` →
  **Dead-letter queue** tab showing `aqmon-ingest-dlq`, maximum receives 3 (`15b_…`).
- **Screenshot E16** `16_sqs_monitoring.png`: `aqmon-ingest-queue` →
  **Monitoring** tab after the uploads, showing *Number of messages sent /
  received / deleted* with non-zero values.
- **DLQ test:** `./deploy/send_poison_message.sh`, then wait about 10 minutes.
  - **Screenshot E17** `17_sqs_dlq_message.png`: `aqmon-ingest-dlq` →
    *Send and receive messages* → **Poll for messages**. Must show 1 message
    whose body is the demo poison message, with receive count.
  - **Screenshot E25** `25_cloudwatch_alarm_dlq.png`: CloudWatch → Alarms →
    `aqmon-dlq-not-empty` in state **In alarm**, with its graph. The alarm also
    emails SNS; capture that email as `25b_alarm_email.png`.
  - Afterwards purge the DLQ (*Purge*) so the alarm returns to OK.

## PHASE 8 – Scheduled processing (EventBridge)

- **Screenshot E22** `22_eventbridge_rule.png`: EventBridge → Rules →
  `aqmon-daily-report`. Must show the schedule `cron(0 21 * * ? *)`, state
  Enabled, target Lambda `aqmon-daily-summary`.
- Don't wait for the schedule. Run the report now:
  `aws lambda invoke --function-name aqmon-daily-summary /dev/stdout`
  - **Screenshot E23** `23_daily_report_email.png`: the email *"AQMon daily
    report"* listing uploads processed, alerts and dead-letter messages.
  - In the report, say that the function was invoked manually to demonstrate
    it, and that E22 shows the automatic schedule.

## PHASE 10–11 – Frontend and visualisation

- **Screenshot E27** `27_live_site_login.png`: signed-out landing page, address bar showing `https://<id>.cloudfront.net/`.
- **Screenshot E28** `28_dashboard_charts.png`: full dashboard after all 24
  uploads (zoom the browser to 67% or use a full-page capture), with the address
  bar visible. Must show the tiles, the daily-mean chart with the dashed limit
  line, monthly bars, exceedance bars, category mix, station summary and alerts.
  - The examiner should notice the January 2020 peak: every exceedance day is in
    January, during the bushfire smoke and the 23–24 Jan dust storm. Check those
    values on your live dashboard before quoting them.
- **Screenshot E28b** `28b_dashboard_pm10.png`: pollutant switched to PM10.
  The 24 Jan spike (about 150–213 µg/m³) is visible.
- **Screenshot E30** `30_upload_validation_failed.png`
  ```bash
  printf 'name,age\nbob,3\n' > bad.csv
  ```
  Upload `bad.csv`. The jobs row turns **failed**; hover over it to show *missing
  required columns*. Proves input validation and that permanent errors are not retried.

## PHASE 12 – Security

- **Screenshot E32** `32_iam_role_policy.png`
  - **Normal AWS account:** IAM → Roles → `aqmon-processor-role` →
    Permissions → expand `least-privilege`. Shows only S3 Get on `raw/*`, Put on
    `processed/*`, DynamoDB writes on two tables, SNS publish on one topic, SQS
    consume on one queue.
  - **Learner Lab:** you cannot create IAM roles. Capture Lambda →
    `aqmon-processor` → Configuration → Permissions showing the role `LabRole`.
    In the report, name this as a platform limitation and point to the
    least-privilege roles in `deploy/template.yaml` (lines `UploadUrlRole`…`SummaryRole`).
- E04 (S3 security), E12 (JWT authorizer), E14 (401), E30 (validation) and E31 (viewer role) complete the security evidence.

## PHASE 13 – Monitoring

- **Screenshot E24** `24_cloudwatch_dashboard.png`: CloudWatch → Dashboards →
  `aqmon-dashboard`, time range 3 h. Must show invocations, SQS, custom
  *Processing results* metrics (FilesProcessed, ExceedancesDetected), API
  requests and the alarms widget.

## PHASE 14 – Deployment (CloudFront)

- **Screenshot E26** `26_cloudfront_distribution.png`: CloudFront →
  Distributions → the distribution with description *AQMon dashboard*. Must
  show the domain name (same as the live URL), status Enabled, and on the
  *Origins* tab the `aqmon-site-…` S3 origin with Origin access control.
- **Live check:** open the URL on your phone over mobile data (not Wi-Fi).
  Seeing the dashboard proves it is public.

## PHASE 15 – Local run evidence

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
python code/tools/local_server.py --preload
```
- **Screenshot E33** `33_local_tests_passed.png`: the terminal showing `pytest -v` with all tests passed.
- **Screenshot E34** `34_local_app_running.png`: the browser at `http://localhost:8080/` showing the dashboard, with the terminal running `local_server.py` beside it.

## PHASE 17 – Repository

- **Screenshot E35** `35_github_repo_structure.png`: the GitHub repository
  page showing `code/`, `deploy/`, `images/`, `docs/`, `tests/`, `README.md`, `readme.txt`.

## Architecture diagram (E01)

See `docs/ARCHITECTURE.md` for the component and arrow list. Save the drawn diagram as `images/01_architecture.png`.

## Tear down after marking

`./deploy/teardown.sh`. Not before marking: the live URL must work during assessment.
