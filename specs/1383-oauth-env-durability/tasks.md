# Tasks: OAuth Env Durability + Per-Origin Token Exchange

**Feature**: `1383-oauth-env-durability` | **Date**: 2026-07-23
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> Hand-authored (speckit skills are branch-creating/interactive; planning-only worktree).
> Structure follows `.specify/templates/tasks-template.md`. `[P]` = parallelizable (different
> files, no ordering dependency).

## Conventions

- IDs: `T0xx`. Deliverable A (infra/CI) and Deliverable B (code) are independent and may proceed
  in parallel; they touch disjoint files.
- Every task lists the FR(s) it satisfies and its acceptance check.
- Verification tasks require REAL preprod (constitution: preprod mirrors prod). No preprod tests
  run locally.

---

## Phase 1 — Deliverable A: Durability (infra + CI)

### T001 [P] — Add Terraform outputs `frontend_url` and `cognito_redirect_uri`
- **File**: `infrastructure/terraform/main.tf` (near `output "enabled_oauth_providers"`, ~L1489)
- **Do**: Add `output "frontend_url" { value = var.frontend_url }` and
  `output "cognito_redirect_uri" { value = length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls[0] : "" }`
  with descriptions. MUST mirror the env expressions at `main.tf:469` / `main.tf:465` exactly.
  Do NOT reuse the existing list-valued `output "cognito_callback_urls"` (AR1-F7).
- **FRs**: FR-003, FR-004
- **Accept**: `terraform validate` passes; `terraform output frontend_url` and
  `terraform output cognito_redirect_uri` are string-valued (not list); values match preprod
  after T002.

### T002 [P] — Populate `preprod.tfvars`
- **File**: `infrastructure/terraform/preprod.tfvars`
- **Do**: Add `frontend_url = "https://main.d29tlmksqcx494.amplifyapp.com"` and
  `cognito_callback_urls = ["https://main.d29tlmksqcx494.amplifyapp.com/auth/callback", "http://localhost:3000/auth/callback"]`.
  Index `[0]` MUST be the Amplify callback (feeds COGNITO_REDIRECT_URI). Comment that the Cognito
  client is `ignore_changes`-frozen so this only feeds the Lambda-env output (AR1-F6, C4).
- **FRs**: FR-001, FR-002
- **Accept**: `terraform plan -var-file=preprod.tfvars` shows NO change to the Cognito app client
  callback_urls (frozen), and the two new outputs resolve to the expected strings.

### T003 — Add `TODO(1383)` breadcrumb to `prod.tfvars` (defer, do NOT populate)
- **File**: `infrastructure/terraform/prod.tfvars`
- **Do**: Add a comment next to `TODO(1269)`: prod `frontend_url` + `cognito_callback_urls[0]`
  to be set once prod Amplify URL is finalized; Step 2.5 is empty-safe until then; never copy the
  preprod URL. Do NOT set any value.
- **FRs**: FR-014 (and Clarification C1, owner question O1)
- **Accept**: `prod.tfvars` contains the breadcrumb and NO `frontend_url`/`cognito_callback_urls`
  assignment.

### T004 — Extend CI "Step 2.5" to sync FRONTEND_URL + COGNITO_REDIRECT_URI (CRITICAL PATH)
- **File**: `.github/workflows/deploy.yml` (dashboard-deploy job, after the existing
  ENABLED_OAUTH_PROVIDERS block at ~L1051-1066, BEFORE `publish-version` at ~L1067)
- **Do**: Fetch `terraform output -raw frontend_url` and `terraform output -raw cognito_redirect_uri`
  (each with `2>/dev/null || echo ""`). Sync each onto the Lambda env using the same
  read-current-map → compare → merge-full-map → `update-function-configuration` → `wait
  function-updated` shape as ENABLED_OAUTH_PROVIDERS. Pass values to `python3` via ENV VARS
  (`KEY`/`VAL`), never shell-interpolated (injection-safe, FR-015).
