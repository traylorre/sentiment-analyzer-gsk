# Feature Specification: OAuth Avatar / Profile Picture in UserMenu

**Feature Branch**: `1380-oauth-avatar-picture`
**Created**: 2026-07-23 (line citations re-verified against main worktree 2026-07-24)
**Status**: Draft
**Input**: User description: "After Google sign-in on the customer frontend (Next.js on Amplify), the UserMenu shows the user's name but NO profile picture (a generic person glyph renders, not even initials). Google's OpenID id_token carries a `picture` claim. Surface it end-to-end and render the avatar with graceful fallback to initials, SSRF-safe."

**Target: Customer Dashboard (Next.js/Amplify)** — `frontend/` + `src/lambdas/dashboard/`. This feature does NOT touch the HTMX admin dashboard (`src/dashboard/`).

> **Sub-feature B of the 1394 set (2026-07-24).** Research (`specs/1394-frontend-routing-session/research.md`) confirms this is an INDEPENDENT root cause (RC-C: avatar persisted but never surfaced) — kept as its own feature, not folded into 1394. **Coordination (research.md §5):** (1) `user-menu.tsx` is edited here (avatar render `:78-80`, `:103-105`) AND by 1394 (nav `router.push` at `:49/:131/:142`) — keep hunks non-overlapping, review together. (2) `auth-store.ts restoreSession` (`:164-176`) is edited here (thread `pictureUrl`) AND by 1384 (single-flight rewrite) — land 1384 first or coordinate the hunk. (3) SC-003 "avatar survives reload" depends on 1384 restoring the OAuth session; gate that E2E behind 1384.

## Context & Confirmed Gaps *(investigation, cite file:line — re-verified in main worktree)*

The Google profile picture is a URL in the OIDC `picture` claim (host: `*.googleusercontent.com`). Tracing the value end-to-end reveals the pipeline is broken in three places, and one place already partially works:

1. **Backend extraction/persistence — PARTIALLY PRESENT.**
   `handle_oauth_callback` already extracts the claim: `avatar=claims.get("picture")` at `src/lambdas/dashboard/auth.py:2373` (existing-user path) and `:2402` (new-user path). It is persisted into per-provider metadata by `_link_provider`, which accepts `avatar` (`auth.py:2479`), builds `ProviderMetadata(... avatar=avatar ...)` at `src/lambdas/dashboard/auth.py:2552`, and writes `provider_metadata`/`last_provider_used` to DynamoDB (`:2561`, `:2569–2574`). The `ProviderMetadata.avatar` field exists at `src/lambdas/shared/models/user.py:28`, and `User.provider_metadata` at `user.py:111`.
   **Gap:** the `User` model has **no top-level picture field** — the avatar lives only inside `provider_metadata[provider].avatar`. There is no accessor that returns "the current user's avatar URL". `User.last_provider_used` (`user.py:114–115`, commented "for avatar selection") is the only avatar-adjacent field ever surfaced.

2. **API responses — MISSING (primary root cause).**
   - `OAuthCallbackResponse` (`src/lambdas/dashboard/auth.py:1472`) has fields `status, email_masked, auth_type, tokens, …, role, verification, linked_providers, last_provider_used` (last field at `:1495`) — **no picture/avatar**. The constructed response at `:2434–2453` never includes it.
   - `UserMeResponse` (`src/lambdas/shared/response_models.py:50`) exposes `auth_type, email_masked, configs_count, max_configs, session_expires_in_seconds, role, linked_providers, verification, last_provider_used` (last at `:62`) — **no picture/avatar**. The `/api/v2/auth/me` handler `get_current_user` (`src/lambdas/dashboard/router_v2.py:2152`) builds the response at `:2183–2194` and never reads `provider_metadata`.
   - Net effect: the persisted avatar URL **never leaves the backend**. Even a correct frontend has nothing to render.

