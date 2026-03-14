# Data Model: X-Ray Instrumentation Hardening

**Feature**: 1220-xray-instrumentation-hardening | **Date**: 2026-03-14

## Entities

### Trace Context (frontend-generated)

| Field | Type | Format | Example |
|-------|------|--------|---------|
| Root | string | 1-{hex_ts}-{96bit_hex} | 1-65f2a1b3-a1b2c3d4e5f6a7b8c9d0e1f2 |
| Parent | string | {64bit_hex} | a1b2c3d4e5f6a7b8 |
| Sampled | integer | 0 or 1 | 1 |

**Serialized**: Root=1-{ts}-{id};Parent={parent};Sampled=1
**Lifecycle**: Generated on page init, new Root per SSE connection, new Parent per request.

### SilentFailure/Count Metric (CloudWatch)

| Attribute | Value |
|-----------|-------|
| Namespace | SentimentAnalyzer/Reliability |
| MetricName | SilentFailure/Count |
| Unit | Count |
| Dimensions | FailurePath (string) |

**FailurePath values** (fanout module):
- fanout_batch_write
- fanout_base_update
- fanout_label_update
- fanout_conditional_unexpected

### ConditionalCheck/Count Metric (CloudWatch, NEW)

| Attribute | Value |
|-----------|-------|
| Namespace | SentimentAnalyzer/Reliability |
| MetricName | ConditionalCheck/Count |
| Unit | Count |
| Dimensions | FailurePath (string) |

**FailurePath values**: fanout_conditional

**State transitions**: None (metrics are fire-and-forget counters, not stateful).

## Relationships

- Trace Context flows: Browser -> Next.js proxy -> Lambda Function URL -> X-Ray
- SilentFailure/Count triggers: existing CloudWatch alarm (threshold-based)
- ConditionalCheck/Count: new metric, alarm threshold TBD after 7-day baseline (SC-006)
- ADOT Collector receives OTel spans on localhost:4318 and exports to X-Ray service
