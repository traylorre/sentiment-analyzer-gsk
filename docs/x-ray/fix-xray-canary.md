# Task 11: Implement Observability Canary (Watcher of the Watcher)

**Priority:** P2 (elevated from P3 — Round 4 meta-observability findings)
**Spec FRs:** FR-019, FR-020, FR-021, FR-036, FR-049, FR-050, FR-051
**Status:** TODO
**Depends on:** All other tasks (canary validates the complete observability system)
**Blocks:** Nothing

---

## Problem

If X-Ray ingestion fails (regional degradation, IAM permission revocation, SDK bug), ALL the new tracing coverage becomes invisible. The entire observability system goes dark, but no alarm fires because all alarms depend on X-Ray.

The audit identified an analogous risk for CloudWatch `put_metric_data` (Section 8.1). The same principle applies: the monitoring system needs a monitor.

---

## Design

A scheduled Lambda (or EventBridge-triggered task) that:

1. **Submits a test trace** to X-Ray with a known, unique marker
2. **Waits** for X-Ray's eventual consistency propagation (5-30 seconds)
3. **Queries** X-Ray for the test trace by its marker
4. **Reports** success/failure via a **CloudWatch metric** (NOT via X-Ray)
5. **Alarm** on the metric with `treat_missing_data = breaching`

### Why CloudWatch Metric?

The canary must report via a channel independent of X-Ray. CloudWatch metrics are the natural choice because:
- CloudWatch metrics pipeline is independent of X-Ray
- `treat_missing_data = breaching` means the alarm fires if the canary stops running entirely
- This creates a two-layer safety net: canary down = alarm fires; X-Ray down = canary detects and alarm fires

---

## Non-X-Ray Exception

Per FR-021, this canary is the **sole permitted non-X-Ray observability mechanism** in the system. Every other tracing/correlation path must use X-Ray exclusively.

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `src/lambdas/xray_canary/handler.py` | New: Canary Lambda handler |
| `src/lambdas/xray_canary/requirements.txt` | New: Dependencies (aws-xray-sdk, boto3) |
| `infrastructure/terraform/main.tf` | New Lambda resource, EventBridge schedule, IAM role |
| `infrastructure/terraform/modules/cloudwatch/main.tf` | New alarm on canary metric |

---

## Canary Logic

```
1. Generate unique test_id (UUID)
2. Submit test trace to X-Ray with annotation: canary_test_id = test_id
3. Wait configured propagation window (default: 30 seconds)
4. Query X-Ray: filter traces where annotation.canary_test_id = test_id
5. If trace found:
   - Emit CloudWatch metric: XRayCanaryHealth = 1
6. If trace NOT found:
   - Emit CloudWatch metric: XRayCanaryHealth = 0
   - Log detailed error (which IS a structured log, not an X-Ray trace — by design)
```

### Alarm Configuration

```
Metric: XRayCanaryHealth
Namespace: SentimentAnalyzer/Observability
Statistic: Minimum
Period: canary_interval * 2 (e.g., 10 minutes if canary runs every 5 min)
Threshold: < 1
Evaluation Periods: 2 (consecutive failures required)
treat_missing_data: breaching
```

### Data Loss Detection (FR-036 — Round 3)

In addition to basic health checking, the canary must detect X-Ray data loss from throttling. X-Ray silently drops data at the 2,600 segments/sec region limit — `PutTraceSegments` returns 429 `ThrottledException` and data in `UnprocessedTraceSegments` is permanently lost, not queued.

**Detection approach:**

1. Submit a batch of N test traces (e.g., 5) with unique markers in a single canary run
2. After propagation window, query for ALL N traces
3. If fewer than N traces are found, data loss occurred
4. Emit CloudWatch metric: `XRayDataLossDetected = (N - found_count)`

**Alarm:**
```
Metric: XRayDataLossDetected
Namespace: SentimentAnalyzer/Observability
Statistic: Sum
Period: 300 (5 minutes)
Threshold: > 0
Evaluation Periods: 1 (single occurrence triggers)
treat_missing_data: notBreaching
```

This detects silent data loss that basic health checking misses — the canary trace might succeed while production traces are being throttled.

