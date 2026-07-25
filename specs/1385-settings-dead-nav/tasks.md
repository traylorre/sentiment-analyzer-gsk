---
description: "Task list for Settings Dead-Nav Fix (1385)"
---

# Tasks: Settings Dead-Nav Fix

**Input**: Design documents from `specs/1385-settings-dead-nav/`
**Prerequisites**: spec.md (US1–US3, FR-001..FR-008, SC-001..SC-005), plan.md (root cause + approach A1–A5)

**Tests**: Vitest unit for nav render / active-state / keyboard; Playwright E2E on the Amplify customer URL for the reported symptom. Root cause is source-verified — no diagnostic-first task needed.

**Two-dashboard guard**: All work targets the **Customer Dashboard** (`frontend/`). Do NOT touch `src/dashboard/` (HTMX admin). Verify on `https://main.d29tlmksqcx494.amplifyapp.com/`, NOT the Lambda Function URL.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (or SETUP/FOUND/POLISH)

---

## Phase 1: Setup

- [ ] T001 [SETUP] Open and re-read the cited lines: `frontend/src/components/navigation/desktop-nav.tsx:37-41,63-101,113`, `mobile-nav.tsx:35-39`, `frontend/src/stores/view-store.ts:82-101,180`, `frontend/src/components/auth/user-menu.tsx:142`, `frontend/src/stores/auth-store.ts:71`. Confirm the four `(dashboard)` routes exist. `cd frontend && npm install` if needed.
- [ ] T002 [SETUP] Reproduce on the Amplify URL: sign in, open Settings via the user menu, click each left-nav item, confirm nothing routes (baseline). Note whether a "Anonymous/Guest" frame appears on entry (US3 baseline).

---

## Phase 2: Foundational (Blocking) — Shared destination map

**Blocks US1/US2 rewrites (both nav files consume it).**

