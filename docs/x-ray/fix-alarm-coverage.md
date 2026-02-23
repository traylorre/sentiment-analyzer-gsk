# Task 17: CloudWatch Alarm Coverage (Round 6)

**Priority:** P1
**Spec FRs:** FR-040, FR-041, FR-042, FR-044, FR-045, FR-061
**Status:** TODO
**Depends on:** Task 4 (silent failure metrics — FR-043 creates the custom metrics that FR-042 alarms on)
**Blocks:** None

---

## Problem

The audit (Sections 4.3, 9.3) identified critical alarm gaps:

1. **SSE Streaming Lambda** has **ZERO** CloudWatch error or latency alarms
2. **Metrics Lambda** has **ZERO** CloudWatch error or latency alarms
3. **7 custom metrics** are emitted with **no alarms** — failures go unnoticed
4. **Ingestion Lambda** has no latency alarm (error alarm exists)
5. **Notification Lambda** has no latency alarm (error alarm exists)
6. **Dashboard alarm widget** shows only 6 of 30+ alarms — operators see false "all green"

X-Ray traces cannot replace CloudWatch alarms. Lambda `Errors` and `Duration` metrics capture 100% of invocations regardless of X-Ray sampling. At production sampling (<100%), most errors have no X-Ray trace — CloudWatch alarms are the only 24/7 alerting mechanism.

---

## Changes Required

### 1. Lambda Error Alarms (FR-040)

Add CloudWatch alarms on the `AWS/Lambda` `Errors` metric for Lambdas with no error alarms:

| Lambda Function | Alarm Name | Threshold | Period | Evaluation Periods | treat_missing_data |
|----------------|------------|-----------|--------|-------------------|-------------------|
| SSE Streaming Lambda | `{env}-sse-streaming-errors` | > 0 | 60s | 1 | notBreaching |
| Metrics Lambda | `{env}-metrics-lambda-errors` | > 0 | 60s | 1 | notBreaching |

**Note:** `treat_missing_data = notBreaching` is correct for error alarms — absence of error metrics means no errors occurred. This is distinct from canary health metrics where absence indicates failure.

### 2. Lambda Latency Alarms (FR-041)

Add CloudWatch alarms on the `AWS/Lambda` `Duration` metric for ALL Lambdas missing latency alarms:

| Lambda Function | Alarm Name | Threshold | Statistic | Period | Evaluation Periods | treat_missing_data |
|----------------|------------|-----------|-----------|--------|-------------------|-------------------|
| SSE Streaming Lambda | `{env}-sse-streaming-latency` | > 14000ms (14s of 15s timeout) | p99 | 300s | 2 | notBreaching |
| Metrics Lambda | `{env}-metrics-lambda-latency` | > 25000ms (25s of 30s timeout) | p99 | 300s | 2 | notBreaching |
| Ingestion Lambda | `{env}-ingestion-latency` | > 25000ms (25s of 30s timeout) | p99 | 300s | 2 | notBreaching |
| Notification Lambda | `{env}-notification-latency` | > 25000ms (25s of 30s timeout) | p99 | 300s | 2 | notBreaching |

Thresholds are set at ~80-90% of the Lambda timeout to alert before timeout failures cascade.

### 3. Custom Metric Alarms (FR-042)

Add CloudWatch alarms for the 7 existing unalarmed custom metrics PLUS the 7 new dual-instrumentation metrics from Task 4 (FR-043):

**Existing unalarmed metrics (audit Section 4.2):**

| Metric | Namespace | Alarm Threshold | Statistic | Period | treat_missing_data |
|--------|-----------|----------------|-----------|--------|-------------------|
| `StuckItems` | `SentimentAnalyzer/SelfHealing` | > 0 | Sum | 300s | notBreaching |
| `ConnectionAcquireFailures` | `SentimentAnalyzer/SSE` | > 0 | Sum | 60s | notBreaching |
| `EventLatencyMs` | `SentimentAnalyzer/SSE` | > 5000 | p99 | 300s | notBreaching |
| `MetricsLambdaErrors` | `SentimentAnalyzer/Metrics` | > 0 | Sum | 60s | notBreaching |
| `HighLatencyAlert` | `SentimentAnalyzer/SSE` | > 0 | Sum | 300s | notBreaching |
| `PollDurationMs` | `SentimentAnalyzer/SSE` | > 10000 | p99 | 300s | notBreaching |
| `AnalysisErrors` | `SentimentAnalyzer/Analysis` | > 0 | Sum | 300s | notBreaching |

