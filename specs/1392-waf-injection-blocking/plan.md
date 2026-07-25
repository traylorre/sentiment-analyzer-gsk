# Implementation Plan: Enable the Regional API-Gateway WAF in Preprod (waf-enable-preprod)

**Feature**: 1392-waf-injection-blocking
**Created**: 2026-07-24 · **Re-scoped**: 2026-07-24
**Complexity**: Low-mechanically (one tfvars line), Medium-operationally (owner-approved cost, net-new false-positive surface, hard cross-feature ordering dependency on 1393).

## Technical Context

- **Infra**: Terraform HCL 1.5+, AWS Provider ~>5.0, AWS WAFv2 (REGIONAL) + API Gateway REST API.
- **WAF module**: `infrastructure/terraform/modules/waf/` — correct as built (1254/1312). SQLi Priority 2 BLOCK (`main.tf:97-117`), Common/XSS Priority 1 BLOCK (`main.tf:70-90`), REGIONAL, associated to the API Gateway stage ARN (`modules/waf/main.tf:254-258`).
- **Instantiation**: `main.tf:924-950` `module "waf" { count = var.enable_waf ? 1 : 0; scope = "REGIONAL"; resource_arn = module.api_gateway.stage_arn; ... }`.
- **Toggle**: `preprod.tfvars:59 enable_waf = false` (default `true` at `variables.tf:212`). Prod never applied → no WAF anywhere today.
- **Test**: `tests/e2e/test_waf_protection.py` asserts 403 for SQLi/XSS at `PREPROD_API_URL` = API Gateway invoke URL (`deploy.yml:1166,1571`; `main.tf:1480-1483`). One-process `pytest -m preprod` masks the whole job on any failure (`deploy.yml:1600,1631-1643`).
- **Cross-feature dependency**: `main.tf:969` (`waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""`) couples `enable_waf` to `module.waf_cloudfront[0]`, which Feature 1393 removes. See "Ordering dependency" below.
- **Constraints**: checkov pre-commit on `.tf` commits (venv active — hcl2 gotcha); GPG-signed commits; terraform state-lock discipline (CI owns applies; do not run `apply`/`plan -lock` locally while CI deploys).

## Root Action (file:line)

**Flip `infrastructure/terraform/preprod.tfvars:59` → `enable_waf = true`.**

That sets `main.tf:925 count = 1`, creating in `module.waf` (REGIONAL):

| Resource | Why it appears | Count logic |
|---|---|---|
| `aws_wafv2_web_acl.main` | the regional WebACL + managed rules | `count=1` (module instantiated) |
| `aws_wafv2_web_acl_association.main` | associates ACL → API Gateway stage | `scope=="REGIONAL" && resource_arn!="" ? 1 : 0` → 1 |
| `aws_cloudwatch_metric_alarm.waf_blocked` | >500-blocks alarm | `length(alarm_actions)>0 ? 1 : 0` → 1 |

Cost: ~$42/mo — **owner-approved** (sanctioned no-new-resources exception).

**Success = `test_waf_protection.py` returns 403 for SQLi/XSS** against the now-fronted preprod API Gateway, turning the Preprod Integration Tests gate GREEN by making the control work — not by skipping. The prior "read-only output + test-skip" approach is withdrawn.

## Ordering dependency on Feature 1393 (HARD — do not skip)

`main.tf:969`:
```hcl
waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""
```
- **Today** (`enable_waf=false`): false branch → `""`; `module.waf_cloudfront[0]` (which exists, `enable_cloudfront_waf=true`) is not indexed. No error.
- **Combined target end-state** (`enable_waf=true` from this feature + `enable_cloudfront_waf=false` from 1393): true branch → indexes `module.waf_cloudfront[0]`, but 1393 set its `count=0` → **terraform "Invalid index / empty tuple" error.** The end-state is NOT plannable with line 969 as written, in either apply order.

**Resolution (owned by 1393):** change the line-969 guard from `var.enable_waf` to `var.enable_cloudfront_waf` (resource-neutral — when `enable_cloudfront_waf=false` it yields `""`, same as the CloudFront distribution already sees). This decouples the two toggles.

**Sequencing:** 1393's teardown (which carries the line-969 fix + `enable_cloudfront_waf=false`) lands FIRST; THEN this feature flips `enable_waf=true`. After that order:
1. 1393 apply (enable_waf still false): CloudFront WAF module destroyed; line 969 (now guarded on `enable_cloudfront_waf=false`) → `""`; no error; no touch to `module.waf`.
2. This feature's apply (enable_waf false→true): line 969 → `""` (enable_cloudfront_waf false), never indexes the empty module; ONLY `module.waf[0]` is created. Clean.

