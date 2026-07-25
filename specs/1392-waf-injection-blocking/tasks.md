# Tasks: Enable the Regional API-Gateway WAF in Preprod (waf-enable-preprod)

**Feature**: 1392-waf-injection-blocking · **Re-scoped**: 2026-07-24

Dependency-ordered. The single infra change is the OWNER-APPROVED `enable_waf` flip. It has a HARD predecessor: Feature 1393's line-969 decoupling + CloudFront-WAF teardown must land first (else `terraform plan` errors on an empty `module.waf_cloudfront[0]` index). `[P]` = parallelizable.

## Phase 0 — Preconditions

### T001 — Confirm zero-WAF baseline
- **Action**: Verify no WAF exists today: `aws wafv2 get-web-acl-for-resource --resource-arn <api-gw stage arn> --region <region>` → none; `preprod.tfvars:59 enable_waf=false`; `grep enable_waf prod.tfvars` → empty (prod never applied).
- **Maps to**: FR-001 (baseline); spec Q1.
- **Status**: [ ]

### T002 — [BLOCKING] Confirm Feature 1393's line-969 decoupling has landed on `main`
- **Action**: Verify `main.tf:969` now guards on `var.enable_cloudfront_waf` (NOT `var.enable_waf`), and that 1393's teardown applied (`enable_cloudfront_waf=false`, `module.waf_cloudfront` gone). Without this, flipping `enable_waf=true` makes `main.tf:969` index an empty `module.waf_cloudfront[0]` → plan error.
- **Maps to**: FR-006; spec Attack F, Q4.
- **Status**: [ ] BLOCKED until 1393 lands
- **Depends on**: Feature 1393 (line-969 fix + Phase-2 teardown)

### T003 [P] — Confirm the test target is the API Gateway URL
- **Action**: Verify `PREPROD_API_URL` = `dashboard_api_url` = `module.api_gateway.api_endpoint` (`deploy.yml:1166,1571`; `main.tf:1480-1483`). Rules out a Function-URL false negative.
- **Maps to**: spec Adversarial Review #1 Attack A.
- **Status**: [ ]

## Phase 1 — Enable the WAF (owner-approved)

### T004 — Flip `enable_waf = true` in preprod [owner-approved cost]
- **File**: `infrastructure/terraform/preprod.tfvars:59`
- **Action**: `enable_waf = false → true`. `terraform fmt`/`validate` (venv active — checkov hcl2 gotcha); GPG-signed commit. Do NOT touch `main.tf` line 969 here (that is 1393's decoupling).
- **Maps to**: FR-001, FR-007.
- **Status**: [ ]
- **Depends on**: T001, T002 (hard), T003

### T005 — Review the plan: ONLY `module.waf[0]` creates, nothing else
- **Action**: `terraform plan -var-file=preprod.tfvars`. CONFIRM exactly: create `module.waf[0].aws_wafv2_web_acl.main`, `module.waf[0].aws_wafv2_web_acl_association.main[0]`, `module.waf[0].aws_cloudwatch_metric_alarm.waf_blocked[0]`. NO other create/destroy/replace — in particular no change to `module.waf_cloudfront` or `module.cloudfront_sse`. Any extra delta → BLOCK, route to owner. (Apply via CI/PR path; respect state-lock — no local `apply`.)
- **Maps to**: FR-008; SC-005.
- **Status**: [ ]
- **Depends on**: T004

## Phase 2 — Prove it blocks (and doesn't over-block)

### T006 — Verify SQLi/XSS 403 + gate green
- **Action**: Post-apply, `pytest tests/e2e/test_waf_protection.py -m preprod -v`: `?q=' OR '1'='1` → 403, `?q='; DROP TABLE users; --` → 403, `?q=<script>alert(1)</script>` → 403; `?q=AAPL` allowed; pass-through tests PASS. Then full `pytest tests/ -m preprod`; add a throwaway failing test to confirm it's now visible (not masked), remove it. `aws wafv2 get-web-acl-for-resource` returns the ACL.
- **Maps to**: FR-002, FR-003, FR-004; SC-001, SC-002, SC-003.
- **Status**: [ ]
- **Depends on**: T005

### T007 — [GO-LIVE GATE] Legit-payload false-positive sweep
- **Action**: Send a representative LEGITIMATE payload set to the WAF-fronted endpoints and confirm no false 403: config names (`O'Reilly Automotive`, `Moody's`, `AT&T`, `<Watchlist>`), alert-threshold/notes text with `--`/`';`/comparison operators, search params with apostrophes/`&`, notification labels with `<`/`>`/SQL words in prose. Triage every 403; resolve genuine false positives with a SCOPED managed-rule exclusion (`rule_action_override`/scope-down on the specific sub-rule) — never disable the ruleset or leave BLOCK off. Monitor `sampled_requests` + the >500-blocks alarm.
- **Maps to**: FR-005; SC-004; spec US3, Adversarial Review #3.
- **Status**: [ ]
- **Depends on**: T006

## Requirement → Task Map

| Requirement | Tasks |
|-------------|-------|
| FR-001 deploy regional WAF (owner-approved) | T004 |
| FR-002 SQLi 403 | T006 |
| FR-003 XSS 403 | T006 |
| FR-004 test runs+passes, gate green | T006 |
| FR-005 legit-payload false-positive sweep | T007 |
| FR-006 depend on 1393 line-969 decoupling | T002 |
| FR-007 fmt/validate/checkov/GPG | T004 |
| FR-008 plan shows only `module.waf[0]` | T005 |

## Adversarial Review #3

Highest-risk analysis, then READY/BLOCKED.

**Highest risk — false-positive 403s on real users (net-new).** This is the residual risk of the entire feature. Preprod is the FIRST WAF deployment for this project (prod never applied), so there is no prior prod exposure that already surfaced false positives — enabling Block-mode can 403 legitimate traffic on day one. Blast radius (see plan table): config names with apostrophes/angle-brackets (`O'Reilly`, `AT&T`, `<Watchlist>`) → SQLi/Common; alert-threshold free-text with `--`/`';`/operators → SQLi; search params with `&`/apostrophes → SQLi/Common; notification labels with `<`/`>`/SQL prose → Common/XSS. The existing happy-path guard covers only `AAPL`. Mitigation: T007 is a hard go-live gate — a representative legit-payload sweep with scoped exclusions for any real false positive, keeping BLOCK. Owner may optionally choose a short Count observation window instead (O1), trading a brief unprotected window for real-traffic telemetry.

**Second risk — the cross-feature terraform error (empty index).** If `enable_waf=true` is flipped before 1393's line-969 decoupling lands, `main.tf:969` indexes an empty `module.waf_cloudfront[0]` → plan fails. Mitigation: T002 is a BLOCKING precondition; T005's plan-review gate catches any residual coupling before apply.

**Third risk — collateral resource changes in the plan.** A dirty preprod state could bundle unrelated changes with the WAF creates, muddying the "only `module.waf[0]`" claim. Mitigation: T005 requires reading the plan and BLOCKING on any delta beyond the three `module.waf[0]` creates.

**Cost/policy**: the ~$42/mo is owner-approved (the sanctioned no-new-resources exception); not a blocker.

**Verdict**: T001, T003 READY; T002 BLOCKED on 1393; T004–T007 READY once T002 clears, with T007 as the go-live gate. The feature is a single owner-approved tfvars flip gated behind (a) 1393's decoupling and (b) a false-positive sweep. **READY, conditioned on the 1393 predecessor and the T007 go-live gate.**
