# Feature Specification: Settings Dead-Nav Fix

> **SUPERSEDED (2026-07-24) by `specs/1394-frontend-routing-session/`.** Research (`specs/1394-frontend-routing-session/research.md`) confirmed this bug shares its root cause (RC-A split-brain nav + RC-B hard-nav auth wipe) and its files (`desktop-nav.tsx`, `mobile-nav.tsx`, `user-menu.tsx`) with 1386 and several follow-ons. Fixing them separately would produce conflicting edits to `user-menu.tsx` and risk a partial fix. This spec's analysis is folded verbatim into 1394 (which is authoritative); it is retained for provenance only. Do NOT implement from this file.

**Feature Branch**: `1385-settings-dead-nav`
**Created**: 2026-07-24
**Status**: Superseded by 1394 (was: Draft)
**Input**: Owner post-OAuth-login QA report — "After a signed-in (Google) user opens the Settings page, the left-hand navigation links stop working. Clicking Dashboard / Configurations / Alerts does nothing. Also noticed Settings shows 'Anonymous/Guest' while the dashboard still shows me signed in."

**Target dashboard**: CUSTOMER dashboard (Next.js in `frontend/`, Amplify `https://main.d29tlmksqcx494.amplifyapp.com/`). NOT the HTMX admin dashboard (`src/dashboard/`).

## Problem Statement

On the customer dashboard, once a user lands on the `/settings` route, the left-hand (desktop) and bottom (mobile) navigation links are unresponsive — clicking them changes nothing. The user is stranded on Settings and can only escape by editing the URL or reloading.

**Root Cause (verified against source, file:line):** The nav links are not links. Both nav components render `<button onClick={() => setView(view)}>` — they mutate an in-memory Zustand `currentView` and never invoke the Next.js router:

- `frontend/src/components/navigation/desktop-nav.tsx:37-41` — `handleNavClick` calls only `setView(view)`.
- `frontend/src/components/navigation/desktop-nav.tsx:63-101` — nav items are `<button>` elements; the four primary items have no `href` and no `router.push`.
- `frontend/src/components/navigation/mobile-nav.tsx:35-39` — identical `setView`-only handler.
- `frontend/src/stores/view-store.ts:82-101` — `setView` updates `currentView`/animation state and a 300ms timer. No routing side effect.

`currentView` was designed to drive an in-place, swipeable view container (`frontend/src/components/navigation/swipe-view.tsx` — `SwipeView`/`SwipeContainer`), but those components are **defined and never mounted** anywhere in the app (grep: only self-references in `swipe-view.tsx`). Meanwhile the real content is served by Next.js file routing: `/` (dashboard), `/configs`, `/alerts`, `/settings` all exist as separate route pages under `frontend/src/app/(dashboard)/`. Nothing bridges `currentView` → the router, so clicking a nav item only re-paints the active-highlight and never leaves the current route.

The reason the bug surfaces specifically *on Settings* is that `/settings` is the one sub-route users actually land on: `frontend/src/components/auth/user-menu.tsx:142` navigates there with `window.location.href = '/settings'` (a full-page load). Once on that distinct route, the state-only nav cannot take the user anywhere else. On the root `/` the defect is latent (the user is already on the only route the nav "targets").

**Shared cause with the reported Guest/Anonymous flash:** the same `window.location.href = '/settings'` hard navigation (`user-menu.tsx:142`) tears down all in-memory React/Zustand state. The auth store is deliberately memory-only — `persist()` was removed for security (`frontend/src/stores/auth-store.ts:6,71` — "Feature 1165: Memory-only store"). So the hard nav wipes the authenticated identity, and Settings re-initializes from scratch (anonymous) until the session is re-restored, while the still-open dashboard shows signed-in. Replacing the hard navigation with client-side routing fixes both symptoms at once.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Signed-in user navigates out of Settings (Priority: P1)

A signed-in (Google OAuth) user opens Settings from the user menu, then clicks a left-nav item (Dashboard / Configurations / Alerts) to leave.

**Why this priority**: This is the reported bug. The nav being dead strands the user with no visible way out — a routing + accessibility failure that blocks the whole app once Settings is reached.

**Independent Test**: On the Amplify URL, sign in, open Settings via the user menu, click each left-nav item, and confirm the route and rendered content change to the clicked destination.

**Acceptance Scenarios**:

1. **Given** a signed-in user on `/settings`, **When** they click "Dashboard" in the left nav, **Then** the app routes to `/` and renders the dashboard content.
2. **Given** a signed-in user on `/settings`, **When** they click "Configurations", **Then** the app routes to `/configs` and renders the configurations content.
3. **Given** a signed-in user on `/settings`, **When** they click "Alerts", **Then** the app routes to `/alerts` and renders the alerts content.
4. **Given** a user on any route, **When** they read the nav, **Then** exactly one nav item is highlighted and it matches the current route (URL).

---

### User Story 2 - Keyboard/AT user operates the nav (Priority: P1)

A keyboard or screen-reader user tabs to a nav item on Settings and activates it with Enter/Space.

