# Feature Specification: Auth Architecture Rewrite

**Feature Branch**: `1126-auth-rewrite`
**Created**: 2026-01-03
**Status**: Draft
**Priority**: P0 - Security + Architecture Foundation

## Problem Statement

Current auth implementation has fundamental flaws:
1. Tokens stored in localStorage (XSS vulnerable)
2. Refresh token sent in request body (should be httpOnly cookie)
3. No role system (only auth_type enum)
4. No decorator-based authorization
5. Admin endpoints unprotected

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AUTH FLOW                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LOGIN (any method: anonymous, magic link, OAuth)               │
│  ─────────────────────────────────────────────────────────────  │
│  Client                           Server                        │
│    │                                │                           │
│    │  POST /api/auth/login          │                           │
│    │  { credentials }  ───────────► │                           │
│    │                                │  Validate                 │
│    │                                │  Generate JWT:            │
│    │                                │    sub: user_id           │
│    │                                │    roles: ["authenticated"]│
│    │                                │    exp: +15min            │
│    │                                │  Generate refresh token   │
│    │                                │                           │
│    │  ◄─────────────────────────────│                           │
│    │  Body: { access_token, user }  │                           │
│    │  Set-Cookie: refresh_token=xyz;│                           │
│    │    HttpOnly; Secure; SameSite=Lax; Path=/api/auth          │
│    │                                │                           │
│    │  Store access_token IN MEMORY  │                           │
│    │  (not localStorage)            │                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  API REQUESTS                                                   │
│  ─────────────────────────────────────────────────────────────  │
│  Client                           Server                        │
│    │                                │                           │
│    │  GET /api/settings             │                           │
│    │  Authorization: Bearer {token} │                           │
│    │  ─────────────────────────────►│                           │
│    │                                │  @require_role("authenticated")
│    │                                │  1. Extract Bearer token  │
│    │                                │  2. Validate JWT sig+exp  │
│    │                                │  3. Check roles in claims │
│    │                                │  4. Pass or 401/403       │
│    │  ◄─────────────────────────────│                           │
│    │  200 OK or 401/403             │                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  TOKEN REFRESH                                                  │
│  ─────────────────────────────────────────────────────────────  │
│  Client                           Server                        │
│    │                                │                           │
│    │  POST /api/auth/refresh        │                           │
│    │  (no body needed)              │                           │
│    │  Cookie: refresh_token=xyz ────►  (browser sends auto)     │
│    │                                │  Validate refresh token   │
│    │                                │  Issue new access_token   │
│    │                                │  Rotate refresh token     │
│    │  ◄─────────────────────────────│                           │
│    │  Body: { access_token }        │                           │
│    │  Set-Cookie: refresh_token=new │                           │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│  PAGE LOAD (session restore)                                    │
│  ─────────────────────────────────────────────────────────────  │
│  Client                           Server                        │
│    │                                │                           │
│    │  POST /api/auth/refresh ───────►  (try to restore session) │
│    │  Cookie sent automatically     │                           │
│    │                                │                           │
│    │  ◄─────────────────────────────│                           │
│    │  200 + new token = logged in   │                           │
│    │  401 = not logged in           │                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Role System

### Role Definition

```python
# src/lambdas/shared/models/roles.py
from enum import Enum

class Role(str, Enum):
    """User roles. Users can have multiple roles."""
    ANONYMOUS = "anonymous"           # Temporary session, no email
    AUTHENTICATED = "authenticated"   # Logged in with email verified
    PAID = "paid"                     # Active subscription
    OPERATOR = "operator"             # On-call/admin access
```

### JWT Claims Structure

```json
{
  "sub": "user-123",
  "email": "user@example.com",
  "roles": ["authenticated", "paid"],
  "iat": 1704307200,
  "exp": 1704308100
}
```

### Role Decorator

```python
# src/lambdas/shared/middleware/require_role.py
from functools import wraps
from fastapi import HTTPException, Request

def require_role(*required_roles: str):
    """
    Decorator to enforce role-based access control.

    Usage:
        @require_role("authenticated")
        async def get_settings(request: Request): ...

        @require_role("operator")
        async def admin_endpoint(request: Request): ...

        @require_role("authenticated", "paid")
        async def premium_feature(request: Request): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Extract token from Authorization header
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Missing or invalid Authorization header"
                )

            token = auth_header[7:]

            # Validate JWT (signature, expiration)
            try:
                claims = validate_jwt(token)
            except JWTError as e:
                raise HTTPException(status_code=401, detail=str(e))

            # Check roles
            user_roles = set(claims.get("roles", []))
            required = set(required_roles)

            if not required.issubset(user_roles):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required: {required_roles}"
                )

            # Inject user context for downstream use
            request.state.user_id = claims["sub"]
            request.state.email = claims.get("email")
            request.state.roles = user_roles

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
```

## API Endpoints

