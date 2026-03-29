# Feature 1272: Accessibility Timeout Stack Fix -- Tasks

## Scope

Fix three accessibility tests in `chaos-accessibility.spec.ts` that fail in CI due to stacking long-running operations. Apply three complementary fixes: reduce helper timeout default, set explicit test timeout, scope axe-core scans.

## Task Dependency Graph

```
T1 (a11y-helpers.ts default timeout) ──┐
T2 (chaos-accessibility.spec.ts edits) ├──→ T3 (verify all pass)
```

T1 and T2 can be done in parallel (different files). T3 depends on both.

## Tasks

### T1: Reduce waitForAccessibilityTree default timeout

**File**: `frontend/tests/e2e/helpers/a11y-helpers.ts`
**Change**: Line 28 -- change `timeout = 5000` to `timeout = 2000`
**Spec refs**: FR-001, SC-003
**Risk**: LOW -- no other callers; callers can pass explicit timeout to override

### T2: Fix chaos-accessibility.spec.ts

**File**: `frontend/tests/e2e/chaos-accessibility.spec.ts`
**Changes**:

1. **Add test.setTimeout(30_000)** as first statement inside the describe block (FR-002, SC-005)
2. **Replace beforeEach waitForTimeout(2000)** with `page.waitForLoadState('networkidle')` (FR-006)
3. **Scope T025 AxeBuilder** -- add `.include('[role="alert"]')` before `.withTags()` in the first AxeBuilder call (FR-003, SC-004)
4. **T026 AxeBuilder** -- no scoping change per AR#1-F2 (FR-004 is SHOULD, no stable selector)
5. **T027** -- no AxeBuilder changes needed (FR-005)

### T3: Verify deterministic pass

Run all 3 tests with `--retries=0`:
```bash
cd frontend && npx playwright test chaos-accessibility --retries=0
```

**Pass criteria**: All 3 tests pass on first attempt, each under 15 seconds (SC-001, SC-002).

## Adversarial Review of Tasks

**Highest-risk task**: T1 -- changing a shared helper default affects all future callers. Current callers: only `chaos-accessibility.spec.ts`. Mitigated by: any caller can pass explicit `timeout` to override.

**Most likely rework**: T2.2 (beforeEach replacement) may conflict with Feature 1271. Trivial merge resolution.

**Gate**: READY FOR IMPLEMENTATION
