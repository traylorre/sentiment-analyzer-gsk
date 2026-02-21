# Task 4: Fix Silent Failure Path Subsegments

**Priority:** P1
**Spec FRs:** FR-002, FR-005, FR-029, FR-043
**Status:** TODO
**Depends on:** Task 1 (IAM permissions), Task 14 (tracer standardization — use Powertools Tracer for automatic exception capture)
**Blocks:** Task 12 (downstream audit depends on knowing which subsegments exist)

---

## Problem

The audit identified **7 silent failure paths** where errors are caught, logged, but create no X-Ray subsegment and emit no metric. An operator cannot find these failures via X-Ray trace filtering — they exist only in CloudWatch Logs.

---

## The 7 Silent Failure Paths

| # | Path | File | Lines | Current Behavior | Impact |
|---|------|------|-------|-----------------|--------|
| 1 | Circuit breaker load | `src/lambdas/shared/circuit_breaker.py` | 334-339 | Logs warning, uses default state | Breaker resets every invocation; defeat fail-open |
| 2 | Circuit breaker save | `src/lambdas/shared/circuit_breaker.py` | 369-374 | Logs error, returns False | Breaker state lost; next invocation sees clean state |
| 3 | Audit trail persist | `src/lambdas/ingestion/audit.py` | 64-72 | Logs error, returns False | Compliance audit trail silently stops |
| 4 | Notification SNS publish | `src/lambdas/ingestion/notification.py` | 127-136 | Logs error, returns None | FR-004 SLA violated (30s notification) |
| 5 | Fanout batch write | `src/lib/timeseries/fanout.py` | 177-184 | Logs error (unprocessed count) | Partial data across resolutions |
| 6 | Self-healing item fetch | `src/lambdas/ingestion/self_healing.py` | 230-238 | Logs warning, continues | Items silently dropped from self-healing |
| 7 | Parallel fetcher errors | `src/lambdas/ingestion/parallel_fetcher.py` | 133-147 | Errors collected in list | No aggregate error subsegment |

