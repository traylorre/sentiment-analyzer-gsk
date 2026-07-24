# Spec: M1 WI-6 — Verifiable Google OAuth Enablement (preprod)

**Feature:** 1375-wi6-google-oauth-enablement
**Milestone:** GitHub Milestone #1 "Verifiable user-auth (non-SSE)", Work Item 6 (final item; M1 is 5/6).
**Branch:** `wi6-enable-google-idp` (holds staged HOLD commit `9629502` / draft PR #932).
**Target:** Customer Dashboard (Next.js/Amplify) on **preprod** — `https://main.d29tlmksqcx494.amplifyapp.com/`.
**Status:** DRAFT (Stage 1 of battleplan).

---

## 1. Context & Framing

This is **not** greenfield OAuth. The OAuth implementation already shipped and merged across
Features 1169–1193 (federation fields, callback route, state/CSRF), 1245/1373 (button render
gating), and 1370 (Secrets-Manager wiring in Terraform). WI-6 is **enablement + verifiable
attestation** of that existing code on preprod — nothing more.

The owner has been hitting recurring "whack-a-mole" OAuth errors. Root cause, confirmed by live
probe this session: **Google OAuth is four coupled parts, none currently wired**, and testing
between steps guarantees an error because the parts only become consistent at a single
`terraform apply`.

### The four coupled parts (live state, verified 2026-07-23)
| Part | Mechanism | Current state |
|---|---|---|
| 1. Google OAuth client | Google Cloud console (web app; redirect = Cognito `/oauth2/idpresponse`) | **not created** (owner-gated) |
| 2. Secret `preprod/sentiment-analyzer/google-oauth` | `{"client_id","client_secret"}` JSON | **empty** (`client_id=""`) |
| 3. Cognito Google IdP | `modules/cognito/google.tf`, `count` gated on tfvars list | **absent** (`[]`) |
| 4. Lambda `ENABLED_OAUTH_PROVIDERS` | `main.tf:138`, derived from secret's `client_id != ""` | **unset** |

### Exact error captured (live probe + owner-confirmed screen)
- Normal app flow: Google button **correctly hidden** — `GET /api/v2/auth/oauth/urls` → `{"providers":{},"state":""}` (200). No error reachable here.
- Manual hosted-UI (`identity_provider=Google`, my probe): **`Login option is not available. Please try another one`** — 302 → 401 on the Cognito `/login` page, because the pool has zero IdPs.
- **Owner's actual screen (confirmed 2026-07-23):** `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/error?error=Invalid%20state` — "An error was encountered with the requested page. / Invalid state". Cognito rejecting the OAuth `state` (CSRF) param at its own domain.

Multiple symptoms, one root cause (nothing wired); the symptom depends on the entry path and on stale
Cognito-domain state cookies (states are single-use — a refresh/back-button replay throws "Invalid
state"). This is the whack-a-mole. The fix is **not** reactive config poking — it is landing all four
parts in one apply, then testing through the real app button in a **fresh incognito context**.

### Terraform reality (confirmed in current tree)
Feature 1370's secret-wiring is **already merged**: `main.tf:119` reads the secret via
`data.aws_secretsmanager_secret_version.google_oauth`; `local.google_oauth.client_id`
(with a `try()` → empty fallback) feeds both `local.enabled_oauth_providers` (→ Lambda env)
and the Cognito module's `google_client_id/secret`. **The only remaining infra delta is one
tfvars line** — `cognito_identity_providers = ["Google"]` — already staged in HOLD commit `9629502`.

---

## 2. User Stories

**US-1 (Owner — credential provisioning).** As the repo owner, I provision a Google OAuth web
client and populate the `google-oauth` secret myself (secrets never enter chat or git), following
a single crisp runbook, so that a subsequent deploy lights up all four parts together.

**US-2 (Customer — sign in with Google).** As a customer on the preprod dashboard, I see a
"Continue with Google" button on `/auth/signin`, complete Google consent, land back authenticated
with a non-Guest identity that survives a page reload, and can reach `/alerts`.

**US-3 (Independent verifier — attestation).** As a verifier who did **not** implement or run the
tests, I judge the `auth-oauth-01..05` evidence against the canonical expected-state table, spot-check
the raw Playwright trace for the restore-critical step, and seal a signed attestation — so "done"
means independently proven, not self-asserted.

---

## 3. Functional Requirements

- **FR-1 (single-apply consistency).** Enabling Google MUST make all four coupled parts consistent
  in one `terraform apply`. The secret MUST be populated **before** the apply that adds the tfvars
  line, so the IdP and `ENABLED_OAUTH_PROVIDERS` land together. (deploy.yml auto-applies on merge to
  main → merging PR #932 IS the apply.)
- **FR-2 (owner runbook).** Produce one authoritative, copy-pasteable runbook for the two
  owner-gated steps (Google console client; `put-secret-value`) with the **exact** redirect URI,
  scopes, secret id, and JSON shape. No secrets in the runbook examples.
- **FR-3 (tfvars enablement).** The infra change is exactly `cognito_identity_providers = ["Google"]`
  (Google-only per Q-M1-1; **never** add "GitHub" — its IdP points at the GitHub Actions OIDC issuer
  and is known-broken). Delivered via draft PR #932, marked ready **only after** FR-1's secret is populated.
- **FR-4 (deploy verification).** After the apply, `./scripts/verify-oauth-deploy.sh preprod` MUST
  pass (Lambda env non-empty, Cognito IdP present, Lambda↔Cognito consistency, `/oauth/urls` 200 with
  ≥1 provider). Its stdout is captured as `evidence/.../verify-oauth-deploy.txt`.
- **FR-5 (instrumented specs).** Author `frontend/tests/e2e/auth-oauth.spec.ts` implementing
  canonical rows `auth-oauth-01..05` using the existing `helpers/verification` harness
  (`verify.shot`, `verify.forbid`, response listener — **no route interception**, banned on preprod).
  Row 01 (button visible + `GET /oauth/urls 200` non-empty) is fully headless-automatable and has
  no identity dependency. Rows 02–05 run inside the **single interactive capture** of FR-6.
- **FR-6 (real-identity capture — HEADED, INTERACTIVE, single-window).** Rows 02–05 require a
  genuine completed Google identity. Google bot-detects automated browsers on its consent screen, and
  every headless path to a `POST /oauth/callback 200` is either blocked or a false-green via Cognito
  hosted-UI session reuse. Therefore rows 02–05 are captured in **one headed run** where the owner
  performs **one real interactive Google login** in a **clean browser context** (cookies cleared, so
  the Google leg genuinely runs — no silent session reuse). All of rows 02→03→04→05 are captured in
  that same run from that same login, so their identity is **lineage-tied** to the real Google auth
  (rows 03–05 otherwise prove only "a non-guest session," not "Google"). The run is attested as
  `capture_mode: interactive` — it is **not** headless-repeatable, and the attestation reason states
  the session origin is the row-02 Google login. No route interception; no mocked auth on preprod
  (convention hard-fail). See **Risk R-1** for provisioning and cadence.
- **FR-7 (independent attestation + seal — NO token-bearing artifacts sealed).** Run with
  `VERIFICATION=1` (trace on) so the verifier can spot-check row-04 restore from the raw trace. Hand
  the run directory + the verifier convention to an **independent verifier agent** (never the
  implementer). The verifier spot-checks `trace.zip` **locally**, then it is **destroyed — never
  sealed**. Only these are sealed in a GPG-signed commit under
  `docs/cleanup-pristine/evidence/m1/wi6-preprod/`: `attestation.json`, `{spec}.manifest.json`, the
  step PNGs, and `verify-oauth-deploy.txt`. See **FR-9** for the redaction that makes those safe.
- **FR-8 (pre-apply poison guard).** Add a lightweight CI/script guard (no AWS resource) that **fails
  the plan/apply** if `cognito_identity_providers` contains "Google" while the `google-oauth` secret's
  `client_id` is empty. Converts the EC-1 footgun (a premature #932 merge auto-applying a
  poisoned-empty-creds IdP that `ignore_changes` then can't repair) from "discipline" into a blocked
  merge. Runs in the deploy workflow before `terraform apply`.
- **FR-9 (evidence redaction).** Before sealing, redact secret-bearing fields from the manifest and
  any surviving artifact: row-02 `page_url` `code=` param, and any `access_token`/`id_token`/
  `refresh_token` in captured bodies. The Playwright `storageState`/auth artifacts MUST be
  `.gitignore`d and never placed in a sealed path. A sealed evidence commit must contain **zero live
  credentials** (a signed, append-only commit is the worst possible place for a refresh token).

## 4. Success Criteria (Definition of Done)

DoD = all five canonical rows attested PASS by an independent verifier, plus the verify-script capture.
Rows are authoritative in `docs/cleanup-pristine/m1-verifier-convention.md`:

| Row | Must show | page_url | Required auth log | Probe |
|---|---|---|---|---|
| `auth-oauth-01-signin-buttons` | Google button visible | `/auth/signin` | `GET /oauth/urls 200` (non-empty providers) | Google button selector |
| `auth-oauth-02-callback-return` | Callback completing | `/auth/callback*` **or** `/` (transient nav) | `POST /oauth/callback 200` (**this auth-log leg is the real gate**, not the screenshot URL) | — |
| `auth-oauth-03-identity` | UserMenu non-Guest name / masked email | `/` | none additional | UserMenu text ≠ "Guest"; **same run/login as row 02** |
| `auth-oauth-04-post-reload` | Same identity after F5 | `/` | `POST /refresh 200` | identity == step-03; **TRACE SPOT-CHECK**; forbidden: `anonymous 201` **max_count:1** (one inherent pre-login guest mint — see amendment (d)) |
| `auth-oauth-05-alerts-page` | Alerts page rendered for signed-in Google user | ends `/alerts` | none additional | alerts-page selector; same run/login as row 02 |

**Convention amendment required BEFORE capture (signed commit).** Per the convention, a WI may refine
its own rows via a signed edit to the canonical table — never at attestation time. Before capture, amend
`m1-verifier-convention.md` to record: (a) row-02 `page_url` tolerance `{/auth/callback*, /}` with the
`POST /oauth/callback 200` leg as the gate (the callback page is transient and may have already
redirected by screenshot time; `main_status` may be null on client-side nav); (b) `capture_mode:
interactive` for the oauth spec (not headless-repeatable); (c) rows 03–05 identity must be lineage-tied
to the row-02 login; **(d) row-04 forbidden rule `anonymous 201` `max_count:1` (was "zero")** — the
global root-layout `SessionProvider` (`app/layout.tsx:54`) mints exactly one inherent guest on the
clean-context signin load before login; `forbid` counts spec-wide at teardown and can't be scoped
post-login, so the "no silent re-guest" guarantee is carried by the row-04 identity-equality probe;
**(e) row-02 trace spot-check** — the verifier confirms in the raw trace (before destruction) both
`POST /oauth/callback 200` and that the returned `id_token.iss = accounts.google.com`, proving a real
Google leg rather than a reused Cognito session. This is the compensating control that makes
`capture_mode: interactive` sound (AR#3). This amendment is itself part of WI-6's sealed record.

Plus: `evidence/.../verify-oauth-deploy.txt` captured; overall verifier verdict `pass`;
sealed in a GPG-signed commit; attestation hash-referenced from that commit; **zero live credentials in
the sealed commit** (FR-9).

## 5. Edge Cases & Failure Modes

- **EC-1 early merge (secret empty).** If PR #932 applies while the secret is empty: `google.tf:14`
  `count` gates on the tfvars list only, so a Google IdP **is** created with `client_id=""`;
  `ENABLED_OAUTH_PROVIDERS` stays empty (button still hidden). Result: broken IdP invisible to the app
  but changing the hosted-UI error. **Mitigation:** #932 stays DRAFT until the secret is populated (FR-1).
- **EC-2 `ignore_changes` on `client_secret`.** `google.tf:34` ignores `provider_details.client_secret`
  after create. If the IdP is ever created with an empty/wrong secret, a later secret fix will **not**
  re-push through terraform — requires a resource taint/replace. Runbook must order secret-before-apply
  to avoid ever creating it wrong.
- **EC-3 Issue #491 dashboard-Lambda TF state drift.** If the apply's plan shows unexpected
  `preprod-dashboard` Lambda changes, **stop and import first** — do not let auto-apply churn it.
- **EC-4 WAF integration gate RED (red herring).** `tests/e2e/test_waf_protection.py` returns 200 not
  403 for SQLi/XSS and fails **every** preprod deploy's integration gate. Unrelated to auth; the deploy
  itself SUCCEEDS. Do not be derailed.
- **EC-5 redirect URI mismatch.** Google client's authorized redirect URI must be **exactly**
  `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`
  (Cognito domain, not the Amplify URL). A mismatch yields Google `redirect_uri_mismatch`.
- **EC-6 callback-URL allowlist.** Cognito app-client callback URLs already include
  `https://main.d29tlmksqcx494.amplifyapp.com/auth/callback`; confirm still present post-apply.

## 6. Out of Scope (do not absorb)

- **Prod rollout** (Google prod client, `prod.tfvars`) — separate follow-up (provisioning-plan W2/W10).
- **GitHub IdP** — known-broken (Q-M1-1); never enable.
- **Out-of-charter M1 debt** — WAF SQLi/XSS gate; alerts-API snake_case gap; magic-link descope
  (Q-M1-4). Tracked separately; flag only if one blocks WI-6.
- **Local-dev OAuth** (spec 1323), **frontend error-visibility hardening** (provisioning-plan W11) —
  not required for the preprod DoD.

## 7. Risks (the hard parts, named)

- **R-1 (real Google identity vs. bot-detection) — the central risk.** Google blocks automated
  browsers on its login/consent screen, so rows 02–05 cannot be produced by a repeatable headless run.
  **Mitigation:** headed, interactive, single-window capture (FR-6). The owner performs one real Google
  login (any Google account the owner controls — a throwaway or a dedicated `sentiment-preprod-test@`
  is fine; it is used **interactively once per capture**, not stored as an automation credential).
  **Cadence:** re-run is interactive each time; there is no persisted session to expire between runs
  because each capture starts from a clean context and does a fresh login. **Owner dependency:** the
  Google login account is an owner-gated prerequisite (added to §Owner-gated steps), distinct from the
  OAuth *client* of FR-2.
- **R-2 (credential leak into sealed history).** `trace:'on'` records full bodies incl. refresh
  tokens; the row-02 callback URL embeds a Cognito `code`. A sealed, signed, append-only commit is the
  worst place for these. **Mitigation:** FR-9 redaction + FR-7 (trace spot-checked locally then
  destroyed, never sealed) + `.gitignore` for auth/storageState artifacts.
- **R-3 (false green via session reuse).** A lingering Cognito hosted-UI session cookie can yield
  `POST /oauth/callback 200` with no real Google leg. **Mitigation:** clean browser context per capture
  (cookies cleared) so the Google leg genuinely runs; FR-6.
- **R-4 (poisoned IdP from premature apply).** EC-1/EC-2: one premature "ready" on #932 with an empty
  secret permanently poisons the IdP (`ignore_changes[client_secret]` blocks repair). **Mitigation:**
  FR-8 automated pre-apply guard + #932 stays DRAFT until the secret is populated.
- **R-5 (owner-observed "Invalid state").** Owner hit `/error?error=Invalid state` on the Cognito
  domain. Consistent with the unwired state + a stale single-use state cookie from manual testing.
  **Mitigation:** post-wiring, test only through the real app Google button in a **fresh incognito
  context** (already required by R-3's clean context). **Watch:** if "Invalid state" recurs in a clean
  context through the real app flow *after* enablement, that is a **Feature-1193 OAuth-state (CSRF) bug**,
  not a wiring gap — escalate as a distinct defect at T010 capture, do not silently retry.

## 8. Hard Constraints

- No new AWS resources without asking (the Cognito IdP is created by *existing* module code the tfvars
  line activates — not a net-new hand-authored resource; still, watch the plan).
- All commits GPG-signed. Secrets never in chat or git.
- Trust contract item 7: independent verifier + sealed evidence; implementer never self-attests.
- Owner gates each push/merge cycle and performs the Google-console + `put-secret-value` steps.

## 9. Owner-Gated Prerequisites (blocking; owner performs)

1. **Google OAuth web client** (FR-2): create in Google Cloud console; authorized redirect URI exactly
   `https://preprod-sentiment-218795110243.auth.us-east-1.amazoncognito.com/oauth2/idpresponse`; scopes
   `email profile openid`; capture `client_id` + `client_secret`.
2. **Populate the secret** (FR-1): `aws secretsmanager put-secret-value --secret-id
   preprod/sentiment-analyzer/google-oauth --secret-string '{"client_id":"…","client_secret":"…"}'`
   (owner runs locally; secret never enters chat/git).
3. **Google login account for the interactive capture** (R-1): a Google account the owner controls, used
   interactively once during the FR-6 headed capture. Not an automation credential; not stored.
4. **Mark PR #932 ready → merge** (push-gate): only after step 2; deploy.yml auto-applies.

## Adversarial Review #1

Independent reviewer (separate agent, security-first) attacked spec.md. Findings and resolutions:

| Severity | Finding | Resolution |
|---|---|---|
| CRITICAL | Row 02 (`POST /oauth/callback 200`) not honestly automatable headless — `code` requires a human past Google's bot-detected consent; session-reuse = false green. | **FR-6 rewritten** to headed interactive single-window capture; row 02 gated on the callback POST auth-log leg, `capture_mode: interactive`. Convention amendment required pre-capture. |
| CRITICAL | Rows 03–05 prove only "a non-guest session," not "Google." | FR-6 + DoD table: rows 03–05 **lineage-tied** to the row-02 login (same run/session); attestation states origin. |
| HIGH | `trace:'on'` + sealing bakes a live refresh token / callback `code` into permanent signed history. | **FR-7 + FR-9 added:** trace spot-checked locally then destroyed, never sealed; redact `code`/token fields; `.gitignore` auth artifacts; zero live creds in sealed commit. |
| HIGH | `Risk R-1` was a dangling reference (no Risks section existed). | **§7 Risks added** (R-1..R-4) with concrete mitigations. |
| HIGH | storageState origin unspecified; first-run seeding paradox; no owner for the Google test account. | Design pivoted **off** storageState-seeding to interactive login; §9 adds the Google login account as an owner-gated prerequisite (R-1). |
| MEDIUM | EC-1/EC-2 poison-IdP guarded only by "keep #932 draft" (discipline, not a control). | **FR-8 added:** pre-apply CI guard fails the apply if tfvars has "Google" while the secret `client_id` is empty. |
| MEDIUM | Row-02 `page_url`/`main_status` timing fragility (callback page redirects fast). | DoD table: row-02 `page_url` tolerance `{/auth/callback*, /}`, callback POST is the gate; recorded in the required convention amendment. |
| MEDIUM | Cognito session reuse false green. | **R-3 + FR-6:** clean context per capture, fresh Google leg. |
| LOW | Token expiry mid-run flake; FR-6 under-scoped into one bullet. | Interactive-per-run removes cross-run expiry; FR-6/§9/R-1 split the mechanics out. |
| LOW (cleared) | `verify-oauth-deploy.sh` exists; google.tf count-gate + `ignore_changes` confirmed. | No action; verified, not assumed. |

**Gate: 0 CRITICAL, 0 HIGH remaining.** Both CRITICALs resolved by the interactive-capture pivot;
both token-leak/dangling-risk HIGHs resolved by FR-7/FR-9 and §7. Proceed to Stage 3 (Plan).

## Clarifications

Self-answered from the codebase (not asked interactively). Evidence cited.

| # | Question | Answer | Evidence |
|---|---|---|---|
| C1 | Row-01 Google-button probe selector? | No `data-testid` on the button; probe by accessible name **`Continue with Google`** (`getByRole('button',{name:/Continue with Google/i})` or `text=Continue with Google`). | `oauth-buttons.tsx:65` `label:'Continue with Google'`; rendered `<Button>` (`:78`). |
| C2 | How does row-01 know providers are non-empty? | Buttons render **iff** `hasOAuthProviders` (`availableProviders.length>0`), which comes straight from `GET /oauth/urls`. Button visible ⟺ providers non-empty. Also assert the 200 via the response listener. | `signin/page.tsx:53` `hasOAuthProviders`; `:81` `{hasOAuthProviders && <OAuthButtons/>}`; `:24` `authApi.getOAuthUrls()`. |
| C3 | Row-02 endpoint + terminal route + redirect_uri? | Callback calls `handleCallback(code, provider, state, redirectUri)` → `POST /api/v2/auth/oauth/callback`; on success `router.push('/')`. `redirectUri = origin + pathname` = `https://main.d29…amplifyapp.com/auth/callback` (matches Cognito callback allowlist, EC-6). Confirms row-02 gate + page_url `{/auth/callback*, /}`. | `callback/page.tsx:114-125`. |
| C4 | Rows 03–05 non-Guest identity probe? | `displayName = isAnonymous ? 'Guest' : user?.email?.split('@')[0] || 'User'` on `[data-testid="user-menu-trigger"]`; open menu shows masked `user.email`. Probe: trigger text ≠ "Guest"; menu shows email. | `user-menu.tsx:57-59, 75, 82, 108-112`. |
| C5 | Does row-01 also require non-empty `state`? | No — the convention row requires **non-empty providers** only. `state` is the Feature-1193 CSRF token, exercised in the row-02 flow, not gated by row 01. | `m1-verifier-convention.md` row `auth-oauth-01`. |

**Deferred questions — RESOLVED at the Phase 2 pause (2026-07-23):**
- **DQ-1 (answered):** Owner's actual screen was `/error?error=Invalid state` on the Cognito domain (see
  §1). Recorded; risk R-5 added; same root cause (unwired) — not a new blocker.
- **DQ-2/DQ-3 (answered):** No preprod GCP project yet; owner has a personal Gmail only. **Decision:**
  personal Gmail is sufficient for preprod — owns the GCP project AND is the capture login. Runbook Step A
  expanded with project creation + consent-screen (External/Testing) + add-Gmail-as-test-user. A dedicated
  account is a prod-time nicety, not required now.

**No CRITICAL/HIGH depends on the deferred questions.** Proceed.
