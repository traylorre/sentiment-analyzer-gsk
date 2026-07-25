# Implementation Plan: Settings Dead-Nav Fix

**Branch**: `1385-settings-dead-nav` | **Date**: 2026-07-24 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/1385-settings-dead-nav/spec.md`

## Summary

The customer dashboard's left/bottom navigation is state-only, not routing. Both nav components render `<button onClick={() => setView(view)}>`, mutating the Zustand `view-store` `currentView` without ever calling the Next.js router. The intended in-place view container (`SwipeView`/`SwipeContainer`) is never mounted, so real content is served by file-based routes under `frontend/src/app/(dashboard)/`. Result: once a user reaches the `/settings` route (via a hard `window.location.href` in the user menu), every nav click only re-paints the highlight and never changes the route — the nav is "dead." The Guest/Anonymous flash reported at the same time is the same hard navigation wiping the memory-only auth store.

Approach (frontend-only): (1) convert the four primary nav items in both `desktop-nav.tsx` and `mobile-nav.tsx` to client-side routing (`<Link>` / `router.push`) targeting `/`, `/configs`, `/alerts`, `/settings`; (2) derive active-highlight from `usePathname` instead of `currentView`, matching the already-working Admin link; (3) replace `window.location.href = '/settings'` in `user-menu.tsx` with client-side navigation to preserve the in-memory session; (4) keep the swipe/gesture layer non-regressed. No backend, no infra, no new AWS resources.

## Technical Context

**Language/Version**: TypeScript 5.x / Next.js 14 (App Router) / React 18 (frontend only).
**Primary Dependencies**: `next/link`, `next/navigation` (`usePathname`, `useRouter`), Zustand (`view-store`, `auth-store`), Radix `DropdownMenu` (user-menu), framer-motion (layout-id highlight animation), lucide-react (icons).
**Storage**: None changed. `auth-store` is memory-only by design (`frontend/src/stores/auth-store.ts:6,71`); `view-store` persists only `currentView` (`view-store.ts:180`).
**Testing**: Vitest unit (nav render/active-state), Playwright E2E against the Amplify URL (customer dashboard, per CLAUDE.md Two-Dashboards rule). `frontend/tests/e2e/*.spec.ts`, `cd frontend && npx playwright test`.
**Target Platform**: AWS Amplify (Next.js). Customer dashboard only — do NOT touch `src/dashboard/` (HTMX admin).
**Project Type**: Web (separate `frontend/`).
**Performance Goals**: Client-side route transitions (no full page reload); nav interaction feels instant.
**Constraints**: Frontend-only; no new AWS resources; preserve mobile swipe/gesture + operator Admin link; GPG-signed commits. Verify the reported symptom on the Amplify URL, not the Lambda Function URL.
**Scale/Scope**: Small, surgical. Three components edited (`desktop-nav.tsx`, `mobile-nav.tsx`, `user-menu.tsx`), one shared destination map, active-state derivation swap. `view-store`/`swipe-view` optionally left as-is.

## Root-Cause Hypothesis (verified, file:line evidence)

Not a hypothesis — proven against source:

1. **Nav does not route.** `frontend/src/components/navigation/desktop-nav.tsx:37-41` `handleNavClick` calls only `setView(view)`. The four primary items (`desktop-nav.tsx:63-101`) are `<button>` with no `href`/`router.push`. `frontend/src/components/navigation/mobile-nav.tsx:35-39` is identical. Grep confirmed: "NO router.push in either nav."
2. **`setView` has no routing side effect.** `frontend/src/stores/view-store.ts:82-101` sets `currentView` + animation state + a 300ms reset timer. Nothing else.
3. **The in-place view container is never mounted.** `frontend/src/components/navigation/swipe-view.tsx` defines `SwipeView`/`SwipeContainer`; grep found only self-references — they are dead in the app. So `currentView` drives nothing but the highlight.
4. **Content is file-routed.** `frontend/src/app/(dashboard)/` has `configs/`, `alerts/`, `settings/`, root `page.tsx`, `layout.tsx`. These are the actual navigation targets.
5. **Settings-specific trigger.** `frontend/src/components/auth/user-menu.tsx:142` `window.location.href = '/settings'` is the only UI path that lands a user on a distinct sub-route; from there the state-only nav can't leave.
6. **Highlight/URL desync (second defect).** `desktop-nav.tsx:64` `isActive = currentView === item.view` (persisted, `view-store.ts:180`) can disagree with the URL after a hard load, while the working Admin link uses `pathname` (`desktop-nav.tsx:113`).
7. **Guest flash shares cause.** The hard nav (#5) tears down the memory-only auth store (`auth-store.ts:6,71`), so Settings re-inits anonymous until re-restore.

**Confidence: HIGH.** Root cause conclusively found; no diagnostic-first task required.

## Approach

- **A1 — Single destination source of truth.** Extend the nav item model to `{ view, label, icon, route }` (routes: `dashboard→'/'`, `configs→'/configs'`, `alerts→'/alerts'`, `settings→'/settings'`). Shared between desktop and mobile to prevent drift.
- **A2 — Route the primary items.** Replace the primary `<button onClick={setView}>` with `<Link href={route}>` (preferred — restores native keyboard/focus semantics and `aria-current`) or `router.push(route)` in the handler. Keep the framer-motion `layoutId` highlight, but gate it on route-derived active state.
- **A3 — Active state from `usePathname`.** Compute `isActive` by comparing `pathname` to the item's route (`'/'` exact; others `startsWith`), mirroring the Admin link. Optionally sync `currentView` from `pathname` in a small effect so the gesture/animation layer stays coherent, but the router is authoritative (FR-003).
- **A4 — Client-side Settings entry.** In `user-menu.tsx:142`, swap `window.location.href = '/settings'` for `router.push('/settings')` (Radix `DropdownMenu.Item onSelect`), preserving the in-memory session (FR-005). Apply the same to the `/auth/signin` item only if it must preserve state (sign-in generally can hard-nav; scope to Settings unless testing shows otherwise).
- **A5 — Non-regression for gestures/Admin.** Leave `swipe-view.tsx`/`use-gesture.ts` behavior intact (already non-routing and unmounted); do not claim to newly wire gestures. Admin link already routes — leave it, just ensure the shared active-state change doesn't alter it.

## Project Structure

### Documentation (this feature)

```text
specs/1385-settings-dead-nav/
├── plan.md      # This file
├── spec.md      # Spec + Adversarial Review #1 + Clarifications
└── tasks.md     # Task list + Adversarial Review #3
```

### Source Code (repository root)

```text
frontend/src/components/navigation/
├── desktop-nav.tsx    # Primary items → Link/router.push; isActive from usePathname (FR-001..FR-004, FR-006)
└── mobile-nav.tsx     # Same rewrite for bottom nav (FR-004)

frontend/src/components/auth/
└── user-menu.tsx      # window.location.href='/settings' → router.push (FR-005)

frontend/src/stores/
└── view-store.ts      # (optional) currentView mirrors pathname; no routing responsibility added

frontend/tests/
├── e2e/               # Playwright: Settings → nav routes on Amplify URL (SC-001, SC-002, SC-003)
└── unit/ (vitest)     # nav render, active-state from pathname, keyboard activation (SC-004)
```

**Structure Decision**: Web app, frontend-only. The fix is concentrated in two nav components plus one user-menu line. `view-store`/`swipe-view` edits are optional and non-load-bearing for the core fix; keeping them untouched minimizes blast radius (they are already dead/animation-only).

## Constitution / Constraints Check

*GATE: pass before tasks.*

- **No new AWS resources**: frontend-only routing change. **PASS.**
- **Two-Dashboards rule (CLAUDE.md)**: all edits under `frontend/`; verification on the Amplify URL; `src/dashboard/` untouched. **PASS.**
- **Security**: no auth logic change; `auth-store` stays memory-only (client-side routing *preserves* the security posture that removed `persist()`). Replacing a hard nav with client routing does not weaken it. **PASS.**
- **A11y**: `<Link>` restores native keyboard/role semantics; FR-006 adds `aria-current`. **PASS.**
- **Testing discipline**: unit for active-state/keyboard; Playwright on Amplify for the real symptom. **PASS.**

No violations.

---

## Adversarial Review #2

Re-read spec.md (incl. AR#1 + Clarifications) and plan.md for drift and cross-artifact consistency introduced by the clarifications.

| # | Sev | Drift / inconsistency | Resolution |
|---|-----|------------------------|------------|
| 1 | HIGH | **`<Link>` vs framer-motion `layoutId` highlight.** The primary items rely on `motion.div layoutId="desktop-nav-bg"/"...-indicator"` for the sliding highlight (`desktop-nav.tsx:80-95`). Naively swapping `<button>` for `<Link>` could drop the animation or break the shared-layout transition, and mixing `currentView`- and `pathname`-driven active state mid-file would double-highlight. | Plan A2/A3 keep the `layoutId` markup but gate it on the single route-derived `isActive`. Active state must be computed one way (`pathname`) for all four items in both files — no mixed sources. Tasks pin this as one atomic change per file. |
| 2 | HIGH | **Root-cause consistency.** Spec asserts "no router.push in either nav" and unused `SwipeView`; plan must not contradict by editing `swipe-view.tsx` as if it were live. | Plan A5 explicitly leaves `swipe-view.tsx`/`use-gesture.ts` intact (dead/animation-only) and scopes edits to the two nav files + user-menu — consistent with spec Q1/Q4. |
| 3 | MED | **`'/'` active-match ambiguity.** `startsWith('/')` matches every route, so dashboard would always highlight. | A3 specifies exact match for `'/'` and `startsWith` for the others. Mirrors the Admin link's `startsWith('/admin')` but with the root special-cased. Called out so the implementer doesn't ship an always-on dashboard highlight. |
| 4 | MED | **Scope of the `window.location.href` swap.** user-menu also hard-navs to `/auth/signin` (`user-menu.tsx:131`). Spec FR-005 only requires the Settings entry to preserve session. | Plan scopes A4 to `/settings`; sign-in may legitimately hard-nav (no session to preserve on the way to signing in). Tasks limit the change to line 142 unless E2E shows a sign-in regression — avoids over-reach. |
| 5 | MED | **Gesture handlers still call `setView` only** (`use-gesture.ts:208`). If `currentView` becomes a pathname mirror, a swipe would change `currentView` but not the route, re-introducing a mini dead-nav on mobile swipe. | Consistent with spec Q4/FR-007: the fix does not *claim* to make swipe route; it must not *regress* current swipe behavior. If A3 mirrors `currentView` from `pathname`, an effect could overwrite a gesture's `setView` — so tasks require: either don't mirror (leave `currentView` independent) OR make gesture handlers `router.push`. Decision recorded, not left ambiguous. |
| 6 | LOW | **Persisted `currentView`** (`view-store.ts:180`) could still seed a stale highlight for one frame before pathname wins. | Deriving `isActive` purely from `pathname` (not `currentView`) means the persisted value never drives the highlight — the one-frame risk is eliminated by not reading `currentView` for active state at all. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** The two HIGHs (animation preservation, dead-code consistency) are resolved by keeping `layoutId` markup with a single `pathname`-derived active source and by explicitly not touching the dead swipe components. MEDs are converted to pinned implementation decisions (root-exact match, Settings-only hard-nav swap, gesture non-regression rule). Spec ↔ plan agree on: frontend-only, two-nav-files + one user-menu line, `usePathname` active state, memory-only session preserved, no new AWS resources.
