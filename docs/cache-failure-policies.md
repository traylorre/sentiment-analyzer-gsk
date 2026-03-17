# Cache Failure Policies

**Feature 1224 — Cache Architecture Audit**
**Last Updated**: 2026-03-17

## Overview

When an upstream dependency is unreachable, each cache behaves according to a documented failure policy. This runbook defines the expected behavior for every cache in the system.

**Failure policy types:**
- **Fail-open**: Serve stale cached data. User sees slightly outdated information but the system remains available.
- **Fail-closed**: Deny access after a grace period. Used for security-critical data where staleness could be dangerous.
- **Fail-conservative**: Reduce functionality rather than full denial. Used for quota tracking where both full-stop and full-speed are undesirable.

## Cache Inventory

### Security-Critical Caches (Fail-Closed)

| Cache | File | Upstream | Grace Period | Behavior on Failure |
|-------|------|----------|-------------|---------------------|
| Secrets Manager | `shared/secrets.py` | AWS Secrets Manager | 15 min | Serve cached secret during grace period. After 15 min, raise `SecretAccessDeniedError`. |

### Quota Tracking (Fail-Conservative)

| Cache | File | Upstream | Behavior on Failure |
|-------|------|----------|---------------------|
| Quota Tracker (write) | `shared/quota_tracker.py` | DynamoDB | Reduce API call rate to 25% of limit. Emit `QuotaTracker/Disconnected` alert. Resume full rate when DynamoDB recovers. |
| Quota Tracker (read) | `shared/quota_tracker.py` | DynamoDB | Use last known cached count. Continue at current rate. |

### Data Caches (Fail-Open)

| Cache | File | Upstream | TTL | Behavior on Failure |
|-------|------|----------|-----|---------------------|
| Ticker List | `shared/cache/ticker_cache.py` | S3 | 5 min | Serve stale list indefinitely. Log warning. Retry on next TTL cycle. |
| OHLC Persistent | `shared/cache/ohlc_cache.py` | DynamoDB | TTL per resolution | Return empty result on read failure. Caller handles. |
| OHLC Response | `dashboard/ohlc.py` | Adapters | 5-60 min | Serve stale response until TTL. |
| Sentiment Response | `dashboard/sentiment.py` | Adapters | 5 min | Serve stale response until TTL. |
| Metrics | `dashboard/metrics.py` | DynamoDB GSIs | 5 min | Serve stale metrics until TTL. |
| Configuration | `dashboard/configurations.py` | DynamoDB | 60 sec | Serve stale config until TTL. |
| Circuit Breaker | `shared/circuit_breaker.py` | DynamoDB | 60 sec | Assume circuit **closed** (allow traffic). Emit `SilentFailure/Count` metric. |
| Tiingo API | `shared/adapters/tiingo.py` | Tiingo REST | 30-60 min | Serve stale API response until TTL. |
| Finnhub API | `shared/adapters/finnhub.py` | Finnhub REST | 30-60 min | Serve stale API response until TTL. |

## Recovery Procedures

### Quota Tracker Disconnected (CRITICAL)

**Symptom**: `QuotaTracker/Disconnected` CloudWatch alarm fires.

**Impact**: All instances reduce API call rate to 25%. Dashboard data updates slow but don't stop.

**Steps**:
1. Check DynamoDB service health: `aws dynamodb describe-table --table-name <quota-table>`
2. Check CloudWatch for DynamoDB throttling metrics
3. If table is healthy, check Lambda IAM permissions for `dynamodb:UpdateItem`
4. Once DynamoDB is reachable, instances auto-recover (exit reduced-rate mode on next successful write)

### Stale Ticker List

**Symptom**: Users report missing tickers that were recently added to S3.

**Impact**: Cosmetic only. Existing tickers work fine. New tickers invisible until refresh.

**Steps**:
1. Check S3 object exists: `aws s3 ls s3://<bucket>/ticker-cache/us-symbols.json`
2. Check Lambda IAM permissions for `s3:GetObject` and `s3:HeadObject`
3. Force refresh: deploy a no-op change to cycle Lambda containers

### Auth Failures (if JWKS were in use)

**Note**: The application uses self-issued HMAC JWTs (`JWT_SECRET`), not Cognito JWKS. There is no JWKS cache failure mode. If `JWT_SECRET` is unavailable, all auth fails immediately (Secrets Manager fail-closed policy applies).
