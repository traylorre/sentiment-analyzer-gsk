# Milestone 1: Verifiable User-Auth (non-SSE)

Goalposts document. No code here. Branch context: `Q-pin-hcl2`, campaign docs in
`docs/cleanup-pristine/`. Inputs: R1 auth inventory, R2 owner OAuth checklist, R3
screenshot-infra gap analysis, R4 milestone sweep (none exist in GitHub), and the
cleanup board's fix lane (16 cards).

## Objective

Two auth flows on the deployed customer dashboard
(`https://main.d29tlmksqcx494.amplifyapp.com/`) provably work, where "provably" means
a verifier agent attests to screenshot evidence, not that a test suite printed green:

1. **Guest session, with restore.** Cold load creates an anonymous session; F5 keeps
   the same `user_id` instead of minting a new DynamoDB user row per reload
   (today's behavior, R1 defect 1).
2. **OAuth sign-in (Google), with restore.** Sign in via Cognito-federated Google,
   land back with a non-Guest identity, survive reload, and reach `/alerts` without
   the middleware bouncing you to signin (today it bounces everyone, R1 defect 3.1).

SSE is excluded entirely. Magic-link is excluded except for a possible trivial UI
descope (open question Q-M1-4). Milestone is done when every Definition-of-Done
artifact below exists, is sealed per trust contract item 7, and the verifier's
`attestation.json` — hash-referenced from a signed evidence commit — says pass on
all steps.

## Trust contract

The failure mode this milestone exists to kill: an agent reports "auth works" and the
evidence is its own assertion. Nothing in this milestone is accepted as done on a
claim. The contract:

1. **Evidence is a verification directory**, produced by the Playwright run itself:
   `frontend/test-results/verification/{run-id}/{project}/` containing named
   screenshots plus one `manifest.json` per spec.
2. **Screenshots are deterministic and named**: `{spec-slug}-{NN}-{step-name}.png`
   (e.g. `auth-guest-01-landing.png`), captured by a shared `shot()` helper on every
   run, pass or fail, full page.
3. **The manifest is written by the same helper.** Per step it records: file name,
   `expected_ui_state` (prose, informational only — the pass criterion lives in
   WI-2's canonical expected-state table, see item 5), `page_url` at capture time,
   main-document HTTP status, **every request to `/api/v2/auth/*` since the previous
   step as `{method, path, status}` — 2xx responses included, not only failures** —
   plus any other API responses >= 400, console errors and `pageerror` events since
   the previous step, a DOM probe result (named selector presence or text),
   timestamp, `test_file:line`, `target: preprod | localhost-mock`, and an
   `interception` field: the `shot()` fixture wraps `page.route()` /
   `context.route()` and records whether ANY route handlers were registered on the
   page or context at capture time. Each spec's manifest also carries a
   `forbidden_requests` array (`[{method, path, status, max_count}]`, e.g.
   `POST /api/v2/auth/anonymous` 201 with `max_count: 1` across the whole guest
   spec) so negative-space evidence — "no second anonymous session was minted after
   reload", "no anonymous fallback fired during OAuth" — is a machine-checkable
   manifest entry the verifier must evaluate, never prose.
4. **Target of record is preprod Amplify.** Milestone evidence must show
   `target: preprod`. Localhost-mock evidence is labeled as such and never counts
   toward a DoD. This is the customer dashboard, never the Lambda HTMX admin surface
   (CLAUDE.md two-dashboards rule).
5. **A verifier agent that did not write or run the tests** walks the manifest, views
   each screenshot, and emits `attestation.json`: per step
   `{step, verdict: pass|fail|suspicious, reason}` plus an overall verdict. A step
   passes only if the screenshot matches the **canonical expected-state table in
   WI-2's convention doc** (seeded from the DoD bullets in this document — the
   manifest's `expected_ui_state` is informational context only, because the
   implementer writes it and a lenient phrasing must not be able to lower the bar)
   AND the url, status, and console sidecars are clean AND every
   `forbidden_requests` entry holds. The verifier **hard-fails any
   `target: preprod` step whose `interception` field shows route handlers were
   active at capture** — a mocked run against the real Amplify URL is exactly the
   screenshot-attests-render-not-function failure this milestone exists to kill,
   and the in-repo mocking helpers (`frontend/tests/e2e/helpers/mock-api-data.ts`)
   are one shared-fixture import away. Verification runs use `trace: 'on'`, and the
   verifier opens the raw Playwright trace for at least the restore-critical steps
   (`auth-guest-03`, `auth-oauth-04`) and spot-checks the trace's real network
   entries against the manifest, so the implementer-built helper is never the sole
   ground truth. A pretty error page with a 200 fails on the DOM probe; a
   redirect-to-signin fails on `page_url`.
6. **Assertions passing is necessary, never sufficient.** The milestone closes on
   attestation, not on exit code 0.
7. **Evidence is sealed, not just produced.** `frontend/test-results/verification/`
   is gitignored build output; nothing in it counts until committed. Each WI's DoD
   ends with an append-only, GPG-signed commit to the campaign docs tree
   (`docs/cleanup-pristine/evidence/m1/`) containing either the verification dir
   itself or, if size demands, a SHA-256 hash manifest covering every artifact in it
   (screenshots, `manifest.json`, `attestation.json`). An `attestation.json` is
   valid only when its hash is referenced from that signed commit — a plain JSON
   file any agent, including the implementer, can rewrite is not a completion
   certificate. This resolves former open question Q-M1-5 now, before WI-3 starts,
   not after milestone close.

## Work items (ordered)

Dependencies flow downward. WI-4 can run in parallel with WI-3 once WI-1 lands.
WI-5's code work can also start then, but its DoD capture needs WI-3's restored
guest session, and its former upgraded-user artifact now lives in WI-6 (see WI-5).
WI-6 is blocked on the owner actions section regardless of code readiness.

### WI-1: Screenshot capture infrastructure — Effort: M

Today Playwright captures nothing, not even on failure (`playwright.config.ts:17-20`
has no `screenshot` key; `trace: 'on-first-retry'` never fires under the PR job's
`--retries=0`). Build the evidence pipeline:

- Config: `screenshot: 'on'`; `trace: 'retain-on-failure'` for ordinary runs and
  `trace: 'on'` for verification runs — the verifier reads the trace as
  helper-independent ground truth (trust contract item 5) (R3 gaps 1-2).
- `shot()` helper in `frontend/tests/e2e/helpers/`: auto-numbered names, known
  output dir, project-namespaced paths so a future multi-browser run cannot collide
  (R3 gaps 3, 13).
- Manifest generation folded into the helper (R3 gap 4), including the full
  `/api/v2/auth/*` request log (method/path/status, 2xx included), the
  `forbidden_requests` evaluation, and the `interception` field: the shared fixture
  wraps `page.route()` / `context.route()` so any handler registration is recorded
  at capture time (trust contract items 3 and 5).
- Console/pageerror/network>=400 capture generalized from the chaos-only pattern in
  `helpers/chaos-helpers.ts:423,466` into a shared fixture (R3 gap 5).
- Document the preprod-target invocation
  (`PREPROD_FRONTEND_URL=https://main.d29tlmksqcx494.amplifyapp.com npx playwright test`)
  in `frontend/tests/e2e/README.md` (R3 gap 11).

**DoD artifacts:** one demo run against preprod producing
`verification/{run-id}/Desktop Chrome/` with `infra-smoke-01-landing.png`, a
`manifest.json` whose entry shows `page_url` on the Amplify domain, main status 200,
`target: preprod`, `interception: false`, the auth request log and
`forbidden_requests` fields present, and a checked-in JSON schema the manifest
validates against (schema covers the item-3 fields including `interception` and
`forbidden_requests`). Evidence sealed per trust contract item 7. No attestation
required yet (WI-2 defines the verifier).

*Depends on:* nothing. Goes first; every later DoD consumes it.

### WI-2: Verifier convention — Effort: S

Write the convention doc plus `attestation.json` schema (R3 gap 10): who the
verifier is (a separate agent, not the implementer), what it consumes (manifest +
screenshots + sidecars + raw Playwright trace, never just PNGs), the pass rule from
the trust contract, and where attestations live (inside the same run's verification
dir, sealed per item 7). The convention doc carries the **canonical expected-state
table**: one row per DoD step in this document, stating the expected UI state,
required auth-request-log entries, `forbidden_requests` entries, and DOM probe — the
verifier judges against this table, never against the manifest's implementer-written
`expected_ui_state` prose (trust contract item 5). The doc also specifies the
verifier's hard-fail rules (interception active on a preprod step; any
`forbidden_requests` violation) and the trace spot-check procedure for
restore-critical steps.

