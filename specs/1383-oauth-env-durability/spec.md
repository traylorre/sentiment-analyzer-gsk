# Feature Specification: OAuth Env Durability + Per-Origin Token Exchange

**Feature Branch**: `1383-oauth-env-durability`
**Created**: 2026-07-23
**Status**: Draft
**Input**: User description: "Make the two manually-set dashboard-Lambda OAuth env vars (FRONTEND_URL, COGNITO_REDIRECT_URI) durable via terraform-sourced CI sync (same pattern as ENABLED_OAUTH_PROVIDERS in PR #936), and fix the OAuth token exchange to use the same validated per-request redirect_uri as the authorize step instead of a static env value."

> Authoring note: The `/speckit.*` skills in this repo run interactive, branch-creating
> workflows (create-new-feature scripts, prompts). This feature is being produced inside an
> isolated planning-only git worktree where branch creation and pushes are disallowed, so all
> nine speckit artifacts were authored by hand following the `.specify/templates/*` structure.
> Content and gating are identical to the skill output; only the invocation mechanism differs.

## Context & Problem

During the M1 WI-6 Google OAuth go-live, three dashboard-Lambda environment variables were set
**manually** via live `aws lambda update-function-configuration` because Terraform cannot manage
Lambda env (`modules/lambda` carries `lifecycle { ignore_changes = [image_uri, environment] }`,
Feature 1290) and the CI dashboard-deploy step synced only ONE of them:

| Env var | Durable today? | Drives |
|---|---|---|
| `ENABLED_OAUTH_PROVIDERS=google` | YES — PR #936, CI "Step 2.5" syncs from `terraform output enabled_oauth_providers` | Provider enablement + authorize URL generation |
| `FRONTEND_URL=https://main.d29tlmksqcx494.amplifyapp.com` | NO — manual only | OAuth redirect_uri allowlist (`_resolve_redirect_uri`, `auth.py:2030`) |
| `COGNITO_REDIRECT_URI=https://main.d29tlmksqcx494.amplifyapp.com/auth/callback` | NO — manual only | Static token-exchange redirect_uri (`cognito.py:162`) |

Two independent facts make these "snowflakes":

1. **Durability gap.** A Lambda recreation (or any recreation of `$LATEST` env) would lose
   `FRONTEND_URL` and `COGNITO_REDIRECT_URI` because nothing reproduces them from source. Only
   `ENABLED_OAUTH_PROVIDERS` is reconstructed by CI Step 2.5.

2. **Correctness gap.** The authorize step uses a **dynamic, per-request** redirect_uri
   (`get_authorize_url(..., redirect_uri_override=_resolve_redirect_uri(origin))`), but the
   token exchange uses a **static** `config.redirect_uri` (from `COGNITO_REDIRECT_URI`). OAuth
   requires the token-exchange redirect_uri to EXACTLY match the authorize redirect_uri. The
   static value is why `COGNITO_REDIRECT_URI` had to be pinned by hand, and it breaks any origin
   other than the pinned one (e.g. localhost dev against preprod). The frontend already sends its
   real redirect_uri in the callback POST; the backend receives it but drops it.

### Confirmed plumbing (file:line)

- **Token-exchange drop-point**: `src/lambdas/dashboard/auth.py:2215` —
  `tokens = exchange_code_for_tokens(config, code, code_verifier=code_verifier)` — the
  `redirect_uri` parameter that `handle_oauth_callback` received (param declared at
  `auth.py:2147`) is not passed through.
- **Static redirect_uri used in exchange**: `src/lambdas/shared/auth/cognito.py:162` —
  `"redirect_uri": config.redirect_uri` (config value comes from `COGNITO_REDIRECT_URI`,
  `cognito.py:59`).
- **Authorize already dynamic**: `auth.py:2101-2105` and `2123-2127` pass
  `redirect_uri_override=redirect_uri` where `redirect_uri = _resolve_redirect_uri(origin)`
  (`auth.py:2078`).
