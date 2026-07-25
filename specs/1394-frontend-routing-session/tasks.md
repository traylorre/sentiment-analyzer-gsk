# Tasks: Router-as-Source-of-Truth (Feature 1394)

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **Research**: `./research.md`
**Scope**: Frontend-only. `[P]` = parallelizable. Every task cites the FR/SC it satisfies. Commits: GPG-signed (`git commit -S`), venv active for any pre-commit hooks that need Python 3.13.

## Phase 0 — Guards & shared helper

- **T001** `[P]` Add `frontend/src/lib/navigation.ts` exporting `safeInternalPath(raw: string | null): string` → returns a safe same-origin relative path or `/`. Reject: null/empty, not starting with a single `/`, starting `//` or `/\`, containing a scheme (`:` before first `/`), and after one `decodeURIComponent` re-check. (FR-005, SC-005)
- **T002** `[P]` Enumerate `view-store` consumers before editing: grep `useViewStore`/`view-store` — confirm `pull-to-refresh.tsx`, `bottom-sheet.tsx`, `use-gesture.ts`, nav components, `swipe-view.tsx`. Record which read `currentView` (nav-authority — to remove) vs gesture/pull/sheet state (keep). (FR-009, plan AR#2 F3)
- **T003** `[P]` Define the single nav destination map `{ label, icon, route }` for the four primaries + Admin (shared shape used by both navs). (FR-001, Key Entities)

## Phase 1 — RC-A: nav routes from the URL

- **T010** `desktop-nav.tsx`: replace the four `<button onClick>` (`:68-101`) with `<Link href={route}>` wrapping the existing `motion.div layoutId` indicator markup; `isActive` from `usePathname()`; add `aria-current={isActive?'page':undefined}` + focus-visible ring. (FR-001, FR-002, FR-006) — **verify the active-indicator still animates**; if broken, fall back to `<button onClick={()=>router.push(route)}>` (plan AR#2 F1).
- **T011** `desktop-nav.tsx` `DesktopHeader` (`:141-171`): `displayTitle` from `usePathname()` via route→title map, not `currentView`. (FR-007, SC-002)
- **T012** `mobile-nav.tsx`: same `<Link>` + `usePathname()` conversion (`:59-124`); switch ARIA from `role="tab"`/`tablist` to nav-link + `aria-current="page"` (these are real page links now, plan AR#2 F7). (FR-001, FR-002, FR-006)
- **T013** Preserve Admin `<Link>` (`desktop-nav.tsx:107`, `mobile-nav.tsx:130`) unchanged; confirm no regression. (FR-010, SC-006)

## Phase 2 — RC-B: client-side routing, no store wipe

- **T020** `user-menu.tsx`: `useRouter()`; convert `:142` (`/settings`), `:49`, `:131` (`/auth/signin`) from `window.location.href` to `router.push`. **Keep hunks separable from 1380 avatar lines `:78-80`/`:103-105`.** (FR-003, NFR-004, SC-003)
- **T021** `[P]` `settings/page.tsx`: add `useRouter()`; wire `<Button onClick={()=>router.push('/auth/signin')}>` at `:137`, keep `isAnonymous` gate `:127`; do NOT import `useTierUpgrade`. (FR-004, US3, SC-004)
- **T022** `[P]` Audit remaining in-SPA `window.location.href`: convert `auth-degradation-toast.tsx:29` → `router.push('/auth/signin')`. For `lib/api/errors.ts:45` and `sign-out-dialog.tsx:35`/`error-boundary.tsx`: record per-call-site whether the full reload is intentional (signout/crash-reset) and leave those with a justifying comment. (FR-003, plan AR#2 F4)

## Phase 3 — F2/US4: signin honors redirect

- **T030** `signin/page.tsx`: `useSearchParams().get('redirect')` → `safeInternalPath` → hold as post-login target. (FR-005, US4)
- **T031** Post-login routing at page layer: `callback/page.tsx` (`:125`) and `verify/page.tsx` (`:30`) route to the validated `redirect` (fallback `/`) instead of hardcoded `/`. Prefer page-layer reads over editing `use-auth.ts:150/168` to minimize 1384 collision. If `use-auth.ts` must change, keep it in the `:147-171` region only. (FR-005, NFR-004, SC-005)

## Phase 4 — F4/F5/F7: swipe/dots/view-store reconciliation

- **T040** `view-store.ts`: remove `currentView` from `persist` `partialize` (`:180`) so no stale nav state survives reload; retain gesture/pull/sheet state. Demote `setView` to animation-layer-only (nav no longer calls it). (FR-009, SC-002)
- **T041** Per Q4 decision: **retire `ViewIndicator` dots** (`swipe-view.tsx:160-183`; remove from `(dashboard)/layout.tsx:44-47`) AND route the swipe — `use-gesture.ts` `useSwipeNavigation` (`:204-218`) → `router.push` the adjacent route from an ordered route list. If team opts to fully retire swipe nav instead, remove `useSwipeNavigation`'s nav wiring; either satisfies FR-008. Justify the choice in the PR. (FR-008, FR-010)

## Phase 5 — Tests (behavior, not presence)

- **T050** `[P]` Unit: `safeInternalPath` allow/deny table incl. `//evil.com`, `https://evil.com`, `/\evil`, `\/\/evil`, `/%2Fevil`, `/alerts` (allow), `` (→`/`). (FR-005, SC-005, plan AR#2 F6)
- **T051** `[P]` Unit: `desktop-nav`/`mobile-nav` render `<Link href>` for each destination and set `aria-current="page"` on the item matching a mocked `usePathname`. (FR-001, FR-002, FR-006)
- **T052** `[P]` Unit: `DesktopHeader` title follows mocked `usePathname`. (FR-007)
- **T053** `[P]` Unit: Settings Upgrade Now click calls `router.push('/auth/signin')` (mock `next/navigation`); fails if handler removed or uses `window.location`. (FR-004, FR-011, SC-004)
- **T054** E2E (Playwright, Amplify — owner interactive Google login): sign in → open Settings via user menu → click each nav item → assert route+content change AND no document reload AND identity stays the Google user (zero Anonymous frame). (SC-001, SC-003)
- **T055** E2E: anonymous → click Alerts → redirected to `signin?redirect=/alerts` → sign in → lands `/alerts`. (SC-005, US4)
- **T056** Upgrade `settings.spec.ts:83-86` from presence-only to click → assert URL `/auth/signin`. (FR-011)
- **T057** Regression E2E: Admin link routes; pull-to-refresh + bottom-sheet animations unaffected. (FR-010, SC-006)

