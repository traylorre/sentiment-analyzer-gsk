# CloudWatch Alarms Contract

**FR References**: FR-040 through FR-045, FR-061, FR-104, FR-121, FR-127, FR-128, FR-129, FR-131, FR-134, FR-162

## Alarm Categories

### Category 1: Lambda Error Alarms (6 alarms)

One per Lambda function.

| Parameter | Value |
|-----------|-------|
| Namespace | `AWS/Lambda` |
| Metric | `Errors` |
| Statistic | `Sum` |
| Comparison | `GreaterThanThreshold` |
| Threshold | FR-127: Percentage-based with minimum guard (`Errors/Invocations > 5% AND Invocations >= 10`) |
| Period | 300s |
| Evaluation Periods | 2 |
| treat_missing_data | `missing` (FR-162 override: missing invocation data = investigate) |

**Lambdas**: Ingestion, Analysis, Dashboard, Notification, Metrics, SSE Streaming

### Category 2: Lambda Latency Alarms (6 alarms)

One per Lambda function. FR-041 two-phase strategy:
- **Phase 1**: 80% of Lambda timeout (safety net before runtime data)
- **Phase 2**: 2x observed P95 (after 2+ weeks ADOT runtime)

| Parameter | Value |
|-----------|-------|
| Namespace | `AWS/Lambda` |
| Metric | `Duration` |
| Statistic | `p95` |
| Comparison | `GreaterThanThreshold` |
| Period | 300s |
| Evaluation Periods | 3 |
| treat_missing_data | `missing` (FR-162 override: missing latency data = investigate) |

**Phase 1 Thresholds (80% of timeout)**:

| Lambda | Timeout | Phase 1 Threshold |
|--------|---------|-------------------|
| Ingestion | 60s | 48,000ms |
| Analysis | 60s | 48,000ms |
| Dashboard | 30s | 24,000ms |
| Notification | 30s | 24,000ms |
| Metrics | 60s | 48,000ms |
| SSE Streaming | 900s | 720,000ms |

### Category 3: Memory Utilization Alarms (6 alarms)

FR-104: All 6 Lambdas at 85% threshold.

| Parameter | Value |
|-----------|-------|
| Namespace | `AWS/Lambda` |
| Metric | Custom (Powertools metric or CloudWatch Lambda Insights) |
| Threshold | 85% of configured memory |
| treat_missing_data | `missing` (FR-162 override: missing memory data = investigate) |

### Category 4: Silent Failure Alarms (7 alarms)

FR-134: One per failure path.

| Parameter | Value |
|-----------|-------|
| Namespace | `SentimentAnalyzer/Reliability` |
| Metric | `SilentFailure/Count` |
| Dimensions | `FunctionName`, `FailurePath` |
| Statistic | `Sum` |
| Comparison | `GreaterThanThreshold` |
| Threshold | 0 (any failure triggers) |
| Period | 300s |
| Evaluation Periods | 1 |
| treat_missing_data | `missing` (missing = emission failure = investigate) |

**Failure Paths** (FR-142 disambiguated names): circuit_breaker_load, circuit_breaker_save, audit_trail, notification_delivery, self_healing_fetch, fanout_partial_write, parallel_fetcher_aggregate

### Category 5: X-Ray Cost Alarms (3 alarms)

FR-038: Budget protection at three tiers.

| Parameter | Value |
|-----------|-------|
| Namespace | `AWS/Billing` or custom |
| Thresholds | $10, $25, $50 per month |
| treat_missing_data | `notBreaching` (FR-162: no billing data = no charges = good) |
| Scope | Aggregate (single-account; per-env on multi-account transition per R26 clarification) |

### Category 6: ADOT Health Alarms (3 alarms)

| Alarm | Metric Filter Pattern | FR |
|-------|----------------------|-----|
| ADOT Export Failure | `"Exporting failed. Dropping data." OR "Exporting failed"` | FR-098/FR-105 |
| ADOT Startup Failure | `"collector server run finished with error"` | FR-123 |
| Span Loss Detection | Span-count comparison (emitted vs retrieved) | FR-166 (FR-091 log-based detection invalidated for SDK v1.39.1 — deque drops silently) |

All: `treat_missing_data = missing`

### Category 7: Canary Alarms (2 alarms)

| Alarm | Metric | Threshold | FR |
|-------|--------|-----------|-----|
| Canary Health | `CanaryHealth` | != HEALTHY for 2 periods | FR-019 |
| Canary Completeness | `completeness_ratio` | < 0.95 | FR-113 |

Both: `treat_missing_data = breaching` (FR-121: heartbeat absence IS the failure)

### Category 8: Function URL Sampling Cost (1 alarm)

FR-161: Daily anomaly detection for Function URL cost amplification.

| Parameter | Value |
|-----------|-------|
| Type | Anomaly detection |
| Metric | X-Ray traced segment count (Function URL) |
| treat_missing_data | `notBreaching` (FR-162: no segment data = no cost = good) |

## Dashboard Widget Requirements (FR-129, FR-141)

### Severity Tiers

| Tier | Color | Alarms |
|------|-------|--------|
| Critical | Red | Lambda errors, ADOT failures, canary health |
| Warning | Orange | Latency P95, memory utilization, silent failures |
| Info | Blue | Cost, sampling, queue overflow |

### Composite Alarm

FR-129: Top-level composite alarm combining all Critical-tier alarms.

## Total Alarm Count

| Category | Count |
|----------|-------|
| Lambda Errors | 6 |
| Lambda Latency | 6 |
| Memory Utilization | 6 |
| Silent Failures | 7 |
| X-Ray Cost | 3 |
| ADOT Health | 3 |
| Canary | 2 |
| Function URL Cost | 1 |
| **Total** | **34** |

Plus 1 composite alarm = **35 total** (fewer than 45 originally estimated after R26 trimming).