- **Server-side stored redirect_uri**: `store_oauth_state(..., redirect_uri=redirect_uri)`
  (`auth.py:2093/2097`, `2115/2119`) persists the authorize-time value.
- **Allowlist validation already enforced on callback**: `handle_oauth_callback` calls
  `validate_oauth_state(table, state_id=state, provider=provider, redirect_uri=redirect_uri)`
  (`auth.py:2186-2192`), and `validate_oauth_state` REJECTS the request unless the client-sent
  `redirect_uri` exactly equals the server-side stored `state.redirect_uri`
  (`src/lambdas/shared/auth/oauth_state.py:220`). Because that stored value was produced by
  `_resolve_redirect_uri` (allowlist-gated), by the time control reaches line 2215 the
  `redirect_uri` is provably equal to an allowlist-validated authorize-time value.
- **Durability pattern to copy**: CI "Step 2.5" at `.github/workflows/deploy.yml:1051-1066` —
  fetch `terraform output -raw enabled_oauth_providers` → read current `Environment.Variables`
  → compare → merge full Variables map → `update-function-configuration` → `wait
  function-updated`; no-ops when already correct.
- **Terraform env expressions** (source of truth for the outputs to add):
  `FRONTEND_URL = var.frontend_url` (`main.tf:469`);
  `COGNITO_REDIRECT_URI = length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls[0] : ""`
  (`main.tf:465`).
- **Existing output to mirror**: `output "enabled_oauth_providers"` (`main.tf:1489`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Durable OAuth env survives Lambda recreation (Priority: P1)

As the platform operator, when the dashboard Lambda's `$LATEST` env is recreated (image swap,
teardown/rebuild, or a fresh account bootstrap), a normal CI deploy must restore `FRONTEND_URL`
and `COGNITO_REDIRECT_URI` to their correct values from Terraform-sourced config, with zero
manual `aws lambda update-function-configuration` steps.

**Why this priority**: This is the core durability defect. Today an env recreation silently
breaks Google OAuth (redirect_uri allowlist collapses to localhost-only) with no code change and
no obvious cause. It is a latent production-mirror outage.

**Independent Test**: On preprod, manually strip `FRONTEND_URL` and `COGNITO_REDIRECT_URI` from
`$LATEST`, trigger a dashboard deploy, and confirm both are restored to the expected values on
the published/served version — with no manual env edit.

**Acceptance Scenarios**:

1. **Given** `FRONTEND_URL` and `COGNITO_REDIRECT_URI` are absent or wrong on `$LATEST`,
   **When** the dashboard-deploy job runs, **Then** Step 2.5 sets both to the Terraform-output
   values and the published version serves them.
2. **Given** both env vars already equal the Terraform-output values, **When** the deploy runs
   again, **Then** Step 2.5 detects no diff and performs no `update-function-configuration`
   call (idempotent no-op) and logs "no change".
3. **Given** the Variables map also contains unrelated keys (e.g. `SENTIMENTS_TABLE`,
   `COGNITO_CLIENT_ID`), **When** Step 2.5 updates the OAuth keys, **Then** all unrelated keys
   are preserved unchanged (full-map merge, never a replace).

---

### User Story 2 - Token exchange uses the same validated redirect_uri as authorize (Priority: P1)

As an authenticating user (including a developer running the frontend on `localhost:3000`
against the deployed preprod API), the OAuth authorization-code exchange must use the exact
redirect_uri that was used at the authorize step, so the exchange is not rejected by the IdP for
`redirect_uri` mismatch.

**Why this priority**: This is the correctness defect that forced the manual pin. It also makes
localhost-dev-against-preprod work without per-origin config, and removes the single-origin
fragility of a static token-exchange redirect_uri.

**Independent Test**: Complete a real Google sign-in from the preprod Amplify origin (token
exchange succeeds), and separately confirm that a callback whose `redirect_uri` does not match
the stored state value is rejected before any token exchange occurs.

**Acceptance Scenarios**:

1. **Given** a user authorized from origin `O` (redirect_uri `O/auth/callback`), **When** the
   callback POST arrives with that same redirect_uri and a valid state, **Then** the backend
   exchanges the code using `O/auth/callback` (not the static `COGNITO_REDIRECT_URI`) and login
   succeeds.
