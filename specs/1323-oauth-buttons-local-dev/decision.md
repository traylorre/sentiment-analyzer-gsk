# Decision: 1323 OAuth Buttons Local Dev — Status

**Date**: 2026-04-29
**Decided by**: Feature 1374 (OAuth Spec Reconciliation)
**Outcome**: **SHIP AS-IS — already implemented**

## Decision

Ship 1323 as authored: mock Cognito env vars in `scripts/run-local-api.py`
to enable OAuth button rendering in local dev. The buttons link to a
non-existent `local-auth.auth.us-east-1.amazoncognito.com` domain;
clicking them won't complete a real OAuth flow, but the UI renders
correctly for visual development and E2E test snapshots.

## Why this option (vs alternatives)

| Option | Why not |
|---|---|
| **Revise** to use a real `sentiment-local` Google client | Operationally heavy: separate Google project, callback URL `http://localhost:3000`, per-developer OAuth setup. Disproportionate to the value. |
| **Archive** the spec | Loses useful local-dev context. New engineers would rediscover the same gap. |
| **Ship as-is** ✓ | Lightest-touch. Mocks the env vars. Buttons render. Click-through fails gracefully (dead Cognito URL). Solves the visual-development problem cleanly. |

## Implementation Status

**Already shipped.** During the audit for Feature 1374, the implementation
was discovered to already be in place:

- `scripts/run-local-api.py:90-99` contains the env var setdefaults
  (`ENABLED_OAUTH_PROVIDERS`, `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`,
  `COGNITO_DOMAIN`, `COGNITO_REDIRECT_URI`, `FRONTEND_URL`) with mock
  values, exactly matching this spec's R1, R2, R3.

The spec dir was uncommitted but the runtime change had landed. 1374
formalizes the closeout.

## Verification

To confirm:

```bash
grep -A 10 "Feature 1323" scripts/run-local-api.py
# Expect to see 6 os.environ.setdefault() calls with mock OAuth/Cognito values.
```

And manually:

```bash
python scripts/run-local-api.py &
cd frontend && npm run dev &
# Open http://localhost:3000/auth/signin
# Verify "Continue with Google" and "Continue with GitHub" buttons render.
```

## Tasks

All tasks in `tasks.md` are **complete** in code, even though the
checkboxes were never ticked. No additional implementation work needed.
This decision doc serves as the closeout marker.

## Related

- Feature 1370: real OAuth secrets infra (production path).
- Feature 1371: preprod OAuth rollout (real Cognito).
- Feature 1374: this spec's reconciliation.
