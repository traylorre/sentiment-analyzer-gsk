# First Production Deploy - Readiness Report

**Date**: 2025-11-22
**Status**: READY WITH SAFEGUARDS ✅
**Estimated Cost**: $5-15/month
**Risk Level**: LOW (with monitoring)

---

## Executive Summary

The system is ready for first production deployment with comprehensive cost controls and monitoring in place. All critical safeguards are configured to prevent runaway costs and overloaded components.

---

## ✅ Cost Controls In Place

### 1. Budget Alarms (AWS Budgets)
**Location**: `infrastructure/terraform/modules/monitoring/main.tf:274-310`

```hcl
resource "aws_budgets_budget" "monthly" {
  limit_amount = var.monthly_budget_limit  # $100 for prod
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  # Alert at $20 (absolute)
  # Alert at 80% ($80)
  # Alert at 100% ($100)
}
```

**Safeguards**:
- ✅ Email alert at $20 (absolute early warning)
- ✅ Email alert at 80% budget ($80/month for $100 budget)
- ✅ Email alert at 100% budget ($100/month)
- ✅ Tagged resources only (Feature=001-interactive-dashboard-demo)

### 2. Lambda Concurrency Limits
**Location**: `infrastructure/terraform/main.tf:127,171,221`

| Lambda | Concurrency | Purpose |
|--------|-------------|---------|
| **Ingestion** | 1 | Prevents event storm, rate limit protection |
| **Analysis** | 5 | Controlled ML processing |
| **Dashboard** | 10 | User-facing requests |

**Safeguards**:
- ✅ Ingestion limited to 1 concurrent execution (critical for cost control)
- ✅ Analysis limited to 5 concurrent executions (prevents ML model overload)
- ✅ Dashboard limited to 10 concurrent executions (user-facing, needs responsiveness)

**Impact**: Even if ingestion is triggered every second, max cost is bounded by 1 execution at a time.

### 3. DynamoDB On-Demand Pricing
- ✅ No provisioned capacity = No waste
- ✅ Auto-scales to zero when idle
- ✅ Pay only for actual reads/writes

### 4. Lambda Reserved Concurrency Prevents Account-Level Blast
- ✅ Account default concurrency (1000) NOT used
- ✅ Each function has explicit limit
- ✅ Total max concurrent: 16 Lambdas (1+5+10)

---

## ✅ Monitoring & Alerting

### CloudWatch Alarms (All Configured)
**Location**: `infrastructure/terraform/modules/monitoring/main.tf`

| Alarm | Threshold | Scenario |
|-------|-----------|----------|
| Ingestion Errors | >3 in 5 min | SC-03 |
| Analysis Errors | >3 in 5 min | SC-04 |
| Dashboard Errors | >5 in 5 min | SC-05 |
| Analysis Latency | P95 >25s | SC-11 |
| Dashboard Latency | P95 >1s | SC-12 |
| SNS Delivery Failures | >5 in 5 min | SC-06 |
| NewsAPI Rate Limit | >0 hits | SC-07 |
| No New Items | 1 hour | SC-10 |
| DLQ Depth | >100 messages | SC-09 |

**All alarms send to**: SNS topic → Email (configured via `alarm_email` variable)

---

## 🎯 Pre-Deployment Checklist

### IMMEDIATE: Before First Deploy

<details>
<summary><strong>1. Get Dashboard Running (Observability First!)</strong></summary>

**Why**: You want metrics visibility BEFORE production traffic hits.

```bash
# Get preprod dashboard URL
cd infrastructure/terraform
terraform output -raw dashboard_function_url

# Test dashboard
curl -H "X-API-Key: $PREPROD_DASHBOARD_API_KEY" \
  https://<preprod-dashboard-url>/health

# Open in browser
open "https://<preprod-dashboard-url>/?api_key=$PREPROD_DASHBOARD_API_KEY"
```

**Verify dashboard shows**:
- [ ] Total items count
- [ ] Sentiment distribution (positive/neutral/negative)
- [ ] Recent items list
- [ ] Metrics update in real-time (SSE stream)

</details>

<details>
<summary><strong>2. Verify Cost Controls (Critical!)</strong></summary>

