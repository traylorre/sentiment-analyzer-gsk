# Feature 1287: Operator Admin Routes — Tasks

## Task List

### Task 1: Create `useIsOperator()` hook
- **File**: `frontend/src/hooks/use-operator.ts`
- **Action**: Create new file
- **Details**:
  - Import `useAuthStore` from `../stores/auth-store`
  - Export `useIsOperator()` — returns `boolean` (`user?.role === 'operator'`)
  - Export `useIsOperatorLoading()` — returns `boolean` (auth store still initializing)
  - Keep it minimal: pure selector hooks, no side effects
- **Requirement mapping**: FR-005
- **Depends on**: Nothing

### Task 2: Create ForbiddenPage component
- **File**: `frontend/src/components/admin/forbidden-page.tsx`
- **Action**: Create new file
- **Details**:
  - Client component (`'use client'`)
  - Uses shadcn `Card`, `Button` from existing UI library
  - Displays "Access Denied" heading
  - Subtext: "You don't have permission to access this page."
  - Button: "Back to Dashboard" linking to `/`
  - No information about what the page contains
  - Responsive: centered on all viewports, works at 375px
  - Keyboard accessible: button is focusable
- **Requirement mapping**: FR-004, SR-003, NFR-004, NFR-005
- **Depends on**: Nothing

### Task 3: Update middleware for admin route authentication
- **File**: `frontend/src/middleware.ts`
- **Action**: Modify existing file
- **Details**:
  - Add `/admin/:path*` to the middleware matcher config
  - In the middleware function, check if path starts with `/admin`
  - If admin path and no session cookie (`sentiment-access-token`): redirect to `/auth/signin`
  - If admin path and has session cookie: allow through (role checked client-side)
  - Follow existing pattern used for `upgradedRoutes`
- **Requirement mapping**: FR-003, FR-006, SR-001
- **Depends on**: Nothing

### Task 4: Create admin route group layout
- **File**: `frontend/src/app/(admin)/layout.tsx`
- **Action**: Create new file
- **Details**:
  - Client component (`'use client'`)
  - Import `useIsOperator`, `useIsOperatorLoading` from hooks
  - Import `ForbiddenPage` component
  - Import existing nav components (`DesktopNav`, `MobileNav`) to reuse dashboard chrome
  - Logic:
    - If loading: render skeleton (same pattern as dashboard layout)
    - If not operator: render `<ForbiddenPage />`
    - If operator: render dashboard chrome + `{children}`
  - Wrap in existing `<ErrorBoundary>` if available
- **Requirement mapping**: FR-001, FR-002, FR-010, SR-002
- **Depends on**: Task 1 (hook), Task 2 (ForbiddenPage)

### Task 5: Create placeholder chaos page
- **File**: `frontend/src/app/(admin)/admin/chaos/page.tsx`
- **Action**: Create new file
- **Details**:
  - Simple page: "Chaos Dashboard" heading + "Coming soon" message
  - Uses shadcn Card for consistent styling
  - Will be completely replaced by Feature 1288
  - Add metadata: `export const metadata = { title: 'Chaos Dashboard' }`
  - Note: the folder structure `(admin)/admin/chaos/` produces URL `/admin/chaos`
- **Requirement mapping**: FR-008
- **Depends on**: Task 4 (admin layout)

### Task 6: Add admin link to desktop navigation
- **File**: `frontend/src/components/navigation/desktop-nav.tsx`
- **Action**: Modify existing file
- **Details**:
  - Import `useIsOperator` from `../../hooks/use-operator`
  - Import `ShieldCheck` icon from `lucide-react`
  - Add conditional nav item at bottom of nav list
  - Only render when `useIsOperator()` returns true
  - Link to `/admin/chaos`
  - Label: "Admin"
  - Icon: `ShieldCheck`
  - Follow existing nav item pattern (same classes, same structure)
- **Requirement mapping**: FR-007, NFR-006
- **Depends on**: Task 1 (hook)

### Task 7: Add admin link to mobile navigation
- **File**: `frontend/src/components/navigation/mobile-nav.tsx`
- **Action**: Modify existing file
- **Details**:
  - Same changes as Task 6 but for mobile nav
  - Import `useIsOperator` and `ShieldCheck`
  - Conditional rendering of admin link
  - Follow existing mobile nav item pattern
- **Requirement mapping**: FR-007
- **Depends on**: Task 1 (hook)

## Dependency Graph

```
Task 1 (hook) ──┬──→ Task 4 (layout) ──→ Task 5 (placeholder page)
                │
                ├──→ Task 6 (desktop nav)
                │
                └──→ Task 7 (mobile nav)

Task 2 (forbidden) ──→ Task 4 (layout)

Task 3 (middleware) ── (independent)
```

## Parallelization

- **Parallel group 1**: Tasks 1, 2, 3 (no dependencies, independent files)
- **Parallel group 2**: Tasks 4, 6, 7 (all depend on Task 1, Task 4 also on Task 2)
- **Sequential**: Task 5 after Task 4

## Requirement Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | Task 4 |
| FR-002 | Task 4 |
| FR-003 | Task 3 |
| FR-004 | Task 2, Task 4 |
| FR-005 | Task 1 |
| FR-006 | Task 3 |
| FR-007 | Task 6, Task 7 |
| FR-008 | Task 5 |
| FR-009 | Task 4 (via useIsOperator reactivity) |
| FR-010 | Task 4 |
| SR-001 | Task 3 |
| SR-002 | Task 4 |
| SR-003 | Task 2 |
| SR-004 | Task 1 |
| SR-005 | N/A (no sitemap exists to exclude from) |
| NFR-001 | All (no new auth infra created) |
| NFR-002 | All (no new API endpoints) |
| NFR-004 | Task 2 |
| NFR-005 | Task 2, Task 6, Task 7 |
| NFR-006 | Task 6 |

All MUST requirements have ≥1 mapped task. Coverage: 100%.

## Adversarial Review #3

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Task 5 uses metadata export but parent layout is client component | MEDIUM | Make chaos page a server component; layout gates access as client component, children can be server components |
| 2 | Nav components may depend on dashboard-specific context | MEDIUM | Self-resolved: nav uses root-level providers (auth, config), not dashboard-specific |
| 3 | No unit test task for useIsOperator hook | LOW | Hook is 2 lines; Playwright e2e in Feature 1288 covers full flow |

**Highest-risk task:** Task 4 (admin layout) — authorization gate lifecycle
**Most likely rework:** Task 3 (middleware) — cookie name/path matching must be exact

**READY FOR IMPLEMENTATION** — 0 CRITICAL, 0 HIGH remaining. 7 tasks, ~2 hours estimated.
