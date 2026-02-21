# Task 14: Standardize on Powertools Tracer Across Non-Streaming Lambdas

**Priority:** P0
**Spec FRs:** FR-029, FR-030, FR-031
**Status:** TODO
**Depends on:** Task 1 (IAM permissions)
**Blocks:** Tasks 2, 4, 13 (all non-streaming instrumentation tasks should use the standardized approach)

> **Round 3 Update:** SSE Streaming Lambda is excluded from this task. Its handler phase uses Powertools Tracer (covered here), but its streaming phase uses OTel SDK with ADOT Lambda Extension (covered in Task 5). The `@tracer.capture_method` decorator MUST NOT be applied to async generator functions (FR-031) — see Task 5 for the correct pattern.

---

## Problem

Two distinct tracing mechanisms are in use, creating an inconsistency gap:

### Problem 1: Exception Capture Gap (FR-029)

- **Dashboard Lambda** uses Powertools `@tracer.capture_method` — automatically captures exceptions as subsegment errors
- **All other Lambdas** use raw `@xray_recorder.capture()` — does NOT auto-capture exceptions
- There are **57 raw `@xray_recorder.capture` decorators** across the codebase that silently close subsegments without marking them as error when exceptions occur
- FR-005's requirement ("mark subsegments as error on exception") is **not achievable** with raw `xray_recorder.capture` alone

### Problem 2: Double-Patching (FR-030)

- **Dashboard Lambda** calls both explicit `patch_all()` (line 31-33) AND initializes `Tracer` with `auto_patch=True` (the default)
- This causes boto3 and requests to be patched twice
- Double-patching is mostly harmless but can cause subtle issues: duplicate subsegments, incorrect timing, and confusing traces

---

## Current State

| Lambda | Tracing Mechanism | Exception Auto-Capture | Patching |
|--------|------------------|----------------------|----------|
| Dashboard | Powertools Tracer | YES | Double (patch_all + Tracer auto_patch) |
| Ingestion | Raw xray_recorder | NO | Single (patch_all) |
| Analysis | Raw xray_recorder | NO | Single (patch_all) |
| Notification | Raw xray_recorder | NO | Single (patch_all) |
| Metrics | None | N/A | None |
| SSE Streaming | Raw xray_recorder | NO | Single (patch_all) |

---

## Target State

