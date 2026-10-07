# Final zero-error audit (living document – update after each phase)

Current state: code complete and verified locally; **not yet deployed to AWS**.

| Check | Requirement | Implementation | Evidence | Screenshot | Verified | Fix required |
|---|---|---|---|---|---|---|
| ☐ | Project idea defined | AQMon Sydney | README, demo slide 2 | – | Yes | – |
| ☐ | Appropriate technologies | 10 AWS services, SAM, Chart.js | COMPLIANCE_MATRIX §3 | E02 | Design only | Deploy |
| ☐ | ≥8 services implemented | 10 in template.yaml | E02–E26 | 25 files | No (not deployed) | Deploy + capture |
| ☐ | Each service has a genuine purpose | Service plan | COMPLIANCE_MATRIX §3 | – | Yes (design review) | – |
| ☐ | Distributed architecture | S3→SQS→Lambda→DynamoDB, API, SNS | ARCHITECTURE.md | E01 | Locally (simulated) | Draw E01, deploy |
| ☐ | Processing separated from storage | Stateless Lambda; S3 + DynamoDB | E08, E03, E05 | | Locally | Deploy |
| ☐ | Additional distributed concept | SQS + DLQ, events, pub/sub | E09, E15–E17 | | Locally (retry logic tested) | Deploy + DLQ test |
| ☐ | Cloud storage | S3 raw + site | E03, E04 | | No | Deploy |
| ☐ | Cloud database | DynamoDB ×2 | E05–E07 | | No | Deploy |
| ☐ | Client-side visualisation | Chart.js dashboard | E28 | | Locally (Chromium) | Deploy + capture |
| ☐ | Application deployed | CloudFront | E26, E27 | | No | Deploy |
| ☐ | API working | HTTP API | E11–E14 | | Handlers tested locally | Deploy |
| ☐ | Backend working | 4 Lambdas | E08–E10 | | Tested locally | Deploy |
| ☐ | Database connection working | boto3 → DynamoDB | E06, E07 | | Simulated | Deploy |
| ☐ | Storage connection working | Presigned POST, S3 events | E03 | | Simulated | Deploy |
| ☐ | Cloud services working | All | All | | No | Deploy |
| ☐ | Monitoring | CloudWatch | E10, E24, E25 | | No | Deploy |
| ☐ | Security | Cognito, JWT, IAM, S3 policies, validation | E04, E12, E14, E30–E32 | | Validation tested | Deploy |
| ☐ | Testing completed | TEST_PLAN A, B done; C pending | TEST_PLAN.md | E33 | Partly | Run C01–C18 |
| ☐ | Evidence collected | 36 items | EVIDENCE_REGISTER | | No | Capture |
| ☐ | Screenshots prove implementation | Rules in guide | | | No | Review each |
| ☐ | No secrets in screenshots | Checklist | | | No | Review each |
| ☐ | GitHub organised | Folders present | E35 | | Yes | – |
| ☐ | code/ complete | backend, frontend, tools | | | Yes | – |
| ☐ | deploy/ complete | template + 4 scripts | | | Lint passes | Real deploy |
| ☐ | images/ complete | | | | No | Capture |
| ☐ | readme.txt complete | Team names, live URL, video link are TODO | | | No | Fill in |
| ☐ | Live URL verified | | E27 | | No | Deploy |
| ☐ | Demo video prepared | DEMO_SCRIPT.md | | | No | Record |
| ☐ | Examiner questions prepared | EXAMINER_QA.md | | | Yes | Rehearse |
| ☐ | Members understand contribution | Ownership table | | | No | Assign |
| ☐ | Contribution agreement signed | | | | No | Team |