**DoD artifacts:** the convention doc including the canonical expected-state table;
the attestation schema; one sample `attestation.json` produced by a verifier agent
over WI-1's demo run, with a per-step verdict and reason. Sealed per trust contract
item 7.

*Depends on:* WI-1.

### WI-3: Guest session green (restore across reload) — Effort: L (was M; backend scope folded in)

The frontend half is what R1 sized as small: call `refreshToken()` at session init
(`use-session-init.ts:57-66`, currently a TODO comment) and drop the
`tokens.refreshToken` guard in `auth-store.ts:247-249` that makes
`POST /api/v2/auth/refresh` unreachable from the entire frontend. Fall back to
`signInAnonymous()` on 401 — noting that this fallback repaints a Guest header that
screenshots identically to success, which is exactly why the DoD below leans on a
machine-checked `forbidden_requests` entry rather than pixels. This also stops the
per-reload DynamoDB user-row churn that orphans configurations (R1 defect 3.4).

The backend half is not an open question — former Q-M1-3 is closed by inspection.
`POST /api/v2/auth/anonymous` returns `json_response(201, ...)` with no Set-Cookie
(`src/lambdas/dashboard/router_v2.py:361-386`, return at `:383`); the refresh cookie
is only set by magic-link verify (`:516-531`) and the OAuth callback (`:597-606`).
So the guest F5 path has no cookie for `POST /api/v2/auth/refresh` to consume, and a
frontend-only fix cannot pass this WI's own DoD. WI-3 therefore includes the backend
change: set the httpOnly refresh cookie (and its CSRF-cookie pair) on the anonymous
path, mirroring the magic-link verify pattern at `:516-531`. No new AWS resources,
but it requires a preprod dashboard-Lambda deploy before evidence capture — that
deploy is a WI-3 dependency and is included in the resized effort. Instrument the
guest-path specs with `shot()` steps as part of this item.

