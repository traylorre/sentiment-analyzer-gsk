# Feature 1287: Operator Admin Route Group

> Supersedes: Feature 1284 (chaos-admin-auth) — wrong framing (separate dashboard)

## Summary

Add an `/admin/*` route group to the existing Next.js customer frontend that is only accessible to users with the `operator` role. This is infrastructure for Feature 1288 (chaos admin pages) and any future operator-only functionality.

**Key constraint:** This is NOT a separate application. It is a route group within the same Amplify/Next.js frontend that customers use. Operators see extra navigation; regular users never know it exists.

## User Stories

### US-001: Operator sees admin navigation
As an operator, I want to see an "Admin" link in the navigation bar so that I can access operator-only pages without leaving the customer frontend.

**Acceptance criteria:**
- Admin nav link visible only when `user.role === 'operator'`
- Link navigates to `/admin/chaos` (the only admin page initially)
- Desktop: appears in sidebar nav below existing items
- Mobile: appears in mobile nav menu

### US-002: Non-operator cannot access admin routes
As a security engineer, I want non-operator users to be blocked from `/admin/*` routes so that chaos controls are not exposed to customers.

**Acceptance criteria:**
- Unauthenticated users redirected to `/auth/signin`
- Authenticated non-operator users see a 403 Forbidden page
- Direct URL navigation to `/admin/*` is blocked (not just hidden nav)
- Server-side middleware enforcement (not just client-side)

### US-003: Operator role check uses existing auth
As a developer, I want operator role checking to use the existing auth system (Cognito + `/api/v2/auth/me`) so that no new auth infrastructure is needed.

**Acceptance criteria:**
- Role comes from `user.role` in Zustand auth store
- Role is refreshed via existing `refreshUserProfile()` mechanism
- Cross-tab sync via existing `useAuthBroadcast()` works for role changes
- No new cookies, tokens, or auth endpoints required

### US-004: Forbidden page is helpful
As a user who accidentally navigates to an admin URL, I want a clear 403 page so that I understand why I can't access it.

**Acceptance criteria:**
- Shows "Access Denied" message (not a generic error)
- Includes link back to dashboard (`/`)
- Does not reveal what the admin page contains
- Matches existing app styling (shadcn/Tailwind)

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Add `(admin)` route group under `src/app/` | MUST |
| FR-002 | Create admin layout with operator role check | MUST |
| FR-003 | Redirect unauthenticated users to `/auth/signin` from admin routes | MUST |
| FR-004 | Render ForbiddenPage component inline for authenticated non-operators | MUST |
| FR-005 | Add `useIsOperator()` hook to auth system | MUST |
| FR-006 | Update Next.js middleware to enforce `/admin/*` authentication server-side (role checked client-side) | MUST |
| FR-007 | Add "Admin" link to DesktopNav and MobileNav (operator-only) | MUST |
| FR-008 | Create placeholder `/admin/chaos` page (replaced by Feature 1288) | SHOULD |
| FR-009 | Cross-tab role sync: if operator role is revoked, redirect to forbidden | SHOULD |
| FR-010 | Admin layout reuses existing dashboard chrome (header, nav) | SHOULD |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | No new auth infrastructure (no new Cognito pools, no new tokens) | MUST |
| NFR-002 | No new API endpoints | MUST |
| NFR-003 | Server-side middleware check completes in <10ms | SHOULD |
| NFR-004 | 403 page renders at 375px without horizontal scroll | MUST |
| NFR-005 | All interactive elements keyboard-accessible | MUST |
| NFR-006 | Admin nav link does not cause layout shift for non-operators | SHOULD |

### Security Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| SR-001 | Server-side authentication enforcement in middleware.ts (Tier 1) | MUST |
| SR-002 | Client-side operator role check in admin layout (Tier 2 — primary authorization gate) | MUST |
| SR-003 | No information leakage: 403 page must not reveal admin page content | MUST |
| SR-004 | Role check must use the role from auth store (populated via `/api/v2/auth/me`) | MUST |
| SR-005 | Admin routes must not be discoverable via sitemap, robots.txt, or link prefetching | SHOULD |

## Edge Cases

1. **Operator role assigned while user is logged in**: Next `refreshUserProfile()` call picks it up; admin nav appears without re-login
2. **Operator role revoked while on admin page**: Cross-tab broadcast triggers redirect to forbidden (FR-009)
3. **Expired session on admin page**: Existing token refresh handles it; if refresh fails, redirect to sign-in
4. **Deep link to admin subpage**: Middleware blocks before page component renders
5. **SSR vs CSR mismatch**: Middleware runs server-side; client layout is a fallback check, not the primary gate

## Success Criteria

| ID | Criterion |
|----|-----------|
| SC-001 | Non-operator user navigating to `/admin/chaos` sees 403 page |
| SC-002 | Unauthenticated user navigating to `/admin/chaos` is redirected to sign-in |
| SC-003 | Operator user navigating to `/admin/chaos` sees the admin page |
| SC-004 | Admin nav link is not visible to non-operator users |
| SC-005 | Authentication enforced server-side in middleware; authorization enforced client-side in admin layout |
| SC-006 | No new auth infrastructure created |
| SC-007 | Forbidden page renders correctly at 375px viewport |