3. **Frontend type / mapping / render — MISSING.**
   - The `User` TS interface (`frontend/src/types/auth.ts:8–25`) has `email` (`:11`), `lastProviderUsed` (`:20`), etc., but **no `picture`/`avatarUrl` field**.
   - The raw response interfaces `UserMeResponse` (`frontend/src/lib/api/auth.ts:24–34`) and `OAuthCallbackResponse` (`:40–60`) carry `last_provider_used` but **no `picture`**. `mapUserMeResponse` (`:84`) and `mapOAuthCallbackResponse` (`:104`) map federation fields (e.g. `lastProviderUsed` at `:93`/`:130`) but **no avatar**.
   - The auth store `restoreSession` path (`frontend/src/stores/auth-store.ts:164–176` Cognito/OAuth restore; guest restore `:119`; anonymous fallback `:180`) populates `User` without any avatar.
   - `UserMenu` (`frontend/src/components/auth/user-menu.tsx`) renders a **generic `<User>` lucide glyph** in the trigger (`:78–80`) and the dropdown header (`:103–105`) — there is **no `<img>`, no initials computation, no fallback logic**. `displayName` derives from `user?.email?.split('@')[0]` (`:57–59`). (The reported "shows name but no picture" matches: the icon is a generic person glyph, not initials.)
   - `next.config.js` (`frontend/next.config.js:4–5`) sets `images.formats` but has **no `images.remotePatterns`** — so `next/image` would reject `googleusercontent.com` at runtime. No component imports `next/image` today (only `middleware.ts:40,45` reference `_next/image` in the matcher).
   - `frontend/src/middleware.ts` sets `X-Frame-Options` (`:22`) and `Referrer-Policy` (`:24`) but emits **no `Content-Security-Policy`** — so a plain remote `<img>` is not CSP-blocked today.

**Conclusion:** the fix must add a nullable `picture` field at the backend response layer (both `/auth/oauth/callback` and `/auth/me`), a pure `_select_avatar(user)` helper that host-validates the URL, the matching frontend `pictureUrl` type + mappings + store threading, and a shared `Avatar` render component with initials + broken-image fallback. No CSP change and no `next/image`/`remotePatterns` change are needed today (forward-guard only).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Google user sees their profile picture after sign-in (Priority: P1)

A user signs in with Google on the Amplify customer frontend. The Google account has a profile photo. After the OAuth callback completes, the UserMenu trigger (top nav) and the dropdown header show the user's actual Google profile picture instead of a generic icon.

**Why this priority**: This is the entire point of the feature and the owner-flagged post-login QA defect. It is the MVP.

**Independent Test**: Complete a real Google login on `https://main.d29tlmksqcx494.amplifyapp.com/`; assert the UserMenu renders an `<img>` whose `src` is the Google `picture` URL, verified on the real Amplify frontend.

**Acceptance Scenarios**:

1. **Given** a Google account with a profile photo, **When** the user completes OAuth sign-in, **Then** the UserMenu trigger and dropdown header display that photo as a circular avatar.
2. **Given** the same user reloads the page (session restored via `/refresh` → `/auth/me`), **When** the app re-initializes, **Then** the avatar still renders (picture survives session restore, not only the fresh callback). *(End-to-end reload verification depends on Feature 1384 session persistence — see Dependencies.)*
3. **Given** the picture URL is present, **When** the avatar renders, **Then** it is served over HTTPS from a Google-owned host and no other host.

### User Story 2 - Graceful fallback to initials when there is no picture (Priority: P1)

Email/magic-link users, guest/anonymous users, GitHub users without an avatar, or a Google user whose image URL fails to load must see a clean initials (or generic) avatar — never a broken-image icon.

**Why this priority**: Fallback is co-critical with P1. A broken image is worse than the current generic icon, so shipping the picture without fallback would regress UX.

**Independent Test**: Sign in as an email/magic-link user (no picture) and confirm initials render; separately, force the image `onError` (bad URL) and confirm it falls back to initials without a broken-image glyph.

**Acceptance Scenarios**:

1. **Given** a user with no picture URL (email/guest/GitHub-no-avatar), **When** the UserMenu renders, **Then** it shows an initials avatar derived from the display name/email (or the existing generic icon when no name is available).
2. **Given** a user with a picture URL that returns 404/blocked, **When** the `<img>` fires `onError`, **Then** the component swaps to the initials fallback with no layout shift and no broken-image icon.
3. **Given** an anonymous/guest session, **When** the UserMenu renders, **Then** no external image request is made (guests have no picture).

### User Story 3 - Avatar shows consistently everywhere the user is represented (Priority: P3)

Wherever the user avatar appears (currently only the UserMenu trigger + dropdown header; future settings page), it uses one shared Avatar component so behavior and fallback are identical.