## Phase 6 — Gate

- **T060** Confirm `auth-store.ts` has ZERO changes in this feature's diff (grep the diff). (SC-007, coordination boundary with 1384)
- **T061** Confirm frontend-only diff, no new AWS resources, no `src/dashboard/` (HTMX) or backend edits. (FR-012, NFR-003)
- **T062** `cd frontend && npm run typecheck && npm test && npm run test:e2e`; then repo pre-push checklist (security alerts, `make validate`).

## Dependencies

- T001 → T030/T031/T050. T002 → T040/T041. T003 → T010/T012.
- Phase 1–4 independent per file (`[P]` across files); Phase 5 after their targets. T060/T061 last.
- **Cross-feature**: verify against 1384's `use-auth.ts`/`auth-store.ts` state before T020/T031; coordinate `user-menu.tsx` with 1380 (T020 vs 1380 avatar tasks).

---

## Adversarial Review #3

Attacked task granularity, ordering hazards, test honesty, and merge-collision omissions.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | HIGH | **No task guards the `auth-store.ts` boundary** — easy to drift into it and collide with 1384. | Added **T060** (assert zero `auth-store.ts` diff) as an explicit gate; referenced in T020/T031. |
| 2 | HIGH | **Tests could regress to presence-only** (the exact reason the button shipped inert). | T053/T056 assert click→`router.push`/URL and are specified to FAIL if the handler is removed; T054 asserts no-reload + identity, not mere render. (FR-011) |
| 3 | HIGH | **Framer `layoutId` regression not actionable in tasks.** | T010 carries the explicit "verify indicator animates, else fall back to `<button onClick=router.push>`" instruction (plan AR#2 F1). |
| 4 | MED | **`view-store` edit ordering** — editing before knowing all consumers risks breaking gestures/pull. | T002 (enumerate consumers) is Phase 0 and blocks T040/T041. |
| 5 | MED | **Open-redirect helper task lacked the tricky cases.** | T050 enumerates backslash/encoded/`//` cases explicitly. |
| 6 | MED | **`use-auth.ts` redirect threading could collide with 1384.** | T031 mandates page-layer reads first; only touches `use-auth.ts:147-171` region if unavoidable. |
| 7 | LOW | **ARIA model change (tab→link) undocumented as a task.** | T012 records the `role="tab"`→`aria-current` link-semantics switch. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** Tasks are behavior-asserting, boundary-gated, and consumer-ordered.