2. **Given** a callback whose `redirect_uri` differs from the value stored in the OAuth state
   record, **When** the backend validates state, **Then** the request is rejected with an
   invalid-state error and NO token exchange is attempted.
3. **Given** `COGNITO_REDIRECT_URI` is set to the Amplify callback and the request origin is the
   Amplify origin, **When** login runs, **Then** behavior is unchanged from today (no
   regression on the primary path).

---

### User Story 3 - Fresh-account/prod parity is explicit and non-breaking (Priority: P3)

As the operator preparing prod (or a fresh account), the Terraform config must make the intended
`frontend_url` / callback values explicit per environment so prod is not silently left with the
empty defaults, and so this change never overwrites a correct prod value with a preprod one.

**Why this priority**: Prod uses a different frontend URL than preprod, and prod's Amplify URL is
not yet finalized in `prod.tfvars` (`cors_allowed_origins` has a `TODO(1269)` placeholder). This
story records the decision rather than shipping a guessed prod value.

**Independent Test**: `terraform output frontend_url` / `terraform output cognito_redirect_uri`
resolve to environment-appropriate values for the selected `*.tfvars`, and the CI Step 2.5 logic
is environment-agnostic (reads whatever the output yields).

**Acceptance Scenarios**:

1. **Given** `preprod.tfvars` sets `frontend_url` and `cognito_callback_urls`, **When**
   `terraform output` runs for preprod, **Then** the outputs equal the preprod Amplify URL and
   `.../auth/callback`.
2. **Given** prod's Amplify URL is not yet finalized, **When** this feature ships, **Then**
   `prod.tfvars` is either populated with the real prod URL or left with a documented,
   deliberate decision (see Clarifications) — never a preprod value.

### Edge Cases

