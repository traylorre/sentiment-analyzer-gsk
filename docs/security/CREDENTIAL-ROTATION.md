# Credential Rotation & Audit Procedures

**Document Purpose:** Standardized procedures for rotating credentials and auditing access

**Audience:** @traylorre (Admin)

**Last Updated:** 2025-11-15

---

## Rotation Schedule

### Mandatory Rotation Intervals

| Credential Type | Rotation Frequency | Notification Period | Owner |
|-----------------|-------------------|---------------------|-------|
| **Contributor AWS Keys** | Every 90 days | 7 days before | @traylorre |
| **Admin AWS Keys** | Every 180 days | Self-managed | @traylorre |
| **Twitter API Keys** | On compromise only | N/A | @traylorre |
| **API Gateway Keys** | Every 180 days | N/A | @traylorre |
| **Terraform Cloud Tokens** | Every 365 days | 30 days before | @traylorre |
| **GitHub PATs** | Every 90 days | Self-managed | Per user |

### Emergency Rotation Triggers

**Rotate immediately if:**
1. Contributor reports credential compromise
2. CloudTrail shows unauthorized access attempts
3. Contributor leaves project
4. Suspicious API call patterns detected
5. Credential accidentally committed to git
6. Twitter API key leaked
7. Any security incident affecting credentials

---

## Contributor AWS Key Rotation

### Scheduled Rotation (Every 90 Days)

**T-7 days: Notify contributor**

```markdown
Subject: AWS Credential Rotation - Action Required

Hello {contributor_name},

Your AWS access credentials for sentiment-analyzer-gsk will be rotated in 7 days.

**Current key expiration:** YYYY-MM-DD
**New credentials will be provided:** YYYY-MM-DD

**Action required:**
1. Wait for new credentials (will be sent on rotation date)
2. Update your local AWS profile
3. Confirm new credentials work
4. Delete old credentials from your system

No action needed until you receive new credentials.

Thanks,
@traylorre
```

**T-0 days: Rotate credentials**

```bash
#!/bin/bash
# rotate-contributor-credentials.sh

CONTRIBUTOR_USER="contributor-alice"
KEY_FILE="contributor-${CONTRIBUTOR_USER}-keys-new.json"

echo "Rotating credentials for ${CONTRIBUTOR_USER}"

# 1. Create new access key
echo "Creating new access key..."
aws iam create-access-key \
  --user-name "${CONTRIBUTOR_USER}" \
  > "${KEY_FILE}"

# 2. Extract credentials
ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' "${KEY_FILE}")
SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' "${KEY_FILE}")

echo "New credentials created:"
echo "Access Key ID: ${ACCESS_KEY}"
echo "Secret Key: ${SECRET_KEY}"

# 3. Send credentials securely (manual step - DO NOT email)
echo ""
echo "⚠️  MANUAL STEP: Send credentials via secure channel"
echo "Options: 1Password share, encrypted email, Signal"
echo ""

# 4. Wait for contributor confirmation
read -p "Has contributor confirmed new credentials work? (yes/no): " CONFIRMED

if [ "$CONFIRMED" != "yes" ]; then
  echo "Aborting - contributor has not confirmed"
  exit 1
fi

# 5. List old access keys
echo "Listing old access keys..."
aws iam list-access-keys --user-name "${CONTRIBUTOR_USER}"

read -p "Enter OLD access key ID to delete: " OLD_KEY_ID

# 6. Delete old access key
echo "Deleting old access key ${OLD_KEY_ID}..."
aws iam delete-access-key \
  --user-name "${CONTRIBUTOR_USER}" \
  --access-key-id "${OLD_KEY_ID}"

echo "✅ Rotation complete!"
echo "Next rotation: $(date -d '+90 days' '+%Y-%m-%d')"

# 7. Add reminder to calendar
echo "Add to calendar: Rotate ${CONTRIBUTOR_USER} credentials on $(date -d '+90 days' '+%Y-%m-%d')"
```

**T+1 day: Verify rotation**

```bash
# Check only one active key exists
aws iam list-access-keys --user-name contributor-alice

# Should show only 1 key (the new one)
```

---

## Emergency Credential Revocation

### Procedure for Suspected Compromise

**Step 1: Immediate Revocation (<5 minutes)**

```bash
#!/bin/bash
# emergency-revoke.sh

CONTRIBUTOR_USER="contributor-alice"

echo "🚨 EMERGENCY REVOCATION for ${CONTRIBUTOR_USER}"

# Delete ALL access keys immediately
aws iam list-access-keys --user-name "${CONTRIBUTOR_USER}" \
  | jq -r '.AccessKeyMetadata[].AccessKeyId' \
  | while read KEY_ID; do
      echo "Deleting access key: ${KEY_ID}"
      aws iam delete-access-key \
        --user-name "${CONTRIBUTOR_USER}" \
        --access-key-id "${KEY_ID}"
    done

echo "✅ All access keys deleted for ${CONTRIBUTOR_USER}"
echo "Contributor has ZERO AWS access now"
```

**Step 2: CloudTrail Investigation (< 30 minutes)**