- **MANDATORY acceptance criteria (from AR2-F2 — the highest-risk detail)**:
  1. **Env freshness**: Immediately before the new syncs, RE-FETCH the current env via
     `aws lambda get-function-configuration ... --query 'Environment.Variables'` (so it includes
     any ENABLED_OAUTH change just written), OR thread a single evolving map through all three
     keys. MUST NOT reuse a stale pre-ENABLED_OAUTH `CUR_ENV`.
  2. **Empty-skip guard (AR1-F1)**: If the desired Terraform value is empty, SKIP that key (log
     "desired empty — skip"); never write an empty string over an existing value.
  3. **Full-map merge (FR-007)**: The update MUST preserve every other env key.
  4. **Idempotent (FR-006)**: When current == desired, issue NO update call; log "no change".
  5. **Ordering (FR-008)**: Runs before `publish-version`.
- **FRs**: FR-005, FR-006, FR-007, FR-008, FR-013, FR-015
- **Accept**: workflow-syntax check passes (T005); dry-read of the block confirms all 5 criteria.

### T005 [P] — Validate deploy.yml syntax + reason through the block
- **File**: `.github/workflows/deploy.yml`
- **Do**: Run `actionlint` (or `yq '.'` / `python3 -c 'import yaml,sys;yaml.safe_load(open("...")) '`)
  to confirm the workflow still parses. Manually trace the merge logic for three cases:
  (a) fresh Lambda both keys empty→set; (b) already-correct→no-op; (c) empty desired→skip.
- **FRs**: FR-005, FR-006 (guards the critical deploy path, AR1-F3)
- **Accept**: linter/parser exit 0; the three traced cases behave per T004 criteria.

---

## Phase 2 — Deliverable B: Correctness (per-origin token exchange)

### T006 [P] — Add `redirect_uri_override` param to `exchange_code_for_tokens`
- **File**: `src/lambdas/shared/auth/cognito.py` (~L130 signature, ~L162 data dict)
- **Do**: Add `redirect_uri_override: str | None = None` to the signature; set the token-exchange
  `data["redirect_uri"] = redirect_uri_override or config.redirect_uri`. Mirror the existing
  `get_authorize_url(..., redirect_uri_override=...)` convention (cognito.py:86). Update the
  docstring.
- **FRs**: FR-009
- **Accept**: signature + data dict updated; falls back to `config.redirect_uri` when override is
  None/empty.

### T007 — Thread validated redirect_uri at the callback exchange call site (MINIMAL, merge-hotspot)
- **File**: `src/lambdas/dashboard/auth.py` (call site at L2215)
- **Do**: Change ONLY line 2215 to
  `tokens = exchange_code_for_tokens(config, code, code_verifier=code_verifier, redirect_uri_override=redirect_uri)`.
  `redirect_uri` is the `handle_oauth_callback` param (L2147), already proven equal to the stored
  authorize-time value by `validate_oauth_state` (which runs above, L2186-2192). Do NOT reflow,
  reorder, or reformat neighboring lines (FR-012 — 1380/1381 merge hotspot). Kwarg name MUST be
  `redirect_uri_override` (AR2-F5).
- **FRs**: FR-010, FR-011, FR-012
- **Accept**: single-line diff in auth.py; kwarg name matches T006 param; no other lines changed.

### T008 [P] — Unit tests for cognito.py exchange override
- **File**: `tests/unit/shared/auth/test_cognito.py`
- **Do**: With mocked httpx, assert: (a) when `redirect_uri_override` is provided, the POST body
  `redirect_uri` equals the override; (b) when omitted, it equals `config.redirect_uri`.
- **FRs**: FR-009
- **Accept**: both tests pass; `pytest tests/unit/shared/auth/test_cognito.py -q` green.

### T009 [P] — Unit test for callback threading + validate-before-exchange ordering
- **File**: existing dashboard auth callback test module (e.g. `tests/unit/dashboard/test_auth*.py`)
- **Do**: Assert `handle_oauth_callback` passes the request `redirect_uri` into
  `exchange_code_for_tokens` (patch/spy the exchange, assert kwarg). Add/confirm a negative test:
  a callback whose `redirect_uri` != stored state value is rejected by `validate_oauth_state`
  BEFORE any exchange call (spy asserts exchange NOT called).