**Why this priority**: A nav that does nothing on activation is a WCAG failure (2.1.1 Keyboard, 4.1.2 Name/Role/Value, and effectively a link with no destination). The fix must keep or improve current a11y (mobile nav already handles Enter/Space at `mobile-nav.tsx:62-67`).

**Independent Test**: Tab to each nav item, press Enter, confirm the route changes; verify each item exposes an accessible name and a current/selected state that tracks the active route.

**Acceptance Scenarios**:

1. **Given** keyboard focus on a nav item, **When** the user presses Enter or Space, **Then** the app routes to that destination.
2. **Given** a screen reader on the nav, **When** it reads the active item, **Then** the active item is programmatically indicated as current (e.g., `aria-current="page"`) and matches the route.
3. **Given** focus-visible styling, **When** a nav item is focused, **Then** a visible focus ring is present (existing on mobile; must exist on desktop too).

---

### User Story 3 - Identity stays consistent across the transition (Priority: P2)

A signed-in user moves between the dashboard and Settings and sees the same identity in both places (no Guest/Anonymous flash).

**Why this priority**: Reported alongside the dead nav and shares the same hard-navigation cause. Secondary because the acute blocker is the dead nav; identity consistency is the correctness follow-through of the same fix.

**Independent Test**: Sign in, open Settings via the user menu, and confirm the account section and the nav user menu both show the Google identity without a transient "Anonymous".

**Acceptance Scenarios**:

1. **Given** a signed-in user on the dashboard, **When** they open Settings, **Then** Settings shows the signed-in Google identity, not "Anonymous/Guest".
2. **Given** the transition into Settings, **When** it happens, **Then** the authenticated in-memory session is preserved (no full-page reload that wipes it).

---

### Edge Cases

- User deep-links directly to `/settings` (fresh tab, cold store): nav must still route correctly; active-highlight must derive from the URL, not stale persisted `currentView` (`view-store.ts:180` persists `currentView`).
- Persisted `currentView` disagrees with the URL after a hard load (e.g., persisted `dashboard` but URL `/settings`): the highlighted item MUST follow the URL, and clicking any item MUST route.
- Operator user: the Admin link already uses `<Link href="/admin/chaos">` and `pathname` for active state (`desktop-nav.tsx:107-120`) — it works; the fix must bring the four primary items to this same pattern without breaking Admin.
- Rapid clicks / clicking the already-active item: activating the current route is a no-op (no error, no duplicate history entry).
- Swipe gestures (mobile): `swipe-view.tsx` and `use-gesture.ts` call `setView`; if `currentView` is repurposed to mirror the route, gesture navigation must also route (or be scoped out — see Clarifications Q4).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Clicking or keyboard-activating any primary left-nav item (Dashboard, Configurations, Alerts, Settings) MUST perform a client-side route change to that item's route (`/`, `/configs`, `/alerts`, `/settings`).
- **FR-002**: Nav navigation MUST use Next.js client-side routing (`<Link>` or `router.push`), NOT `window.location.href`, so in-memory session/state is preserved across the transition.
- **FR-003**: The active-highlight state of each nav item MUST be derived from the current route (`usePathname`), so exactly one item is highlighted and it always matches the URL.
- **FR-004**: The mobile bottom nav MUST route identically to the desktop nav (same four destinations, same client-side routing).
- **FR-005**: The entry point into Settings (`user-menu.tsx:142`) MUST use client-side routing rather than `window.location.href`, so opening Settings does not wipe the authenticated in-memory session (fixes the Guest/Anonymous flash).
- **FR-006**: Each nav item MUST be keyboard operable (Enter/Space) and expose an accessible name and a programmatic current/selected indication that tracks the active route (WCAG 2.1.1, 4.1.2).
- **FR-007**: The Admin operator link and mobile swipe/gesture behavior MUST continue to function (no regression) after the nav is rewired.
- **FR-008**: No new AWS resources; change is frontend-only.

### Key Entities

- **Nav destination**: a mapping of `{ label, icon, route }` for the four primary items plus the operator Admin item; the single source of truth for what each nav control targets.
- **Active route**: the current pathname (`usePathname`), which drives highlight and current-state ARIA.
- **Session identity (memory-only)**: the authenticated user held in `auth-store` (no localStorage persistence, `auth-store.ts:71`); must survive a route transition, which client-side routing guarantees and a hard load does not.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From `/settings`, 100% of clicks on Dashboard/Configurations/Alerts change the route and rendered content to the clicked destination.
- **SC-002**: The highlighted nav item matches the current URL on 100% of routes, including after a direct deep-link/reload onto `/settings`.
- **SC-003**: Opening Settings from the user menu shows the signed-in identity with zero transient "Anonymous/Guest" frames for an already-authenticated user.
- **SC-004**: Every nav item is operable by keyboard (Enter/Space) and exposes a current/selected state to assistive tech.
- **SC-005**: Admin operator link and mobile swipe navigation show no regression.

---

## Adversarial Review #1

