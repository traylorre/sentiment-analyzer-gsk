# Feature Specification: Enable the Regional API-Gateway WAF in Preprod (waf-enable-preprod)

**Feature Branch**: `1392-waf-injection-blocking`
**Created**: 2026-07-24
**Re-scoped**: 2026-07-24 (owner premise correction — see below)
**Status**: Draft (re-scoped)
**Input (original)**: "`tests/e2e/test_waf_protection.py` fails on EVERY preprod deploy — SQLi/XSS payloads return 200 instead of 403. The failing test masks the entire Preprod Integration Tests job, hiding other regressions."
**Input (re-scope, owner)**: "Prod has NEVER been deployed for this project — there is NO WAF anywhere currently. The app has ZERO WAF coverage right now. Actually ENABLE the regional API-Gateway WAF on preprod (do not gate the test away). ~$42/mo is OWNER-APPROVED — this is the sanctioned exception to no-new-resources."

## Premise Correction (supersedes the prior spec)

The prior version of this spec assumed **prod runs the WAF via `prod.tfvars` default `true`**, so it treated the failing preprod test as a preprod-only cost artifact and defaulted to a **zero-cost test-skip** ("Option B"). That premise is **MOOT and false**:

- **Prod was never deployed.** `prod.tfvars` carries **no** `enable_waf` override (verified: `grep enable_waf prod.tfvars` → empty). The `variables.tf:212` default is `true`, but a default only takes effect at `terraform apply`, and prod has never been applied.
- **Therefore the app has ZERO WAF coverage today** — not in prod, not in preprod. `preprod.tfvars:59 enable_waf = false` means `module.waf` (`main.tf:925 count = var.enable_waf ? 1 : 0`) is `count = 0`. No `aws_wafv2_web_acl.main`, no `aws_wafv2_web_acl_association.main` exist anywhere.
- The prior spec's "Production reality (the security control DOES exist in prod)" section, its "prod carries WAF" assumption, and Q3 are all **withdrawn**.

**Owner decision (this re-scope):** ENABLE the regional API-Gateway WAF on preprod by flipping `preprod.tfvars:59 enable_waf = false → true`. Make the gate GREEN by making the WAF actually block (403), NOT by skipping the assertion. The ~$42/mo cost is **owner-approved** and is the sanctioned exception to the standing no-new-resources constraint.

## Context

### Current State (zero WAF)

`preprod.tfvars:59` = `enable_waf = false` ⇒ `main.tf:925 count = 0` ⇒ no regional WebACL, no association to the API Gateway stage. SQLi/XSS requests reach Lambda unfiltered and return 200/201. `test_waf_protection.py` asserts 403 for those payloads and therefore **fails on every preprod deploy**. Because the Preprod Integration Tests job runs a single `pytest -m preprod` process (`deploy.yml:1600-1601`), any one failure turns the whole job red (`deploy.yml:1631-1643`), masking every other preprod signal.

The WAF **module** is correct as built (Features 1254 + 1312) — it simply is not instantiated:

- SQLi group present, BLOCK mode — `modules/waf/main.tf:97-117` (`override_action { none {} }`, Priority 2).
- Common/XSS group, BLOCK mode — `modules/waf/main.tf:70-90` (Priority 1).
- REGIONAL scope, associated to the API Gateway **stage ARN** — `main.tf:929-930`; `modules/waf/main.tf:254-258`.

### What "enable" actually creates

Flipping `enable_waf=true` sets `main.tf:925 count = 1`, which provisions, in `module.waf` (REGIONAL):

1. `aws_wafv2_web_acl.main` — the regional WebACL with the managed rule groups (SQLi/Common/KnownBadInputs BLOCK; Bot Control COUNT; per-IP rate-limit BLOCK).
2. `aws_wafv2_web_acl_association.main` — associates the ACL to `module.api_gateway.stage_arn` (`count = scope=="REGIONAL" && resource_arn != "" ? 1 : 0` → 1).
3. `aws_cloudwatch_metric_alarm.waf_blocked` — the >500-blocks alarm (`count = length(alarm_actions) > 0 ? 1 : 0` → 1, since `alarm_actions = [module.monitoring.alarm_topic_arn]`).

