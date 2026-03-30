# Feature 1287: Operator Admin Routes — Implementation Plan

## Technical Context

### Existing Infrastructure (No Changes Needed)
- **Auth types**: `UserRole = 'anonymous' | 'free' | 'paid' | 'operator'` already defined in `frontend/src/types/auth.ts`
- **Auth store**: `useUserRole()` selector already exists in `frontend/src/stores/auth-store.ts`
- **Profile refresh**: `refreshUserProfile()` fetches `/api/v2/auth/me` which returns `role` field
- **Cross-tab sync**: `useAuthBroadcast()` broadcasts role changes across tabs
- **Backend**: `/api/v2/auth/me` already returns `role` field from DynamoDB user table

### Architecture: Two-Tier Access Control

```
Request → Next.js Middleware (Tier 1: Authentication)
              │
              ├── No session cookie → Redirect to /auth/signin
              │
              └── Has session cookie → Allow through
                      │
                      └── Admin Layout (Tier 2: Authorization)
                              │
                              ├── user.role !== 'operator' → Render ForbiddenPage
                              │
                              └── user.role === 'operator' → Render children
```

**Why two tiers?**
- JWT doesn't contain role claim (Cognito limitation)
- Middleware can't call APIs (latency + failure mode)
- Client layout has access to Zustand store with role
- Two independent checks = defense in depth

## Implementation Phases

### Phase 1: Hook + Component (no routing changes)

**File: `frontend/src/hooks/use-operator.ts`**
```typescript
// Simple selector hook wrapping existing auth store
export function useIsOperator(): boolean
```

**File: `frontend/src/components/admin/forbidden-page.tsx`**
```typescript
// Standalone component: "Access Denied" message + link to /
// Uses existing shadcn Card + Button components
// No information leakage about what the admin page contains
```

### Phase 2: Middleware Update

**File: `frontend/src/middleware.ts`**
- Add `/admin/:path*` to matcher config
- For admin routes: check session cookie exists → redirect to `/auth/signin` if not
- Pattern: identical to existing `upgradedRoutes` check but for `/admin/*` paths
- No role check here (JWT has no role claim)

### Phase 3: Admin Route Group

**File: `frontend/src/app/(admin)/layout.tsx`**
```typescript
// Client component ('use client')
// Uses useIsOperator() hook
// If loading: show skeleton
// If not operator: render <ForbiddenPage />
// If operator: render {children} wrapped in existing dashboard layout chrome
```

**File: `frontend/src/app/(admin)/admin/chaos/page.tsx`**
```typescript
// Placeholder page: "Chaos Dashboard — Coming Soon"
// Will be replaced by Feature 1288
```

### Phase 4: Navigation Links

**File: `frontend/src/components/navigation/desktop-nav.tsx`**
- Add conditional "Admin" nav item below existing items
- Only rendered when `useIsOperator()` returns true
- Links to `/admin/chaos`
- Icon: Shield or Settings from Lucide

**File: `frontend/src/components/navigation/mobile-nav.tsx`**
- Same conditional admin link in mobile menu
- Same icon and behavior

## Data Flow

```
1. User logs in → /api/v2/auth/me returns { role: 'operator' }
2. Auth store: user.role = 'operator'
3. useIsOperator() returns true
4. DesktopNav renders "Admin" link
5. User clicks → /admin/chaos
6. Middleware: session cookie exists? YES → allow
7. Admin layout: useIsOperator()? YES → render chaos page
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Role field missing from /me response | Low | High | Treat undefined role as non-operator |
| Zustand store race condition on page load | Medium | Low | Show skeleton while loading, check after hydration |
| Middleware matcher misconfiguration | Low | High | Test with non-operator user in Playwright |

## Dependencies

- **Upstream**: None — all auth infrastructure exists
- **Downstream**: Feature 1288 (chaos admin pages) depends on this route group

## Adversarial Review #2

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | SC-005 said "all protection server-side" but middleware only does authentication | MEDIUM | Updated SC-005 to reflect two-tier model |
| 2 | Plan doesn't specify how admin layout reuses dashboard chrome | MEDIUM | Clarified: admin layout imports DesktopNav/MobileNav directly, same pattern as (dashboard)/layout.tsx |
| 3 | No spec drift from AR#1 clarifications | — | No action |
| 4 | Loading state handling consistent between spec and plan | LOW | No action |

**Drift found:** 1 spec edit (SC-005 wording).
**Cross-artifact inconsistencies:** 0 remaining.
**Gate: 0 CRITICAL, 0 HIGH remaining.**
