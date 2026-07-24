# Implementation Plan — Feature 1382 apigw-cors-patch

**Spec:** `./spec.md`
**Branch:** `1382-apigw-cors-patch`
**Scope:** Terraform-only change to `infrastructure/terraform/modules/api_gateway/main.tf` (+ one deployment-trigger line). No backend, no frontend, no new AWS resources.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| Two-dashboard hazard | ✅ | Customer API only (Amplify → API Gateway → Dashboard Lambda). No `src/dashboard/` HTMX touch. |
| No new AWS resources | ✅ | Edits existing `integration_response` params + one `local` + deployment trigger. Zero new resources. |
| No CORS over-broadening | ✅ | Origin stays `local.cors_origin` (allowlist, never `*`); credentials preserved; only served verbs advertised. Honors "CORS wildcard + credentials" gotcha. |
| GPG-signed commits | ✅ | `git commit -S` for spec commits; implementation commit likewise (implement phase, not now). |
| Preprod-first real-AWS verification | ✅ | FR-008: verify on live preprod API Gateway after apply. |
| Least-diff / idempotent | ✅ | One canonical `local` + reference swaps; smallest change that also kills the drift class. |
| SAST / secrets | ✅ | No secrets, no Python. `terraform fmt`/`validate` + checkov (venv-activated per repo gotcha). |

**Result: PASS.** No violations, no complexity deviations to record.

---

## Approach

**Chosen: consolidate to a single canonical `local`, then force redeploy.**

