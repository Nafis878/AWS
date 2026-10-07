#!/usr/bin/env bash
# Delete every AQMon resource (empties the buckets first, including old object versions).
set -euo pipefail
STACK_NAME="${STACK_NAME:-aqmon-stack}"
REGION="${AWS_REGION:-us-east-1}"
read -r -p "Delete stack $STACK_NAME and ALL its data in $REGION? Type yes: " answer
[[ "$answer" == "yes" ]] || exit 1

for key in RawBucketName SiteBucketName; do
  bucket="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$key'].OutputValue" --output text)"
  python3 - "$bucket" "$REGION" <<'EOF'
import sys, boto3
bucket, region = sys.argv[1], sys.argv[2]
boto3.resource("s3", region_name=region).Bucket(bucket).object_versions.delete()
print(f"emptied {bucket}")
EOF
done
sam delete --stack-name "$STACK_NAME" --region "$REGION" --no-prompts
