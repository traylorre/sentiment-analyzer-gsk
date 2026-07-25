# Feature Specification: Router-as-Source-of-Truth — Navigation + Session-Preserving Routing

**Feature Branch**: `1394-frontend-routing-session` (current worktree — NO new branch)
**Created**: 2026-07-24
**Status**: Draft (planning only — no implementation in this pipeline)
**Target**: CUSTOMER dashboard (`frontend/` — Next.js 14 App Router on Amplify, `https://main.d29tlmksqcx494.amplifyapp.com/`). NOT the HTMX admin dashboard (`src/dashboard/`).
**Supersedes**: `specs/1385-settings-dead-nav` and `specs/1386-upgrade-now-button` (folded in — same root cause + same files; see `research.md §6`).
**Companion**: `specs/1380-oauth-avatar-picture` (sub-feature B, avatar surfacing — independent RC-C, kept as-is). Coordinates with `specs/1384-oauth-session-persistence-harden` (shared files `user-menu.tsx`, `auth-store.ts` — see `research.md §5`).
**Input**: Owner post-OAuth-login QA + directive to research past the "one-liner" framing. Findings in `research.md` (read that first).

---

## Problem Statement

On the customer dashboard the Next.js router is not the navigation source of truth. Two structural defects follow, plus a chain of follow-on symptoms:

- **RC-A — split-brain nav.** The four primary nav items (desktop + mobile) are `<button onClick={() => setView(view)}>` that mutate the vestigial Zustand `view-store.currentView` (`desktop-nav.tsx:37-41,68-70`; `mobile-nav.tsx:35-39,59-61`; `view-store.ts:82-101`). `currentView` was built to drive `SwipeView`/`SwipeContainer`, which are **defined and never mounted** (`swipe-view.tsx`; grep = self-references only). Actual content is file-routed (`app/(dashboard)/{page,configs,alerts,settings}`). So clicking a nav item only re-paints the highlight; it never leaves the route. The bug surfaces on `/settings` because that is the one sub-route users land on (`user-menu.tsx:142`).
- **RC-B — hard-nav wipes the memory-only auth store.** `user-menu.tsx:142` uses `window.location.href='/settings'` (full reload). The auth store is memory-only by design (`auth-store.ts:6,71`, Feature 1165). The reload destroys the signed-in identity; the `/settings` document re-inits anonymous until `restoreSession()` resolves → Settings shows "Guest/Anonymous" while the dashboard had shown the Google user. The same reload triggers Feature 1384's cookie-clobber race.

Both reduce to: **use the router; derive UI state from the URL.** Fixing them together (they share `user-menu.tsx`) also lets us close the follow-ons the owner expected (F1–F7 in `research.md §4`): highlight/URL desync (F1), `/auth/signin` dropping `redirect` (F2), other hard-navs (F3), dead mobile swipe (F4) and dots (F5), stale header title (F6), and the dead `view-store` subsystem (F7). Sub-feature B (avatar, 1380) and 1384 are tracked separately with explicit coordination notes.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Signed-in user navigates out of Settings without losing identity (Priority: P1) 🎯 MVP

A signed-in (Google) user opens Settings from the user menu, then clicks a left/bottom nav item to leave. Navigation works AND identity is preserved (no Guest flash).

**Why P1**: This is the acute reported blocker (dead nav) plus the reported Guest/Anonymous split-brain, which share RC-A/RC-B. Both must fall to one fix.

**Independent Test**: On the Amplify URL, sign in (owner interactive Google login), open Settings via the user menu, click each nav item. Assert (a) the route + rendered content change to the clicked destination, (b) NO full-page reload occurs (client-side route), (c) the account section + UserMenu keep the Google identity with zero transient "Anonymous" frames.

**Acceptance Scenarios**:
1. **Given** a signed-in user on `/settings`, **When** they click Dashboard / Configurations / Alerts, **Then** the app client-side routes to `/` / `/configs` / `/alerts` and renders that content, with no document reload.
2. **Given** any route, **When** the nav is read, **Then** exactly one item is highlighted and it matches the URL (`usePathname`), including after a direct deep-link/reload onto `/settings`.
3. **Given** the transition into and out of Settings, **When** it happens, **Then** the authenticated in-memory session survives (client-side routing, no `window.location.href`).

---

### User Story 2 - Keyboard / assistive-tech user operates the nav (Priority: P1)

A keyboard or screen-reader user tabs to a nav item and activates it with Enter/Space; it routes and exposes correct current-state.

