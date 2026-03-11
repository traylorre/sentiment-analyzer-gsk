# X-Ray Groups and Sampling Rules Contract

**FR References**: FR-034, FR-035, FR-094, FR-111, FR-161, FR-175, FR-179, FR-185

## X-Ray Groups

### Group Definitions

| Group Name | Filter Expression | insights_enabled | Purpose |
|------------|-------------------|------------------|---------|
| `sentiment-errors` | `fault = true OR error = true` | `true` | Error trace filtering + CloudWatch metric generation |
| `production-traces` | `!annotation.synthetic` | `true` | Production trace isolation (excludes canary) (FR-185) |
| `canary-traces` | `annotation.synthetic = true` | `true` | Canary trace isolation (FR-185) |
| `sentiment-sse` | `service("sentiment-analyzer-sse")` | `true` | SSE streaming trace monitoring |
| `sse-reconnections` | `annotation.previous_trace_id BEGINSWITH "1-"` | `true` | SSE reconnection correlation (FR-141) |

**Quota**: 25 groups per region (default, adjustable via Service Quotas per FR-172). Current usage: 5 of 25.

### Terraform Resource

```hcl
resource "aws_xray_group" "errors" {
  group_name        = "sentiment-errors"
  filter_expression = "fault = true OR error = true"
  insights_configuration {
    insights_enabled          = true  # FR-111
    notifications_enabled     = true
  }
  tags = local.common_tags
}
```

## Sampling Rules

### Environment-Specific Rules

| Environment | Rule Name | Priority | Reservoir | Rate | Service | Notes |
|-------------|-----------|----------|-----------|------|---------|-------|
| dev | `sentiment-dev-all` | 1000 | 1 | 1.0 | `sentiment-analyzer-*` | 100% sampling (FR-034: reservoir=1) |
| preprod | `sentiment-preprod-all` | 1000 | 1 | 1.0 | `sentiment-analyzer-*` | 100% sampling (FR-034: reservoir=1) |
| prod | `sentiment-prod-apigw` | 100 | 10 | 0.10 | `sentiment-analyzer-dashboard` | API Gateway traces |
| prod | `sentiment-prod-fnurl` | 200 | 5 | 0.05 | `sentiment-analyzer-sse` | Function URL traces (lower rate) |
| prod | `sentiment-prod-default` | 9000 | 5 | 0.10 | `sentiment-analyzer-*` | Catch-all for other services |

**Quota**: 25 sampling rules per region (default, adjustable per FR-172).

### Sampling Rule Constraints

- **FR-035**: Server-side sampling rules override client-supplied `Sampled=1` header on API Gateway
- **FR-094**: Function URL has NO parent sampling context — inherits 100% from no parent; centralized rule required
- **FR-175**: Centralized rules don't override `ParentBasedTraceIdRatio` sampler — Lambda honoring parent decision is correct behavior
- **FR-179**: Sampling graduation plan (4 phases): 100% → 50% → 25% → cost-optimized

### Terraform Resource

```hcl
resource "aws_xray_sampling_rule" "prod_apigw" {
  rule_name      = "sentiment-prod-apigw"
  priority       = 100
  reservoir_size = 10
  fixed_rate     = 0.10
  host           = "*"
  http_method    = "*"
  service_name   = "sentiment-analyzer-dashboard"
  service_type   = "*"
  url_path       = "*"
  version        = 1
  resource_arn   = "*"
  tags           = local.common_tags
}
```

## IAM Permissions (FR-017, FR-159)

All 6 Lambda execution roles + canary role require these 5 X-Ray actions:

```json
{
  "Effect": "Allow",
  "Action": [
    "xray:PutTraceSegments",
    "xray:PutTelemetryRecords",
    "xray:GetSamplingRules",
    "xray:GetSamplingTargets",
    "xray:GetSamplingStatisticSummaries"
  ],
  "Resource": "*"
}
```

**Canary additional permissions** (FR-051, separate IAM role):

```json
{
  "Effect": "Allow",
  "Action": [
    "xray:GetTraceSummaries",
    "xray:BatchGetTraces"
  ],
  "Resource": "*"
}
```

**Amendment 1.8 compliance**: All policies MUST be `aws_iam_policy` + `aws_iam_role_policy_attachment` (no inline policies).
