# Feature 1374 — Implementation Discovery

**Date**: 2026-04-29

While starting implementation, the following was discovered: **most of
1331's task list and 1323's task list are already shipped**. The spec
directories were uncommitted, but the underlying code changes had
landed in the repo.

## What Was Already Done

### 1323 — OAuth Buttons Local Dev

`scripts/run-local-api.py:90-99` already contains:

```python
# OAuth / Cognito config for local development (Feature 1323)
os.environ.setdefault("ENABLED_OAUTH_PROVIDERS", "google,github")
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_localdev")
os.environ.setdefault("COGNITO_CLIENT_ID", "local-client-id")
os.environ.setdefault("COGNITO_DOMAIN", "local-auth")
os.environ.setdefault("COGNITO_REDIRECT_URI", "http://localhost:3000/auth/callback")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
```

That's 1323's R1-R3 in full.

### 1331 — Auth OAuth Fixes

| 1331 Task | Status |
|---|---|
| B1: `auth.spec.ts:231` assertion fixed to `'Sign-in was cancelled. ...'` | Already correct in current file |
| B2: `auth.spec.ts:247` assertion fixed to `'Something went wrong with sign-in. ...'` | Already correct |
| A5: `mockOAuthUrls()` helper + applied to oauth-flow tests | Already implemented in `oauth-flow.spec.ts:17` and called at lines 48, 80, 111 |
| A2-A4: magic-link verify mocks | Need to verify by running tests; spec said "validate without mocks first" |
| B3, B4: assertion adjustments | Need to verify |

## Updated Task List for 1374

The remaining genuine work in 1374:

- [ ] **T1**: Run `cd frontend && npx playwright test magic-link.spec.ts oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts` and confirm pass count. If anything fails, address per 1331's task list.
- [ ] **T2**: Tick checkboxes in `specs/1331-auth-oauth-fixes/tasks.md` for what's done. Add a closeout note if any tasks remain.
- [ ] **T3**: Tick checkboxes in `specs/1323-oauth-buttons-local-dev/tasks.md`. Decision doc landed at `specs/1323-oauth-buttons-local-dev/decision.md`.
- [ ] **T4 (deferred)**: Capture observed `/urls` response from preprod after 1371 deploys. Add to `specs/1374-oauth-spec-reconciliation/observed-response.json` (with state redacted).

## Why Specs Drifted from Implementation

Likely cause: someone fixed the auth tests directly during a CI sweep
(perhaps Feature 1340-1345 chaos work in the git status), updated
`run-local-api.py` for local dev, but didn't merge back into the
1323/1331 spec dirs. Specs and code drifted.

## Implication for Future Specs

If `specs/<NUM>-<slug>/` exists with all tasks unchecked but the
implementation has shipped, the spec dir is stale. Worth adding to the
team's mental check: "does the spec tracker match git history?"
