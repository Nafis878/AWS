/* Copy to config.js and fill in from the CloudFormation stack outputs.
 * deploy/deploy.sh generates config.js automatically. None of these values are secrets. */
window.AQMON_CONFIG = {
  region: "us-east-1",
  apiUrl: "https://<api-id>.execute-api.us-east-1.amazonaws.com",
  userPoolClientId: "<user-pool-client-id>",
  cognitoDomain: "aqmon-<account-id>.auth.us-east-1.amazoncognito.com",
};
