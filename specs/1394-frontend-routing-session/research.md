# Research: Frontend Routing + Session-State Architecture (Feature 1394)

**Created**: 2026-07-24
**Author**: principal-frontend investigation (research-first, per owner directive)
**Target**: CUSTOMER dashboard only (`frontend/` — Next.js 14 App Router on Amplify, `https://main.d29tlmksqcx494.amplifyapp.com/`). NOT the HTMX admin dashboard (`src/dashboard/`).
**Mandate**: The owner flagged that three bugs (1385 dead-nav, 1386 upgrade-now, 1380 oauth-avatar) "seem like a simplification of a complex issue with likely follow-up issues." This document maps the actual routing + session-state architecture against current `main`, cites `file:line`, proves/disproves that framing, and drives the fix-feature structure. Prior specs' conclusions were re-verified against source, not restated on faith.

---

## 0. TL;DR

- The three surface bugs are NOT three isolated one-liners. They resolve to **3 technical root causes** that cluster into **2 fix-features**.
- **RC-A (nav architecture split-brain)** and **RC-B (hard-nav wipes the memory-only auth store)** are two facets of one meta-defect: *the app does not treat the Next.js router as the navigation source of truth.* They share the same files (`desktop-nav.tsx`, `mobile-nav.tsx`, `user-menu.tsx`) and the same fix pattern (client-side routing + URL-derived state). They must be fixed together to avoid conflicting edits to `user-menu.tsx` and to avoid a partial fix that leaves a second dead-nav/guest-flash surface. → **Feature 1394 (this set).**
- **RC-C (avatar persisted but never surfaced)** is an independent data-plumbing defect (backend response field → frontend type/mapper/render). → **Feature 1380 (kept as-is; already fully spec'd with AR#1/#2/#3).**
- The owner's instinct was correct: I found **8 follow-on defects** beyond the 3 reported, several of which a naive "add `router.push`" fix would leave broken.
- **1384 (session-persistence-harden) is complementary, not conflicting** — the routing fix *removes a common trigger* of 1384's cookie-clobber race but does not fix the race itself. Two shared files (`user-menu.tsx`, `auth-store.ts`) demand merge coordination.

---

## 1. The routing model — who actually owns navigation?

### 1.1 Two navigation systems exist; only one is wired to the screen

| System | Source of truth | Drives | Status |
|---|---|---|---|
| **Next.js file routing** | URL / `usePathname` | The actual page content under `frontend/src/app/(dashboard)/` | **LIVE** — this is what renders |
| **Zustand `view-store`** (`currentView`) | in-memory `setView()` | nav highlight, `DesktopHeader` title, `ViewIndicator` dots | **Vestigial** — a leftover of an abandoned in-place-view design |

File-routed pages (all real, verified): `src/app/(dashboard)/page.tsx` (`/`), `configs/page.tsx` (`/configs`), `alerts/page.tsx` (`/alerts`), `settings/page.tsx` (`/settings`), plus `(dashboard)/layout.tsx`. The layout renders `<DesktopNav/>`, `<MobileNav/>`, `<DesktopHeader/>`, `<ViewIndicator/>` and `{children}` — children come from the router.

### 1.2 The `view-store` was built for `SwipeView`/`SwipeContainer`, which are never mounted

`view-store.currentView` is designed to select which `SwipeView` renders (`swipe-view.tsx:113` `if (view !== currentView) return null`). But `SwipeView`/`SwipeContainer` are **defined and never mounted** anywhere in the app. Grep for usage:
- `src/components/navigation/index.ts:1` re-exports them.
- Only self-references inside `swipe-view.tsx`.
- No page or layout wraps content in `<SwipeView>`/`<SwipeContainer>`.

So `currentView` drives nothing that shows page content. It only feeds:
- `desktop-nav.tsx:64` `isActive = currentView === item.view` (highlight)
- `mobile-nav.tsx:55` same (highlight)
- `desktop-nav.tsx:142-151` `DesktopHeader` title = `viewTitles[currentView]`
- `swipe-view.tsx:160-183` `ViewIndicator` dots + `onClick=setView`

### 1.3 Every nav entry point and where it actually goes

| Entry point | Code | Mechanism | Actually navigates? |
|---|---|---|---|
| Desktop nav (4 primary) | `desktop-nav.tsx:37-41,68-70` `<button onClick=setView>` | mutates `currentView` | **NO** — highlight only |
| Mobile bottom nav (4) | `mobile-nav.tsx:35-39,59-61` `<button onClick=setView>` | mutates `currentView` | **NO** — highlight only |
| `ViewIndicator` dots (mobile) | `swipe-view.tsx:169-171` `onClick=setView` | mutates `currentView` | **NO** |
| Mobile swipe gesture | `use-gesture.ts:208,215-216` `navigateLeft/Right` → `view-store` → `setView` | mutates `currentView` | **NO** |
| Desktop/mobile Admin link | `desktop-nav.tsx:107` / `mobile-nav.tsx:130` `<Link href="/admin/chaos">` + `usePathname` | real routing | **YES** (the one that works) |
| UserMenu → Settings | `user-menu.tsx:142` `window.location.href='/settings'` | full page reload | YES, but hard (wipes state) |
| UserMenu → Sign in | `user-menu.tsx:49,131` `window.location.href='/auth/signin'` | full page reload | YES, but hard |
| `verify`/`callback` success | `use-auth.ts:150,168`; `callback:125`; `verify:30` `router.push('/')` | real routing | YES (but drops redirect intent — see §4) |

**Conclusion (RC-A):** The four primary nav items — the reported dead-nav — are dead by construction. The Admin link already demonstrates the correct pattern (`<Link>` + `usePathname`). The bug is that the primary items were wired to a store that was supposed to drive a view container that was never mounted. **Confirmed against source; 1385's root-cause claim holds.**

---

## 2. The hard-navigation problem (RC-B)

### 2.1 The auth store is memory-only by design

`auth-store.ts:6,71` — Feature 1165 removed `persist()` (CVSS 8.6); session state lives ONLY in memory and is rebuilt from httpOnly cookies via `/refresh` at init (`restoreSession`, `auth-store.ts:102-198`). There is no localStorage fallback for identity.

### 2.2 A full page reload therefore destroys the signed-in identity until re-restore

`window.location.href = '/settings'` (`user-menu.tsx:142`) is a **full document navigation**. It tears down all React/Zustand memory, so on the `/settings` document:
1. `auth-store` starts at `initialState` (`isAuthenticated:false`, `isAnonymous:false`).
2. `SessionProvider` (`app/layout.tsx:54`) mounts `useSessionInit` (`use-session-init.ts:46-96`) → `restoreSession()`; every `useAuth` mount (`settings/page.tsx:44`, `user-menu.tsx:37`, `protected-route.tsx:30`, …) runs its own init effect (`use-auth.ts:52-69`).
3. Until `restoreSession()`'s `/refresh` round-trip resolves, `UserMenu`/Settings read `isAnonymous`/no-user → they can paint "Guest"/"Anonymous" while a still-open tab (or the pre-reload dashboard) showed the Google user. This is the reported **Settings-shows-Guest split-brain**.

### 2.3 This reload is exactly the surface that exposes 1384's cookie-clobber race

The reload triggers the full init storm 1384 documents: `restoreSession` + N concurrent `useAuth` init effects + per-mount pre-expiry refresh timers, all racing on the single shared `refresh_token` cookie (`router_v2.py:179-194`). One stray `signInAnonymous()` from `useAuth`'s init effect (`use-auth.ts:59-64`) clobbers the OAuth cookie → the next of the 2-3 `/refresh` calls returns guest → the tab flips to Guest permanently. So the hard-nav is **the trigger**; 1384's race is **the mechanism**.

**Shared-cause verdict:** RC-B is the common cause of (a) 1385's Guest-flash symptom, (b) the reload path that 1384 hardens, and (c) the correct implementation of 1386 (the upgrade button must navigate via the router, not `window.location.href`, or it re-introduces RC-B). Replacing the hard navigations with client-side routing does NOT fix a genuine F5 (that still needs 1384), but it removes the app's own most-common self-inflicted reload.

---

## 3. Interconnection map — how it all wires together

```
                       URL / usePathname  ◄──────── (correct source of truth)
                              │
        ┌─────────────────────┼───────────────────────────────┐
        │ file routing        │                               │
        ▼                     ▼                               ▼
  (dashboard)/page   (dashboard)/settings/page     (dashboard)/alerts/layout
        │                     │  useAuth()                    │ <ProtectedRoute requireUpgraded>
        │                     │  (mounts init effect)         │   → redirect /auth/signin?redirect=..&upgrade=true
        │                     │                               │        │
        ▼                     ▼                               ▼        ▼
   DesktopNav/MobileNav   UserMenu ─ window.location.href ──► FULL RELOAD ──► auth-store wiped
        │  setView() only      │  (:142 /settings, :49/:131 /signin)         │
        ▼  (RC-A)              ▼                                             ▼
   view-store.currentView   avatar render (RC-C: no pictureUrl)     SessionProvider→useSessionInit
        │  (drives ONLY                                              restoreSession() + N useAuth inits
        ▼   highlight+title+dots, NOT content)                       racing on ONE refresh_token cookie
   DesktopHeader title (stale vs URL)                                 (RC-B trigger → 1384 race)
```

Key wiring facts (cited):
- `SessionProvider` is the single mount of `useSessionInit` (`app/layout.tsx:54`, `providers/session-provider.tsx:57`). Identity bootstrap is *supposed* to be owned here.
- `useAuth` is mounted at ≥9 sites and each runs an independent init effect that can `signInAnonymous()` (`use-auth.ts:52-69`). This is 1384's second anon-mint trigger.
- `ProtectedRoute` (`protected-route.tsx:19-92`) wraps `(dashboard)/alerts` (`alerts/layout.tsx:18` `requireUpgraded`) and `(admin)` (`(admin)/layout.tsx:16`). It builds `redirect=<pathname>&upgrade=true` (`protected-route.tsx:41-45`) and `router.replace`s to signin.
- `signin/page.tsx` reads **no** `searchParams` (verified: only `authApi.getOAuthUrls()`), so the redirect param is silently dropped.

**Which bugs share a root cause:**
- RC-A (split-brain nav): 1385 dead-nav, follow-ons F1 (highlight desync), F4/F5/F7 (dead swipe, dead dots, stale header title).
- RC-B (hard-nav wipes memory auth): 1385 Guest-flash (US3), 1386's correct fix, 1384's reload trigger, follow-on F3 (other hard-navs).
- RC-C (avatar not surfaced): 1380 only. Independent.

RC-A and RC-B both reduce to "use the router; derive UI state from the URL." That is why they are ONE fix-feature.

---

## 4. Follow-on defects the owner expected (found: 8)

| # | Defect | Evidence | A naive fix misses it? |
|---|---|---|---|
| **F1** | Active-nav highlight derives from **persisted** `view-store.currentView`, not the URL. `currentView` is persisted (`view-store.ts:180 partialize currentView`), so after a deep-link/reload onto `/settings` the highlight can show a stale item that disagrees with the route. | `desktop-nav.tsx:64`, `mobile-nav.tsx:55`, `view-store.ts:178-182` | Yes — "just add `router.push`" leaves highlight wrong. |
| **F2** | `/auth/signin` ignores `?redirect=`/`?upgrade=` params. `ProtectedRoute` sets them (`protected-route.tsx:41-45`) but signin never reads `searchParams`; `callback`/`verify` hardcode `router.push('/')` (`use-auth.ts:150,168`, `callback:125`, `verify:30`). Post-login the user never returns where they were. | `signin/page.tsx` (no `useSearchParams`), `use-auth.ts:150,168` | Yes — separate from the button/nav fix; becomes MORE visible once nav works (Alerts→signin→stranded). |
| **F3** | Other hard-nav `window.location.href` calls also wipe the memory-only store: `user-menu.tsx:49,131` (→`/auth/signin`), `lib/api/errors.ts:45` (→`/`), `auth-degradation-toast.tsx:29` (→`/auth/signin`). Each forces a reload → same RC-B trigger as `:142`. | grep `window.location.href` | Yes — fixing only `:142` leaves the sign-in hard-navs. |
| **F4** | Mobile **swipe** navigation is silently dead: `useSwipeNavigation` → `navigateLeft/Right` → `view-store.setView` only, never routes (`use-gesture.ts:208,215-216`; `view-store.ts:103-117`). | `use-gesture.ts:200-218` | Yes — an additional dead-nav surface not in the report. |
| **F5** | `ViewIndicator` dots (mobile swipe hint, rendered in `(dashboard)/layout.tsx:46`) also call `setView` only → dead on click. | `swipe-view.tsx:169-171` | Yes. |
| **F6** | `DesktopHeader` title derives from `currentView` (`desktop-nav.tsx:142-151`), not the route. Because `currentView` never updates from the URL, the header title can be wrong (e.g. shows "Dashboard" while on `/settings`). A visible second symptom of RC-A. | `desktop-nav.tsx:141-151`, layout `:33` renders it with no `title` prop | Yes. |
| **F7** | `view-store` + `SwipeView`/`SwipeContainer` are a partially-dead abandoned subsystem (never mounted). Leaving it as the highlight/title source is the root of F1/F6; the fix must either retire it or make it a pure route-mirror. | §1.2 grep | Yes — this is the architectural cleanup the owner sensed. |
| **F8** | Avatar-survives-reload (1380 SC-003) is cross-coupled: it needs (a) `/auth/me` to carry `picture` (1380 FR-002) AND (b) 1384 to actually restore the OAuth session on reload. Without 1384 the reload E2E is flaky. | 1380 spec Dependencies; `auth-store.ts:162-176` restore path | Documented in 1380; carried here as a cross-feature dependency. |

---

## 5. Relationship to Feature 1384 (session-persistence-harden)

I read `specs/1384-oauth-session-persistence-harden/spec.md` in full. 1384's fix set:
- Remove `useAuth`'s independent anon-mint init effect (FR-002, `use-auth.ts:52-69`).
- Make identity bootstrap single-flight/idempotent, owned by `useSessionInit` (FR-004).
- Guard `signInAnonymous()` against minting over an in-flight/existing OAuth session (FR-003).
- Backend no-clobber guard on `POST /api/v2/auth/anonymous` (FR-005).

**Does the routing fix reduce 1384's trigger surface? YES, partially.** Replacing `user-menu.tsx:142` (`window.location.href='/settings'`) and `:49/:131` (`→/auth/signin`) with client-side routing means the app stops forcing full reloads on its own most common in-app navigations. A client-side route change preserves the memory auth store → no re-`restoreSession` → no init storm → the clobber race is not triggered on those navigations. It does **not** fix a genuine browser F5 (that still triggers the storm and still needs 1384's single-flight + guards). So the two features are **complementary**: 1394 removes self-inflicted reloads; 1384 hardens the one reload the user can always force.

