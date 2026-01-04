# Session Summary: Dashboard UI Fix Investigation

**Created**: 2026-01-03
**Branch**: `1123-skeleton-architecture` (checked out)
**Purpose**: Persist context across /clear

---

## TL;DR

Started investigating "blinking halo" UI bug. Discovered **critical security vulnerability**: JWT tokens stored in localStorage (XSS vulnerable). Created 4 specs. Security fix (1126) must be done FIRST.

---

## The Original Problem

User reported:
- "Portrait halo" blinking on bottom left with no content
- Sign-in button, refresh button, connection status missing
- Elements hidden behind hydration gates showing only animated circles

## What We Discovered

### 1. UI Issues (Symptom)
- `UserMenu` skeleton shows pulsing circle instead of button shape
- `RefreshTimer` exists but `onRefresh` callback never wired
- `ConnectionStatus` hard-coded to `'connected'` (not real SSE state)
- `PullToRefresh` component exists but not integrated

### 2. Architecture Issues (Root Cause)
- SSE connection status stored in local hook state, never exposed globally
- No refresh coordinator to invalidate React Query caches
- Multiple independent hydration flows with race conditions

### 3. **CRITICAL SECURITY VULNERABILITY** (The Real Problem)
```
localStorage["auth-storage"] = {
  tokens: {
    accessToken: "eyJhbG...",   ← ANY XSS SCRIPT CAN STEAL THIS
    idToken: "eyJhbG...",
    refreshToken: "eyJhbG...",
  }
}
```

Current implementation stores JWT tokens in localStorage via zustand persist. This is **fundamentally insecure** - any XSS attack can steal tokens.

Additionally, the "localStorage fallback" to in-memory storage causes **silent logout** in private browsing mode.

---

## Specs Created

| Spec | Priority | Focus |
|------|----------|-------|
| **1126-auth-httponly-migration** | **P0 SECURITY** | Move tokens to httpOnly cookies, add CSRF protection |
| 1124-sse-connection-store | P1 | Expose SSE connection status globally |
| 1125-refresh-coordinator | P1 | Wire refresh button, pull-to-refresh, React Query |
| 1123-skeleton-architecture | P2 | Fix skeleton dimensions to match final elements |

### Implementation Order

```
1126 (SECURITY) → 1124 + 1125 (parallel) → 1123 (UI polish)
```

---

## Key Decisions Made

### 1. httpOnly Cookies for Auth (Industry Best Practice)
```
OLD (INSECURE):
  localStorage → zustand persist → tokens in JavaScript

NEW (SECURE):
  Server sets: Set-Cookie: session=xyz; HttpOnly; Secure; SameSite=Strict
  JavaScript CANNOT read tokens
  Zustand stores only: { user, isAuthenticated, isLoading }
```

### 2. CSRF Protection Required
- `SameSite=Strict` on cookies
- CSRF tokens on state-changing requests
- Origin header validation on backend

### 3. /api/me for Session Hydration
- On page load, call `GET /api/me`
- Server validates httpOnly cookie, returns user profile
- Zustand populated with non-sensitive data only

### 4. localStorage Fallback REMOVED
- The "fallback" to memory storage was causing silent logouts
- Not a real solution - just masked the problem
- httpOnly cookies work in ALL browsing modes

---

## Files to Modify

### Spec 1126 (Security Fix)

**Backend**:
- `src/lambdas/dashboard/auth.py` - Add httpOnly cookie handling
- `src/lambdas/dashboard/middleware.py` - Add Origin validation
- New: `src/lambdas/dashboard/csrf.py` - CSRF token management

**Frontend**:
- `frontend/src/stores/auth-store.ts` - REMOVE tokens, keep only UI state
- `frontend/src/hooks/use-session-init.ts` - Call /api/me instead of localStorage
- `frontend/src/lib/api/client.ts` - Remove Bearer header, add `credentials: 'include'`
- `frontend/src/lib/api/auth.ts` - Remove token handling

### Spec 1124 (SSE Store)
- `frontend/src/stores/sse-store.ts` - New global store
- `frontend/src/hooks/use-sse.ts` - Publish status to store
- `frontend/src/app/(dashboard)/layout.tsx` - Read from store

### Spec 1125 (Refresh Coordinator)
- `frontend/src/hooks/use-refresh-coordinator.ts` - New hook
- `frontend/src/app/(dashboard)/layout.tsx` - Wire callbacks
- Integrate `PullToRefresh` component

### Spec 1123 (Skeletons)
- `frontend/src/components/auth/user-menu.tsx` - Fix skeleton dimensions
- `frontend/src/components/navigation/desktop-nav.tsx` - Fix user section skeleton

---

## Spec Locations

```
/home/traylorre/projects/sentiment-analyzer-gsk/specs/
├── 1123-skeleton-architecture/
│   ├── spec.md
│   └── checklists/requirements.md
├── 1124-sse-connection-store/
│   ├── spec.md
│   └── checklists/requirements.md
├── 1125-refresh-coordinator/
│   ├── spec.md
│   └── checklists/requirements.md
├── 1126-auth-httponly-migration/
│   ├── spec.md
│   └── checklists/requirements.md
└── SESSION-SUMMARY.md  ← THIS FILE
```

---

## Next Steps

1. **Run `/speckit.plan` on 1126-auth-httponly-migration** (security first)
2. Then `/speckit.tasks` and `/speckit.implement`
3. After 1126 merged, do 1124 and 1125 in parallel
4. Finally 1123 for UI polish

---

## Context for Sub-Agents

- **Template repo**: `/home/traylorre/projects/terraform-gsk-template`
- **Target repo**: `/home/traylorre/projects/sentiment-analyzer-gsk`
- **Current branch**: `1123-skeleton-architecture`
- **PR #588**: Zustand hydration fix (already merged) - added `_hasHydrated` flag
- **Unit tests trigger on git commit** - use sub-agents for any git operations to avoid context pollution

---

## Key Findings from Risk Analysis

1. **SSE status never exposed** - `useSSE()` stores status locally, Header gets hardcoded 'connected'
2. **Refresh button wired to nothing** - `onRefresh` prop never passed in layout
3. **React Query not invalidated** - Manual refresh doesn't clear caches
4. **Multi-system race conditions** - Auth, runtime config, SSE all hydrate independently
5. **No "app ready" signal** - Components don't know when all systems initialized

---

## Commands Reference

```bash
# View specs
cat /home/traylorre/projects/sentiment-analyzer-gsk/specs/1126-auth-httponly-migration/spec.md

# Continue with planning
/speckit.plan   # On current feature

# Check branch
cd /home/traylorre/projects/sentiment-analyzer-gsk && git branch
```
