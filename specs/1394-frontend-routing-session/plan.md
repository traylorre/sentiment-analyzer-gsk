# Implementation Plan: Router-as-Source-of-Truth (Feature 1394)

**Spec**: `./spec.md` · **Research**: `./research.md` · **Status**: Draft (planning only)
**Scope**: Frontend-only (`frontend/`). No `auth-store.ts` edits (coordination boundary with 1384). No backend/infra.

## Technical Context

- **Stack**: TypeScript 5.x, Next.js 14 App Router, React 18, Zustand 5, Framer Motion, Radix, Playwright + Vitest.
- **Source of truth shift**: from `view-store.currentView` (persisted, drives an unmounted view container) → `usePathname()` (URL).
- **Non-goals**: session mint/restore logic (1384), avatar (1380), copy changes.

## Approach (by root cause)

### RC-A — split-brain nav → make the router authoritative

1. **`desktop-nav.tsx`** — replace the four `<button onClick={handleNavClick}>` (`:68-101`) with `<Link href={route}>` wrapping the existing inner markup (icon + label + the Framer `motion.div layoutId="desktop-nav-bg"/"desktop-nav-indicator"` at `:80-95`). Derive `isActive` from `usePathname()` (not `currentView`), mirroring the Admin link at `:113`. Add `aria-current={isActive ? 'page' : undefined}`. Keep a focus-visible ring (align with mobile). Map `NAV_ITEMS` from `{view}` to `{label, icon, route}` where route = `/` | `/configs` | `/alerts` | `/settings`.
2. **`mobile-nav.tsx`** — same conversion (`:59-124`); it already has Enter/Space + focus ring, but `<Link>` makes those native. `isActive` from `usePathname()`.
3. **`DesktopHeader`** (`desktop-nav.tsx:141-171`) — derive `displayTitle` from `usePathname()` via a `route→title` map, not `viewTitles[currentView]` (FR-007).
4. **`view-store` reconciliation (FR-009)** — chosen approach: **demote to animation/gesture layer.** Remove `partialize`/persist of `currentView` (`view-store.ts:178-182`) so no stale nav state survives reload; keep gesture/pull-to-refresh/bottom-sheet state. `setView` is retained ONLY for the swipe animation layer if Q4 keeps swipe-routing; nav no longer calls it. Justification (NFR-002): this is the one intentional structural change — leaving `currentView` persisted keeps F1/F6 alive.

### RC-B — hard-nav wipes memory auth → client-side routing

5. **`user-menu.tsx`** — `useRouter()`; convert `:142` (`/settings`), `:49` and `:131` (`/auth/signin`) from `window.location.href` to `router.push(...)`. **Coordination**: these are distinct lines from 1380's avatar render hunks (`:78-80`, `:103-105`) — keep hunks separable (NFR-004).
6. **Audit remaining in-SPA hard-navs (FR-003)** — `auth-degradation-toast.tsx:29` → `router.push('/auth/signin')`; `lib/api/errors.ts:45` (`window.location.href='/'`) — this fires from the API error layer (non-component); evaluate whether a full reload is intended (it may be a deliberate hard reset on unrecoverable error). Decision recorded in tasks per call site. `sign-out-dialog.tsx:35` (`→'/'` after signout) and `error-boundary.tsx` reloads are **intentional** (post-signout / crash recovery) → leave, document why.

### RC-B/US3 — Upgrade Now button

7. **`settings/page.tsx`** — add `const router = useRouter()`; wire `<Button onClick={() => router.push('/auth/signin')}>` at `:137`. Keep `isAnonymous` gate (`:127`). Do NOT import `useTierUpgrade`.

### F2/US4 — signin honors `redirect`

8. **`signin/page.tsx`** — read `useSearchParams().get('redirect')`; validate via a shared `safeInternalPath(redirect)` helper (single leading `/`, not `//`, no scheme/host → else `/`). Stash the validated target for the post-login handlers.
9. **Post-login routing** — `use-auth.ts` `verifyToken` (`:150`) and `handleCallback` (`:168`) currently `router.push('/')`. Thread the validated `redirect` (read from the URL at the signin/callback layer) so they route to the origin. **Coordination**: `use-auth.ts` is where 1384 removes the anon-mint init effect (`:52-69`); the redirect change is in the callback/verify callbacks (`:147-171`), a different region — keep hunks separable. Prefer implementing the redirect read/validate at the page layer (`signin`, `callback`, `verify`) to minimize `use-auth.ts` churn and 1384 collision.
10. **`safeInternalPath`** — new pure helper in `frontend/src/lib/` (e.g. `lib/navigation.ts`), unit-tested against the SC-005 attack strings.

### F4/F5/F8 — swipe + dots + header (Q4 decision)

11. Per Clarifications Q4, **wire swipe + `ViewIndicator` to `router.push` the adjacent route** (keep UX, make it honest) OR retire them. Plan recommendation: **retire `ViewIndicator` dots** (pure hint, low value, `(dashboard)/layout.tsx:44-47`) and **route the swipe** in `useSwipeNavigation` (`use-gesture.ts:204-218`) using an ordered route list + `router.push`. Final call justified in tasks; both satisfy FR-008.

## Structure / files touched

