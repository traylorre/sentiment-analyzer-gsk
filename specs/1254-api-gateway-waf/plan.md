# Implementation Plan: Add WAF v2 WebACL to API Gateway

**Branch**: `1254-api-gateway-waf` | **Date**: 2026-03-24 | **Spec**: `specs/1254-api-gateway-waf/spec.md`

## Summary

Create a WAF v2 WebACL module with per-IP rate limiting (2000/5min), AWS managed rules for SQLi/XSS/bad-inputs/bots, and associate it with the API Gateway stage. Separate module for CloudFront reuse in Feature 1255. OPTIONS preflight exempted via priority-0 ALLOW rule.

## Technical Context

**Language/Version**: HCL (Terraform 1.5+, AWS Provider ~> 5.0)
**Primary Dependencies**: AWS WAF v2, AWS API Gateway (existing)
**Storage**: N/A
**Testing**: `terraform plan` validation, E2E WAF block tests
**Target Platform**: AWS us-east-1 (REGIONAL scope)
**Project Type**: Infrastructure-as-code
**Performance Goals**: <5ms added latency per request (WAF inline evaluation)
**Constraints**: $15/month cost ceiling; must not false-positive on ticker search or config names
**Scale/Scope**: ~15 new Terraform resources (WebACL + rules + association + alarm)

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Auth on management endpoints | PASS | WAF adds layer before Cognito |
| TLS in transit | PASS | API Gateway HTTPS |
| IaC deployment | PASS | Terraform module |
| Health check endpoints | PASS | /health still accessible (WAF default ALLOW) |
| Unit tests | PASS | Terraform plan + E2E block tests |
| GPG-signed commits | PASS | |
| No pipeline bypass | PASS | |

## Project Structure

```text
infrastructure/terraform/
├── modules/waf/                   # NEW module (FR-009: reusable for CloudFront)
│   ├── main.tf                    # WebACL, rules, association
│   ├── variables.tf               # rate_limit, scope, resource_arn, managed rules config
│   └── outputs.tf                 # web_acl_arn, web_acl_id
├── modules/api_gateway/
│   └── outputs.tf                 # Existing: stage ARN needed for association
└── main.tf                        # Wire WAF module with API Gateway stage ARN

tests/
└── e2e/
    └── test_waf_protection.py     # NEW: Rate limit, SQLi, XSS block tests
```

## Architecture

```
Internet → WAF WebACL
             ├── Rule 0 (priority 0): OPTIONS ALLOW (bypass rate counter)
             ├── Rule 1 (priority 1): AWSManagedRulesCommonRuleSet (SQLi, XSS, size limits)
             ├── Rule 2 (priority 2): AWSManagedRulesKnownBadInputsRuleSet (Log4j, etc.)
             ├── Rule 3 (priority 3): AWSManagedRulesBotControlRuleSet (COUNT mode initially)
             ├── Rule 4 (priority 4): Rate-based (2000/5min per IP → BLOCK)
             └── Default action: ALLOW
           → API Gateway (existing rate limit + Cognito) → Lambda
```

### WAF Module Design

The module accepts:
- `scope`: "REGIONAL" (API Gateway) or "CLOUDFRONT" (Feature 1255)
- `resource_arn`: The ARN to associate with (API Gateway stage or CloudFront distribution)
- `rate_limit`: Requests per 5-minute window per IP
- `enable_bot_control`: Toggle for bot detection rule
- `bot_control_action`: "COUNT" or "BLOCK"
- `managed_rule_groups`: List of AWS managed rule group names to include

This design lets Feature 1255 reuse the same module with `scope = "CLOUDFRONT"`.

### API Gateway Stage ARN

The WAF association needs the **stage ARN**, not the API ARN. Current outputs.tf exports `api_arn` but not the stage ARN. Need to add:
```hcl
output "stage_arn" {
  value = aws_api_gateway_stage.dashboard.arn
}
```