- **FRs**: FR-010, FR-011
- **Accept**: positive + negative tests pass.

---

## Phase 3 — Verification (real preprod; constitution: no preprod tests locally)

### T010 — Preprod: durability + idempotency + no-clobber
- **Do**: Deploy to preprod. Confirm Step 2.5 logs "synced" for both keys on first run and
  "no change" on a second run. `aws lambda get-function-configuration` shows both correct and all
  unrelated env keys intact. Then strip both keys manually, redeploy, confirm restored.
- **FRs**: FR-005/006/007; **SCs**: SC-001, SC-002, SC-003, SC-006
- **Accept**: all four observations hold with zero manual env edits (beyond the deliberate strip).

### T011 — Preprod: per-origin token exchange correctness + open-redirect negative
- **Do**: Complete a real Google sign-in from the Amplify origin; confirm login succeeds and the
  token exchange used the origin `/auth/callback`. Confirm a tampered-redirect_uri callback is
  rejected before exchange.
- **FRs**: FR-009/010/011; **SCs**: SC-004, SC-005
- **Accept**: primary login works (no regression); tampered request rejected pre-exchange.

### T012 [P] — Local gates before push
- **Do**: `make validate`, `pytest tests/unit/ -q` (or the auth subsets), `terraform fmt -recursive`
  + `terraform validate`, workflow lint (T005). GPG-signed commits. Pre-push security check
  (`gh api ... code-scanning/alerts`).
- **Accept**: all gates green; commits signed.

---

## Requirement → Task coverage

| FR | Task(s) |
|---|---|
| FR-001 | T002 |
| FR-002 | T002 |
| FR-003 | T001 |
| FR-004 | T001 |
| FR-005 | T004, T005 |
| FR-006 | T004, T005, T010 |
| FR-007 | T004, T010 |
| FR-008 | T004 |
| FR-009 | T006, T008 |
| FR-010 | T007, T009 |
| FR-011 | T007, T009, T011 |
| FR-012 | T007 |
| FR-013 | T004 (no new resources) |
| FR-014 | T003 |
| FR-015 | T004, T005 |
| SC-001..007 | T010, T011 |

Every FR and SC maps to ≥1 task. No orphan requirements.

## Parallelization

- A-track: T001, T002, T005 are `[P]`; T003 independent; T004 depends on T001/T002 (needs outputs).
- B-track: T006, T008, T009 are `[P]`; T007 depends on T006 (param must exist first).
- A-track and B-track fully parallel (disjoint files).
- T010/T011 require a deployed preprod (after A/B merged); T012 before push.

---

## Cross-Artifact Analysis (`/speckit.analyze` equivalent)

Non-destructive consistency scan across spec.md, plan.md, tasks.md.

### Coverage
- **Requirements → tasks**: All 15 FRs and all 7 SCs map to ≥1 task (see table above). No orphans.
- **Tasks → requirements**: Every task cites its FR(s). No task without a requirement anchor.
- **User stories → tasks**: US1 (durability) → T001-T005, T010; US2 (per-origin exchange) →
  T006-T009, T011; US3 (prod parity/defer) → T003. All stories covered.

### Consistency
- **Terminology**: "Step 2.5", "FRONTEND_URL", "COGNITO_REDIRECT_URI", "redirect_uri_override"
  used identically across all three artifacts. Kwarg name reconciled to `redirect_uri_override`
  everywhere (AR2-F5 fix propagated to T007).
- **File:line anchors**: auth.py:2215 (drop-point), cognito.py:162 (static uri), oauth_state.py:220
  (validation), main.tf:465/469 (env expressions), deploy.yml:1051-1066 (pattern) — consistent
  spec↔plan↔tasks.