**Overlap / conflict:** No *logical* conflict — the routing fix never touches mint/restore logic. But there are **two shared files** that demand serialization:

| File | 1394 (this) edits | 1384 edits | 1380 edits | Coordination |
|---|---|---|---|---|
| `user-menu.tsx` | `:142` Settings nav → router; `:49/:131` sign-in nav → router | mounts `useAuth` (consumer; likely no nav edit) | `:78-80,103-105` avatar render | **3 features touch this file.** Serialize; land 1394's nav rewire and 1380's avatar render as non-overlapping hunks (different lines), but review together. |
| `auth-store.ts` | none (routing fix is orthogonal) | rewrites `restoreSession`/`signInAnonymous`/`refreshSession` for single-flight + guard | threads `pictureUrl` into `restoreSession` `setUser(...)` (`:164-176`) | **1380 + 1384 both edit `restoreSession`.** Land 1384 first (structural), then 1380 threads the field; or coordinate the hunk. 1394 stays out. |

**Recommendation:** Sequence = 1384 (structural auth hardening) → 1394 (routing/session nav) → 1380 (avatar surfacing), OR run 1394 and 1380 in parallel with 1384 since 1394 avoids `auth-store.ts` entirely and 1380's `auth-store.ts` hunk is a narrow additive field. Flag the `user-menu.tsx` and `auth-store.ts` hotspots explicitly in each feature's plan.