### Auth Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/api/auth/anonymous` | POST | No | Create anonymous session |
| `/api/auth/magic-link` | POST | No | Request magic link email |
| `/api/auth/magic-link/verify` | GET | No | Verify magic link, issue tokens |
| `/api/auth/oauth/urls` | GET | No | Get OAuth provider URLs |
| `/api/auth/oauth/callback` | POST | No | Exchange OAuth code for tokens |
| `/api/auth/refresh` | POST | Refresh cookie | Get new access token |
| `/api/auth/logout` | POST | Refresh cookie | Clear session |
| `/api/auth/me` | GET | Bearer token | Get current user info |

### Token Response Format

All auth endpoints that issue tokens return:

```json
{
  "access_token": "eyJhbG...",
  "user": {
    "id": "user-123",
    "email": "user@example.com",
    "roles": ["authenticated"]
  }
}
```

Plus `Set-Cookie` header for refresh token.

### Refresh Token Cookie Attributes

```
Set-Cookie: refresh_token=<token>;
  HttpOnly;           # JavaScript cannot read
  Secure;             # HTTPS only
  SameSite=Lax;       # Sent on top-level navigations
  Path=/api/auth;     # Only sent to auth endpoints
  Max-Age=604800      # 7 days
```

**Why SameSite=Lax instead of Strict:**
- `Strict` breaks OAuth redirects (cookie not sent on redirect from OAuth provider)
- `Lax` is secure enough (not sent on cross-origin POST)
- Path restriction limits exposure

## Frontend Implementation

### Auth Store (No Persistence)

```typescript
// frontend/src/stores/auth-store.ts
import { create } from 'zustand';
// NO persist middleware - tokens live in memory only

interface User {
  id: string;
  email?: string;
  roles: string[];
}

interface AuthStore {
  // State
  accessToken: string | null;
  user: User | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;

  // Computed
  isAuthenticated: boolean;
  isAnonymous: boolean;
  hasRole: (role: string) => boolean;

  // Actions
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
  setLoading: (loading: boolean) => void;
  setInitialized: () => void;
  setError: (error: string | null) => void;
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  accessToken: null,
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  get isAuthenticated() {
    return get().accessToken !== null;
  },

  get isAnonymous() {
    return get().user?.roles.includes('anonymous') ?? false;
  },

  hasRole: (role: string) => {
    return get().user?.roles.includes(role) ?? false;
  },

  setAuth: (token, user) => set({
    accessToken: token,
    user,
    error: null
  }),

  clearAuth: () => set({
    accessToken: null,
    user: null
  }),

  setLoading: (loading) => set({ isLoading: loading }),
  setInitialized: () => set({ isInitialized: true }),
  setError: (error) => set({ error }),
}));
```

### API Client

```typescript
// frontend/src/lib/api/client.ts
import { useAuthStore } from '@/stores/auth-store';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

class ApiClient {
  private getAuthHeader(): HeadersInit {
    const token = useAuthStore.getState().accessToken;
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${path}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeader(),
        ...options.headers,
      },
      credentials: 'include', // Always send cookies
    });

    // If 401, try refresh once
    if (response.status === 401) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        // Retry with new token
        return this.request(path, options);
      }
      // Refresh failed - clear auth state
      useAuthStore.getState().clearAuth();
      throw new ApiError(401, 'Session expired');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.detail || 'Request failed');
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) return false;

      const { access_token, user } = await response.json();
      useAuthStore.getState().setAuth(access_token, user);
      return true;
    } catch {
      return false;
    }
  }

  // Convenience methods
  get<T>(path: string) {
    return this.request<T>(path, { method: 'GET' });
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  put<T>(path: string, body: unknown) {
    return this.request<T>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}
```

### Session Initialization

```typescript
// frontend/src/hooks/use-session-init.ts
import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';

export function useSessionInit() {
  const { isInitialized, setAuth, clearAuth, setLoading, setInitialized, setError } = useAuthStore();

  useEffect(() => {
    if (isInitialized) return;

    const init = async () => {
      setLoading(true);

      try {
        // Try to refresh - if we have valid refresh cookie, we get tokens
        const response = await fetch('/api/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        });

        if (response.ok) {
          const { access_token, user } = await response.json();
          setAuth(access_token, user);
        } else {
          // No valid session - that's fine, user is not logged in
          clearAuth();
        }
      } catch (error) {
        // Network error during init
        setError('Failed to initialize session');
        clearAuth();
      } finally {
        setLoading(false);
        setInitialized();
      }
    };

    init();
  }, [isInitialized, setAuth, clearAuth, setLoading, setInitialized, setError]);

  return {
    isLoading: useAuthStore((s) => s.isLoading),
    isInitialized: useAuthStore((s) => s.isInitialized),
    error: useAuthStore((s) => s.error),
  };
}
```

## Migration Path

### Phase 1: Backend (No Breaking Changes)

1. Add `Role` enum and JWT generation with roles
2. Add `@require_role` decorator
3. Add `/api/auth/refresh` endpoint that reads httpOnly cookie
4. Update existing auth endpoints to:
   - Return `access_token` in body
   - Set `refresh_token` as httpOnly cookie
   - Include `roles` in JWT claims
5. **Keep existing header auth working** during transition

### Phase 2: Frontend

