# Tasks: Fix Vacuous E2E Tests

**Input**: Design documents from `/specs/1322-fix-vacuous-e2e-tests/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Fix Vacuous Tests

**Purpose**: Modify the 2 vacuous tests in `first-impression.spec.ts` to assert real behavior.

- [ ] T-001 [US1, R1] Fix the `should have working navigation tabs` test in `frontend/tests/e2e/first-impression.spec.ts` (lines 21-36). Add an `else` block after the existing `if (isMobile)` block that asserts desktop navigation behavior: (a) locate desktop nav container via `getByRole('navigation', { name: /main/i })` and assert visible, (b) assert exactly 4 navigation links exist within the container, (c) assert each link is visible with the correct name: Dashboard, Configs, Alerts, Settings. Keep the existing mobile `if` block unchanged. See Change 1 in plan.md for exact code.

- [ ] T-002 [US2, R2] Fix the `should respect reduced motion preference` test in `frontend/tests/e2e/first-impression.spec.ts` (lines 65-73). Replace the entire test body: (a) call `page.emulateMedia({ reducedMotion: 'reduce' })`, (b) navigate to `/`, (c) evaluate `getComputedStyle(document.body)` and assert `animationDuration === '0.01ms'` and `transitionDuration === '0.01ms'`, (d) call `page.emulateMedia({ reducedMotion: 'no-preference' })`, (e) navigate to `/` again, (f) assert `animationDuration !== '0.01ms'` and `transitionDuration !== '0.01ms'`. See Change 2 in plan.md for exact code.

**Checkpoint**: Both tests modified with substantive assertions. No changes to `chaos.spec.ts` (R3).

---

## Phase 2: Local Verification

**Purpose**: Confirm both fixed tests pass locally and are non-vacuous.

- [ ] T-003 [NR1, SC-001, SC-002] Run both modified tests locally to verify they pass: `cd frontend && npx playwright test tests/e2e/first-impression.spec.ts`. If either test fails: (a) for T-001, inspect the actual desktop navigation DOM to find the correct roles and selectors, adjust assertions accordingly; (b) for T-002, check the computed style values returned by the browser -- they may be reported in a different format (e.g., `'0s'` instead of `'0.01ms'`), adjust expected values accordingly. Both tests must pass before proceeding.

**Checkpoint**: Both tests pass locally. Test execution time increase is within 2s budget (NR2).

---

## Phase 3: Non-Vacuousness Verification

**Purpose**: Confirm the tests would fail if the assertions were removed (SC-003).

- [ ] T-004 [SC-003] Verify non-vacuousness by mental review (no code change needed): (a) T-001 `else` block contains 6 `expect` calls that query specific DOM elements -- if removed, the test body on desktop is empty (same as before, vacuous). Confirmed non-vacuous. (b) T-002 contains 4 `expect` calls on computed CSS values -- if removed, no assertions remain. Confirmed non-vacuous. (c) Verify `chaos.spec.ts` has no diff (SC-004): `git diff frontend/tests/e2e/chaos.spec.ts` should show nothing.

**Checkpoint**: All success criteria verified.

---

## Dependencies & Execution Order

- **T-001** (Phase 1): No dependencies -- start immediately.
- **T-002** (Phase 1): No dependency on T-001 (different test, same file). Can run in parallel with T-001.
- **T-003** (Phase 2): Depends on T-001 and T-002 (both tests must be modified before running).
- **T-004** (Phase 3): Depends on T-003 (tests must pass before verifying non-vacuousness).

### Parallel Opportunities

- T-001 and T-002 can be implemented in parallel (they modify different sections of the same file).

---

## Requirement Coverage

| Requirement | Task(s) | Verification |
|-------------|---------|--------------|
| R1: Desktop navigation assertions | T-001 | T-003 (local run), T-004 (non-vacuous check) |
| R2: Reduced motion CSS verification | T-002 | T-003 (local run), T-004 (non-vacuous check) |
| R3: Chaos auth test unchanged | (none) | T-004 (`git diff` check) |
| NR1: Tests pass in CI | T-003 | Local pass implies CI pass (same viewport) |
| NR2: Execution time budget | T-003 | Observe test timing in Playwright output |
| SC-001: Navigation test >= 2 assertions | T-001 | 6 assertions added in `else` block |
| SC-002: Reduced motion checks CSS values | T-002 | 4 CSS property assertions |
| SC-003: Tests fail if assertions removed | T-004 | Mental review confirms |
| SC-004: chaos.spec.ts unchanged | T-004 | `git diff` verification |

---

## Adversarial Review #3

**Reviewed**: 2026-04-05

**Highest-risk task**: **T-003** (Local Verification). Both T-001 and T-002 make assumptions about DOM structure and computed style formats that can only be validated by running the tests against the actual application. Specifically:

- **T-001 risk**: The desktop navigation may use different ARIA roles than assumed (`role="navigation"` with `role="link"`). If the sidebar uses `role="list"` with `role="listitem"`, or plain `<a>` tags without explicit roles, the selectors will fail. Mitigation: T-003 includes instructions to inspect actual DOM and adjust selectors.

- **T-002 risk**: The `getComputedStyle` return format for `animation-duration` varies by browser. Chromium may report `0.01ms` as `'0s'` (rounding) or `'0.00001s'` (unit conversion). The `0.01ms !important` CSS rule is authoritative, but the computed value representation is browser-dependent. Mitigation: T-003 includes instructions to check actual computed values and adjust expectations.

**Second-highest risk**: Tailwind CSS configuration. If the project's Tailwind config or PostCSS pipeline modifies or strips the `@media (prefers-reduced-motion: reduce)` block in `globals.css`, T-002 will fail because the CSS rule won't exist in the built output. This is actually a desirable failure -- it would reveal that the accessibility feature is broken.

**Readiness assessment**: READY FOR IMPLEMENTATION. The spec is tight (2 test fixes, 1 documented no-op), the plan maps changes 1:1 to requirements, and the task list includes a local verification step that catches selector/format mismatches before merge. The highest risks are mitigated by T-003's adjustment instructions.