**Why P1**: A nav inert on activation is a WCAG 2.1.1 (Keyboard) and 4.1.2 (Name/Role/Value) failure. Desktop nav today lacks the Enter/Space handler + focus ring the mobile nav has (`mobile-nav.tsx:62-72`).

**Acceptance Scenarios**:
1. **Given** focus on a nav item, **When** Enter or Space is pressed, **Then** the app routes to that destination.
2. **Given** a screen reader, **When** it reads the nav, **Then** the active item is programmatically current (`aria-current="page"`) and tracks the URL.
3. **Given** focus-visible styling, **When** a nav item is focused, **Then** a visible focus ring is present on desktop and mobile.

---

### User Story 3 - Guest clicks "Upgrade Now" and reaches sign-in via the router (Priority: P1)

An anonymous user in Settings clicks the "Upgrade Now" button (`settings/page.tsx:137` — currently no `onClick`, inert) and is taken to `/auth/signin` via client-side routing.

**Why P1**: The reported dead button (former 1386). It shares RC-B: the fix MUST use the router (not `window.location.href`), or it re-introduces the auth-store wipe. "Upgrade" here means anonymous→authenticated (prompt copy `settings/page.tsx:133-136`; `useIsUpgraded` `use-auth.ts:203`), NOT paid-tier billing — `useTierUpgrade` (post-Stripe poller) MUST NOT be used.

**Acceptance Scenarios**:
1. **Given** an anonymous user in Settings, **When** they click Upgrade Now, **Then** they client-side route to `/auth/signin` (magic-link + configured OAuth render), with no document reload and no console error.
2. **Given** an authenticated user, **When** they view Settings, **Then** the button is absent (existing `isAnonymous` gate `settings/page.tsx:127` unchanged).
3. **Given** the button, **When** focused, **Then** it is keyboard-activatable (native `<button>` semantics preserved).

---

### User Story 4 - Sign-in returns the user to where they were (Priority: P2)

A user gated out of `/alerts` (or any protected route) is sent to `/auth/signin?redirect=/alerts&upgrade=true` (`protected-route.tsx:41-45`); after signing in they return to `/alerts`, not the generic `/`.

**Why P2**: Follow-on F2. Fixing the nav makes `/alerts` reachable (it is `requireUpgraded`, `alerts/layout.tsx:18`), so an anonymous user clicking Alerts now hits the redirect — and today `/auth/signin` drops the param, stranding them at `/`. Correctness follow-through, not the acute blocker.

**Acceptance Scenarios**:
1. **Given** an anonymous user clicks Alerts, **When** `ProtectedRoute` redirects to signin with `?redirect=/alerts`, **Then** after successful sign-in the app routes to `/alerts` (the origin), not `/`.
2. **Given** a `redirect` param that is not a safe same-origin path, **When** post-login routing resolves it, **Then** it is rejected and falls back to `/` (no open redirect).
3. **Given** no `redirect` param, **When** the user signs in, **Then** behavior is unchanged (routes to `/`).

---

### User Story 5 - Mobile swipe / indicator navigation is honest (Priority: P3)

Mobile swipe gestures and the `ViewIndicator` dots either navigate for real (client-side route) or are removed — never silently dead.

**Why P3**: Follow-ons F4/F5/F7. Not the acute blocker; but leaving a store-only swipe that appears to navigate is the same class of defect and confuses mobile users. Scope choice (route vs retire) is pinned in Clarifications Q4.

**Acceptance Scenarios**:
1. **Given** the mobile swipe gesture, **When** the implementer keeps it, **Then** completing a swipe client-side routes to the adjacent route; **or** if scoped out, the gesture/indicator is removed so nothing appears interactive-but-dead.
2. **Given** the `DesktopHeader` title, **When** on any route, **Then** the title matches the URL (F6), not a stale `currentView`.

---

### Edge Cases