**New dual-instrumentation metrics (from Task 4 FR-043):**

| Metric | Namespace | Alarm Threshold | Statistic | Period | treat_missing_data |
|--------|-----------|----------------|-----------|--------|-------------------|
| `CircuitBreakerPersistenceFailure` | `SentimentAnalyzer/Reliability` | > 0 | Sum | 300s | notBreaching |
| `AuditEventPersistenceFailure` | `SentimentAnalyzer/Compliance` | > 0 | Sum | 60s | notBreaching |
| `DownstreamNotificationFailure` | `SentimentAnalyzer/Reliability` | > 0 | Sum | 60s | notBreaching |
| `TimeseriesFanoutPartialFailure` | `SentimentAnalyzer/Data` | > 0 | Sum | 300s | notBreaching |
| `SelfHealingItemFetchFailure` | `SentimentAnalyzer/Reliability` | > 0 | Sum | 300s | notBreaching |
| `ParallelFetcherErrors` | `SentimentAnalyzer/Reliability` | > 0 | Sum | 300s | notBreaching |

### 4. Dashboard Alarm Widget Completeness (FR-044)

The CloudWatch dashboard alarm widget currently shows only 6 of 30+ alarms. After this task, the system will have ~45 alarms total. The dashboard MUST display ALL alarms:

- Replace the static alarm widget (hardcoded 6 alarms) with a dynamic alarm status widget that shows ALL alarms in the namespace
- Or explicitly list all alarm ARNs in the widget configuration
- Group alarms by category: Lambda errors, Lambda latency, Custom metrics, Canary health, Cost

### 5. `treat_missing_data` Alignment Audit (FR-045)

Audit ALL existing and new alarms for correct `treat_missing_data` configuration:

| Alarm Type | Correct Setting | Rationale |
|-----------|----------------|-----------|
| Error count alarms | `notBreaching` | No errors = no data = healthy |
| Latency alarms | `notBreaching` | No invocations = no data = healthy |
| Custom metric alarms (failure counters) | `notBreaching` | No failures = no data = healthy |
| Canary health alarms | `breaching` | No canary data = canary down = UNHEALTHY |
| Cost budget alarms | `notBreaching` | No billing data = no spend = healthy |

**The critical distinction:** Canary alarms use `breaching` because the canary MUST emit data on every scheduled run. If no data arrives, the canary itself has failed. All other alarms use `notBreaching` because absence of error/latency data genuinely means no errors/invocations occurred.

### 6. Existing Alarm Threshold Review (FR-061) — Round 6