Cost: ~$42/mo (WAF v2 has no free tier: $5/ACL + managed-rule + per-request). **Owner-approved.**

### Cross-feature coupling with 1393 (CRITICAL — read before sequencing)

`main.tf:969` wires the CloudFront WAF ARN into the CloudFront/SSE distribution:

```hcl
# main.tf:969
waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""
```

This guard is on **`enable_waf`**, but the thing it indexes — `module.waf_cloudfront[0]` — exists only when **`enable_cloudfront_waf`** is true (`main.tf:996 count = var.enable_cloudfront_waf ? 1 : 0`). The two flags historically moved together, so the mismatch was latent. Feature 1393 **deletes** the CloudFront WAF (`enable_cloudfront_waf → false`). The combined target end-state of both features is:

- `enable_waf = true` (this feature) **and** `enable_cloudfront_waf = false` (1393).

Under that end-state, `main.tf:969` evaluates `var.enable_waf` = true → it indexes `module.waf_cloudfront[0]`, but that module has `count = 0` → **terraform errors with "Invalid index / empty tuple."** The end-state is **not plannable** with line 969 as written, regardless of apply order. See Adversarial Review #1 Attack F. Resolution: 1393 changes the line-969 guard to `var.enable_cloudfront_waf` (decoupling fix, resource-neutral, its FR-016), and **1393's teardown lands before this feature's flip** (this feature's FR-006, Clarification Q4).

### Out of Scope

