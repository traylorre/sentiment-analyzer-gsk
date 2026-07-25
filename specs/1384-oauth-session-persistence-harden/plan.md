# Implementation Plan: OAuth Session Persistence — Harden (Anti-Clobber)

**Branch**: `1384-oauth-session-persistence-harden` | **Date**: 2026-07-24 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/1384-oauth-session-persistence-harden/spec.md`
**Follow-on to**: Feature 1381 / PR #942 (merged + deployed to preprod)

## Summary

PR #942 made the OAuth happy-path restore work (the Cognito refresh branch now resolves `user_id` via the `by_cognito_sub` GSI, so `restoreSession()` no longer bails to guest). But the owner's canonical DevTools waterfall — **three** `/refresh` calls in one page load carrying **two different identities** (`anon.*` and Cognito `eyJ…`) under the same `refresh_token` cookie — shows a **clobber race that #942 does not close**. This feature hardens beyond #942:

1. **Remove the race at the source (frontend)**: make identity bootstrap single-flight and owned solely by `useSessionInit`; stop `useAuth` from independently minting anonymous; guard `signInAnonymous()` so it never mints over an in-flight restore or a present OAuth session.
2. **Defense-in-depth (backend)**: `POST /api/v2/auth/anonymous` refuses to overwrite a valid non-anon (Cognito) `refresh_token` cookie — a no-clobber backstop that survives multi-tab and any future client path.
3. **Verify-fail diagnostic**: before blaming the race, confirm the live alias actually serves #942 code and the owner's user record carries `cognito_sub` in the GSI.

## Technical Context

**Language/Version**: TypeScript 5.x / Next.js 14 / React 18 (frontend — primary change); Python 3.13 (dashboard Lambda — backend guard).
**Primary Dependencies**: Zustand (auth store, single-flight), React Query; aws-lambda-powertools (routing/Response), boto3 (DynamoDB), the existing Cognito token decode/verify used by the refresh path.
**Storage**: DynamoDB `{env}-sentiment-users` (existing GSIs incl. `by_cognito_sub`). No schema change. Tokens stay in httpOnly cookies — NO JS storage.
**Testing**: Vitest (frontend unit — interleaved restore/anon-mint simulation, single-flight); pytest (backend unit — no-clobber guard on `/anonymous`); Playwright against the Amplify URL for login+reload E2E (Google consent owner-manual).
**Target Platform**: AWS Amplify (frontend); AWS Lambda (dashboard) behind API Gateway; AWS Cognito.
**Project Type**: Web (separate `frontend/` + `src/lambdas/dashboard/`).
**Constraints**: No new AWS resources. Tokens in httpOnly cookies only (SR-001). Backend Bearer + `require_role` is the security boundary. Dashboard Lambda env is FROZEN (manual snapshot versions v105/v108/v110 via `lifecycle { ignore_changes }`) — see Verify-Fail. GPG-signed + venv-active commits. Customer dashboard only (ignore `src/dashboard/` HTMX).
**Scale/Scope**: Small but shared-hotspot: touches `frontend/src/hooks/use-auth.ts`, `use-session-init.ts`, `stores/auth-store.ts`, and `src/lambdas/dashboard/router_v2.py` (`/anonymous` handler). `auth.py`/`router_v2.py` are a **backend hotspot shared with other in-flight auth features (1381/1383/1382)** — coordinate to avoid merge collisions; keep the backend change confined to the `/anonymous` handler + a small cookie-inspection helper.

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after design.*

- **Security & Access Control (§3)**: Tokens stay httpOnly; guard verifies Cognito token server-side (SR-002); CSRF on `/anonymous` unchanged (SR-004); `/refresh` blocklist preserved (SR-005). **PASS.**
- **No raw input into logs (§3, CWE-117/312)**: clobber diagnostics use hash-prefix/masking (FR-009/SR-006). **PASS.**
- **IaC / deployment (§5)**: no new infra; respects the frozen-env delivery reality (Verify-Fail confirms the live alias). **PASS.**
- **Least privilege / no schema churn**: reuses existing tables/GSIs; no client-trusted identity. **PASS.**
- **Testing discipline**: unit tests simulate interleaved init orderings; real-frontend E2E for reload persistence. **PASS.**

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/1384-oauth-session-persistence-harden/
├── plan.md              # This file
├── spec.md              # Spec + Adversarial Review #1 + Clarifications
├── contracts/
│   └── anonymous-no-clobber.md  # /anonymous no-clobber guard contract
└── tasks.md             # Task list + Adversarial Review #3
```

