# Implementation Tasks: Fix SSE E2E Integration Test Timeouts

**Branch**: `082-fix-sse-e2e-timeouts` | **Date**: 2025-12-10 | **Plan**: [plan.md](./plan.md)
**Input**: Implementation plan from `/specs/082-fix-sse-e2e-timeouts/plan.md`

## Task Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1 | 3 | Verify infrastructure (SSE Lambda configuration) |
| Phase 2 | 4 | Fix URL routing (PreprodAPIClient + CI workflow) |
| Phase 3 | 3 | Implement heartbeat keep-alive |
| Phase 4 | 3 | Verify & validate |

**Total**: 13 tasks | **Estimated Complexity**: Medium

## User Story Mapping

| User Story | Phase | Tasks |
|------------|-------|-------|
| US1: Diagnose SSE Streaming Failures | Phase 1 | T001-T003 |
| US2: Fix SSE Streaming Endpoint Response | Phase 2, Phase 3 | T004-T010 |
| US3: Verify E2E Test Suite Passes | Phase 4 | T011-T013 |

## Success Criteria Traceability

| SC | Task(s) | Verification |
|----|---------|--------------|
| SC-001 | T004, T005, T006 | All 6 SSE tests pass |
| SC-002 | T001, T002 | Connection < 10 seconds |
| SC-003 | T007 | Deploy workflow succeeds |
| SC-004 | T011 | Non-SSE tests still pass |
| SC-005 | T008, T009, T010 | Heartbeat within 35s |

---

## Phase 1: Infrastructure Verification

### T001: Verify SSE Lambda RESPONSE_STREAM configuration

**User Story**: US1 (Diagnose)
**File**: `infrastructure/terraform/main.tf`
**Action**: READ (verify only)

**Steps**:
1. Confirm SSE Lambda uses `invoke_mode = "RESPONSE_STREAM"` (expected: line ~642)
2. Confirm Dashboard Lambda uses `invoke_mode = "BUFFERED"` (expected: line ~421)
3. Document any discrepancies

**Acceptance**:
- [x] SSE Lambda configured for streaming (VERIFIED in plan.md)
- [x] Dashboard Lambda configured for buffered (VERIFIED in plan.md)

**Status**: COMPLETE (verified during diagnosis)

---

### T002: Verify SSE Lambda Function URL output exists

**User Story**: US1 (Diagnose)
**File**: `infrastructure/terraform/outputs.tf` or `main.tf` outputs block
**Action**: READ (verify only)

**Steps**:
1. Find `sse_lambda_function_url` output definition
2. Confirm it references the SSE Lambda Function URL resource
3. Document the exact output name for CI workflow reference

**Acceptance**:
- [ ] Output `sse_lambda_function_url` exists
- [ ] Output correctly references SSE Lambda Function URL

---

### T003: Document root cause analysis findings

**User Story**: US1 (Diagnose)
**File**: `specs/082-fix-sse-e2e-timeouts/spec.md`
**Action**: READ (verify documentation)

**Steps**:
1. Confirm root cause section is complete
2. Confirm evidence supporting diagnosis is documented
3. Verify FR-007, FR-008, FR-009 capture the required fix

**Acceptance**:
- [x] Root cause documented (VERIFIED in spec.md)
- [x] Evidence documented (VERIFIED in spec.md)
- [x] Fix requirements captured (FR-007, FR-008, FR-009)

**Status**: COMPLETE (documented in spec.md)

---

## Phase 2: URL Routing Fix

### T004: Add SSE_LAMBDA_URL support to PreprodAPIClient

**User Story**: US2 (Fix)
**File**: `tests/e2e/helpers/api_client.py`
**Action**: MODIFY
**Requirement**: FR-007, FR-008

**Steps**:
1. Add `sse_url` parameter to `__init__` method
2. Add `SSE_LAMBDA_URL` environment variable fallback
3. Default to `base_url` if `SSE_LAMBDA_URL` not set

**Code Change**:
```python
def __init__(
    self,
    base_url: str | None = None,
    sse_url: str | None = None,  # NEW
    timeout: float = 30.0,
):
    self.base_url = base_url or os.environ.get("PREPROD_API_URL", "...")
    self.sse_url = sse_url or os.environ.get("SSE_LAMBDA_URL", self.base_url)
```

