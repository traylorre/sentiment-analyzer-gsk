# X-Ray Tracing

> **QUARRYSOME**: unaudited; verify against code before trusting.

## How tracing is set up

Two stacks, split by Lambda type.

**Non-streaming Lambdas** (dashboard, ingestion, analysis, notification, metrics, canary):
Powertools Tracer, instantiated at module level per file (`Tracer(service=...)` in each
handler, plus bare `Tracer()` in shared modules). Exceptions are auto-captured as
subsegment faults by `@tracer.capture_method`.

**SSE streaming Lambda** (`src/lambdas/sse_streaming/`): dual framework. Powertools
Tracer covers the handler phase, constructed with `auto_patch=False`
(`handler.py:32`) so boto3 is not patched twice. The OTel SDK covers the streaming
phase, because the runtime's X-Ray segment closes before RESPONSE_STREAM streaming
begins and standard subsegments cannot attach there.

The OTel side, all in `src/lambdas/sse_streaming/`:

- `tracing.py`: module-level singleton `TracerProvider` (per-invocation creation leaks
  daemon threads), `AwsXRayIdGenerator`, `AwsLambdaResourceDetector`,
  `shutdown_on_exit=False`. Exports OTLP HTTP to `localhost:4318` with a 2s exporter
  timeout. `BatchSpanProcessor` is Lambda-tuned: 1s schedule delay, 1500 queue,
  64 batch. `OTEL_SERVICE_NAME` is required; a missing var logs and disables tracing.
  Kill switch: `OTEL_SDK_DISABLED=true`, no rebuild needed.
- `safe_force_flush()` wraps `force_flush()` in a daemon thread with a 2500ms hard
  join, because the SDK's own timeout parameter is not enforced against a hung
  extension. A `True` return from `force_flush()` proves nothing about export success;
  the canary is the detection path for silent export failure.
- `extract_trace_context()` runs per invocation (`handler.py:550`). Module-level
  extraction would pin every warm invocation to the first trace ID. The custom
  `bootstrap` propagates the trace ID from the Runtime API header on each invocation.
- `Dockerfile`: the SSE Lambda is container-based, so the ADOT collector extension is
  embedded in the image at `/opt/extensions/` (container images cannot use Lambda
  layers). CI downloads the layer zip; local builds tolerate its absence.
- `collector-config.yaml`: processor-less pipeline (`otlp` receiver straight to
  `awsxray` exporter). The ADOT Lambda Extension binary has zero processors compiled
  in, so span retention rides on the SDK-side flush.
- Streaming spans and their attributes: `dynamodb_poll` (`item_count`,
  `changed_count`, `poll_duration_ms`, `cache_hit_rate`, `cache_hit`) in
  `polling.py`; `sse_event_dispatch` (`event_type`, `latency_ms`) in `stream.py`;
  `cloudwatch_put_metric` in `metrics.py`; connection spans (`connection_id`,
  `session_id`) in `connection.py`.
- Lifecycle guards in `stream.py`: a deadline check flushes proactively when under
  3000ms remain, and a `flush_fired` flag stops span creation afterward, since spans
  created post-flush have no export path. Client disconnect (`BrokenPipeError`) is
  annotated `client.disconnected=true` with status OK, not treated as an error.
  Caught exceptions get the explicit dual call: `set_status(ERROR)` plus
  `record_exception()`.
- Every SSE event JSON payload carries a `trace_id` field for frontend correlation.

**Canary** (`src/lambdas/canary/handler.py`): submits synthetic traces on a 5-minute
EventBridge schedule, queries `GetTraceSummaries` with 30/60/90s retries, computes a
completeness ratio against a 0.95 threshold, and emits to `SentimentAnalyzer/Canary`.

**Tests**: `tests/unit/sse_streaming/test_xray_otel_tracing.py` covers the singleton
lifecycle, per-invocation context extraction, span schemas, the `flush_fired` guard,
and the kill switch.

## Operational gotcha: Lambda env var updates

`aws lambda update-function-configuration` REPLACES the entire environment variable
set. Sending only the one variable you want to change (for example, flipping
`OTEL_SDK_DISABLED`) deletes every other variable on the function. Any env-var change
procedure must first capture the existing set with
`aws lambda get-function-configuration`, merge the change locally, and send the
complete set back.

## Open work

Each item below was verified open against the code before being listed here.

### Delete latency_logger.py

`src/lambdas/sse_streaming/latency_logger.py` still exists and is live:
`stream.py` imports `log_latency_metric` and calls it on event creation paths,
dual-emitting alongside the `sse_event_dispatch` span. Before deleting:

- The span carries only `event_type` and `latency_ms`. The logger also carries
  `is_cold_start`, `is_clock_skew` (negative-latency detection), and
  `connection_count`. Port those as span attributes or the clock-skew signal is lost.
- Audit CloudWatch Logs Insights saved queries that `pctile()` over `latency_ms`
  fields; these live in the console, not Terraform.
- Omit an attribute rather than setting it to `None`; OTel attributes accept only
  `str`, `int`, `float`, `bool`.

### Delete cache_logger.py

`src/lambdas/sse_streaming/cache_logger.py` still exists; `stream.py` constructs
`CacheMetricsLogger` and calls `maybe_log()` on a 60s cadence. The `dynamodb_poll`
span already carries `cache_hit_rate` and `cache_hit`. Still uncovered by any span:
`entry_count`, `max_entries`, `trigger`, raw `hits`/`misses`, and the below-threshold
alert the logger emits when hit rate drops. Port the indexed fields as attributes and
the detail fields (`hits`, `misses`, high-cardinality `ticker`) as span metadata, then
delete the module. Any automated check of the cache hit rate SLO (>80%) that reads
cache_logger output must move to the `cache_hit_rate` span attribute.

### Finish correlation ID removal

`generate_correlation_id()` and `src/lib/deduplication.py` are already gone, as is the
`correlation_id` schema field. What remains: `get_correlation_id()` is still defined
in `src/lib/metrics.py:299`, still recommended by that module's docstring, and still
tested by `tests/unit/test_metrics.py`. It has zero production call sites. Delete the
function, its tests, and the docstring guidance. Open decision: whether
`StructuredLogger` (same file) should add an `xray_trace_id` top-level field to every
log entry so Logs Insights queries can join against traces; it emits no trace ID
today. If added, the field is absent when no segment is active, never a fallback ID.

### Downstream consumer audit for the removals above

Terraform carries no references to the latency or cache log field names (verified by
grep across `infrastructure/`). The remaining audit surface is outside the repo:
saved Logs Insights queries in the console, and any runbook that instructs searching
logs by those fields or by the old `{source_id}-{request_id}` correlation format.
Do this audit before the deletions land, not after.
