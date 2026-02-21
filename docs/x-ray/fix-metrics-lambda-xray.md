# Task 2: Fix Metrics Lambda X-Ray Instrumentation

**Priority:** P0
**Spec FRs:** FR-003, FR-004, FR-029
**Status:** TODO
**Depends on:** Task 1 (IAM permissions), Task 14 (tracer standardization — use Powertools Tracer, not raw xray_recorder)
**Blocks:** Task 11 (canary needs all Lambdas instrumented)

---

## Problem

The Metrics Lambda is the monitoring system's core ("monitor of monitors") but has **zero X-Ray SDK integration**:

- No `patch_all()` import
- No `xray_recorder` import
- No subsegments on DynamoDB queries or CloudWatch `put_metric_data` calls
- If this Lambda fails, custom metrics stop flowing, and alarms that depend on them go blind

This is the most dangerous gap: the Terraform config says `tracing_mode = "Active"` (line 490 in `main.tf`), so X-Ray creates a top-level segment, but no subsegments exist to show what happened inside.

---

## Current State

**File:** `src/lambdas/metrics/handler.py`

- DynamoDB queries: ~lines 90-96 (stuck items scan)
- CloudWatch `put_metric_data`: ~lines 118-124 (metric emission)
- No imports from `aws_xray_sdk`
- No X-Ray decorators or subsegments

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/metrics/handler.py` | Add Powertools Tracer with `@tracer.capture_lambda_handler` and `@tracer.capture_method` |
| `src/lambdas/metrics/requirements.txt` | Add `aws-lambda-powertools[tracer]` dependency |
| `infrastructure/terraform/main.tf` | Add `POWERTOOLS_SERVICE_NAME = "metrics"` to Lambda environment |

---

## What to Change

**IMPORTANT (Round 2 — FR-029/FR-030):** Use Powertools Tracer, NOT raw `xray_recorder`. Task 14 standardizes all Lambdas on Powertools Tracer for automatic exception capture.

1. Add `from aws_lambda_powertools import Tracer` and `tracer = Tracer()` at module level
2. Decorate the handler function with `@tracer.capture_lambda_handler`
3. Use `@tracer.capture_method` on DynamoDB query and CloudWatch `put_metric_data` functions
4. Powertools Tracer handles `auto_patch=True` by default — no explicit `patch_all()` needed
5. Add `aws-lambda-powertools[tracer]` to requirements.txt
6. Add `POWERTOOLS_SERVICE_NAME` environment variable in Terraform

---

## Success Criteria

- [ ] Invoking Metrics Lambda produces an X-Ray trace with subsegments
- [ ] DynamoDB query appears as auto-instrumented subsegment
- [ ] CloudWatch `put_metric_data` appears as auto-instrumented subsegment
- [ ] `put_metric_data` failure (throttled, permission denied) shows error in trace
- [ ] No try/catch around X-Ray SDK calls (FR-018)

---

## Blind Spots

1. **Import order**: Powertools Tracer must be imported and `tracer = Tracer()` initialized before boto3 is used, to ensure patching takes effect. Place at top of module.
2. **Cold start latency**: Adding Powertools + X-Ray SDK imports adds ~50-80ms cold start. Acceptable for a Lambda that runs on a schedule, not user-facing.
3. **Requirements.txt**: Must add `aws-lambda-powertools[tracer]` (the `[tracer]` extra pulls in `aws-xray-sdk` transitively).
4. **POWERTOOLS_SERVICE_NAME**: Must be set as Lambda environment variable in Terraform. Without it, traces show `service_undefined` in the service map.
5. **Exception auto-capture (FR-029)**: Powertools `@tracer.capture_method` automatically marks subsegments as error on exception. This is the key advantage over raw `xray_recorder.capture` and the reason for standardization.