- **Empty Terraform output**: If `terraform output -raw frontend_url` returns empty (var
  defaults to `""`), Step 2.5 MUST NOT wipe a correct existing Lambda value with an empty
  string. Desired behavior: skip the update for an env var whose desired value is empty (treat
  empty as "not managed here"), mirroring the safety of the existing ENABLED_OAUTH block but
  without clobbering. (See Adversarial Review #1 — empty-clobber hazard.)
- **`cognito_callback_urls` empty list**: `COGNITO_REDIRECT_URI` output expression must guard the
  index (`length(...) > 0 ? [0] : ""`) exactly as `main.tf:465` does.
- **Trailing-slash / normalization drift**: `_resolve_redirect_uri` strips a trailing slash on
  `FRONTEND_URL`; the stored state redirect_uri and the client-sent one must normalize the same
  way or `validate_oauth_state` will falsely reject. Confirm no new normalization is introduced.
- **State record lacks redirect_uri**: If an older state row has no stored redirect_uri,
  `validate_oauth_state` already rejects on mismatch; the exchange path must never fall back to
  an unvalidated client value.
- **Concurrent deploy env race**: Step 2.5 reads-then-writes the full Variables map; a
  simultaneous unrelated env write could be lost. Deploys are serialized by the workflow
  concurrency group, so this is out of scope but noted.
- **deploy.yml injection**: Only trusted Terraform outputs and AWS CLI JSON flow through `run:`
  blocks; values are passed via env to `python3` (never interpolated into shell), matching the
  existing ENABLED_OAUTH block.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `preprod.tfvars` MUST set `frontend_url = "https://main.d29tlmksqcx494.amplifyapp.com"`.
- **FR-002**: `preprod.tfvars` MUST set `cognito_callback_urls` such that index `[0]` is
  `"https://main.d29tlmksqcx494.amplifyapp.com/auth/callback"` (the value the static
  `COGNITO_REDIRECT_URI` env is derived from). Note: the Cognito app client has
  `ignore_changes=[callback_urls]` (`modules/cognito/main.tf:146`), so this change affects the
  Lambda-env-derived output, not the live Cognito client registration.
- **FR-003**: Terraform MUST expose an `output "frontend_url"` whose value equals the exact env
  expression `var.frontend_url` (the same source `main.tf:469` uses for `FRONTEND_URL`).
- **FR-004**: Terraform MUST expose an `output "cognito_redirect_uri"` whose value equals the
  exact env expression `length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls[0] : ""`
  (the same source `main.tf:465` uses for `COGNITO_REDIRECT_URI`).
- **FR-005**: CI "Step 2.5" in `.github/workflows/deploy.yml` MUST be extended to sync
  `FRONTEND_URL` and `COGNITO_REDIRECT_URI` onto the dashboard Lambda `$LATEST` env from
  `terraform output -raw frontend_url` and `terraform output -raw cognito_redirect_uri`, using
  the same fetch → read-current-map → compare → merge-full-map → `update-function-configuration`
  → `wait function-updated` pattern already used for `ENABLED_OAUTH_PROVIDERS`.
- **FR-006**: The Step 2.5 sync MUST be idempotent: when the current Lambda value already equals
  the desired Terraform-output value, no `update-function-configuration` call is made.
- **FR-007**: The Step 2.5 sync MUST preserve every other key in the Lambda `Environment.Variables`
  map (merge, never replace the whole map with only OAuth keys).
- **FR-008**: The Step 2.5 sync MUST run BEFORE `publish-version` so the served alias/version
  carries the synced env, matching the existing ordering.
- **FR-009**: `exchange_code_for_tokens` (`src/lambdas/shared/auth/cognito.py`) MUST accept a
  per-request redirect_uri (new optional parameter, e.g. `redirect_uri_override: str | None`)
  and use it for the token-exchange `redirect_uri` when provided, falling back to
  `config.redirect_uri` otherwise — mirroring `get_authorize_url`'s existing
  `redirect_uri_override` parameter.
- **FR-010**: `handle_oauth_callback` (`src/lambdas/dashboard/auth.py`) MUST thread the request's
  already-state-validated `redirect_uri` into `exchange_code_for_tokens` at the call site
  (`auth.py:2215`).
- **FR-011**: The redirect_uri used for the token exchange MUST be one that has passed
  `validate_oauth_state` (i.e. equals the server-side stored authorize-time value). The system
  MUST NOT pass a raw, un-validated client-supplied redirect_uri to the token exchange. (Today
  this is guaranteed by the existing `validate_oauth_state` redirect_uri equality check at
  `oauth_state.py:220`, which runs before line 2215.)
- **FR-012**: The `auth.py` change MUST be minimal and localized to the callback token-exchange
  call site (no refactor of surrounding logic), because `auth.py` is a known merge hotspot shared
  with Features 1380 and 1381 (serialized merge).
- **FR-013**: No new AWS resources are created; the dashboard-Lambda env remains
  Terraform-frozen (`ignore_changes=[environment]`) and flows only via CI Step 2.5.
- **FR-014**: `prod.tfvars` handling MUST be an explicit, documented decision (populate with the
  real prod frontend URL, or deliberately defer) — never populated with a preprod value. (See
  Clarifications.)
- **FR-015**: Secrets MUST never be logged by the new Step 2.5 lines; only non-secret URLs are
  echoed, consistent with the existing block.

### Key Entities *(include if feature involves data)*

- **Dashboard Lambda Environment (`$LATEST` Variables map)**: The frozen-in-Terraform,
  CI-synced env of `preprod-sentiment-dashboard`. Relevant keys: `FRONTEND_URL`,
  `COGNITO_REDIRECT_URI`, `ENABLED_OAUTH_PROVIDERS`.
- **OAuth State record** (`oauth_state.py`): DynamoDB row storing `provider`, `redirect_uri`,
  `code_verifier`, `created_at`, `used`. The stored `redirect_uri` is the authorize-time,
  allowlist-validated value the exchange must match.
- **Terraform outputs**: `frontend_url`, `cognito_redirect_uri` (new), `enabled_oauth_providers`
  (existing) — the source of truth CI reads to reconstruct the frozen env.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh dashboard deploy sets `FRONTEND_URL` and `COGNITO_REDIRECT_URI` on the
  served Lambda version from Terraform-sourced config with ZERO manual steps (verified on real
  preprod).
- **SC-002**: Running the deploy a second time with env already correct produces a Step 2.5
  "no change" log for both keys and issues zero `update-function-configuration` calls for them
  (idempotent).
- **SC-003**: After Step 2.5 runs, every pre-existing non-OAuth env key is byte-for-byte
  unchanged (no clobber).
- **SC-004**: A real Google sign-in from the preprod Amplify origin succeeds, and the token
  exchange request carries `redirect_uri` equal to the origin's `/auth/callback` (not a
  hardcoded static value).