```bash
# Check budget alarm exists with 3 notifications
aws budgets describe-budgets \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  | grep "prod-sentiment-monthly-budget"

# Verify notification thresholds
aws budgets describe-notifications-for-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget-name prod-sentiment-monthly-budget
# Should show: $20 absolute, 80% percentage, 100% percentage

# Check Lambda concurrency limits
aws lambda get-function-concurrency \
  --function-name prod-sentiment-ingestion
# Should show: ReservedConcurrentExecutions: 1

aws lambda get-function-concurrency \
  --function-name prod-sentiment-analysis
# Should show: ReservedConcurrentExecutions: 5

aws lambda get-function-concurrency \
  --function-name prod-sentiment-dashboard
# Should show: ReservedConcurrentExecutions: 10
```

**Checklist**:
- [ ] Budget alarm configured ($100/month limit)
- [ ] Budget notification at $20 (absolute early warning) ✅ NEW
- [ ] Budget notification at 80% ($80)
- [ ] Budget notification at 100% ($100)
- [ ] Ingestion concurrency = 1 ✅ CRITICAL
- [ ] Analysis concurrency = 5
- [ ] Dashboard concurrency = 10
- [ ] DynamoDB on-demand pricing enabled

</details>

<details>
<summary><strong>3. Review Production Preflight Checklist</strong></summary>

**Location**: `docs/PRODUCTION_PREFLIGHT_CHECKLIST.md`

**Critical Items**:
- [ ] Terraform state verified (separate prod/preprod)
- [ ] Secrets exist in Secrets Manager:
  - `prod/sentiment-analyzer/newsapi`
  - `prod/sentiment-analyzer/dashboard-api-key`
- [ ] CORS origins restricted (TD-002 - defer if internal demo)
- [ ] CloudWatch alarms configured
- [ ] Alarm email configured (will receive notifications)
- [ ] GitHub Secrets configured:
  - `AWS_ACCESS_KEY_ID` (prod credentials)
  - `AWS_SECRET_ACCESS_KEY` (prod credentials)

</details>

<details>
<summary><strong>4. Prepare Andon Cord (Emergency Stop)</strong></summary>

**If you see runaway costs or issues, pull the andon cord IMMEDIATELY:**

```bash
# Option 1: Disable EventBridge scheduler (stops ingestion)
aws events disable-rule --name prod-sentiment-ingestion-scheduler

# Option 2: Set ingestion concurrency to 0 (stops all executions)
aws lambda put-function-concurrency \
  --function-name prod-sentiment-ingestion \
  --reserved-concurrent-executions 0

# Option 3: Delete the EventBridge rule (nuclear option)
aws events delete-rule --name prod-sentiment-ingestion-scheduler

# Verify ingestion stopped
aws lambda get-function \
  --function-name prod-sentiment-ingestion \
  --query 'Configuration.LastUpdateStatus'
```

**Restoration** (after fixing issue):
```bash
# Re-enable scheduler
aws events enable-rule --name prod-sentiment-ingestion-scheduler

# Restore concurrency
aws lambda put-function-concurrency \
  --function-name prod-sentiment-ingestion \
  --reserved-concurrent-executions 1
```

</details>

---

## 🚀 Deployment Execution

### Automatic Deployment (Recommended)

```bash
# 1. Ensure PR #48 is merged (deploy pipeline path filter fix)
gh pr view 48 --repo traylorre/sentiment-analyzer-gsk

# 2. Wait for preprod tests to pass
gh run watch --repo traylorre/sentiment-analyzer-gsk

# 3. Production deploy will automatically trigger after preprod passes
# Monitor at: https://github.com/traylorre/sentiment-analyzer-gsk/actions
```

### Manual Deployment (Backup)

```bash
# Trigger deploy workflow manually
gh workflow run deploy.yml \
  --repo traylorre/sentiment-analyzer-gsk \
  --ref main
```

---

## 📊 Post-Deployment Monitoring

### Immediate (First 10 Minutes)

```bash
# 1. Verify all Lambdas are active
for func in ingestion analysis dashboard; do
  echo "=== prod-sentiment-${func} ==="
  aws lambda get-function --function-name prod-sentiment-${func} \
    --query 'Configuration.State' --output text
done
# All should show: Active

# 2. Check CloudWatch alarms (should be OK)
aws cloudwatch describe-alarms \
  --alarm-name-prefix "prod-" \
  --state-value ALARM
# Should return empty (no alarms firing)

# 3. Test dashboard health
DASHBOARD_URL=$(cd infrastructure/terraform && terraform output -raw dashboard_function_url)
curl -H "X-API-Key: $PROD_DASHBOARD_API_KEY" \
  https://${DASHBOARD_URL}/health
# Should return: {"status":"healthy",...}

# 4. Open dashboard in browser
open "https://${DASHBOARD_URL}/?api_key=$PROD_DASHBOARD_API_KEY"
```

