# Contract: `POST /api/v2/auth/anonymous` — No-Clobber Guard

**Feature**: 1384-oauth-session-persistence-harden | **Requirement**: FR-005, FR-006, SR-002, SR-003, SR-004
**Handler**: `src/lambdas/dashboard/router_v2.py:382` (`create_anonymous_session`)

## Purpose

Defense-in-depth backstop: the anonymous-session endpoint MUST NOT overwrite a live OAuth
(`refresh_token` = Cognito JWE) session when a stray or multi-tab client mint slips through the
frontend single-flight guards. The endpoint reads the incoming cookie it already receives on this
path (`_extract_refresh_token_from_event`, `router_v2.py:197`) and decides whether to clobber.

## Decision table (server-side, on the incoming `refresh_token` cookie)

| Incoming `refresh_token` cookie | Server action | `Set-Cookie: refresh_token=` | Diagnostic |
|---|---|---|---|
| Absent | Mint anonymous | `anon.{user_id}.{secret}` | (normal) |
| `anon.*` (self-describing guest, `auth.py:177`/`:2978`) | Mint anonymous (re-mint allowed) | `anon.{...}` | (normal) |
| Valid non-`anon.*` (Cognito token) | **Refuse to clobber** — do NOT emit an `anon.*` cookie | *(none — OAuth cookie left intact)* | `anonymous.clobber_blocked` |
| Malformed / unrecognized | Mint anonymous (fail-open to guest, never starve) | `anon.{...}` | (normal) |

## Rules

- **R1 (FR-005)**: A valid Cognito `refresh_token` in the request → the response MUST NOT set an
  `anon.*` refresh cookie. The OAuth session survives.
- **R2 (SR-002)**: "Valid Cognito token" is determined **server-side** by local shape
  discrimination (not `anon.*`) plus lightweight structural validation consistent with the refresh
  path — **NO Cognito network round-trip** on the guest path. Never trust a client-supplied claim.
- **R3 (FR-006/SR-003)**: Absent, `anon.*`, or unrecognized cookie MUST always be allowed to mint.
  The guard is "don't overwrite a valid OAuth session," never "require a cookie to mint." A real
  first-time visitor is never starved.
- **R4 (SR-004)**: `require_csrf_middleware` on `/api/v2/auth/anonymous` is unchanged; the guard adds
  no CSRF-exempt surface.
- **R5 (FR-009/SR-006)**: The `anonymous.clobber_blocked` log carries only a hash-prefix / masked
  context — never the raw token (CWE-117/CWE-312).

## Response body

Unchanged from today on the mint paths. On the refuse-to-clobber path, the endpoint returns without
rotating the refresh cookie; body content is out of scope for this contract (the point is the
*absence* of an `anon.*` `Set-Cookie`). No refresh/anon token material appears in any response body.