1. Introduce `local.cors_allow_methods = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"` (single-quote wrapping preserved — AR#1 L2). Optionally `local.cors_allow_headers` for the canonical full header list (FR-006 decision below).
2. Replace every `Access-Control-Allow-Methods` **value** literal with `local.cors_allow_methods`:
   - line 78 (`gateway_response.unauthorized`)
   - line 103 (`gateway_response.missing_auth_token`)
   - line 127 (`gateway_response.access_denied`)
   - line 217 (inside `local.cors_headers`)
   - line 628 (`proxy_options` integration_response) ← the broken one (FR-001)
   - line 692 (`root_options` integration_response) ← same drift (FR-002)
   After this, 628/692 carry PATCH and no scattered methods literal remains (FR-003/FR-004/US-3).
3. **Force stage redeploy (FR-007a — the critical step):** add `local.cors_allow_methods` (and `local.cors_allow_headers` if consolidated) into the `aws_api_gateway_deployment.dashboard` `triggers.redeployment` hash (`main.tf:741-755`). Resource `.id`s don't change on a param-only edit, so without this the stage keeps serving the stale preflight. Adding the value string makes any future verb change auto-redeploy too.
4. FR-006 (headers drift): **decision — fold headers into the same consolidation.** Replacing the short lists at 627/691 with the canonical `local.cors_allow_methods`-style headers local is low-risk, removes a second drift class, and keeps the two OPTIONS surfaces identical to the gateway-response and explicit-route surfaces. Still non-blocking; if it complicates the diff it can be dropped without affecting the PATCH fix.

**Rejected alternatives**
- *Two-line edit (628 + 692 only), leave literals scattered:* fixes the symptom but leaves the drift class alive and, more importantly, still fails AR#1 H1 unless the trigger is touched. Rejected — doesn't satisfy FR-004/FR-007a.
- *Add explicit `preferences` public_route resource:* larger surface, new resources-ish (new method/integration/responses), contradicts "no new resources / least diff". The catch-all already routes it correctly for the actual PATCH; only its preflight advertisement is wrong. Rejected.

---

## Files Touched

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/api_gateway/main.tf` | Add `local.cors_allow_methods` (+ optional `local.cors_allow_headers`); swap 6 methods-value references; fold 2 header literals (FR-006); add methods/headers value to deployment `triggers`. |

No other files. No `variables.tf`/`outputs.tf` change (no new inputs; the existing `cors_allowed_origins` already drives origin).

---

## Validation Strategy

**Static (pre-push):**
- `cd infrastructure/terraform && terraform fmt -recursive && terraform validate`
- `checkov` via pre-commit **with venv activated** (repo gotcha: `.tf` commits need venv or checkov's hcl2 parser crashes on pyenv).
- Confirm `grep -c "Access-Control-Allow-Methods.*PATCH"` reflects the consolidated `local` (no remaining `GET,POST,PUT,DELETE,OPTIONS` literal without PATCH).

**Plan-time (preprod, dry):**
- `terraform plan` for preprod shows in-place updates to `proxy_options`/`root_options` (and the 3 gateway responses if the local swap is a no-op-value) integration responses **and** a new `aws_api_gateway_deployment` (trigger hash changed). If the plan shows **no** deployment replacement, FR-007a is not satisfied — stop.

**Post-apply (preprod, real AWS — FR-008):**
- `curl -i -X OPTIONS "$PREPROD_API/api/v2/notifications/preferences" -H "Origin: <amplify-origin>" -H "Access-Control-Request-Method: PATCH" -H "Access-Control-Request-Headers: content-type,authorization"` → expect `200` and `Access-Control-Allow-Methods` containing `PATCH`, `Access-Control-Allow-Origin: <amplify-origin>` (not `*`), `Access-Control-Allow-Credentials: true`.
- Fresh browser context / cache-bust (AR#1 L1) then exercise Settings → Save Changes on the Amplify customer dashboard; confirm the `PATCH` returns 2xx and preferences persist.
- Spot-check a still-working verb (e.g. a GET) to confirm no regression, and confirm no unused verb was added.

**Rollback:** revert the single commit; `terraform apply` restores prior integration responses + deployment. Idempotent, no data involved.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Applied but stage not redeployed (stale preflight) | High if trigger untouched | Fix appears dead | FR-007a: methods value in deploy trigger; plan must show new deployment. |
| Dropped `'…'` quoting in `local` | Low | All CORS mappings break | AR#1 L2: local value keeps exact single-quote wrapping; `terraform validate` + preflight curl catch it. |
| Browser cached failed preflight masks success | Low | False negative in verify | Fresh context / cache-bust; curl-based check is authoritative. |
| checkov hook crash on `.tf` commit | Med | Commit blocked | Activate venv before commit (documented gotcha). |
| Header consolidation (FR-006) introduces typo | Low | Preflight header mismatch | Optional; validate against `_CORS_ALLOW_HEADERS`; can be dropped without affecting PATCH fix. |

---

## Adversarial Review #2

**Stance:** hunt for spec↔plan drift and cross-artifact contradictions after Clarify.

### Cross-artifact consistency

| Check | Spec | Plan | Consistent? |
|-------|------|------|-------------|
| Broken location | 628 (+692) | 628 (+692) both swapped | ✅ |
| Consolidation to `local` | FR-004 | Approach step 1-2, files table | ✅ |
| Redeploy trigger (H1/C4) | FR-007a | Approach step 3, plan validation "new deployment" gate, risk row | ✅ |
| Origin allowlist, no `*` | FR-005, C1 | Constitution + post-apply curl assert | ✅ |
| Header drift decision | FR-006, C5 | Approach step 4 = fold, marked non-blocking | ✅ |
| Verb set exactly served | FR-003, C3 | curl assert + grep check | ✅ |
| Preflight cache | Assumptions §7, AR#1 L1 | curl-authoritative + fresh context | ✅ |
| No new resources | NFR-002 | Files table (1 file), constitution | ✅ |
| Preprod real-AWS verify | FR-008 | Validation Strategy post-apply | ✅ |

### Drift findings

| ID | Sev | Finding | Resolution |
|----|-----|---------|-----------|
| D1 | LOW | Plan proposes an *optional* `local.cors_allow_headers` (FR-006 fold); if implemented it changes the 3 gateway-response header values too (they already match the canonical list, so it's a no-op-value swap) — but the plan's "files table" should make explicit that gateway-response header values are already canonical and the local swap must preserve them byte-for-byte. | Clarified: the headers `local` value MUST equal the existing canonical string at 77/102/126/216; swapping those references is a no-op by construction. Recorded here; no FR change. |
| D2 | LOW | Plan validation says "plan shows in-place update to the 3 gateway responses **if** the local swap is a no-op-value" — a methods `local` whose value equals the existing `'GET,POST,PUT,DELETE,PATCH,OPTIONS'` at 78/103/127/217 produces **zero** diff on those three + line 217; the only value-changing diffs are 628/692 + the deployment trigger. | Expectation tightened: `terraform plan` should show exactly (a) updated `proxy_options` + `root_options` integration responses, (b) a new/replaced `aws_api_gateway_deployment`. Gateway-response + explicit-route resources show no change. If more churn appears, investigate before apply. |
| D3 | INFO | No contradiction between "least diff" (NFR-003) and "consolidate to local" (FR-004): the local reduces future diff and is a one-time structural change; net lines added are minimal. | No action. |

### Gate
- CRITICAL: **0** · HIGH: **0** · Unresolved drift: **0** (D1/D2 clarified, D3 info)

**PASS.** Spec and plan are consistent. No structural rework needed → Plan 2nd pass **skipped** (Stage 6).