| Lambda | Tracing Mechanism | Exception Auto-Capture | Patching |
|--------|------------------|----------------------|----------|
| Dashboard | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| Ingestion | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| Analysis | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| Notification | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| Metrics | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| SSE Streaming (handler phase) | Powertools Tracer | YES | Single (Tracer auto_patch only) |
| SSE Streaming (streaming phase) | OTel SDK + ADOT Extension | YES (manual spans) | N/A (OTel, not X-Ray SDK) |

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/dashboard/handler.py` | Remove explicit `patch_all()` call; keep Tracer with `auto_patch=True` |
| `src/lambdas/ingestion/handler.py` | Replace `patch_all()` + `xray_recorder.capture` with Powertools Tracer |
| `src/lambdas/analysis/handler.py` | Replace `patch_all()` + `xray_recorder.capture` with Powertools Tracer |
| `src/lambdas/notification/handler.py` | Replace `patch_all()` + `xray_recorder.capture` with Powertools Tracer |
| `src/lambdas/metrics/handler.py` | Add Powertools Tracer (new instrumentation, no xray_recorder) |
| `src/lambdas/sse_streaming/handler.py` | Replace `patch_all()` + `xray_recorder.capture` with Powertools Tracer (handler phase only; streaming phase uses OTel — see Task 5) |
| All files with `@xray_recorder.capture` | Replace 57 decorators with `@tracer.capture_method` (EXCEPT async generators in SSE Lambda — FR-031) |
| All `requirements.txt` files | Ensure `aws-lambda-powertools[tracer]` is listed |

---

## What to Change

### Per Lambda (handler files)

1. **Remove**: `from aws_xray_sdk.core import patch_all, xray_recorder` and the `patch_all()` call
2. **Add**: `from aws_lambda_powertools import Tracer` and `tracer = Tracer()` at module level
3. **Replace**: `@xray_recorder.capture('name')` with `@tracer.capture_method`
4. **Replace**: handler decorator (if exists) with `@tracer.capture_lambda_handler`
5. **Verify**: `auto_patch=True` is the default for Powertools Tracer — no explicit call needed

### Per Supporting File (non-handler files with xray_recorder)

1. **Remove**: `from aws_xray_sdk.core import xray_recorder`
2. **Add**: `from aws_lambda_powertools import Tracer` and `tracer = Tracer()` at module level
3. **Replace**: `@xray_recorder.capture('name')` with `@tracer.capture_method`
4. **Replace**: `xray_recorder.begin_subsegment('name')` / `end_subsegment()` with `tracer.provider.in_subsegment('name') as subsegment:`

### Dashboard Lambda (fix double-patching)

1. **Remove**: The explicit `patch_all()` call (lines 31-33)
2. **Keep**: Existing `Tracer()` initialization — it handles patching via `auto_patch=True`

---

## Execution Order

This task MUST be completed before tasks 2, 4, 5, and 13 because those tasks add new subsegments. If new subsegments are added using `xray_recorder.capture` and then this task migrates to Powertools Tracer, the new subsegments would need to be migrated again. Do this standardization first, then all subsequent instrumentation uses the standardized approach.

---

## Success Criteria

- [ ] All 6 Lambda functions use Powertools Tracer for handler phase (not raw xray_recorder)
- [ ] Zero remaining `@xray_recorder.capture` decorators in codebase
- [ ] Zero remaining `patch_all()` calls in codebase (Tracer handles patching)
- [ ] Exceptions raised inside `@tracer.capture_method` decorated functions are automatically captured as subsegment errors
- [ ] Dashboard Lambda has exactly one patching mechanism (Tracer auto_patch)
- [ ] All `requirements.txt` files include `aws-lambda-powertools[tracer]`
- [ ] No try/catch around Tracer calls (FR-018)
- [ ] Existing X-Ray trace structure preserved (same subsegment names, same annotations)

---

## Blind Spots

1. **Tracer service name**: Powertools Tracer uses `POWERTOOLS_SERVICE_NAME` environment variable. Each Lambda needs this set in Terraform (`infrastructure/terraform/main.tf` environment blocks). Without it, the service name defaults to `service_undefined`.
2. **SSE Streaming Phase (Round 3 — Revised)**: Powertools Tracer assumes a Lambda segment exists. During RESPONSE_STREAM streaming (after handler returns), the Tracer's subsegment methods won't work. ~~Phase 2 still needs raw `xray_recorder.begin_segment()` for independent segments.~~ **INVALIDATED in Round 3:** `begin_segment()` is a no-op in Lambda — `LambdaContext.put_segment()` silently discards segments. The streaming phase uses the OTel SDK with ADOT Lambda Extension instead (see Task 5). `@tracer.capture_method` MUST NOT be applied to async generator functions (FR-031) — they silently capture near-zero time.
3. **Shared modules**: Files in `src/lambdas/shared/` (like `circuit_breaker.py`) are imported by multiple Lambdas. Each Lambda creates its own `Tracer()` instance. The shared module should also create a `Tracer()` instance — Powertools handles the singleton pattern internally.
4. **Import order**: Powertools Tracer must be imported and initialized before boto3 is used, to ensure patching takes effect. This is the same constraint as `patch_all()`.
5. **57 decorators**: The migration of 57 `@xray_recorder.capture` decorators is mechanical but needs verification. Each decorator's string argument (subsegment name) should be preserved — Powertools Tracer generates names from function names by default, but custom names may be needed for backward-compatible trace queries.
6. **Test mocking**: Tests that mock `xray_recorder` will need to be updated to mock `Tracer` instead. This affects test files in `tests/unit/` and `tests/integration/`.