- **SC-005**: A callback with a redirect_uri that does not match the stored state value is
  rejected before any token exchange (no open-redirect, no token theft path).
- **SC-006**: Simulated env-strip + redeploy on preprod restores correct OAuth env (Lambda
  "recreation" survivability demonstrated).
- **SC-007**: `terraform output frontend_url` and `terraform output cognito_redirect_uri` return
  environment-appropriate values for preprod; prod handling matches the recorded decision.

## Assumptions

- The dashboard-deploy job runs `terraform` in a directory where `terraform output` is available
  (same context the existing `enabled_oauth_providers` fetch relies on).
- `preprod-sentiment-dashboard` is the correct function name (already hardcoded in Step 2.5).
- CUSTOMER dashboard only (Next.js/Amplify). The HTMX admin dashboard is untouched.
- The frontend already sends `redirect_uri = window.location.origin + window.location.pathname`
  in the callback POST (`frontend/src/app/auth/callback/page.tsx:115`) and the route handler
  passes it into `handle_oauth_callback`.

## Out of Scope

- Removing the static `COGNITO_REDIRECT_URI` entirely (kept as fallback for FR-009; removal is a
  follow-up once per-origin exchange is proven).
- Un-freezing the Lambda env in Terraform (Feature 1290 constraint stands).
- GitHub as an OAuth provider (Google-only per M1 WI-6).
- Any change to the Cognito app client's registered callback URLs (frozen via
  `ignore_changes`).

---

## Adversarial Review #1

**Reviewer stance**: Assume the spec is wrong. Attack surfaces named by the battleplan:
open-redirect via unvalidated redirect_uri; Step 2.5 clobbering other env vars; deploy.yml
breaking the critical dashboard deploy; prod.tfvars not getting these (prod uses a different
frontend URL); race where token redirect_uri != authorize.

### Findings

**AR1-F1 (HIGH → resolved in spec): Empty-output clobber.** The battleplan says "copy the
ENABLED_OAUTH pattern," which updates whenever `CUR != DESIRED` — INCLUDING when `DESIRED` is
empty. `var.frontend_url` defaults to `""` and `cognito_callback_urls` can be empty. If the
outputs ever resolve empty (prod today, a bad tfvars, or a `terraform output` miss swallowed by
`|| echo ""`), a naive copy would SET `FRONTEND_URL=""` / `COGNITO_REDIRECT_URI=""` on the
Lambda, wiping a correct manually-set value and collapsing the redirect allowlist to
localhost-only — the exact outage this feature exists to prevent, now triggered BY the fix.
*Resolution*: FR-006 + Edge Case "Empty Terraform output" require Step 2.5 to SKIP the update
when the desired value is empty (treat empty as "not managed here"). This diverges intentionally
from the ENABLED_OAUTH block (whose empty is a legitimate "OAuth disabled" state). Documented as
a deliberate, tested divergence, not an oversight. **Gate impact: would have been CRITICAL in
prod; downgraded to resolved-HIGH by spec edit.**

