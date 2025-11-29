# Scaling Runbook

This document provides procedures for scaling the Sentiment Analyzer system in response to traffic changes.

## Architecture Overview

The system uses AWS serverless architecture:

| Component | Service | Scaling Mode | Default Capacity |
|-----------|---------|--------------|------------------|
| API | Lambda | Auto (concurrent) | 1000 concurrent |
| Database | DynamoDB | On-demand | Auto |
| CDN | CloudFront | Auto | Global |
| Ingestion | Lambda + EventBridge | Scheduled | Every 15 min |

## Monitoring Dashboards

- **CloudWatch Dashboard**: `sentiment-analyzer-{env}-dashboard`
- **X-Ray Service Map**: AWS X-Ray console
- **Lambda Insights**: CloudWatch Lambda Insights

## Key Metrics to Monitor

### Lambda Metrics
| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| ConcurrentExecutions | >70% of limit | >90% of limit | Request limit increase |
| Duration p95 | >5s | >10s | Profile for bottlenecks |
| Errors | >1% | >5% | Investigate logs |
| Throttles | Any | Sustained | Increase reserved concurrency |

### DynamoDB Metrics
| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| ConsumedReadCapacity | >70% of provisioned | >90% | Scale up or switch to on-demand |
| ConsumedWriteCapacity | >70% of provisioned | >90% | Scale up or switch to on-demand |
| ThrottledRequests | Any | Sustained | Review GSI design, add capacity |
| SystemErrors | Any | Any | AWS issue - check status page |

### API Gateway (Lambda Function URL)
| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| Latency p95 | >1s | >3s | Check downstream services |
| 5xx Errors | >1% | >5% | Check Lambda errors |
| 429 Rate Limit | >10/min | >100/min | Review rate limit config |

## Scaling Procedures

### 1. Increase Lambda Concurrency

**When to use**: Throttling observed, or preparing for traffic spike

```bash
# Check current concurrency
aws lambda get-function-configuration \
  --function-name sentiment-analyzer-{env}-dashboard \
  --query 'ReservedConcurrentExecutions'

# Increase reserved concurrency
aws lambda put-function-concurrency \
  --function-name sentiment-analyzer-{env}-dashboard \
  --reserved-concurrent-executions 500

# Verify
aws lambda get-function-configuration \
  --function-name sentiment-analyzer-{env}-dashboard \
  --query 'ReservedConcurrentExecutions'
```

**Rollback**:
```bash
aws lambda delete-function-concurrency \
  --function-name sentiment-analyzer-{env}-dashboard
```

### 2. Switch DynamoDB to Provisioned Capacity

**When to use**: Predictable traffic patterns, cost optimization at scale

```bash
# First, analyze current usage (last 7 days)
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=sentiment-analyzer-{env} \
  --start-time $(date -d '7 days ago' --iso-8601=seconds) \
  --end-time $(date --iso-8601=seconds) \
  --period 3600 \
  --statistics Maximum

# Update via Terraform (recommended)
cd infrastructure/terraform
terraform plan -var-file={env}.tfvars -target=module.dynamodb
terraform apply -var-file={env}.tfvars -target=module.dynamodb
```

### 3. Enable Lambda Provisioned Concurrency

**When to use**: Reduce cold starts for critical paths

```bash
# Publish new version
VERSION=$(aws lambda publish-version \
  --function-name sentiment-analyzer-{env}-dashboard \
  --query 'Version' --output text)

# Create alias with provisioned concurrency
aws lambda create-alias \
  --function-name sentiment-analyzer-{env}-dashboard \
  --name prod-warm \
  --function-version $VERSION

aws lambda put-provisioned-concurrency-config \
  --function-name sentiment-analyzer-{env}-dashboard \
  --qualifier prod-warm \
  --provisioned-concurrent-executions 10
```

### 4. Scale Ingestion Frequency

**When to use**: Need more real-time data during market events

```bash
# Current schedule in Terraform
# ingestion_schedule = "rate(15 minutes)"

# To change, update preprod.tfvars or prod.tfvars:
# ingestion_schedule = "rate(5 minutes)"

cd infrastructure/terraform
terraform apply -var-file={env}.tfvars -target=module.eventbridge
```

## Emergency Procedures

### High Error Rate (>5%)

1. Check Lambda logs for errors:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/lambda/sentiment-analyzer-{env}-dashboard \
     --filter-pattern "ERROR" \
     --start-time $(date -d '1 hour ago' +%s000)
   ```

2. Check X-Ray for failed traces:
   ```bash
   aws xray get-trace-summaries \
     --start-time $(date -d '1 hour ago' --iso-8601=seconds) \
     --end-time $(date --iso-8601=seconds) \
     --filter-expression 'responsetime > 5 AND error = true'
   ```

3. If external API (Tiingo/Finnhub) issue:
   - Circuit breaker should activate automatically
   - Check quota tracker: `DynamoDB scan for QUOTA# keys`

### Sustained Throttling

1. Request AWS limit increase:
   - Go to AWS Service Quotas
   - Request increase for Lambda concurrent executions

2. Temporarily reduce traffic:
   - Update rate limits in `src/lambdas/shared/middleware/rate_limit.py`
   - Deploy via CI/CD

### DynamoDB Hot Key

1. Identify hot key using Contributor Insights:
   ```bash
   aws dynamodb describe-contributor-insights \
     --table-name sentiment-analyzer-{env}
   ```

2. Review access patterns in X-Ray
3. Consider adding GSI or caching layer

## Load Testing Before Scaling

Before any major scaling change, run load tests:

```bash
# Smoke test (quick validation)
k6 run --env API_URL=$PREPROD_API_URL --env STAGE=smoke tests/load/api-load-test.js

# Load test (normal traffic)
k6 run --env API_URL=$PREPROD_API_URL --env STAGE=load tests/load/api-load-test.js

# Stress test (find breaking point)
k6 run --env API_URL=$PREPROD_API_URL --env STAGE=stress tests/load/api-load-test.js
```

## Cost Considerations

| Action | Cost Impact | When to Use |
|--------|-------------|-------------|
| Increase Lambda memory | +$$ | CPU-bound operations |
| Provisioned concurrency | +$$$ | Cold start sensitive |
| DynamoDB provisioned | -$ at scale | Predictable traffic |
| CloudFront caching | -$ | Static content |
| Reserved capacity | -30% | Long-term commitment |

## Contacts

- **On-call**: Check PagerDuty rotation
- **AWS Support**: Support ticket (if Business/Enterprise support)
- **Escalation**: See incident response runbook