Task 17 MUST review ALL existing CloudWatch alarm thresholds in addition to adding new alarms. The audit (Section 6.1) identified `analysis_latency_high` at 25s (42% of the Analysis Lambda's 60s timeout) as too generous. New alarms added by this task use the 80-90% of timeout standard (see Section 2). Existing alarms MUST be recalibrated to match this same methodology. It would be contradictory to add new alarms at strict thresholds while leaving existing alarms at overly generous thresholds.

**Required steps:**

1. **Review all pre-existing alarm thresholds** — Enumerate every CloudWatch alarm that existed before this task, including `analysis_latency_high` and any others in `modules/monitoring/alarms.tf` or elsewhere.
2. **Compare each threshold against the Lambda's configured timeout** — For each latency alarm, determine the associated Lambda's timeout value and calculate what percentage the current threshold represents.
3. **Align to 80-90% of timeout** — Recalibrate thresholds to fall within 80-90% of the Lambda's configured timeout. For example, for a Lambda with a 60s timeout, the latency alarm threshold should be 48000-54000ms, not 25000ms. The `analysis_latency_high` alarm must move from 25s (42%) to 48-54s (80-90%).
4. **Document each threshold change and rationale** — For every threshold that is adjusted, record the old value, new value, the Lambda timeout, and the percentage of timeout the new value represents.

**Example recalibration:**

| Alarm | Lambda Timeout | Old Threshold | Old % | New Threshold | New % |
|-------|---------------|---------------|-------|---------------|-------|
| `analysis_latency_high` | 60s | 25000ms | 42% | 51000ms | 85% |

This ensures all alarms — both new and pre-existing — follow a single, consistent methodology for threshold selection.

---

## Files to Modify

| File | Change |
|------|--------|
| `modules/monitoring/alarms.tf` | Add Lambda error alarms (2), Lambda latency alarms (4), custom metric alarms (13), recalibrate existing alarm thresholds |
| `modules/monitoring/dashboard.tf` | Update alarm widget to show all alarms |
| `modules/monitoring/variables.tf` | Add alarm threshold variables for configurability |
| `modules/monitoring/outputs.tf` | Export alarm ARNs for dashboard widget |

---

## Verification

1. **Lambda error alarms:** Trigger an error in SSE Streaming Lambda and Metrics Lambda. Verify CloudWatch alarm transitions to ALARM state within 1 minute.
2. **Lambda latency alarms:** Introduce artificial delay approaching timeout threshold. Verify alarm transitions to ALARM.
3. **Custom metric alarms:** Emit a test value above threshold for each custom metric. Verify alarm fires.
4. **Dashboard completeness:** Open CloudWatch dashboard. Verify ALL alarms are visible in the alarm widget, grouped by category.
5. **`treat_missing_data` audit:** For each alarm, verify the `treat_missing_data` setting matches the table in Section 5. Particular attention to canary alarms (must be `breaching`).
6. **Existing alarm threshold review:** For each pre-existing latency alarm, verify the threshold is 80-90% of the associated Lambda's timeout. Confirm `analysis_latency_high` has been recalibrated from 25s to 48-54s.

---

## Success Criteria

- [ ] SSE Streaming Lambda has error AND latency alarms (SC-017)
- [ ] Metrics Lambda has error AND latency alarms (SC-017)
- [ ] Ingestion Lambda has latency alarm (error alarm pre-exists)
- [ ] Notification Lambda has latency alarm (error alarm pre-exists)
- [ ] All 7 existing unalarmed custom metrics have alarms (SC-018)
- [ ] All 7 new dual-instrumentation metrics from FR-043 have alarms
- [ ] Dashboard alarm widget shows ALL alarms, not a subset (SC-022)
- [ ] All `treat_missing_data` settings audited and corrected
- [ ] All pre-existing alarm thresholds reviewed and recalibrated to 80-90% of Lambda timeout (SC-061)
- [ ] `analysis_latency_high` threshold changed from 25s to 48-54s (80-90% of 60s timeout)
- [ ] All alarms route to the operations SNS topic

---

## Blind Spots

1. **Alarm count scaling:** With ~45 alarms, operators may experience alarm fatigue. Consider composite alarms that aggregate related alarms into higher-level indicators (e.g., "SSE Health" = SSE errors + SSE latency + SSE connection failures).
2. **Alarm threshold tuning:** Initial thresholds are conservative (> 0 for error counts, ~80-90% timeout for latency). Production traffic patterns may require adjustment. Document the tuning process.
3. **SNS topic fan-out:** All alarms route to the same operations SNS topic. As alarm count grows, consider per-severity SNS topics (critical vs warning) to reduce noise.
4. **Terraform alarm naming:** Alarm names include `{env}` prefix for multi-environment deployments. Ensure Terraform variable interpolation is consistent with existing alarm naming conventions.
5. **Dashboard widget limits:** CloudWatch dashboards have a maximum of 500 widgets. A single alarm status widget can display up to 100 alarms. With ~45 alarms, this is well within limits.
