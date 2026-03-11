# Data Model: X-Ray Exclusive Tracing

**Feature**: 1219-xray-exclusive-tracing | **Date**: 2026-03-10

## Entity Relationship Overview

```
Browser (RUM) ──→ API Gateway ──→ Dashboard Lambda
                                     └──→ DynamoDB (queries)

EventBridge ──→ Ingestion Lambda ──→ DynamoDB (circuit breaker, audit, time-series)
                    └──→ SNS ──→ Analysis Lambda ──→ DynamoDB (ticker buckets)

EventBridge ──→ Notification Lambda ──→ SendGrid (email)
                    └──→ DynamoDB (alert queries)

Scheduler ──→ Metrics Lambda ──→ DynamoDB (queries)
                  └──→ CloudWatch (put_metric_data)

Browser (fetch) ──→ Function URL ──→ SSE Streaming Lambda ──→ DynamoDB (polling)
                                         └──→ CloudWatch (metrics)

EventBridge ──→ Canary Lambda ──→ X-Ray (GetTraceSummaries)
                    └──→ CloudWatch (GetMetricData)
                    └──→ SNS cross-region (out-of-band alert)
```

## Entities

### 1. X-Ray Trace

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| trace_id | string | `1-{timestamp}-{24hex}` | Unique trace identifier, propagated via `X-Amzn-Trace-Id` header |
| segments[] | Segment[] | Lambda runtime + SDK | Ordered collection of segments per service |
| duration | float | Computed | End-to-end trace duration |
| is_error | bool | Segment annotations | Any segment has `error=true` or `fault=true` |
| is_partial | bool | X-Ray API | Trace still being assembled (IsPartial flag) |

**Validation**: trace_id format must match X-Ray spec (`1-{8hex}-{24hex}`).
**State transitions**: Partial → Complete (within 60s typically).

### 2. X-Ray Segment / Subsegment

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| name | string | Tracer/OTel | Service or operation name |
| id | string | SDK-generated | Segment identifier |
| trace_id | string | Propagated | Parent trace ID |
| parent_id | string | Propagated | Parent segment/subsegment ID |
| start_time | float | SDK | Unix epoch timestamp |
| end_time | float | SDK | Unix epoch timestamp |
| fault | bool | SDK | Server error (5xx) |
| error | bool | SDK | Client error (4xx) |
| annotations | map<string, str\|int\|float\|bool> | Application code | Indexed, searchable key-value pairs (max 50/segment) |
| metadata | map<string, any> | Application code | Non-indexed structured data (max 64KB/segment) |
| cause | ErrorCause | SDK | Exception details when fault/error |

**Validation**: annotations limited to 50 per segment, 2KB per value. Metadata limited to 64KB per segment.

### 3. Annotation Schema (Per Lambda)

#### Ingestion Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `ticker_symbol` | string | Clarification R25 | Primary debugging identifier (ANNOTATION, not metadata) |
| `ingestion_duration_ms` | int | Clarification R25 | Raw duration (threshold at query time, not `is_slow` boolean) |
| `failure_path` | string | FR-043 | One of FR-142 disambiguated names (see Silent Failure Metric entity) |
| `error_type` | string | FR-005 | Exception class name on error |

#### Analysis Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `ticker_symbol` | string | FR-043 | Ticker being analyzed |
| `bucket_count` | int | FR-009 | DynamoDB ticker buckets updated |
| `failed_buckets` | string | Clarification R25 | Comma-separated failed bucket names (single subsegment) |

#### SSE Streaming Lambda (OTel spans)
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `connection_id` | string | FR-008 | Unique connection identifier |
| `session_id` | string | FR-048 | Client session for reconnection correlation |
| `previous_trace_id` | string | FR-048 | Previous connection's trace ID |
| `connection_sequence` | int | FR-048 | Reconnection count |
| `cache_hit` | bool | Clarification R25 | Per-lookup cache hit (annotate existing subsegment) |
| `cache_hit_rate` | float | FR-007 | Aggregate rate per poll cycle |
| `latency_ms` | int | FR-006 | Event dispatch latency |
| `event_type` | string | FR-006 | SSE event type |
| `client.disconnected` | bool | FR-085 | True on BrokenPipeError |

#### Dashboard Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `query_type` | string | FR-029 | Dashboard query type |
| `result_count` | int | FR-029 | Number of results returned |

#### Notification Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `recipient_count` | int | FR-028 | Number of email recipients |
| `template_name` | string | FR-028 | SendGrid template used |
| `sendgrid_status` | int | FR-028 | HTTP response code |

#### Metrics Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `metric_count` | int | FR-003 | Number of metrics emitted |
| `query_duration_ms` | int | FR-004 | DynamoDB query duration |

#### Canary Lambda
| Key | Type | FR | Description |
|-----|------|----|-------------|
| `synthetic` | bool | FR-185 | Always `true` (X-Ray Group filter: `annotation.synthetic = true`) |
| `completeness_ratio` | float | FR-113 | Segments found / expected |
| `health_status` | string | FR-019 | HEALTHY / DEGRADED / UNHEALTHY |
| `is_partial` | bool | FR-087 | Trace still assembling |