```
frontend/src/
  components/navigation/desktop-nav.tsx     # Link + usePathname + aria-current + header title
  components/navigation/mobile-nav.tsx      # Link + usePathname
  components/navigation/swipe-view.tsx      # ViewIndicator: retire or route
  components/auth/user-menu.tsx             # router.push (nav hunks only — coord w/ 1380)
  components/ui/auth-degradation-toast.tsx  # router.push
  app/(dashboard)/settings/page.tsx         # Upgrade Now onClick → router.push
  app/auth/signin/page.tsx                  # read+validate redirect
  app/auth/callback/page.tsx                # honor redirect (page-layer)
  app/auth/verify/page.tsx                  # honor redirect (page-layer)
  hooks/use-gesture.ts                      # swipe → router (if kept)
  stores/view-store.ts                      # drop persist of currentView; demote to anim layer
  lib/navigation.ts                         # NEW safeInternalPath()
tests/
  unit + e2e (see tasks.md)
```

## Coordination & sequencing (see research.md §5)

- **Do NOT edit `auth-store.ts`** (1380/1384 own it). SC-007 gate.
- **`user-menu.tsx`**: 3 features touch it (1394 nav, 1380 avatar, 1384 mounts useAuth). Land 1394's `router.push` hunks and 1380's avatar-render hunks as non-overlapping regions; review together.
- **`use-auth.ts`**: minimize churn (redirect read at page layer) to avoid colliding with 1384's `:52-69` removal.
- **Recommended order**: 1384 → 1394 → 1380, or 1394 ∥ 1380 alongside 1384 (1394 avoids `auth-store.ts`; 1380's `auth-store.ts` hunk is a narrow additive field).

## Verification

- Unit (Vitest): `safeInternalPath` allow/deny table; nav renders `<Link>` with correct `href` + `aria-current` from mocked `usePathname`; Upgrade Now calls `router.push('/auth/signin')`; header title from pathname.
- E2E (Playwright, Amplify): nav click changes route+content with no document reload; owner-login → Settings → nav → identity preserved (no Anonymous frame); anonymous → Alerts → signin?redirect=/alerts → login → lands `/alerts`; Upgrade Now → `/auth/signin`. Upgrade the presence-only `settings.spec.ts:83-86` to click+assert.
- Regression: Admin link, pull-to-refresh, bottom-sheet animations unaffected.

## Risks

- **Framer `layoutId` shared-layout animation** across `<Link>` boundaries — verify the active-indicator still animates; if `<Link>` breaks it, keep `<button>` + `onClick={()=>router.push()}` as fallback (still client-side, still fixes RC-A/B). (AR#2 F1)
- **`view-store` demotion blast radius** — `pull-to-refresh.tsx`, `bottom-sheet.tsx`, `use-gesture.ts` read the store; only `currentView` nav-authority + its persistence are removed, gesture/refresh/sheet state stays. (AR#2 F2)
- **1384 collision on `use-auth.ts`** — mitigated by doing redirect at the page layer. (AR#2 F3)

---

## Adversarial Review #2

Attacked the plan for feasibility, hidden coupling, merge collisions, and whether it silently expands into 1384/1380's territory.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | HIGH | **`<Link>` may break the Framer `layoutId` active-indicator** (`desktop-nav.tsx:80-95`, `mobile-nav.tsx:80-86`) — shared-layout animation across route boundaries can drop or double-render. A broken animation is a visible regression. | Added Risk + fallback: wrap the existing `motion.div` inside `<Link>`; if the shared-layout animation misbehaves, fall back to `<button onClick={router.push}>` (still client-side, still satisfies FR-001/RC-A/RC-B). Tasks include an explicit "verify indicator animates" check. |
| 2 | HIGH | **Plan could drift into `auth-store.ts` while "fixing the Guest flash," colliding with 1384.** | Reaffirmed: the flash is fixed ONLY by removing self-inflicted reloads (steps 5-7). Step list never edits `auth-store.ts`; SC-007 gates it; redirect handling kept at the page layer (step 8-9) to avoid `use-auth.ts`/1384 overlap. |
| 3 | HIGH | **Retiring `view-store` could break `pull-to-refresh.tsx`/`bottom-sheet.tsx`/`use-gesture.ts` which import it.** | Step 4 scoped to removing ONLY nav-authority + `currentView` persistence; gesture/pull/sheet state retained. FR-010/SC-006 guard. Grep of consumers enumerated in tasks before edit. |
| 4 | MED | **`errors.ts:45` hard reload may be intentional** (unrecoverable-error reset); blindly converting it could hide a needed reset. | Step 6 makes it a per-call-site decision with recorded justification, not a blanket convert. Only in-SPA *navigations* convert; deliberate resets (signout, crash) stay. |
| 5 | MED | **Threading `redirect` through `use-auth.ts` callbacks risks 1384 merge conflict** (`use-auth.ts:52-69` is 1384's removal site). | Step 9 prefers reading/validating `redirect` at the page layer (`signin`/`callback`/`verify`) so `use-auth.ts` churn is minimal and in a different region (`:147-171`) than 1384's edit. |
| 6 | MED | **Open-redirect helper could be bypassed by backslash/encoded tricks** (`/\evil`, `/%2Fevil`, `\/\/evil`). | `safeInternalPath` (step 10) normalizes: reject if not exactly one leading `/`, reject `//` and `/\`, reject any `:` before the first `/`, decode once and re-check; unit table includes backslash + encoded cases (extends SC-005). |
| 7 | LOW | **Mobile nav already had Enter/Space + ring; `<Link>` swap could regress `role="tab"` semantics** (`mobile-nav.tsx:50,74-77`). | Keep or drop `role="tablist"/"tab"` deliberately: since these are now real page links, `aria-current="page"` on `<Link>` is more correct than tab semantics. Tasks note the ARIA model change (nav links, not tabs). |

**Gate: 0 CRITICAL, 0 HIGH remaining** (F1/F2/F3 mitigated with fallbacks + scope fences). MED/LOW carried into tasks.
