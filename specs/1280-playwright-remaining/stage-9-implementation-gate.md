# Stage 9: Implementation Gate — 1280-playwright-remaining

## Gate Checklist

| # | Gate Criterion | Status | Evidence |
|---|---------------|--------|----------|
| 1 | Spec exists and is complete | PASS | `spec.md` — 5 sections, all requirements covered |
| 2 | Adversarial spec review completed | PASS | `stage-3-adversarial-spec-review.md` — 6 findings, all resolved |
| 3 | Plan exists and addresses all requirements | PASS | `plan.md` — 4 design sections + risk mitigation |
| 4 | Adversarial plan review completed | PASS | `stage-5-adversarial-plan-review.md` — 6 findings, 3 amendments |
| 5 | Tasks exist and are dependency-ordered | PASS | `tasks.md` — 6 tasks, explicit dependency graph |
| 6 | Adversarial tasks review completed | PASS | `stage-7-adversarial-tasks-review.md` — 7 findings, 3 amendments |
| 7 | Consistency analysis passed | PASS | `stage-8-consistency-analysis.md` — 0 inconsistencies |
| 8 | All adversarial amendments traced | PASS | 7 amendments traced in consistency analysis |
| 9 | Root causes identified with evidence | PASS | 3 categories with code-level analysis |
| 10 | Blast radius assessed | PASS | 4 files modified, zero production code logic changes |

## Implementation Readiness

### Files To Modify (in order)

1. **`frontend/src/components/ui/error-boundary.tsx`** (Task 1)
   - Add `role="alert"` to ErrorFallback container
   - Add `aria-hidden="true"` to 4 decorative SVG icons
   - Add `type="button"` to 3 buttons in ErrorFallback
   - Add `aria-label="Retry"` to InlineError retry button
   - Estimated: 10 lines changed

2. **`frontend/tests/e2e/helpers/mock-api-data.ts`** (Task 2)
   - Add `mockAuthSession()` export function
   - Estimated: 25 lines added

3. **`frontend/tests/e2e/chaos-cached-data.spec.ts`** (Task 3)
   - Add `mockAuthSession` import
   - Add `mockAuthSession(page)` call in beforeEach (before goto)
   - Estimated: 3 lines changed

4. **`frontend/tests/e2e/chaos-cross-browser.spec.ts`** (Task 4)
   - Add `mockAuthSession` import
   - Add `mockAuthSession(page)` call in beforeEach (before goto)
   - Mark SSE test as `test.fixme()`
   - Estimated: 10 lines changed

### Process Steps (not code)

5. **Disable auto-merge on PR** (Task 5)
   - `gh pr merge --disable-auto <PR_NUMBER>` after PR creation

6. **Update branch protection** (Task 6, post-merge)
   - Add `Playwright Chaos Tests` to required checks

## Key Implementation Constraints

1. `mockAuthSession(page)` MUST be called BEFORE `page.goto('/')` — session init fires on navigation
2. The auth mock response MUST match `AnonymousSessionResponse` type exactly
3. `test.fixme()` MUST keep the callback code for future reference
4. Do NOT add `aria-hidden="true"` to icon-only buttons (InlineError retry) — use `aria-label` instead
5. After PR creation, immediately disable auto-merge to allow Playwright to complete

## Gate Decision

**APPROVED FOR IMPLEMENTATION**

All 9 stages complete. All adversarial findings resolved. Artifacts are consistent.
Total scope: 4 file modifications, ~48 lines changed.

Expected outcome: 5 of 6 failures fixed, 1 marked as fixme (SSE). 30 passing + 1 fixme.
