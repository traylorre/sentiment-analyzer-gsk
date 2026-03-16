# Hardened Behavior Contracts (1222)

No new API endpoints are introduced. This document describes changed behavior on existing endpoints.

## POST /api/v2/auth/link-accounts

**New behavior**: Returns 403 if the authenticated user's JWT `sub` does not match the `current_user_id` derived from the request. Previously accepted any authenticated caller.

| Scenario | Before | After |
|----------|--------|-------|
| User A merges own anon account | 200 | 200 (unchanged) |
| User A targets User B's account | 200 (vulnerability) | 403 Forbidden |
| Unauthenticated caller | 401 | 401 (unchanged) |

## OAuth Callback (internal: handle_oauth_callback)

**New behavior**: Provider linking rejects duplicate `provider_sub` values. OAuth authorization URLs include PKCE `code_challenge`.

| Scenario | Before | After |
|----------|--------|-------|
| Link unlinked provider sub | Success | Success (unchanged) |
| Link already-linked provider sub (different user) | Success (vulnerability) | Error: provider identity already linked |
| Link already-linked provider sub (same user, re-link) | Success | Success (idempotent) |
| Authorization URL | No code_challenge | Includes code_challenge + code_challenge_method=S256 |
| Token exchange | No code_verifier | Includes code_verifier from state record |

## Email Verification Updates (internal)

**New behavior**: DynamoDB conditional writes guard the `verification` field.

| Scenario | Before | After |
|----------|--------|-------|
| Valid magic link verification | Sets verified | Sets verified (unchanged, with conditional guard) |
| Direct DB write to set verified | Succeeds (bypass) | Conditional write rejects |
| Re-verification of already-verified user | Succeeds (no-op) | Succeeds (idempotent, logged) |
