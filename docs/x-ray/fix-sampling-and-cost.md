# Task 16: Configure Sampling Strategy and Cost Guard

**Priority:** P1
**Status:** TODO
**Spec FRs:** FR-034, FR-035, FR-038, FR-039
**Depends on:** None (infrastructure configuration)
**Blocks:** None (but should be in place before production deployment)

---

## Scope Clarification (FR-039 — Round 4)

**"X-Ray exclusive" applies to TRACING, not to ALARMING.**

X-Ray is the exclusive distributed tracing system — all trace context, subsegments, and diagnostic data flow through X-Ray. However, CloudWatch alarms on Lambda built-in metrics (`Errors`, `Duration`, `Throttles`) are NOT tracing — they are operational alarming powered by CloudWatch Metrics, a separate AWS system.

This distinction matters because X-Ray sampling means not all errors produce traces. CloudWatch Lambda metrics capture 100% of invocations regardless of X-Ray sampling. Both systems are required:

| System | Purpose | Coverage | Sampling Impact |
|--------|---------|----------|----------------|
| X-Ray | Distributed tracing, diagnostic context | Sampled requests only | At 10% sampling, ~90% of errors have no trace |
| CloudWatch Metrics | Operational alarming, SLA monitoring | 100% of invocations | Not affected by X-Ray sampling |

The X-Ray Error Group (Section 2 below) provides trace-level error alerting on SAMPLED traces. CloudWatch Lambda `Errors` metric provides 100% error alerting. These are complementary, not redundant.

---

## Problem

The system has no explicit X-Ray sampling strategy. Three issues:

1. **Default sampling loses errors:** X-Ray's default rule (1 request/second + 5%) means most errored requests during traffic spikes are untraced. Since X-Ray is the EXCLUSIVE debugging tool, untraced errors are undiagnosable.

2. **Client can force 100% sampling:** A malicious client sending `Sampled=1` in the `X-Amzn-Trace-Id` header forces X-Ray to trace every request at $5/million traces. Server-side sampling rules must override client decisions.

3. **No cost guard:** At 100% sampling, costs scale linearly with traffic. No alarm exists to catch cost surprises.

---

## Changes Required

### 1. Per-Environment X-Ray Sampling Rules (FR-034)

Configure via Terraform (`modules/xray/sampling.tf`):

**Dev/Preprod — 100% sampling:**
```
Rule: TraceAll-{env}
Priority: 1
Reservoir: 1
FixedRate: 1.0 (100%)
ServiceName: *
```

**Production — Configurable rate:**
```
Rule: Production-Default
Priority: 100
Reservoir: 10 (10 requests/second guaranteed)
FixedRate: 0.10 (10% of additional)
ServiceName: *
```

At current traffic (<1M requests/month), even 100% sampling in production costs <$5/month. The production rate is configurable via Terraform variable for future scaling.

### 2. X-Ray Error Group with CloudWatch Metrics (FR-034)

Create an X-Ray Group that automatically generates CloudWatch metrics for errored traces:

```
Group Name: {env}-errors
Filter Expression: fault = true OR error = true
```

This Group generates CloudWatch metrics in the `AWS/XRay` namespace:
- `ApproximateErrorCount` — errored traces
- `FaultCount` — faulted traces
- Latency percentiles for errored requests

Create CloudWatch alarm on the Group's error count metric for operator notification.

### 3. Server-Side Sampling Defense (FR-035)

X-Ray respects the incoming `Sampled` field as authoritative when already decided (not `?`). To prevent client-driven cost amplification:

- API Gateway's X-Ray tracing configuration makes its own sampling decision regardless of client header
- Configure API Gateway tracing at a fixed sampling percentage (not passthrough)
- Lambda Function URLs (SSE endpoint): configure X-Ray sampling rules that apply to the Lambda service, overriding client headers

**Note:** When API Gateway has X-Ray tracing enabled with a specific sampling rule, it evaluates its own rules rather than blindly trusting the incoming `Sampled` field. This is the default behavior — no additional configuration needed beyond having server-side rules in place.

### 4. X-Ray Cost Budget Alarms (FR-038)

Create CloudWatch billing alarms in `modules/monitoring/cost.tf`:

- Alarm at $10/month X-Ray spend
- Alarm at $25/month X-Ray spend
- Alarm at $50/month X-Ray spend

Use the `AWS/Billing` namespace with `ServiceName: AWSXRay` dimension.

---

## Files to Modify

| File | Change |
|------|--------|
| `modules/xray/sampling.tf` (new) | X-Ray sampling rules per environment |
| `modules/xray/groups.tf` (new) | X-Ray error Group with filter expression |
| `modules/monitoring/cost.tf` | Add X-Ray billing alarms at $10/$25/$50 |
| `modules/monitoring/alarms.tf` | Add alarm on X-Ray Group error count metric |

---

## Verification

1. **Sampling rate:** In dev, verify 100% of requests generate X-Ray traces. In production, verify the configured rate is respected.
2. **Error Group:** Generate an error (e.g., DynamoDB throttle) and verify the trace appears in the X-Ray error Group. Verify the Group's CloudWatch metric increments.
3. **Client defense:** Send requests with `Sampled=1` header and verify the server-side sampling rule is applied (not 100% sampling).
4. **Cost alarms:** Verify CloudWatch billing alarms are configured with correct thresholds and SNS notifications.

---

## Cost Estimate

| Scenario | Monthly Requests | Sampling Rate | Traces Recorded | Monthly Cost |
|----------|-----------------|---------------|-----------------|-------------|
| Dev | ~100K | 100% | 100K | **$0** (free tier) |
| Preprod | ~500K | 100% | 500K | **$2.00** |
| Production (current) | ~1M | 100% | 1M | **$4.50** |
| Production (10x growth) | ~10M | 10% | 1M | **$4.50** |
| Production (100x growth) | ~100M | 10% | 10M | **$49.50** |

At current traffic levels, 100% sampling in all environments is cost-effective. The $50 alarm provides early warning for the 100x growth scenario.

---

## Future: Tail-Based Sampling

When traffic grows beyond cost-effective 100% sampling, the upgrade path is:

1. Deploy ADOT Collector as an ECS task or Lambda with buffering
2. Configure all Lambdas to send traces to the Collector via OTLP
3. Collector applies tail-based sampling policy: always keep error/fault traces, sample successful traces
4. Collector exports to X-Ray

This is NOT a current requirement — documented here for future reference.
