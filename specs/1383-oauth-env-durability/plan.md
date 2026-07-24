# Implementation Plan: OAuth Env Durability + Per-Origin Token Exchange

**Branch**: `1383-oauth-env-durability` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/1383-oauth-env-durability/spec.md`

> Authored by hand (speckit skills are branch-creating/interactive; this runs in an isolated
> planning-only worktree). Structure follows `.specify/templates/plan-template.md`.

## Summary

Two independent deliverables, isolated for serialized merge:

- **A) Durability (infra/CI, isolated):** Set `frontend_url` and `cognito_callback_urls` in
  `preprod.tfvars`; add two Terraform outputs (`frontend_url`, `cognito_redirect_uri`) that
  mirror the exact env expressions used at `main.tf:469` and `main.tf:465`; extend CI "Step 2.5"
  in `.github/workflows/deploy.yml` to sync `FRONTEND_URL` and `COGNITO_REDIRECT_URI` onto the
  dashboard Lambda `$LATEST` env from those outputs — same fetch→read-current→compare→merge-full-
  map→`update-function-configuration`→`wait` shape as the existing `ENABLED_OAUTH_PROVIDERS`
  block, plus an empty-value skip guard (AR1-F1). `prod.tfvars` deliberately deferred (AR1-F4).

- **B) Correctness (code, auth.py merge hotspot):** Add an optional `redirect_uri_override` param
  to `exchange_code_for_tokens` (`cognito.py`) and thread the already-state-validated per-request
  `redirect_uri` from `handle_oauth_callback` (`auth.py:2215`) into it. Security holds because
  `validate_oauth_state` (`oauth_state.py:220`) already enforces client `redirect_uri` ==
  server-side stored authorize-time value before the exchange runs. Optional hardening: return
  the stored value from `validate_oauth_state` and thread the server-side value.

## Technical Context

**Language/Version**: Python 3.13 (backend), YAML (GitHub Actions), HCL/Terraform 1.5+ (infra)
**Primary Dependencies**: aws-lambda-powertools (routing), httpx (token exchange), boto3
(DynamoDB state), AWS CLI + `terraform output` (CI), AWS Provider ~> 5.0
**Storage**: DynamoDB OAuth state records (existing, read/validated — no schema change)
**Testing**: pytest (unit, mocked httpx/moto), workflow-syntax lint (actionlint/yq), real-AWS
preprod verification (manual, per constitution — preprod mirrors prod)
**Target Platform**: AWS Lambda (`preprod-sentiment-dashboard`), GitHub Actions runner
**Project Type**: web (backend Lambda + Next.js/Amplify customer frontend) — CUSTOMER dashboard only
**Performance Goals**: N/A (config + single call-site thread-through; no hot-path change)
**Constraints**: Dashboard Lambda env FROZEN in Terraform (`ignore_changes=[environment]`,
Feature 1290) — env MUST flow via CI Step 2.5. No new AWS resources. `auth.py` is a merge hotspot
shared with Features 1380/1381 — change must be minimal and localized. GPG-signed commits.
**Scale/Scope**: 1 workflow file, 1 tfvars file (+ 1 deferred), ~2 Terraform outputs, 2 Python
files, unit tests. Small blast radius except deploy.yml (critical path).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Relevant constitution requirements (`.specify/memory/constitution.md`):

| Requirement | Status | Notes |
|---|---|---|
| Auth on management/OAuth flows | PASS | Strengthens OAuth correctness; no new unauth surface. |
| External API auth flows (OAuth) correct | PASS | Fixes redirect_uri correctness per OAuth spec. |
| TLS in transit | PASS | All redirect_uris are https (Amplify) or localhost dev; token exchange over https. |
| Secrets in managed store, never in source/logs | PASS | Only non-secret URLs echoed in Step 2.5 (FR-015). No secret touched. |
| No raw user input into security-sensitive sinks | PASS | redirect_uri is allowlist+state validated before use (FR-011). |
| IaC via Terraform, pinned providers, module layout | PASS | Outputs/tfvars only; no resource churn; env stays frozen by design. |
| Least privilege / no new resources | PASS | FR-013: zero new AWS resources; reuses existing deploy IAM. |
| SAST / no log injection | PASS | provider/uri already sanitized for logs in existing code; no new log of user input. |

**Constitution gate: PASS.** No violations, no complexity-tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/1383-oauth-env-durability/
├── spec.md              # Complete (+ Adversarial Review #1)
├── plan.md              # This file (+ Adversarial Review #2)
├── tasks.md             # Stage 7 (+ Adversarial Review #3)
└── quickstart.md        # Optional verification recipe (Phase 1)
```

