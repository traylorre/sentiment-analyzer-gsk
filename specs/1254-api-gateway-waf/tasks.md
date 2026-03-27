# Tasks: Add WAF v2 WebACL to API Gateway

**Input**: Design documents from `/specs/1254-api-gateway-waf/`
**Tests**: Included — E2E tests for WAF block behavior.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Create WAF module directory at `infrastructure/terraform/modules/waf/`
- [x] T002 [P] Create `infrastructure/terraform/modules/waf/variables.tf` with scope, resource_arn, rate_limit, enable_bot_control, bot_control_action, managed_rule_groups, environment, tags variables
- [x] T003 [P] Add `stage_arn` output to `infrastructure/terraform/modules/api_gateway/outputs.tf`

---

## Phase 2: Foundational

- [x] T004 Create `infrastructure/terraform/modules/waf/main.tf` with WebACL resource (default action ALLOW, scope from variable)
- [x] T005 [P] Add OPTIONS ALLOW rule (priority 0) — matches HTTP method OPTIONS, action ALLOW — in `infrastructure/terraform/modules/waf/main.tf`
- [x] T006 [P] Add AWSManagedRulesCommonRuleSet managed rule group (priority 1, action BLOCK) in `infrastructure/terraform/modules/waf/main.tf`
- [x] T007 [P] Add AWSManagedRulesKnownBadInputsRuleSet managed rule group (priority 2, action BLOCK) in `infrastructure/terraform/modules/waf/main.tf`
- [x] T008 [P] Add AWSManagedRulesBotControlRuleSet managed rule group (priority 3, action from variable, default COUNT) in `infrastructure/terraform/modules/waf/main.tf`
- [x] T009 Add per-IP rate-based rule (priority 4, limit from variable, default 2000/5min, action BLOCK) in `infrastructure/terraform/modules/waf/main.tf`
- [x] T010 Add WAF custom response body for BLOCK actions with CORS headers and JSON error message in `infrastructure/terraform/modules/waf/main.tf`
- [x] T011 Create `infrastructure/terraform/modules/waf/outputs.tf` with web_acl_arn, web_acl_id outputs

**Checkpoint**: WAF module complete. `terraform validate` on module alone.

---

## Phase 3: User Story 1 — Per-IP Rate Limiting (Priority: P1) MVP

- [x] T012 [US1] Wire WAF module in `infrastructure/terraform/main.tf` with `module.api_gateway.stage_arn`, scope REGIONAL, rate_limit 2000
- [ ] T013 [US1] Run `terraform plan` — verify WebACL, rules, and association created

---

## Phase 4: User Story 2+3 — SQLi and XSS Protection (Priority: P1)

- [x] T014 [US2] Verify AWSManagedRulesCommonRuleSet includes SQLi and XSS rules in `terraform plan` output
- [x] T015 [P] [US3] Create E2E test `tests/e2e/test_waf_protection.py` — SQLi in query param → 403, XSS in body → 403, normal request → 200

---

## Phase 5: User Story 4 — Bot Detection (Priority: P2)

- [x] T016 [US4] Verify AWSManagedRulesBotControlRuleSet in COUNT mode in `terraform plan` output
- [x] T017 [US4] Add variable `bot_control_action = "COUNT"` in WAF module call in `infrastructure/terraform/main.tf`

---

## Phase 6: User Story 5 — Metrics and Alerting (Priority: P2)

- [x] T018 [US5] Add CloudWatch alarm for WAF BlockedRequests metric (>500 in 5 min) in `infrastructure/terraform/modules/waf/main.tf`
- [x] T019 [US5] Wire alarm_actions (SNS topic) from `module.monitoring.alarm_topic_arn` in `infrastructure/terraform/main.tf`

---

## Phase 7: Polish

- [ ] T020 [P] Run `terraform plan` full validation — verify resource count, no unexpected changes
- [x] T021 [P] Add E2E test cases for rate limit, OPTIONS exemption, and normal traffic in `tests/e2e/test_waf_protection.py`
- [ ] T022 Run existing Playwright E2E suite — verify zero regression
- [ ] T023 Update checkov baseline if new findings (expected: WAF BLOCK rules may flag)
- [ ] T024 Run `terraform apply` and execute verification (SQLi curl, rate limit curl, health check)

---

## Dependencies

- Phase 1-2: Independent (module creation)
- Phase 3: Depends on Phase 2 (WebACL must exist before association)
- Phase 4-5: Depends on Phase 3 (rules are part of the WebACL, deployed together)
- Phase 6: Independent (alarm can be created with WebACL)
- Phase 7: Depends on all previous

All terraform changes deploy atomically in single apply.

---

## Notes

- ~15 new Terraform resources (WebACL, 5 rules, association, alarm, custom response body)
- Cost: ~$12/month
- Rollback: Remove WAF module call from main.tf, `terraform apply`
- Bot Control starts in COUNT mode — switch to BLOCK after monitoring for false positives
