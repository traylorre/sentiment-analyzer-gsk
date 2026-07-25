# Implementation Plan: OAuth Avatar / Profile Picture in UserMenu

**Branch**: `1380-oauth-avatar-picture` | **Date**: 2026-07-24 | **Spec**: `specs/1380-oauth-avatar-picture/spec.md`
**Input**: Feature specification from `/specs/1380-oauth-avatar-picture/spec.md`

## Summary

Surface the already-persisted Google profile picture end-to-end so the customer-frontend UserMenu renders it as a circular avatar, with graceful fallback to initials/generic icon for users without a picture or on image-load failure. The picture is already extracted (`auth.py:2373/2402`) and stored in `provider_metadata[provider].avatar` (`auth.py:2552`), but it is never returned by any API and the frontend has no field/type/render for it. The fix adds one nullable `picture` field to two response models (`OAuthCallbackResponse` `auth.py:1472`, `UserMeResponse` `response_models.py:50`) sourced through a small pure `_select_avatar(user)` helper that host-validates (`urlparse` → `hostname` exact-suffix `.googleusercontent.com` + `https`, fail-closed), plus a frontend `pictureUrl` type field, two mapper additions, store propagation, and a shared `Avatar` component (plain `<img>` + `referrerpolicy="no-referrer"` + `onError`→initials; no `next/image` optimizer, to avoid a server-side fetch/SSRF surface). No CSP change is needed (the frontend emits none today — R5; forward-guard only). Backend change is deliberately minimal/localized because `handle_oauth_callback` is a merge hotspot shared with Features 1381/1383. End-to-end "avatar survives reload" verification depends on Feature 1384 session persistence — **merged (#944) as of 2026-07-24, gate clear**.

## Technical Context

**Language/Version**: Python 3.13 (backend Lambda), TypeScript 5.x / React 18 / Next.js 14.2.21 (frontend)
**Primary Dependencies**: aws-lambda-powertools (response/routing), pydantic 2.x (response models); React, Radix UI dropdown, lucide-react (fallback glyph), Zustand (store)
**Storage**: DynamoDB `${env}-sentiment-users` — **read-only for this feature** (avatar already persisted in `provider_metadata`; no schema change, no write, no migration)
**Testing**: pytest (backend unit — `_select_avatar` + response-shape), Vitest (frontend unit — Avatar fallback/onError, mappers), Playwright (E2E on Amplify — real Google login)
**Target Platform**: AWS Lambda (Dashboard) + AWS Amplify (Next.js customer frontend)
**Project Type**: web (frontend + backend), customer dashboard only
**Performance Goals**: No added backend latency (helper is pure, in-memory over already-fetched user); avatar image loads async client-side; 0 image requests for guests
**Constraints**: No new AWS resources; Dashboard Lambda env FROZEN (no env var change); httpOnly session model unchanged; backend diff to `handle_oauth_callback` = one kwarg + out-of-body helper (merge-hotspot with 1381/1383); no open image proxy; host allowlist enforced backend (authoritative) + frontend (defense-in-depth); GPG-signed + venv-active commits
**Scale/Scope**: ~7 files touched (backend: `auth.py` response model + helper + 1 handler kwarg, `router_v2.py` /me handler, `response_models.py`; frontend: `types/auth.ts`, `lib/api/auth.ts`, `stores/auth-store.ts`, new `components/ui/avatar.tsx`, `components/auth/user-menu.tsx`). No `next.config.js`/CSP change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Security & Access Control** — TLS-only: FR-004/FR-012 enforce `https`-only image host. No raw user text into logs: the picture URL is PII-adjacent; the `_select_avatar` helper logs nothing (no `sanitize_for_log` needed because nothing is logged). **PASS.**
- **Data & Model Requirements** — no new persisted attribute; avatar derived at response time from existing `provider_metadata`. **PASS.**
- **DB access** — N/A (no new queries; read-only over already-loaded `User`). **PASS.**
- **Deployment (serverless/IaC)** — No infra change; Dashboard Lambda env frozen; no CSP change (frontend emits none today — R5); no AWS resources touched. **PASS.**
- **SAST/secret scanning** — new code passes Bandit/Semgrep; no secrets; no `eval`; URL host-check uses `urllib.parse` allowlist (not regex-on-string). **PASS.**

**No violations. Complexity Tracking not required.**

## Phase 0 — Research (decisions)

| # | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| R1 | Derive avatar at response-build time via `_select_avatar(user)`; do NOT add a stored `User.avatar` attribute | Avoids a DynamoDB schema/migration and keeps single source of truth (`provider_metadata`); no backfill | New top-level attribute (needs migration + backfill + write path in `_link_provider`); heavier and redundant |
| R2 | Select provider by `user.last_provider_used`, fallback to first `provider_metadata` entry with a non-null avatar | Handles multi-provider linking; `last_provider_used` exists and is documented "for avatar selection" (`user.py:114–115`) | Always Google-only (breaks if last provider differs); rejected |
| R3 | Host allowlist = scheme `https` + `urlparse(url).hostname == "googleusercontent.com" or hostname.endswith(".googleusercontent.com")`; fail-closed to `None` | Blocks SSRF/spoofed-claim + subdomain lookalikes (AR#1 F1/F2). Parsing the hostname (not the raw string) rejects `evil.com/googleusercontent.com/x`; the leading dot rejects `evil-googleusercontent.com`; and a full-hostname endswith rejects `evilgoogleusercontent.com.evil.com` | `url.endswith("googleusercontent.com")` (matches `evil-googleusercontent.com`); `"googleusercontent.com" in url` (matches path/label tricks); regex on raw string (bypassable). All rejected |
| R4 | Frontend renders a plain `<img>` (not `next/image`) with `referrerpolicy="no-referrer"` + `onError` fallback | Avoids the `next/image` server-side optimizer fetch (optimizer-as-open-proxy SSRF, AR#1 F1/F4) and Amplify image-optimization cost; simpler | `next/image` + `remotePatterns` (adds server fetch path + config); rejected for this feature |
| R5 | **Forward-guard only:** the customer frontend emits **no CSP today** (`middleware.ts` sets `X-Frame-Options`/`Referrer-Policy` but no `Content-Security-Policy`), so the `<img>` is not blocked. Do NOT add a CSP here. IF a CSP is later introduced it MUST include `img-src https://*.googleusercontent.com`. Client-side host allowlist in `Avatar` is defense-in-depth over the backend fail-closed (R3). | Clarification Q1 established no CSP exists; inventing one now risks blocking existing resources. Backend `HTML_CSP` already allows `img-src https:` but governs only the Lambda HTML admin dashboard (out of scope). | Adding a CSP in this feature (scope creep, regression risk); assuming a CSP exists (implementer chases nonexistent header). Both rejected |
| R6 | Backend diff to `handle_oauth_callback` limited to `picture=_select_avatar(user)` in the single `OAuthCallbackResponse(...)` return (`auth.py:2434`); helper placed near `_mask_email` (`:2016`), NOT inside the callback | Minimizes merge conflict with 1381/1383 (AR#1 F10, FR-015) | Refactoring the callback / adding branches; rejected |
| R7 | Initials fallback derives from existing `displayName` logic (`email.split('@')[0]`, `user-menu.tsx:57–59`); take first 1–2 chars uppercased; if no name, keep existing lucide `<User>` glyph | Reuses current display logic; works with `email_masked`; no new PII exposure | Fetch full name from a new `name` claim (out of scope; new field end-to-end) |

**Output**: research folded inline (feature too small for a separate `research.md`).

## Phase 1 — Design & Contracts

### End-to-end data path (file:line at each gap)

```
Google OIDC id_token.picture
  └─ EXTRACTED  auth.py:2373 (existing user) / :2402 (new user)  [WORKS]
  └─ PERSISTED  _link_provider avatar= param auth.py:2479 → ProviderMetadata(avatar=…) :2552
                → DynamoDB provider_metadata / last_provider_used :2561, :2569–2574        [WORKS]
                (ProviderMetadata.avatar model: user.py:28; User.provider_metadata: user.py:111)
  ── GAP 1 (backend response) ────────────────────────────────────────────────
  └─ /oauth/callback  OAuthCallbackResponse (auth.py:1472, fields end :1495) — NO picture
                      return site auth.py:2434–2453 — never sets picture         [ADD]
  └─ /auth/me        UserMeResponse (response_models.py:50, fields end :62) — NO picture
                     get_current_user router_v2.py:2152; construction :2183–2194 [ADD]
  ── GAP 2 (frontend thread) ─────────────────────────────────────────────────
  └─ User type       frontend/src/types/auth.ts:8–25 — NO pictureUrl             [ADD :20-ish]
  └─ raw interfaces  lib/api/auth.ts UserMeResponse :24–34, OAuthCallbackResponse :40–60 — NO picture [ADD]
  └─ mappers         mapUserMeResponse :84, mapOAuthCallbackResponse :104 — NO avatar map [ADD]
  └─ store           auth-store.ts restoreSession :164–176 (OAuth), guest :119, anon :180 [THREAD]
  ── GAP 3 (render) ──────────────────────────────────────────────────────────
  └─ UserMenu        user-menu.tsx trigger glyph :78–80, header glyph :103–105   [REPLACE w/ <Avatar>]
                     (new shared components/ui/avatar.tsx)                        [NEW]
```

### Allowlist design + enforcement point

- **Authoritative enforcement = backend**, in `_select_avatar(user) -> str | None` (`auth.py`, near `_mask_email` `:2016`). Pure function, no I/O, no logging. Steps: (1) pick candidate = `provider_metadata[last_provider_used].avatar` else first entry with non-null avatar; (2) `parsed = urlparse(candidate)`; (3) return `candidate` only if `parsed.scheme == "https"` AND `parsed.hostname` is truthy AND (`parsed.hostname == "googleusercontent.com"` OR `parsed.hostname.endswith(".googleusercontent.com")`); (4) else `None`. Fail-closed on any exception (malformed URL → `None`).
- **Defense-in-depth = frontend**, same exact-suffix rule inside `Avatar` before emitting the `<img>` (parse via `new URL(src)`, check `url.protocol === "https:"` and `url.hostname === "googleusercontent.com" || url.hostname.endsWith(".googleusercontent.com")`). If the check fails → treat as no `src` → fallback.
- **The rule that matters**: exact-suffix match on the **parsed hostname**, with the leading dot on the suffix. This is the line most likely to be gotten wrong (see AR#3). Rejects: `evil-googleusercontent.com` (no leading-dot boundary), `evilgoogleusercontent.com.evil.com` (hostname suffix is `.evil.com`), `evil.com/googleusercontent.com/x` (hostname is `evil.com`), `http://lh3.googleusercontent.com` (scheme).

### Data model (`data-model.md` equivalent)

- **No DynamoDB change.** `ProviderMetadata.avatar` (`user.py:28`) remains the store of record.
- **Derived value**: `_select_avatar(user: User) -> str | None` — pure, reused by both response builders.
- **Response model additions (contracts)**:
  - `OAuthCallbackResponse` (`auth.py:1472`): add `picture: str | None = None`.
  - `UserMeResponse` (`response_models.py:50`): add `picture: str | None = None`.
- **Frontend type**: `User.pictureUrl?: string` (`frontend/src/types/auth.ts`).

### API contracts

`GET /api/v2/auth/me` → `UserMeResponse` gains:
```json
{ "picture": "https://lh3.googleusercontent.com/a/....=s96-c" }   // or null
```
`POST /api/v2/auth/oauth/callback` → `OAuthCallbackResponse` gains the same nullable `picture`. Additive, backward-compatible (all consumers ignore unknown fields; new field nullable).

### Hot-link vs proxy — decision: HOT-LINK

Two ways to get the pixels on screen:

| | Hot-link (browser fetches Google directly) | Proxy (our server fetches, re-serves) |
|---|---|---|
| SSRF surface | **None** — no server-side fetch exists | Real — server fetches an attacker-influenceable URL; needs allowlist + redirect refusal + `Content-Type: image/*` check + size cap (~1 MB) + timeout + no cookie forwarding |
| Privacy | Viewer IP + fetch timing exposed to Google (inherent to any 3rd-party image, same as gravatar); app path leak suppressed via `referrerpolicy="no-referrer"` (FR-011) | Viewer IP hidden from Google; but our Lambda pays the fetch |
| Infra/cost | Zero | New egress + Lambda time; conflicts with the standing no-new-AWS-resources constraint |
| Freshness | URL-stable; Google serves current bytes | Cache-staleness handling needed |

**Recommendation: hot-link.** The avatar host is Google's own CDN (`lh3.googleusercontent.com` in practice — the standard OIDC `picture` host; the suffix allowlist covers `lh4`/`play-lh` variants). The privacy cost is the viewer's IP to Google — a party that already has it (the user just completed a Google OAuth flow in the same browser). Accepting that buys total elimination of the SSRF class instead of mitigating it. The allowlist (R3, backend + client) still gates *which* hosts may be hot-linked, so a spoofed claim can't point the browser at an attacker server. **Forward-guard:** if a proxy is ever introduced (e.g. for caching/resizing), it MUST refuse redirects (`allow_redirects=False`, 3xx → treat as failure), enforce the same exact-suffix host allowlist *after* DNS-rebind-safe resolution, require `Content-Type: image/*`, cap the body (~1 MB), time out fast, and never forward credentials. None of that is built today.

### next/image consideration

`next/image` is **not** involved and is deliberately avoided (R4). No component imports it; `next.config.js` has no `remotePatterns`. Using it would (a) require adding a narrowly-scoped `remotePatterns` for `**.googleusercontent.com`, and (b) route the fetch through the `/_next/image` server-side optimizer — an optimizer-as-open-proxy SSRF surface if ever misconfigured (AR#1 F1/F4), plus Amplify image-optimization cost. A plain `<img referrerpolicy="no-referrer">` sidesteps all of that. If image optimization is wanted later, revisit with the scoped `remotePatterns` only.

### Frontend design

- New `frontend/src/components/ui/avatar.tsx` — `<Avatar src?, name?, size, className>`: renders `<img src referrerPolicy="no-referrer" onError=…>` when `src` present AND passes the client-side host allowlist; else initials from `name`; else existing generic `<User>` glyph. Fixed circular dimensions, `object-cover`, no layout shift. Fallback is text/glyph (never an `<img>`) to avoid an error loop.
- `mapUserMeResponse` / `mapOAuthCallbackResponse` (`lib/api/auth.ts:84,104`): add `pictureUrl: response.picture ?? undefined`; add `picture: string | null` to the two raw interfaces (`:24–34`, `:40–60`).
- `auth-store.ts` restore path (`:164–176`, OAuth/Cognito restore from `profile.pictureUrl`) and OAuth sign-in path thread `pictureUrl`. Guest (`:119`) and anonymous (`:180`) paths set no picture. Tier-upgrade (`use-tier-upgrade.ts:96–97`) and broadcast (`use-auth-broadcast.ts:46–47`, `:70–71`) spread the existing user object, so `pictureUrl` survives those paths with no change (verified 2026-07-24).
- `user-menu.tsx`: replace the two generic `<div><User/></div>` blocks (`:78–80` trigger, `:103–105` header) with `<Avatar src={user?.pictureUrl} name={displayName} size=…>`.
- CSP / `next.config.js`: **no change** (R5; plain `<img>`, no `next/image`).

### Quickstart (verification)

1. Backend unit: `_select_avatar` returns URL for a Google `provider_metadata`; `None` for the four lookalike/scheme spoofs; correct provider selection by `last_provider_used`; fallback when last provider has no avatar.
2. Backend unit: `/auth/me` and callback responses include `picture` (present + null cases; additive/backward-compatible).
3. Frontend unit (Vitest): Avatar renders `<img>` with `referrerPolicy="no-referrer"` for allowlisted src; falls back to initials on missing/non-allowlisted src and on `onError`; guest → no `<img>`. Mapper maps `picture`→`pictureUrl`.
4. E2E (Playwright, Amplify): real Google login → assert `<img>` in UserMenu with googleusercontent src; reload → still present (**gated on Feature 1384**).

## Project Structure

### Documentation (this feature)

```text
specs/1380-oauth-avatar-picture/
├── spec.md              # complete (+ Adversarial Review #1 + Clarifications)
├── plan.md              # this file (+ Adversarial Review #2)
└── tasks.md             # (+ Adversarial Review #3)
```
(research/data-model/contracts folded inline; feature too small to warrant separate files.)

### Source Code (repository root)

```text
src/lambdas/
├── dashboard/
│   ├── auth.py              # ADD _select_avatar() near _mask_email (~:2016); ADD picture field to OAuthCallbackResponse (:1472); set picture= in the callback return (:2434) — one kwarg
│   └── router_v2.py         # /auth/me handler (:2152): pass picture=_select_avatar(user) into UserMeResponse (:2183)
└── shared/
    ├── models/user.py       # (read-only reference; no change — provider_metadata.avatar :28 already exists)
    └── response_models.py   # ADD picture: str | None to UserMeResponse (:50)

frontend/src/
├── types/auth.ts            # ADD pictureUrl?: string to User (:8–25)
├── lib/api/auth.ts          # add picture to raw UserMeResponse (:24–34) + OAuthCallbackResponse (:40–60); map picture -> pictureUrl in both mappers (:84, :104)
├── stores/auth-store.ts     # thread pictureUrl through restoreSession (:164–176) + OAuth sign-in
├── components/ui/avatar.tsx # NEW shared Avatar (img + no-referrer + onError fallback + client allowlist)
└── components/auth/user-menu.tsx  # use <Avatar> in trigger (:78–80) + dropdown header (:103–105)
frontend/next.config.js      # NO CHANGE (plain <img>, no next/image remotePatterns; no CSP emitted today — R5)

tests/unit/dashboard/        # test__select_avatar + response shape (backend)
frontend/src/**/*.test.tsx   # Avatar + mapper unit tests
frontend/tests/e2e/*.spec.ts # Amplify Google-login avatar E2E (reload path gated on 1384)
```

**Structure Decision**: Web app, customer dashboard only. Backend touch confined to `dashboard/` + shared response model; frontend touch confined to `frontend/src`. No `src/dashboard/` (HTMX) involvement.

## Complexity Tracking

No constitution violations. Table intentionally empty.

## Merge-Hotspot Note (cross-feature)

`src/lambdas/dashboard/auth.py::handle_oauth_callback` is concurrently modified by **1380 (this)**, **1381**, and **1383**. To keep merges serializable:
- This feature adds exactly: (a) the `picture` field on `OAuthCallbackResponse` (model at `:1472`, after `last_provider_used` `:1495`), (b) a new pure helper `_select_avatar` (append near `_mask_email` `:2016`, NOT inside the callback), (c) `picture=_select_avatar(user)` as one kwarg in the single existing `OAuthCallbackResponse(...)` return (`:2434`).
- No reordering, no new branches, no changes to the token-exchange / linking logic those features touch.
- Recommend the owner serialize merges and re-run backend unit tests after each rebase.

---

## Adversarial Review #2

Posture: hunt for drift between spec.md (incl. AR#1 + Clarifications) and this plan, and for internal plan inconsistency. Verify every FR maps to a design element and no design element invents scope.

### Cross-artifact consistency (FR → design coverage)

| FR | Covered by plan element | OK |
|---|---|---|
| FR-001 (picture in callback resp) | R6, `OAuthCallbackResponse.picture`, structure `auth.py:2434` | ✅ |
| FR-002 (picture in /me resp) | `UserMeResponse.picture`, `router_v2.py:2183` handler | ✅ |
| FR-003 (select by last_provider_used) | R2, `_select_avatar` | ✅ |
| FR-004 (backend host/scheme allowlist, exact-suffix, fail-closed) | R3, Allowlist design (urlparse hostname endswith) | ✅ |
| FR-005 (nullable/default null) | Phase 1 contracts (`str | None = None`) | ✅ |
| FR-006 (frontend pictureUrl type + mappers) | Frontend design, `types/auth.ts`, `lib/api/auth.ts` | ✅ |
| FR-007 (store propagation incl. restore) | Store design; Clarification Q4 confirms upgrade/broadcast auto-preserve | ✅ |
| FR-008 (render in trigger + header) | `Avatar` + `user-menu.tsx` wiring (:78/:103) | ✅ |
| FR-009 (fallback initials/generic) | R7, `Avatar` fallback | ✅ |
| FR-010 (onError → fallback, no layout shift, non-img fallback) | `Avatar` onError, fixed dims, text/glyph fallback | ✅ |
| FR-011 (no-referrer, no credentials) | R4, `<img referrerpolicy="no-referrer">` | ✅ |
| FR-012 (render-side allowlist / forward-guard CSP+remotePatterns) | R4/R5 + client allowlist in Avatar; next/image consideration | ✅ |
| FR-013 (no image request for guests) | `Avatar` renders no `<img>` when no src; guests have null picture | ✅ |
| FR-014 (single shared Avatar component) | `components/ui/avatar.tsx` | ✅ |
| FR-015 (minimal localized backend diff) | R6, Merge-Hotspot Note | ✅ |

Every FR maps to at least one design element. No design element introduces scope beyond the spec.

### Drift findings

**D1 (LOW → resolved): allowlist wording alignment.**
Spec FR-004 now specifies the parsed-hostname exact-suffix rule; plan R3 + Allowlist design state the same rule with the leading dot and the four rejected examples. The frontend defense-in-depth (`new URL().hostname`) mirrors the backend. Consistent. No change.
*Provenance (salvaged from the worktree draft's AR#2):* in the earlier draft pass this area carried a **MEDIUM** drift — R5 was phrased as "add a CSP `img-src` allowance" as though a CSP existed, which would have sent an implementer chasing (or inventing) a nonexistent header. That was resolved by a plan second pass amending R5 to forward-guard-only. Recorded here because CSP phrasing is a demonstrated error-prone spot for this feature; reviewers should re-check it on any future edit.

**D2 (LOW → resolved): "initials" vs generic glyph.**
Spec notes the current UI is a generic `<User>` glyph, not true initials. Plan R7 derives initials from displayName and keeps the glyph as last-resort. SC-002 ("0 broken-image icons") is satisfied by either fallback. No contradiction.

**D3 (LOW → noted): no separate research.md/data-model.md.**
Plan folds Phase 0/1 inline and says so. tasks.md must not reference missing files. Carried to Stage 7.

**D4 (LOW → resolved via Dependencies): reload verification depends on 1384.**
Spec SC-003 / US1 scenario 2 depend on Feature 1384 for the end-to-end reload. Plan Summary + Quickstart step 4 mark the E2E reload as gated on 1384; the `/auth/me` picture surfacing (FR-002) is this feature's own prerequisite and is independently unit-testable. Consistent.

### Internal consistency

- Constitution Check PASS consistent with "no new AWS resources / read-only DynamoDB / no logging of URL / httpOnly session unchanged". ✅
- File list in Project Structure matches Phase 1 design and spec's cited (re-verified) lines: `auth.py:1472/2016/2434`, `response_models.py:50`, `router_v2.py:2152/2183`, `user.py:28/111/114`, `types/auth.ts:8–25`, `lib/api/auth.ts:24/40/84/104`, `auth-store.ts:119/164/180`, `user-menu.tsx:57/78/103`. ✅
- Merge-Hotspot Note line references match spec's cited `auth.py` lines. ✅

### Gate

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 0 | — |
| LOW | 0 open | D1/D2/D4 resolved; D3 noted for Stage 7 |

**Gate result: PASS.** No MEDIUM+ drift; line citations re-verified against the main worktree. Proceeding to Tasks.

### Addendum (2026-07-24 worktree reconciliation)

Post-gate edits from reconciling the divergent worktree draft (`.claude/worktrees/agent-a7bc7836fc7e73b90/…`): (a) added the explicit **Hot-link vs proxy** decision table (decision unchanged — hot-link was already implied by R4; now stated with the privacy tradeoff and proxy forward-guard requirements); (b) restored the D1 CSP-drift provenance note; (c) added verified `use-tier-upgrade.ts`/`use-auth-broadcast.ts` citations to the store design. No FR/SC/design change; gate result unaffected.