No `data-model.md` (no schema change) or `contracts/` (no new API surface) — the API request
shape is unchanged; only the internal redirect_uri source changes.

### Source Code (repository root)

```text
infrastructure/terraform/
├── preprod.tfvars               # A: add frontend_url + cognito_callback_urls
├── prod.tfvars                  # A: TODO(1383) breadcrumb only (deferred, AR1-F4)
└── main.tf                      # A: add output "frontend_url" + output "cognito_redirect_uri"

.github/workflows/
└── deploy.yml                   # A: extend Step 2.5 (~line 1051-1066) to sync 2 more keys

src/lambdas/
├── shared/auth/cognito.py       # B: exchange_code_for_tokens gains redirect_uri_override param
└── dashboard/auth.py            # B: thread redirect_uri at call site (line 2215) — MINIMAL

tests/unit/
├── shared/auth/test_cognito.py            # B: exchange uses override when provided; falls back
└── dashboard/ (auth callback tests)       # B: callback threads validated redirect_uri
```

## Phase 0 — Research (resolved)

All unknowns were resolved during spec authoring by reading the live code; no open research.

1. **Does `terraform output` work in the Step 2.5 context?** YES — the dashboard-deploy job runs
   with `working-directory: infrastructure/terraform` (deploy.yml:767) and already calls
   `terraform output -raw enabled_oauth_providers` (deploy.yml:1052).
2. **Is the callback redirect_uri already validated before exchange?** YES —
   `validate_oauth_state` enforces equality against stored state (`oauth_state.py:220`) prior to
   the exchange call (`auth.py:2215`). Security for Deliverable B is therefore pre-existing.
3. **Does setting `cognito_callback_urls` mutate the live Cognito client?** NO —
   `ignore_changes=[callback_urls]` (`modules/cognito/main.tf:146`). It only feeds the
   Lambda-env-derived output. (AR1-F6)
4. **Which output source is correct for COGNITO_REDIRECT_URI?** A NEW output computed from
   `var.cognito_callback_urls[0]` (matches env expression `main.tf:465`), NOT the existing
   `output "cognito_callback_urls"` (which returns the `ignore_changes`-drifted client attr).
   (AR1-F7)
5. **Prod values?** Unknown/undeployed — `prod.tfvars` has no Amplify config; `TODO(1269)`
   placeholder stands. Defer (AR1-F4 / Clarification C4).

## Phase 1 — Design

### A) Terraform outputs (mirror env expressions exactly)

```hcl
# main.tf — near output "enabled_oauth_providers" (line ~1489)
output "frontend_url" {
  description = "Customer dashboard URL synced onto the dashboard Lambda FRONTEND_URL env by CI (Feature 1383). Terraform-frozen env; see deploy.yml Step 2.5."
  value       = var.frontend_url
}

output "cognito_redirect_uri" {
  description = "Static OAuth token-exchange redirect URI synced onto COGNITO_REDIRECT_URI by CI (Feature 1383). Mirrors the main.tf env expression exactly."
  value       = length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls[0] : ""
}
```

### A) preprod.tfvars