**AR1-F2 (HIGH → already safe): Open-redirect / token-theft via client redirect_uri.** The
concern: threading a client-supplied redirect_uri into the token exchange could let an attacker
redirect the code/token to an attacker origin. *Investigation*: The value threaded at
`auth.py:2215` is the SAME `redirect_uri` that `validate_oauth_state` already checked for exact
equality against the server-side stored `state.redirect_uri` (`oauth_state.py:220`), which was
itself produced by the allowlist-gated `_resolve_redirect_uri` at authorize time. So the value
is provably (a) allowlist-validated and (b) equal to the authorize-time value before it ever
reaches the exchange. No new trust is extended. *Resolution*: FR-011 codifies this ordering
constraint (validate-before-exchange) so a future refactor cannot reorder it. **Belt-and-
suspenders option recorded in plan**: have `validate_oauth_state` RETURN the stored redirect_uri
and thread the server-side value rather than the (equal) client value — removes any doubt.
**Gate impact: no code-path vulnerability found; FR-011 hardens against regression.**

**AR1-F3 (HIGH → resolved in spec): deploy.yml is the critical path.** A syntax error or a
`set -e` abort in the extended Step 2.5 would break EVERY dashboard deploy, not just OAuth.
*Resolution*: (1) The new logic mirrors the proven ENABLED_OAUTH block byte-for-byte in shape
(fetch with `|| echo ""`, python3 for JSON via env-passed vars, guarded update, `wait`). (2)
FR-007 mandates full-map merge. (3) Tasks include a `yq`/`actionlint`-style workflow-syntax
check and a dry-run reasoning pass. (4) Empty-skip (AR1-F1) also prevents a failed output fetch
from doing damage. **Gate impact: mitigated by pattern-fidelity + validation tasks.**

**AR1-F4 (MEDIUM → deferred, documented): prod.tfvars not populated.** Confirmed: `prod.tfvars`
sets none of `frontend_url` / `enable_amplify` / `cognito_callback_urls`, and prod's Amplify URL
is an unfilled `TODO(1269)` placeholder in `cors_allowed_origins`. Prod Amplify may not even be
deployed. Shipping a preprod URL to prod would be actively wrong (FR-014 forbids it).
*Resolution*: Defer prod population with a documented decision (see Clarifications C4). The
Step 2.5 logic is environment-agnostic and empty-safe (AR1-F1), so prod deploys will simply
no-op these two keys until prod's real URL is filled in. Add a `TODO(1383)` breadcrumb in
`prod.tfvars` next to the existing `TODO(1269)`. **Gate impact: not a blocker; explicit defer.**

**AR1-F5 (MEDIUM → resolved by design): token redirect_uri != authorize race.** Concern: what
if the redirect_uri at exchange differs from authorize? *Investigation*: They are the same
object — authorize stores `_resolve_redirect_uri(origin)` into state; callback validates the
client value equals that stored value; the fix threads that same validated value into exchange.
There is no window where they diverge because validation gates the exchange. The ONLY remaining
divergence risk is trailing-slash / normalization drift (Edge Case), which is pre-existing and
unchanged by this feature. **Gate impact: none; design eliminates the race.**

**AR1-F6 (LOW): Cognito client callback registration is frozen.** Setting `cognito_callback_urls`
in `preprod.tfvars` will NOT re-register the Cognito app client's callback URLs because
`modules/cognito/main.tf:146` has `ignore_changes=[callback_urls]`. This is fine — we only need
the value to flow into the Lambda-env-derived output — but the spec must state it so a reviewer
doesn't expect Cognito to change. *Resolution*: Called out in FR-002 and Out of Scope. **Gate
impact: documentation only.**

**AR1-F7 (LOW): Terraform output must mirror the env EXPRESSION, not `module.cognito.callback_urls`.**
An existing `output "cognito_callback_urls"` returns `module.cognito.callback_urls` (the live,
`ignore_changes`-drifted client attribute) — using THAT for Step 2.5 would sync whatever drift
is on the client, not the intended value. *Resolution*: FR-004 requires a NEW
`cognito_redirect_uri` output computed from `var.cognito_callback_urls[0]` (identical to the
`main.tf:465` env expression), guaranteeing output == intended env. **Gate impact: prevents a
subtle wrong-source bug.**

### Edits applied to spec