**Why this priority**: Consistency/maintainability. Not required for MVP but prevents divergent copies.

**Independent Test**: Grep confirms a single `Avatar` component is the only place that renders the picture `<img>`; the UserMenu trigger and header both use it.

**Acceptance Scenarios**:

1. **Given** the shared Avatar component, **When** it is used in the trigger and the dropdown header, **Then** both render identical picture/fallback behavior at their respective sizes.

### Edge Cases

- **Picture URL host is not Google-owned** (spoofed/malicious `picture` claim): backend MUST NOT surface a non-allowlisted host; frontend MUST NOT render a non-allowlisted host. See Security / Adversarial Review #1.
- **Subdomain lookalike hosts**: `evil-googleusercontent.com` and `evilgoogleusercontent.com.evil.com` MUST be REJECTED. The allowlist is an **exact-suffix match on the parsed hostname** (`hostname == "googleusercontent.com"` OR `hostname.endswith(".googleusercontent.com")`), never a substring/`in`/regex check on the raw URL string.
- **Picture URL uses `http://` or a non-URL string**: treated as "no picture" → fallback.
- **Very large image / slow load**: circular container has fixed dimensions; image is `object-cover`; a slow load shows the fallback until `onLoad` (no layout shift either way).
- **Picture changed on Google side** (user updated their photo): app shows whatever URL was captured at last login/refresh; it refreshes on next `/auth/me`. Stale-until-next-login is acceptable (documented; see Clarifications).
- **Email masking interaction**: initials must be derivable even though the API returns `email_masked` (`j***@example.com`). The initial letter of the masked local-part is still meaningful; `displayName` already uses `email.split('@')[0]` (`user-menu.tsx:57–59`).
- **CSP**: rendering a remote image requires `img-src` to permit `https://*.googleusercontent.com`. No CSP is emitted by the customer frontend today (`middleware.ts` sets no `Content-Security-Policy`), so this is a forward-guard: if a CSP is later introduced it MUST include that host; otherwise the image is blocked → fallback (no crash).
- **Referrer leakage**: the avatar `<img>` request to googleusercontent.com MUST carry `referrerpolicy="no-referrer"` to avoid leaking the app URL.
- **Anonymous → Google upgrade mid-session**: after upgrade the avatar should appear once the store user is repopulated from the callback/`/me`.
- **Non-Google future providers** (GitHub): out of scope for the allowlist here; GitHub users fall back to initials. Adding `avatars.githubusercontent.com` later reuses the same allowlist mechanism.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend MUST expose the current user's profile picture URL in the `/api/v2/auth/oauth/callback` response (`OAuthCallbackResponse`), sourced from the picture already persisted in `provider_metadata`.
- **FR-002**: The backend MUST expose the current user's profile picture URL in the `/api/v2/auth/me` response (`UserMeResponse`), so the avatar survives page reload / session restore.
- **FR-003**: The backend MUST select the picture from the provider indicated by `last_provider_used` (falling back to any `provider_metadata` entry that has a non-null avatar) so the "current" avatar is returned when multiple providers are linked.
- **FR-004**: The backend MUST only surface picture URLs whose scheme is `https` AND whose parsed hostname is exactly `googleusercontent.com` or ends with `.googleusercontent.com` (exact-suffix match). Any other value MUST be returned as null (fail-closed). The check MUST parse the URL (`urllib.parse.urlparse`) and compare the `hostname`; it MUST NOT use a substring/`in`/regex test on the raw URL string. No open image proxy is introduced.
- **FR-005**: The picture field MUST be optional/nullable in every response model and default to null for email, guest/anonymous, and GitHub-without-avatar users.
- **FR-006**: The frontend `User` type MUST include an optional `pictureUrl` (camelCase) field, and the callback + `/me` mappers MUST populate it from the snake_case `picture` API field (null → undefined).
- **FR-007**: The auth store MUST carry `pictureUrl` on the user object through OAuth sign-in and session restore (`restoreSession` → `/auth/me`). Tier-upgrade and broadcast paths that spread `...currentUser` preserve it automatically.
- **FR-008**: The UserMenu MUST render the picture as a circular avatar in both the trigger (`user-menu.tsx:78–80`) and the dropdown header (`:103–105`) when `pictureUrl` is present and allowlisted.
- **FR-009**: When `pictureUrl` is absent, the UI MUST render a graceful fallback (initials derived from display name/email, or the existing generic icon) — never a broken-image icon.
- **FR-010**: When the picture `<img>` fails to load (`onError`), the UI MUST swap to the same fallback with no layout shift. The fallback MUST NOT itself be an `<img>` (no error loop).
- **FR-011**: The avatar image request MUST use `referrerpolicy="no-referrer"` and MUST NOT send credentials/cookies to the image host.
- **FR-012**: The render path MUST NOT allow arbitrary remote hosts. A client-side host allowlist (same exact-suffix rule as FR-004) MUST gate rendering as defense-in-depth on top of the backend fail-closed. If `next/image` is ever adopted, `next.config.js` `images.remotePatterns` MUST be scoped to `https` + `**.googleusercontent.com`; if a CSP is ever added, its `img-src` MUST permit `https://*.googleusercontent.com`. Neither change is required today (plain `<img>`, no CSP emitted).
- **FR-013**: Guest/anonymous sessions MUST NOT trigger any external image request.
- **FR-014**: The picture rendering MUST be implemented once in a shared `Avatar` component reused by the UserMenu trigger and dropdown header (and available for future surfaces).
- **FR-015**: The backend change to `handle_oauth_callback` MUST be minimal and localized to picture surfacing (a single added response field + one kwarg + a small pure helper placed OUTSIDE the callback body), because `auth.py`/`handle_oauth_callback` is concurrently edited by Features 1381 and 1383 (merge hotspot).