**Acceptance**:
- [ ] `sse_url` parameter added to `__init__`
- [ ] `SSE_LAMBDA_URL` environment variable read
- [ ] Falls back to `base_url` if not set

---

### T005: Implement path-based URL routing in stream_sse()

**User Story**: US2 (Fix)
**File**: `tests/e2e/helpers/api_client.py`
**Action**: MODIFY
**Requirement**: FR-008

**Steps**:
1. Modify `stream_sse()` method to detect `/api/v2/stream*` paths
2. Route matching paths to `self.sse_url`
3. Route non-matching paths to `self.base_url`

**Code Change**:
```python
async def stream_sse(self, path: str, ...) -> tuple[int, dict, str]:
    # Route to SSE Lambda URL for streaming endpoints
    effective_url = self.sse_url if path.startswith("/api/v2/stream") else self.base_url
    url = f"{effective_url}{path}"
    ...
```

**Acceptance**:
- [ ] `/api/v2/stream*` paths route to `sse_url`
- [ ] Other paths route to `base_url`
- [ ] URL construction works correctly

---

### T006: Add docstring explaining dual-URL architecture

**User Story**: US2 (Fix)
**File**: `tests/e2e/helpers/api_client.py`
**Action**: MODIFY

**Steps**:
1. Update class docstring explaining two-Lambda architecture
2. Document when each URL is used
3. Reference this spec for context

**Acceptance**:
- [ ] Docstring explains SSE vs Dashboard Lambda routing
- [ ] Documents `PREPROD_API_URL` vs `SSE_LAMBDA_URL`

---

### T007: Set SSE_LAMBDA_URL in CI workflow

**User Story**: US2 (Fix)
**File**: `.github/workflows/deploy.yml`
**Action**: MODIFY
**Requirement**: FR-009

**Steps**:
1. Add step to capture `sse_lambda_function_url` Terraform output
2. Export as `SSE_LAMBDA_URL` environment variable
3. Ensure available to E2E test job

**Code Change**:
```yaml
- name: Set SSE Lambda URL
  run: |
    SSE_URL=$(terraform output -raw sse_lambda_function_url)
    echo "SSE_LAMBDA_URL=$SSE_URL" >> $GITHUB_ENV
```

**Acceptance**:
- [ ] Terraform output captured correctly
- [ ] Environment variable exported
- [ ] E2E tests have access to variable

---

## Phase 3: Heartbeat Implementation

### T008: Locate SSE event generator in handler

**User Story**: US2 (Fix)
**File**: `src/sse/handler.py`
**Action**: READ

**Steps**:
1. Find the async generator that yields SSE events
2. Identify where heartbeat logic should be inserted
3. Understand current event format

**Acceptance**:
- [ ] Event generator located
- [ ] Insertion point identified
- [ ] Current format understood

---

### T009: Implement 30-second heartbeat in SSE generator

**User Story**: US2 (Fix)
**File**: `src/sse/handler.py`
**Action**: MODIFY
**Requirement**: FR-010

**Steps**:
1. Add heartbeat timer tracking last event time
2. Yield heartbeat comment if 30 seconds elapsed
3. Format: `: heartbeat\n\n` (SSE comment format)

**Code Change** (conceptual):
```python
async def event_generator():
    last_event_time = time.monotonic()
    while True:
        # Check for heartbeat
        if time.monotonic() - last_event_time >= 30:
            yield ": heartbeat\n\n"
            last_event_time = time.monotonic()

        # Check for actual events
        event = await get_next_event()
        if event:
            yield format_sse_event(event)
            last_event_time = time.monotonic()

        await asyncio.sleep(0.1)  # Small sleep to prevent busy loop
```

**Acceptance**:
- [ ] Heartbeat sent every 30 seconds during idle
- [ ] Uses SSE comment format (`: heartbeat\n\n`)
- [ ] Timer resets on actual event send

---

### T010: Add heartbeat E2E test