---

## Success Criteria

- [ ] Canary Lambda deployed and running on schedule
- [ ] Canary submits test trace and verifies retrieval
- [ ] On X-Ray healthy: `XRayCanaryHealth = 1` metric emitted
- [ ] On X-Ray degraded: `XRayCanaryHealth = 0` metric emitted
- [ ] Alarm fires on 2 consecutive failures
- [ ] Alarm fires if canary itself stops running (`treat_missing_data = breaching`)
- [ ] Canary does NOT depend on X-Ray for its own health reporting

---

## Blind Spots

1. **False positives from cold start**: First canary invocation after deploy may have higher query latency. The 2-consecutive-failures requirement mitigates this.
2. **X-Ray query API rate limits**: `GetTraceSummaries` has rate limits. If canary runs too frequently, it may be throttled. 5-minute interval is safe.
3. **Cost**: Each canary run submits N+1 traces (1 health check + N data loss probes) and 2 `GetTraceSummaries` queries. At 5-minute intervals with N=5, that's ~1,728 traces/day — negligible X-Ray cost.
4. **IAM permissions**: Canary Lambda needs both `xray:PutTraceSegments` (submit) AND `xray:GetTraceSummaries`/`xray:BatchGetTraces` (query). Standard write-only policies are insufficient.
5. **Canary's own X-Ray**: The canary Lambda itself should NOT have Active tracing enabled. It submits traces programmatically, not through the Lambda runtime's auto-tracing. Enabling Active tracing would create confusing double traces.
6. **Throttling vs data loss**: The canary's batch probe detects data loss but cannot directly measure the 2,600 segments/sec throttle limit. Under normal load, the canary's N traces succeed. Under heavy load, production traces may be throttled while canary traces still succeed (canary runs during low-traffic canary schedule). The batch probe increases sensitivity but is not a perfect proxy for production throttling.
7. **`begin_segment()` in canary**: The canary Lambda submits test traces programmatically. Unlike other Lambdas, the canary MUST use `xray_recorder.begin_segment()` directly — this works because the canary should NOT have Active tracing enabled (Blind Spot 5), so the Lambda runtime does NOT install `LambdaContext`. Without `LambdaContext`, `begin_segment()` works normally. If Active tracing is accidentally enabled, `begin_segment()` becomes a no-op and the canary silently stops functioning.

---

## CloudWatch Metric Emission Health (FR-049 — Round 4)

The audit (Section 8.1) identified the "single most dangerous blind spot": if CloudWatch `put_metric_data` fails (IAM change, throttling, regional degradation), ALL custom metric-based alarms go dark. Alarms configured with `treat_missing_data = notBreaching` resolve to OK when no data arrives — creating false-green status.

The canary MUST validate CloudWatch metric emission health in addition to X-Ray health.

### CloudWatch Health Check Logic

```
1. Emit a test metric: CloudWatchCanaryHealth = 1
   Namespace: SentimentAnalyzer/Observability
   Timestamp: now
2. Wait CloudWatch ingestion delay (60-120 seconds — see Assumption 17)
3. Query CloudWatch: GetMetricStatistics for the test metric
   Period: 60 seconds
   Start: (now - 180 seconds)  # Account for ingestion delay
   End: now
   Statistic: Maximum
4. If metric found with value = 1:
   - CloudWatch emission healthy
5. If metric NOT found:
   - Emit alert via out-of-band channel (FR-050)
   - Log detailed error
```

### Why 60-120 Second Wait?

CloudWatch metric ingestion has a propagation delay of 60-120 seconds (documented in AWS CloudWatch Developer Guide). The canary query window must account for this delay. The canary's 5-minute schedule provides ample time for the round-trip.

---

## Out-of-Band Alerting (FR-050 — Round 4)

When the canary detects failure in EITHER X-Ray OR CloudWatch, it MUST alert via a channel that does NOT depend on the failed system:

- **X-Ray down** → alert via CloudWatch metric (existing design — this works because CloudWatch metrics pipeline is independent of X-Ray)
- **CloudWatch down** → alert via **SNS direct publish** (NOT via CloudWatch alarm, which depends on CloudWatch)
- **Both down** → alert via SNS direct publish (worst case — both observability planes failed)