```hcl
# Feature 1383: durable OAuth env (was manually set during WI-6 go-live).
frontend_url = "https://main.d29tlmksqcx494.amplifyapp.com"
# Index [0] feeds COGNITO_REDIRECT_URI (main.tf:465). Cognito client callback
# registration is ignore_changes-frozen, so this only affects the Lambda env output.
cognito_callback_urls = [
  "https://main.d29tlmksqcx494.amplifyapp.com/auth/callback",
  "http://localhost:3000/auth/callback",
]
```

### A) prod.tfvars (deferred)

```hcl
# TODO(1383): set frontend_url + cognito_callback_urls[0] to the prod Amplify URL once
# enable_amplify is turned on for prod and the URL is finalized (see TODO(1269)). CI Step 2.5
# is empty-safe and will no-op these keys until then. Do NOT copy the preprod URL here.
```

### A) deploy.yml Step 2.5 extension (design sketch, not final code)

Reuse the exact idempotent shape, generalized to a per-key helper with an **empty-skip guard**:

```bash
# after the existing ENABLED_OAUTH_PROVIDERS sync, same CUR_ENV re-read or reuse
sync_env_key () {   # $1=key  $2=desired
  local key="$1" desired="$2"
  if [ -z "$desired" ]; then echo "  ${key}: desired empty — skip (not managed here)"; return; fi
  local cur; cur="$(printf '%s' "$CUR_ENV" | KEY="$key" python3 -c 'import sys,json,os;print(json.load(sys.stdin).get(os.environ["KEY"],""))')"
  if [ "$cur" != "$desired" ]; then
    CUR_ENV="$(printf '%s' "$CUR_ENV" | KEY="$key" VAL="$desired" python3 -c 'import sys,json,os;e=json.load(sys.stdin);e[os.environ["KEY"]]=os.environ["VAL"];print(json.dumps(e))')"
    aws lambda update-function-configuration --function-name "$FUNC_NAME" --environment "{\"Variables\":$CUR_ENV}" >/dev/null
    aws lambda wait function-updated --function-name "$FUNC_NAME"
    echo "  ✅ ${key} synced"
  else
    echo "  ${key}: already correct, no change"
  fi
}
FRONTEND_URL_TF="$(terraform output -raw frontend_url 2>/dev/null || echo "")"
COGNITO_REDIRECT_TF="$(terraform output -raw cognito_redirect_uri 2>/dev/null || echo "")"
sync_env_key FRONTEND_URL "$FRONTEND_URL_TF"
sync_env_key COGNITO_REDIRECT_URI "$COGNITO_REDIRECT_TF"
```

Design notes:
- Values pass to `python3` via env (`KEY`/`VAL`), never interpolated into shell → no injection.
- `CUR_ENV` is threaded so multiple keys merge into ONE evolving map; unrelated keys preserved.
- Empty-skip prevents the AR1-F1 clobber. Diverges intentionally from the ENABLED_OAUTH block.
- Runs BEFORE `publish-version` (FR-008), same placement as today.
- Implementer may keep the existing ENABLED_OAUTH inline block as-is and add the two new syncs
  after it, OR refactor all three through `sync_env_key`. Refactoring all three is cleaner but
  touches the proven block — see AR#2 for the risk trade-off; default is ADD-ONLY to minimize
  critical-path risk.

### B) cognito.py — exchange_code_for_tokens

```python
def exchange_code_for_tokens(
    config: CognitoConfig,
    code: str,
    code_verifier: str | None = None,
    redirect_uri_override: str | None = None,   # Feature 1383
) -> CognitoTokens:
    ...
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri_override or config.redirect_uri,   # Feature 1383
    }
```

Mirrors the existing `get_authorize_url(..., redirect_uri_override=...)` convention (cognito.py:86).

### B) auth.py — call site (MINIMAL, merge-hotspot)

```python
# auth.py:2215 — thread the already-state-validated redirect_uri
tokens = exchange_code_for_tokens(
    config, code, code_verifier=code_verifier, redirect_uri=redirect_uri,   # name matches param
)
```