### Key Entities *(include if feature involves data)*

- **ProviderMetadata.avatar** (existing, `user.py:28`): the persisted per-provider picture URL. Source of truth; no schema change required.
- **User.picture (derived, not stored)**: a computed "current avatar URL" chosen from `provider_metadata[last_provider_used].avatar` with fallback across linked providers. Not a new DynamoDB attribute — derived at response-build time.
- **UserMeResponse.picture / OAuthCallbackResponse.picture (new response fields)**: nullable string; the only new API surface.
- **Frontend `User.pictureUrl` (new TS field)**: nullable; drives Avatar rendering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a real Google login on the Amplify frontend, 100% of Google accounts that have a profile photo render that photo in the UserMenu (trigger + dropdown), verified on `https://main.d29tlmksqcx494.amplifyapp.com/`.
- **SC-002**: 0 broken-image icons across all auth types: Google-with-photo, Google-without-photo, email/magic-link, GitHub, and anonymous all render either a photo or an initials/generic fallback.
- **SC-003**: The avatar persists across a full page reload (session restore) — present on first paint after re-initialization, not only immediately after the callback. *(Depends on Feature 1384 session persistence for the end-to-end reload path.)*
- **SC-004**: 0 external image requests are issued for anonymous/guest sessions.
- **SC-005**: No picture URL from a non-`googleusercontent.com` host is ever rendered, verified by unit tests feeding spoofed/lookalike `picture` claims (`https://evil-googleusercontent.com/x`, `https://evilgoogleusercontent.com.evil.com/x`, `https://evil.com/googleusercontent.com/x`, `http://lh3.googleusercontent.com/x`) and asserting a null/absent avatar field.
- **SC-006**: The backend diff to `handle_oauth_callback` is confined to picture surfacing (a single kwarg + a helper outside the callback) so it can be serialized against Features 1381/1383 at merge time.

## Assumptions

- The persisted `provider_metadata[provider].avatar` for existing Google users already contains a valid URL (the extraction at `auth.py:2373/2402` predates this feature). Users who signed in before extraction existed will get their picture on next login/refresh — acceptable.
- Google profile photo URLs are hosted on `*.googleusercontent.com` and are served over HTTPS without auth. (Google may append size params like `=s96-c`; the URL is used as-is.)
- No new AWS resources; the Dashboard Lambda environment is frozen (irrelevant — no env change needed). httpOnly session model unchanged.
- GitHub avatars are out of scope for the allowlist in this feature (GitHub users fall back to initials).

## Out of Scope

- Proxying, caching, resizing, or re-hosting the image on our infrastructure.
- Storing a new top-level `avatar` DynamoDB attribute (we derive from existing `provider_metadata`).
- Uploading/editing a custom avatar.
- The HTMX admin dashboard (`src/dashboard/`).
- GitHub avatar rendering (fallback to initials is acceptable for now).

