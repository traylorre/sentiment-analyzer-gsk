# Research: Feature 1254 — WAF v2 WebACL

**Date**: 2026-03-24 | **Status**: Complete

## R1: WAF v2 Rate-Based Rule OPTIONS Exemption

**Decision**: Add priority-0 ALLOW rule for OPTIONS requests before rate-based rule.

**Rationale**: WAF rate-based rules count ALL requests in scope. No built-in method filter on the rate counter. A separate rule that ALLOWs OPTIONS at higher priority (lower number) means OPTIONS requests never reach the rate counter. This is the documented AWS pattern for exempting specific request types.

## R2: WAF Association Target

**Decision**: Associate with API Gateway stage ARN, not REST API ARN.

**Rationale**: `aws_wafv2_web_acl_association` uses `resource_arn` which for API Gateway must be the stage ARN format: `arn:aws:apigateway:{region}::/restapis/{id}/stages/{stage}`. The current API Gateway module exports `api_arn` (REST API) and `execution_arn` but NOT `stage_arn`. Need to add `stage_arn` output.

## R3: CORS on WAF 403 Responses

**Decision**: Use WAF custom response body with CORS headers.

**Rationale**: WAF blocks happen before API Gateway processes the request, so Gateway Response CORS headers (from Feature 1253) don't apply. WAF v2 supports `custom_response_body` on block actions, which can include headers. Configure:
- `Access-Control-Allow-Origin: *` (can't reference request origin in WAF custom response)
- `Access-Control-Allow-Methods: GET,POST,PUT,DELETE,PATCH,OPTIONS`

Note: WAF custom response uses `*` for origin (can't dynamically match). This is acceptable because WAF blocks are security rejections, not normal CORS flow. The browser will see the 403 even with `credentials: 'include'` as long as `Access-Control-Allow-Origin` is present.

## R4: Managed Rule Group Selection

**Decision**: 3 managed rule groups.

| Group | Purpose | Action | Cost |
|-------|---------|--------|------|
| AWSManagedRulesCommonRuleSet | SQLi, XSS, size limits, bad inputs | BLOCK | $1/month |
| AWSManagedRulesKnownBadInputsRuleSet | Log4j, Java deserialization, known CVEs | BLOCK | $1/month |
| AWSManagedRulesBotControlRuleSet | Bot detection, scrapers, vulnerability scanners | COUNT → BLOCK | $1/month |

## R5: Cost Estimate Verification

| Component | Monthly Cost |
|-----------|-------------|
| WebACL | $5.00 |
| 3 rule groups × $1 | $3.00 |
| 1 custom rule (rate-based) | $1.00 |
| 1 custom rule (OPTIONS ALLOW) | $1.00 |
| Per-request: 100K/day × 30 days × $0.60/M | $1.80 |
| **Total** | **~$12/month** |

Under $15 budget ceiling (SC-008).

## R6: Stage ARN Output

Need to add to `modules/api_gateway/outputs.tf`:
```hcl
output "stage_arn" {
  description = "ARN of the API Gateway stage (for WAF association)"
  value       = aws_api_gateway_stage.dashboard.arn
}
```
