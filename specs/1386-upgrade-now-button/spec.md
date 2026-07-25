# Feature 1386 — upgrade-now-button

> **SUPERSEDED (2026-07-24) by `specs/1394-frontend-routing-session/`.** The correct fix (navigate to `/auth/signin` via the router, not `window.location.href`) shares root cause RC-B and the file surface with 1385. See `specs/1394-frontend-routing-session/research.md §6` for the merge justification. Folded into 1394 (authoritative) as User Story 3. Retained for provenance only; do NOT implement from this file.

**Status:** Superseded by 1394 (was: Draft — planning-only; no implementation)
**Branch:** current worktree (no new branch)
**Type:** Bug fix — Frontend-only (Next.js / React, customer dashboard)
**Target:** CUSTOMER dashboard (`frontend/`, Next.js on Amplify — `https://main.d29tlmksqcx494.amplifyapp.com/`). NOT the HTMX admin dashboard (`src/dashboard/`).
**Created:** 2026-07-24

---

## 1. Problem Statement

An anonymous ("Guest") user on the customer dashboard opens **Settings**. Because their session
is anonymous, an upgrade prompt renders with an **"Upgrade Now"** button. Clicking it does
**nothing** — no navigation, no modal, no network request, no console error. The owner reported
this during post-OAuth-login QA.

### Root cause (verified from code, not inferred)

The button is rendered with **no `onClick` handler** — it is inert by construction.

- `frontend/src/app/(dashboard)/settings/page.tsx:137-140`:
  ```tsx
  <Button size="sm" className="gap-2">
    <Mail className="w-4 h-4" />
    Upgrade Now
  </Button>
  ```
  No `onClick`, no `asChild`+`<a>`, no form submit. `Button` (`frontend/src/components/ui/button.tsx:44-52`)
  is a plain `forwardRef` `<button>` that spreads `...props`; with no handler passed it renders a
  functioning-but-do-nothing button. Clicking fires no behavior.

- Contrast with the sibling that **works**: the user menu's anonymous item navigates on select —
  `frontend/src/components/auth/user-menu.tsx:128-136` (`onSelect={() => { window.location.href = '/auth/signin'; }}`),
  and the top-level "Sign in" button at `user-menu.tsx:44-54` (`onClick={() => (window.location.href = '/auth/signin')}`).
  The Settings button simply never got the same wire-up.

### What "Upgrade" means here (disambiguation)

In this app **"upgrade" = converting an anonymous/guest session into a real authenticated account**,
NOT a free→paid billing upgrade:

- The prompt's own copy: *"Sign in with email or social to unlock all features and save your data
  across devices."* (`settings/page.tsx:133-136`) — this is a sign-in call to action.
- The guard `useIsUpgraded()` (`frontend/src/hooks/use-auth.ts:203`) defines "upgraded" as
  "upgraded from anonymous", and `ProtectedRoute` gates non-anonymous routes with
  `?upgrade=true` (`frontend/src/components/auth/protected-route.tsx:42-43`).
- The prompt only renders when `isAnonymous` is true (`settings/page.tsx:127`).

**Therefore the correct action is: navigate the user to the sign-in page (`/auth/signin`).**

### Not the fix: `useTierUpgrade`

`frontend/src/hooks/use-tier-upgrade.ts` (Feature 1191) is **unrelated**. It polls the profile
after a **Stripe payment** to detect `role === 'paid'` (line 92); it has no "start checkout"
entry point and nothing to do with anonymous→authenticated conversion. No Stripe/checkout
initiation flow exists anywhere in `frontend/src` (grep: only the post-webhook poller). Wiring this
hook to the button would be wrong. This is recorded so implementation does not chase it.

### Why QA/tests didn't catch it

`frontend/tests/e2e/settings.spec.ts:83-86` asserts only that the "Upgrade Now" button is
**present** (`getByRole('button', { name: /upgrade now/i })`) — it never clicks it or asserts a
navigation. A present-but-inert button passes. No unit test covers the handler.

---

## 2. Scope

**In scope**
- Wire the Settings "Upgrade Now" button so clicking it navigates the anonymous user to the
  sign-in page (`/auth/signin`), matching the established auth-navigation pattern in `user-menu.tsx`.
- Add a regression test that asserts the **click behavior** (navigation), not mere presence.

**Out of scope**
- Any free→paid / Stripe billing flow, `useTierUpgrade`, or checkout initiation (none exists).
- Renaming the button or rewording the prompt copy (kept as-is).
- Making the sign-in page honor a `redirect`/return-to param (the signin page currently ignores
  query params — separate pre-existing gap; see Clarifications C4).
- Any backend, API Gateway, HTMX admin dashboard, or infra change.
- The user-menu's own "Sign in with email" item (already works).

