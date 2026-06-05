# Feature Specification: E2E Worker Isolation

**Feature Branch**: `1324-e2e-worker-isolation`
**Created**: 2026-04-05
**Status**: Draft
**Input**: Playwright E2E tests run with 4 parallel workers; 2 test files use Date.now() for resource naming, creating collision risk when workers execute at the same millisecond.

## Problem Statement

Playwright E2E tests now run with `workers: 4`. Two test files generate resource names using `Date.now()`, which returns millisecond-precision timestamps. When two workers execute tests at the same millisecond, resource names collide, causing flaky test failures:

| File | Pattern | Risk |
|------|---------|------|
| `magic-link.spec.ts` | `e2e-magiclink-${Date.now()}@test.example.com` (describe scope) | Email collision across workers; shared across 4 tests in block |
| `dialog-dismissal.spec.ts` | `e2e-delete-test-${Date.now()}`, `e2e-escape-test-${Date.now()}` (test scope) | Config name collision across workers |

**Safe pattern already in use**: `config-crud.spec.ts` uses `e2e-${test.info().testId}` which is globally unique per test execution. This is the canonical pattern.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - All E2E Test Resources Use Globally Unique Identifiers (Priority: P1)

As a CI pipeline, I need every E2E test to use globally unique resource identifiers so that parallel worker execution never produces resource name collisions.

**Why this priority**: Without unique identifiers, 4-worker parallel runs produce intermittent collisions that are extremely difficult to reproduce and diagnose.

**Independent Test**: Run `npx playwright test --workers=4 --repeat-each=10` and verify zero resource collision failures across all runs.

**Acceptance Scenarios**:

1. **Given** `magic-link.spec.ts` runs in parallel with other tests, **When** two workers execute magic-link tests at the same millisecond, **Then** each test uses a distinct email address derived from `test.info().testId`
2. **Given** `dialog-dismissal.spec.ts` runs in parallel, **When** the `delete dialog: cancel preserves item` and `delete dialog: escape closes` tests run concurrently, **Then** each creates a config with a unique name derived from `test.info().testId`
3. **Given** all E2E tests run with 4+ workers, **When** the full suite completes, **Then** zero tests fail due to resource name collisions

---

### Edge Cases

- **`test.info().testId` availability**: `test.info()` is only available inside `test()` callbacks and hooks (`beforeEach`, `afterEach`), NOT at `test.describe()` scope. `magic-link.spec.ts` currently defines `testEmail` at describe scope (line 12) -- this must be moved into each test or a `beforeEach` hook.
- **testId length limits**: `test.info().testId` is a hex string (e.g., `a1b2c3d4e5f6`). For email addresses this is fine. For config names that may have length limits, verify the combined prefix + testId stays within bounds.
- **testId uniqueness guarantee**: `testId` is globally unique per test in the Playwright test plan -- it is derived from the file path, describe block, and test title. Even with `--repeat-each`, each repetition gets a unique testId.

## Requirements *(mandatory)*

### Functional Requirements

- **R1**: `magic-link.spec.ts` MUST replace the describe-scoped `Date.now()` email with per-test `test.info().testId`-based emails
- **R2**: `dialog-dismissal.spec.ts` MUST replace `Date.now()` config names with `test.info().testId`-based names

### Key Entities

- **testId**: Playwright-assigned globally unique identifier per test, accessible via `test.info().testId`
- **Resource name**: Any string used to identify test-created resources (emails, config names) that must be unique across parallel workers

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero `Date.now()` calls remain in E2E test resource naming across both files
- **SC-002**: All resource names include `test.info().testId` for global uniqueness
- **SC-003**: `npx playwright test --workers=4` passes with zero collision-related failures
- **SC-004**: No regressions in existing test assertions (email format, config name display)

## Out of Scope

- Changing `config-crud.spec.ts` (already uses safe `test.info().testId` pattern)
- Changing `alert-crud.spec.ts` (already safe)
- Modifying Playwright worker count or parallelism configuration
- Adding new test cases -- this is a naming-only fix

---

## Adversarial Review #1

**Reviewer**: Adversarial Analysis
**Date**: 2026-04-05

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | `test.info().testId` is only available inside `test()` callbacks, not at `test.describe()` scope. `magic-link.spec.ts` line 12 defines `testEmail` at describe scope. Attempting `test.info()` there would throw a runtime error. | Move email construction into each `test()` body or a `test.beforeEach()` hook. Since tests 2-4 (`valid magic link token`, `reused magic link token`, `expired magic link token`) do not actually use `testEmail` for backend resource creation (they use hardcoded invalid/expired tokens), only test 1 (`requesting magic link shows confirmation message`) and test 2 (which re-requests the link) need the unique email. Safest approach: define `testEmail` inside each test that uses it. |
| LOW | `dialog-dismissal.spec.ts` config names (`e2e-delete-test-`, `e2e-escape-test-`) include descriptive prefixes. Replacing `Date.now()` with `testId` changes the visual appearance in test output but does not affect functionality. | Acceptable. Prefix remains for human readability; testId provides uniqueness. |
| LOW | If `test.info().testId` contains characters invalid in email local-part, the email could be rejected. | testId is hexadecimal (alphanumeric only). Safe for email local-part per RFC 5321. |

### Gate Statement

Spec is **APPROVED WITH CONDITION**: Implementation MUST use per-test email construction (inside `test()` body or `beforeEach`), not describe-scope. The describe-scope pattern is the root cause of the collision risk AND would cause a runtime error with `test.info()`.

---

## Clarifications

1. **Q: Should we use `beforeEach` or inline in each test?** A: Inline in each test is simpler and more explicit. `beforeEach` adds a layer of indirection for only 2 tests that need the email. Use inline.
2. **Q: Should the email prefix change?** A: Keep `e2e-magiclink-` prefix for log readability. Format: `e2e-magiclink-${test.info().testId}@test.example.com`.
3. **Q: Should dialog-dismissal config names keep their descriptive prefixes?** A: Yes. `e2e-delete-test-${test.info().testId}` and `e2e-escape-test-${test.info().testId}` preserve intent.
