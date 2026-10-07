AQMon Sydney - Air Quality Monitoring & Alert Platform
=======================================================

TEAM (fill in before submission)
  Name: TODO                Student number: TODO
  Name: TODO                Student number: TODO
  Name: TODO                Student number: TODO
  Name: TODO                Student number: TODO

PROJECT DESCRIPTION
  A distributed, event-driven cloud application on AWS for analysing air quality
  in Sydney. Users sign in (Amazon Cognito), upload hourly readings from NSW
  Government monitoring stations, and the files are stored in Amazon S3, queued
  in Amazon SQS and processed by AWS Lambda into daily statistics in Amazon
  DynamoDB. Days above the 24-hour PM2.5/PM10 limits trigger Amazon SNS email
  alerts. A dashboard served through Amazon CloudFront shows trends, monthly
  averages, limit exceedances and pollution categories. Amazon EventBridge sends a
  daily operations report and Amazon CloudWatch monitors every component.

PUBLIC URL
  TODO - paste the SiteUrl output of the CloudFormation stack (https://<id>.cloudfront.net/)

REPOSITORY
  https://github.com/Nafis878/AWS

DEMONSTRATION VIDEO (private/unlisted)
  TODO - paste link

DATASET
  OpenAQ data archive, AWS Registry of Open Data, public bucket s3://openaq-data-archive
  Files: records/csv.gz/locationid=<id>/year=2020/month=<mm>/
  Stations (OpenAQ location ids): 7428 Cook And Phillip (Sydney CBD), 7425 Parramatta North,
  7426 Macquarie Park, 7427 Rouse Hill. Period: January-June 2020.
  Copies used by the application: data/sydney/*.csv
  Download script: code/tools/fetch_openaq.py

FOLDERS
  code/     source code (backend Lambda functions, frontend, tools)
  deploy/   AWS SAM / CloudFormation template and deployment scripts
  images/   evidence screenshots
  docs/     implementation guide, evidence register, test plan
  tests/    automated tests
  data/     dataset files

BASIC INSTRUCTIONS
  Run locally:
    pip install -r requirements-dev.txt
    pytest -q
    python code/tools/local_server.py --preload      then open http://localhost:8080/
  Deploy (AWS CLI + SAM CLI, e.g. in AWS CloudShell):
    ALERT_EMAIL=<email> ./deploy/deploy.sh                (add LEARNER_LAB=1 for AWS Academy)
    confirm the SNS email, sign up on the dashboard, then ./deploy/add_uploader.sh <email>
  Upload the CSV files from data/sydney/ on the dashboard.
  Remove all resources: ./deploy/teardown.sh
