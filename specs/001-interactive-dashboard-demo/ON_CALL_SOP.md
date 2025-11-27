# On-Call Standard Operating Procedures

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-17
**On-Call**: @traylorre (current)
**Escalation**: N/A (single contributor)

---

## Overview

This document provides clear, unambiguous guidance for handling production incidents. Each scenario is mapped to specific alarms and includes step-by-step remediation.

**Philosophy**: The on-call should never be guessing. Every alarm has a known cause list and clear next steps.

---

## Quick Reference: Alarm → Scenario Mapping

| Alarm Name | Scenario | Severity | Page |
|------------|----------|----------|------|
| `dynamodb-user-errors` | [SC-01](#sc-01-dynamodb-user-errors) | HIGH | Jump |
| `dynamodb-system-errors` | [SC-02](#sc-02-dynamodb-throttling) | HIGH | Jump |
| `dynamodb-write-throttles` | [SC-02](#sc-02-dynamodb-throttling) | MEDIUM | Jump |
| `lambda-ingestion-errors` | [SC-03](#sc-03-ingestion-lambda-failures) | HIGH | Jump |
| `lambda-analysis-errors` | [SC-04](#sc-04-analysis-lambda-failures) | HIGH | Jump |
| `lambda-dashboard-errors` | [SC-05](#sc-05-dashboard-unavailable) | HIGH | Jump |
| `sns-delivery-failures` | [SC-06](#sc-06-sns-delivery-failures) | MEDIUM | Jump |
| `api-rate-limit` | [SC-07](#sc-07-api-rate-limit) | LOW | Jump |
| `budget-threshold-80` | [SC-08](#sc-08-cost-overrun) | MEDIUM | Jump |
| `budget-threshold-100` | [SC-08](#sc-08-cost-overrun) | HIGH | Jump |
| `dlq-depth-exceeded` | [SC-09](#sc-09-dlq-backup) | MEDIUM | Jump |
| `no-new-items-1h` | [SC-10](#sc-10-no-data-ingestion) | MEDIUM | Jump |
| `analysis-latency-high` | [SC-11](#sc-11-model-performance-degradation) | MEDIUM | Jump |
| `dashboard-latency-high` | [SC-12](#sc-12-dashboard-slow) | LOW | Jump |

**Other Sections**: [Secrets Management](#secrets-management) (caching, rotation, troubleshooting)

---

## Incident Response Framework

### Severity Levels

| Level | Response Time | Description |
|-------|---------------|-------------|
| **HIGH** | < 15 min | Service down, data loss risk, security incident |
| **MEDIUM** | < 1 hour | Degraded performance, partial outage |
| **LOW** | < 4 hours | Minor issues, no immediate user impact |

### Response Steps (All Incidents)

1. **Acknowledge** - Note the time, alarm name, and initial symptoms
2. **Assess** - Use the scenario guide to identify root cause
3. **Contain** - Stop the bleeding (disable triggers if needed)
4. **Remediate** - Follow the fix steps
5. **Verify** - Confirm service restored
6. **Document** - Update incident log with timeline and actions

---

## Scenario Details

### SC-01: DynamoDB User Errors

**Alarm**: `${environment}-dynamodb-user-errors`
**Trigger**: UserErrors > 10 in 5 minutes
**Severity**: HIGH

**What This Means**: Application is sending malformed requests to DynamoDB.

**Possible Causes** (check in order):

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Schema mismatch after deployment | HIGH | Check recent deployments, compare item schema |
| 2 | Validation bypass in Lambda | MEDIUM | Check CloudWatch logs for validation errors |
| 3 | Corrupted SNS message | LOW | Check DLQ for malformed messages |

**Immediate Actions**:

```bash
# 1. Check recent errors in CloudWatch Logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-ingestion \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Check DynamoDB for recent failed writes
aws dynamodb describe-table \
  --table-name dev-sentiment-items \
  --query 'Table.ItemCount'

# 3. If schema issue, check last successful item
aws dynamodb scan \
  --table-name dev-sentiment-items \
  --limit 1 \
  --scan-filter '{"status":{"AttributeValueList":[{"S":"analyzed"}],"ComparisonOperator":"EQ"}}'
```

**Remediation**:

1. **If schema mismatch**: Roll back Lambda to previous version
   ```bash
   aws lambda update-function-code \
     --function-name dev-sentiment-ingestion \
     --s3-bucket <deployment-bucket> \
     --s3-key <previous-version.zip>
   ```

2. **If validation bypass**: Deploy hotfix with validation, then redeploy

3. **If corrupted messages**: Purge DLQ after analysis
   ```bash
   aws sqs purge-queue --queue-url <dlq-url>
   ```

**Verify Resolution**: UserErrors metric returns to 0 within 5 minutes

---

### SC-02: DynamoDB Throttling

**Alarms**:
- `${environment}-dynamodb-system-errors` (SystemErrors > 5 in 5 min)
- `${environment}-dynamodb-write-throttles` (WCU > 1000 in 1 min)

**Severity**: HIGH (system errors), MEDIUM (write throttles)

**What This Means**: DynamoDB is rejecting requests due to capacity limits.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Traffic spike (legitimate) | MEDIUM | Check ingestion metrics, is it demo time? |
| 2 | Infinite loop in Lambda | HIGH | Check Lambda invocation count spike |
| 3 | Hot partition (single source_id) | LOW | Check CloudWatch Contributor Insights |

**Immediate Actions**:

```bash
# 1. Check current consumed capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedWriteCapacityUnits \
  --dimensions Name=TableName,Value=dev-sentiment-items \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Sum

# 2. Check Lambda invocations (look for spike)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=dev-sentiment-ingestion \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Sum

# 3. If infinite loop suspected, disable trigger immediately
aws events disable-rule --name dev-ingestion-schedule
```

**Remediation**:

1. **If traffic spike (legitimate)**: Wait for on-demand to scale (automatic)

2. **If infinite loop**:
   - Disable EventBridge rule (done above)
   - Check Lambda code for recursion
   - Fix and redeploy
   - Re-enable rule

3. **If hot partition**: Redesign partition key (requires planning)

**Verify Resolution**: SystemErrors and throttle metrics return to 0

---

### SC-03: Ingestion Lambda Failures

**Alarm**: `${environment}-lambda-ingestion-errors`
**Trigger**: Errors > 3 in 5 minutes
**Severity**: HIGH

**What This Means**: Ingestion Lambda is failing to process financial news data.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Tiingo/Finnhub API key invalid/expired | HIGH | Check Secrets Manager, test APIs manually |
| 2 | Tiingo or Finnhub service down | MEDIUM | Check https://api.tiingo.com/status, https://finnhub.io/status |
| 3 | Network timeout | MEDIUM | Check Lambda timeout errors in logs |
| 4 | Code bug after deployment | MEDIUM | Check recent deployments |
| 5 | Memory exhaustion | LOW | Check Lambda memory metrics |

**Immediate Actions**:

```bash
# 1. Check Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-ingestion \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Verify Tiingo API key is valid
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo-api-key \
  --query 'SecretString' --output text | jq -r '.api_key' | \
  xargs -I {} curl -s -H "Authorization: Token {}" "https://api.tiingo.com/tiingo/news?limit=1" | jq '.[0].title'

# 3. Verify Finnhub API key is valid
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/finnhub-api-key \
  --query 'SecretString' --output text | jq -r '.api_key' | \
  xargs -I {} curl -s "https://finnhub.io/api/v1/news?category=general&token={}" | jq '.[0].headline'

# 4. Check Lambda metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=dev-sentiment-ingestion \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Maximum
```

**Remediation**:

1. **If Tiingo API key invalid**:
   ```bash
   # Update Tiingo secret with new key
   aws secretsmanager put-secret-value \
     --secret-id dev/sentiment-analyzer/tiingo-api-key \
     --secret-string '{"api_key":"NEW_KEY_HERE"}'
   ```

2. **If Finnhub API key invalid**:
   ```bash
   # Update Finnhub secret with new key
   aws secretsmanager put-secret-value \
     --secret-id dev/sentiment-analyzer/finnhub-api-key \
     --secret-string '{"api_key":"NEW_KEY_HERE"}'
   ```

3. **If Tiingo/Finnhub down**: Circuit breaker will auto-fallback; wait for recovery

4. **If timeout**: Increase Lambda timeout or reduce batch size

5. **If code bug**: Roll back to previous version

6. **If memory**: Increase Lambda memory allocation

**Verify Resolution**: Next scheduled invocation succeeds (check in 5 min)

---

### SC-04: Analysis Lambda Failures

**Alarm**: `${environment}-lambda-analysis-errors`
**Trigger**: Errors > 3 in 5 minutes
**Severity**: HIGH

**What This Means**: Sentiment analysis is failing.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Model loading failure | HIGH | Check for "Model not found" in logs |
| 2 | Out of memory (OOM) | HIGH | Check Lambda memory metrics, look for 137 exit |
| 3 | Malformed input text | MEDIUM | Check DLQ for bad messages |
| 4 | DynamoDB update failure | MEDIUM | Check for conditional check errors |
| 5 | Lambda layer missing | LOW | Check Lambda configuration |

**Immediate Actions**:

```bash
# 1. Check for OOM errors (exit code 137)
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-analysis \
  --filter-pattern "Runtime exited" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Check memory usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MaxMemoryUsed \
  --dimensions Name=FunctionName,Value=dev-sentiment-analysis \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Maximum

# 3. Check DLQ depth
aws sqs get-queue-attributes \
  --queue-url <dlq-url> \
  --attribute-names ApproximateNumberOfMessages
```

**Remediation**:

1. **If OOM**: Increase Lambda memory to 2048MB
   ```bash
   aws lambda update-function-configuration \
     --function-name dev-sentiment-analysis \
     --memory-size 2048
   ```

2. **If model loading failure**: Verify Lambda layer attachment
   ```bash
   aws lambda get-function-configuration \
     --function-name dev-sentiment-analysis \
     --query 'Layers'
   ```

3. **If malformed input**: Check and purge DLQ, fix validation in ingestion

4. **If DynamoDB failure**: Check SC-01 or SC-02

**Verify Resolution**: Errors metric returns to 0, DLQ stops growing

---

### SC-05: Dashboard Unavailable

**Alarm**: `${environment}-lambda-dashboard-errors`
**Trigger**: Errors > 5 in 5 minutes
**Severity**: HIGH

**What This Means**: Users cannot access the dashboard.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Lambda cold start timeout | MEDIUM | Check duration metrics |
| 2 | DynamoDB query failure | MEDIUM | Check DynamoDB errors |
| 3 | Invalid API key rejection | MEDIUM | Check 401 responses in logs |
| 4 | Function URL misconfigured | LOW | Test URL directly |

**Immediate Actions**:

```bash
# 1. Test dashboard endpoint
DASHBOARD_URL=$(aws lambda get-function-url-config \
  --function-name dev-sentiment-dashboard \
  --query 'FunctionUrl' --output text)

curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL/health"

# 2. Check Lambda errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-dashboard \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 3. Verify API key
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/dashboard-api-key \
  --query 'SecretString' --output text
```

**Remediation**:

1. **If cold start timeout**: Increase timeout or add provisioned concurrency

2. **If DynamoDB failure**: See SC-01 or SC-02

3. **If API key issue**: Verify key matches what user is sending

4. **If Function URL issue**: Recreate via Terraform

**Verify Resolution**: `/health` endpoint returns 200

---

### SC-06: SNS Delivery Failures

**Alarm**: `${environment}-sns-delivery-failures`
**Trigger**: NumberOfNotificationsFailed > 5 in 5 minutes
**Severity**: MEDIUM

**What This Means**: Messages are not reaching the Analysis Lambda.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Lambda throttled | HIGH | Check concurrent executions |
| 2 | Lambda deleted/misconfigured | LOW | Check subscription |
| 3 | IAM permission issue | LOW | Check Lambda resource policy |

**Immediate Actions**:

```bash
# 1. Check SNS subscription
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:us-east-1:...:sentiment-analysis-requests

# 2. Check Lambda throttles
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Throttles \
  --dimensions Name=FunctionName,Value=dev-sentiment-analysis \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

**Remediation**:

1. **If throttled**: Increase reserved concurrency
   ```bash
   aws lambda put-function-concurrency \
     --function-name dev-sentiment-analysis \
     --reserved-concurrent-executions 10
   ```

2. **If subscription missing**: Recreate via Terraform apply

3. **If IAM issue**: Check Lambda resource policy allows SNS

**Verify Resolution**: Delivery failures return to 0

---

### SC-07: API Rate Limit

**Alarm**: `${environment}-api-rate-limit`
**Trigger**: Custom metric TiingoRateLimitHit > 0 OR FinnhubRateLimitHit > 0
**Severity**: LOW

**What This Means**: Hit Tiingo or Finnhub API rate limits.

**Rate Limits**:
- **Tiingo**: 1000 requests/day (free tier), 50,000/day (Power tier)
- **Finnhub**: 60 requests/minute, 300/day (free tier)

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Too many tickers configured | HIGH | Check user configurations |
| 2 | Schedule too frequent | MEDIUM | Check EventBridge rule |
| 3 | Free tier quota exhausted | HIGH | Check CloudWatch metrics |

**Immediate Actions**:

```bash
# 1. Check circuit breaker status
aws dynamodb query \
  --table-name dev-sentiment-items \
  --index-name by_status \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":status": {"S": "circuit_breaker"}}' \
  --limit 5

# 2. Check Tiingo quota usage
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name TiingoRequestCount \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 3600 \
  --statistics Sum

# 3. Check Finnhub quota usage
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name FinnhubRequestCount \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Sum
```

**Remediation**:

1. **Circuit breaker active**: Wait for auto-recovery (60s half-open timeout)

2. **Reduce frequency**: Change EventBridge to every 15 min instead of 5 min

3. **Upgrade plan**:
   - Tiingo: Upgrade to Power tier ($30/month)
   - Finnhub: Upgrade to Basic tier ($29/month)

**Verify Resolution**: Circuit breaker closes, next invocation succeeds

---

### SC-08: Cost Overrun

**Alarms**:
- `${environment}-budget-threshold-80` (80% of monthly budget)
- `${environment}-budget-threshold-100` (100% of monthly budget)

**Severity**: MEDIUM (80%), HIGH (100%)

**What This Means**: AWS costs approaching or exceeding budget.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | DynamoDB write spike | HIGH | Check WCU metrics |
| 2 | Lambda invocation flood | HIGH | Check invocation metrics |
| 3 | CloudWatch Logs explosion | MEDIUM | Check log ingestion |
| 4 | Forgot to tear down resources | MEDIUM | Check running resources |

**Immediate Actions**:

```bash
# 1. Check cost breakdown (requires Cost Explorer API)
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# 2. Pull the andon cord if critical
aws events disable-rule --name dev-ingestion-schedule
aws lambda put-function-concurrency \
  --function-name dev-sentiment-ingestion \
  --reserved-concurrent-executions 0
aws lambda put-function-concurrency \
  --function-name dev-sentiment-analysis \
  --reserved-concurrent-executions 0
```

**Remediation**:

1. **Identify cost driver** from Cost Explorer
2. **Apply specific fix** (reduce frequency, increase TTL, etc.)
3. **Re-enable services** after fix confirmed

**Verify Resolution**: Daily cost trend decreases

---

### SC-09: DLQ Backup

**Alarm**: `${environment}-dlq-depth-exceeded`
**Trigger**: ApproximateNumberOfMessages > 100
**Severity**: MEDIUM

**What This Means**: Failed messages are accumulating.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Analysis Lambda failing (see SC-04) | HIGH | Check analysis errors |
| 2 | Poison message (unprocessable) | MEDIUM | Sample DLQ messages |

**Immediate Actions**:

```bash
# 1. Sample messages from DLQ
aws sqs receive-message \
  --queue-url <dlq-url> \
  --max-number-of-messages 5 \
  --attribute-names All

# 2. Check if Analysis Lambda is healthy
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=dev-sentiment-analysis \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

**Remediation**:

1. **If Analysis Lambda failing**: Fix per SC-04, then replay DLQ
   ```bash
   # Replay messages (manual for now)
   # See plan.md "DLQ Processing Strategy"
   ```

2. **If poison messages**: Delete after analysis
   ```bash
   aws sqs purge-queue --queue-url <dlq-url>
   ```

**Verify Resolution**: DLQ depth decreases to 0

---

### SC-10: No Data Ingestion

**Alarm**: `${environment}-no-new-items-1h`
**Trigger**: NewItemsIngested = 0 for 6 consecutive periods (1 hour)
**Severity**: MEDIUM

**What This Means**: No new articles are being ingested.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | EventBridge rule disabled | HIGH | Check rule state |
| 2 | Tiingo/Finnhub returning empty | MEDIUM | Test APIs manually |
| 3 | All articles are duplicates | MEDIUM | Check dedup metrics |
| 4 | Configured tickers return no results | LOW | Test tickers in Tiingo/Finnhub |

**Immediate Actions**:

```bash
# 1. Check EventBridge rule state
aws events describe-rule --name dev-ingestion-schedule

# 2. Manually invoke ingestion
aws lambda invoke \
  --function-name dev-sentiment-ingestion \
  --payload '{}' \
  /tmp/ingestion-output.json && cat /tmp/ingestion-output.json

# 3. Test Tiingo directly
TIINGO_KEY=$(aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo-api-key \
  --query 'SecretString' --output text | jq -r '.api_key')
curl -s -H "Authorization: Token $TIINGO_KEY" \
  "https://api.tiingo.com/tiingo/news?tickers=AAPL&limit=5" | jq 'length'

# 4. Test Finnhub directly
FINNHUB_KEY=$(aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/finnhub-api-key \
  --query 'SecretString' --output text | jq -r '.api_key')
curl -s "https://finnhub.io/api/v1/company-news?symbol=AAPL&from=$(date -d '7 days ago' +%Y-%m-%d)&to=$(date +%Y-%m-%d)&token=$FINNHUB_KEY" | jq 'length'
```

**Remediation**:

1. **If rule disabled**: Re-enable
   ```bash
   aws events enable-rule --name dev-ingestion-schedule
   ```

2. **If Tiingo/Finnhub empty**: Check if tickers are valid, verify market hours

3. **If all duplicates**: This is normal after initial load, wait for new articles

**Verify Resolution**: NewItemsIngested > 0 in next invocation

---

### SC-11: Model Performance Degradation

**Alarm**: `${environment}-analysis-latency-high`
**Trigger**: Duration P95 > 25000ms (25 seconds)
**Severity**: MEDIUM

**What This Means**: Model inference is slow, approaching timeout.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Cold starts | HIGH | Check init duration |
| 2 | Memory pressure | MEDIUM | Check memory usage |
| 3 | Model corruption | LOW | Redeploy layer |

**Immediate Actions**:

```bash
# 1. Check cold start frequency
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-analysis \
  --filter-pattern "Init Duration" \
  --start-time $(date -d '1 hour ago' +%s)000

# 2. Check memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MaxMemoryUsed \
  --dimensions Name=FunctionName,Value=dev-sentiment-analysis \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Maximum
```

**Remediation**:

1. **If cold starts**: Add provisioned concurrency (costs ~$10/month)
   ```bash
   aws lambda put-provisioned-concurrency-config \
     --function-name dev-sentiment-analysis \
     --qualifier $LATEST \
     --provisioned-concurrent-executions 1
   ```

2. **If memory pressure**: Increase to 2048MB

3. **If model corruption**: Redeploy Lambda layer

**Verify Resolution**: P95 latency drops below 5 seconds

---

### SC-12: Dashboard Slow

**Alarm**: `${environment}-dashboard-latency-high`
**Trigger**: Duration P95 > 1000ms
**Severity**: LOW

**What This Means**: Dashboard queries are slow but functional.

**Possible Causes**:

| # | Cause | Likelihood | How to Verify |
|---|-------|------------|---------------|
| 1 | Large dataset scan | HIGH | Check item count |
| 2 | Cold starts | MEDIUM | Check init duration |
| 3 | DynamoDB throttling | LOW | Check throttle metrics |

**Immediate Actions**:

```bash
# 1. Check table size
aws dynamodb describe-table \
  --table-name dev-sentiment-items \
  --query 'Table.ItemCount'

# 2. Check GSI usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=dev-sentiment-items Name=GlobalSecondaryIndexName,Value=by_status \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

**Remediation**:

1. **If large dataset**: Add pagination, reduce default limit

2. **If cold starts**: Add provisioned concurrency

3. **If throttling**: See SC-02

**Verify Resolution**: P95 latency drops below 500ms

---

## Alarms Required (Must Create)

The following alarms are referenced above but may not exist in Terraform yet:

| Alarm | Resource | Metric | Threshold | Status |
|-------|----------|--------|-----------|--------|
| `lambda-ingestion-errors` | Lambda | Errors | > 3 in 5 min | **MUST CREATE** |
| `lambda-analysis-errors` | Lambda | Errors | > 3 in 5 min | **MUST CREATE** |
| `lambda-dashboard-errors` | Lambda | Errors | > 5 in 5 min | **MUST CREATE** |
| `sns-delivery-failures` | SNS | NumberOfNotificationsFailed | > 5 in 5 min | **MUST CREATE** |
| `tiingo-error-rate` | Custom | TiingoErrors | > 5 in 5 min | ✅ EXISTS |
| `finnhub-error-rate` | Custom | FinnhubErrors | > 5 in 5 min | ✅ EXISTS |
| `circuit-breaker-open` | Custom | CircuitBreakerOpen | > 0 | ✅ EXISTS |
| `budget-threshold-80` | Budget | ACTUAL > 80% | - | **MUST CREATE** |
| `budget-threshold-100` | Budget | ACTUAL > 100% | - | **MUST CREATE** |
| `dlq-depth-exceeded` | SQS | ApproximateNumberOfMessages | > 100 | **MUST CREATE** |
| `no-new-items-1h` | Custom | NewItemsIngested | = 0 for 1h | **MUST CREATE** |
| `analysis-latency-high` | Lambda | Duration P95 | > 25000ms | **MUST CREATE** |
| `dashboard-latency-high` | Lambda | Duration P95 | > 1000ms | **MUST CREATE** |
| `dynamodb-user-errors` | DynamoDB | UserErrors | > 10 in 5 min | ✅ EXISTS |
| `dynamodb-system-errors` | DynamoDB | SystemErrors | > 5 in 5 min | ✅ EXISTS |
| `dynamodb-write-throttles` | DynamoDB | ConsumedWriteCapacityUnits | > 1000 in 1 min | ✅ EXISTS |

---

## Technical Debt: On-Call IAM Role

### Current State

The on-call currently uses personal AWS credentials with admin access.

### Debt to Address (Phase 2)

**Why Create Dedicated On-Call Role**:
1. **Least privilege** - On-call shouldn't have admin access
2. **Audit trail** - Separate role for incident response actions
3. **Credential rotation** - Role credentials rotate automatically
4. **Breakglass** - Emergency access without sharing personal creds

**Proposed IAM Policy** (for future implementation):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOnlyDiagnostics",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:DescribeAlarms",
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "dynamodb:DescribeTable",
        "dynamodb:Scan",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "sqs:GetQueueAttributes",
        "sqs:ReceiveMessage",
        "sns:ListSubscriptionsByTopic",
        "events:DescribeRule",
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Feature": "001-interactive-dashboard-demo"
        }
      }
    },
    {
      "Sid": "EmergencyActions",
      "Effect": "Allow",
      "Action": [
        "events:EnableRule",
        "events:DisableRule",
        "lambda:UpdateFunctionConfiguration",
        "lambda:PutFunctionConcurrency",
        "sqs:PurgeQueue"
      ],
      "Resource": [
        "arn:aws:events:*:*:rule/dev-*",
        "arn:aws:lambda:*:*:function:dev-*",
        "arn:aws:sqs:*:*:dev-*"
      ]
    }
  ]
}
```

### Will This Cause Issues Later?

**No** - Creating a dedicated on-call role later will not cause issues because:

1. **Additive change** - Adding a new role doesn't affect existing setup
2. **No breaking changes** - Current workflows continue to work
3. **Gradual adoption** - Can migrate to role-based access incrementally
4. **Terraform managed** - Easy to add as new IAM module

**Recommended Timeline**:
- Phase 2: Create IAM role and policy
- Phase 2: Test with simulated incidents
- Phase 3: Enforce role usage for all on-call actions

---

## Incident Log Template

Use this template to document incidents:

```markdown
## Incident: [YYYY-MM-DD] [Alarm Name]

**Severity**: HIGH/MEDIUM/LOW
**Duration**: HH:MM - HH:MM (X minutes)
**On-Call**: @username

### Timeline

- HH:MM - Alarm triggered
- HH:MM - Acknowledged
- HH:MM - Root cause identified: [description]
- HH:MM - Remediation started: [action]
- HH:MM - Service restored
- HH:MM - Verified resolution

### Root Cause

[Detailed description of what went wrong]

### Resolution

[What was done to fix it]

### Action Items

- [ ] [Preventive measure 1]
- [ ] [Preventive measure 2]

### Lessons Learned

[What we learned from this incident]
```

---

## Secrets Management

### Secrets Caching Architecture

All Lambdas use a centralized secrets caching module (`src/lambdas/shared/secrets.py`) with:

- **5-minute TTL**: Secrets auto-refresh after 5 minutes
- **In-memory cache**: Reduces API calls during Lambda warm invocations
- **Automatic cold start refresh**: Cache clears on Lambda cold start (memory isolation)

### When Secrets Are Refreshed

| Event | Cache Behavior |
|-------|----------------|
| Lambda cold start | Cache empty, fetches fresh |
| Within 5 min of last fetch | Returns cached value |
| After 5 min TTL expires | Fetches fresh on next access |
| Manual `force_refresh=True` | Bypasses cache, fetches fresh |

### Forcing Secret Refresh

**Option 1: Wait for TTL (Recommended)**
- Secrets automatically refresh within 5 minutes
- No action needed for routine rotations

**Option 2: Force Lambda Cold Start**
```bash
# Update an env var to force cold start (reverts instantly)
aws lambda update-function-configuration \
  --function-name dev-sentiment-dashboard \
  --environment "Variables={FORCE_COLD_START=$(date +%s)}"
```

**Option 3: Use force_refresh in Code**
```python
from src.lambdas.shared.secrets import get_secret
secret = get_secret("dev/sentiment-analyzer/tiingo-api-key", force_refresh=True)
```

### Clearing All Cached Secrets

If multiple secrets need immediate refresh:

```python
from src.lambdas.shared.secrets import clear_cache
clear_cache()  # Next get_secret() call fetches fresh
```

### Secret Rotation Checklist

When rotating a secret (e.g., API key compromise):

1. **Update in Secrets Manager**:
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id dev/sentiment-analyzer/tiingo-api-key \
     --secret-string '{"api_key":"NEW_KEY_HERE"}'
   ```

2. **Wait for cache refresh** (max 5 minutes) OR force cold start

3. **Verify new secret is in use**:
   ```bash
   # Invoke Lambda and check logs for successful API call
   aws lambda invoke \
     --function-name dev-sentiment-ingestion \
     --payload '{}' \
     /tmp/output.json && cat /tmp/output.json
   ```

### Troubleshooting Secret Issues

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "Secret not found" error | Secret doesn't exist or wrong path | Verify with `aws secretsmanager describe-secret` |
| "Access denied" error | IAM permission missing | Check Lambda role has `secretsmanager:GetSecretValue` |
| Old secret still used | Cache not expired | Force cold start or wait 5 min |
| Slow Lambda cold start | Too many secrets fetched | Consolidate secrets, use shared module |

### Cache Configuration

The TTL can be adjusted via environment variable:

```bash
# Set to 10 minutes (600 seconds)
aws lambda update-function-configuration \
  --function-name dev-sentiment-dashboard \
  --environment "Variables={SECRETS_CACHE_TTL_SECONDS=600}"
```

**Default**: 300 seconds (5 minutes)
**Minimum recommended**: 60 seconds (avoid API throttling)
**Maximum recommended**: 900 seconds (15 minutes for non-critical secrets)

---

## Escalation Procedures

### Current (Single Contributor)

No escalation path - @traylorre handles all incidents.

### Future (Team)

1. **L1**: On-call engineer (15 min response)
2. **L2**: Senior engineer (30 min response)
3. **L3**: Engineering manager (1 hour response)

---

## Contact Information

| Role | Contact | Hours |
|------|---------|-------|
| On-Call | @traylorre | 24/7 |
| Tiingo Support | support@tiingo.com | Business hours |
| Finnhub Support | support@finnhub.io | Business hours |
| AWS Support | AWS Console | 24/7 (if support plan) |

---

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
