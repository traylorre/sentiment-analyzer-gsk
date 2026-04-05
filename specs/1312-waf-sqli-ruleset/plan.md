# Implementation Plan: WAF SQL Injection Ruleset

**Feature**: 1312-waf-sqli-ruleset
**Created**: 2026-04-02
**Complexity**: Low (single file change, well-understood pattern)

## Changes

### 1. Update WAF Module (`infrastructure/terraform/modules/waf/main.tf`)

#### 1a. Fix header comment (lines 1-12)

Update the rule evaluation order comment to accurately reflect that SQLi is handled by its own dedicated rule group, not CommonRuleSet.

**Before**:
```
#   Priority 1: AWSManagedRulesCommonRuleSet (SQLi, XSS — FR-003, FR-004)
#   Priority 2: AWSManagedRulesKnownBadInputsRuleSet (Log4j, CVEs)
#   Priority 3: AWSManagedRulesBotControlRuleSet (COUNT → BLOCK — FR-005)
#   Priority 4: Per-IP rate-based (2000/5min — FR-002)
```

**After**:
```
#   Priority 1: AWSManagedRulesCommonRuleSet (XSS — FR-004)
#   Priority 2: AWSManagedRulesSQLiRuleSet (SQLi — FR-003)
#   Priority 3: AWSManagedRulesKnownBadInputsRuleSet (Log4j, CVEs)
#   Priority 4: AWSManagedRulesBotControlRuleSet (COUNT → BLOCK — FR-005)
#   Priority 5: Per-IP rate-based (2000/5min — FR-002)
```

#### 1b. Fix Rule 1 comment (line 67-68)

Remove "SQL injection" from Rule 1 comment since CommonRuleSet does not handle SQLi.

**Before**: `# Includes SQL injection, XSS, size constraints, and known bad patterns.`
**After**: `# Includes XSS, size constraints, and known bad patterns.`

#### 1c. Add new Rule 2: AWSManagedRulesSQLiRuleSet (after line 89)

Insert a new rule block for SQL injection detection at Priority 2, between CommonRuleSet (P1) and KnownBadInputs (P2, shifting to P3).

#### 1d. Shift Priority 2 (KnownBadInputs) to Priority 3

Change `priority = 2` to `priority = 3` on the KnownBadInputs rule.

#### 1e. Shift Priority 3 (BotControl) to Priority 4

Change `priority = 3` to `priority = 4` on the BotControl rule.

#### 1f. Shift Priority 4 (RateLimit) to Priority 5

Change `priority = 4` to `priority = 5` on the RateLimit rule.

## No Changes Required

- `variables.tf` — No new variables (SQLi ruleset has no configuration options)
- `outputs.tf` — No new outputs
- `infrastructure/terraform/main.tf` — Module interface unchanged
- `tests/e2e/test_waf_protection.py` — Tests already assert 403 for SQLi payloads

## Verification Plan

1. `terraform fmt -check` — Formatting valid
2. `terraform validate` — HCL valid
3. `terraform plan` — Shows WAF WebACL update (both REGIONAL and CLOUDFRONT)
4. Deploy to preprod
5. Run `pytest tests/e2e/test_waf_protection.py -v` — All tests pass

## Rollback

Revert the single commit. Terraform will remove the SQLi rule group on next apply. No data loss risk (stateless change).
