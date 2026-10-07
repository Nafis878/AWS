#!/usr/bin/env bash
# Give a signed-up user permission to upload data (adds them to the Cognito "uploaders" group).
#   ./deploy/add_uploader.sh someone@example.com
set -euo pipefail
EMAIL="${1:?usage: add_uploader.sh <email>}"
STACK_NAME="${STACK_NAME:-aqmon-stack}"
REGION="${AWS_REGION:-us-east-1}"
POOL_ID="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)"
aws cognito-idp admin-add-user-to-group --region "$REGION" \
  --user-pool-id "$POOL_ID" --username "$EMAIL" --group-name uploaders
echo "$EMAIL is now in the uploaders group. Sign out and sign in again to refresh the token."