```bash
# Query CloudTrail for all activity in last 7 days
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=contributor-alice \
  --start-time "$(date -d '7 days ago' --iso-8601)" \
  --end-time "$(date --iso-8601)" \
  > cloudtrail-contributor-alice.json

# Check for unauthorized actions
jq '.Events[] | select(.CloudTrailEvent | contains("errorCode")) | .EventName' \
  cloudtrail-contributor-alice.json

# Red flags:
# - GetSecretValue (attempting Secrets Manager access)
# - PutItem/UpdateItem on DynamoDB (write attempts)
# - InvokeFunction on Lambda
# - CreateAccessKey (attempting to create more credentials)
```

**Step 3: Assess Damage (< 1 hour)**

```bash
# Check what resources were accessed
jq '.Events[] | .EventName' cloudtrail-contributor-alice.json | sort | uniq -c | sort -rn

# Common legitimate actions (safe):
# - DescribeAlarms
# - ListFunctions
# - GetDashboard
# - FilterLogEvents

# Suspicious actions (investigate further):
# - Any Secrets Manager calls
# - Any IAM calls
# - Any DynamoDB PutItem/UpdateItem
# - High volume of ListFunctions (>100/day)
```

**Step 4: Decide on Further Actions**

| Finding | Action |
|---------|--------|
| Only denied API calls | No further action - IAM policies worked correctly |
| Secrets Manager access succeeded | **CRITICAL**: Rotate ALL secrets immediately |
| DynamoDB write succeeded | Review data integrity, restore from backup if needed |
| Lambda invocation succeeded | Review Lambda logs for malicious activity |
| High volume API calls | Check for data exfiltration, review what was accessed |

**Step 5: Notify Contributor**

```markdown
Subject: URGENT: Your AWS credentials have been revoked

Hello {contributor_name},

We detected suspicious activity associated with your AWS credentials and have immediately revoked access as a security precaution.

**Status:** Your AWS access keys have been deleted. You currently have NO AWS access.

**What we detected:**
[Summary of suspicious activity]

**Next steps:**
1. Please confirm whether you were performing the detected actions
2. If not, your credentials may have been compromised
3. Please scan your local machine for malware
4. We will investigate and determine if new credentials can be issued

Please respond within 24 hours.

Thanks,
@traylorre
```

---

## Twitter API Key Rotation

### Procedure