This feature is therefore a **pure `preprod.tfvars` one-line flip with a hard predecessor** (1393's line-969 decoupling on `main`). It touches no `.tf` of its own.

## Files Changed

| File | Change | Cost |
|------|--------|------|
| `infrastructure/terraform/preprod.tfvars` (line 59) | `enable_waf = false → true` | ~$42/mo (owner-approved) |

## Files NOT Changed

| File | Reason |
|------|--------|
| `infrastructure/terraform/modules/waf/main.tf` | Module correct (1254/1312); no rule/mode change |
| `infrastructure/terraform/main.tf` (incl. line 969) | The line-969 decoupling belongs to Feature 1393 (dependency), not here |
| `tests/e2e/test_waf_protection.py` | Test is correct; it should PASS once the WAF blocks (no skip added) |

## False-Positive (403) Blast Radius

BLOCK-mode `AWSManagedRulesCommonRuleSet` (XSS/generic) and `AWSManagedRulesSQLiRuleSet` inspect query string, body, headers, cookies, and URI. Real API inputs that can trip them:

| Surface | Endpoint (representative) | Legit input that can 403 | Rule likely to fire |
|---|---|---|---|
| Config names | `POST/PATCH /api/v2/configurations` | `O'Reilly Automotive`, `Moody's`, `AT&T`, `<Watchlist>` | SQLi (apostrophe), Common (angle brackets, `&`) |
| Alert thresholds / expressions | alert-rule create/update | free-text notes containing `--`, `';`, `OR 1=1`-like phrasing, comparison operators | SQLi keyword/comment patterns |
| Search / ticker params | `GET /api/v2/tickers/search?q=` | tickers/names with apostrophes or `&` (`AT&T`), quoted phrases | SQLi/Common |
| Notification prefs | notifications save (`PATCH`) | free-text labels/messages with `<`, `>`, `script`, SQL words in prose | Common (XSS), SQLi (keywords) |

**Net-new**: preprod is the first WAF ever for this project (prod never deployed), so there is NO prior prod exposure that already surfaced/absorbed these. Enabling Block-mode can 403 real users on day one.

**De-risk (FR-005):** BEFORE declaring the flip done, run a representative legit-payload set (the rows above) against the WAF-fronted endpoints; triage every 403. Resolve genuine false positives with a **scoped managed-rule exclusion** (`rule_action_override` / `excluded_rule` on the specific sub-rule, or a scope-down statement) — never by disabling the ruleset or leaving BLOCK. Monitor `sampled_requests` + the >500-blocks alarm (`modules/waf/main.tf:264`) during the first days. The requirement stays BLOCK (Q5); a Count observation window is an owner option only (O1), not the plan default.

## Verification Plan

1. Confirm 1393's line-969 decoupling is on `main` (guard reads `var.enable_cloudfront_waf`) and 1393's teardown has applied (`enable_cloudfront_waf=false`, CloudFront WAF gone) — hard predecessor (FR-006).
2. Flip `preprod.tfvars:59 enable_waf=true`; `terraform fmt`/`validate` (venv active); GPG-signed commit; checkov passes.
3. Review `terraform plan -var-file=preprod.tfvars` — MUST show ONLY `module.waf[0].*` creates (WebACL + association + alarm) and NOTHING else (no `module.waf_cloudfront`, no `module.cloudfront_sse` change). Any extra delta BLOCKS (FR-008). (Applies run via CI/PR path — respect state-lock; don't run local `apply`.)
4. Post-apply: `aws wafv2 get-web-acl-for-resource --resource-arn <api-gw stage arn>` returns the ACL (SC-001).
5. `pytest tests/e2e/test_waf_protection.py -m preprod -v`: SQLi/XSS assertions run and PASS (403); pass-through tests PASS (SC-002/003).
6. Legit-payload sweep (FR-005): zero unresolved false-positive 403s (SC-004).
7. Full `pytest tests/ -m preprod`: job result now reflects the real suite; a throwaway failing test confirms it is no longer masked, then removed (SC-003).

## Rollback

Flip `enable_waf` back to `false` (one line) → `terraform apply` destroys the created ACL/association/alarm. No state migration. (If false positives are found post-go-live and cannot be scoped quickly, this is the escape hatch — owner call.)

## Adversarial Review #2

Drift + cross-artifact consistency, then gate.

**Drift vs spec.md**: Root action (flip `enable_waf=true`), the 1393 ordering dependency, the net-new false-positive framing, and the plan/FR mapping match the re-scoped spec 1:1. FR-001↔flip + creates table; FR-002/003↔WAF-on 403 verification; FR-004↔test runs+passes; FR-005↔false-positive sweep; FR-006↔ordering dependency section; FR-007↔fmt/validate/checkov/GPG; FR-008↔plan-shows-only-`module.waf[0]` gate. No orphan FRs.

**Cross-artifact — the creates set**: Plan's three-row creates table matches the module's count logic verified in `modules/waf/main.tf` (association `count = scope=="REGIONAL" && resource_arn!="" ? 1 : 0`; alarm `count = length(alarm_actions)>0 ? 1 : 0`; both → 1 with the `main.tf:924-950` inputs). Consistent.

**Cross-artifact — the coupling**: Plan's line-969 analysis matches spec Attack F and 1393's decoupling. The "not plannable in either order" claim is verified by reading `main.tf:969` (`var.enable_waf ?`) against `main.tf:996` (`count = var.enable_cloudfront_waf ? 1 : 0`). No drift.

**Trap check — "just flip it, it's one line"**: The plan explicitly blocks the flip behind 1393's decoupling (FR-006) and behind a plan-review gate (FR-008), preventing the empty-index terraform error and any collateral resource change. Correct.

**Trap check — false positives dismissed as "already in prod"**: The old plan's dismissal is removed; the net-new framing and mandatory sweep (FR-005) replace it. Consistent with the withdrawn-premise correction.

**Gate**: No CRITICAL/HIGH drift; artifacts consistent and citation-backed. **PASS.**