1. Rewrite `auth-store.ts` (no persist)
2. Rewrite `client.ts` (header-based auth, auto-refresh)
3. Rewrite `use-session-init.ts` (cookie-based restore)
4. Update `protected-route.tsx` to use new store
5. Delete: `cookies.ts`, token-related code in `api/auth.ts`

### Phase 3: Cleanup

1. Remove localStorage migration code
2. Remove old token handling from backend
3. Add `@require_role` to all protected endpoints

## Files to Modify

### Backend

| File | Action | Description |
|------|--------|-------------|
| `src/lambdas/shared/models/roles.py` | Create | Role enum |
| `src/lambdas/shared/middleware/require_role.py` | Create | Role decorator |
| `src/lambdas/shared/middleware/jwt.py` | Create | JWT validation |
| `src/lambdas/dashboard/auth.py` | Modify | Add httpOnly cookie handling |
| `src/lambdas/dashboard/router_v2.py` | Modify | Add @require_role to endpoints |

### Frontend

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/stores/auth-store.ts` | Rewrite | No persist, roles support |
| `frontend/src/lib/api/client.ts` | Rewrite | Header auth, auto-refresh |
| `frontend/src/hooks/use-session-init.ts` | Rewrite | Cookie-based restore |
| `frontend/src/components/auth/protected-route.tsx` | Modify | Use new store |
| `frontend/src/components/providers/session-provider.tsx` | Modify | Simpler logic |
| `frontend/src/lib/cookies.ts` | Delete | No longer needed |
| `frontend/src/lib/api/auth.ts` | Simplify | Remove token handling |

## Success Criteria

1. No tokens in localStorage or sessionStorage
2. No tokens accessible via JavaScript
3. All API requests use `Authorization: Bearer` header
4. Token refresh works via httpOnly cookie
5. Session restored on page reload via cookie
6. All protected endpoints use `@require_role` decorator
7. 401 returned for missing/invalid token
8. 403 returned for insufficient roles

## Edge Cases and Clarifications

### Anonymous Users

Anonymous users follow the same pattern:
1. POST `/api/auth/anonymous` (no credentials needed)
2. Server creates anonymous user, issues tokens
3. Response: `{ access_token, user: { id, roles: ["anonymous"] } }`
4. Set-Cookie: refresh_token (httpOnly)

Anonymous users get refresh cookies. Session persists across page loads.

### Anonymous → Authenticated Upgrade

When anonymous user authenticates (magic link or OAuth):
1. Frontend sends `anonymous_user_id` with auth request (extracted from current user state)
2. Backend:
   - Creates/finds authenticated user
   - Merges anonymous user's data (configs, alerts) if `anonymous_user_id` provided
   - Invalidates old anonymous refresh token
   - Issues new refresh token with `roles: ["authenticated"]`
3. Frontend receives new access_token, replaces user state

### OAuth Callback Flow

```
1. User clicks "Sign in with Google"
2. Frontend redirects to Cognito authorize URL
3. User authenticates with Google
4. Cognito redirects to /auth/verify?code=xyz
5. Frontend POSTs code to /api/auth/oauth/callback
6. Backend:
   - Exchanges code for Cognito tokens
   - Extracts email from ID token
   - Creates/finds user, assigns roles
   - Returns access_token in body
   - Sets refresh_token as httpOnly cookie
7. Frontend stores access_token in memory
```

### Token Expiry During Form Submission

The API client retry logic preserves the request:

```typescript
// client.ts - already handles this
if (response.status === 401) {
  const refreshed = await this.tryRefresh();
  if (refreshed) {
    return this.request(path, options); // options includes body
  }
}
```

The original `options` (including `body`) is reused on retry.

### Multi-Tab Behavior

- Logout in one tab does NOT immediately affect other tabs
- Other tabs continue with their in-memory access token until it expires (15 min max)
- On next API call after expiry, refresh fails (cookie cleared), user sees login prompt
- This is acceptable. Cross-tab sync via BroadcastChannel is out of scope.

### CSRF Protection

Not required for this architecture because:
1. Access token is in memory, not cookie - attacker cannot include it
2. Refresh cookie has `SameSite=Lax` - not sent on cross-origin POST
3. Bearer token authentication is inherently CSRF-resistant

If paranoid, add `Origin` header validation on backend (defense in depth).

### Session Init Error Handling

When `/api/auth/refresh` fails:

| Status | Meaning | Action |
|--------|---------|--------|
| 401 | No valid session | `clearAuth()`, user is logged out (expected for new users) |
| 500 | Server error | `setError("Server error")`, show retry button |
| Network error | Offline/unreachable | `setError("Network error")`, show offline banner |

SessionProvider MUST show error UI, not silently render broken app.

### Refresh Rate Limiting

If refresh endpoint returns 429:
1. Parse `Retry-After` header
2. Show "Please wait X seconds" message
3. Auto-retry after delay
4. If still failing, show "Session expired, please log in again"

## Out of Scope

- Subscription/payment integration (Paid role assignment)
- Operator role assignment UI
- Multi-device session management
- Token revocation list
- Cross-tab session sync (BroadcastChannel)
