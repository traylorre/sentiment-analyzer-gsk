# Tasks: OAuth Avatar / Profile Picture in UserMenu

**Feature**: `1380-oauth-avatar-picture` | **Spec**: `spec.md` | **Plan**: `plan.md`
**Target: Customer Dashboard (Next.js/Amplify)** — `frontend/` + `src/lambdas/dashboard/`. Do NOT touch `src/dashboard/` (HTMX admin).

Legend: `[P]` = parallelizable (different file, no ordering dep). Tasks are dependency-ordered. Each FR maps to ≥1 task (traceability table at bottom).

Note (from AR#2 D3): research/data-model/contracts are folded into `plan.md`; there are no separate `research.md`/`data-model.md` files to reference.
Note (Dependencies): T015 reload verification depended on **Feature 1384** (session persistence) — **MERGED (#944) 2026-07-24, gate CLEAR**. Backend `handle_oauth_callback` edits share `auth.py` with **Features 1381/1383** (merge hotspot) — keep the diff minimal (FR-015).

## Phase A — Backend: derive + surface picture (merge-hotspot; keep minimal)

- [ ] **T001 [P]** Add pure helper `_select_avatar(user: User) -> str | None` in `src/lambdas/dashboard/auth.py` (place near `_mask_email` ~`:2016`, NOT inside `handle_oauth_callback`). Logic: pick `provider_metadata[user.last_provider_used].avatar` if present, else first `provider_metadata` entry with non-null `avatar`; then validate with `urllib.parse.urlparse` — return the URL only if `scheme == "https"` AND `hostname` is truthy AND (`hostname == "googleusercontent.com"` OR `hostname.endswith(".googleusercontent.com")`); otherwise return `None` (fail-closed, incl. on any parse exception). Do NOT log the URL. (FR-003, FR-004, FR-005)
- [ ] **T002** Add field `picture: str | None = None` to `OAuthCallbackResponse` (`src/lambdas/dashboard/auth.py:1472`, after `last_provider_used` at `:1495`). (FR-001, FR-005)
- [ ] **T003** In `handle_oauth_callback`, add exactly one kwarg `picture=_select_avatar(user)` to the single existing `OAuthCallbackResponse(...)` return (`auth.py:2434–2453`). No other change to the callback body (merge-hotspot with 1381/1383 — FR-015). (FR-001)
- [ ] **T004 [P]** Add field `picture: str | None = None` to `UserMeResponse` (`src/lambdas/shared/response_models.py:50`, after `last_provider_used` at `:62`). (FR-002, FR-005)
- [ ] **T005** In the `/api/v2/auth/me` handler `get_current_user` (`src/lambdas/dashboard/router_v2.py:2152`), pass `picture=_select_avatar(user)` into the `UserMeResponse(...)` construction (`:2183–2194`). Import/reference `_select_avatar` from `auth.py` (or the auth service module both import) — watch for circular import at cold start (see AR#3; lazy-import inside the handler if needed). (FR-002)

## Phase B — Backend tests

- [ ] **T006 [P]** Unit tests for `_select_avatar` in `tests/unit/dashboard/test_auth_avatar.py`: (a) Google metadata → returns URL; (b) `https://evil-googleusercontent.com/x` → `None`; (c) `https://evilgoogleusercontent.com.evil.com/x` → `None`; (d) `https://evil.com/googleusercontent.com/x` → `None`; (e) `http://lh3.googleusercontent.com/…` → `None`; (f) non-URL / malformed string → `None`; (g) no `provider_metadata` → `None`; (h) multi-provider: picks `last_provider_used`; (i) `last_provider_used` has no avatar but another provider does → fallback returns that. (FR-003, FR-004, FR-005, SC-005)
- [ ] **T007 [P]** Response-shape tests: `/auth/me` and OAuth-callback responses include `picture` key (value = URL when Google avatar present, `null` for email/guest). Assert additive/backward-compatible (unknown-field tolerance). (FR-001, FR-002, FR-005)

## Phase C — Frontend: type + mapping + store

- [ ] **T008 [P]** Add optional `pictureUrl?: string` to the `User` interface in `frontend/src/types/auth.ts:8–25`. (FR-006)
- [ ] **T009** In `frontend/src/lib/api/auth.ts`: add `picture: string | null` to the raw `UserMeResponse` interface (`:24–34`) and the raw `OAuthCallbackResponse` interface (`:40–60`); in `mapUserMeResponse` (`:84`) and `mapOAuthCallbackResponse` (`:104`) set `pictureUrl: response.picture ?? undefined`. (FR-006)
- [ ] **T010** In `frontend/src/stores/auth-store.ts`, thread `pictureUrl` onto the `User` in the OAuth/Cognito restore path of `restoreSession` (`:164–176`, from `profile.pictureUrl`) and the OAuth sign-in path (from mapped `data.user.pictureUrl`). Guest restore (`:119`) and anonymous fallback (`:180`) set no picture (guests have none — FR-013). Confirm tier-upgrade (`use-tier-upgrade.ts:96–97` spreads `...currentUser`) and broadcast (`use-auth-broadcast.ts:46–47`, `:70–71` spread `...user`) paths preserve `pictureUrl` (verified 2026-07-24 — no change expected; add a guard/comment if a rebase breaks the spread). (FR-007, FR-013)

## Phase D — Frontend: shared Avatar component + wiring

- [ ] **T011 [P]** Create `frontend/src/components/ui/avatar.tsx`: `Avatar({ src?, name?, size, className })`. Render order: if `src` present AND passes a client-side host allowlist (parse via `new URL(src)`; require `protocol === "https:"` AND `hostname === "googleusercontent.com" || hostname.endsWith(".googleusercontent.com")` — same exact-suffix rule as backend, defense-in-depth per plan R3/R5) → `<img src referrerPolicy="no-referrer" onError={()=>setFailed(true)} className="object-cover rounded-full">` with fixed dims; on error or no/invalid `src` → initials (first 1–2 chars of `name`, uppercased); if no `name` → existing lucide `<User>` glyph. Fallback is text/glyph, never an `<img>` (no error loop). No credentials on the request. Fixed circular container to avoid layout shift. (FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014)
- [ ] **T012** Wire `Avatar` into `frontend/src/components/auth/user-menu.tsx`: replace the generic-icon `<div>` in the trigger (`:78–80`) and in the dropdown header (`:103–105`) with `<Avatar src={user?.pictureUrl} name={displayName} size={…} />` at the respective sizes (trigger ~8, header ~10). Keep `UserMenuSkeleton` untouched. (FR-008, FR-009, FR-014)

## Phase E — Frontend tests

- [ ] **T013 [P]** Vitest for `Avatar` (`frontend/src/components/ui/avatar.test.tsx`): (a) allowlisted `src` → renders `<img>` with `referrerPolicy="no-referrer"`; (b) non-allowlisted `src` (`https://evil-googleusercontent.com/x`, `https://evil.com/x`) → no `<img>`, initials shown; (c) no `src` + name → initials; (d) no `src` + no name → generic glyph; (e) simulate `<img>` `onError` → swaps to initials, no broken-image, fallback is not an `<img>`. (FR-008..FR-013)
- [ ] **T014 [P]** Vitest for mappers (`frontend/src/lib/api/auth.test.ts` or existing): `picture` → `pictureUrl` mapping present + `null`→`undefined` for both `mapUserMeResponse` and `mapOAuthCallbackResponse`. (FR-006)

## Phase F — E2E + verification (real Amplify)

- [ ] **T015** Playwright E2E (`frontend/tests/e2e/oauth-avatar.spec.ts`, header `// Target: Customer Dashboard (Next.js/Amplify)`): against `https://main.d29tlmksqcx494.amplifyapp.com/`, complete a real Google login, assert UserMenu trigger renders an `<img>` with a `googleusercontent.com` `src`; reload the page and assert the avatar is still present (session restore via `/refresh`→`/auth/me`). **The reload assertion depends on Feature 1384 (session persistence) — 1384 is MERGED (#944) as of 2026-07-24, so run the reload half ungated.** Use a freshly-linked Google account (pre-extraction accounts have no stored avatar — see AR#3). (SC-001, SC-003, US1)
- [ ] **T016 [P]** Manual/scripted verification matrix (record in PR): Google-with-photo (photo), Google-without-photo (initials), email/magic-link (initials), guest/anonymous (generic glyph + **no network request** to any image host — check devtools), forced bad URL (onError→initials). (SC-002, SC-004, US2)

## Phase G — Guardrails

- [ ] **T017 [P]** Confirm no CSP change and no `next.config.js` change were introduced (R5 forward-guard, no `next/image`); confirm the backend `handle_oauth_callback` diff is the single `picture=` kwarg + the out-of-body helper (git diff review for merge-serializability vs 1381/1383). (FR-012, FR-015, SC-006)
- [ ] **T018 [P]** venv-active: run `make sast` / Bandit + `ruff check` on backend; `npm run typecheck` + `npm test` on frontend; ensure `_select_avatar` triggers no log-injection/clear-text-logging findings (it logs nothing). Commits GPG-signed. (Constitution SAST gate)

## Dependencies

- T001 → T003, T005, T006 (helper must exist first).
- T002 → T003; T004 → T005.
- T008 → T009 → T010 → T012 (type → mapper → store → UI).
- T011 → T012, T013.
- T009 → T014.
- T001–T012 → T015/T016 (feature must be built to verify).
- T015 reload half → **Feature 1384** (external) — **satisfied: merged #944**.
- T003/T005 backend edits ↔ **Features 1381/1383** (merge-serialize `auth.py`).
- Parallelizable groups: {T001, T004, T008}; {T006, T007}; {T013, T014}; {T016, T017, T018}.

## Requirement → Task Traceability

| FR / SC | Task(s) |
|---|---|
| FR-001 | T002, T003, T007 |
| FR-002 | T004, T005, T007 |
| FR-003 | T001, T006 |
| FR-004 | T001, T006 |
| FR-005 | T001, T002, T004, T006, T007 |
| FR-006 | T008, T009, T014 |
| FR-007 | T010 |
| FR-008 | T011, T012, T013 |
| FR-009 | T011, T012, T013 |
| FR-010 | T011, T013 |
| FR-011 | T011, T013 |
| FR-012 | T011, T017 |
| FR-013 | T010, T011, T013, T016 |
| FR-014 | T011, T012 |
| FR-015 | T003, T017 |
| SC-001 | T015 |
| SC-002 | T013, T016 |
| SC-003 | T015 (1384 gate cleared — merged #944) |
| SC-004 | T016 |
| SC-005 | T006 |
| SC-006 | T017 |

Every FR and SC maps to ≥1 task. ✅

---

## Analyze (/speckit.analyze equivalent) — cross-artifact consistency

Non-destructive consistency scan across spec.md / plan.md / tasks.md after task generation.

### Coverage
- **All 15 FRs → tasks:** confirmed by traceability table (no orphan requirement).
- **All 6 SCs → tasks:** confirmed (SC-001/003 via T015, SC-002 via T013/T016, SC-004 via T016, SC-005 via T006, SC-006 via T017).
- **All 3 user stories → tasks:** US1 (T015), US2 (T016/T013), US3 (T011/T012, single shared component).
- **No task without a requirement:** every task cites an FR/SC; guardrail tasks T017/T018 map to FR-012/FR-015/SC-006 and the constitution SAST gate.

### Consistency checks
- **File citations** in tasks match spec + plan (re-verified against main worktree: `auth.py:1472/2016/2434`, `response_models.py:50/62`, `router_v2.py:2152/2183`, `user.py:28/111/114`, `types/auth.ts:8–25`, `lib/api/auth.ts:24/40/84/104`, `auth-store.ts:119/164/180`, `user-menu.tsx:57/78/103`). ✅
- **CSP / next/image:** tasks reflect R5 (no CSP change; no `next/image`; T017 verifies). No residual "add CSP / remotePatterns" task. ✅
- **Merge-hotspot:** T003 + T017 enforce the minimal localized diff (FR-015). ✅
- **Two-dashboard hazard:** every frontend/e2e task targets `frontend/` + Amplify URL; T015 header mandated. No `src/dashboard/` task. ✅
- **No new AWS resources / frozen env / httpOnly session:** no infra/terraform/env task exists. ✅
- **1384 dependency:** T015 reload half was explicitly gated; 1384 merged (#944) → gate cleared. ✅

### Ambiguities / residual
- **A1 (LOW):** T005 needs `_select_avatar` importable from `router_v2.py`. If the `auth.py`↔`router_v2.py` import direction risks a circular import at cold start, place `_select_avatar` in the auth service module both import, lazy-import inside the handler, or duplicate the ~8-line pure helper. Implementer's call; flagged, not blocking.
- **A2 (LOW):** Exact initials rule (1 vs 2 chars) is a UI detail left to T011. Acceptable.
- No CRITICAL/HIGH inconsistencies. Artifacts are internally consistent and ready for task execution (pending owner go-ahead — implementation NOT part of this pipeline).

---

## Adversarial Review #3

Posture: assume implementation will go wrong. Identify the highest-risk task, the most likely rework, and gate READY/BLOCKED.

### Highest-risk task: **T001 `_select_avatar` host allowlist (SSRF bypass)**

The single line that decides whether SSRF/exfiltration is possible. The overwhelmingly likely first-pass mistake is a permissive check:
- `url.endswith("googleusercontent.com")` → passes `https://evil-googleusercontent.com/x` (no boundary before the suffix).
- `"googleusercontent.com" in url` → passes `https://evil.com/googleusercontent.com/x` (label in the path) and `https://evilgoogleusercontent.com.evil.com/x`.
- Regex on the raw string → almost always anchored wrong.

**Mitigation (already specified):** parse with `urlparse`, compare `hostname` (not the raw URL), require `hostname == "googleusercontent.com" or hostname.endswith(".googleusercontent.com")` with the **leading dot**, and `scheme == "https"`; fail-closed on exceptions. T006 pins all four lookalike/scheme cases (b)–(e) plus malformed (f) as tests — they must be RED against a naive implementation and GREEN only against the parsed-hostname rule. This is the gate: **if T006 (b)–(e) do not fail on a naive `endswith`/`in` implementation, the tests are wrong, not the code.**

### Second-highest risk: **T005 `/auth/me` surfacing (the real reload acceptance path)**

1. **Import direction / circular import.** `_select_avatar` lives in `auth.py`; `/auth/me` is in `router_v2.py`. Powertools resolves routers at import time, so a new top-level import can surface a circular import at Lambda cold start. Mitigation: lazy-import inside the handler or relocate the helper (Analyze A1).
2. **Session-restore is the real acceptance path, not the callback.** Per Clarification Q4, the avatar on reload comes from `/auth/me`, not the callback. If T005 is skipped or `_select_avatar` returns `None` due to a `last_provider_used` mismatch, US1 scenario 2 / SC-003 fail silently — avatar appears after login, vanishes on refresh. This is the same class of bug seen in the M1 session-restore regressions (WI-3/WI-5). T015 must test the reload path (it does) — that half was gated on Feature 1384, which is **now merged (#944)**, so the full reload E2E runs ungated.
3. **Empty `provider_metadata` for pre-existing users.** Accounts linked before the extraction code existed have no stored avatar → initials until next login. Expected (Assumptions), but reads as "doesn't work for me" if a tester uses an old account. Mitigation: T016/T015 use a freshly-linked Google account.

### Most likely rework

- **The host-allowlist check (T001)** — see highest-risk above; forced by T006 (b)–(e).
- **Broken-image fallback flicker (T011).** A naive `onError` that unmounts/remounts, or a fallback that is itself an `<img>`, causes layout shift or an infinite error loop. Fallback must be non-`<img>` (initials text / glyph). T013(e) catches it.

### Cross-feature risk (merge)

`auth.py` is edited by 1380/1381/1383. T003 keeps this feature's callback change to one kwarg; if 1381/1383 also add helpers near `_mask_email`, expect a trivial textual conflict in the helper cluster (not logic). T017 verifies the diff is minimal. Recommend the owner serialize merges and re-run T006/T007 after each rebase. The former 1384 wait on the reload E2E (T015) is resolved (merged #944).

### Residual open items (non-blocking)

- Owner Q-A (deletion-path coverage) — deferred; no deletion flow exists today.
- A1 (import placement) — implementer's call at T005.
- Feature 1384 dependency for the T015 reload assertion — external, tracked in Dependencies; **now satisfied (merged #944)**.

### Gate

| Check | Result |
|---|---|
| Every FR/SC has a task | ✅ |
| Highest-risk task identified + mitigated | ✅ (T001 SSRF allowlist; parsed-hostname exact-suffix; T006 pins lookalikes) |
| Likely rework flagged with catching test | ✅ (T001 allowlist ↔ T006 b–e; T011 flicker ↔ T013e) |
| CRITICAL/HIGH open | 0 |
| Two-dashboard / no-new-AWS / frozen-env / httpOnly respected | ✅ |
| External dependency (1384) tracked, now satisfied (merged #944) | ✅ |

**Gate result: READY.** Planning pipeline complete. Implementation is intentionally NOT executed (stops here per battleplan pre-implementation gate). Recommend owner: (1) review deferred Q-A, (2) serialize `auth.py` merges with 1381/1383 — and serialize the `auth-store.ts`/`user-menu.tsx` frontend hunks after the 1395/1394 FE work (shared OAuth-cohort hotspot), (3) note Feature 1384 is now MERGED (#944), so the T015 reload assertion gate is CLEAR — run the full E2E including reload.

### Addendum (2026-07-24 worktree reconciliation)

Reconciled the divergent worktree draft. tasks.md salvage: T010 gained the verified `use-tier-upgrade.ts:96` / `use-auth-broadcast.ts:46,70` spread citations; AR#3 restored the WI-3/WI-5 regression reference. All other worktree-only task text was the pre-hardening version (weaker T001 allowlist wording without the leading-dot rule, T006 with only 3 spoof cases instead of 4+malformed, stale `auth.py:2426`/`router_v2.py:2166` line numbers) — superseded, not lost. Gate remains READY.