- Added Edge Case "Empty Terraform output" and tightened FR-006 to require empty-skip.
- Added FR-011 (validate-before-exchange ordering) and FR-014 (prod never gets preprod value).
- Added FR-002 note + Out-of-Scope entry on frozen Cognito callback registration.
- Added FR-004 wording to compute from `var.cognito_callback_urls[0]`, not the drifted module output.

### Gate

- CRITICAL: 0
- HIGH: 0 open (F1/F2/F3 resolved or shown already-safe)
- MEDIUM: 0 open (F4 deferred-with-decision, F5 resolved-by-design)
- LOW: 3 documented (F6, F7, and the pre-existing normalization edge case)

**AR#1 GATE: PASS (0 CRITICAL / 0 HIGH open).**

---

## Clarifications

Session 2026-07-23 (self-answered from live code/config; unanswerable items deferred to owner).

### C1 — Should `prod.tfvars` also receive `frontend_url` / `cognito_callback_urls` now?

**Answer: NO — defer (documented).** Evidence: `prod.tfvars` sets none of `frontend_url`,
`enable_amplify`, or `cognito_callback_urls`; `cors_allowed_origins` still carries the
`TODO(1269)` placeholder "Add Amplify production URL after enable_amplify is set." Prod's Amplify
frontend URL is not finalized (and Amplify may not be deployed for prod). Shipping a value now
would either be a guess or (worse) a copy of the preprod URL. Decision: leave `prod.tfvars`
unpopulated, add a `TODO(1383)` breadcrumb next to `TODO(1269)`, and rely on the empty-safe
Step 2.5 (AR1-F1) to no-op the two keys on prod deploys until the real URL exists. **Owner
question O1** (below) records the one thing I cannot self-answer: the actual prod frontend URL.

### C2 — Should the static `COGNITO_REDIRECT_URI` env var be removed now that the exchange is per-origin?

**Answer: NO — keep as fallback.** `exchange_code_for_tokens` falls back to
`config.redirect_uri` when no override is provided (FR-009). Keeping the env durable (Deliverable
A) preserves a correct default for any code path that does not pass an override and de-risks the
correctness change. Removal is an explicit follow-up (Out of Scope) once per-origin exchange is
proven on preprod.

### C3 — Add-only Step 2.5 vs. refactor all three keys through one helper?

**Answer: ADD-ONLY by default.** The existing `ENABLED_OAUTH_PROVIDERS` block is proven on the
critical deploy path. The lowest-risk change adds two new syncs after it (optionally via a small
`sync_env_key` helper used ONLY by the two new keys). A full three-key refactor is cleaner but
touches the working block; defer unless a reviewer insists. Recorded in plan Phase 1 + AR#2.

### C4 — Should `cognito_callback_urls[0]` be the Amplify callback, and should localhost be included?

**Answer: Amplify callback at index [0]; include localhost as a second entry.** Index `[0]` must
be the Amplify callback because `main.tf:465` derives `COGNITO_REDIRECT_URI` from `[0]`. Including
`http://localhost:3000/auth/callback` as a second entry documents the dev origin the allowlist
(`_resolve_redirect_uri`) already permits; because the Cognito client is `ignore_changes`-frozen
this list does not alter live Cognito registration, so ordering only matters for the env output.

### C5 — Does the per-origin exchange need any new client-input validation?

**Answer: NO new validation needed; existing state validation suffices.** `validate_oauth_state`
already enforces client `redirect_uri == stored state.redirect_uri` (`oauth_state.py:220`) before
the exchange, and the stored value came from the allowlist-gated `_resolve_redirect_uri`. FR-011
codifies the validate-before-exchange ordering. Optional defense-in-depth (return + use the
server-side stored value) is recorded in the plan, default OFF to keep the `auth.py` change to a
single line (merge-hotspot constraint, FR-012).

### Deferred to owner (cannot self-answer)

- **O1 (prod frontend URL):** What is prod's canonical customer-dashboard URL (prod Amplify), and
  is prod Amplify deployed yet? Needed before `prod.tfvars` can be populated (C1). Until answered,
  prod deploys no-op these two keys (safe).
