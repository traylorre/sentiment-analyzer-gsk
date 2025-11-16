# IAM Role Separation: Admin vs Contributor

**Document Purpose:** Define IAM roles and policies for secure collaboration

**Audience:** @traylorre (for implementation), Contributors (for understanding access boundaries)

**Last Updated:** 2025-11-15

---

## Table of Contents

- [Overview](#overview)
- [Role Definitions](#role-definitions)
- [Admin Role](#admin-role)
- [Contributor Role](#contributor-role)
- [CloudWatch Metrics Filtering](#cloudwatch-metrics-filtering)
- [Credential Management](#credential-management)
- [Implementation Checklist](#implementation-checklist)

---

## Overview

### Security Model

**Principle: Zero-Trust Collaboration**

- **Assumption:** All contributors are potential bad-faith actors
- **Strategy:** Least privilege + defense in depth + comprehensive auditing
- **Goal:** Limit blast radius from compromised contributor accounts

### Role Hierarchy

```
traylorre (Admin)
    ↓ Controls everything
    ↓ Issues credentials
    ↓ Approves all PRs
    ↓
Contributors (Read-Only AWS, No GitHub Merge)
    ↓ Can view non-sensitive metrics
    ↓ Can read logs (sanitized)
    ↓ Can create PRs only
```

---

## Role Definitions

### Comparison Matrix

| Capability | Admin (@traylorre) | Contributor |
|------------|-------------------|-------------|
| **GitHub** |
| Approve PRs | ✅ | ❌ |
| Merge PRs | ✅ | ❌ |
| Modify branch protection | ✅ | ❌ |
| Change repository settings | ✅ | ❌ |
| Create PRs | ✅ | ✅ |
| Comment on PRs | ✅ | ✅ |
| **AWS - Infrastructure** |
| Deploy Terraform | ✅ | ❌ |
| Modify IAM policies | ✅ | ❌ |
| Access Secrets Manager | ✅ | ❌ |
| Rotate credentials | ✅ | ❌ |
| **AWS - Monitoring (Read)** |
| List Lambda functions | ✅ | ✅ (names only) |
| View CloudWatch dashboards | ✅ | ✅ (filtered metrics) |
| Read Lambda logs | ✅ | ✅ (sanitized) |
| View alarm states | ✅ | ✅ |
| **AWS - Monitoring (Write)** |
| Create/modify alarms | ✅ | ❌ |
| Delete dashboards | ✅ | ❌ |
| **AWS - Data Access** |
| Read DynamoDB data | ✅ | ❌ |
| Query DynamoDB | ✅ | ❌ |
| Invoke Lambda functions | ✅ | ❌ |
| **Terraform Cloud** |
| Queue runs | ✅ | ❌ |
| Approve runs | ✅ | ❌ |
| View run history | ✅ | ✅ (read-only) |
| Modify workspaces | ✅ | ❌ |

---

## Admin Role

### IAM Policy: `SentimentAnalyzerAdmin`

**Attached to:** @traylorre's IAM user/role

**Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "FullAdminAccess",
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
```

**Rationale:** Admin needs unrestricted access to deploy, troubleshoot, and manage all infrastructure.

### MFA Requirement

**CRITICAL:** Admin account MUST have MFA enabled.

```bash
# Verify MFA is enabled
aws iam get-user --user-name traylorre | jq '.User.MfaDevices'

# Should show at least one MFA device
```

### Admin Responsibilities

1. **Credential Management:**
   - Create contributor IAM users
   - Generate access keys
   - Rotate credentials every 90 days
   - Revoke compromised credentials immediately

2. **PR Approval:**
   - Review all PRs for security implications
   - Approve and merge after validation
   - Never merge without thorough review

3. **Incident Response:**
   - Investigate CloudTrail logs for suspicious activity
   - Respond to credential compromise reports
   - Rotate secrets if breach suspected

4. **Infrastructure Deployment:**
   - Execute Terraform Cloud runs
   - Deploy Lambda function updates
   - Modify CloudWatch alarms and dashboards

---

## Contributor Role

### IAM Policy: `SentimentAnalyzerContributor`

**Attached to:** Each contributor's IAM user (e.g., `contributor-alice`, `contributor-bob`)

**Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyCloudWatch",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "cloudwatch:DescribeAlarmsForMetric",
        "cloudwatch:GetDashboard",
        "cloudwatch:GetMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListDashboards",
        "cloudwatch:ListMetrics"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Sid": "ReadOnlyLambda",
      "Effect": "Allow",
      "Action": [
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:ListFunctions",
        "lambda:ListTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Sid": "ReadOnlyLogs",
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "arn:aws:logs:us-west-2:*:log-group:/aws/lambda/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Sid": "ReadOnlyDynamoDB",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:ListTables",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:DescribeContinuousBackups"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Sid": "ReadOnlyEventBridge",
      "Effect": "Allow",
      "Action": [
        "events:DescribeRule",
        "events:ListRules",
        "events:ListTargetsByRule"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-west-2"
        }
      }
    },
    {
      "Sid": "DenySecretsManager",
      "Effect": "Deny",
      "Action": "secretsmanager:*",
      "Resource": "*"
    },
    {
      "Sid": "DenyIAM",
      "Effect": "Deny",
      "Action": "iam:*",
      "Resource": "*"
    },
    {
      "Sid": "DenyDynamoDBData",
      "Effect": "Deny",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:BatchGetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyLambdaInvoke",
      "Effect": "Deny",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:InvokeAsync",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:CreateFunction",
        "lambda:DeleteFunction"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyCloudWatchWrite",
      "Effect": "Deny",
      "Action": [
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms",
        "cloudwatch:SetAlarmState",
        "cloudwatch:PutDashboard",
        "cloudwatch:DeleteDashboards"
      ],
      "Resource": "*"
    }
  ]
}
```

### Key Restrictions

**Contributors CANNOT:**
1. Access AWS Secrets Manager (all actions denied)
2. Modify IAM roles/policies
3. Read DynamoDB table data (only schema metadata)
4. Invoke or modify Lambda functions
5. Create/modify CloudWatch alarms or dashboards
6. Access resources outside `us-west-2` region

**Contributors CAN:**
- List Lambda function names and configurations
- View CloudWatch dashboards (but metrics are filtered - see below)
- Read CloudWatch Logs (sanitized via Lambda log filtering)
- Describe DynamoDB table schemas
- View EventBridge rule status
- Check alarm states (OK/ALARM/INSUFFICIENT_DATA)

---

## CloudWatch Metrics Filtering

### Problem

CloudWatch doesn't support per-metric IAM filtering. Contributors with `cloudwatch:GetMetricData` can query **any** metric.

### Solution: Dashboard-Based Access Control

**Strategy:**
1. Create two dashboards:
   - `sentiment-analyzer-contributor-dashboard` (safe metrics only)
   - `sentiment-analyzer-admin-dashboard` (all metrics including sensitive)

2. Contributors access **only** the contributor dashboard
3. Document which metrics are safe vs. sensitive

### Safe Metrics (Contributor Dashboard)

**Lambda Metrics:**
- `Invocations` - Request count
- `Duration` - Execution time (P50, P90, P99)
- `Errors` - Total error count (NOT error details)
- `Throttles` - Throttling count
- `ConcurrentExecutions` - Concurrent invocations

**DynamoDB Metrics:**
- `ConsumedReadCapacityUnits` - Read capacity usage
- `ConsumedWriteCapacityUnits` - Write capacity usage
- `UserErrors` - General user errors (NOT details)

**API Gateway Metrics:**
- `Count` - Total request count
- `4XXError` - Client error count
- `5XXError` - Server error count
- `Latency` - Response latency (P50, P90, P99)

**EventBridge Metrics:**
- `Invocations` - Total rule invocations
- `FailedInvocations` - Failed invocations (NOT reasons)

### Sensitive Metrics (Admin Only - NOT on Contributor Dashboard)

**NEVER expose to contributors:**
- `twitter.quota_utilization_pct` - Reveals quota exhaustion attacks
- `scheduler.scan_duration_ms` - Reveals timing attack patterns
- `dlq.oldest_message_age_days` - Reveals sustained attack duration
- `oauth.refresh_failure_rate` - Reveals OAuth token issues
- `dynamodb.throttled_requests` - Reveals hot partition attacks
- `lambda.memory_utilization_pct` - Reveals memory bomb attacks
- Custom metrics with source-specific breakdowns (enables competitive intelligence)

**Rationale:** These metrics reveal attack patterns, system vulnerabilities, and business-sensitive data.

### Implementation

**Contributor Dashboard Creation:**

```python
# Terraform - Create contributor-safe dashboard
resource "aws_cloudwatch_dashboard" "contributor" {
  dashboard_name = "sentiment-analyzer-contributor"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum" }],
            ["AWS/Lambda", "Duration", { stat = "Average" }],
            ["AWS/Lambda", "Errors", { stat = "Sum" }],
          ]
          title = "Lambda Health (Service Level)"
          region = "us-west-2"
        }
      }
    ]
  })
}
```

**Document access:**
```bash
# Contributors can view this dashboard
aws cloudwatch get-dashboard \
  --dashboard-name sentiment-analyzer-contributor \
  --profile sentiment-analyzer-contributor
```

---

## Credential Management

### Creating Contributor IAM User

**@traylorre procedure:**

```bash
# 1. Create IAM user
aws iam create-user --user-name contributor-alice

# 2. Attach contributor policy
aws iam attach-user-policy \
  --user-name contributor-alice \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SentimentAnalyzerContributor

# 3. Generate access key
aws iam create-access-key --user-name contributor-alice > contributor-alice-keys.json

# 4. Securely send credentials to Alice (NOT via email/Slack)
# Use encrypted channel or 1Password share

# 5. Set expiration reminder (90 days)
# Add to calendar: Rotate contributor-alice credentials on YYYY-MM-DD
```

### Rotating Credentials

**Every 90 days or on compromise:**

```bash
# 1. Notify contributor 7 days in advance
# "Your AWS credentials will be rotated on YYYY-MM-DD. New credentials will be provided."

# 2. Create new access key
aws iam create-access-key --user-name contributor-alice > contributor-alice-keys-new.json

# 3. Send new credentials securely

# 4. After contributor confirms new keys work, delete old key
aws iam list-access-keys --user-name contributor-alice
aws iam delete-access-key \
  --user-name contributor-alice \
  --access-key-id AKIAIOSFODNN7EXAMPLE

# 5. Update rotation calendar for next cycle
```

### Emergency Revocation

**On suspected compromise:**

```bash
# 1. Delete ALL access keys immediately
aws iam list-access-keys --user-name contributor-alice
aws iam delete-access-key \
  --user-name contributor-alice \
  --access-key-id AKIAIOSFODNN7EXAMPLE

# 2. Review CloudTrail logs
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=contributor-alice \
  --start-time 2025-11-01T00:00:00Z \
  --end-time 2025-11-15T23:59:59Z

# 3. If unauthorized activity detected, rotate related secrets
# (Twitter API keys, API Gateway keys, etc.)

# 4. Investigate scope and notify contributor
```

---

## Implementation Checklist

### Initial Setup (@traylorre)

- [ ] Create IAM policy `SentimentAnalyzerContributor` in AWS
- [ ] Create IAM policy `SentimentAnalyzerAdmin` (or use AdministratorAccess)
- [ ] Enable MFA on @traylorre's admin account
- [ ] Create CloudWatch contributor dashboard (safe metrics only)
- [ ] Create CloudWatch admin dashboard (all metrics)
- [ ] Document sensitive metrics in admin notes

### Per-Contributor Onboarding

- [ ] Contributor reads and acknowledges CONTRIBUTING.md
- [ ] Create IAM user: `contributor-{username}`
- [ ] Attach `SentimentAnalyzerContributor` policy
- [ ] Generate access key pair
- [ ] Securely transmit credentials
- [ ] Contributor verifies access with test commands
- [ ] Add credential rotation reminder to calendar (90 days)
- [ ] Grant GitHub repository read+PR permissions (no merge)
- [ ] Add contributor to CODEOWNERS (automatic assignment)

### Per-Contributor Offboarding

- [ ] Delete all access keys
- [ ] Detach IAM policies
- [ ] Delete IAM user
- [ ] Remove GitHub repository access
- [ ] Review CloudTrail logs for final activity
- [ ] Remove from CODEOWNERS (if manually added)

### Ongoing Maintenance

- [ ] Review CloudTrail logs monthly for suspicious activity
- [ ] Rotate contributor credentials every 90 days
- [ ] Update IAM policies if new AWS services added
- [ ] Audit permissions quarterly
- [ ] Review and update sensitive metrics list

---

## Security Notes

### Defense Against Bad-Faith Contributors

**Scenario: Compromised contributor account**

**Damage limitation:**
- ✅ Cannot access production secrets
- ✅ Cannot deploy malicious code (PR approval required)
- ✅ Cannot exfiltrate DynamoDB data
- ✅ Cannot invoke Lambdas to cause service disruption
- ✅ Cannot disable CloudWatch alarms
- ✅ All AWS API calls logged in CloudTrail (audit trail)

**Worst-case impact:**
- Can read Lambda source code (but it's open-source anyway)
- Can see service-level metrics (request counts, error rates)
- Can read sanitized logs (secrets filtered out)
- Can create PR with malicious code (caught in review)

**Recovery time:** < 5 minutes (delete access keys)

### Audit Log Monitoring

**CloudTrail queries to detect abuse:**

```bash
# Check for denied API calls (unauthorized access attempts)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=contributor-alice \
  --start-time 2025-11-01T00:00:00Z \
  --query 'Events[?contains(CloudTrailEvent, `errorCode`)].CloudTrailEvent'

# Check for Secrets Manager access attempts (should all fail)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=GetSecretValue \
  --start-time 2025-11-01T00:00:00Z

# Check for unusual API call volume
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=contributor-alice \
  --start-time 2025-11-15T00:00:00Z \
  --end-time 2025-11-15T23:59:59Z \
  | jq '[.Events[]] | length'
# Typical: <50 calls/day, Suspicious: >500 calls/day
```

---

**Document Maintainer:** @traylorre
**Review Frequency:** Quarterly or on security incident