- [ ] T003 [FOUND] (FR-001, A1) Define a single source-of-truth nav destination model `{ view, label, icon, route }` with routes `dashboard→'/'`, `configs→'/configs'`, `alerts→'/alerts'`, `settings→'/settings'`. Place it where both `desktop-nav.tsx` and `mobile-nav.tsx` can import it (e.g., a shared `nav-items.ts` in `components/navigation/`) to prevent desktop/mobile drift.
- [ ] T004 [FOUND] (FR-003, A3, AR#2 #3) Add a pure `isRouteActive(pathname, route)` helper: exact match for `'/'`, `startsWith` for the others (matching the Admin link's `startsWith('/admin')` pattern but root special-cased). Unit-test it (root does NOT match `/configs`, `/settings` matches `/settings`).

**Checkpoint**: Shared destinations + active-state helper exist and are tested.

---

## Phase 3: User Story 1 — Nav routes out of Settings (P1) 🎯 MVP

**Goal**: Every primary nav item performs a client-side route change; highlight follows the URL.

**Independent Test**: On Amplify, from `/settings`, click Dashboard/Configurations/Alerts → route + content change; highlighted item matches URL.

### Tests for User Story 1

- [ ] T005 [P] [US1] Vitest in `frontend/tests/unit/` (or `src` co-located): render `DesktopNav`, mock `usePathname` → `/settings`, assert Settings item is active and the others are not; assert each primary item renders as a link/has a click handler that targets its route. Covers FR-001, FR-003.
- [ ] T006 [P] [US1] Vitest for `MobileNav`: same assertions for the bottom nav. Covers FR-004.

### Implementation for User Story 1

- [ ] T007 [US1] (FR-001, FR-002, A2) In `desktop-nav.tsx`, convert the four primary `<button onClick={() => setView(view)}>` (lines ~63-101) to client-side routing via `<Link href={route}>` (preferred) or `router.push(route)`. Preserve the framer-motion `layoutId="desktop-nav-bg"/"desktop-nav-indicator"` highlight markup (AR#2 #1) — do not drop the animation.
- [ ] T008 [US1] (FR-003, A3, AR#2 #1) In `desktop-nav.tsx`, compute `isActive` for all four items from `usePathname` via `isRouteActive` (T004), replacing `currentView === item.view` (line 64). Single active source for all items — no mixing with `currentView`.
- [ ] T009 [US1] (FR-004, FR-002) In `mobile-nav.tsx`, apply the identical rewrite: primary items route client-side; `isActive` from `usePathname`. Keep the existing Enter/Space handler intent (native `<Link>` gives it for free).
- [ ] T010 [US1] (FR-007, AR#2 #2, #5) Do NOT modify `swipe-view.tsx`. If `currentView` is mirrored from `pathname` for animation coherence, ensure a mirroring effect does not fight gesture `setView` calls (`use-gesture.ts:208`); if in doubt, leave `currentView` independent and drive nav purely from the router. Record the decision in a code comment.
- [ ] T011 [US1] Run `cd frontend && npm run typecheck` and unit tests; `npm run build` to catch App Router link issues.

**Checkpoint**: From `/settings`, all nav items route; highlight matches URL (SC-001, SC-002).

---

## Phase 4: User Story 2 — Keyboard / AT operability (P1)

**Goal**: Nav is fully keyboard operable with correct current-state semantics.

**Independent Test**: Tab to each nav item, press Enter → routes; screen reader announces the active item as current.

- [ ] T012 [US2] (FR-006) Ensure each primary item exposes an accessible name and `aria-current="page"` when active (native for `<Link>`; add `aria-current` explicitly). Verify desktop items get a visible focus-visible ring (mobile already has one at `mobile-nav.tsx:72`); add matching focus styling to desktop if `<Link>` doesn't inherit it.
- [ ] T013 [P] [US2] Vitest: focus a nav item, fire `keydown` Enter → assert navigation intent (link href present / router.push called); assert `aria-current` on the active item only. Covers SC-004.

**Checkpoint**: Keyboard + AT operate the nav; current state is programmatic.

---

## Phase 5: User Story 3 — Identity consistency (no Guest flash) (P2)

**Goal**: Opening Settings preserves the in-memory authenticated session.

**Independent Test**: Signed-in user opens Settings from the user menu → no "Anonymous/Guest" frame; account section shows the Google identity.

- [ ] T014 [US3] (FR-005, A4, AR#2 #4) In `user-menu.tsx:142`, replace `window.location.href = '/settings'` with client-side navigation (`router.push('/settings')`; keep the Radix `DropdownMenu.Item onSelect`). Scope the change to the Settings entry only — leave the `/auth/signin` hard-nav (line 131) unless T016 shows a regression.
- [ ] T015 [US3] Playwright on Amplify: sign in (owner-assisted for Google consent), open Settings via the user menu, assert NO full-page load occurred (client route) and the account section shows the signed-in identity with zero transient "Anonymous". Covers SC-003.

**Checkpoint**: Settings shows the signed-in identity; no session wipe on entry.

---

## Phase 6: Polish & Verification

- [ ] T016 [POLISH] (FR-007, SC-005) Regression check on Amplify: operator Admin link still routes (`desktop-nav.tsx:107`, `mobile-nav.tsx:130`); mobile swipe navigation behaves as before (no new breakage). Sign-in from user menu still works.
- [ ] T017 [P] [POLISH] Full E2E: from every route, confirm the highlighted nav item matches the URL, including a direct deep-link/reload onto `/settings` (SC-002 edge case). `cd frontend && npx playwright test` against the Amplify URL.
- [ ] T018 [POLISH] `cd frontend && npm run typecheck && npm run build && npm test`; run lint. GPG-sign commits (`git commit -S`). Do NOT push/open PR — pipeline stops at planning; implementation/commit is a separate gated step.

---

## Dependencies & Execution Order

- **Setup (T001–T002)**: first.
- **Foundational (T003–T004)**: blocks all nav rewrites (shared map + active helper).
- **US1 (T005–T011)**: core MVP. T007/T008 (desktop) and T009 (mobile) depend on T003/T004; tests T005/T006 can be written first (TDD) or alongside.
- **US2 (T012–T013)**: builds on the US1 `<Link>` rewrite.
- **US3 (T014–T015)**: independent file (`user-menu.tsx`); can proceed in parallel with US1/US2 but verify after US1 so the routed Settings destination exists.
- **Polish (T016–T018)**: last; regression + full E2E + seal.

### Parallel Opportunities

- T005, T006 (different test files) in parallel.
- T014 (user-menu) parallel with T007–T009 (nav files) — different files.
- T013 (a11y unit) parallel with T015 (identity E2E).

---

## Requirement → Task Coverage (traceability)

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (nav performs route change) | T003, T005, T007, T009 |
| FR-002 (client-side routing, not window.location) | T007, T009, T014 |
| FR-003 (active state from pathname) | T004, T008, T009 |
| FR-004 (mobile nav routes identically) | T006, T009 |
| FR-005 (Settings entry preserves session) | T014, T015 |
| FR-006 (keyboard + current-state a11y) | T012, T013 |
| FR-007 (Admin + swipe non-regression) | T010, T016 |
| FR-008 (frontend-only, no new AWS) | plan Constraints Check; all tasks frontend-only |
| SC-001 (clicks route from Settings) | T007, T009, T015 |
| SC-002 (highlight matches URL incl. deep-link) | T004, T008, T017 |
| SC-003 (no Guest flash) | T014, T015 |
| SC-004 (keyboard operable) | T012, T013 |
| SC-005 (Admin + swipe no regression) | T016 |

Every FR/SC maps to ≥1 task. Every task traces to a requirement or an explicit setup/verification purpose.

---

## Adversarial Review #3

Final readiness review across spec.md, plan.md, tasks.md.

### Highest-risk task
**T007/T008 — the desktop nav rewrite while preserving the framer-motion shared-layout highlight.** Risk: an implementer swaps `<button>` for `<Link>` but drops or double-binds the `layoutId` highlight, or leaves one item's `isActive` still reading `currentView` while others read `pathname`, producing a flickering or double highlight that looks like a new bug. Mitigation baked in: T007 mandates preserving the `layoutId` markup; T008 mandates a single `pathname`-derived active source for all four items in one atomic edit; T004 gives a tested `isRouteActive` so the `'/'` always-match trap (AR#2 #3) can't ship.

### Most-likely rework
**T010 — the `currentView` / gesture interaction.** If the implementer mirrors `currentView` from `pathname` via an effect, it can overwrite a mobile swipe's `setView` (`use-gesture.ts:208`), making swipe feel dead — trading the reported desktop bug for a new mobile one. Rework path: decide up front NOT to mirror (drive nav purely from the router, leave `currentView` independent for animation), which T010 states as the safe default. The dead `swipe-view.tsx` stays untouched (spec Q1/Q4), so blast radius is contained.

### Readiness checks
- Root cause verified against source with file:line (not re-derived from the task hypothesis); confidence HIGH, no diagnostic-first task needed. ✅
- Both reported symptoms (dead nav + Guest flash) are task-covered and share one fix (client-side routing). ✅
- The silent second defect (highlight/URL desync) has dedicated tasks (T004, T008, T017). ✅
- A11y is first-class (T012, T013) — the fix restores native link keyboard semantics plus `aria-current`. ✅
- Non-regression for Admin link and mobile swipe is explicitly owned (T010, T016). ✅
- All edits under `frontend/`; verification on the Amplify URL, not the Lambda URL (Two-Dashboards rule). ✅
- No new AWS resources; frontend-only. ✅

### Gate

**READY FOR IMPLEMENTATION.**

Rationale: root cause is conclusively found and cited, the fix is small and frontend-only, every requirement is task-covered and traceable, and the two riskiest failure modes (breaking the highlight animation, trading the desktop bug for a mobile-swipe bug) are pre-mitigated with explicit decisions. No open CRITICAL/HIGH. Pipeline stops here (no `/speckit.implement`, no push).