Attacked spec.md for scope, testability, feasibility, missing failure modes, and accessibility.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | CRITICAL | **Root cause asserted without proof would make the whole spec a guess.** | Root cause is proven against source with file:line: `setView`-only handlers (`desktop-nav.tsx:37-41`, `mobile-nav.tsx:35-39`), no `router.push` in either nav (grep: "NO router.push in either nav"), unused `SwipeView`/`SwipeContainer` (`swipe-view.tsx`), and the hard-nav entry point (`user-menu.tsx:142`). Verified, not hypothesized. |
| 2 | HIGH | **A11y failure not first-class** — a nav that does nothing on activation is the core WCAG defect, yet an early draft treated it as cosmetic. | Added US2 (keyboard/AT) and FR-006 with WCAG 2.1.1 / 4.1.2 mapping and `aria-current` for the active item. Desktop nav currently lacks the Enter/Space handler and focus-visible ring the mobile nav has (`mobile-nav.tsx:62-72`); `<Link>` restores native keyboard semantics. |
| 3 | HIGH | **Highlight/URL desync missed.** `isActive` derives from persisted `currentView` (`desktop-nav.tsx:64`), which can disagree with the URL after a hard load — a real second defect that would survive a naive "just add router.push" fix. | FR-003 + SC-002 require highlight to derive from `usePathname` (matching how the working Admin link already behaves, `desktop-nav.tsx:113`). Edge case added. |
| 4 | HIGH | **Fixing nav but leaving `window.location.href` would leave the Guest flash unfixed** and re-wipe session on every Settings open. | FR-005 + US3 fold the `user-menu.tsx:142` hard-nav into scope; it shares the root cause. Tied to the memory-only store evidence (`auth-store.ts:71`). |
| 5 | MED | **Repurposing `currentView` could break mobile swipe/gestures** (`swipe-view.tsx`, `use-gesture.ts` call `setView`). | FR-007 requires no gesture regression; Clarifications Q4 records the chosen approach (keep `currentView` as a route mirror OR drop it) so the implementer is not left guessing. |
| 6 | MED | **Testability of "no Guest flash"** — "flash" is subjective. | SC-003 pins it to "zero transient Anonymous frames for an already-authenticated user"; verifiable by asserting no full-page load occurs on the transition (client-side route) and identity is unchanged. |
| 7 | LOW | **Configs/Alerts routes may be otherwise unreachable via UI**, hinting the nav has been latently broken beyond Settings. | Noted in Problem Statement (latent on `/`); scope stays on the reported symptom while the fix (real routing) incidentally makes all four destinations reachable. No scope creep. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** Root cause is source-verified; a11y is first-class (US2/FR-006); the two silent second-defects (highlight desync, hard-nav Guest flash) are pulled into scope (FR-003, FR-005); gesture regression is guarded (FR-007) with the approach pinned in Clarifications.

## Clarifications

Self-answered from the codebase; each cites evidence. Genuinely unanswerable items are deferred.

- **Q1: Are `/configs`, `/alerts`, `/settings` real Next.js routes, or in-place views?**
  **A:** Real routes. `frontend/src/app/(dashboard)/` contains `configs/`, `alerts/`, `settings/`, plus root `page.tsx` and `layout.tsx`. The `SwipeView`/`SwipeContainer` in-place mechanism (`swipe-view.tsx`) is defined but never mounted (grep found only self-references). So the fix is "make nav route to these pages," not "mount a view container."

- **Q2: How is `/settings` currently reached, and why is the bug Settings-specific?**
  **A:** Via `user-menu.tsx:142` `window.location.href = '/settings'` (hard load). It's the one distinct sub-route users land on; the nav's `setView`-only handlers can't leave it. On `/` the defect is latent because the user already occupies the nav's implicit target.

- **Q3: Should active-state come from the URL or from `currentView`?**
  **A:** From the URL. The already-working Admin link uses `pathname?.startsWith('/admin')` for active state (`desktop-nav.tsx:113`), while the broken primary items use `currentView === item.view` (`desktop-nav.tsx:64`). Aligning the primaries to `usePathname` fixes both routing and the highlight/URL desync (FR-003).

- **Q4: What happens to `currentView` and the mobile swipe/gesture system?**
  **A:** Recommended: keep `view-store` as the animation/gesture layer but make navigation authoritative on the router — either (a) drive nav via `<Link>`/`router.push` and derive `currentView`/highlight from `pathname`, letting gesture handlers also `router.push`, or (b) if gestures are out of scope, leave `swipe-view.tsx` untouched (it's unmounted anyway) and only rewire the two nav components + user-menu. `use-gesture.ts:208` (`navigateLeft/Right`) currently only mutates `currentView`, so gestures are already non-routing today; the fix must not silently claim to fix them unless it wires them to the router (FR-007 guards regression, not new capability).

- **Q5: Is a hard reload ever required when entering Settings (e.g., to force session re-read)?**
  **A:** No evidence of intent. `auth-store` is memory-only by design (`auth-store.ts:6,71`); a hard load actively destroys the session it should preserve. Client-side routing is the correct behavior. (Deferred/unanswerable: whether the original author used `window.location.href` deliberately for some cache-busting reason — no comment or commit rationale found; treat as an accidental anti-pattern unless the owner knows otherwise.)
