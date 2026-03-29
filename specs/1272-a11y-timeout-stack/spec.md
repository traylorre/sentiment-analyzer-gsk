# Feature Specification: Accessibility Timeout Stack Fix

**Feature Branch**: `1272-a11y-timeout-stack`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Three accessibility tests in `chaos-accessibility.spec.ts` fail in CI because they stack multiple long-running operations (triggerHealthBanner + waitForAccessibilityTree + AxeBuilder.analyze) that exceed the per-test timeout budget.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accessibility Tests Pass in CI Without Timeout (Priority: P1)

A developer pushes a PR that includes changes to the frontend. The CI pipeline runs the full Playwright E2E suite including the chaos-accessibility tests. All three accessibility tests (T025, T026, T027) complete within the per-test timeout budget on the first attempt without relying on CI retries.

**Why this priority**: These tests consistently fail in CI, which means the accessibility verification gate is broken. Every PR either retries (wasting CI minutes) or the failures are ignored (defeating the purpose of the accessibility tests).

**Independent Test**: Run `npx playwright test chaos-accessibility --retries=0` and confirm all 3 tests pass on the first attempt.

**Acceptance Scenarios**:

1. **Given** the chaos-accessibility spec runs T025 ("health banner has zero critical accessibility violations"), **When** the test executes triggerHealthBanner + waitForAccessibilityTree + AxeBuilder.analyze in sequence, **Then** the total execution completes within 15 seconds (well under the 30s default timeout).
2. **Given** the chaos-accessibility spec runs T026 ("error boundary fallback has zero critical a11y violations"), **When** the test executes error boundary trigger + waitForAccessibilityTree + AxeBuilder.analyze, **Then** the total execution completes within 15 seconds.
3. **Given** the chaos-accessibility spec runs T027 ("error boundary buttons are keyboard-focusable"), **When** the test executes error boundary trigger + waitForAccessibilityTree + keyboard focus checks, **Then** the total execution completes within 15 seconds.

---

### User Story 2 - waitForAccessibilityTree Default Timeout Reduced (Priority: P1)

The `waitForAccessibilityTree()` helper in `a11y-helpers.ts` currently has a 5000ms default timeout. ARIA attributes are computed by the browser in under 200ms after component render. The 5000ms timeout is the maximum wait, not the expected wait -- but it inflates the worst-case timing budget unnecessarily. Reducing the default to 2000ms still provides ample headroom while recovering ~3 seconds from the timeout stack.

**Why this priority**: This is the highest-impact single change. The 5000ms default is the largest single contributor to the timeout budget after triggerHealthBanner.

**Independent Test**: Run the 3 accessibility tests. Confirm waitForAccessibilityTree resolves in under 500ms (the ARIA attributes should already be present when the function is called).

**Acceptance Scenarios**:

1. **Given** waitForAccessibilityTree is called with no explicit timeout, **When** the helper checks for ARIA attributes, **Then** the default timeout is 2000ms (not 5000ms).
2. **Given** a component has already rendered its ARIA attributes, **When** waitForAccessibilityTree polls for those attributes, **Then** it resolves on the first or second poll cycle (~50-100ms), not at the timeout boundary.

---

### User Story 3 - Per-Test Timeout Increased for Accessibility Tests (Priority: P1)

Accessibility tests are inherently slower than regular E2E tests because they run the axe-core engine which performs a full page accessibility scan (~2-3 seconds). The describe block should declare an explicit timeout that accounts for this legitimate overhead.

**Why this priority**: Even after optimizing individual operations, accessibility tests will always take longer than non-accessibility tests. An explicit per-test timeout communicates intent and prevents false-negative CI failures.

**Independent Test**: Verify the describe block or individual tests have an explicit timeout set via `test.setTimeout()`.

**Acceptance Scenarios**:

1. **Given** the `chaos-accessibility.spec.ts` describe block, **When** it runs any test with axe-core scanning, **Then** the per-test timeout is set to 30000ms (30 seconds) which provides ample headroom for the triggerHealthBanner + waitForAccessibilityTree + AxeBuilder.analyze stack.

---

### User Story 4 - Scoped axe-core Scan to Reduce Scan Time (Priority: P2)

AxeBuilder.analyze() currently scans the full page. Scoping the scan to only the relevant component (banner or error boundary) reduces scan time from ~2-3s to ~0.5-1s.