### 4. CloudWatch Alarm

| Field | Type | Description |
|-------|------|-------------|
| alarm_name | string | `{service}-{lambda}-{metric}-alarm` |
| metric_name | string | Target CloudWatch metric |
| namespace | string | `AWS/Lambda` or `SentimentAnalyzer/Reliability` |
| statistic | string | Sum, Average, p95, etc. |
| threshold | float | Alarm firing threshold |
| comparison | string | GreaterThanThreshold, etc. |
| evaluation_periods | int | Number of periods to evaluate |
| treat_missing_data | string | breaching \| notBreaching \| missing \| ignore |
| dimensions | map | FunctionName, FailurePath, etc. |

**Alarm Categories** (FR-162 classification):

| Category | treat_missing_data | Rationale |
|----------|-------------------|-----------|
| Lambda error count | missing | FR-162: Missing invocation data = investigate |
| Lambda latency P95 | missing | FR-162: Missing latency data = investigate |
| Memory utilization | missing | FR-162: Missing memory data = investigate |
| Silent failure count | missing | Missing = emission failure = investigate |
| X-Ray cost | notBreaching | FR-162: No billing data = no charges = good |
| Canary heartbeat | breaching | FR-121: Heartbeat absence IS the failure |
| ADOT export failure | missing | Missing = no log data = investigate |

### 5. X-Ray Group

| Field | Type | Description |
|-------|------|-------------|
| group_name | string | Descriptive name |
| filter_expression | string | X-Ray filter syntax |
| insights_enabled | bool | Always `true` (FR-111) |

**Groups** (FR-034, FR-141, FR-185):
| Name | Filter Expression | Purpose |
|------|-------------------|---------|
| `sentiment-errors` | `fault = true OR error = true` | Error trace filtering |
| `production-traces` | `!annotation.synthetic` | Production trace isolation (FR-185) |
| `canary-traces` | `annotation.synthetic = true` | Canary trace isolation (FR-185) |
| `sentiment-sse` | `service("sentiment-analyzer-sse")` | SSE trace monitoring |
| `sse-reconnections` | `annotation.previous_trace_id BEGINSWITH "1-"` | SSE reconnection correlation (FR-141) |

### 6. X-Ray Sampling Rule

| Field | Type | Description |
|-------|------|-------------|
| rule_name | string | Rule identifier |
| priority | int | Evaluation order (lower = first) |
| reservoir_size | int | Fixed traces per second |
| fixed_rate | float | Percentage after reservoir |
| service_name | string | Target service |
| host | string | Target host pattern |
| http_method | string | HTTP method filter |

**Rules** (FR-034, FR-161):
| Environment | Reservoir | Rate | Notes |
|-------------|-----------|------|-------|
| dev | 1 | 1.0 | 100% sampling (FR-034: reservoir=1) |
| preprod | 1 | 1.0 | 100% sampling (FR-034: reservoir=1) |
| prod (API GW) | 10 | 0.10 | 10% default, adjustable |
| prod (Function URL) | 5 | 0.05 | Lower rate, no parent context |

### 7. ADOT Collector Config

| Field | Type | Description |
|-------|------|-------------|
| receivers.otlp.protocols.http.endpoint | string | `0.0.0.0:4318` |
| exporters.awsxray.region | string | `${AWS_REGION}` |
| processors | list | `[decouple, batch]` (FR-075/FR-090) |
| service.pipelines.traces | object | receivers → processors → exporters |

### 8. OTel TracerProvider (Singleton)

| Field | Type | Description |
|-------|------|-------------|
| resource | Resource | `service.name`, `cloud.*`, `faas.*` attributes |
| id_generator | AwsXRayIdGenerator | X-Ray-compatible trace IDs |
| sampler | ParentBasedAlwaysOn | Honor Lambda runtime decision |
| span_processors[] | SpanProcessor[] | [BatchSpanProcessor] (R26: AllowListProcessor removed — CI-only PII gate per FR-184 amendment) |

**State transitions**: Uninitialized → Initialized (module-level singleton) → Active (per-invocation extract_context).

### 9. Silent Failure Metric

| Field | Type | Description |
|-------|------|-------------|
| metric_name | string | `SilentFailure/Count` (FR-124) |
| namespace | string | `SentimentAnalyzer/Reliability` (FR-097) |
| dimensions.FunctionName | string | Lambda function name |
| dimensions.FailurePath | string | One of 7 failure paths |
| value | float | 1.0 per occurrence |

**7 Failure Paths** (FR-142 disambiguated names):
1. `circuit_breaker_load` — DynamoDB circuit breaker read failure
2. `circuit_breaker_save` — DynamoDB circuit breaker write failure
3. `audit_trail` — Audit write failure
4. `notification_delivery` — SNS publish failure
5. `self_healing_fetch` — Self-healing mechanism fetch failure
6. `fanout_partial_write` — Time-series fanout partial write failure
7. `parallel_fetcher_aggregate` — Parallel fetch aggregation failure