- **Decisions**: Clarifications C1-C5 reflected in tasks (T003 defers prod per C1; T006 keeps
  static fallback per C2; T004 add-only per C3; T002 Amplify-at-[0]+localhost per C4; T007 relies
  on existing validation per C5). No contradiction.

### Gaps / risks surfaced
- **G1 (accepted)**: No automated CI test proves Step 2.5 idempotency/no-clobber; verification is
  manual on preprod (T010). Acceptable — matches how the existing ENABLED_OAUTH block is verified;
  automating a live-Lambda env test is out of proportion for this change.
- **G2 (accepted)**: Owner question O1 (prod URL) leaves prod unconfigured. Non-blocking:
  empty-safe Step 2.5 no-ops prod (T003). Flagged for owner.
- **G3 (watch)**: T007 is a one-line change in a merge-hotspot file. Merge with 1380/1381 must be
  serialized; take-both resolution expected (line-disjoint). Called out in plan + T007.

### Duplication / dead scope
- None. No duplicate tasks; no task without an artifact anchor; Out-of-Scope items (remove static
  env, unfreeze env, GitHub provider) are not tasked.

**Analyze result: CONSISTENT. 0 blocking gaps. 3 accepted/watch items (G1 manual-verify, G2 owner
O1, G3 merge serialization).**

---

## Adversarial Review #3

**Stance**: Final gate before implementation. Identify the highest-risk task, the most likely
rework, and decide READY vs BLOCKED.

### Highest-risk task: **T004 (extend deploy.yml Step 2.5)**

Why it dominates the risk budget:
- It edits the **critical dashboard-deploy path**. A YAML or bash error breaks EVERY dashboard
  deploy, not just OAuth (AR1-F3).
- It carries the **subtlest correctness trap** in the whole feature (AR2-F2): reusing a stale
  `CUR_ENV` after the ENABLED_OAUTH block already wrote the env would silently REVERT
  ENABLED_OAUTH_PROVIDERS on the next merge — turning a durability fix into an OAuth outage.
- The **empty-clobber hazard** (AR1-F1) means a naive copy of the existing pattern can wipe a
  correct value with `""` — again, the fix causing the outage it prevents.

### Most likely rework
1. **Env re-read/merge ordering (AR2-F2)** — highest-probability rework. If the implementer
   copies the ENABLED_OAUTH block's `CUR_ENV` variable and appends, they'll likely reuse the
   stale map. Mitigation baked into T004 acceptance criterion #1 (re-fetch or single evolving
   map). Reviewer MUST diff-read this specifically.
2. **Empty-skip omission (AR1-F1)** — second most likely. Easy to forget; T004 criterion #2 makes
   it explicit; T005 case (c) tests it.
3. **Kwarg name (AR2-F5)** — low probability now that T007 pins `redirect_uri_override`, but a
   TypeError if missed. Caught by T008/T009 unit tests immediately.

### Security re-confirmation
- Open-redirect: neutralized — exchange uses a state-validated, allowlist-derived redirect_uri
  (FR-011, T007/T009/T011). No raw client value reaches the exchange.
- Secret leakage / deploy.yml injection: values pass to python3 via env vars, only non-secret
  URLs echoed (FR-015, T004/T005). No secret touched.
- No new AWS resources; env stays Terraform-frozen (FR-013).

### Merge-serialization note (carried)
auth.py (T007) overlaps Features 1380 and 1381. Keep to one line; serialize the merge; expect
take-both. Do not let a 1380/1381 rebase silently drop the `redirect_uri_override` kwarg.

### Gate
- CRITICAL: 0
- HIGH: 0 (all HIGH items from AR#1/#2 resolved or converted to enforced task criteria)
- Blocking gaps: 0
- Owner questions outstanding: 1 (O1, prod URL) — non-blocking for preprod delivery.

**AR#3 GATE: READY for implementation.** Proceed with T004's five acceptance criteria treated as
hard requirements and a mandatory focused review of the deploy.yml diff. Populate prod (T003→real
value) only after owner answers O1.