Only this one line changes in `auth.py`. `redirect_uri` here is the function parameter
(`auth.py:2147`) that `validate_oauth_state` already proved equals the stored authorize-time
value. No surrounding logic touched → clean serialized merge with 1380/1381.

**Optional hardening (recorded, default OFF to keep auth.py minimal):** change
`validate_oauth_state` to also return the stored `state.redirect_uri`, and thread THAT
server-side value into the exchange. Removes reliance on the client value being equal (it is
equal, but returning the server value is defense-in-depth). Costs a signature change to a shared
function (`oauth_state.py`) touched by other OAuth features — deferred unless AR#2/clarify
elevates it.

### Merge-hotspot note (auth.py ↔ 1380/1381)

`src/lambdas/dashboard/auth.py` is edited by Features 1380 and 1381 concurrently. This feature's
footprint is a SINGLE line at the `exchange_code_for_tokens` call site (2215). Keep it a one-line
kwarg addition; do not reflow, reorder, or reformat neighboring code. Merge these serially and
resolve by taking both changes (they are line-disjoint from typical 1380/1381 edits, but confirm
at merge time).

## Phase 2 — Verification approach (preprod, real AWS)

1. Deploy to preprod; confirm Step 2.5 logs "synced" for FRONTEND_URL + COGNITO_REDIRECT_URI on
   first run, "already correct, no change" on a second run (idempotency, SC-002).
2. `aws lambda get-function-configuration` shows both keys correct; unrelated keys intact (SC-003).
3. Strip both keys manually → redeploy → confirm restored (SC-006, recreation survivability).
4. Real Google sign-in from Amplify origin succeeds; inspect that token exchange used the origin
   callback (SC-004). Negative: tampered redirect_uri rejected pre-exchange (SC-005).

## Complexity Tracking

No constitution violations → table intentionally empty.

## Progress Tracking

- [x] Phase 0 research complete (resolved during spec)
- [x] Phase 1 design complete
- [x] Constitution check (initial) PASS
- [ ] Constitution re-check after AR#2
- [ ] tasks.md generated (Stage 7)

---

## Adversarial Review #2