**DoD artifacts** (preprod, attested by WI-2 verifier):
- `auth-guest-01-landing.png`: header UserMenu shows "Guest"; manifest's auth
  request log shows `POST /api/v2/auth/anonymous` 201 (cold load), zero console
  errors, `interception: false`.
- `auth-guest-02-menu-open.png`: open menu with session-remaining chip and the
  anonymous "Sign in with email" upsell item.
- `auth-guest-03-post-reload.png`: after F5, same `user_id` recorded in the
  manifest's DOM/network probe, `POST /api/v2/auth/refresh` 200 in the auth request
  log, and the spec's `forbidden_requests` entry
  (`POST /api/v2/auth/anonymous` 201, `max_count: 1` across the whole spec)
  evaluated and holding — the "no new anonymous 201 after reload" claim is a
  manifest field the verifier checks, not prose.
- `manifest.json` + `attestation.json` with all guest steps pass, sealed per trust
  contract item 7.

*Depends on:* WI-1, WI-2, and a preprod backend deploy of the dashboard Lambda
carrying the anonymous-path Set-Cookie change.

### WI-4: Next.js bump to >= 14.2.25 (CVE-2025-29927) — Effort: S

Fix-lane card pulled IN. `frontend/package.json:34` pins 14.2.21, in the vulnerable
range for the `x-middleware-subrequest` middleware bypass, and Amplify runs the
self-hosted Next server so the bypass applies. R1 rates practical severity low
(middleware auth is inert anyway, see WI-5) but it is a one-line lockfile change on
the exact surface this milestone certifies, and it clears a critical Dependabot
alert.

