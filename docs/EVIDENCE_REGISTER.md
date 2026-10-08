# Evidence register

Status: DONE · IN PROGRESS · NOT STARTED · NEEDS EVIDENCE · FAILED · BLOCKED.
"NEEDS EVIDENCE" means the code exists and passed local tests, but the cloud
deployment and screenshot have not been done yet. Capture instructions:
`docs/IMPLEMENTATION_GUIDE.md`.

| ID | Requirement | Service | Filename | Where | Must be visible | Proves | Status |
|---|---|---|---|---|---|---|---|
| E01 | Architecture | All | 01_architecture.png | Generated from deploy/template.yaml (source: docs/architecture.svg) | Every box and arrow in ARCHITECTURE.md | Distributed design matches what is deployed | DONE |
| E02 | Deployment as code | CloudFormation | 02_cloudformation_stack_resources.png | CloudFormation → aqmon-stack → Resources | CREATE_COMPLETE, resource types | All services deployed in your account | NOT STARTED |
| E03 | Cloud storage | S3 | 03_s3_raw_bucket_objects.png (+03b) | S3 → aqmon-raw-… → raw/, processed/ | Bucket name, uploaded CSVs, JSON summaries, times | Storage holds and is used by the app | NOT STARTED |
| E04 | Storage security | S3 | 04_s3_bucket_security.png (+04b) | Bucket → Permissions / Properties | Block public access On, TLS-only policy, SSE-S3, versioning | Secure storage | NOT STARTED |
| E05 | Cloud database | DynamoDB | 05_dynamodb_tables.png | DynamoDB → Tables | Both tables, Active, On-demand | Database exists | NOT STARTED |
| E06 | Database data | DynamoDB | 06_dynamodb_daily_items.png | Explore items, pk=7428#pm25 | Items with date, mean, max, min, count | Processed results stored | NOT STARTED |
| E07 | Database data | DynamoDB | 07_dynamodb_meta_items.png | Explore items, aqmon-meta | UPLOAD (PROCESSED), STATION, ALERT items | App writes status and alerts | NOT STARTED |
| E08 | Compute | Lambda | 08_lambda_functions.png | Lambda → Functions, filter aqmon | 4 functions, Python 3.12 | Serverless compute deployed | NOT STARTED |
| E09 | Event-driven trigger | Lambda + SQS | 09_lambda_processor_trigger.png | aqmon-processor overview / triggers | SQS trigger, batch 5, max concurrency 5 | Asynchronous processing wiring | NOT STARTED |
| E10 | Processing executed | CloudWatch Logs | 10_cloudwatch_processor_logs.png | /aws/lambda/aqmon-processor | "processing s3://…" and "processed upload_id=…" | Processing really ran | NOT STARTED |
| E11 | API | API Gateway | 11_api_gateway_routes.png | HTTP API → Routes | 6 routes, JWT authorization | API implemented | NOT STARTED |
| E12 | API security | API Gateway + Cognito | 12_api_gateway_authorizer.png | Authorization → CognitoJwt | Issuer, audience | API protected by Cognito | NOT STARTED |
| E13 | API response | API Gateway | 13_api_response_devtools.png | Browser DevTools → Network | URL, 200, JSON body (no headers tab) | API returns real data | NOT STARTED |
| E14 | API security test | API Gateway | 14_api_unauthorised_401.png | Terminal curl | 401 Unauthorized | Requests without a token are rejected | NOT STARTED |
| E15 | Messaging | SQS | 15_sqs_queues.png (+15b) | SQS → Queues / DLQ tab | Both queues, redrive max receives 3 | Queue + DLQ configured | NOT STARTED |
| E16 | Messaging in use | SQS | 16_sqs_monitoring.png | Queue → Monitoring | Messages sent/received/deleted > 0 | Producer/consumer traffic | NOT STARTED |
| E17 | Failure handling | SQS DLQ | 17_sqs_dlq_message.png | DLQ → Poll for messages | The poison message | Failed messages are kept, not lost | NOT STARTED |
| E18 | Authentication | Cognito | 18_cognito_user_pool.png (a/b) | aqmon-users → Users / Groups | Confirmed user, uploaders group | Managed identity + roles | NOT STARTED |
| E19 | Authentication | Cognito | 19_cognito_hosted_login.png | Sign-in page | amazoncognito.com URL, form | Hosted login used by the app | NOT STARTED |
| E20 | Notification | SNS | 20_sns_topic_subscription.png | SNS → aqmon-alerts → Subscriptions | Confirmed email subscription | SNS configured | NOT STARTED |
| E21 | Notification in use | SNS | 21_sns_alert_email.png | Email inbox | Subject "AQMon alert…", exceedance list | Real alert delivered | NOT STARTED |
| E22 | Scheduling | EventBridge | 22_eventbridge_rule.png | EventBridge → Rules | cron, Enabled, Lambda target | Scheduled processing | NOT STARTED |
| E23 | Scheduled output | Lambda + SNS | 23_daily_report_email.png | Email inbox | "AQMon daily report" with counts | Summary job works | NOT STARTED |
| E24 | Monitoring | CloudWatch | 24_cloudwatch_dashboard.png | Dashboards → aqmon-dashboard | All widgets with data | Monitoring implemented | NOT STARTED |
| E25 | Alerting on failure | CloudWatch | 25_cloudwatch_alarm_dlq.png (+25b) | Alarms → aqmon-dlq-not-empty | In alarm + alarm email | Failures are detected | NOT STARTED |
| E26 | Hosting | CloudFront | 26_cloudfront_distribution.png | CloudFront → Distributions | Domain, Enabled, S3 origin with OAC | CDN deployment | NOT STARTED |
| E27 | Live URL | CloudFront + S3 | 27_live_site_login.png | Browser | cloudfront.net URL, landing page | Application is live | NOT STARTED |
| E28 | Visualisation | Frontend | 28_dashboard_charts.png (+28b) | Browser | Tiles, 4 charts, tables, URL | Client-side visualisation of real results | NOT STARTED |
| E29 | End-to-end flow | All | 29_upload_processing_flow.png | Browser | Upload message, job processed | The distributed pipeline works | NOT STARTED |
| E30 | Input validation | Lambda | 30_upload_validation_failed.png | Browser | Job failed + reason | Validation, no retry of bad files | NOT STARTED |
| E31 | Authorisation | Cognito + Lambda | 31_viewer_role_denied.png | Browser | viewer badge, view-only message | Role-based access | NOT STARTED |
| E32 | IAM | IAM | 32_iam_role_policy.png | IAM role / Lambda permissions | Least-privilege policy (or LabRole) | Access control | NOT STARTED |
| E33 | Works locally | pytest | 33_local_tests_passed.png | Your terminal | All tests passed | Tested code | NOT STARTED |
| E34 | Works locally | Local server | 34_local_app_running.png | localhost:8080 | Dashboard running locally | Local execution | NOT STARTED |
| E35 | Submission | GitHub | 35_github_repo_structure.png | GitHub repo page | Required folders and files | Repository organised | NOT STARTED |
| E36 | Scalability | SQS + Lambda + CloudWatch | 36_scalability_burst.png | aqmon-dashboard | Burst of 23 uploads buffered and drained | Elastic, buffered processing | NOT STARTED |

Before submission, check each image in `images/` for:
☐ resource name visible ☐ region visible ☐ no keys/tokens/passwords ☐ emails partly blurred ☐ not cropped so much that context is lost.
