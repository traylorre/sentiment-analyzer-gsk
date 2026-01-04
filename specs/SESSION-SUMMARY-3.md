# Session Summary: Auth Architecture Audit & Corrected Spec

**Created**: 2026-01-03
**Purpose**: Persist context across /clear

---

## TL;DR

Deep audit of SESSION-SUMMARY-2.md revealed **false claims**. The spec described an architecture that doesn't exist. Created `spec-v2.md` that:
1. Documents what backend already does right
2. Fixes critical security gaps
3. Removes vestigial claims
4. Is explicit about what to delete/change

---

## Audit Findings

### SESSION-SUMMARY-2.md Lies

| Claim | Reality |
|-------|---------|
| "Access token in memory only" | **FALSE** - In localStorage via zustand persist |
| "Refresh token as httpOnly cookie" | **PARTIAL** - Backend sets it, frontend also sets non-httpOnly copy |
| "No zustand persist for auth" | **FALSE** - `persist` middleware still active |
| "SameSite=Lax" | **MISMATCH** - Backend uses `Strict` |

### Critical Security Issues Found

1. **Hardcoded Secret** (auth.py:1101-1103)
   ```python
   MAGIC_LINK_SECRET = os.environ.get(
       "MAGIC_LINK_SECRET", "default-dev-secret-change-in-prod"
   )
   ```
   If env var not set, attacker can forge magic links.

2. **Mock Tokens in Production Path** (auth.py:1510-1529)
   Mock token generation used in OAuth/magic link flows. Not guarded.

3. **Triple XSS Exposure**
   - localStorage (zustand persist)
   - Non-httpOnly cookies (cookies.ts)
   - Module-level JS variables (client.ts)

4. **No JWT Secret Management**
   Spec never said where signing keys come from.

5. **No CORS Configuration**
   Spec assumed same-origin. Reality may differ.

6. **Concurrent Refresh Race Condition**
   Two 401s trigger simultaneous refreshes.

### What Backend Already Does Right

Spec v1 didn't document these existing features:
- Magic Link: HMAC-SHA256 signed, 1-hour expiry, atomic one-time use
- OAuth: Google + GitHub via Cognito
- Session Revocation: Admin andon cord with audit trails
- Account Merging: Tombstone pattern, idempotent
- Email Uniqueness: GSI with race protection
- Sanitized Logging: CRLF injection prevention

---

## Corrected Spec Location

```
specs/1126-auth-httponly-migration/spec-v2.md
```

### Key Additions in v2

1. **JWT Secret Management** - Secrets Manager, no fallbacks
2. **CORS Configuration** - Same vs cross-origin options
3. **Role Hierarchy** - Clarified AND vs OR semantics
4. **Concurrent Refresh** - Request deduplication
5. **Magic Link** - Documented existing implementation
6. **Files to DELETE** - Explicit list
7. **Browser Scenarios** - Incognito behavior documented

---

## Implementation Order

```
Phase 1: Backend (Non-Breaking)
├── Create secrets.py (fail if not configured)
├── Fix hardcoded secret in auth.py
├── Guard mock token generation
├── Add @require_role decorator
└── Keep existing auth working

Phase 2: Frontend (Breaking)
├── DELETE cookies.ts
├── REWRITE auth-store.ts (no persist)
├── REWRITE client.ts (dedup + retry)
├── REWRITE use-session-init.ts (cookie restore)
└── UPDATE protected-route.tsx

Phase 3: Backend Cleanup
├── Remove X-User-ID header support
├── Remove mock token generation
├── Add @require_role to all endpoints
└── Add rate limiting to /refresh
```

---

## Files Summary

### DELETE

| File | Reason |
|------|--------|
| `frontend/src/lib/cookies.ts` | Sets non-httpOnly cookies |

### CREATE (Backend)

| File | Purpose |
|------|---------|
| `src/lambdas/shared/config/secrets.py` | Secret management |
| `src/lambdas/shared/config/jwt_config.py` | JWT configuration |
| `src/lambdas/shared/middleware/require_role.py` | Role decorator |
| `src/lambdas/shared/middleware/jwt.py` | JWT validation |

### REWRITE (Frontend)

| File | Change |
|------|--------|
| `auth-store.ts` | Remove persist, memory-only |
| `client.ts` | Add dedup + 401 retry |
| `use-session-init.ts` | Cookie-based restore |

### MODIFY

| File | Change |
|------|--------|
| `auth.py` | Use secrets module, guard mocks |
| `router_v2.py` | Add @require_role decorators |

---

## Success Criteria

1. No tokens in localStorage
2. No tokens in JS-accessible cookies
3. Refresh token ONLY in httpOnly cookie
4. Access token ONLY in memory
5. No hardcoded secrets
6. Concurrent refresh deduplicated
7. All endpoints use @require_role

---

## Repos

- **Template**: `/home/traylorre/projects/terraform-gsk-template`
- **Target**: `/home/traylorre/projects/sentiment-analyzer-gsk`

---

## Commands After /clear

```bash
# Read this summary
cat /home/traylorre/projects/sentiment-analyzer-gsk/specs/SESSION-SUMMARY-3.md

# Read the corrected spec
cat /home/traylorre/projects/sentiment-analyzer-gsk/specs/1126-auth-httponly-migration/spec-v2.md

# Check current branch
cd /home/traylorre/projects/sentiment-analyzer-gsk && git branch
```

---

## Next Steps

1. Review spec-v2.md
2. Run `/speckit.plan` for 1126 using spec-v2.md
3. Generate tasks from plan
4. Implement Phase 1 (backend, non-breaking)