**DoD artifacts:** `evidence/next-version.txt` in the verification dir showing the
installed version >= 14.2.25, plus the WI-3 guest screenshot set re-captured green
against the bumped build (proves no regression), attested and sealed per trust
contract item 7.

*Depends on:* WI-1 (for evidence capture). Parallel with WI-3.

### WI-5: Middleware cookie reconciliation (guest gate provable) — Effort: M — ✅ DONE

**Status: DONE (preprod-attested + sealed 2026-07-23).** Merged to main via PR #929
(`c46c6f3`), Amplify build #383. Independent verifier attested `auth-guest-04` PASS
against the canonical row on preprod; sealed under
`docs/cleanup-pristine/evidence/m1/wi5-preprod/2026-07-23T20-24-45-535Z/`. Latent
OAuth-restore bug fixed on the way (upgraded restore never set the user because
`/me` omits `user_id`; now sourced from `/refresh`) — de-risks WI-6
`auth-oauth-04`. A separate config-delete snake_case bug the fix unmasked is
tracked in PR #930.

R1 defect 3.1: `middleware.ts:48-67` gates `/admin` and `/alerts` on cookies
(`sentiment-access-token`, `sentiment-is-anonymous`) that nothing in `frontend/src`
sets (the setter died with Feature 1145). Every user, including valid OAuth users,
gets redirected off `/alerts`. Two candidate fixes: set the cookies for real, or
strip the middleware gating and rely on backend Bearer auth plus the client-side
role check the middleware itself acknowledges at `middleware.ts:16-17`. Which one is
open question Q-M1-2 — **resolved 2026-07-23: strip** (see Open questions; the fix
wires the latent Feature-1165 `ProtectedRoute` with `requireUpgraded` around
`/alerts` and `/admin`, and the guest redirect becomes client-side
`router.replace` to `/auth/signin?redirect=%2Falerts&upgrade=true`).

Scope note: the upgraded-user proof (`auth-oauth-05-alerts-page.png`) does NOT live
here. On preprod the only working upgrade path is Google OAuth — magic-link dispatch
does not exist (see out of scope) and guest sessions are by definition not upgraded —
so that artifact is owner-blocked and belongs in WI-6, where the BLOCKED label is
honest. Keeping it here would make WI-5 secretly owner-blocked while the doc claims
only WI-6 is. WI-5's own DoD is achievable with nothing but WI-3's guest session.
Optional accelerator if we want an /alerts render before owner creds land: mint an
upgraded-session token directly in DynamoDB per the Feature 1223 test pattern
(boto3 token query) and capture the page with the manifest explicitly labeled
`synthetic-upgrade`; such a capture is supplementary and never substitutes for
WI-6's real OAuth-path `auth-oauth-05`.

**DoD artifacts** (attested): `auth-guest-04-alerts-redirect.png` showing a guest
still gets redirected off `/alerts`, with manifest `page_url` showing the redirect
destination (proves the gate works, not that it was deleted outright — unless Q-M1-2
resolves to client-side-only gating, in which case this step's row in WI-2's
canonical expected-state table changes accordingly). `manifest.json` +
`attestation.json` pass, sealed per trust contract item 7.

*Depends on:* WI-3 (needs a working restored guest session to capture against);
code work can start once WI-1 lands. The middleware fix itself is a prerequisite
for WI-6's `auth-oauth-05` artifact, but no WI-6 evidence gates WI-5.

### WI-6: OAuth green — Effort: M — BLOCKED on owner actions

Code side is wired end to end per R1; what is missing is real credentials in the
Secrets Manager placeholders and the `cognito_identity_providers` tfvars line (R2).
Until the owner completes the checklist below, `/api/v2/auth/oauth/urls` returns no
providers and the signin page shows the email-only fallback. Once unblocked:
instrument the OAuth specs with `shot()` steps and run the full flow against
preprod. Scope acceptance to Google; the GitHub IdP is wired to the GitHub Actions
OIDC issuer (`modules/cognito/github.tf:22`) and is expected to fail token exchange
(R2 known gap, open question Q-M1-1).