- Deep-link directly to `/settings` (cold store): highlight must derive from the URL, not the persisted `currentView` (`view-store.ts:180`). Persisted `currentView` disagreeing with the URL MUST resolve in favor of the URL.
- Clicking the already-active nav item: no-op, no duplicate history entry, no error.
- Operator user: the Admin `<Link>` (`desktop-nav.tsx:107`, `mobile-nav.tsx:130`) already routes on `usePathname` — the fix must bring the four primary items to this exact pattern WITHOUT regressing Admin.
- `redirect` param carrying an absolute URL or `//evil.com`: treat as unsafe → fall back to `/` (US4 AC-2).
- Anonymous user on `/settings` clicking Upgrade Now while a session restore is mid-flight: routing must not depend on auth state; `/auth/signin` is reachable regardless.
- Interaction with 1384: if 1384 has NOT landed, a genuine F5 can still flip to Guest; this feature only removes the app's self-inflicted reloads. State that boundary in verification so the two aren't conflated.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Clicking or keyboard-activating any primary nav item (Dashboard, Configurations, Alerts, Settings), desktop and mobile, MUST perform a **client-side** route change to that item's route (`/`, `/configs`, `/alerts`, `/settings`) via Next.js routing (`<Link>` or `router.push`), NOT `window.location.href`.
- **FR-002**: The active-highlight of each nav item MUST derive from the current route (`usePathname`), so exactly one item is highlighted and it always matches the URL — including after a deep-link/reload. It MUST NOT derive from persisted `view-store.currentView`.
- **FR-003**: The `user-menu.tsx` navigations that today use `window.location.href` — Settings (`:142`), and the two sign-in entries (`:49`, `:131`) — MUST use client-side routing so opening them does not wipe the memory-only auth store (fixes the Guest/Anonymous flash). Any other in-app `window.location.href` that navigates within the SPA (`auth-degradation-toast.tsx:29`; `lib/api/errors.ts:45`) MUST be audited and converted to client-side routing unless a full reload is deliberately required (justify per call site).
- **FR-004**: The Settings "Upgrade Now" button (`settings/page.tsx:137`) MUST navigate an anonymous user to `/auth/signin` via client-side routing on click. It MUST remain gated to `isAnonymous` (`:127`). `useTierUpgrade` and any billing/checkout route MUST NOT be used.
- **FR-005**: `/auth/signin` MUST read a `redirect` query param and, after a successful sign-in (magic-link verify AND OAuth callback), route the user to that path. The post-login redirect MUST be validated as a **safe same-origin relative path** (starts with a single `/`, not `//`, no scheme/host); anything else falls back to `/`. When absent, behavior is unchanged (route to `/`).
- **FR-006**: Every nav control MUST be keyboard operable (Enter/Space) and expose an accessible name plus `aria-current="page"` on the active item that tracks the route (WCAG 2.1.1, 4.1.2). Desktop nav MUST gain the focus-visible ring the mobile nav already has.
- **FR-007**: The `DesktopHeader` title (`desktop-nav.tsx:142-151`) MUST reflect the current route, not `view-store.currentView`.
- **FR-008**: Mobile swipe navigation (`use-gesture.ts:208`, `useSwipeNavigation`) and the `ViewIndicator` dots (`swipe-view.tsx:169-171`) MUST either (a) perform a real client-side route change, or (b) be removed, per the decision recorded in Clarifications Q4 — they MUST NOT remain store-only "dead" interactions.
- **FR-009**: The `view-store`/`SwipeView`/`SwipeContainer` subsystem MUST be reconciled: either retired, or demoted to a pure animation/gesture layer whose `currentView` is a mirror of the route (never the navigation authority). No nav decision may depend on persisted `currentView`.
- **FR-010**: The Admin operator link and existing gesture/pull-to-refresh animation behavior MUST NOT regress.
- **FR-011**: New regression tests MUST assert **behavior**, not presence: nav click → route change (not `setView`); Upgrade Now click → `/auth/signin`; post-login → honored `redirect`. The existing presence-only checks (`settings.spec.ts:83-86`) MUST be upgraded to click+assert-navigation.
- **FR-012**: No new AWS resources; change is frontend-only (`frontend/`). No backend/API Gateway/HTMX-admin/infra change.

### Non-Functional Requirements

- **NFR-001 (a11y)**: Controls stay native/`<Link>` with button/link semantics; no bare `<div onClick>`; focus rings on all.
- **NFR-002 (least diff)**: Smallest correct change per file; no gratuitous refactor of unrelated card/layout markup. The `view-store` reconciliation (FR-009) is the one intentional structural change and MUST be justified in the plan.
- **NFR-003 (two-dashboard hazard)**: All work in `frontend/`; verify on the Amplify URL, never the Lambda Function URL / HTMX dashboard.
- **NFR-004 (coordination)**: `user-menu.tsx` is edited by this feature (nav) AND 1380 (avatar); `auth-store.ts` is edited by 1380/1384, NOT this feature. Keep this feature's diff out of `auth-store.ts` entirely; keep the `user-menu.tsx` nav hunks separable from 1380's avatar hunks (see `research.md §5`).

### Key Entities

- **Nav destination**: `{ label, icon, route }` for the four primary items + Admin — single source of truth for what each control targets.
- **Active route**: `usePathname()` — drives highlight, `aria-current`, and header title.
- **Session identity (memory-only)**: authenticated user in `auth-store` (no persistence, `auth-store.ts:71`); survives client-side routing, destroyed by a hard reload.
- **`redirect` param**: safe same-origin relative path threaded from `ProtectedRoute` → signin → post-login route.