## Dependencies

- **Feature 1384 (session persistence)**: US1 scenario 2 / SC-003 ("avatar survives reload") is only end-to-end verifiable once the OAuth session reliably restores across reload. The backend `/auth/me` picture surfacing (FR-002) is a prerequisite this feature owns; the reload restoration itself is 1384's. **Status 2026-07-24: 1384 is MERGED (#944) — this gate is CLEAR; the reload E2E can run ungated.**
- **Features 1381 / 1383 (merge hotspot)**: both edit `handle_oauth_callback` in `auth.py`. FR-015 keeps this feature's callback diff to one kwarg + an out-of-body helper to keep merges serializable.

---

## Adversarial Review #1

Attack surface reviewed: SSRF via picture URL, allowlist bypass on subdomain tricks, open-redirect/XSS via the URL, IP/referrer leak from `<img>`, broken-image UX, PII/GDPR of avatar URL, CSP breakage, stale avatar, multi-provider ambiguity, merge blast radius. Reviewer posture: assume the spec is wrong and try to break it.

### Findings

**F1 — SSRF / arbitrary-host image render (Severity: HIGH → mitigated).**
The `picture` claim is attacker-influenceable in principle (a malicious/compromised IdP response, a token tampered before signature verification, or a future non-Google provider). Rendering `<img src={picture}>` with an unvalidated host lets an attacker (a) exfiltrate the viewer's IP/timing to an arbitrary server, (b) turn any server-side fetch (e.g. `next/image` optimizer) into an SSRF probe of internal hosts, (c) leak referrer.
- **Edit applied:** FR-004 mandates a host allowlist enforced **at the backend response layer** (fail-closed to null) using `urlparse` + `hostname` exact-suffix match on `.googleusercontent.com`, `https`-only. FR-012 enforces the same allowlist on the render side (client-side gate; `remotePatterns`/CSP only if those are ever adopted), explicitly forbidding arbitrary hosts and any proxy. Defense in depth: both surfaces validate; backend is authoritative. SC-005 adds spoofed + lookalike unit tests. Residual: LOW.

**F2 — Allowlist bypass via subdomain/suffix trickery (Severity: HIGH → mitigated).**
The classic way this ships broken: `url.endswith("googleusercontent.com")` (matches `evil-googleusercontent.com`), or `"googleusercontent.com" in url` (matches `evil.com/googleusercontent.com/x` and `evilgoogleusercontent.com.evil.com`). Any of these pass a naive check.
- **Edit applied:** FR-004 requires parsing the URL and testing the **hostname** with `hostname == "googleusercontent.com" or hostname.endswith(".googleusercontent.com")` — the leading dot on the suffix is load-bearing (rejects `evil-googleusercontent.com`), and comparing the parsed hostname (not the raw string) rejects `evil.com/googleusercontent.com/x` (hostname is `evil.com`) and `evilgoogleusercontent.com.evil.com` (hostname does not end with `.googleusercontent.com`). SC-005 pins all four cases as tests. Residual: LOW.

**F3 — Open-redirect / XSS via the URL (Severity: MEDIUM → mitigated).**
Could the URL be `javascript:`/`data:` and execute, or redirect? An `<img src>` does not execute `javascript:` in modern browsers, but `data:` could render arbitrary image bytes, and a non-`https` scheme is disallowed anyway.
- **Edit applied:** FR-004's `https`-only scheme check rejects `javascript:`, `data:`, `http:`, `file:`, etc. at the backend before the value is ever returned. The frontend renders it only as an `<img src>` (never `href`, never `innerHTML`), so no redirect/script sink exists. Residual: LOW.

**F4 — Referrer / credential / IP leakage to image host (Severity: MEDIUM → mitigated).**
An `<img>` to googleusercontent.com by default sends a `Referer` header (leaks the app path) and, via a `next/image` optimizer, could route through a server-side fetch. Even for allowlisted Google hosts, the viewer's IP is exposed to Google on render (unavoidable for any 3rd-party image), but referrer/path leakage is avoidable.
- **Edit applied:** FR-011 mandates `referrerpolicy="no-referrer"` and no credentials. FR-012/Clarification Q2 choose a plain `<img>` over `next/image` to avoid any server-side fetch path. The IP-to-Google exposure is inherent to showing a Google-hosted avatar and is accepted (same as any site rendering a gravatar). Residual: LOW.