## Out of Scope

- Chaos dashboard content (Feature 1288)
- Backend chaos API changes (backend already supports operator role)
- Cognito user pool changes (operator role assigned via DynamoDB user table)
- Role assignment UI (operators are assigned via backend/DB — manual for now)

## Files to Create/Modify

### New Files
- `frontend/src/app/(admin)/layout.tsx` — Admin layout with operator role check + inline ForbiddenPage
- `frontend/src/app/(admin)/admin/chaos/page.tsx` — Placeholder (replaced by 1288)
- `frontend/src/hooks/use-operator.ts` — `useIsOperator()` hook
- `frontend/src/components/admin/forbidden-page.tsx` — 403 Forbidden component

### Modified Files
- `frontend/src/middleware.ts` — Add `/admin/*` authentication enforcement
- `frontend/src/components/navigation/desktop-nav.tsx` — Add admin link (operator-only)
- `frontend/src/components/navigation/mobile-nav.tsx` — Add admin link (operator-only)

## Architecture Decision: Two-Tier Access Control

The JWT access token (issued by Cognito) does **NOT** contain a `role` claim. Role is stored in the DynamoDB user table and returned only by `/api/v2/auth/me`.

**Tier 1 — Server-side middleware (authentication):** Verifies the user has a valid session (access token cookie exists and is not expired). Blocks unauthenticated users from `/admin/*` with redirect to `/auth/signin`. Cannot check role.

**Tier 2 — Client-side admin layout (authorization):** After page loads, checks `user.role === 'operator'` from Zustand store (populated by `/api/v2/auth/me`). Non-operators see the ForbiddenPage component inline (no redirect, no separate route).

**Why not decode JWT in middleware?** The JWT doesn't have role claims. Making a network call to `/api/v2/auth/me` from middleware adds latency and a failure mode. The two-tier approach is simpler, reliable, and still defense-in-depth.

**Why render forbidden inline instead of redirecting?** A redirect to `/admin/forbidden` would itself be under the `/admin/*` matcher, creating a redirect loop. Rendering the forbidden component inside the admin layout avoids this entirely.

## Corrected File Paths

### Route Structure
```
frontend/src/app/
├── (admin)/                          # Route group (no URL segment)
│   ├── layout.tsx                    # Operator role check, renders ForbiddenPage if non-operator
│   └── admin/                        # URL segment: /admin
│       └── chaos/
│           └── page.tsx              # URL: /admin/chaos (placeholder, replaced by 1288)
```

Note: `(admin)` is the Next.js route group for layout sharing. The actual URL path `/admin/chaos` comes from the nested `admin/chaos/` folders.

### Navigation Components (verified paths)
- `frontend/src/components/navigation/desktop-nav.tsx`
- `frontend/src/components/navigation/mobile-nav.tsx`

## Deprecation Note

Features 1284, 1285, 1286 are **deprecated**. They were written with a "separate chaos dashboard" framing (Option A). This feature (1287) and its successors (1288, 1289) implement Option B: chaos controls integrated into the customer frontend.

## Clarifications

| # | Question | Answer | Source |
|---|----------|--------|--------|
| 1 | Share dashboard chrome or separate layout? | Share existing dashboard chrome — admin pages feel like same app | User: "NOT a separate application" |
| 2 | Admin nav icon? | Shield (Lucide `ShieldCheck`) | Convention for admin sections |
| 3 | Operator role revoked mid-session? | Next `refreshUserProfile()` updates store, layout renders ForbiddenPage | Existing auth polling model, no WebSocket |
| 4 | Breadcrumbs? | No — sidebar only, no breadcrumb component exists | Codebase search |
| 5 | How is operator role assigned in DynamoDB? | **DEFERRED** — affects Playwright test user provisioning | Open question from prior session |

All questions self-answered except #5 (deferred to Phase 2 cumulative review).

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | CRITICAL | Middleware cannot check role — JWT has no role claim, role is only in DynamoDB/auth-me endpoint | Two-tier approach: middleware checks authentication only, admin layout checks authorization. Added Architecture Decision section. |
| 2 | HIGH | Route group structure was wrong — `(admin)/chaos/page.tsx` would give URL `/chaos`, not `/admin/chaos` | Fixed: `(admin)/admin/chaos/page.tsx` gives correct URL `/admin/chaos` |
| 3 | HIGH | Forbidden page as separate route under `/admin/*` creates redirect loop | Changed to inline component rendering in admin layout — no redirect needed |
| 4 | MEDIUM | Nav component paths were guessed (`components/nav/`) — actual path is `components/navigation/` | Fixed file paths in spec |
| 5 | LOW | No Playwright test requirements in spec | Deferred to Feature 1288 test suite which will cover access control |
| 6 | LOW | SR-001 says "server-side enforcement" but middleware can only enforce authentication, not authorization | Updated SR-001 wording to reflect two-tier model |

**Spec edits made:**
- Added "Architecture Decision: Two-Tier Access Control" section
- Fixed route group folder structure
- Changed forbidden from separate page to inline component
- Corrected navigation component paths
- Updated FR-006 and SR-001 to reflect authentication-only middleware

**Gate: 0 CRITICAL, 0 HIGH remaining.**