---

## 3. User Scenarios

### US-1 (Primary) — Guest clicks Upgrade Now
**As** an anonymous ("Guest") user, **when** I open Settings and click **Upgrade Now**,
**then** I am taken to `/auth/signin` where I can sign in with email or a social provider.

**Acceptance:**
- Clicking the button navigates the browser to `/auth/signin`.
- The sign-in page renders (magic-link form + any configured OAuth buttons).
- No console error; the button is keyboard-activatable (Enter/Space) since it is a real `<button>`.

### US-2 — Behavior matches the user menu
**As** a user, **when** I compare the Settings "Upgrade Now" button and the user-menu
"Sign in with email" item, **then** both take me to the same `/auth/signin` destination
(consistent auth-entry behavior across the app).

### US-3 — Regression is guarded
**As** a maintainer, **when** the button's handler is later removed or mis-wired,
**then** an automated test fails because it asserts the **navigation on click**, not just that the
button exists.

---

## 4. Functional Requirements

- **FR-001** The Settings "Upgrade Now" button (`settings/page.tsx:137`) MUST invoke a navigation to
  `/auth/signin` when clicked (via `onClick`).
- **FR-002** The navigation MUST use the app's established auth-entry pattern. Primary choice:
  `useRouter().push('/auth/signin')` from `next/navigation` (SPA nav; Settings is already a
  `'use client'` component). Using `window.location.href = '/auth/signin'` — identical to
  `user-menu.tsx:49/131` — is an acceptable equivalent (see Plan for the decision + rationale).
- **FR-003** The destination MUST be `/auth/signin` (the customer sign-in page,
  `frontend/src/app/auth/signin/page.tsx`), NOT a billing/checkout route (none exists) and NOT the
  HTMX admin dashboard.
- **FR-004** The button MUST remain rendered **only** for anonymous users (existing `isAnonymous`
  gate at `settings/page.tsx:127` unchanged). No behavior change for authenticated users.
- **FR-005** No new dependency, hook, store, route, or component is required. The change is confined
  to `settings/page.tsx` (handler wire-up) plus test files. `useTierUpgrade` MUST NOT be used.
- **FR-006** A regression test MUST assert the **click → navigation** behavior (mock the router or
  `window.location`), replacing the presence-only assertion gap. The existing e2e presence check
  (`settings.spec.ts:83-86`) MAY be extended to click and assert URL `/auth/signin`.

## 5. Non-Functional Requirements

- **NFR-001 (Accessibility)** The control stays a native `<button>` (keyboard/Enter/Space, focus
  ring) — no regression from the current `Button`. Do not swap to a bare `<a>` styled as a button
  in a way that loses button semantics.
- **NFR-002 (No infra / no backend)** Frontend-only; zero new AWS resources; standing "no new AWS
  resources" constraint honored.
- **NFR-003 (Least diff)** Smallest correct change: add a handler (and, if using `useRouter`, one
  import + hook call). No refactor of the surrounding card/prompt.
- **NFR-004 (Two-dashboard hazard)** All work in `frontend/`; verify on the Amplify URL, never the
  Lambda Function URL / HTMX dashboard.

## 6. Success Criteria

1. On the Amplify customer dashboard, an anonymous user clicking **Upgrade Now** in Settings lands
   on `/auth/signin`.
2. Authenticated users see no change (prompt still hidden for them).
3. A unit (and/or e2e) test asserts the click-navigation and fails if the handler is removed.
4. No console errors; button remains keyboard-accessible.
5. Frontend-only diff; no new resources; verified on the Amplify origin (not the Lambda URL).

## 7. Assumptions & Dependencies

- `/auth/signin` exists and renders (`app/auth/signin/page.tsx`, 127 lines) with magic-link + OAuth.
- The sign-in page does **not** currently consume a `redirect`/return-to query param (grep: none);
  navigating with such a param is harmless but not honored — out of scope (C4).
- `useAuth()` already exposes `isAnonymous` used by the render gate (`use-auth.ts`), unchanged.

## 8. Out-of-Scope / Deferred

- Post-sign-in return-to-Settings redirect (pre-existing signin-page gap).
- Button copy/wording ("Upgrade Now" implies billing to some readers) — left as-is; owner may
  revisit separately (see Clarifications C5, deferred).
- Any paid-tier / Stripe flow.

---

## Adversarial Review #1

**Reviewer stance:** assume the "just add an onClick" fix is wrong or incomplete. Attack scope
misread (billing vs sign-in), destination correctness, testability, and accessibility.

### Findings

