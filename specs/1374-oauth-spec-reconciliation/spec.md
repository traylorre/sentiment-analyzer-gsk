# Feature 1374: OAuth Spec Reconciliation (1323 + 1331)

**Status**: Draft
**Created**: 2026-04-29
**Source**: `specs/oauth-provisioning-plan.md` (W12)
**Depends On**: 1371 (need real `/urls` response shape from preprod)
**Blocks**: none

## Summary

After 1371's preprod rollout produces a real `/api/v2/auth/oauth/urls`
response, reconcile two pre-existing OAuth specs against the new reality:

- **`specs/1323-oauth-buttons-local-dev/`**: Originally addressed local-dev
  OAuth button rendering by setting mock Cognito env vars. After 1371,
  decide whether to (a) ship 1323 as-is for offline dev, or (b) point
  local dev at a real "sentiment-local" Google client.
- **`specs/1331-auth-oauth-fixes/`**: 9 Playwright E2E test failures.
  Several depend on the exact shape of the `/urls` response. After 1371,
  the mock route handlers in those tests can be tightened to match
  reality.

This feature is **bookkeeping**: close out specs that are no longer
accurate, update mocks to match reality, and ensure CI tests reflect the
deployed state.

## Problem

Spec 1323 was authored before 1370/1371 existed. Its plan (mock Cognito
env vars in `scripts/run-local-api.py`) is still useful for offline dev,
but its rationale — "OAuth buttons don't render locally because env vars
aren't set" — is partially overlapping with what 1370 just landed.

Spec 1331 was authored to fix Playwright tests. Several tests assume the
shape of `OAuthUrlsResponse` matches a guess. After 1371, the real shape
is known and the mocks can be hardcoded to it.

## User Stories

### US1: Decide 1323's fate (P2)

As a maintainer, I want a clear decision on whether 1323 ships as-is, gets
revised, or gets archived, so the local dev experience is unambiguous.

**Acceptance**: A short decision document in
`specs/1323-oauth-buttons-local-dev/decision.md` (new) captures the choice
with rationale. Either:
- **Ship 1323 as-is**: offline dev keeps mocked Cognito values; clicking
  the button hits a non-existent URL. Lightweight.
- **Revise 1323**: replace mocks with a real "sentiment-local" Google
  client (separate Google project, callback URL `http://localhost:3000`).
  Click-through actually works locally.
- **Archive 1323**: delete the spec; document that local dev OAuth buttons
  are intentionally hidden (graceful degradation only).

### US2: Update 1331's mocks to match reality (P2)

As a CI engineer, I want the Playwright route mocks in
`frontend/tests/e2e/oauth-flow.spec.ts` to return a response shape that
exactly matches what the deployed Lambda returns, so the tests catch
contract drift if the shape changes.

**Acceptance**: After 1371 produces a real `/urls` response, the
`mockOAuthUrls()` helper in `frontend/tests/e2e/helpers/auth-helper.ts`
(introduced in 1331's T5) is updated to mirror the real shape. The 9
tests in 1331 pass.

### US3: Run 1331's task list to completion (P2)

As a CI maintainer, I want the 9 Playwright tests in 1331 to pass, so the
test suite is green.

**Acceptance**: All 9 test fixes from 1331's tasks.md complete. CI run
shows zero auth-related test failures.

## Requirements

### R1: Capture real `/urls` response shape from preprod

After 1371's apply, run:
```
curl -s https://<preprod-api-gw>/api/v2/auth/oauth/urls | jq .
```
Save output to `specs/1374-oauth-spec-reconciliation/observed-response.json`
(a captured artifact, not a contract). Strip the `state` value (don't commit
real CSRF tokens to git).

### R2: Update or archive 1323

Make the call documented in US1. Write the decision document with rationale.
If "Revise" is chosen, fork into a new feature (1376 or similar). If "Ship
as-is" is chosen, complete 1323's tasks.md and merge. If "Archive" is
chosen, move the spec dir to `specs/_archived/1323-oauth-buttons-local-dev/`
and update README pointers.

### R3: Update 1331's helpers to match reality

Edit `frontend/tests/e2e/helpers/auth-helper.ts` (the file 1331 introduces)
to use the captured real shape. Run 1331's task list to completion.

### R4: Don't introduce new spec drift

After 1374, all references to OAuth in `specs/` should either:
- Point at 1370/1371/1372/1373 for the new provisioning + frontend
  hardening flow, OR
- Point at 1374 for reconciliation history.

No orphaned specs.

## Success Metrics

1. `specs/1323-oauth-buttons-local-dev/` either has a complete tasks.md
   (all checked) or is archived.
2. `specs/1331-auth-oauth-fixes/` has all 9 tests passing in CI.
3. `frontend/tests/e2e/helpers/auth-helper.ts` `mockOAuthUrls()` matches
   the captured real response.
4. `specs/1374-oauth-spec-reconciliation/observed-response.json` exists
   (with state redacted).

## Out of Scope

- Real backend / frontend / Terraform changes (covered by 1370-1373).
- Adding new tests (out of scope for reconciliation).
- Local-dev real OAuth (would be a separate spawned feature if US1
  decision is "Revise").

## Adversarial Review #1

**Reviewer**: Self (adversarial — bookkeeping vs real risk)
**Date**: 2026-04-29

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | The captured `observed-response.json` could leak `state` (CSRF token) or `authorize_url` parameters that contain hints about the deployed Cognito domain (which is generally OK) but also `client_id` (which is a public identifier — also OK by spec, but might surprise reviewers). | Strip `state` from the captured file. `client_id` is intentionally public per OAuth spec. Document this in the file's header comment. |
| MEDIUM | If 1331's tests rely on `state` being a specific format, the captured file's redacted state will break them. | The `mockOAuthUrls()` helper generates a fresh state per test invocation. Captured file is illustrative, not the source for the helper's state value. |
| MEDIUM | "Archive" outcome for 1323 risks losing useful local-dev context. Future engineers might rebuild 1323 from scratch. | Don't `rm -rf`. Move to `specs/_archived/` with a `WHY-ARCHIVED.md` note. |
| LOW | This feature has no production risk (bookkeeping only). | Acceptable. |

### Spec edits made in response

- R1 explicitly says "strip state" before committing observed-response.json.
- R2 specifies move to `specs/_archived/` (not delete) for the Archive case.

### Gate

**0 CRITICAL, 0 HIGH unresolved.**
