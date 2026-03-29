# Requirements Checklist: 1272-a11y-timeout-stack

## Functional Requirements

- [x] FR-001: waitForAccessibilityTree default timeout reduced from 5000ms to 2000ms
- [x] FR-002: test.setTimeout(30_000) added to chaos-accessibility describe block
- [x] FR-003: T025 AxeBuilder scoped with .include('[role="alert"]')
- [x] FR-004: T026 AxeBuilder scoping evaluated -- no stable selector without app code change, full-page scan retained per AR#1-F2
- [x] FR-005: T027 confirmed no AxeBuilder changes needed
- [x] FR-006: beforeEach waitForTimeout(2000) replaced with waitForLoadState('networkidle')

## Non-Functional Requirements

- [ ] NFR-001: All 3 tests complete within 15 seconds each (requires CI verification)
- [x] NFR-002: No regressions in other callers of waitForAccessibilityTree (confirmed: no other callers exist)

## Success Criteria

- [ ] SC-001: All 3 tests pass with --retries=0 (requires CI verification)
- [ ] SC-002: No test exceeds 15 seconds (requires CI verification)
- [x] SC-003: Default timeout is 2000ms in a11y-helpers.ts
- [x] SC-004: T025 AxeBuilder scan is scoped to [role="alert"]
- [x] SC-005: Explicit 30s timeout declared in describe block

## Pre-Merge Checklist

- [ ] GPG-signed commits
- [ ] No application code changes (test infrastructure only) -- VERIFIED
- [x] Feature 1270 dependency satisfied (waitForAccessibilityTree exists in a11y-helpers.ts)
- [ ] No merge conflicts with Feature 1271 (or trivially resolved)