### Source Code (repository root)

```text
frontend/src/
├── hooks/use-session-init.ts   # SOLE owner of identity bootstrap (single-flight) — primary change
├── hooks/use-auth.ts           # REMOVE independent signInAnonymous() (:52-69); keep timers but source state from bootstrap
├── stores/auth-store.ts        # single-flight guard on restoreSession/refreshSession/signInAnonymous (:102-239, :343+)
└── (components/auth/protected-route.tsx — verify requireAuth still renders loading, no change expected)

src/lambdas/dashboard/
├── router_v2.py         # /api/v2/auth/anonymous handler (:382) → no-clobber guard reading incoming cookie (_extract_refresh_token_from_event :197)
└── auth.py              # (reference only) anon token shape (:177), Cognito branch (:2978-3012) — HOTSPOT shared w/ 1381/1383

tests/
├── frontend (Vitest)   # interleaved restore/anon-mint race sim; single-flight assertion
└── unit/dashboard/      # no-clobber guard: valid-Cognito-cookie → refuse mint; absent/anon → mint

E2E:
└── frontend/tests/e2e/  # Playwright login+reload against Amplify URL (owner-manual Google consent)
```

**Structure Decision**: Web app. Primary change is frontend (removes the race source). Backend adds one guard in the `/anonymous` handler as a backstop. No `auth.py` behavior change beyond what the guard reads; keep the backend diff minimal because `auth.py`/`router_v2.py` collide with sibling auth features.

## Race Analysis (file:line — the residual that survives #942)

Three concurrent writers to the ONE shared `refresh_token` cookie (`router_v2.py:179-194`, path `{/stage}/api/v2/auth`) on a single reload:

1. **`useSessionInit` restore-or-mint** (`use-session-init.ts:46-103`): `await restoreSession()` (network `/refresh`); on `false`, `signInAnonymous()` (`:73-76`). Post-#942 the OAuth path returns `true`, so this path's mint no longer fires on the happy path — **but it is still gated on a slow awaited restore.**
2. **`useAuth` init effect** (`use-auth.ts:52-69`): independently calls `signInAnonymous().catch(...)` (`:59-64`) when `!isInitialized && !hasValidSession && requireAuth`. **Untouched by #942.** Mounted at 9 sites; `protected-route.tsx` uses `requireAuth`. This can mint `anon.*` *before* the awaited OAuth restore resolves → clobbers `eyJ…`.
3. **Pre-expiry refresh timers** (`use-auth.ts:96-98`) + 60s validity checks (`:104-111`), one set per `useAuth` mount → several `/refresh` calls per load (the owner's 3-call waterfall). If one fires after a stray anon-mint, it sends `anon.*` and the response flips the store to guest.

**Shared-state TOCTOU**: `isInitialized` is read (`!isInitialized`) and later written (`setInitialized(true)`) by BOTH `useSessionInit` (`:48`, `:82`) and every `useAuth` (`:53`, `:67`) — classic check-then-act; both can pass the check before either writes. The `initAttempted` ref (`use-session-init.ts:32`) only dedups `useSessionInit` against *itself*, not against `useAuth`.

**Conclusion**: a race survives #942. `restoreSession()` succeeding (dashboard shows Google user) does not prevent a concurrent `useAuth` mint or a stale-cookie refresh from overwriting to guest a beat later — exactly the Settings "Anonymous/Guest" symptom.

## Chosen Defense-in-Depth Approach

**Primary (frontend) = single-flight + owned bootstrap + `signInAnonymous` guard; Backstop (backend) = `/anonymous` no-clobber guard.**

- **Owned, single-flight bootstrap (FR-002/FR-004)**: `useSessionInit` is the ONLY caller that does restore-or-mint. Remove the `signInAnonymous()` call from `useAuth`'s init effect (`use-auth.ts:59-64`); `useAuth` consumes resolved state and keeps only the timer/redirect duties. In the store, wrap `restoreSession`/`refreshSession` (the `/refresh` callers) and `signInAnonymous` in a shared in-flight promise so concurrent callers collapse to one cookie write.
- **`signInAnonymous` guard (FR-003)**: before minting, if a restore is in flight or the store already holds a non-anonymous user, no-op (return the existing session) instead of minting. Client-side, cheap, closes the common single-tab race.
- **Backend no-clobber (FR-005, backstop)**: `POST /api/v2/auth/anonymous` reads the incoming `refresh_token` cookie (`_extract_refresh_token_from_event`, `router_v2.py:197`); if it is a valid non-`anon.*` (Cognito) token, refuse to set a new `anon.*` cookie — return the request without clobbering (and log `anonymous.clobber_blocked`). Survives multi-tab and any future/again-introduced client mint path. Feasible with zero new resources because the cookie already arrives on that path.

**Rationale (1 line)**: single-flight + owned bootstrap collapses every init ordering to one deterministic cookie write (fixes the race at its source), and the server-side no-clobber makes the failure unreachable even if a new client path regresses or a second tab races.

### Rejected alternatives

- **Frontend-only guard, no backend backstop** — rejected: per-tab; multi-tab and any future `useAuth`-like mint path re-open the clobber. AR#1 #2.
- **Backend-only no-clobber, leave the frontend race** — rejected: still fires spurious `/anonymous` calls and depends on the guard for correctness of a purely client-created problem; also leaves the 3-refresh timer pile-up. Weaker and noisier.
- **Distinguish the two session types with separate cookie names/paths** (spec option c) — rejected for THIS feature: cleaner long-term but touches every cookie set/read site across login, magic-link, OAuth, guest, and refresh (`router_v2.py` cookie helpers used by all flows) — high blast radius on a shared hotspot mid-flight with 1381/1383/1382. Deferred as a possible follow-up; the guard achieves the same safety with a fraction of the surface.
- **Move tokens to JS storage to coordinate writers** — forbidden (SR-001); would break the httpOnly security boundary.

## Verify-Fail Diagnostic Plan

If the owner's post-#942 interactive login STILL guests on reload, do NOT assume the frontend race before ruling out two deployment/data causes:

- **(i) Live alias may not serve #942 code.** The dashboard Lambda carries manual out-of-band env-snapshot versions **v105/v108/v110** (frozen env via `lifecycle { ignore_changes }`); the live alias could point at a snapshot published before #942. Check: `aws lambda get-function-configuration`/`get-alias` for the live alias' `FunctionVersion` and image digest; confirm the served code contains `get_user_by_cognito_sub` (`auth.py:2906`) and the Cognito-branch identity resolution (`auth.py:2989-3012`). If the alias points at a pre-#942 snapshot, the fix is a deploy/alias-repoint, not code.
- **(ii) Owner's user record may lack `cognito_sub` in the GSI.** `get_user_by_cognito_sub` returns `None` if the `by_cognito_sub` GSI has no item for the owner's sub, so `/refresh` returns guest even with #942 code. Check: query `by_cognito_sub` for the owner's sub (sub from a decoded id_token); confirm an item exists and `_update_cognito_sub` (`auth.py:2456`) ran on their last OAuth login. If missing, backfill via a re-login or a one-off write (no new resource).

Both checks precede any conclusion that the frontend race is the live cause. They are cheap, runtime-only, and owner-assisted.

## Phased Approach

- **Phase 0 — Verify-Fail gate**: run the two diagnostics above IF D1 (owner live-verify) shows a persisting guest. Records whether the residual is the race (proceed) or a deploy/data issue (hand off).
- **Phase 1 — Frontend single-flight + owned bootstrap (FR-002/FR-004)**: store-level in-flight promise; remove `useAuth` anon-mint; `useSessionInit` sole owner. Vitest race sim.
- **Phase 2 — `signInAnonymous` guard (FR-003)**: client guard against minting over restore/OAuth.
- **Phase 3 — Backend no-clobber (FR-005/FR-009)**: `/anonymous` refuses to overwrite a valid Cognito cookie; unit tests + diagnostic log.
- **Phase 4 — Verify (real, no mocks)**: owner login on Amplify → ≥5 reloads → 0 `/anonymous`, all `/refresh` OAuth, Settings shows Google; fresh-profile guest still works.

## Complexity Tracking

No constitution violations; table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

---

## Adversarial Review #2

Re-read spec.md (incl. AR#1 + Clarifications) and plan.md for drift and cross-artifact inconsistency, verifying every cited symbol against source.

| # | Sev | Drift / inconsistency | Resolution |
|---|-----|------------------------|------------|
| 1 | HIGH | **Backend behavior-change on a shared hotspot could collide with 1381/1383.** A broad `auth.py` edit for the guard would fight sibling auth PRs and risk a merge that reverts #942's identity resolution. | Scoped the backend change to the `/anonymous` handler in `router_v2.py` + a small cookie-inspection helper; `auth.py` is reference-only (reuse `anon.*` shape check `:2978`). Called out the hotspot in Technical Context and tasks. |
| 2 | HIGH | **"Remove `useAuth` anon-mint" could strand `requireAuth` routes** with no session if bootstrap is slow (the exact worst case the original code was guarding against). | Verified `useSessionInit` exposes `isInitializing` (`use-session-init.ts:110`) and protected routes already render on it; `useAuth` redirect effect (`use-auth.ts:131-136`) fires only after `isInitialized`. Bootstrap-owned, not mint-owned. Consistent with FR-004/Q4. |
| 3 | MED | **Single-flight scope creep** — could accidentally cache refresh *results* and bypass the blocklist (SR-005) or serve a stale identity across a real sign-out. | Plan specifies single-flight caches only the in-flight *promise* for one tick, cleared on settle; per-request blocklist (`auth.py:2963-2974`) still runs. Matches AR#1 #7 / SR-005. |
| 4 | MED | **Guard's "valid Cognito token" check** — if it does a full Cognito network verify on every `/anonymous`, it adds latency and a failure mode to guest creation. | Guard uses local token-shape discrimination (`anon.*` prefix, `auth.py:2978`) + lightweight local id/refresh-token structure validation consistent with the refresh path; it does NOT add a Cognito round-trip to the guest-mint path. Absent/`anon.*` always mints (SR-003). |
| 5 | MED | **Verify-Fail vs "race survives #942" could read as contradictory** (is the bug the race, or the deploy/data?). | Ordered explicitly: Verify-Fail is a *gate* that runs only if D1 shows persisting guest; it rules out deploy/data BEFORE attributing to the race. Both can be true independently; the plan sequences them. |
| 6 | LOW | **Cookie-name-split alternative** mentioned in spec Out-of-Scope but evaluated in plan — ensure it's clearly rejected-for-now, not silently dropped. | Rejected-alternatives section keeps it as an explicit deferred follow-up with rationale (blast radius on shared cookie helpers). |

**Gate: 0 CRITICAL, 0 HIGH remaining.** The two HIGHs (hotspot collision, stranded protected routes) are resolved by scoping the backend diff and confirming bootstrap-owned loading state. Cross-artifact references (spec ↔ plan) are consistent on: primary-frontend + backend-backstop, single-flight, guard-keys-on-valid-Cognito-cookie, and the Verify-Fail gate ordering. All cited file:line verified against source in this session.
