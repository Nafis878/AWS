#!/usr/bin/env bash
# Demonstrates the dead-letter queue: sends a message that is not an S3 event.
# The processor rejects it, SQS retries it 3 times, then moves it to aqmon-ingest-dlq,
# which fires the aqmon-dlq-not-empty CloudWatch alarm and an SNS email.
set -euo pipefail
STACK_NAME="${STACK_NAME:-aqmon-stack}"
REGION="${AWS_REGION:-us-east-1}"
QUEUE_URL="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='IngestQueueUrl'].OutputValue" --output text)"
aws sqs send-message --region "$REGION" --queue-url "$QUEUE_URL" \
  --message-body '{"demo": "poison message - not an S3 event notification"}'
echo "Sent. Allow about 10 minutes: each retry waits for the 3-minute visibility timeout."
