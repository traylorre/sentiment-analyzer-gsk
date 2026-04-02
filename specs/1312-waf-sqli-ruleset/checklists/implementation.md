# Implementation Checklist: WAF SQL Injection Ruleset

**Feature**: 1312-waf-sqli-ruleset

## Pre-Implementation

- [ ] Spec reviewed and adversarial review passed
- [ ] Plan reviewed with no blocking findings
- [ ] Confirm current WAF priority order: P0 OPTIONS, P1 Common, P2 KnownBad, P3 Bot, P4 Rate

## Implementation

- [ ] Header comment updated (SQLi removed from CommonRuleSet, added as own line at P2)
- [ ] Rule 1 inline comment fixed (no longer mentions SQL injection)
- [ ] New rule block added: `AWSManagedRulesSQLiRuleSet` at Priority 2
- [ ] New rule uses `override_action { none {} }` (enforce BLOCK, not COUNT)
- [ ] CloudWatch metric name follows pattern: `${var.environment}-waf-sqli-rules`
- [ ] `sampled_requests_enabled = true` on new rule
- [ ] KnownBadInputs priority shifted: 2 -> 3
- [ ] BotControl priority shifted: 3 -> 4
- [ ] RateLimit priority shifted: 4 -> 5
- [ ] All section header comments updated (Rule 2 -> Rule 3, etc.)

## Post-Implementation

- [ ] `terraform fmt -check` passes
- [ ] `terraform validate` passes
- [ ] `terraform plan` shows WAF update only (no unexpected changes)
- [ ] WCU total stays under 1500 (~1153 expected)

## Verification

- [ ] Deploy to preprod
- [ ] `test_sqli_in_query_param_blocked` passes (403)
- [ ] `test_sqli_drop_table_blocked` passes (403)
- [ ] `test_normal_query_not_blocked` passes (200, no false positives)
- [ ] `test_xss_url_encoded_blocked` still passes (403, regression)
- [ ] `test_options_request_allowed` still passes (200, regression)
- [ ] `test_health_check_passes_waf` still passes (200, regression)