**When to rotate:**
- On suspected compromise only
- NOT on schedule (Twitter doesn't recommend frequent rotation)

**Steps:**

```bash
# 1. Generate new API keys in Twitter Developer Portal
# https://developer.twitter.com/en/portal/projects-and-apps

# 2. Test new keys locally
export TWITTER_API_KEY="new-key"
export TWITTER_API_SECRET="new-secret"
# Run test script

# 3. Update AWS Secrets Manager
aws secretsmanager update-secret \
  --secret-id sentiment-analyzer/twitter-api-key \
  --secret-string '{"api_key":"new-key","api_secret":"new-secret"}'

# 4. Verify Lambda picks up new secret (may take up to 5 minutes due to caching)

# 5. Delete old keys from Twitter Developer Portal

# 6. Monitor for errors in CloudWatch Logs
```

---

## API Gateway API Key Rotation

### Procedure (Every 180 days)

```bash
# 1. Create new API key
aws apigateway create-api-key \
  --name "sentiment-analyzer-api-key-v2" \
  --enabled \
  --query 'id' \
  --output text

NEW_KEY_ID="abc123..."

# 2. Get key value
aws apigateway get-api-key \
  --api-key "${NEW_KEY_ID}" \
  --include-value \
  --query 'value' \
  --output text

NEW_KEY_VALUE="xyz789..."

# 3. Associate with usage plan
aws apigateway create-usage-plan-key \
  --usage-plan-id "usageplan123" \
  --key-id "${NEW_KEY_ID}" \
  --key-type API_KEY

# 4. Notify API consumers of new key (if external)
# "New API key will be required starting YYYY-MM-DD"

# 5. After 30-day transition period, delete old key
aws apigateway delete-api-key --api-key old-key-id
```

---

## Audit Procedures

### Monthly CloudTrail Review

**Run on 1st of each month:**

```bash
#!/bin/bash
# monthly-audit.sh

LAST_MONTH_START=$(date -d 'last month' '+%Y-%m-01')
LAST_MONTH_END=$(date -d 'last day of last month' '+%Y-%m-%d')

echo "Auditing CloudTrail for ${LAST_MONTH_START} to ${LAST_MONTH_END}"

# 1. List all unique users who made API calls
aws cloudtrail lookup-events \
  --start-time "${LAST_MONTH_START}T00:00:00Z" \
  --end-time "${LAST_MONTH_END}T23:59:59Z" \
  | jq -r '.Events[].Username' | sort | uniq

# Expected: traylorre, contributor-alice, contributor-bob, ...

# 2. Check for denied API calls (unauthorized access attempts)
aws cloudtrail lookup-events \
  --start-time "${LAST_MONTH_START}T00:00:00Z" \
  --end-time "${LAST_MONTH_END}T23:59:59Z" \
  | jq '.Events[] | select(.CloudTrailEvent | contains("AccessDenied")) | {User: .Username, Event: .EventName}' \
  | jq -s 'group_by(.User) | map({user: .[0].User, denied_calls: length})'

# Review: High denied_calls count (>10) may indicate probing

# 3. Check for Secrets Manager access attempts
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --start-time "${LAST_MONTH_START}T00:00:00Z" \
  --end-time "${LAST_MONTH_END}T23:59:59Z" \
  | jq '.Events[] | {User: .Username, Time: .EventTime}'

# Expected: Only traylorre or Lambda execution roles

# 4. Check for IAM modifications
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutUserPolicy \
  --start-time "${LAST_MONTH_START}T00:00:00Z" \
  --end-time "${LAST_MONTH_END}T23:59:59Z"

# Expected: Only traylorre

# 5. Generate summary report
echo "=== Monthly Audit Summary ==="
echo "Period: ${LAST_MONTH_START} to ${LAST_MONTH_END}"
echo ""
echo "Total API Calls by User:"
aws cloudtrail lookup-events \
  --start-time "${LAST_MONTH_START}T00:00:00Z" \
  --end-time "${LAST_MONTH_END}T23:59:59Z" \
  | jq -r '.Events[].Username' | sort | uniq -c | sort -rn
```

### Quarterly Permission Review

**Run every 3 months:**

```bash
# 1. List all IAM users
aws iam list-users | jq -r '.Users[].UserName'

# 2. For each contributor, verify:
for USER in $(aws iam list-users | jq -r '.Users[] | select(.UserName | startswith("contributor-")) | .UserName'); do
  echo "Reviewing: ${USER}"

  # Check attached policies
  aws iam list-attached-user-policies --user-name "${USER}"
  # Expected: SentimentAnalyzerContributor only

  # Check access key age
  aws iam list-access-keys --user-name "${USER}" \
    | jq '.AccessKeyMetadata[] | {KeyId: .AccessKeyId, Age: (.CreateDate | fromdateiso8601 | now - . | . / 86400 | floor)}'
  # Flag if age > 90 days

  # Check last activity
  aws iam get-user --user-name "${USER}" \
    | jq '.User.PasswordLastUsed // "Never"'
done

# 3. Remove inactive users
# If user hasn't made API call in >6 months AND no active PRs, offboard
```

---

## Incident Response Checklist

### Credential Compromise Response

**Phase 1: Containment (<5 min)**
- [ ] Revoke compromised credentials immediately
- [ ] Notify @traylorre if not already aware
- [ ] Document time of discovery

**Phase 2: Investigation (<30 min)**
- [ ] Query CloudTrail for all activity from compromised account
- [ ] Identify what resources were accessed
- [ ] Determine if any writes occurred
- [ ] Check for lateral movement (attempted privilege escalation)

**Phase 3: Assessment (<1 hour)**
- [ ] Determine if secrets were accessed
- [ ] Check DynamoDB for data integrity
- [ ] Review Lambda logs for invocations
- [ ] Calculate blast radius

**Phase 4: Remediation**
- [ ] Rotate all potentially compromised secrets
- [ ] Restore data from backup if corrupted
- [ ] Patch vulnerabilities that enabled compromise
- [ ] Update IAM policies if bypass detected

**Phase 5: Communication**
- [ ] Notify affected contributor
- [ ] Document incident in security log
- [ ] Update procedures to prevent recurrence
- [ ] Consider whether to continue contributor relationship

**Phase 6: Lessons Learned**
- [ ] Conduct post-mortem within 7 days
- [ ] Update security documentation
- [ ] Enhance monitoring if gaps identified

---

## Automation Opportunities

### Credential Age Monitoring

**CloudWatch Event Rule + Lambda:**

```python
# Lambda: check-credential-age
import boto3
from datetime import datetime, timedelta

def lambda_handler(event, context):
    iam = boto3.client('iam')
    users = iam.list_users()['Users']

    expiring_soon = []

    for user in users:
        if user['UserName'].startswith('contributor-'):
            keys = iam.list_access_keys(UserName=user['UserName'])['AccessKeyMetadata']
            for key in keys:
                age_days = (datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']).days
                if age_days >= 83:  # 7 days before 90-day limit
                    expiring_soon.append({
                        'user': user['UserName'],
                        'key_id': key['AccessKeyId'],
                        'age_days': age_days
                    })

    if expiring_soon:
        sns = boto3.client('sns')
        sns.publish(
            TopicArn='arn:aws:sns:us-west-2:ACCOUNT:credential-expiration-alerts',
            Subject='Contributor Credentials Expiring Soon',
            Message=f"The following credentials need rotation:\n{expiring_soon}"
        )
```

### Suspicious Activity Alerts

**CloudWatch Insights Query (run daily):**

```
fields @timestamp, userIdentity.principalId, eventName, errorCode
| filter userIdentity.principalId like /contributor-/
| filter errorCode = "AccessDenied"
| stats count() as denied_count by userIdentity.principalId
| filter denied_count > 10
```

**Alert if:** Any contributor has >10 AccessDenied errors in 24 hours

---

**Document Maintainer:** @traylorre
**Review Frequency:** After each incident or quarterly