**User Story**: US2 (Fix)
**File**: `tests/e2e/test_sse.py`
**Action**: MODIFY
**Requirement**: SC-005

**Steps**:
1. Add test that opens SSE connection and waits for heartbeat
2. Assert heartbeat received within 35 seconds
3. Use `@pytest.mark.slow` if appropriate

**Code Change**:
```python
@pytest.mark.preprod
async def test_sse_heartbeat_keepalive(api_client):
    """Verify SSE connection receives heartbeat within 35 seconds."""
    async with api_client.stream_sse("/api/v2/stream") as stream:
        start = time.monotonic()
        async for event in stream:
            if event.startswith(": heartbeat"):
                elapsed = time.monotonic() - start
                assert elapsed <= 35, f"Heartbeat took {elapsed}s (expected <= 35s)"
                break
        else:
            pytest.fail("No heartbeat received within timeout")
```

**Acceptance**:
- [ ] Test verifies heartbeat within 35 seconds
- [ ] Test marked with appropriate pytest marker
- [ ] Test handles timeout gracefully

---

## Phase 4: Verification & Validation

### T011: Run full E2E test suite and verify no regression

**User Story**: US3 (Verify)
**Command**: `pytest tests/e2e/ -m preprod`
**Requirement**: SC-001, SC-004

**Steps**:
1. Run all E2E tests in preprod
2. Verify all 6 SSE tests pass
3. Verify non-SSE tests still pass

**Acceptance**:
- [ ] All 6 SSE tests pass (SC-001)
- [ ] Non-SSE tests pass (SC-004)
- [ ] No new test failures

---

### T012: Verify pipeline deploy workflow completes

**User Story**: US3 (Verify)
**Action**: Monitor GitHub Actions
**Requirement**: SC-003

**Steps**:
1. Push changes to feature branch
2. Monitor deploy workflow execution
3. Verify workflow completes with "success" status

**Acceptance**:
- [ ] Deploy workflow triggers
- [ ] All jobs complete successfully
- [ ] No timeout errors in logs

---

### T013: Document fix in PR description

**User Story**: US3 (Verify)
**Action**: Create PR

**Steps**:
1. Create PR with clear description of fix
2. Reference this spec and root cause
3. Include test evidence

**PR Template**:
```markdown
## Summary
- Fix SSE E2E timeout by routing streaming requests to SSE Lambda URL
- Add heartbeat keep-alive to prevent idle connection timeout

## Root Cause
PreprodAPIClient used single PREPROD_API_URL for all requests, but SSE
streaming endpoints require the SSE Lambda (RESPONSE_STREAM mode), not
the Dashboard Lambda (BUFFERED mode).

## Changes
- `tests/e2e/helpers/api_client.py`: Add SSE_LAMBDA_URL routing
- `.github/workflows/deploy.yml`: Export SSE_LAMBDA_URL from TF output
- `src/sse/handler.py`: Add 30-second heartbeat

## Test Evidence
- All 6 SSE tests pass
- Non-SSE tests unaffected
- Heartbeat received within 35s

## References
- Spec: specs/082-fix-sse-e2e-timeouts/spec.md
- Plan: specs/082-fix-sse-e2e-timeouts/plan.md
```

**Acceptance**:
- [ ] PR created with clear description
- [ ] Root cause explained
- [ ] Test evidence provided

---

## Implementation Order

```
Phase 1 (Verify)     Phase 2 (Fix)           Phase 3 (Heartbeat)   Phase 4 (Validate)
    |                    |                        |                     |
    v                    v                        v                     v
  T001 ---------------> T004 ------------------> T008                  T011
  T002 ---------------> T005                     T009                  T012
  T003                  T006                     T010                  T013
                        T007
```

**Dependencies**:
- T004 -> T005 (SSE URL must exist before routing logic)
- T005 -> T007 (Routing logic before CI workflow)
- T008 -> T009 (Understand handler before modifying)
- T009 -> T010 (Heartbeat impl before heartbeat test)
- Phase 2 + Phase 3 -> Phase 4 (All fixes before validation)

---

**Next Step**: Run `/speckit.implement` to begin implementation starting with Phase 2 (Phase 1 verification is already complete per plan.md).
