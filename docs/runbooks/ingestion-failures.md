# Ingestion Failures Runbook

**Service**: Market Data Ingestion Lambda
**Owner**: Platform Team
**Last Updated**: 2025-12-09
**Spec Reference**: specs/072-market-data-ingestion/

## Overview

The ingestion Lambda collects market sentiment data from Tiingo (primary) and Finnhub (secondary) every 5 minutes during market hours (9:30 AM - 4:00 PM ET). Alerts are triggered after 3 consecutive failures within 15 minutes.

## Alert Types

### 1. Consecutive Collection Failures (SNS)

**Trigger**: 3 consecutive failures within 15-minute window

**Symptoms**:
- SNS alert to ingestion-alerts topic
- CloudWatch metric: `CollectionFailure` count increasing
- Data freshness degrading (>15 minutes)

**Investigation Steps**:

1. Check CloudWatch Logs for the ingestion Lambda:
```bash
aws logs tail /aws/lambda/ingestion --since 30m --filter-pattern "ERROR"
```

2. Check source API status:
   - Tiingo: https://status.tiingo.com/
   - Finnhub: https://finnhub.io/status

3. Check circuit breaker state:
```bash
aws dynamodb get-item \
  --table-name sentiment-analyzer-dev \
  --key '{"pk": {"S": "CB#tiingo"}, "sk": {"S": "STATE"}}'
```

4. Verify API credentials:
```bash
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo-api-key \
  --query SecretString --output text | head -c 10
```

**Resolution**:

| Root Cause | Resolution |
|------------|------------|
| Source API down | Wait for recovery or force failover by setting circuit breaker to OPEN |
| Rate limited | Reduce collection frequency or upgrade API tier |
| Credential expired | Rotate secret in Secrets Manager |
| Lambda timeout | Increase timeout or check network connectivity |

### 2. High Latency Alert (CloudWatch)

**Trigger**: Collection latency exceeds 30 seconds (3x normal 10s timeout)

**Symptoms**:
- CloudWatch metric: `HighLatencyAlert` count = 1
- CloudWatch metric: `CollectionLatencyMs` > 30000

**Investigation Steps**:

1. Check Lambda duration:
```bash
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer/Ingestion \
  --metric-name CollectionLatencyMs \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average Maximum
```

2. Check for network issues (VPC config, NAT gateway)

3. Check source API response times

**Resolution**:
- If temporary spike: Monitor, usually self-resolves
- If persistent: Increase Lambda timeout, add retries, or investigate API

### 3. Notification SLA Breach (CloudWatch)

**Trigger**: Downstream notification takes >30 seconds after storage

**Symptoms**:
- CloudWatch metric: `NotificationLatencyMs` with `SLAMet=false`
- Downstream consumers report stale data

**Investigation Steps**:

1. Check SNS delivery logs:
```bash
aws logs tail /aws/lambda/ingestion --filter-pattern "notification latency"
```

2. Check DynamoDB write capacity:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ThrottledRequests \
  --dimensions Name=TableName,Value=sentiment-analyzer-dev \
  --start-time ... --end-time ... --period 60 --statistics Sum
```

**Resolution**:
- Check DynamoDB capacity mode (should be on-demand)
- Check SNS topic configuration
- Verify no Lambda concurrency throttling

## Scheduled Maintenance Windows

- **Safe to disable**: Outside market hours (before 9:30 AM or after 4:00 PM ET)
- **Staleness acceptable**: 1 hour outside market hours
- **Do NOT disable during**: Market hours unless emergency

## Contact Information

- **Primary On-Call**: See PagerDuty rotation
- **Escalation**: Platform Team Lead
- **External Contacts**:
  - Tiingo Support: support@tiingo.com
  - Finnhub Support: support@finnhub.io

## Rollback Procedures

If a recent deployment caused failures:

1. Identify last known good version:
```bash
aws lambda list-versions-by-function --function-name ingestion
```

2. Roll back to previous version:
```bash
aws lambda update-alias \
  --function-name ingestion \
  --name prod \
  --function-version <previous-version>
```

3. Verify collection resumes within 5 minutes

## Metrics Dashboard

Key metrics to monitor:
- `CollectionSuccess` / `CollectionFailure` ratio
- `CollectionLatencyMs` p50, p90, p99
- `ItemsCollected` per collection
- `ItemsDuplicate` rate
- `FailoverCount` (should be 0 normally)