**F5 — Broken-image UX regression (Severity: MEDIUM → mitigated).**
Shipping the picture without an `onError` handler makes a dead URL render the browser's broken-image glyph — strictly worse than today's generic icon.
- **Edit applied:** FR-010 requires `onError` → initials fallback with no layout shift and a non-`<img>` fallback (no error loop); SC-002 asserts 0 broken-image icons across all auth types. Residual: LOW.

**F6 — CSP blocks the image → silent breakage (Severity: MEDIUM → mitigated).**
If Amplify/Next middleware later enforces a CSP without `img-src https://*.googleusercontent.com`, the image is blocked.
- **Edit applied:** Clarification Q1 established **no CSP exists today** (`middleware.ts:18–32` sets other headers but no `Content-Security-Policy`). FR-012 records the forward-guard; Edge Cases note a CSP block degrades to the fallback, not a crash. Residual: LOW (fails safe).

**F7 — PII / GDPR of avatar URL (Severity: LOW → accepted with note).**
The Google picture URL is personal data. We already persist it in `provider_metadata.avatar` (pre-existing). This feature adds no new storage — it surfaces the already-stored value and holds it in client memory (within the existing user object). No new retention obligation beyond what Features 1162/1180 established.
- **Edit applied:** Assumptions/Out-of-Scope clarify no new stored attribute. Owner question Q-A: confirm the existing `provider_metadata.avatar` is covered by any future account-deletion path. Residual: LOW.

**F8 — Stale avatar after user changes Google photo (Severity: LOW → accepted).**
The app renders the URL captured at last login/refresh; stale until next `/auth/me`. Documented as acceptable (no live userinfo re-fetch per page load — adds latency/quota). Residual: LOW.

**F9 — Multi-provider avatar ambiguity (Severity: LOW → mitigated).**
A user linking Google + GitHub has two `provider_metadata` entries. FR-003 selects by `last_provider_used` (`user.py:114–115`, "for avatar selection"), fallback to first entry with a non-null avatar. Residual: LOW.

**F10 — Merge-hotspot blast radius (Severity: MEDIUM, process → mitigated).**
`handle_oauth_callback` is edited by 1380/1381/1383 simultaneously. FR-015 constrains this feature's callback change to a single `picture=_select_avatar(user)` kwarg on the existing `OAuthCallbackResponse(...)` return (`auth.py:2434`) plus a pure helper placed near `_mask_email` (`:2016`), NOT inside the callback. SC-006 makes reviewability-in-isolation a criterion. Residual: LOW.

### Edits Applied to Spec

- Split the SSRF finding into F1 (arbitrary host) and F2 (suffix/subdomain bypass); hardened FR-004 to a parsed-hostname exact-suffix rule with the leading dot; enumerated the four lookalike test cases in SC-005.
- Added FR-011 (referrer/no-credentials), FR-012 (render-side allowlist / forward-guard CSP & remotePatterns), FR-003 (multi-provider selection), FR-015 (minimal localized diff), FR-010 non-`<img>` fallback clause.
- Expanded Edge Cases (subdomain lookalikes, http/non-URL → no picture, CSP block → fallback, referrer, stale avatar, non-Google providers).
- Added Dependencies section for Feature 1384 (reload) and 1381/1383 (merge).
- Recorded owner questions Q-A (deletion-path coverage) and Q-B (is a CSP enforced in prod today? — self-answered No in Q1).

### Gate

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | F1, F2 mitigated to LOW |
| MEDIUM | 0 | F3/F4/F5/F6/F10 mitigated to LOW |
| LOW | accepted/mitigated | F7, F8 accepted; F9 mitigated |

**Gate result: PASS — 0 CRITICAL / 0 HIGH remaining.** Proceed to planning.

---

## Clarifications

Session 2026-07-23 — up to 5 targeted questions, self-answered from the codebase where possible.

