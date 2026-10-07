#!/usr/bin/env bash
# Build and deploy the whole AQMon stack, then publish the frontend.
#
#   ALERT_EMAIL=you@example.com ./deploy/deploy.sh                 # normal AWS account
#   ALERT_EMAIL=you@example.com LEARNER_LAB=1 ./deploy/deploy.sh   # AWS Academy Learner Lab (uses LabRole)
#
# Optional: STACK_NAME (default aqmon-stack), AWS_REGION (default us-east-1)
set -euo pipefail

STACK_NAME="${STACK_NAME:-aqmon-stack}"
REGION="${AWS_REGION:-us-east-1}"
: "${ALERT_EMAIL:?Set ALERT_EMAIL to the address that should receive alerts}"
HERE="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$HERE/../code/frontend"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "Deploying $STACK_NAME to account ****${ACCOUNT_ID: -4} in $REGION"

PARAMS=("AlertEmail=$ALERT_EMAIL")
if [[ "${LEARNER_LAB:-0}" == "1" ]]; then
  PARAMS+=("LabRoleArn=arn:aws:iam::${ACCOUNT_ID}:role/LabRole")
  echo "Learner Lab mode: Lambda functions will use the existing LabRole"
fi

cd "$HERE"
# No "sam build" step: the functions have no third-party dependencies (boto3 is in the
# Lambda runtime), so sam deploy zips code/backend directly. This also means the local
# Python version does not have to match the python3.12 Lambda runtime.
sam deploy \
  --template-file template.yaml \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides "${PARAMS[@]}"

output() {
  aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

API_URL="$(output ApiUrl)"
CLIENT_ID="$(output UserPoolClientId)"
COGNITO_DOMAIN="$(output CognitoDomain)"
SITE_BUCKET="$(output SiteBucketName)"
DISTRIBUTION_ID="$(output DistributionId)"
SITE_URL="$(output SiteUrl)"

# config.js holds public identifiers only (no secrets) and is generated per deployment.
cat > "$FRONTEND/config.js" <<EOF
window.AQMON_CONFIG = {
  region: "$REGION",
  apiUrl: "$API_URL",
  userPoolClientId: "$CLIENT_ID",
  cognitoDomain: "$COGNITO_DOMAIN",
};
EOF

aws s3 sync "$FRONTEND" "s3://$SITE_BUCKET/" --delete --region "$REGION" \
  --exclude "config.example.js" --exclude "vendor/CHARTJS_LICENSE.md"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" >/dev/null

echo
echo "Deployed."
echo "  Dashboard : $SITE_URL"
echo "  API       : $API_URL"
echo "Next: confirm the SNS subscription email, sign up on the dashboard,"
echo "then run deploy/add_uploader.sh <your-email> and sign in again."