**DoD artifacts** (preprod, attested):
- `auth-oauth-01-signin-buttons.png`: Google button visible on `/auth/signin`
  (proves `ENABLED_OAUTH_PROVIDERS` non-empty); manifest's auth request log shows
  `GET /api/v2/auth/oauth/urls` 200 with a non-empty provider list.
- `auth-oauth-02-callback-return.png`: `/auth/callback` completing; auth request
  log shows `POST /api/v2/auth/oauth/callback` 200.
- `auth-oauth-03-identity.png`: header UserMenu with non-Guest display name or
  masked email, session chip present in open menu.
- `auth-oauth-04-post-reload.png`: after F5, same identity retained (WI-3's restore
  path exercised by an OAuth session; auth request log shows `/refresh` 200, and the
  spec's `forbidden_requests` entry — zero `POST /api/v2/auth/anonymous` 201 during
  the OAuth spec — holds, so "no anonymous fallback fired" is machine-checked).
- `auth-oauth-05-alerts-page.png` (moved here from WI-5 because it requires an
  upgraded user, and upgrading requires the owner-provisioned OAuth path): the
  signed-in Google user reaching `/alerts` rendered, manifest `page_url` ending in
  `/alerts` (not `/auth/signin`), DOM probe hitting a named alerts-page selector.
- `manifest.json` + `attestation.json` all pass, sealed per trust contract item 7.
- `evidence/verify-oauth-deploy.txt`: captured output of
  `scripts/verify-oauth-deploy.sh preprod` passing.

*Depends on:* WI-1, WI-2, WI-3, WI-5 (the middleware fix must have landed for
`auth-oauth-05`), and the owner-actions checklist. Provider consent screens live on
Google's domain; the manifest records the redirect legs by URL and status rather
than screenshotting third-party pages.

## Owner actions (blocking)

WI-6 cannot start until these are done. Full copy-paste detail lives in the R2
checklist; summary (~15 min, preprod first, account `218795110243`):

1. Create a Google OAuth web client with redirect URI
   `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`
   and consent scopes `email`, `profile`, `openid`.
2. (Optional for M1) Create a GitHub OAuth App with the same callback URL. Known
   caveat: the Cognito GitHub IdP points at the GitHub Actions OIDC issuer, so this
   flow is expected to fail until a follow-up fix; do not debug it in the console.
3. `aws secretsmanager put-secret-value` for
   `preprod/sentiment-analyzer/google-oauth` (and `github-oauth` if doing 2), JSON
   keys exactly `client_id` / `client_secret`.
4. Approve the one-line repo change adding
   `cognito_identity_providers = ["Google", "GitHub"]` to
   `infrastructure/terraform/preprod.tfvars` (without it Cognito rejects authorize
   requests even after the IdPs exist).
5. Trigger `terraform apply` for preprod via the GitHub Actions UI (state-locking
   policy). Risk note: open Issue #491 reports dashboard Lambda Terraform state
   drift, which can surface during this apply; if the plan shows unexpected dashboard
   Lambda changes, stop and resolve the import first.
6. Run `./scripts/verify-oauth-deploy.sh preprod` and confirm the Google button
   appears on `https://main.d29tlmksqcx494.amplifyapp.com/auth/signin`.
7. Answer open question Q-M1-1 (is Google-only sufficient to call OAuth green?).

## Fix-lane card decisions (all 16)

Titles verbatim from the board.