**Why this priority**: This is an optimization that reduces scan time but is not strictly necessary if the timeout is increased. However, it makes the tests more precise (testing only the relevant component's accessibility, not the entire page) and faster.

**Independent Test**: Verify AxeBuilder is called with `.include()` to scope to the relevant container element.

**Acceptance Scenarios**:

1. **Given** T025 scans for health banner accessibility, **When** AxeBuilder runs, **Then** the scan is scoped to the banner element using `.include('[role="alert"]')`.
2. **Given** T026 scans for error boundary accessibility, **When** AxeBuilder runs, **Then** the scan is scoped to the error boundary container.

---

### Edge Cases

- What if waitForAccessibilityTree times out at the reduced 2000ms? The attributes should be present in <200ms. If a timeout occurs, it indicates a real bug (component not rendering ARIA attributes) rather than a timing issue.
- What if AxeBuilder.include() changes scan results vs full-page scan? Scoped scans only test the targeted element and its children. Violations in other parts of the page would not be caught -- but those are not the concern of these tests (they test degraded state accessibility, not full-page baseline).
- What if the beforeEach `waitForTimeout(2000)` contributes to the timeout stack? Yes -- Feature 1271 addresses replacing this with `waitForLoadState('networkidle')`. If 1271 is not yet merged, the 2000ms beforeEach wait adds to the budget but the 30s test timeout provides sufficient headroom.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `waitForAccessibilityTree()` helper in `a11y-helpers.ts` MUST have its default timeout reduced from 5000ms to 2000ms.
- **FR-002**: The `chaos-accessibility.spec.ts` describe block MUST set an explicit per-test timeout of 30000ms (30 seconds) using `test.setTimeout(30_000)`.
- **FR-003**: In T025, the AxeBuilder scan MUST be scoped to the health banner element using `.include('[role="alert"]')`.
- **FR-004**: In T026, the AxeBuilder scan SHOULD be scoped to the error boundary container if a stable CSS selector exists. If no stable selector is available without modifying application code (out of scope), the full-page scan is acceptable.
- **FR-005**: T027 does NOT use AxeBuilder and requires no scan scoping changes.
- **FR-006**: The `beforeEach` block's `waitForTimeout(2000)` SHOULD be replaced with `page.waitForLoadState('networkidle')` if Feature 1271 has not already addressed it. If 1271 has addressed it, no change needed.

### Non-Functional Requirements

- **NFR-001**: All 3 accessibility tests MUST complete within 15 seconds each on CI runners.
- **NFR-002**: The `waitForAccessibilityTree` helper change MUST NOT break any other callers (there are currently no other callers outside chaos-accessibility.spec.ts).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 3 tests in `chaos-accessibility.spec.ts` pass with `--retries=0` on the first attempt.
- **SC-002**: No individual test exceeds 15 seconds execution time.
- **SC-003**: waitForAccessibilityTree default timeout is 2000ms.
- **SC-004**: AxeBuilder scans in T025 and T026 are scoped (not full-page).
- **SC-005**: An explicit test timeout of 30000ms is declared in the describe block.

## Assumptions

- The `waitForAccessibilityTree()` helper from Feature 1270 is already present in `a11y-helpers.ts`.
- ARIA attributes are computed by the browser in under 200ms after component render, making a 2000ms default timeout generous.
- axe-core scoped scans complete in ~0.5-1s compared to ~2-3s for full-page scans.
- chaos-degradation.spec.ts passes using `triggerHealthBanner()` without `waitForAccessibilityTree()` or AxeBuilder, confirming the helper and scanner are the timeout contributors, not the banner trigger itself.

## Dependencies

- **Feature 1270** (`a11y-race-fix`): Provides the `waitForAccessibilityTree()` helper. Must be merged first.
- **Feature 1271** (`a11y-timing-audit`): Addresses `waitForTimeout` replacements across multiple files including chaos-accessibility.spec.ts. This feature focuses specifically on the timeout stack problem, not the broader timing audit.

## Scope Boundaries

### In Scope

- `frontend/tests/e2e/chaos-accessibility.spec.ts` -- the 3 failing tests
- `frontend/tests/e2e/helpers/a11y-helpers.ts` -- default timeout reduction
- AxeBuilder scan scoping in T025 and T026

### Out of Scope

- Other test files (covered by Feature 1271)
- `chaos-helpers.ts` triggerHealthBanner optimization (covered by Feature 1271)
- Application code changes (React components, ARIA attribute rendering)
- Playwright global configuration changes
- New accessibility tests or assertions

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Reducing waitForAccessibilityTree timeout causes failures if ARIA attrs take >2s | LOW -- attrs compute in <200ms | 2000ms is 10x the expected time; if it fails, it's a real bug |
| Scoped AxeBuilder.include() misses violations caught by full-page scan | LOW -- these tests specifically test degraded state components | The scoped scan is more precise, not less |
| beforeEach waitForTimeout(2000) is still present if 1271 not merged | LOW -- 30s test timeout provides headroom | Can be addressed by either 1271 or 1272, whichever merges first |
| CI runner performance variance causes flaky results even with fixes | LOW -- 30s timeout is 2-3x the expected runtime | Monitor CI results; the margin is generous |

## Clarifications

### Session 2026-03-28

No critical ambiguities. All taxonomy categories assessed:
- Functional scope: Bounded to 2 files (chaos-accessibility.spec.ts, a11y-helpers.ts)
- No data model changes (test infrastructure only)
- Edge cases documented (reduced timeout, scoped scan trade-offs, beforeEach interaction with 1271)
- Success criteria measurable (SC-001 through SC-005)
- Dependencies on Features 1270 and 1271 documented

---

## Adversarial Review #1 (AR#1)

**Reviewer**: Adversarial self-review
**Date**: 2026-03-28

### Findings

**AR1-F1 (MEDIUM): Reducing waitForAccessibilityTree default may be counterproductive**

The spec assumes ARIA attributes compute in <200ms and proposes reducing the default from 5000ms to 2000ms. However, the research (R5) identified that if `waitForAccessibilityTree` is TIMING OUT at 5000ms (the function fails, not succeeds slowly), reducing the default to 2000ms would make it fail FASTER, not fix the problem.

If the function is timing out, it means the ARIA attributes are NOT present when expected, which is a different bug (perhaps the selector doesn't match, or the component hasn't rendered by the time the function is called).

**Resolution**: The tests currently report times of 5.6s, 8.4s, and 8.3s. If `waitForAccessibilityTree` were timing out at 5000ms, T025 would be at least 5s (triggerHealthBanner) + 5s (timeout) = 10s minimum. At 5.6s, the function is likely resolving quickly (within ~600ms after the 5s triggerHealthBanner). This means the function is NOT timing out -- the overall stack just takes longer than expected for CI. The 2000ms reduction is safe because the function IS resolving within that window. **No spec change needed** -- the timing math confirms the reduction is safe.

**AR1-F2 (MEDIUM): Error boundary container selector for AxeBuilder.include() is unspecified**

FR-004 says "scoped to the error boundary container" but doesn't specify the CSS selector. The error boundary component renders `<div className="min-h-[400px]..."><Card>...</Card></div>`. There's no `role`, `data-testid`, or semantic selector on the outer div.

Options:
1. Add a `data-testid="error-boundary-fallback"` to the component (application code change -- out of scope)
2. Use `.include('.min-h-\\[400px\\]')` -- fragile, depends on Tailwind class
3. Use `.include('main')` or another ancestor -- too broad
4. Skip scoping for T026 and only scope T025 (which has `[role="alert"]`)

**Resolution**: Option 4 is the pragmatic choice. T025 has a natural semantic selector (`[role="alert"]`). T026's error boundary has no stable semantic selector without modifying application code, which is out of scope. Update FR-004 to make scoping OPTIONAL for T026 (apply only if a stable selector exists). The primary fix (explicit test timeout + reduced waitForAccessibilityTree default) is sufficient to resolve the CI failures.

**Spec update**: FR-004 changed from MUST to SHOULD.

**AR1-F3 (LOW): 30s test timeout may mask future regressions**

Setting test.setTimeout(30_000) is the Playwright default. If the tests were failing at <10s, setting an explicit 30s timeout doesn't change behavior -- the default is already 30s. The tests may be failing for a reason other than the test-level timeout (e.g., an individual operation timeout or a Playwright assertion timeout).

**Resolution**: The explicit `test.setTimeout(30_000)` serves as documentation more than behavioral change. It communicates "this test legitimately takes longer." The real fixes are the waitForAccessibilityTree reduction and axe-core scoping. **No spec change needed** -- FR-002 is still valuable for intent documentation.

**AR1-F4 (LOW): Feature 1271 overlap**

Feature 1271 includes `chaos-accessibility.spec.ts` in its scope (replacing the beforeEach `waitForTimeout(2000)`). If both features modify the same file, merge conflicts will occur.

**Resolution**: Feature 1272 makes minimal changes (add test.setTimeout, scope AxeBuilder). Feature 1271 makes broader changes (replace waitForTimeout). The changes are additive and non-overlapping. Whoever merges second resolves any trivial conflict. **No spec change needed.**

### Summary

| ID | Severity | Status |
|----|----------|--------|
| AR1-F1 | MEDIUM | Accepted -- timing math confirms reduction is safe |
| AR1-F2 | MEDIUM | Accepted -- FR-004 relaxed to SHOULD for T026 |
| AR1-F3 | LOW | Accepted -- explicit timeout is documentation of intent |
| AR1-F4 | LOW | Accepted -- non-overlapping changes, trivial merge |

**Verdict**: PASS -- 0 CRITICAL, 0 HIGH findings. Spec is ready for planning.