**Q1 — Is a Content-Security-Policy enforced on the customer (Amplify/Next) frontend today, and would it block a remote `<img>`?**
**A (self-answered):** No CSP is set. `frontend/src/middleware.ts` sets `X-Content-Type-Options` (`:21`), `X-Frame-Options` (`:22`), `X-XSS-Protection` (`:23`), `Referrer-Policy` (`:24`), and `Permissions-Policy` (`:27–28`) — but **no `Content-Security-Policy`** header. So a plain `<img src="https://…googleusercontent.com/…">` renders without a CSP block. FR-012's CSP allowance is a forward-guard: only needed if a CSP is later introduced; add `img-src https://*.googleusercontent.com` at that point. (Note: `src/lambdas/shared/middleware/security_headers.py:58` sets `img-src 'self' data: https:` for the Lambda-served HTML admin dashboard — already permissive, and out of scope.) Resolves owner-question Q-B. *(Header list + line citations salvaged from the worktree draft and re-verified 2026-07-24.)*

**Q2 — Plain `<img>` or `next/image`?**
**A (self-answered):** Plain `<img>`. `next.config.js:4–5` has no `remotePatterns`, no component imports `next/image`, and `middleware.ts:45` excludes `_next/image` from the matcher; using `next/image` would require config plus a server-side optimizer fetch (the AR#1 F1/F4 SSRF surface). Decision R4 stands: `<img referrerpolicy="no-referrer" onError=…>`.

**Q3 — When a user has linked multiple providers, which avatar is "current"?**
**A (self-answered):** Select by `User.last_provider_used` (`user.py:114–115`, explicitly commented "for avatar selection"), falling back to the first `provider_metadata` entry with a non-null avatar. Encoded in FR-003 / R2.

**Q4 — Does the avatar survive a page reload, and where must `pictureUrl` be threaded?**
**A (self-answered):** Session restore rebuilds `User` from `/auth/me` in `restoreSession` (`auth-store.ts:164–176`), so `/auth/me` MUST carry `picture` (FR-002) or the avatar vanishes on reload. Tier-upgrade (`use-tier-upgrade.ts:96–97` `setUser({ ...currentUser, … })`) and broadcast (`use-auth-broadcast.ts:46–47`, `:70–71` `setUser({ ...user, … })`) paths spread the existing user, so `pictureUrl` is preserved automatically there — no extra work beyond the restore/signIn mapper additions. (Bonus: the broadcast refresh handler spreads `...profile` from `getProfile()`, so once the mapper carries `pictureUrl` it also refreshes on cross-tab refresh.) End-to-end reload correctness also depends on Feature 1384. *(Concrete file:line citations salvaged from the worktree draft and re-verified 2026-07-24.)*

**Q5 — With `email_masked` (`j***@example.com`), can initials still be derived?**
**A (self-answered):** Yes. `displayName` already uses `user?.email?.split('@')[0]` (`user-menu.tsx:57–59`), yielding `j***` for a masked email; the first character uppercased ("J") is a usable initial. No new `name`/`given_name` claim is needed for MVP (that would require adding a field end-to-end and is out of scope).

### Deferred (cannot be fully answered from code) — for owner

- **Q-A (PII deletion coverage):** Is the persisted `provider_metadata[provider].avatar` covered by an account-data deletion/erasure path? **Finding:** there is currently **no account-deletion flow in `src/lambdas/dashboard/`** (no `delete_user`/`delete_account` anywhere in the module — grep re-verified 2026-07-24). So the question is moot today; when a deletion flow is built, it should delete the whole `User` item (avatar included). Low priority, no action for this feature.

---

## Worktree Draft Reconciliation (2026-07-24)

A divergent older draft existed at `.claude/worktrees/agent-a7bc7836fc7e73b90/specs/1380-oauth-avatar-picture/`. Diffed line-by-line against this (newer) copy. Verdict: this copy is the hardened superset — the worktree-only lines are almost entirely pre-hardening versions of paragraphs rewritten here (weaker FR-004 allowlist wording, stale `auth.py` line numbers `:2365/:2394/:2426/:2544` from before #942/#944 landed, merged F1/F2 SSRF finding, single spoof test instead of four). Salvaged into this copy: (1) full middleware header list + `security_headers.py:58` citation in Q1; (2) `use-tier-upgrade.ts:96` / `use-auth-broadcast.ts:46,70` citations in Q4 (re-verified exact); (3) the `delete_user`/`delete_account` grep evidence in Q-A. Everything else worktree-only was deliberately superseded, not lost.