### First Hour

Monitor these metrics every 10 minutes:

```bash
# Lambda invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=prod-sentiment-ingestion \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 600 --statistics Sum

# Lambda errors
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=prod-sentiment-ingestion \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 600 --statistics Sum

# DynamoDB write capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=prod-sentiment-items \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 600 --statistics Sum
```

### First 24 Hours

Watch for:
- ✅ No cost alarms triggered (check email)
- ✅ DynamoDB item count growing steadily
- ✅ No Lambda errors
- ✅ NewsAPI rate limit not hit
- ✅ Dashboard accessible

```bash
# Cost to date (won't show up for ~24 hours)
aws ce get-cost-and-usage \
  --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UnblendedCost \
  --filter file://<(cat <<EOF
{
  "Tags": {
    "Key": "Feature",
    "Values": ["001-interactive-dashboard-demo"]
  }
}
EOF
)
```

---

## 💰 Expected Costs (First Month)

### Baseline (No Traffic)
- DynamoDB (on-demand, idle): **$0.00/month**
- Lambda (no invocations): **$0.00/month**
- CloudWatch Logs (minimal): **$0.50/month**
- **Total idle**: ~$0.50/month

### Production Load (5-minute ingestion schedule)
- **Lambda Invocations**:
  - Ingestion: 8,640/month (every 5 min)
  - Analysis: ~8,640/month (1 per ingestion)
  - Dashboard: ~1,000/month (user access)
  - **Cost**: ~$2-3/month

- **DynamoDB**:
  - Writes: 8,640/month
  - Reads: ~10,000/month (dashboard queries)
  - Storage: ~1 GB
  - **Cost**: ~$2-4/month

- **Data Transfer**: <$1/month

### Total Estimated: **$5-8/month** (well under $100 budget)

### Worst Case (Event Storm)
- Concurrency limits prevent runaway costs
- Max Lambda cost: ~$50/month (if maxed out 24/7)
- Budget alarm triggers at $80

---

## 🚨 Warning Signs & Response

### Cost Alarm (80% budget = $80)

**Response**:
1. Check Cost Explorer for anomaly
2. Review Lambda invocation counts
3. Check for DynamoDB throttling
4. Consider reducing ingestion frequency

### Lambda Errors Spike

**Response**:
1. Check CloudWatch Logs: `/aws/lambda/prod-sentiment-ingestion`
2. Look for NewsAPI rate limit (SC-07)
3. Check DynamoDB write throttling
4. Review recent code changes

### No New Items (1 hour)

**Response**:
1. Check EventBridge scheduler enabled
2. Test NewsAPI manually
3. Check Lambda logs for errors
4. Verify secrets accessible

---

## 📚 References

- **Production Preflight Checklist**: `docs/PRODUCTION_PREFLIGHT_CHECKLIST.md`
- **Failure Recovery Runbook**: `docs/FAILURE_RECOVERY_RUNBOOK.md`
- **Deployment Guide**: `docs/DEPLOYMENT.md`
- **Cost Controls**: `infrastructure/terraform/modules/monitoring/main.tf`
- **Lambda Concurrency**: `infrastructure/terraform/main.tf:127,171,221`

---

## ✅ GO/NO-GO Decision

**GO** if:
- ✅ All cost controls verified
- ✅ Dashboard accessible in preprod
- ✅ Alarm email configured
- ✅ Andon cord procedures understood
- ✅ PR #48 merged (deploy pipeline fix)

**NO-GO** if:
- ❌ Ingestion concurrency != 1
- ❌ Budget alarm not configured
- ❌ Can't access preprod dashboard
- ❌ Prod secrets not in Secrets Manager

---

**Recommendation**: **GO FOR PRODUCTION DEPLOY** ✅

All safeguards in place. Risk is LOW. Monitoring is comprehensive. Andon cord ready.

---

*Generated: 2025-11-22*
*Last Updated: 2025-11-22*
