# Task 3: Verify SNS Cross-Lambda Trace Propagation

**Priority:** P1
**Spec FRs:** FR-013
**Status:** TODO
**Depends on:** Task 1 (IAM permissions)
**Blocks:** Nothing directly, but validates assumption for end-to-end tracing

---

## Problem

The Ingestion Lambda publishes to an SNS topic, which triggers the Analysis Lambda. The audit found these traces appear **disconnected** — two separate trace IDs instead of one continuous trace.

AWS Active tracing should auto-propagate trace context via the `AWSTraceHeader` system attribute. But this only works when:
1. Both Lambdas have Active tracing enabled (confirmed: lines 264, 320 in `main.tf`)
2. The SNS SDK call is auto-patched (confirmed: `patch_all()` in Ingestion)
3. The SNS subscription supports trace propagation

---

## Current State

**SNS Configuration:** `infrastructure/terraform/modules/sns/main.tf`
- Topic: `{env}-sentiment-analysis-requests`
- Subscription: Lambda protocol to Analysis Lambda
- No explicit `AWSTraceHeader` configuration (should be automatic)

**Ingestion Lambda:** `src/lambdas/ingestion/handler.py`
- `patch_all()` at line 83
- `@xray_recorder.capture("publish_sns_batch")` at line 1081

**Analysis Lambda:** `src/lambdas/analysis/handler.py`
- `patch_all()` at line 61

---

## Files to Modify

| File | Change |
|------|--------|
| None (verification only) | — |
| `tests/e2e/` (if needed) | Add E2E test asserting linked traces |

---

## What to Verify

1. Deploy both Lambdas with Active tracing and `patch_all()`
2. Trigger Ingestion Lambda to process articles → publish to SNS → invoke Analysis Lambda
3. Query X-Ray for the Ingestion Lambda's trace ID
4. Verify the Analysis Lambda invocation appears in the **same trace**
5. If traces are disconnected, investigate:
   - Is `AWSTraceHeader` present in SNS message system attributes?
   - Is the Analysis Lambda receiving the trace context?
   - Is there a `batch_size > 1` SNS subscription setting that breaks propagation?

---

## Success Criteria

- [ ] Ingestion → SNS → Analysis appears under a single trace ID
- [ ] No manual `MessageAttributes` needed (auto-propagation works)
- [ ] E2E test exists to prevent regression

---

## Blind Spots

1. **Batch SNS invocations**: If SNS delivers messages in batches, trace context may only link to the first message's trace.
2. **Async invoke**: SNS invokes Lambda asynchronously. Verify X-Ray links async invocations to the parent trace.
3. **Dead letter queue**: If Analysis Lambda fails and message goes to DLQ, does the trace show the DLQ routing?
4. **Existing E2E helper**: `tests/e2e/helpers/xray.py` (247 lines) already has trace query utilities — use these.
