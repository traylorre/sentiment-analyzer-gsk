# Implementation Plan: Config Helper Resilience

**Branch**: `1335-config-helper-resilience` | **Date**: 2026-04-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1335-config-helper-resilience/spec.md`

## Summary

Harden `createTestConfig()` in `frontend/tests/e2e/helpers/clean-state.ts` to throw descriptive errors on failure instead of silently timing out. Add post-submit creation verification, explicit ticker selection guard, and replace `waitForTimeout` with `waitForLoadState('networkidle')` (timeout-capped). Single-file change with no signature modifications.

## Technical Context

**Language/Version**: TypeScript (Playwright ^1.57.0)
**Primary Dependencies**: `@playwright/test` (existing, no new deps)
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright E2E tests (existing test files are the verification)
**Target Platform**: Local dev + CI (GitHub Actions)
**Project Type**: Single file change (`clean-state.ts`)
**Performance Goals**: Helper completes within 15s total
**Constraints**: Function signature must not change; all 6 call sites must work without modification
**Scale/Scope**: ~1 file modified, ~50-80 lines changed

## Constitution Check

| Constitution Requirement | Status | Notes |
|--------------------------|--------|-------|
| **7) Testing & Validation** | PASS | Existing tests serve as verification |
| Implementation Accompaniment | PASS | No new production code, only test infrastructure |
| **8) Git Workflow** | PASS | Feature branch, GPG signing |
| Pre-Push Requirements | PASS | `make validate` before push |
| **10) Local SAST** | N/A | No security-sensitive code |

**Gate Result**: PASS - No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1335-config-helper-resilience/
├── spec.md              # Feature specification
├── plan.md              # This file
├── tasks.md             # Task breakdown
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (modified files)

```text
frontend/tests/e2e/helpers/
└── clean-state.ts       # MODIFY: createTestConfig() hardening
```

## Design Decisions

### DD-001: Error Wrapping Strategy

**Options**:
1. Wrap each Playwright assertion in try/catch with custom error
2. Use a helper function that wraps assertions with context
3. Create step-tracking state that enriches the final error

**Choice**: Option 1 -- Direct try/catch wrapping. Simplest, most readable, and each step gets its own descriptive message. Option 2 adds abstraction that obscures the Playwright calls. Option 3 is clever but makes debugging harder.

### DD-002: Post-Submit Verification Signal

**Options**:
1. Check for success toast only
2. Check for config name in list only
3. Check for URL change only
4. Check all three with `Promise.race`-style fallthrough

**Choice**: Option 4 with sequential short-timeout checks. Try toast first (1.5s), then config name in list (3s), then URL change (2s). If none succeed within 5s total, throw. This handles the toast auto-dismiss (EC-003) and varying app behavior.

### DD-003: networkidle Timeout Cap

**Options**:
1. Use `waitForLoadState('networkidle')` with no timeout cap
2. Use `waitForLoadState('networkidle')` wrapped in `Promise.race` with a 5s timer
3. Use `waitForTimeout(2000)` as before but shorter

**Choice**: Option 2 -- Cap at 5s. If TanStack Query auto-refetch is active (AR-003), networkidle may never fire. The 5s cap ensures we proceed to verification regardless.

### DD-004: Ticker Selection Failure Behavior

**Options**:
1. Silently skip (current behavior)
2. Throw immediately
3. Retry once then throw

**Choice**: Option 2 -- Throw immediately (FR-002). Silent skip is the root cause of the cascading failures. The ticker mock is set up before navigation, so if it's not visible, something is fundamentally wrong.

## Implementation Phases

### Phase 1: Refactor createTestConfig() (single file change)

**File**: `frontend/tests/e2e/helpers/clean-state.ts`

Changes:
1. Wrap CTA click in try/catch with descriptive error (lines 65-68)
2. Wrap name input fill in try/catch with descriptive error (lines 71-73)
3. Remove `.catch(() => false)` on ticker input visibility -- throw on failure (lines 78-83)
4. Add explicit ticker selection verification after option click
5. Wrap submit button enabled check in try/catch with descriptive error (lines 87-88)
6. Replace `waitForTimeout(1000)` with timeout-capped `waitForLoadState('networkidle')` (line 90)
7. Add post-submit creation verification: check toast, then list, then URL (new code)
8. Wrap `page.unroute()` in try/catch (line 93, AR-004)

### Phase 2: Verification (no code changes)

Run existing tests to verify:
```bash
cd frontend && npx playwright test config-crud alert-crud dialog-dismissal --reporter=list
```

All 6 call sites must pass. No test file modifications needed.

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `networkidle` hangs due to auto-refetch | Medium | Low | 5s timeout cap (DD-003) |
| Toast selector doesn't match Sonner version | Low | Low | Fallback to list check |
| Ticker input placeholder changed | Low | Medium | Error message includes tried selectors |
| New verification adds >5s to helper | Low | Medium | Short timeouts on each check |
