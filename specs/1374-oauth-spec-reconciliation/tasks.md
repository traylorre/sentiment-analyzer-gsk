# Tasks: Feature 1374 — OAuth Spec Reconciliation

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)
**Depends On**: 1371 preprod browser test green (for shape capture)

## Phase 1: Pure Assertion Fixes (no dep on 1371)

- [ ] **T1**: Run 1331's T1: fix `auth.spec.ts` line 247 assertion to
  `/Sign-in was cancelled/`. Mark 1331 T1 complete.
  - **Maps to**: 1331 spec B1
  - **Deps**: none

- [ ] **T2**: Run 1331's T2: fix `auth.spec.ts` line 263 assertion to
  `/Something went wrong with sign-in/`. Mark 1331 T2 complete.
  - **Maps to**: 1331 spec B2
  - **Deps**: none

- [ ] **T3**: Run 1331's T3: validate magic-link tests 2-4 pass without
  mocks. If pass: mark 1331 T4 SKIP. If fail: run T4.
  - **Maps to**: 1331 spec A2-A4
  - **Deps**: none

## Phase 2: Capture Real Response (depends on 1371)

- [ ] **T4**: After 1371's preprod apply, run:
  ```
  curl -s https://<preprod-api-gw>/api/v2/auth/oauth/urls | jq .
  ```
  Save to `specs/1374-oauth-spec-reconciliation/observed-response.json`.
  Edit the file: replace `state` value with `"<redacted>"`. Commit.
  - **File**: `specs/1374-oauth-spec-reconciliation/observed-response.json` (new)
  - **Maps to**: spec R1, plan AD1
  - **Deps**: 1371 preprod apply complete

## Phase 3: Test Helper Update (depends on T4)

- [ ] **T5**: Update / create `frontend/tests/e2e/helpers/auth-helper.ts`
  `mockOAuthUrls()` helper. Use the shape from `observed-response.json`.
  Generate a fresh state per call (`crypto.randomUUID()` or similar).
  - **File**: `frontend/tests/e2e/helpers/auth-helper.ts`
  - **Maps to**: 1331 spec T5, this spec R3
  - **Deps**: T4

- [ ] **T6**: Run 1331's T6, T7: add `mockOAuthUrls(page)` calls to
  oauth-flow.spec.ts. Run tests; verify pass.
  - **Maps to**: 1331 spec A5, A5b
  - **Deps**: T5

## Phase 4: 1323 Decision

- [ ] **T7**: Write `specs/1323-oauth-buttons-local-dev/decision.md`. Default
  decision per plan AD2: Ship as-is. Document rationale.
  - **File**: `specs/1323-oauth-buttons-local-dev/decision.md` (new)
  - **Maps to**: spec R2, plan AD2
  - **Deps**: none

- [ ] **T8**: Run 1323's tasks T1-T6 (env var setdefaults in
  `scripts/run-local-api.py`).
  - **Maps to**: 1323's tasks
  - **Deps**: T7

## Phase 5: Validation

- [ ] **T9**: Run full Playwright suite:
  ```
  cd frontend && npx playwright test magic-link.spec.ts oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts
  ```
  All 9 originally-failing tests must pass.
  - **Deps**: T1, T2, T3, T6

- [ ] **T10**: Verify no specs reference 1323 or 1331 except 1374:
  ```
  grep -rn "1323\|1331" specs/ | grep -v 'specs/1323\|specs/1331\|specs/1374'
  ```
  Expect zero matches (or only matches in `specs/oauth-provisioning-plan.md`,
  which is the source of truth).
  - **Deps**: T7, T8

## Phase 6: PR

- [ ] **T11**: Open PR titled `chore(1374): reconcile OAuth specs 1323 +
  1331 with provisioning reality`.
  - GPG-signed commits.
  - **Deps**: T9, T10

## Adversarial Review #3

**Reviewer**: Self
**Date**: 2026-04-29

### Coverage check

| Requirement | Mapped Tasks |
|---|---|
| R1 (capture response) | T4 |
| R2 (1323 decision) | T7, T8 |
| R3 (1331 mock update) | T5, T6 |
| R4 (no orphans) | T10 |

All requirements have ≥1 mapped task. ✓

### Highest-risk task

**T6** — adding mocks and verifying tests pass. If the captured response
shape differs from what `signin/page.tsx`'s code expects (because the
backend `OAuthURLsResponse` Pydantic model has fields we didn't
anticipate), the helper might not satisfy the component. Mitigation:
T5 reads BOTH the captured JSON and `auth.py:1440` (the Pydantic model)
to generate a complete mock.

### Most likely source of rework

T8 — running 1323's existing tasks. Those tasks were authored assuming
no real Cognito; if 1370's changes affected `scripts/run-local-api.py`'s
environment (they shouldn't, but might), the tasks need adjustment.

### Failure modes (3am production check)

This is bookkeeping. No prod risk. Worst case: a Playwright test fails,
CI is yellow, fix in a follow-up.

### Gate

**READY FOR IMPLEMENTATION (when 1371 is green for T4 onwards; T1-T3 + T7
can land any time).**
0 CRITICAL, 0 HIGH unresolved.
