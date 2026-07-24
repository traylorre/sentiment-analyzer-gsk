# Tasks — Feature 1382 apigw-cors-patch

**Spec:** `./spec.md` · **Plan:** `./plan.md` · **Branch:** `1382-apigw-cors-patch`
**Nature:** Terraform-only. Dependency-ordered. `[P]` = parallelizable with siblings.

> Planning artifact only. Do NOT execute (no `/speckit.implement`). Implementation happens in a later phase.

---

## Phase 0 — Baseline capture

- **T001** Capture the current preprod preflight as the "before" evidence:
  `curl -i -X OPTIONS "$PREPROD_API/api/v2/notifications/preferences" -H "Origin: https://main.d29tlmksqcx494.amplifyapp.com" -H "Access-Control-Request-Method: PATCH"` → record that `Access-Control-Allow-Methods` lacks PATCH. (Covers: reproduces bug behind FR-001.)

## Phase 1 — Consolidate the canonical methods (and headers) local

- **T002** In `infrastructure/terraform/modules/api_gateway/main.tf` `locals` block, add `cors_allow_methods = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"` — single-quote wrapping preserved exactly (AR#1 L2). (Covers: FR-003, FR-004.)
- **T003 [P]** Add `cors_allow_headers = "'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'"` (FR-006 fold; value MUST equal the existing canonical string at lines 77/102/126/216 and backend `_CORS_ALLOW_HEADERS`). Optional — drop without affecting the PATCH fix. (Covers: FR-006.)

## Phase 2 — Swap methods references (kills the drift class)

- **T004** Replace the `Access-Control-Allow-Methods` value at line 628 (`aws_api_gateway_integration_response.proxy_options`) with `local.cors_allow_methods`. **This is the fix for the broken preflight.** (Covers: FR-001, US-1.)
- **T005** Replace the `Access-Control-Allow-Methods` value at line 692 (`aws_api_gateway_integration_response.root_options`) with `local.cors_allow_methods`. (Covers: FR-002, US-2.)
- **T006 [P]** Replace the methods values at lines 78, 103, 127 (gateway responses) and 217 (`local.cors_headers`) with `local.cors_allow_methods` — no value change (already correct), removes scattered literals so drift can't recur. (Covers: FR-004, US-3.)
- **T007 [P]** If T003 done: replace the `Access-Control-Allow-Headers` literals at lines 627/691 with `local.cors_allow_headers`; verify the value is byte-identical to the canonical list (D1). (Covers: FR-006.)

## Phase 3 — Force stage redeploy (the make-or-break step)

- **T008** In `aws_api_gateway_deployment.dashboard.triggers.redeployment` (`main.tf:741-755`), add `local.cors_allow_methods` (and `local.cors_allow_headers` if T003) into the hashed `concat([...])` list so the value change forces a new deployment. Without this the stage keeps serving the stale preflight. (Covers: FR-007a — resolves AR#1 H1 / C4.)

## Phase 4 — Static validation (pre-push)

- **T009** `cd infrastructure/terraform && terraform fmt -recursive && terraform validate` → clean. (Covers: NFR-004.)
- **T010 [P]** `grep -n "GET,POST,PUT,DELETE,OPTIONS'" infrastructure/terraform/modules/api_gateway/main.tf` → **zero** matches (no PATCH-less literal remains); `grep` for `local.cors_allow_methods` shows 6 references. (Covers: FR-003, FR-004.)
- **T011 [P]** Confirm no new resource and no origin/credentials change: diff shows only param values + local + trigger; `Allow-Origin` still `'${local.cors_origin}'`, `Allow-Credentials` still `'true'`, no `*`. (Covers: FR-005, NFR-001, NFR-002.)

## Phase 5 — Plan-time gate (preprod dry)

- **T012** `terraform plan` (preprod): MUST show (a) in-place update to `proxy_options` + `root_options` integration responses, (b) a **new** `aws_api_gateway_deployment`. Gateway-response/explicit-route resources show no change (D2). If no new deployment appears → STOP, FR-007a unmet. (Covers: FR-007, FR-007a.)

## Phase 6 — Commit

- **T013** GPG-signed commit of the `.tf` change **with venv activated** (checkov hook gotcha): `source .venv/bin/activate && git commit -S`. Terraform-only. (Covers: NFR-004.)

## Phase 7 — Post-apply real-preprod verification (FR-008)

- **T014** After the deploy pipeline applies to preprod, re-run the T001 curl (cache-bust / fresh): `Access-Control-Allow-Methods` now contains **PATCH**; `Allow-Origin` = the Amplify origin (not `*`); `Allow-Credentials: true`; status 200. (Covers: FR-001, FR-005, FR-008, Success #1/#4.)
- **T015** On the Amplify customer dashboard in a fresh browser context: Settings → toggle → Save Changes → the `PATCH /api/v2/notifications/preferences` returns 2xx and the preference persists on reload. (Covers: US-1, Success #2.)
- **T016 [P]** Regression spot-check: a GET route still works and no unused verb was added to the advertised set. (Covers: FR-003, US-2, Success #3.)

---

## Requirement → Task coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (preferences preflight advertises PATCH) | T001, T004, T014 |
| FR-002 (root OPTIONS advertises PATCH) | T005 |
| FR-003 (exact served verb set, none extra) | T002, T006, T010, T016 |
| FR-004 (single canonical `local`) | T002, T006, T010 |
| FR-005 (origin allowlist, no `*`; credentials) | T011, T014 |
| FR-006 (headers fold, non-blocking) | T003, T007 |
| FR-007 (Terraform-only, no new resources, redeploy) | T011, T012 |
| FR-007a (deploy trigger includes CORS value) | T008, T012 |
| FR-008 (real preprod verification) | T014, T015 |
| NFR-001 (no over-broadening) | T011 |
| NFR-002 (no infra growth) | T011 |
| NFR-003 (least diff) | T002, T006 |
| NFR-004 (fmt/validate, GPG, venv) | T009, T013 |
| US-1 | T004, T015 |
| US-2 | T005, T016 |
| US-3 | T006, T010 |

Every requirement maps to ≥1 task.

---

## Analyze — cross-artifact consistency

- **Coverage:** 8 FR + 1 FR-a + 4 NFR + 3 US → all covered (table above). No orphan requirement; no task without a requirement.
- **Ordering:** locals (T002/3) → references (T004-7) → trigger (T008) → validate (T009-11) → plan gate (T012) → commit (T013) → verify (T014-16). No forward dependency violation. T008 correctly gated before plan/apply (the H1 fix can't be an afterthought).
- **Constitution:** unchanged from Plan — PASS (customer-only, no new resources, no over-broadening, GPG, preprod-verify).
- **Terminology:** "preflight", "catch-all `{proxy+}`", `local.cors_allow_methods`, line numbers consistent across spec/plan/tasks.
- **Ambiguities:** none open (Clarify resolved all 5; 0 deferred).

**Analyze result: consistent. No blocking issues.**

---

## Adversarial Review #3

**Stance:** find the task most likely to cause rework or a silent failed fix; decide readiness.

### Highest-risk task: **T008 (add CORS value to the deployment redeploy trigger)**

**Why it's the crux, not T004:** T004 is the intuitive "fix" (add PATCH at line 628), but on its own
it changes only latent API config. AWS API Gateway REST serves the last **deployment** snapshot to the
stage. The redeploy trigger hashes resource `.id`s (`main.tf:741-755`), which do **not** change on a
param-only edit. So skipping/mis-implementing T008 yields the worst outcome: `terraform apply` succeeds,
the plan looks done, and the live preflight is **unchanged** — a fix that ships green but does nothing.
This is exactly the failure the whole review chain (AR#1 H1 → C4 → FR-007a → T008/T012) exists to prevent.

**Likely rework:** if T008 is forgotten, T014/T015 verification fails on preprod, forcing a second
apply cycle (slow, real-AWS). Mitigation is already inline: **T012 is a hard plan-time gate** — the plan
MUST show a *new* `aws_api_gateway_deployment`; if it doesn't, stop before apply. That converts a
post-deploy discovery into a pre-apply catch.

**Secondary risk:** T008 mis-implemented by hashing the resource `.id` again (no-op) instead of the
**value** string. Guard: T008 explicitly hashes `local.cors_allow_methods` (a value), and T012 verifies
the deployment actually replaces.

### Other notable risks
- **T002/T007 quoting** (AR#1 L2 / D1): a `local` missing the `'…'` wrap or a mistyped headers string breaks all mappings — caught by T009 `terraform validate` + T014 curl.
- **T006 scope creep:** swapping the 3 gateway-response literals is value-neutral; if the local value ever diverged from `GET,POST,PUT,DELETE,PATCH,OPTIONS` it would change 401/403 CORS too — T010 grep + T012 plan-diff confirm no unintended value change.

### Gate

| Criterion | Status |
|-----------|--------|
| Every requirement has a task | ✅ |
| Highest-risk task identified + mitigated pre-apply | ✅ (T008 via T012 gate) |
| No open clarifications | ✅ (0 deferred) |
| Constitution PASS | ✅ |
| CRITICAL / HIGH findings | 0 / 0 |

**READY FOR IMPLEMENTATION** (implementation deferred per battleplan — planning stops here).
