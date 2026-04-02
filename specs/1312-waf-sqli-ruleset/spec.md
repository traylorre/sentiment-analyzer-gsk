# Feature Specification: WAF SQL Injection Ruleset

**Feature Branch**: `1312-waf-sqli-ruleset`
**Created**: 2026-04-02
**Status**: Draft
**Input**: WAF SQL injection tests return 200 instead of 403. The WAF uses `AWSManagedRulesCommonRuleSet` which covers XSS but NOT SQL injection. The dedicated `AWSManagedRulesSQLiRuleSet` managed rule group is missing.

## Problem Statement

The WAF perimeter deployed in Feature 1254 claims to block SQL injection attacks (FR-003), but only includes `AWSManagedRulesCommonRuleSet`. This rule group provides XSS protection via `CrossSiteScripting_*` rules but does NOT include dedicated SQL injection detection rules. SQL injection payloads like `' OR '1'='1` and `'; DROP TABLE users; --'` pass through the WAF unblocked (HTTP 200 instead of 403).

### Root Cause

AWS documents `AWSManagedRulesCommonRuleSet` as covering "general web application security" including some size constraints, bad inputs, and XSS. SQL injection detection is a separate concern handled by `AWSManagedRulesSQLiRuleSet`, which inspects:
- Query parameters (`SQLi_QUERYARGUMENTS`)
- Request body (`SQLi_BODY`)
- Cookie values (`SQLi_COOKIE`)
- URI path (`SQLi_URIPATH`)

The original Feature 1254 implementation incorrectly assumed CommonRuleSet covered SQLi.

### Evidence

- XSS test (`test_xss_url_encoded_blocked`) passes: confirms CommonRuleSet works
- SQLi tests (`test_sqli_in_query_param_blocked`, `test_sqli_drop_table_blocked`) fail with 200: confirms SQLi rules are missing
- Live WAF name: `preprod-sentiment-waf`, associated with API Gateway stage

## User Stories

### US1: SQL Injection Detection

**As a** security engineer,
**I want** WAF to block SQL injection payloads in query parameters, request bodies, and URI paths,
**So that** the API is protected from SQL injection attacks at the perimeter.

**Acceptance Criteria**:
- `' OR '1'='1` in query parameter returns 403
- `'; DROP TABLE users; --` in query parameter returns 403
- Normal queries like `?q=AAPL` return 200 (no false positives)

### US2: Correct Rule Priority Ordering

**As a** platform engineer,
**I want** the SQLi rule group evaluated before rate limiting and bot control,
**So that** injection attacks are blocked early in the rule chain.

**Acceptance Criteria**:
- SQLi ruleset evaluates at Priority 2 (after CommonRuleSet at P1)
- KnownBadInputs shifts to Priority 3
- BotControl shifts to Priority 4
- RateLimit shifts to Priority 5

### US3: Accurate Documentation

**As a** developer reading the WAF module,
**I want** comments to accurately describe which rule group handles which threat,
**So that** there is no confusion about coverage.

**Acceptance Criteria**:
- Module header comment lists SQLi as covered by `AWSManagedRulesSQLiRuleSet`, not CommonRuleSet
- Each rule block has accurate inline comments

## Scope

### In Scope

- Add `AWSManagedRulesSQLiRuleSet` managed rule group to WAF module
- Adjust priority numbering for existing rules (shift P2+ up by 1)
- Fix misleading comments claiming CommonRuleSet handles SQLi
- Update CloudWatch metric name for the new rule

### Out of Scope

- New variables (SQLi ruleset has no configurable options)
- Changes to module interface (no new inputs/outputs)
- Test changes (existing tests already assert 403 for SQLi payloads)
- Rate limit or bot control behavioral changes

## Technical Design

### Rule Priority Order (After Change)

| Priority | Rule | Description |
|----------|------|-------------|
| 0 | OPTIONS ALLOW | Bypass rate counter for CORS preflight (FR-010) |
| 1 | AWSManagedRulesCommonRuleSet | XSS, size constraints, bad patterns |
| 2 | **AWSManagedRulesSQLiRuleSet** | **SQL injection detection (NEW)** |
| 3 | AWSManagedRulesKnownBadInputsRuleSet | Log4j, Java deser, CVEs |
| 4 | AWSManagedRulesBotControlRuleSet | Bot detection (COUNT mode) |
| 5 | Per-IP rate-based rule | 2000 req/5min threshold |

### New Rule Block

```hcl
rule {
  name     = "aws-managed-sqli-rules"
  priority = 2

  override_action {
    none {}
  }

  statement {
    managed_rule_group_statement {
      name        = "AWSManagedRulesSQLiRuleSet"
      vendor_name = "AWS"
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.environment}-waf-sqli-rules"
    sampled_requests_enabled   = true
  }
}
```

### Files Changed

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/waf/main.tf` | Add SQLi rule block, shift priorities, fix comments |

### Files NOT Changed

| File | Reason |
|------|--------|
| `infrastructure/terraform/modules/waf/variables.tf` | No new variables needed |
| `infrastructure/terraform/modules/waf/outputs.tf` | No new outputs needed |
| `infrastructure/terraform/main.tf` | Module interface unchanged |
| `tests/e2e/test_waf_protection.py` | Tests already assert correct behavior (403) |

## Risk Assessment

### Low Risk
- **False positives**: AWS SQLi ruleset is well-tuned and widely deployed. The existing `test_normal_query_not_blocked` test validates no false positives.
- **Priority shift**: Renumbering priorities is a logical change only; WAF evaluates all rules regardless of numbering gaps.

### Mitigations
- Deploy to preprod first (existing pattern)
- Existing E2E tests validate both blocking and pass-through behavior
- `override_action { none {} }` enforces BLOCK (same pattern as other managed rules)

## Verification

- **Pre-deploy**: `terraform plan` shows only WAF WebACL changes (both REGIONAL and CLOUDFRONT)
- **Post-deploy**: Run `pytest tests/e2e/test_waf_protection.py -v` — all SQLi tests should pass (403)
- **Regression**: XSS tests, OPTIONS tests, and normal traffic tests continue to pass