| ID | Sev | Attack | Finding | Resolution |
|----|-----|--------|---------|-----------|
| H1 | HIGH | "You're fixing the wrong thing — 'Upgrade' means paid tier; wire `useTierUpgrade`." | If implementer reads "Upgrade" as billing, they'd invoke `useTierUpgrade.startPolling()` — which only **polls after a Stripe webhook** and has no checkout entry (`use-tier-upgrade.ts:65-92`). It would do nothing useful and time out. The prompt copy + `isAnonymous` gate + `useIsUpgraded` ("upgraded from anonymous") prove this is anonymous→authenticated. | **Resolved in spec:** §1 "What 'upgrade' means" + FR-003/FR-005 explicitly forbid `useTierUpgrade` and fix the destination as `/auth/signin`. |
| H2 | HIGH | "Present-only test lets the bug come back." | The only existing coverage asserts presence (`settings.spec.ts:85`), which is exactly why the inert button shipped. A fix without a behavior test leaves the regression door open. | **Resolved:** FR-006 + US-3 require a click→navigation assertion. Added as a first-class deliverable, not optional. |
| M1 | MED | "SPA push vs full reload — you'll pick the wrong one and break state." | Two valid patterns exist: `useRouter().push` (SPA) and `window.location.href` (sibling code, full reload). Ambiguity could cause churn or an inconsistent UX. | Resolved: FR-002 names `useRouter().push` as primary (SPA, no reload; Settings is already client) with `window.location.href` as an accepted equivalent matching `user-menu.tsx`. Plan makes the final call. Non-blocking either way. |
| M2 | MED | "Destination has no return path — user signs in and is stranded." | `/auth/signin` ignores redirect params today, so after sign-in the user isn't bounced back to Settings. | Acknowledged as a **pre-existing, separate** gap (C4, §8). US-1 only requires reaching the sign-in page; the return-to flow is out of scope and does not block this fix. |
| L1 | LOW | "You'll break a11y swapping to an anchor." | A tempting alt is `<Button asChild><a href>`. Done carelessly it can drop button semantics/focus. | NFR-001 keeps the native `<button>` + `onClick`. If an anchor is ever used it must preserve semantics. No change needed. |
| L2 | LOW | "Wrong dashboard again." | The four-incident two-dashboard hazard. | NFR-004 + header/target banner pin this to `frontend/` + Amplify URL. The file path `frontend/src/app/(dashboard)/settings/page.tsx` is unambiguously the Next.js app. |

### Spec edits applied
- FR-003/FR-005 hardened to explicitly exclude `useTierUpgrade` and any billing route (H1).
- FR-006 + US-3 added as required behavior test (H2).
- §8 records the signin return-to gap as deferred (M2).

### Gate
- CRITICAL: **0**
- HIGH: **0** (H1, H2 resolved inline)

**PASS — 0 CRITICAL / 0 HIGH.** Proceed to Plan.

---

## Clarifications

Self-answered from the codebase (no owner input required). Max 5.

**C1 — Is the button truly missing an `onClick`, or is a handler passed some other way?**
Resolved. `settings/page.tsx:137-140` passes only `size` + `className` to `Button`. `Button`
(`components/ui/button.tsx:44-52`) spreads `...props` onto a `<button>`; with no `onClick`/form/`asChild`
anchor, click does nothing. Confirmed inert.

**C2 — Should the button trigger sign-in or a paid-tier upgrade?**
Resolved. Sign-in (anonymous→authenticated). Evidence: prompt copy "Sign in with email or social to
unlock all features" (`:133-136`), `isAnonymous` render gate (`:127`), `useIsUpgraded` = "upgraded
from anonymous" (`use-auth.ts:203`), and no Stripe/checkout initiation exists in `frontend/src`
(grep). `useTierUpgrade` is post-payment polling only — not applicable.

**C3 — What's the correct destination route?**
Resolved. `/auth/signin` — the customer sign-in page (`app/auth/signin/page.tsx`), identical to
where `user-menu.tsx:49/131` sends anonymous users. Renders magic-link + configured OAuth providers.

**C4 — Does `/auth/signin` support returning the user to Settings after sign-in?**
Resolved. No. `signin/page.tsx` reads no `redirect`/`upgrade`/searchParams (grep = none); it only
renders the forms. So this fix gets the user to sign-in but not automatically back to Settings.
That return-to behavior is a pre-existing, separate gap — deferred (§8), not part of 1386.

**C5 — Should the label "Upgrade Now" change (it implies billing)?**
Deferred to owner. The label is arguably misleading given "upgrade" here means "make an account,"
but rewording is a copy/UX decision, not required to fix the dead button. Left as-is; owner may
revisit. Non-blocking.

**Deferred to owner:** C5 (label wording only). All functional questions resolved from code.
