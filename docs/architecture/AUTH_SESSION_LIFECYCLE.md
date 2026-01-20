# Authentication Session Lifecycle

This document explains the complete authentication flow, session management, and multi-device behavior.

## First Visit - Anonymous Session

Users get an **anonymous session** automatically on first visit. No email required.

| Anonymous Session | Details |
|-------------------|---------|
| Role | `anonymous` |
| Email | `null` |
| Scopes | `["read:public"]` |
| Can use site? | Yes (limited features) |

## Email Verification Flow

After providing email, users can **continue using the site** as anonymous while waiting for the magic link.

```
Anonymous user → Enters email → Magic link sent → Still anonymous until clicked
                                                  (can continue using site)
```

- Magic link expiry: **1 hour**
- Magic link usage: **One-time only**

## Post-Verification Tokens

After clicking the magic link:

| Token | Expiry | Storage |
|-------|--------|---------|
| Access token | 15 minutes | In-memory only |
| Refresh token | 7 days | httpOnly cookie |

The refresh token auto-rotates on each `/auth/refresh` call, extending the session.

## Multi-Device Sessions

Each device creates a **separate session** linked to the **same account**.

```
Desktop login  → Session A (device 1)  ─┐
                                         ├── Same user_id, same account
Mobile login   → Session B (device 2)  ─┘
```

| Aspect | Same or Different? |
|--------|-------------------|
| `user_id` | Same |
| `email` | Same |
| `session_id` | Different |
| Refresh token | Different |
| Session expiry | Independent |

### Session Limit

**Maximum 5 concurrent sessions per user.**

If a 6th device attempts login:
- Oldest session is evicted (FIFO)
- Evicted device receives `AUTH_006` error

## Independent Session Expiry

Sessions expire **independently**. Using one device does NOT extend another.

```
Day 1: Desktop login  → Session A (expires Day 8)
Day 1: Mobile login   → Session B (expires Day 8)

Day 7: Mobile use     → Session B refreshed (now expires Day 14)
       Desktop idle   → Session A still expires Day 8

Day 8: Desktop        → Session A EXPIRED (must re-auth)
       Mobile         → Session B still valid (expires Day 14)
```

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  FIRST VISIT (any device)                                       │
│  └─→ Anonymous session created automatically                    │
│      └─→ Can use site with limited features                     │
│                                                                 │
│  ENTER EMAIL                                                    │
│  └─→ Magic link sent (1hr expiry, one-time use)                 │
│      └─→ Still anonymous, can keep using site                   │
│                                                                 │
│  CLICK MAGIC LINK                                               │
│  └─→ Role upgraded: anonymous → free                            │
│      └─→ Refresh token issued (7 days, httpOnly cookie)         │
│          └─→ Access token (15 min, in-memory)                   │
│                                                                 │
│  SECOND DEVICE (same email)                                     │
│  └─→ New session created (same user_id, different session_id)   │
│      └─→ Independent 7-day expiry                               │
│      └─→ Max 5 concurrent sessions (FIFO eviction if exceeded)  │
└─────────────────────────────────────────────────────────────────┘
```

## Authentication Methods

| Method | Description | Password Required? |
|--------|-------------|-------------------|
| Magic Link | Email with 256-bit random token | No |
| OAuth | Google/GitHub via Cognito | No |
| Anonymous | Auto-created session | No |

The system is **passwordless by design**.

## Role Progression

```
anonymous → free → paid → operator
```

| Role | Description | Session Limit |
|------|-------------|---------------|
| `anonymous` | Temporary session, no email | 5 |
| `free` | Verified email | 5 |
| `paid` | Paid subscription | 5 |
| `operator` | Admin privileges | 5 |

## Token Configuration

From `JWTConfig`:

```python
access_token_expiry_seconds = 900      # 15 minutes
refresh_token_expiry_seconds = 604800  # 7 days
clock_skew_seconds = 60                # Leeway for clock drift
```

## References

- Spec: `specs/1126-auth-httponly-migration/spec-v2.md`
- Session limits: `src/lambdas/dashboard/auth.py:128`
- JWT config: `src/lambdas/shared/middleware/auth_middleware.py`