**Stance**: Hunt for drift between spec and plan, cross-artifact contradictions, and design flaws
the spec-level review (AR#1) could not see now that the design is concrete.

### Drift checks (spec ↔ plan)

| Spec item | Plan coverage | Drift? |
|---|---|---|
| FR-001/002 (preprod.tfvars values) | Phase 1 "preprod.tfvars" block | none |
| FR-003/004 (two outputs, exact expressions) | Phase 1 "Terraform outputs" | none — plan uses `var.cognito_callback_urls[0]` with length guard, matching main.tf:465 |
| FR-005/006/007/008 (Step 2.5 extend, idempotent, merge, ordering) | Phase 1 deploy.yml sketch + Phase 2 verify | none — empty-skip + full-map merge + pre-publish placement all present |
| FR-009 (exchange override param) | Phase 1 cognito.py block | none |
| FR-010 (thread at 2215) | Phase 1 auth.py block | none |
| FR-011 (validate-before-exchange) | Phase 1 note + Phase 0 research #2 | none |
| FR-012 (minimal auth.py) | Phase 1 "Merge-hotspot note" | none |
| FR-013 (no new AWS resources) | Constitution check + Summary | none |
| FR-014 (prod never gets preprod value) | Phase 1 prod.tfvars block (TODO only) | none |
| FR-015 (no secret logging) | Constitution check + design note (env-passed vars) | none |

No drift found. Every FR maps to a concrete plan element.

### New findings at design granularity

**AR2-F1 (MEDIUM → resolved): Two separate `update-function-configuration` calls thrash the map.**
The `sync_env_key` sketch calls `update-function-configuration` once PER changed key, re-reading
`CUR_ENV` from a threaded variable (not re-fetching from AWS). If both keys change on a fresh
Lambda, that's two sequential update+wait cycles. Correctness holds (CUR_ENV is threaded so the
second call includes the first key's change), but it's two API round-trips. *Resolution*:
Acceptable — matches the existing block's one-key-one-update rhythm, keeps the diff minimal, and
fresh-Lambda (both-change) is rare. Tasks note an OPTIONAL single-batched-update variant (compute
both desired values, merge once, one update) for the implementer if they prefer. Not required.

**AR2-F2 (MEDIUM → resolved): `CUR_ENV` reuse vs. the existing ENABLED_OAUTH block.** The existing
block reads `CUR_ENV` once and builds `NEW_ENV` from it. If the new code reuses that SAME `CUR_ENV`
variable AFTER the ENABLED_OAUTH block already issued an update, `CUR_ENV` would be stale (missing
the just-written ENABLED_OAUTH value) — a merge that re-reads stale state could revert it.
*Resolution*: The plan's helper threads `CUR_ENV` forward, but the SAFEST implementation re-reads
`CUR_ENV` from `aws lambda get-function-configuration` AFTER the ENABLED_OAUTH block (or folds all
three keys into one read→merge→write). Task T-DEPLOY must specify: re-fetch current env
immediately before the new syncs, OR thread the same evolving map through all three keys. Elevated
to an explicit task acceptance criterion. **This is the single most important implementation
detail** — flagged for AR#3.

**AR2-F3 (LOW → resolved): `terraform output -raw` on a list vs string.** `frontend_url` and
`cognito_redirect_uri` are both string-valued outputs (the latter guards the index), so `-raw`
works. The existing (unused-by-us) `cognito_callback_urls` output is a list and `-raw` would fail
on it — but we deliberately do NOT use that output (AR1-F7). No action.

**AR2-F4 (LOW → resolved): quickstart.md optionality.** Plan lists quickstart.md as optional. The
verification recipe (Phase 2) is self-contained; a separate quickstart is not needed for a
config+one-line change. Decision: fold verification into tasks.md rather than a separate file.

**AR2-F5 (LOW): auth.py kwarg name must match the new param name.** Plan shows
`exchange_code_for_tokens(config, code, code_verifier=..., redirect_uri=redirect_uri)` but the new
param in cognito.py is named `redirect_uri_override`. The call site MUST use
`redirect_uri_override=redirect_uri` (kwarg name = param name) or it's a TypeError. *Resolution*:
Corrected here and carried into tasks — call site uses `redirect_uri_override=redirect_uri`.
**(Genuine bug in the plan sketch; fixed.)**

### Cross-artifact consistency

- Clarifications C1–C5 are consistent with plan decisions (defer prod, keep static fallback,
  add-only Step 2.5, Amplify-at-[0]+localhost, no new validation). No contradiction.
- Owner question O1 (prod URL) is the only unresolved item; it does not block Deliverable A/B on
  preprod and is correctly scoped as deferred.

### Constitution re-check (post-design)

Re-ran the gate table with concrete design: still PASS. The empty-skip guard (AR1-F1) and
env-passed python3 vars (no shell interpolation) reinforce the "no secret leak / no injection"
constitution items. No new resources. No violations.

### Gate

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 0 open (AR2-F1, AR2-F2 resolved with task-level acceptance criteria)
- LOW: 3 (AR2-F3/F4 resolved, AR2-F5 fixed)

**AR#2 GATE: PASS. Drift: none. One genuine plan bug fixed (AR2-F5 kwarg name). One critical
implementation detail elevated to AR#3 (AR2-F2 env re-read/merge ordering).**

---

## Plan 2nd Pass (Stage 6)

**Outcome: SKIPPED (no structural drift).** AR#2 found zero spec↔plan drift. The only genuine
defect (AR2-F5, wrong kwarg name in the auth.py sketch) was a localized one-token fix applied
inline in the AR#2 section and carried into tasks (call site uses
`redirect_uri_override=redirect_uri`). The one elevated concern (AR2-F2, env re-read/merge
ordering in Step 2.5) is not a plan-structure change — it becomes an explicit acceptance
criterion on the deploy task. No re-plan required.
