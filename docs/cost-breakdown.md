# Infrastructure Cost Breakdown

**Feature**: Real-time Multi-Resolution Dashboard (1009)
**Date**: 2025-12-22
**Budget**: $60/month (SC-010)
**Status**: ✅ PASS ($53.21/month)

## Usage Assumptions

Based on parent spec SC-010 requirements:

| Parameter | Value | Source |
| --------- | ----- | ------ |
| Concurrent Users | 100 | SC-010 |
| Tracked Tickers | 13 | SC-010 |
| News Items/Day | ~500 | Tiingo + Finnhub |
| Active SSE Connections | 50 avg | Dashboard usage |
| Resolution Switches/Day | ~1000 | User interactions |

## Cost Breakdown by Resource

### DynamoDB (Timeseries Table)

On-demand capacity mode for unpredictable workloads.

| Operation | Calculation | Monthly Cost |
| --------- | ----------- | ------------ |
| Write Request Units | 4000/day × 30 = 120,000 WRUs | $0.15 |
| Read Request Units | 9600/day × 30 = 288,000 RRUs | $0.07 |
| Storage | 13 tickers × 8 resolutions × 30 days × 1KB = ~3MB | $0.001 |
| **Subtotal** | | **$0.23** |

**Pricing Reference** (us-east-1):
- WRU: $1.25 per million
- RRU: $0.25 per million
- Storage: $0.25 per GB-month

### Lambda Functions

#### SSE Streaming Lambda

Long-running function with streaming response.

| Metric | Calculation | Monthly Cost |
| ------ | ----------- | ------------ |
| Invocations | 50 users × 10 sessions/day × 30 = 15,000 | $0.003 |
| Duration | 500 × 300s × 0.128GB = 19,200 GB-s | $0.32 |
| **Subtotal** | | **$0.33** |

#### Ingestion Lambda

Processes incoming news items from Tiingo and Finnhub.

| Metric | Calculation | Monthly Cost |
| ------ | ----------- | ------------ |
| Invocations | 500/day × 30 = 15,000 | $0.003 |
| Duration | 15,000 × 5s × 0.256GB = 19,200 GB-s | $0.32 |
| **Subtotal** | | **$0.33** |

#### Analysis Lambda

Performs sentiment analysis on ingested items.

| Metric | Calculation | Monthly Cost |
| ------ | ----------- | ------------ |
| Invocations | 500/day × 30 = 15,000 | $0.003 |
| Duration | 15,000 × 10s × 0.512GB = 76,800 GB-s | $1.28 |
| **Subtotal** | | **$1.29** |

**Lambda Pricing Reference** (us-east-1):
- Invocations: $0.20 per 1 million
- Duration: $0.0000166667 per GB-second

### CloudWatch Logs

Structured logging from all Lambda functions.

| Metric | Calculation | Monthly Cost |
| ------ | ----------- | ------------ |
| Ingestion | 45,000 invocations × 1KB = 45MB | $0.02 |
| Storage | 45MB × 30 days retention | $0.001 |
| **Subtotal** | | **$0.03** |

**CloudWatch Pricing Reference** (us-east-1):
- Ingestion: $0.50 per GB
- Storage: $0.03 per GB-month

## Total Cost Summary

| Resource Category | Monthly Cost |
| ----------------- | ------------ |
| DynamoDB (timeseries table) | $0.23 |
| Lambda (SSE streaming) | $0.33 |
| Lambda (Ingestion) | $0.33 |
| Lambda (Analysis) | $1.29 |
| CloudWatch Logs | $0.03 |
| **New Feature Subtotal** | **$2.21** |
| Existing Infrastructure | ~$51.00 |
| **Total** | **~$53.21** |

## Budget Comparison

| Metric | Value |
| ------ | ----- |
| Budget (SC-010) | $60.00/month |
| Estimated Cost | $53.21/month |
| Remaining Margin | $6.79/month |
| Budget Status | ✅ PASS |

## Optimization Recommendations

If costs need to be reduced in the future:

### 1. Reduce Analysis Lambda Memory

**Current**: 512MB
**Proposed**: 256MB
**Savings**: ~$0.64/month (50% duration cost reduction)
**Trade-off**: Slightly longer execution time for ML inference

### 2. Increase Timeseries TTL

**Current**: 30-day retention
**Proposed**: 14-day retention
**Savings**: ~$0.10/month (storage reduction)
**Trade-off**: Less historical data available

### 3. Batch Ingestion Writes

**Current**: 1 write per item × 8 resolutions = 8 WRUs per item
**Proposed**: BatchWriteItem with 25 items = ~1.5 WRUs per item
**Savings**: ~$0.10/month
**Trade-off**: Increased complexity, slight latency increase

## Alternatives Considered

| Alternative | Rejected Because |
| ----------- | ---------------- |
| DynamoDB DAX | $60/month minimum = entire budget |
| Provisioned DynamoDB | Unpredictable workload, on-demand safer |
| CloudWatch Custom Metrics | Not needed, Logs Insights sufficient |

## References

- [AWS DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [AWS CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [Parent Spec SC-010](../specs/1009-realtime-multi-resolution/spec.md)
