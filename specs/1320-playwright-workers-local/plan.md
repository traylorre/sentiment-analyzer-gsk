# Feature 1320: Implementation Plan

## Status: PLANNED

## Change Summary

Single-line edit in `frontend/playwright.config.ts`.

## Changes

### C1: Set Local Workers to 4

**File:** `frontend/playwright.config.ts`
**Line:** 15
**Type:** Modify

**Before:**
```typescript
workers: process.env.CI ? 1 : undefined,
```

**After:**
```typescript
workers: process.env.CI ? 1 : 4,
```

**Rationale:** Replace `undefined` (CPU-count-dependent default) with explicit `4` for deterministic local test execution. CI branch (`process.env.CI ? 1`) is untouched per R2.

## Files Touched

| File                              | Action | Lines Changed |
| --------------------------------- | ------ | ------------- |
| `frontend/playwright.config.ts`   | Modify | 1             |

## Risks

| Risk                                 | Likelihood | Impact | Mitigation                          |
| ------------------------------------ | ---------- | ------ | ----------------------------------- |
| API server can't handle 4 workers    | LOW        | HIGH   | Feature 1319 adds ThreadingHTTPServer |
| Tests flaky at 4 workers             | LOW        | MEDIUM | Revert to lower count if needed     |

## Dependencies

- Feature 1319 must be merged before this change is meaningful.
- Feature 1321 (CI workers) is independent and not blocked by this.

---

## Adversarial Review #2

### AR2: Plan-to-Spec Consistency

**Finding:** No drift detected. The plan specifies exactly one change that satisfies both R1 (workers=4 locally) and R2 (CI workers=1 preserved). The ternary expression structure is maintained -- only the falsy branch value changes from `undefined` to `4`.

**Cross-artifact check:**
- spec.md R1 (set workers=4 locally) -> C1 changes `undefined` to `4` in the non-CI branch. SATISFIED.
- spec.md R2 (preserve CI workers=1) -> C1 does not modify the `process.env.CI ? 1` branch. SATISFIED.
- No orphan requirements. No orphan changes.

### Gate: 0 inconsistencies. PASS.