| Card | Auth? | Decision | Justification |
|---|---|---|---|
| CRITICAL: next.js middleware auth bypass (CVE-2025-29927) | Yes | **IN** (WI-4) | One-line bump on the exact middleware surface M1 certifies; clears a critical alert. |
| Session restore on reload unimplemented — /refresh never called at init | Yes | **IN** (WI-3) | The single defect blocking both guest-restore and OAuth-restore acceptance. |
| Q13: Magic-link emails never send — no send_email_callback provider or notification-Lambda invoker | Yes | OUT | Full email-dispatch feature plus a POST/GET verb fix; not trivially descoped into M1 (see Q-M1-4 for the UI-hide option). |
| Issue #501: Audit anonymous access on all endpoints | Yes | OUT | Breadth-first authz audit; M1 is depth on two flows, and mid-milestone audit findings would churn scope. Sequence it after M1's evidence pipeline exists. |
| Q8: User alerts never fire — alert_evaluator.py unwired, paid-tier feature silently dead | Adjacent | OUT | Alert evaluation backend, not auth; M1 only needs the /alerts page reachable (WI-5/WI-6), not alerts firing. |
| LB-2 VERIFIED: /api/v2/runtime hands dev browsers the raw IAM-locked SSE Function URL | SSE | OUT | SSE excluded by milestone charter; dev-scoped only. |
| /api/v2/runtime DRIFT: prod SSE resolves via API Gateway, not the intended CloudFront path | SSE | OUT | SSE excluded by milestone charter. |
| Q6: by_tag GSI live-queried but never populated — tag queries silently return empty | No | OUT | Data-plane query gap, no auth surface. |
| LB-1 VERIFIED: Cross-source dedup merge never fires — Tiingo tz-aware vs Finnhub naive timestamps in DynamoDB SK | No | OUT | Ingestion correctness, unrelated to auth. |
| No CI job runs pre-commit — bandit, detect-secrets, trivy, checkov, mypy all dark server-side | No | OUT | Validation hardening lane, orthogonal to auth flows. |
| pip-audit runs in CI but cannot gate a merge (advisory-only) | No | OUT | Same lane as above. |
| Issue #491: Dashboard Lambda Terraform state drift | No | OUT | Infra state hygiene, not auth; flagged as a risk on owner action 5 since the OAuth apply crosses it. |
| CRITICAL: torch RCE via torch.load (CVE-2025-32434) | No | OUT | Analysis Lambda inference path, not auth. |
| CRITICAL: basic-ftp vulnerability (CVE-2026-27699) | No | OUT | Transitive tooling dep at repo root, not auth. |
| CRITICAL: vitest vulnerability (CVE-2026-47429) | No | OUT | Dev-time test runner, not auth. |
| Dependabot backlog: 30 high, 46 moderate, 13 low alerts | No | OUT | Batch upgrade campaign; only the middleware CVE bump is pulled into M1 despite the next x7 overlap. |

Non-card auth items R1 surfaced, for completeness: middleware phantom cookies
(defect 3.1) becomes WI-5, IN. SSE same-origin proxy 401 (defect 3.2) OUT, SSE.
Anonymous user-row churn (defect 3.4) IN, subsumed by WI-3. Dead `sig` plumbing
(defect 3.5) OUT, harmless dead weight for a later cleanup pass. Anonymous-path
refresh-cookie gap (former Q-M1-3, confirmed at `router_v2.py:383`) IN, subsumed by
WI-3's backend half.

## Out of scope

- **All SSE work.** Streaming endpoints, the same-origin proxy 401, CloudFront SSE
  routing drift, and any `EventSource` verification.
- **Magic-link as a working flow.** Email dispatch does not exist (three-layer
  confirmation in R1), verify is a POST-to-GET mismatch, and the API lies with
  `status="email_sent"`. Only the trivial UI descope is under consideration
  (Q-M1-4).
- **GitHub OAuth acceptance.** Credentials get provisioned alongside Google, but
  the OIDC issuer wiring is known-broken; fixing it is a follow-up feature.
- **CI plumbing beyond M1's needs** (R3 gaps 7-9): verification-dir uploads with
  30-day retention, fixing deploy.yml's silently-empty artifact upload, a scheduled
  full-suite preprod run, and the sanity-gate blocking policy. M1 attests from
  local preprod-target runs; CI enforcement is the natural M2. (Distinct from
  evidence sealing per trust contract item 7, which is in scope: sealed evidence
  lives in signed commits to the campaign docs tree, not in CI artifact storage.)