## Success Criteria *(mandatory)*

- **SC-001**: From `/settings`, 100% of clicks on Dashboard/Configurations/Alerts change route + content with **zero** full-page reloads (client-side route confirmed via no document navigation / no re-init of `SessionProvider`).
- **SC-002**: The highlighted nav item and the `DesktopHeader` title match the URL on 100% of routes, including after a direct deep-link/reload onto `/settings`.
- **SC-003**: Opening Settings and clicking through the nav shows the signed-in Google identity with **zero** transient "Anonymous/Guest" frames for an already-authenticated user (no reload → no re-restore).
- **SC-004**: An anonymous user clicking "Upgrade Now" lands on `/auth/signin` (client-side); a test fails if the handler is removed or uses `window.location.href`.
- **SC-005**: After sign-in from a `?redirect=/alerts` flow, the user lands on `/alerts`; unsafe `redirect` values (`//evil.com`, `https://evil.com`, `/\evil`) fall back to `/` (unit-tested).
- **SC-006**: Every nav control is keyboard-operable (Enter/Space) and exposes `aria-current` on the active item; Admin link + gesture/pull-to-refresh animations show no regression.
- **SC-007**: Frontend-only diff; no new resources; `auth-store.ts` untouched by this feature; verified on the Amplify origin.

## Assumptions

- `/`, `/configs`, `/alerts`, `/settings` are real Next.js routes (verified: `app/(dashboard)/`).
- `SwipeView`/`SwipeContainer` are unmounted (verified grep) — retiring or demoting them changes no rendered content.
- Owner performs interactive Google login for the identity-preservation verification (Google consent cannot be automated).
- A genuine browser F5 reload still relies on Feature 1384 to avoid the clobber-guest flip; this feature does not claim to fix that path.

## Out of Scope

- The HTMX admin dashboard (`src/dashboard/`).
- Feature 1384's auth-store single-flight / anon-mint / backend no-clobber work (separate feature; this feature does not edit `auth-store.ts`).
- Feature 1380's avatar surfacing (separate; only overlaps on `user-menu.tsx` render hunks).
- Rewording the "Upgrade Now" label (copy decision; deferred to owner).
- Adding new protected routes or changing `ProtectedRoute`'s gate logic beyond honoring `redirect`.

---

## Adversarial Review #1

Attacked as a skeptical staff engineer, an a11y auditor, a security reviewer (open redirect), and a 3am on-call. All CRITICAL/HIGH self-resolved inline by editing the spec above.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | CRITICAL | **Merging 1385+1386 could smuggle in 1384's auth work and cause conflicting `auth-store.ts` edits.** If this feature "fixes the Guest flash" by touching the mint/restore logic, it collides head-on with 1384. | Scoped hard: FR-003/NFR-004/SC-007 forbid any `auth-store.ts` edit here. The Guest flash is fixed purely by removing the self-inflicted reload (client-side routing), never by changing session logic. 1384 owns the F5 path. `research.md §5` documents the shared-file boundary. |
| 2 | CRITICAL | **Open redirect via the new `redirect` param.** Honoring `?redirect=` naively (`router.push(redirect)`) lets `//evil.com` or `https://evil.com` become an open redirect after login. | FR-005 + SC-005 require validation to a safe same-origin **relative** path (single leading `/`, not `//`, no scheme/host); unsafe → `/`. Enumerated attack strings unit-tested. |
| 3 | HIGH | **A naive "add router.push" leaves the highlight wrong.** Highlight derives from persisted `currentView` (`desktop-nav.tsx:64`, `view-store.ts:180`), which disagrees with the URL after deep-link/reload — a real second defect. | FR-002 + SC-002 require highlight (and header title, F6/FR-007) to derive from `usePathname`, matching the working Admin link (`desktop-nav.tsx:113`). |
| 4 | HIGH | **Fixing only `:142` leaves other hard-navs wiping the store.** `user-menu.tsx:49/131`, `auth-degradation-toast.tsx:29`, `errors.ts:45` also full-reload. | FR-003 folds all in-SPA `window.location.href` into scope with a per-call-site justify-or-convert rule. |
| 5 | HIGH | **Making the nav work newly exposes `/alerts`'s `requireUpgraded` redirect, which drops `redirect` → user stranded at `/`.** The dead nav was hiding this. | US4 + FR-005 pull the signin redirect-param handling into scope precisely because the nav fix surfaces it (`alerts/layout.tsx:18`, `protected-route.tsx:41-45`, signin reads no params). |
| 6 | HIGH | **Retiring `view-store` could break mobile swipe / pull-to-refresh animations that also read it** (`use-gesture.ts`, `pull-to-refresh.tsx`, `bottom-sheet.tsx`). | FR-009 demotes `view-store` to a pure animation/gesture layer (or retires nav-authority only); FR-010 + SC-006 guard gesture/pull-to-refresh from regression. FR-008/Q4 pin the swipe decision. |
| 7 | MED | **"No reload" is hard to assert.** "Guest flash" is subjective. | SC-001/SC-003 pin it to "no document navigation / no `SessionProvider` re-init" and "zero transient Anonymous frames," both observable (network has no new document; auth store identity unchanged). |
| 8 | MED | **Upgrade Now could be mis-wired to `useTierUpgrade`.** "Upgrade" reads as billing. | FR-004 forbids `useTierUpgrade`/billing routes; destination fixed as `/auth/signin`; rationale cited (prompt copy, `useIsUpgraded`). |
| 9 | MED | **`aria-current` + `<Link>` swap could drop the Framer `layoutId` active-indicator animation.** | NFR-002/FR-010: keep the `layoutId` indicator; `<Link>` wraps the same inner markup. Plan specifies preserving the motion element. |
| 10 | LOW | **Two-dashboard hazard.** | NFR-003 pins all work to `frontend/` + Amplify verification. |

