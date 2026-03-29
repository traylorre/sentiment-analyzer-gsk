# Stage 8: Consistency Analysis — 1280-playwright-remaining

## Cross-Artifact Consistency Check

### Spec -> Plan Alignment

| Spec Requirement | Plan Section | Status |
|------------------|-------------|--------|
| FR-001: Fix ErrorFallback a11y | Plan Section 1 | ALIGNED |
| FR-002: Fix cached data auth | Plan Sections 2-3 | ALIGNED (amended per Stage 3: route-only approach) |
| FR-003: Fix SSE test | Plan Section 3 | ALIGNED (amended: test.fixme) |
| FR-004: Branch protection | Plan Section 4 | ALIGNED (amended: post-merge step) |
| NFR-001: No regressions | Plan Risk Mitigation | ALIGNED |
| NFR-002: CI performance | Plan Section 2 (instant mock) | ALIGNED |

### Plan -> Tasks Alignment

| Plan Item | Task # | Status |
|-----------|--------|--------|
| ErrorFallback a11y | Task 1 (1.1-1.6) | ALIGNED |
| Auth mock helper | Task 2 (2.1-2.2) | ALIGNED |
| Cached data test fixes | Task 3 (3.1-3.2) | ALIGNED |
| Cross-browser test fixes | Task 4 (4.1-4.4) | ALIGNED |
| Disable auto-merge on PR | Task 5 | ALIGNED |
| Branch protection update | Task 6 | ALIGNED |

### Acceptance Criteria Coverage

| AC | Covered By | Status |
|----|-----------|--------|
| chaos-accessibility.spec.ts:68 passes | Task 1 (a11y fixes) | COVERED |
| chaos-accessibility.spec.ts:109 passes | Task 1 (type="button" fix) | COVERED |
| chaos-cached-data.spec.ts:39 passes | Task 2+3 (auth mock) | COVERED |
| chaos-cached-data.spec.ts:69 passes | Task 2+3 (auth mock) | COVERED |
| chaos-cross-browser.spec.ts:35 passes | Task 2+4 (auth mock) | COVERED |
| chaos-cross-browser.spec.ts:69 passes/fixme | Task 4.4 (test.fixme) | COVERED (fixme) |
| Playwright runs to completion | Task 5 (disable auto-merge) | COVERED |
| 9 passing tests continue to pass | NFR-001, no-regression check | COVERED |
| Branch protection updated | Task 6 (post-merge) | COVERED |

### Amendments Traceability

| Amendment | Source | Applied To |
|-----------|--------|-----------|
| Drop addInitScript for auth | Stage 3, Finding 1 | Plan Section 2 |
| SSE test -> test.fixme | Stage 3, Finding 4 | Plan Section 3, Task 4.4 |
| Branch protection post-merge | Stage 3, Finding 5 | Plan Section 4, Task 6 |
| Add InlineError a11y fix | Stage 5, Finding 3 | Task 1.6 |
| mockAuthSession in cross-browser beforeEach | Stage 5, Finding 2+4 | Task 4.2 |
| InlineError aria-label not aria-hidden | Stage 7, Finding 1 | Task 1.6 |
| Keep test.fixme callback | Stage 7, Finding 2 | Task 4.4 |

## Inconsistencies Found

### 1. Spec Says 5 Files, Plan Shows 5 Files — BUT Task Count Is 6

The spec scope says 5 files. The plan shows 5 files. But tasks include 6 tasks because
Task 5 (disable auto-merge) and Task 6 (branch protection) are process steps, not file changes.
Only Tasks 1-4 produce code changes across 4 files:

1. `frontend/src/components/ui/error-boundary.tsx`
2. `frontend/tests/e2e/helpers/mock-api-data.ts`
3. `frontend/tests/e2e/chaos-cached-data.spec.ts`
4. `frontend/tests/e2e/chaos-cross-browser.spec.ts`

The 5th file in scope (`scripts/setup-branch-protection.sh`) is only modified in the post-merge
step (Task 6). This is consistent — the scope includes it but it's deferred.

**Verdict**: Consistent. No action needed.

### 2. Spec AC Says "passes OR is skipped" for SSE Test

The spec acceptance criteria says: `chaos-cross-browser.spec.ts:69` passes OR is skipped with
documented reason. The task marks it as `test.fixme()` which is different from "skipped". In
Playwright, `test.fixme()` is reported as "fixme" (not "skip"). Both mean the test doesn't
execute, but they're semantically different:
- `test.skip()` = intentionally not run (e.g., wrong platform)
- `test.fixme()` = known broken, needs fixing later

`test.fixme()` is more appropriate because the test IS broken, not skipped for platform reasons.

**Verdict**: Consistent in intent, minor semantic difference. No action needed.

### 3. Task Dependencies Are Complete

```
Task 1 (standalone) ──┐
                       ├──> Task 5 (process) ──> Task 6 (post-merge)
Task 2 (standalone) ──┤
  └──> Task 3 ────────┤
  └──> Task 4 ────────┘
```

All dependencies are explicit and non-circular. Tasks 1 and 2 can be implemented in parallel.

**Verdict**: Consistent.

## Risk Assessment

### Residual Risks After All Amendments

1. **A11y violations may not be fully resolved**: LOW. The test logs violation details, so
   any remaining issues will be visible in CI output. Iterative fix is straightforward.

2. **Auth mock may not match production behavior exactly**: LOW. The mock response matches
   the TypeScript type definition exactly. The code path through `signInAnonymous` ->
   `authApi.createAnonymousSession` -> `mapAnonymousSession` is tested.

3. **Playwright flakiness after becoming required check**: MEDIUM. Mitigated by:
   - 2 retries in CI configuration
   - test.fixme for known-flaky SSE test
   - Post-merge timing for branch protection change (can revert if needed)

## Conclusion

All artifacts are consistent. The 7 amendments from adversarial reviews are traced and applied.
The implementation is ready to proceed. Total scope: 4 file modifications + 2 process steps.