- Re-architecting WAF rules (SQLi/XSS coverage already correct — Features 1254, 1312).
- Rate-limit / bot-control mode changes (Bot Control stays COUNT).
- The CloudFront/SSE WAF teardown itself — that is **Feature 1393** (this feature only depends on 1393's line-969 decoupling landing first).
- Prod deployment (prod has never been applied; not in scope here).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — The regional API-Gateway WAF actually blocks injection in preprod (Priority: P1)

With `enable_waf=true` applied to preprod, SQLi and XSS payloads to the API Gateway endpoint are blocked with HTTP 403 before reaching Lambda; legitimate traffic passes.

**Why this priority**: This is the security control and the reason the gate exists. The owner wants the control real, not asserted-then-skipped.

**Independent Test**: Against preprod post-apply, `GET /api/v2/tickers/search?q=' OR '1'='1` → 403; `GET …?q=<script>alert(1)</script>` → 403; `GET …?q=AAPL` → allowed.

**Acceptance Scenarios**:

1. **Given** preprod with `enable_waf=true` applied and the ACL associated to the API Gateway stage, **When** a request carries `' OR '1'='1` in a query parameter, **Then** WAF returns 403 (`AWSManagedRulesSQLiRuleSet`, Priority 2, BLOCK — `main.tf:101-110`).
2. **Given** the same, **When** a request carries `'; DROP TABLE users; --`, **Then** WAF returns 403.
3. **Given** the same, **When** a request carries `<script>alert(1)</script>`, **Then** WAF returns 403 (`AWSManagedRulesCommonRuleSet`, Priority 1, BLOCK — `main.tf:74-83`).

---

### User Story 2 — The Preprod Integration Tests gate goes GREEN honestly (Priority: P1)

`test_waf_protection.py` runs (not skipped) against the now-WAF-fronted preprod endpoint and PASSES, unmasking the Preprod Integration Tests job so real regressions surface.

**Why this priority**: A permanently-red gate trains everyone to ignore it and buries real regressions. Unmasking must come from the control WORKING, not from deleting the assertion.

**Independent Test**: `pytest tests/ -m preprod` after the apply: the WAF injection tests execute and pass; the job result reflects the real suite.

**Acceptance Scenarios**:

4. **Given** preprod with WAF enabled, **When** the integration job runs, **Then** `test_waf_protection.py` executes (not skip) and its SQLi/XSS assertions PASS (403), and `test_normal_query_not_blocked` / pass-through tests PASS.
5. **Given** an unrelated preprod regression, **When** the job runs, **Then** the job fails **because of that regression**, now visible (not masked by the WAF test).

---

### User Story 3 — Legitimate user inputs are not falsely blocked (Priority: P1)

Real API inputs that superficially resemble attacks (apostrophes, angle brackets, SQL keywords) are validated against the BLOCK-mode managed rules so that enabling WAF does not 403 real users.

**Why this priority**: This is the **net-new** residual risk. Preprod is the **first** environment to ever run this WAF for the project — there is no prior prod exposure that already "absorbed" false positives. A Block-mode managed rule 403-ing legitimate traffic is a real regression for users.

**Independent Test**: A representative legit-payload set (company names with apostrophes, config text with `<`/`>`, free-text containing SQL keywords) is sent to the WAF-fronted endpoints; each is allowed (2xx), or any 403 is triaged before go-live.

**Acceptance Scenarios**:

6. **Given** WAF enabled, **When** a legit config name like `O'Reilly Automotive` or a search for `AT&T` is submitted, **Then** it is allowed (no false 403).
7. **Given** WAF enabled, **When** a legit input contains a SQL keyword in prose (e.g. a note "select the alert threshold"), **Then** it is allowed.
8. **Given** any legit payload that DOES 403 during pre-go-live validation, **When** triaged, **Then** it is resolved by a scoped rule exclusion (not by disabling the ruleset) before the flip is declared done.

---

### Edge Cases

- **Count vs Block**: SQLi (`main.tf:101-110`) and Common/XSS (`main.tf:74-83`) already run in BLOCK (`override_action { none {} }`). The requirement is BLOCK; no Count-mode is introduced for them. Bot Control is COUNT and out of scope. So the ONLY flip that matters for injection blocking is `enable_waf` false→true (deploy vs no-deploy). See Adversarial Review #1 Attack B.
- **Net-new false positives**: With WAF newly on, legit apostrophe/angle-bracket/SQL-keyword inputs can 403. Enumerated in Adversarial Review #3. `test_normal_query_not_blocked` only covers `AAPL` — it does NOT exercise these. This is genuinely new exposure (no prior prod WAF), which is why US3 + a representative validation set are mandatory before declaring the flip done.
- **Line-969 coupling (CRITICAL)**: `enable_waf=true` with `enable_cloudfront_waf=false` (the combined end-state with 1393) makes `main.tf:969` index an empty `module.waf_cloudfront[0]` → terraform error. 1393's decoupling fix (guard on `enable_cloudfront_waf`, 1393 FR-016) MUST land first (this feature's FR-006).
- **Which endpoints are WAF-fronted**: Only API Gateway (this REGIONAL ACL). Lambda Function URLs are NOT WAF-fronted (Feature 1256 restricts them separately). The test hits the API Gateway URL, which is correct (Adversarial Review #1 Attack A).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Preprod MUST deploy the regional API-Gateway WAF by setting `preprod.tfvars:59 enable_waf = true`, provisioning `aws_wafv2_web_acl.main` + `aws_wafv2_web_acl_association.main` (+ the blocked-requests alarm) in `module.waf` (REGIONAL, associated to the API Gateway stage). This is the OWNER-APPROVED ~$42/mo exception to no-new-resources.
- **FR-002**: With WAF enabled, SQLi payloads in a query parameter MUST return HTTP 403 at the API Gateway endpoint (`AWSManagedRulesSQLiRuleSet`, BLOCK).
- **FR-003**: With WAF enabled, XSS payloads in a query parameter MUST return HTTP 403 at the API Gateway endpoint (`AWSManagedRulesCommonRuleSet`, BLOCK).
- **FR-004**: `test_waf_protection.py` MUST run (not skip) and PASS against the WAF-fronted preprod endpoint, unmasking the Preprod Integration Tests gate by making it GREEN. No other preprod test's outcome may remain masked by this test.
- **FR-005**: Before the flip is declared complete, a representative set of LEGITIMATE inputs (apostrophes, angle brackets, SQL keywords across config names / alert thresholds / search-ticker params / notification prefs) MUST be validated against the WAF-fronted endpoints; any false-positive 403 MUST be resolved via a scoped managed-rule exclusion (not by weakening/disabling the ruleset) before go-live.
- **FR-006**: This feature MUST NOT proceed to the `enable_waf` flip until Feature 1393's line-969 decoupling fix (guard on `enable_cloudfront_waf`) has landed on `main`, because `enable_waf=true` + `enable_cloudfront_waf=false` otherwise makes `main.tf:969` index an empty `module.waf_cloudfront[0]` and errors the plan.
- **FR-007**: The change MUST pass `terraform fmt`/`validate` and the checkov pre-commit hook (venv active — hcl2 gotcha); the commit MUST be GPG-signed.
- **FR-008**: `terraform plan` for the flip MUST be reviewed and MUST show ONLY the creation of `module.waf[0].*` (WebACL + association + alarm) — no other resource create/destroy/replace (in particular, no change to `module.waf_cloudfront` or `module.cloudfront_sse`, which 1393 owns). Any additional delta BLOCKS and routes to the owner.

### Key Entities

- **`enable_waf` toggle**: `variables.tf:212` (default true), overridden `false` at `preprod.tfvars:59`. Governs whether `module.waf` (REGIONAL, API-GW) exists.
- **`module.waf`**: REGIONAL WebACL + association to the API Gateway stage ARN + blocked-requests alarm. Count-gated on `enable_waf`.
- **`main.tf:969` guard**: the cross-module wiring that couples `enable_waf` to `module.waf_cloudfront[0]`; decoupled by Feature 1393 (dependency).
- **`test_waf_protection.py`**: Preprod E2E asserting 403 for SQLi/XSS at `PREPROD_API_URL` (= API Gateway invoke URL).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the preprod apply, `aws wafv2 get-web-acl-for-resource --resource-arn <api-gw stage arn>` returns the associated regional WebACL.
- **SC-002**: SQLi and XSS query-parameter payloads return 403 at the preprod API Gateway endpoint; `?q=AAPL` returns 200/201.
- **SC-003**: `test_waf_protection.py` runs and passes; the Preprod Integration Tests job is no longer forced red by it; an unrelated failing test is now visible.
- **SC-004**: The representative legit-input validation set (FR-005) produces zero unresolved false-positive 403s at go-live.
- **SC-005**: `terraform plan` shows exactly the `module.waf[0]` creation set and nothing else (FR-008).
- **SC-006**: `terraform validate`/`fmt` pass; checkov pre-commit passes (venv active); commit GPG-signed.

## Assumptions

- Prod has never been applied → there is no WAF anywhere today; preprod is the first WAF deployment for this project.
- The AWS managed SQLi/Common rulesets block the test payloads once deployed (Features 1254/1312 design; proven by the passing test post-apply).
- Feature 1393 (CloudFront WAF teardown + line-969 decoupling) is being executed in the same battleplan and can land first.
- The ~$42/mo cost is owner-approved (the sanctioned no-new-resources exception).

## Adversarial Review #1

Attacking this spec before it hardens.

**Attack A — "The test hits an un-fronted URL."** REFUTED. `PREPROD_API_URL` = `dashboard_api_url` = `module.api_gateway.api_endpoint` (API Gateway invoke URL — `main.tf:1480-1483`, `deploy.yml:1166,1571`), exactly what a REGIONAL WAF fronts — not the Lambda Function URL. Severity: N/A. Keep the API Gateway target.

**Attack B — "This is a Count-vs-Block bug."** REFUTED. SQLi (`main.tf:101-110`) and Common/XSS (`main.tf:74-83`) already use `override_action { none {} }` = BLOCK. Only Bot Control is COUNT (out of scope). The only flip that matters is `enable_waf` (deploy vs no-deploy). Severity: MEDIUM misdiagnosis → resolved by pinning root cause to the toggle.

**Attack C — "Just skip the test (the old Option B)."** REJECTED by the re-scope. The owner wants the control REAL, not asserted-then-skipped. Skipping would leave the API un-protected and the gate green-by-omission. Severity: was the old default → withdrawn. Resolution: enable the WAF (FR-001) so the test passes on a working control.

**Attack D — "Enabling WAF re-creates billable resources / violates no-new-resources."** ACKNOWLEDGED and ACCEPTED. ~$42/mo, explicitly OWNER-APPROVED as the sanctioned exception (FR-001). Not assumed — stated as an owner decision. Severity: HIGH (cost/policy) → resolved by explicit owner approval recorded in the input.

**Attack E — "Block mode will 403 legitimate users (false positives)."** HIGH — and now **net-new**, not pre-existing. The prior spec argued "this risk is already live in prod, so no delta." That argument is void: prod was never deployed, so **preprod is the first WAF ever** for this project and there is no prior exposure. A Block-mode managed rule can 403 legit apostrophe/angle-bracket/SQL-keyword inputs. Resolution: US3 + FR-005 require a representative legit-payload validation set before go-live, with scoped rule exclusions for any real false positive (never disabling the ruleset). See Adversarial Review #3 for the blast-radius enumeration. Severity: HIGH → resolved by mandatory pre-go-live validation.

**Attack F — "Enabling `enable_waf` is independent of 1393; just flip it."** REFUTED — this is the most dangerous cross-feature trap. `main.tf:969` guards on `enable_waf` but indexes `module.waf_cloudfront[0]`, which 1393 removes (`enable_cloudfront_waf=false`). The combined end-state (`enable_waf=true` + `enable_cloudfront_waf=false`) makes line 969 index an empty tuple → terraform error; the end-state is not plannable as written. Resolution: FR-006 makes 1393's line-969 decoupling (guard on `enable_cloudfront_waf`) a HARD prerequisite that lands first; FR-008 requires the plan to show ONLY `module.waf[0]` creates. Severity: CRITICAL (blocks the whole change) → resolved by the sequencing dependency + plan gate.

**Gate**: No unresolved CRITICAL/HIGH. F resolved by the 1393 dependency (FR-006) + plan gate (FR-008); E resolved by mandatory legit-payload validation (FR-005); D accepted as owner-approved cost. **PASS.**

## Clarifications

Self-answered (≤5), each with evidence.

- **Q1 — Is there any WAF deployed today?** NO. `preprod.tfvars:59 enable_waf=false` → `main.tf:925 count=0`; `prod.tfvars` has no `enable_waf` override and prod was never applied. Zero WAF coverage anywhere. Evidence: `grep enable_waf prod.tfvars` empty; `variables.tf:212` default true only matters at an apply that never happened.
- **Q2 — Is the fix to skip the test or to enable the WAF?** ENABLE the WAF. Owner re-scope: flip `preprod.tfvars:59 enable_waf=true`; make the gate green by making the control block (403), not by skipping. The old test-skip "Option B" is withdrawn.
- **Q3 — Does enabling add net-new false-positive risk?** YES — net-new, because preprod is the first WAF for this project (no prior prod WAF absorbed false positives). Mitigated by FR-005 representative legit-payload validation + scoped exclusions. Evidence: Attack E; `test_normal_query_not_blocked` only covers `AAPL`.
- **Q4 — Can `enable_waf=true` be applied independently of 1393?** NO. `main.tf:969` couples it to `module.waf_cloudfront[0]`; with 1393's `enable_cloudfront_waf=false` the combined state errors on an empty index. 1393's line-969 decoupling MUST land first (FR-006). Evidence: `main.tf:969` vs `main.tf:996`.
- **Q5 — Should any managed rule start in Count to observe before Block?** The requirement is BLOCK for SQLi/XSS, and they are already BLOCK. A Count observation window is NOT introduced for them (it would leave the API unprotected and the test red). Instead, the pre-go-live legit-payload validation (FR-005) de-risks false positives while keeping BLOCK. (Open question O1 records the owner's option to run a short Count window if they prefer observation over an upfront payload sweep.)

### Deferred to owner

- **O1 (Count-vs-Block observation window):** The spec keeps SQLi/XSS in BLOCK (requirement) and de-risks via an upfront legit-payload sweep. If the owner prefers a brief Count-mode observation window on the managed groups before Block (trading a short unprotected window for real-traffic false-positive telemetry), that is an owner call. Default: stay BLOCK, sweep payloads (FR-005).