---

## 6. Feature-structure decision (one coherent feature vs N sub-features)

**Chosen: ONE new fix-feature (1394) absorbing 1385 + 1386 + follow-ons F1–F7, and KEEP 1380 as the independent avatar sub-feature.** Justification:

- **1385 and 1386 share RC-A/RC-B and the same files.** Both must convert `user-menu.tsx` navigations to the router; doing them as two features produces conflicting edits to the same lines and risks a partial fix (fix the button with `window.location.href`, re-introducing RC-B). Merging them makes the fix pattern (router + URL-derived state) uniform and testable as a unit. → **1385 and 1386 are marked superseded-by-1394** (headers added to their spec files); 1394 is authoritative.
- **Follow-ons F1–F7 are the same fix pattern** (retire/repurpose `view-store`; derive highlight/title from `usePathname`; route swipe/dots; honor `redirect` param; audit hard-navs). They belong with the nav rewire, not as scattered one-liners.
- **1380 (avatar) is genuinely independent (RC-C)** and is already a complete, adversarially-reviewed feature (AR#1 spec, AR#2 plan, AR#3 tasks, 5 Clarifications). Re-authoring it would add risk, not value. It stays as the "Feature 1394-set sub-feature B," cross-linked, with the coordination notes from §5. Its only touch-points with 1394 (`user-menu.tsx`) and 1384 (`auth-store.ts`) are recorded above.

So the coherent SET is: **research.md (this) + 1394 spec/plan/tasks (routing/session, sub-feature A) + existing 1380 spec/plan/tasks (avatar, sub-feature B).** 1385/1386 fold into 1394; 1380 stays.

---

## 7. Root-cause map (answer to owner Q1)

**3 distinct technical root causes → 2 fix-features.**

- **RC-A — Navigation split-brain.** Nav mutates the vestigial `view-store` (built for an unmounted `SwipeView`) instead of the router. Underlies: 1385 dead-nav, F1 highlight desync, F4 dead swipe, F5 dead dots, F6 stale header title, F7 dead subsystem.
- **RC-B — Hard-nav wipes the memory-only auth store.** `window.location.href` full reloads destroy the 1165 memory-only identity → Guest/Anonymous flash + they trigger 1384's clobber race. Underlies: 1385 Guest-flash, 1386's correct fix, F2 redirect-drop exposure, F3 other hard-navs, and the 1384 trigger surface.
- **RC-C — Avatar persisted but never surfaced.** `/auth/me` + OAuth callback responses omit `picture`; frontend `User`/mappers/render lack it. Underlies: 1380 only. Independent.

RC-A + RC-B = one meta-cause ("router isn't the source of truth") → **Feature 1394**. RC-C → **Feature 1380**.