---

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/shared/circuit_breaker.py` | Wrap load/save in X-Ray subsegments; mark as error on exception |
| `src/lambdas/ingestion/audit.py` | Wrap DynamoDB put_item in subsegment; mark as error on ClientError |
| `src/lambdas/ingestion/notification.py` | Wrap SNS publish in subsegment; mark as fault on ClientError |
| `src/lib/timeseries/fanout.py` | Wrap BatchWriteItem in subsegment; add error annotation with unprocessed count |
| `src/lambdas/ingestion/self_healing.py` | Wrap individual get_item in subsegment; mark as error on exception |
| `src/lambdas/ingestion/parallel_fetcher.py` | Add aggregate error subsegment after parallel fetch completes |

---

## What to Change

**IMPORTANT (Round 2 — FR-029):** Use Powertools Tracer (`tracer.provider.in_subsegment()` context manager), NOT raw `xray_recorder.begin_subsegment()`. Powertools Tracer automatically captures exceptions as subsegment errors, which is the core requirement of FR-005. With raw `xray_recorder`, exceptions do NOT auto-mark subsegments as error — defeating the purpose of this task.

For each path:
1. Create a named subsegment using `tracer.provider.in_subsegment('name') as subsegment:` wrapping the try/except block
2. Powertools automatically marks the subsegment as error on exception (FR-005 satisfied)
3. Add exception details as subsegment metadata for debugging
4. **Do NOT change the existing catch-and-continue behavior** — the subsegment is additive observability, not a behavior change
5. **Do NOT add try/catch around the Tracer calls themselves** (FR-018)

### Subsegment Names

| Path | Subsegment Name |
|------|----------------|
| Circuit breaker load | `circuit_breaker_load` |
| Circuit breaker save | `circuit_breaker_save` |
| Audit trail persist | `audit_trail_persist` |
| Notification publish | `downstream_notification_publish` |
| Fanout batch write | `timeseries_fanout_batch_write` |
| Self-healing fetch | `self_healing_item_fetch` |
| Parallel fetcher | `parallel_fetch_aggregate` |

---

## Success Criteria

- [ ] All 7 failure paths have named X-Ray subsegments
- [ ] Each subsegment is marked as error/fault when the wrapped exception fires
- [ ] Exception type and message included as subsegment metadata
- [ ] Fanout subsegment includes `unprocessed_count` and `ticker` as annotations
- [ ] Self-healing subsegment includes `source_id` as annotation
- [ ] Existing catch-and-continue behavior unchanged
- [ ] No try/catch around X-Ray SDK calls (FR-018)

---

## Blind Spots

1. **Shared code across Lambdas**: `circuit_breaker.py` is in `shared/` — used by Ingestion and potentially others. The subsegment requires an active X-Ray segment, which exists in any Lambda with Active tracing.
2. **Loop context for self-healing**: Self-healing iterates over items in a loop (line 230). Each iteration should create its own subsegment, not one subsegment for the whole loop.
3. **Parallel fetcher timing**: `parallel_fetcher.py` uses threads. X-Ray subsegments are thread-local. Need to use `xray_recorder.begin_subsegment()` / `end_subsegment()` in each thread context, or create the aggregate subsegment after threads join.
4. **Fanout partial writes**: The unprocessed items may span multiple tables/resolutions. The annotation should capture which resolutions were affected.
5. **Powertools Tracer in shared modules (FR-029)**: Files in `src/lambdas/shared/` create their own `Tracer()` instance. Powertools handles the singleton pattern internally — multiple `Tracer()` calls return the same underlying instance within a Lambda invocation.
6. **Exception auto-capture (FR-029)**: With Powertools `tracer.provider.in_subsegment()`, exceptions are automatically captured as subsegment errors. This eliminates the need for manual `subsegment.add_exception()` calls and is the reason Task 14 (tracer standardization) is a prerequisite.

---

## Dual Instrumentation: CloudWatch Metrics (FR-043 — Round 4)

X-Ray subsegments alone are insufficient for alarming on silent failures. X-Ray sampling means only a fraction of errors produce traces — at 10% production sampling, ~90% of silent failure occurrences have no trace. CloudWatch Lambda `Errors` metric captures 100% of invocations regardless of sampling, but does NOT distinguish which of the 7 failure paths failed.

**Requirement:** Each silent failure path MUST emit a **CloudWatch custom metric** alongside its X-Ray subsegment. This provides:

- **X-Ray subsegment** → trace context for debugging (when sampled)
- **CloudWatch metric** → 100% alarm coverage (always emitted)

### Metrics to Emit

| # | Failure Path | Metric Name | Namespace | Dimensions |
|---|-------------|-------------|-----------|------------|
| 1 | Circuit breaker load | `CircuitBreakerPersistenceFailure` | `SentimentAnalyzer/Reliability` | `Operation=load`, `Lambda={function_name}` |
| 2 | Circuit breaker save | `CircuitBreakerPersistenceFailure` | `SentimentAnalyzer/Reliability` | `Operation=save`, `Lambda={function_name}` |
| 3 | Audit trail persist | `AuditEventPersistenceFailure` | `SentimentAnalyzer/Compliance` | `Lambda={function_name}` |
| 4 | Notification publish | `DownstreamNotificationFailure` | `SentimentAnalyzer/Reliability` | `Lambda={function_name}` |
| 5 | Fanout batch write | `TimeseriesFanoutPartialFailure` | `SentimentAnalyzer/Data` | `Lambda={function_name}` |
| 6 | Self-healing fetch | `SelfHealingItemFetchFailure` | `SentimentAnalyzer/Reliability` | `Lambda={function_name}` |
| 7 | Parallel fetcher | `ParallelFetcherErrors` | `SentimentAnalyzer/Reliability` | `Lambda={function_name}` |

### Implementation Pattern

For each failure path, the pattern is:

```
1. Enter Powertools subsegment (existing — X-Ray trace context)
2. On exception:
   a. Subsegment auto-marks as error (existing — Powertools handles)
   b. Emit CloudWatch metric with value=1 (NEW — via Powertools Metrics or boto3 put_metric_data)
3. Continue existing catch-and-continue behavior
```

Use Powertools Metrics (`metrics.add_metric()`) if already available in the Lambda, or direct `boto3.client('cloudwatch').put_metric_data()`. Powertools Metrics is preferred because it batches emissions efficiently.

### Alarms

Each metric MUST have a CloudWatch alarm (configured in Task 17). The alarms are defined in `fix-alarm-coverage.md`, not here — this task creates the metric emission; Task 17 creates the alarms.