**Post-resolution gate: 0 CRITICAL, 0 HIGH remaining.** MED/LOW captured as FRs/edge cases and carried into plan + tasks.

---

## Clarifications

Self-answered from the codebase (no human asked, per pipeline rules); ≤5; each cites evidence.

### Session 2026-07-24

- **Q1: Are the four primary destinations real routes or in-place views?**
  **A: Real Next.js routes.** `app/(dashboard)/` has `page.tsx` (`/`), `configs/`, `alerts/`, `settings/`, plus `layout.tsx`. `SwipeView`/`SwipeContainer` (the in-place mechanism) are defined but never mounted (grep = self-references). Fix = route to the pages, not mount a container. Evidence: `research.md §1`.

- **Q2: Highlight/header from the URL or from `currentView`?**
  **A: From the URL (`usePathname`).** The working Admin link already does this (`desktop-nav.tsx:113`); the broken primaries use `currentView === item.view` (`:64`) and `currentView` is persisted (`view-store.ts:180`), so it desyncs after reload. FR-002/FR-007.

- **Q3: `<Link>` or `router.push` for the primary items, and how to keep the active-indicator animation?**
  **A: `<Link>`** for the four primaries (native keyboard/`aria-current`, matches Admin), wrapping the existing Framer `motion.div layoutId` indicator so the animation is preserved. `router.push` is acceptable for imperative call sites (Upgrade Now, post-login redirect) where a click handler already exists. Evidence: `desktop-nav.tsx:80-95` indicator; `mobile-nav.tsx:80-86`.

- **Q4: What happens to `currentView` and mobile swipe/gesture navigation?**
  **A: Demote `view-store` to a pure animation/gesture layer; make the router authoritative.** Recommended concrete choice: derive highlight/title/`aria-current` from `usePathname`; convert `useSwipeNavigation` and `ViewIndicator` to `router.push` the adjacent route (keep the gesture UX but make it route). If the team prefers minimal blast radius, retire the swipe nav + `ViewIndicator` instead (they're mobile-only hints and never routed anyway). Either satisfies FR-008/FR-009; the plan makes the final call and justifies it. Evidence: `use-gesture.ts:200-218`, `swipe-view.tsx:160-183`, `view-store.ts:103-117`.

- **Q5: Must the signin redirect handling touch `auth-store.ts` (colliding with 1384)?**
  **A: No.** The `redirect` param is read in the signin page + the post-login callers (`use-auth.ts:150,168` verify/callback route, `callback:125`, `verify:30`) — all UI/routing layer. Reading/validating a query param and choosing the post-login target is orthogonal to the mint/restore logic 1384 rewrites. This feature stays out of `auth-store.ts`. Evidence: `research.md §5` file table.

**Deferred to owner (not codebase-answerable):**
- **D1**: Whether to retire the mobile swipe subsystem entirely vs. wire it to the router (Q4 offers both; owner UX preference). Non-blocking — either meets FR-008.
- **D2**: Whether "Upgrade Now" should be reworded (implies billing). Copy decision; non-blocking (carried from 1386 C5).
