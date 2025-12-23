# Research: $60/Month Budget Validation

**Feature**: 1020-validate-budget-60-month
**Date**: 2025-12-22

## RQ-1: How does infracost calculate DynamoDB on-demand costs?

### Decision
Use infracost with usage file for on-demand pricing estimation.

### Rationale
- Infracost reads Terraform state and calculates base costs
- On-demand DynamoDB requires usage estimates (RCUs/WCUs per month)
- Usage file (`infracost-usage.yml`) provides monthly estimates

### AWS Pricing Reference (us-east-1)
- Write Request Unit (WRU): $1.25 per million
- Read Request Unit (RRU): $0.25 per million
- Storage: $0.25 per GB-month

### Calculation for Timeseries Table
- **Writes**: 4000/day × 30 = 120,000 WRUs/month = $0.15/month
- **Reads**: 9600/day × 30 = 288,000 RRUs/month = $0.07/month
- **Storage**: 3MB = ~$0.001/month
- **Total DynamoDB**: ~$0.23/month

## RQ-2: What Lambda invocation assumptions for SSE streaming?

### Decision
Model SSE Lambda as long-running function URL with streaming response.

### Rationale
- Lambda Function URLs support response streaming
- 50 concurrent connections × average 5 minutes per connection
- Heartbeat every 30s doesn't create new invocations (streaming)

### AWS Pricing Reference (us-east-1)
- Invocations: $0.20 per 1 million requests
- Duration: $0.0000166667 per GB-second (128MB = $0.0000020833)
- Function URL: No additional cost

### Calculation for SSE Lambda
- **Invocations**: 50 users × 10 sessions/day = 500/day × 30 = 15,000/month = ~$0.003/month
- **Duration**: 500 × 300s × 0.128GB = 19,200 GB-s/month = $0.32/month
- **Total SSE Lambda**: ~$0.33/month

### Calculation for Ingestion Lambda
- **Invocations**: 500/day × 30 = 15,000/month = ~$0.003/month
- **Duration**: 15,000 × 5s × 0.256GB = 19,200 GB-s/month = $0.32/month
- **Total Ingestion Lambda**: ~$0.33/month

### Calculation for Analysis Lambda
- **Invocations**: 500/day × 30 = 15,000/month = ~$0.003/month
- **Duration**: 15,000 × 10s × 0.512GB = 76,800 GB-s/month = $1.28/month
- **Total Analysis Lambda**: ~$1.29/month

## RQ-3: How to model CloudWatch Logs ingestion?

### Decision
Include log ingestion and storage costs based on Lambda output.

### Rationale
- Each Lambda invocation logs to CloudWatch
- Structured logs ~1KB per invocation
- 30-day retention configured

### AWS Pricing Reference (us-east-1)
- Ingestion: $0.50 per GB
- Storage: $0.03 per GB-month

### Calculation for CloudWatch
- **Log volume**: (15,000 + 15,000 + 15,000) invocations × 1KB = 45MB/month
- **Ingestion**: 0.045GB × $0.50 = $0.02/month
- **Storage**: 0.045GB × $0.03 = ~$0.001/month
- **Total CloudWatch Logs**: ~$0.03/month

## Total Cost Estimate

| Resource | Monthly Cost |
| -------- | ------------ |
| DynamoDB (timeseries table) | $0.23 |
| Lambda (SSE streaming) | $0.33 |
| Lambda (Ingestion) | $0.33 |
| Lambda (Analysis) | $1.29 |
| CloudWatch Logs | $0.03 |
| **Subtotal (new feature)** | **$2.21** |

### Existing Infrastructure (from parent spec)
Per specs/1009-realtime-multi-resolution/plan.md:
- Existing infrastructure: ~$51/month
- **New feature addition**: $2.21/month
- **Total**: ~$53.21/month

## Budget Status: PASS

**$53.21 < $60** - Within budget with $6.79 margin.

## Alternatives Considered

| Alternative | Rejected Because |
| ----------- | ---------------- |
| DAX for caching | $60/month minimum = entire budget |
| Provisioned DynamoDB | Unpredictable workload, on-demand safer |
| CloudWatch Metrics (custom) | Not needed, Logs Insights sufficient |

## Optimization Recommendations (if over budget)

1. **Reduce Lambda memory** - Analysis Lambda could use 256MB instead of 512MB (saves ~$0.64/month)
2. **Increase TTL on timeseries data** - Reduce storage by expiring old data faster
3. **Batch ingestion writes** - Reduce WRUs by batching multiple items per write
