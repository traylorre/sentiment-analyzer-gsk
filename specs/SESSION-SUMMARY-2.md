# Session Summary: Auth Architecture Rewrite

**Created**: 2026-01-03
**Purpose**: Persist context across /clear

---

## TL;DR

Principal engineer audit found garbage auth architecture. Rewrote spec 1126 with correct industry-standard pattern: Bearer tokens in header, refresh tokens in httpOnly cookies, role-based decorators. Updated spec 1123 to remove zustand persist dependency.

---

## What Was Wrong (Audit Findings)

### Auth Architecture Failures

1. **Tokens in localStorage** - XSS vulnerable
2. **Refresh token sent in request body** - Should be httpOnly cookie
3. **No role system** - Only `auth_type` enum (anonymous/authenticated)
4. **Admin endpoints unprotected** - `/api/v2/admin/sessions/revoke` has NO auth check
5. **"Paid" and "Operator" roles don't exist** - Spec only, zero code
6. **zustand persist for tokens** - Causes hydration race conditions

### Hydration Failures

1. **Silent failure on session init error** - SessionProvider renders broken app
2. **No global ErrorBoundary** - App crashes = white screen
3. **Blocking render during init** - Network failure = infinite loading

---

## The Correct Architecture (Now in Spec 1126)

```
LOGIN:
  Client                           Server
    │  POST /api/auth/login          │
    │  { credentials }  ───────────► │
    │                                │  Generate JWT with roles
    │  ◄─────────────────────────────│
    │  Body: { access_token, user }  │
    │  Set-Cookie: refresh_token     │
    │    HttpOnly; Secure; SameSite=Lax
    │                                │
    │  Store access_token IN MEMORY  │
    │  (NOT localStorage)            │

API REQUESTS:
    │  GET /api/settings             │
    │  Authorization: Bearer {token} │
    │  ─────────────────────────────►│
    │                                │  @require_role("authenticated")
    │  ◄─────────────────────────────│
    │  200 OK or 401/403             │

TOKEN REFRESH:
    │  POST /api/auth/refresh        │
    │  (no body - cookie sent auto)  │
    │  ─────────────────────────────►│
    │                                │  Validate cookie, issue new token
    │  ◄─────────────────────────────│
    │  Body: { access_token }        │
    │  Set-Cookie: new refresh_token │

PAGE LOAD:
    │  POST /api/auth/refresh ───────►  Try restore session
    │  200 = logged in, 401 = not    │
```

---

## Role System

```python
class Role(str, Enum):
    ANONYMOUS = "anonymous"           # Temp session
    AUTHENTICATED = "authenticated"   # Logged in
    PAID = "paid"                     # Has subscription
    OPERATOR = "operator"             # Admin access

# JWT claims
{ "sub": "user-123", "roles": ["authenticated", "paid"], "exp": ... }

# Decorator usage
@require_role("authenticated")
async def get_settings(): ...

@require_role("operator")
async def admin_endpoint(): ...
```

---

## Specs Status

| Spec | Status | Notes |
|------|--------|-------|
| **1126** | REWRITTEN | Correct auth architecture, edge cases addressed |
| **1123** | UPDATED | Removed zustand persist dependency |
| 1124 | Unchanged | SSE store is independent |
| 1125 | Unchanged | Refresh coordinator is independent |

---

## Files for Surgical Rewrite

### Backend (Create)
```
src/lambdas/shared/models/roles.py              # Role enum
src/lambdas/shared/middleware/require_role.py   # @require_role decorator
src/lambdas/shared/middleware/jwt.py            # JWT validation
```

### Backend (Modify)
```
src/lambdas/dashboard/auth.py                   # httpOnly cookie handling
src/lambdas/dashboard/router_v2.py              # Add @require_role to endpoints
```

### Frontend (Rewrite)
```
frontend/src/stores/auth-store.ts               # No persist, roles support
frontend/src/lib/api/client.ts                  # Header auth, auto-refresh
frontend/src/hooks/use-session-init.ts          # Cookie-based restore
```

### Frontend (Modify)
```
frontend/src/components/auth/protected-route.tsx
frontend/src/components/providers/session-provider.tsx
```

### Frontend (Delete)
```
frontend/src/lib/cookies.ts                     # No longer needed
```

---

## Implementation Order

```
1126 Backend Phase 1 (add new, keep old working)
    ↓
1126 Frontend Phase 2 (rewrite auth layer)
    ↓
1126 Backend Phase 3 (cleanup)
    ↓
1123 (skeleton fixes)
    ↓
1124 + 1125 (parallel)
```

---

## Key Decisions Made

1. **Access token in memory only** - Not localStorage, not cookies
2. **Refresh token as httpOnly cookie** - Browser sends automatically
3. **SameSite=Lax** (not Strict) - Strict breaks OAuth redirects
4. **Role decorator pattern** - `@require_role("authenticated")` on endpoints
5. **No zustand persist for auth** - Session restored via cookie on page load
6. **No CSRF tokens needed** - Bearer auth + SameSite=Lax is sufficient

---

## Edge Cases Addressed in Spec

- Anonymous users get refresh cookies too
- Anonymous → Authenticated upgrade merges data
- OAuth callback sets httpOnly cookie
- Token expiry mid-form: retry preserves request body
- Multi-tab logout: acceptable 15min stale window
- Session init errors: MUST show UI, not silent fail
- Rate limiting on refresh: show message, auto-retry

---

## Repos

- **Template**: `/home/traylorre/projects/terraform-gsk-template`
- **Target**: `/home/traylorre/projects/sentiment-analyzer-gsk`

---

## Commands After /clear

```bash
# Read this summary
cat /home/traylorre/projects/sentiment-analyzer-gsk/specs/SESSION-SUMMARY-2.md

# Read the rewritten spec
cat /home/traylorre/projects/sentiment-analyzer-gsk/specs/1126-auth-httponly-migration/spec.md

# Check current branch
cd /home/traylorre/projects/sentiment-analyzer-gsk && git branch
```

---

## Next Steps

1. Review rewritten spec 1126 if needed
2. Start implementation: Backend Phase 1 first
3. Use sub-agents for any git commits (pre-commit hooks run tests)