### SNS Direct Publish

The canary directly calls `sns:Publish` to the operations SNS topic. This bypasses CloudWatch entirely:

```
sns.publish(
    TopicArn=OPERATIONS_SNS_TOPIC_ARN,
    Subject="CRITICAL: CloudWatch metric emission failure detected",
    Message="Canary {function_name} detected CloudWatch put_metric_data failure. All treat_missing_data=notBreaching alarms may be false-green. Investigate IAM, throttling, or regional CloudWatch degradation."
)
```

This is NOT a CloudWatch alarm — it is a direct SNS notification triggered by the canary Lambda itself.

---

## Separate IAM Role (FR-051 — Round 4)

The canary Lambda MUST use a **separate IAM role** from application Lambdas. Rationale:

1. If an IAM change revokes `xray:PutTraceSegments` from application roles, the canary's independent role detects the outage
2. If an IAM change revokes `cloudwatch:PutMetricData` from application roles, the canary's independent role detects the outage
3. The canary needs `xray:GetTraceSummaries` and `cloudwatch:GetMetricStatistics` (read permissions) that application Lambdas should NOT have

### Required Permissions

| Permission | Purpose |
|-----------|---------|
| `xray:PutTraceSegments` | Submit test traces |
| `xray:GetTraceSummaries` | Query test traces |
| `xray:BatchGetTraces` | Retrieve full trace details |
| `cloudwatch:PutMetricData` | Emit canary health metrics |
| `cloudwatch:GetMetricStatistics` | Query test metrics |
| `sns:Publish` | Out-of-band alerting |
| `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | Lambda execution logging |

---

## Updated Files to Create/Modify

| File | Change |
|------|--------|
| `src/lambdas/xray_canary/handler.py` | New: Canary Lambda handler (X-Ray health + CloudWatch health + out-of-band alerting) |
| `src/lambdas/xray_canary/requirements.txt` | New: Dependencies (aws-xray-sdk, boto3) |
| `infrastructure/terraform/main.tf` | New Lambda resource, EventBridge schedule, **separate IAM role** |
| `infrastructure/terraform/modules/cloudwatch/main.tf` | New alarm on canary metrics |
| `infrastructure/terraform/modules/sns/main.tf` | Operations SNS topic for out-of-band alerts (if not already existing) |

---

## Updated Success Criteria

- [ ] Canary Lambda deployed and running on schedule
- [ ] Canary submits test trace and verifies retrieval (X-Ray health)
- [ ] Canary emits test metric and verifies retrieval (CloudWatch health — FR-049)
- [ ] On X-Ray healthy: `XRayCanaryHealth = 1` metric emitted
- [ ] On X-Ray degraded: `XRayCanaryHealth = 0` metric emitted
- [ ] On CloudWatch degraded: SNS direct publish fires (FR-050)
- [ ] Alarm fires on 2 consecutive failures
- [ ] Alarm fires if canary itself stops running (`treat_missing_data = breaching`)
- [ ] Canary does NOT depend on X-Ray for its own health reporting
- [ ] Canary does NOT depend on CloudWatch alarms for CloudWatch failure reporting
- [ ] Canary uses separate IAM role from application Lambdas (FR-051)

---

## Updated Blind Spots

8. **CloudWatch ingestion delay**: The 60-120 second ingestion delay means the canary cannot detect CloudWatch failures faster than ~2 minutes. At 5-minute canary intervals, worst-case detection is ~7 minutes.
9. **SNS dependency**: The out-of-band alert depends on SNS being operational. If SNS is also down, the alert fails silently. This is an acceptable residual risk — simultaneous X-Ray + CloudWatch + SNS regional failure is an extreme scenario.
10. **IAM role drift**: If the canary's IAM role is accidentally modified to match application roles, the independent detection value is lost. The canary role should be in a separate Terraform module or have explicit lifecycle protection.
11. **Cost of CloudWatch health check**: Each canary run adds 1 `PutMetricData` + 1 `GetMetricStatistics` API call. At 5-minute intervals, ~8,640 API calls/month — well within free tier.