- **Instrumenting the full E2E suite** with step screenshots (R3 gap 6 beyond the
  auth specs), and the Python admin-suite screenshot capability (gap 12, wrong
  surface for this milestone).
- **Endpoint authz audit** (Issue #501) and all other OUT cards above.

## Standing constraints

- **No new AWS resources without asking the owner first.** The OAuth secrets
  already exist as placeholders; the tfvars line and apply are owner-approved
  actions. Anything beyond that (new tables, new Lambdas, new queues) needs an
  explicit ask. WI-3's backend Set-Cookie change modifies an existing Lambda only.
- **No pushes to remote until the work is green locally.** Pre-push checklist per
  CLAUDE.md (security alerts, `make validate`, unit tests) still applies when a
  push does happen.
- **All verification targets the CUSTOMER dashboard** on Amplify
  (`https://main.d29tlmksqcx494.amplifyapp.com/`), never the Lambda HTMX admin
  dashboard. Every manifest entry carries the `target` field so mock or admin
  evidence can never masquerade as preprod evidence, and the `interception` field
  so mocked-against-Amplify runs cannot either.
- **Campaign rules carry over:** GPG-signed commits, append-only history,
  `file:line` citations for claims, comments are suspects and never evidence.
  Evidence sealing (trust contract item 7) is these rules applied to the
  verification artifacts themselves.

## Open questions

- **Q-M1-1: CLOSED (owner decision, 2026-07-22).** Google-only OAuth is sufficient
  to call WI-6 green. GitHub OAuth (`oidc_issuer` wired to the GitHub Actions
  issuer, `modules/cognito/github.tf:22`, will fail token exchange) becomes a
  tracked follow-up card on the cleanup board, out of M1.
- **Q-M1-2: CLOSED (owner decision, 2026-07-23).** Strip the middleware cookie
  gating; middleware keeps security headers only. `/alerts` and `/admin` gate
  client-side by wiring the latent `ProtectedRoute` component
  (`frontend/src/components/auth/protected-route.tsx`, built in Feature 1165,
  never mounted) with `requireUpgraded`; the backend Bearer + role middleware
  remains the sole security boundary. Rationale: the HttpOnly refresh cookie
  lives on the API Gateway domain and can never reach Amplify's middleware, so
  any middleware-readable cookie must be JS-written on the Amplify domain — the
  exact pattern Feature 1145 deleted as CVSS 8.6. Both options are equally
  secure (spoofing either gate yields an empty shell + backend 403); a flag
  cookie buys only a sub-second flash at the cost of permanently synced shadow
  state. Canonical `auth-guest-04` row amended in the same commit as this
  closure, before capture.
- **Q-M1-3: CLOSED.** `POST /api/v2/auth/anonymous` does not set the httpOnly
  refresh cookie — `json_response(201, ...)` with no Set-Cookie at
  `src/lambdas/dashboard/router_v2.py:383` (handler `:361-386`); only magic-link
  verify (`:516-531`) and the OAuth callback (`:597-606`) set it. Resolution: the
  backend Set-Cookie change is folded into WI-3's scope (with the CSRF-cookie
  pair, mirroring the verify pattern), WI-3 resized M → L, and the preprod Lambda
  deploy added to WI-3's dependencies.
- **Q-M1-4:** Magic-link descope: hide `MagicLinkForm` on `/auth/signin` now (small
  frontend change, stops the UI advertising a flow that silently does nothing), or
  leave it visible until the flow is actually built? The `status="email_sent"`
  response is a lie either way; hiding the form at least stops users from hitting it.
- **Q-M1-5: CLOSED.** Resolved as trust contract item 7, effective before WI-3
  starts: attested runs are archived via append-only GPG-signed commits under
  `docs/cleanup-pristine/evidence/m1/` (full dir or SHA-256 hash manifest), and an
  attestation only counts when hash-referenced from such a commit.
