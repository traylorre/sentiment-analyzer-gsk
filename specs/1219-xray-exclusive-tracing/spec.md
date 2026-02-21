# Feature Specification: X-Ray Exclusive Tracing

**Feature Branch**: `1219-xray-exclusive-tracing`
**Created**: 2026-02-14
**Status**: Draft (Round 4)
**Input**: Full X-Ray trace coverage across entire sentiment-analyzer-gsk system. Consolidate all custom logging, custom correlation IDs, and missing trace propagation onto X-Ray exclusively. Single exception: one non-X-Ray canary to validate X-Ray itself is operational.
**Round 2 Emergent Issues**: (1) SSE Lambda RESPONSE_STREAM mode closes X-Ray segment before streaming completes — orphaned subsegments, (2) asyncio.new_event_loop() breaks X-Ray context propagation in async-to-sync bridge, (3) SendGrid uses urllib not httpx — NOT auto-patched by X-Ray SDK, (4) Powertools Tracer vs raw xray_recorder inconsistency across Lambdas causes silent exception loss in traces.
**Round 3 Emergent Issues**: (1) `begin_segment()` is a documented no-op in Lambda — the "Two-Phase Architecture" proposed in Round 2 is **INVALID**, (2) Powertools `@tracer.capture_method` silently mishandles async generators — falls through to sync wrapper, (3) `EventSource` API does not support custom HTTP headers per WHATWG spec — trace header propagation for SSE requires `fetch()` + `ReadableStream`, (4) Clients can force 100% X-Ray sampling via `Sampled=1` header — cost amplification attack vector, (5) X-Ray has no native "guaranteed capture on error" mode — sampling decisions made before request outcome is known, (6) X-Ray silently drops data at 2,600 segments/sec region limit — no alert on data loss, (7) X-Ray SDK `AsyncContext` loses context across event loop boundaries — must use default `threading.local()` context.
**Round 4 Emergent Issues**: (1) Audit reveals 2 Lambda functions (SSE Streaming, Metrics) have zero CloudWatch error alarms — operators never alerted to failures that X-Ray traces could diagnose, (2) 7 custom metrics emitted without alarms (StuckItems, ConnectionAcquireFailures, EventLatencyMs, MetricsLambdaErrors, HighLatencyAlert, PollDurationMs, AnalysisErrors) — failures invisible to operators, (3) X-Ray Groups only operate on already-sampled traces — at production sampling <100%, error monitoring via trace data misses unsampled errors; CloudWatch metrics required for 100% error alarming, (4) ADOT auto-instrumentation (`AWS_LAMBDA_EXEC_WRAPPER`) conflicts with Powertools Tracer — double-patches botocore, duplicates handler wrapping; must use sidecar-only mode, (5) CloudFront removed from architecture (Features 1203-1207) — browser-to-backend trace propagation works without intermediary; re-adding CloudFront would break it (CloudFront treats `X-Amzn-Trace-Id` as restricted header, replaces client value), (6) X-Ray has no native span links — SSE reconnection trace correlation requires annotation-based pattern (`session_id`, `previous_trace_id`), (7) CloudWatch `put_metric_data` failure makes all `treat_missing_data=notBreaching` alarms false-green — canary must verify CloudWatch emission health in addition to X-Ray health; requires separate IAM role and out-of-band alerting.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Traces a Request End-to-End in X-Ray Console (Priority: P1)

An operator investigating a slow or failed request opens the AWS X-Ray console and sees a complete service map and trace from browser through API Gateway, through every Lambda invocation, through every downstream call (DynamoDB, SNS, SendGrid), and back. No gaps. No disconnected segments. The operator never needs to leave X-Ray to understand what happened.

**Why this priority**: This is the core value proposition. Without end-to-end traces, operators must correlate across multiple tools (CloudWatch Logs Insights, custom correlation IDs, dashboard widgets), which costs investigation time during incidents and increases mean-time-to-resolution (MTTR).

**Independent Test**: Can be fully tested by triggering a single user request (e.g., ticker search) and verifying in the X-Ray console that one continuous trace spans from RUM through API Gateway through Dashboard Lambda through DynamoDB. Delivers immediate operator value.

**Acceptance Scenarios**:

1. **Given** a user searches for ticker "AAPL" in the browser, **When** the operator opens X-Ray traces for that time window, **Then** a single trace ID links the browser RUM segment, the API Gateway segment, the Dashboard Lambda segment (with all subsegments for auth, alerts, DynamoDB calls), and the DynamoDB segment.
2. **Given** the Ingestion Lambda processes a batch of articles and publishes to SNS, **When** the Analysis Lambda is invoked by that SNS message, **Then** both Lambda invocations appear under the same X-Ray trace ID with the SNS hop visible as a connecting segment.
3. **Given** the Notification Lambda sends an email via SendGrid, **When** the operator views the trace, **Then** the SendGrid HTTP call appears as an explicitly instrumented subsegment (not auto-instrumented — SendGrid's HTTP transport is not auto-patched) with status code, duration, and recipient count.
4. **Given** a user connects to the SSE streaming endpoint, **When** the operator views the trace, **Then** the connection lifecycle (authentication, connection acquisition, DynamoDB polling, event serialization) appears as named subsegments with timing data.
5. **(Round 3)** **Given** a request that results in an error/fault under any sampling configuration, **When** the operator searches X-Ray for errored traces, **Then** the complete trace is present including all subsegments and annotations — errored requests are never lost to sampling.

---

### User Story 2 - Operator Diagnoses Silent Failure via X-Ray Error Annotations (Priority: P1)

An operator notices stale dashboard data. Instead of grepping CloudWatch Logs, the operator filters X-Ray traces by error/fault status and immediately sees which subsegment failed — circuit breaker persistence, audit trail write, SNS notification publish, time-series fanout partial write, or self-healing item fetch.

**Why this priority**: Equal to P1 because silent failure paths are the most dangerous blind spots. The audit identified 7 silent failure paths where errors are caught, logged, but emit no metric and create no X-Ray subsegment. These paths currently require log-grepping to diagnose.

**Independent Test**: Can be tested by injecting a DynamoDB throttle on the circuit breaker table and verifying that the X-Ray trace shows an error annotation on the circuit breaker subsegment with the throttle details.

**Acceptance Scenarios**:

1. **Given** DynamoDB throttles the circuit breaker table during Ingestion Lambda execution, **When** the circuit breaker load or save fails, **Then** the X-Ray trace contains a subsegment named "circuit_breaker_load" or "circuit_breaker_save" marked as error with the exception details.
2. **Given** the audit trail DynamoDB write fails during ingestion, **When** the operator filters X-Ray traces by fault, **Then** a subsegment named "audit_trail_persist" appears with the ClientError details.
3. **Given** SNS publish fails in the notification publisher, **When** the operator views the trace, **Then** a subsegment named "downstream_notification_publish" is marked as fault with the SNS error.
4. **Given** a BatchWriteItem has unprocessed items after retries during time-series fanout, **When** the operator views the trace, **Then** a subsegment named "timeseries_fanout_batch_write" shows an error annotation with the count of unprocessed items and affected resolutions.
5. **Given** self-healing skips an item due to a fetch failure, **When** the operator views the trace, **Then** a subsegment named "self_healing_item_fetch" is marked as error with the failed source_id and exception.

---

### User Story 3 - Operator Views SSE Streaming Latency and Cache Performance in X-Ray (Priority: P2)

An operator investigating SSE live update latency opens X-Ray and sees per-event latency as subsegment durations and cache hit rate as annotations — without needing CloudWatch Logs Insights pctile() queries.

**Why this priority**: SSE streaming currently has only 1 X-Ray subsegment (stream_status) despite being the most latency-sensitive Lambda. All latency and cache data is in custom structured logs, requiring a separate CloudWatch Logs Insights query tool. Consolidating onto X-Ray provides single-pane observability.

**Architectural constraint (Round 2 finding, revised in Round 3)**: The SSE Lambda uses `RESPONSE_STREAM` invoke mode with Lambda Function URLs. The Lambda runtime's auto-created X-Ray segment closes when the handler returns the generator — but streaming continues after that. All DynamoDB polling, event dispatch, and CloudWatch metric calls happen DURING streaming, AFTER the segment closes.

~~Round 2 proposed creating "independent X-Ray segments" during streaming linked to the original trace ID.~~ **INVALIDATED in Round 3**: The X-Ray SDK's `begin_segment()` is a documented no-op in Lambda. The SDK's `LambdaContext.put_segment()` silently discards segments (source: `aws_xray_sdk/core/lambda_launcher.py:55-59`), and the `FacadeSegment` raises `FacadeSegmentMutationException` on all mutation operations. Independent segments CANNOT be created within Lambda.

**Round 3 corrected approach**: The system MUST use a tracing mechanism with a lifecycle independent of the Lambda runtime's X-Ray segment. This mechanism must create trace spans during response streaming, link them to the original invocation's trace ID, and export them to X-Ray. The mechanism runs as a separate process within the Lambda execution environment (e.g., a Lambda Extension) that survives after the handler returns and has its own shutdown phase for flushing buffered trace data.

**Independent Test**: Can be tested by connecting to the SSE streaming endpoint, waiting for events, and verifying X-Ray traces contain latency annotations and cache hit rate annotations on spans linked to the connection's trace ID.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda processes a DynamoDB change and sends an event to a connected client, **When** the operator views the trace, **Then** a span named "sse_event_dispatch" contains annotations for `event_type`, `latency_ms`, and `is_cold_start`, linked to the original invocation trace ID.
2. **Given** the SSE Lambda polls DynamoDB for sentiment updates, **When** the operator views the trace, **Then** a span named "dynamodb_poll" contains annotations for `item_count`, `changed_count`, and `poll_duration_ms`.
3. **Given** the SSE Lambda cache reaches a periodic logging trigger, **When** the operator views the trace, **Then** the current span contains annotations for `cache_hit_rate`, `cache_entry_count`, and `cache_max_entries`.
4. **Given** a new SSE connection is acquired, **When** the operator views the trace, **Then** a span named "connection_acquire" contains annotations for `connection_id`, `current_count`, and `max_connections`.

---

### User Story 4 - Operator Traces Browser-to-Backend via X-Ray Headers (Priority: P2)

An operator investigating a specific user's slow experience uses the RUM trace ID to find the exact backend trace. The browser's X-Ray trace ID propagates through the frontend API client and SSE proxy into backend Lambdas, creating one continuous trace from browser to database.

**Why this priority**: Currently, CloudWatch RUM captures browser traces and backend Lambdas capture server traces, but they are disconnected. The frontend does not propagate `X-Amzn-Trace-Id` headers, breaking the client-to-server correlation chain.

**Architectural constraint (Round 3 finding)**: The standard `EventSource` API does not support custom HTTP headers (WHATWG HTML Living Standard, Section 9.2). CloudWatch RUM's automatic trace header injection only patches `window.fetch()`, not `EventSource`. To propagate `X-Amzn-Trace-Id` headers on SSE connections, the frontend MUST use `fetch()` with `ReadableStream` consumption instead of `EventSource`. This loses `EventSource`'s built-in auto-reconnection, which must be reimplemented.

**Independent Test**: Can be tested by making a browser API request, extracting the RUM trace ID, and verifying the same trace ID appears in the backend Lambda's X-Ray trace.

**Acceptance Scenarios**:

1. **Given** a browser makes an API call to the Dashboard endpoint, **When** the frontend API client sends the request, **Then** the request includes an `X-Amzn-Trace-Id` header containing the active RUM trace ID.
2. **Given** a browser connects to the SSE endpoint via the Next.js proxy, **When** the proxy forwards the request to the SSE Lambda, **Then** the proxy propagates the `X-Amzn-Trace-Id` header from the incoming request to the upstream SSE Lambda call.
3. **Given** the CORS configuration for both API Gateway and Lambda Function URLs, **When** a browser sends an `X-Amzn-Trace-Id` header, **Then** the CORS preflight response includes `X-Amzn-Trace-Id` in `Access-Control-Allow-Headers`.
4. **(Round 3)** **Given** the frontend SSE client uses `fetch()` + `ReadableStream` instead of `EventSource`, **When** the connection drops, **Then** the client reconnects with exponential backoff, jitter, and `Last-Event-ID` header propagation — matching the reliability guarantees of `EventSource` auto-reconnection.

---

### User Story 5 - Operator Replaces Custom Correlation IDs with X-Ray Trace IDs (Priority: P3)

Operators and automated systems that currently search for custom `{source_id}-{request_id}` correlation IDs in CloudWatch Logs instead use X-Ray trace IDs as the universal correlation key. The custom correlation ID system is removed.

**Why this priority**: The custom correlation system in `metrics.py:get_correlation_id()` creates a parallel tracing universe. Operators must know to search both X-Ray and CloudWatch Logs with different ID formats. Consolidating on X-Ray trace IDs as the single correlation key eliminates this cognitive overhead.

**Independent Test**: Can be tested by processing an article through ingestion, finding the X-Ray trace ID, and verifying that the same trace ID appears in structured log output as the correlation key (replacing the old `{source}-{request_id}` format).

**Acceptance Scenarios**:

1. **Given** the Ingestion Lambda processes an article, **When** it emits structured logs, **Then** the log field `correlation_id` contains the active X-Ray trace ID (format: `1-{hex_timestamp}-{hex_id}`) instead of the custom `{source_id}-{request_id}` format.
2. **Given** the custom `get_correlation_id()` function and `generate_correlation_id()` function, **When** this feature is complete, **Then** both functions are removed and all call sites use the X-Ray trace ID instead.
3. **Given** any Lambda function emitting structured logs, **When** the log entry is written, **Then** the X-Ray trace ID is automatically included as a top-level field so CloudWatch Logs Insights queries can join with X-Ray traces.

---

### User Story 6 - X-Ray Canary Validates Tracing Infrastructure Health (Priority: P3)

A lightweight, non-X-Ray canary periodically verifies that X-Ray itself is operational and that trace data is not being silently lost. This is the single permitted exception to the "X-Ray exclusive" rule — the "watcher of the watcher" that detects X-Ray regional degradation or throttling-induced data loss before it causes cascading alarm blindness.

**Why this priority**: The audit identified that if CloudWatch `put_metric_data` fails, the entire observability system goes dark. Analogously, if X-Ray ingestion fails or is throttled, all the new tracing coverage becomes invisible. A canary that does NOT depend on X-Ray must verify X-Ray is working.

**Independent Test**: Can be tested by running the canary and verifying it reports X-Ray health status via a non-X-Ray channel.

**Acceptance Scenarios**:

1. **Given** the canary runs on its scheduled interval, **When** it submits a known test trace to X-Ray and queries for it, **Then** within the expected propagation window, the trace is retrievable and the canary reports success.
2. **Given** X-Ray ingestion is degraded (simulated by IAM permission revocation in test), **When** the canary's test trace is not retrievable within the expected window, **Then** the canary reports failure via a non-X-Ray channel (CloudWatch metric with `treat_missing_data = breaching`).
3. **Given** the canary itself fails to run, **When** the expected canary metric is absent, **Then** the CloudWatch alarm with `treat_missing_data = breaching` fires, alerting the operator that the watcher is down.
4. **(Round 3)** **Given** the canary submits N test traces per interval, **When** fewer than N are retrievable within the query window, **Then** the canary reports a `trace_data_loss_ratio` metric, enabling detection of partial data loss from X-Ray throttling.

---

### User Story 7 - Metrics Lambda Gains Full X-Ray Instrumentation (Priority: P2)

The Metrics Lambda — which is the monitoring system's core — gains X-Ray instrumentation so that failures in the monitoring system itself are traceable. Currently, the Metrics Lambda has zero X-Ray SDK integration despite having Active tracing enabled in Terraform.

**Why this priority**: The Metrics Lambda is the "monitor of monitors." If it fails, custom metrics stop being emitted, and alarms that depend on those metrics either fire incorrectly or resolve to green (depending on `treat_missing_data`). Having no X-Ray visibility into its execution makes diagnosing these failures impossible.

**Independent Test**: Can be tested by invoking the Metrics Lambda and verifying X-Ray shows subsegments for DynamoDB queries and CloudWatch metric emission.

**Acceptance Scenarios**:

1. **Given** the Metrics Lambda is invoked, **When** it queries DynamoDB for stuck items, **Then** the X-Ray trace contains a subsegment for the DynamoDB query with item count and duration.
2. **Given** the Metrics Lambda emits CloudWatch metrics, **When** the `put_metric_data` call succeeds, **Then** the X-Ray trace contains a subsegment for the CloudWatch API call.
3. **Given** the Metrics Lambda's `put_metric_data` call fails (throttled, permission denied), **When** the operator views the trace, **Then** the subsegment is marked as error with the exception details.

---

### User Story 8 - Guaranteed Error Trace Capture (Priority: P1) *(Round 3 — New)*

An operator investigating a production error is guaranteed to find an X-Ray trace for that errored request. The system ensures that all error/fault traces are captured and queryable, regardless of traffic volume or sampling configuration. Successful requests may be sampled, but errors are always traced.

**Why this priority**: X-Ray sampling decisions are made BEFORE the request completes (at the entry point, the outcome is unknown). Under default sampling (1 request/second + 5%), most errored requests in a high-traffic window would be untraced. For a system that uses X-Ray as its EXCLUSIVE debugging tool, losing error traces makes incidents undiagnosable. This is a P1 because it directly affects the viability of Story 1 and Story 2 during real incidents.

**Independent Test**: Can be tested by configuring sampling, generating 100 requests that result in errors, and verifying that 100% of errored traces are retrievable in X-Ray.

**Acceptance Scenarios**:

1. **Given** the system is running with production sampling rules, **When** a Lambda invocation results in an error/fault, **Then** the complete trace (including all subsegments and annotations) is captured and queryable in X-Ray.
2. **Given** an X-Ray Group configured with the filter `fault = true OR error = true`, **When** errored traces are captured, **Then** the group generates CloudWatch metrics (error count, error rate, latency percentiles), enabling alarm-based monitoring from trace data.
3. **Given** dev/preprod environments, **When** any request is made, **Then** 100% of requests are traced (no sampling), ensuring complete debuggability during development.
4. **Given** the production sampling rate controls cost for successful requests, **When** the monthly X-Ray cost exceeds configured thresholds ($10, $25, $50), **Then** a CloudWatch billing alarm fires.

---

### User Story 9 - Trace Data Integrity Protection (Priority: P2) *(Round 3 — New)*

An operator is alerted when trace data is being silently lost due to X-Ray throttling, daemon failure, or systematic SDK errors. The system treats undetected trace data loss as a first-class failure mode, because an operator who trusts X-Ray traces that aren't there will misdiagnose issues.

**Why this priority**: X-Ray has a hard throughput limit (2,600 segments/second/region). When exceeded, `PutTraceSegments` returns throttled segments in `UnprocessedTraceSegments` — data is silently lost, not queued, no alarm fires. If the system's EXCLUSIVE debugging tool is losing data without alerting, operators have a false sense of complete observability.

**Independent Test**: Can be tested by configuring the canary to track submission-vs-retrieval ratios and verifying that simulated data loss (temporary IAM revocation or throughput saturation) triggers an alert within 2 canary intervals.

**Acceptance Scenarios**:

1. **Given** the X-Ray canary submits N test traces per interval, **When** fewer than N traces are retrievable within the query window, **Then** the canary emits a `trace_data_loss_ratio` metric and the CloudWatch alarm fires when the ratio exceeds the configured threshold.
2. **Given** the system approaches the X-Ray region throughput limit, **When** the canary detects consecutive intervals with data loss, **Then** an operator is alerted to investigate throttling or daemon health.

---

### User Story 10 - Operator Is Alerted to All Failure Modes Regardless of X-Ray Sampling (Priority: P1) *(Round 4 — New)*

An operator is automatically alerted when any Lambda function errors, when latency breaches SLO thresholds, or when critical application metrics indicate degradation — regardless of whether the specific request was X-Ray sampled. CloudWatch alarms on Lambda built-in metrics and custom application metrics provide the 24/7 alerting signal; X-Ray traces provide the diagnostic context when operators investigate.

**Why this priority**: The audit identified 2 Lambda functions (SSE Streaming, Metrics) with zero error alarms and 7 custom metrics emitted without alarms. Without alarms, operators only discover these failures from customer complaints or by staring at dashboards. This directly undermines the value of X-Ray traces — operators don't know to look at X-Ray if nothing alerts them to a problem.

**Scope clarification**: "X-Ray exclusive" applies to **tracing** — the mechanism for distributed request tracing, latency analysis, and dependency visualization. CloudWatch alarms on Lambda built-in metrics (Errors, Duration, Throttles) and custom application metrics are a separate, complementary system for **operational alerting**. Alarms tell operators "something is wrong"; X-Ray traces tell operators "what went wrong and where." Both are required. CloudWatch alarms are NOT duplicative with X-Ray.

**Independent Test**: Can be tested by injecting errors into each Lambda function and verifying CloudWatch alarms fire within the configured evaluation period.

**Acceptance Scenarios**:

1. **Given** the SSE Streaming Lambda errors, **When** the error count exceeds the configured threshold within the evaluation period, **Then** a CloudWatch alarm fires and notifies the on-call operator.
2. **Given** the Metrics Lambda errors, **When** the error count exceeds the configured threshold within the evaluation period, **Then** a CloudWatch alarm fires — alerting operators that the monitoring system itself has failed.
3. **Given** items remain stuck in "pending" status beyond the SLO threshold, **When** the StuckItems metric exceeds threshold, **Then** a CloudWatch alarm fires, alerting operators to stale dashboard data before customers notice.
4. **Given** SSE connection pool exhaustion, **When** ConnectionAcquireFailures exceeds threshold, **Then** a CloudWatch alarm fires, alerting operators that new SSE connections are being rejected.
5. **Given** SSE live update latency breaches the p95 < 3000ms SLO, **When** EventLatencyMs p95 exceeds threshold, **Then** a CloudWatch alarm fires.

---

### User Story 11 - Meta-Observability for Monitoring Infrastructure (Priority: P1) *(Round 4 — New)*

An operator is alerted when the monitoring infrastructure itself fails — whether X-Ray trace ingestion, CloudWatch metric emission, or the canary itself. A broken monitoring system that silently reports "all green" is the single most dangerous failure mode because it prevents detection of all other failures.

**Why this priority**: The audit Section 8.1 identifies CloudWatch `put_metric_data` failure as "the single most dangerous blind spot." If metric emission fails, alarms with `treat_missing_data = notBreaching` resolve to OK (false green), while alarms with `treat_missing_data = breaching` fire correctly but only cover those specific alarms. The X-Ray canary (US6) addresses X-Ray health but not CloudWatch health. The monitoring system needs a unified meta-observability canary that verifies both the tracing plane (X-Ray) and the alerting plane (CloudWatch metrics) are functional.

**Independent Test**: Can be tested by temporarily revoking the application Lambda's CloudWatch permissions and verifying the canary detects the emission failure within 2 intervals.

**Acceptance Scenarios**:

1. **Given** the canary emits a test metric to CloudWatch and queries for it after the ingestion delay, **When** the metric is retrievable, **Then** the canary reports CloudWatch metric pipeline health as healthy.
2. **Given** CloudWatch `put_metric_data` is failing for application Lambdas (simulated via IAM revocation), **When** the canary's test metric query returns empty results, **Then** the canary reports failure via a channel independent of CloudWatch alarms.
3. **Given** all alarms where metric absence indicates failure, **When** the `treat_missing_data` configuration is audited, **Then** 100% of those alarms use `breaching`.
4. **Given** the canary uses a separate IAM role from application Lambdas, **When** application IAM permissions are changed, **Then** the canary retains its ability to emit and query metrics, ensuring it can detect the failure.

---

### Edge Cases

- What happens when the X-Ray daemon is throttled (SDK rate limiting)? Subsegments beyond the sampling rate are dropped, but the Lambda still executes normally. The X-Ray SDK handles throttling internally; the system must not add error-suppression around it (see FR-018).
- What happens when a long-running SSE connection spans multiple X-Ray trace windows (traces have a 5-minute default window)? Each DynamoDB poll cycle within the SSE Lambda creates its own trace. The connection lifecycle subsegments must be scoped to the poll cycle, not the entire connection.
- What happens when the X-Ray canary reports failure but X-Ray is actually healthy (false positive)? The canary query window must account for X-Ray's eventual consistency delay (typically 5-30 seconds). The canary MUST NOT trigger on a single missed query — require consecutive failures.
- What happens when CloudWatch RUM sampling is reduced in production (10% sampling)? Only 10% of browser sessions generate RUM trace IDs. For the remaining 90%, the browser-side API client MUST still generate a valid `X-Amzn-Trace-Id` header so backend traces are created regardless of RUM sampling. Note: this applies to the browser-side API client only; the server-side SSE proxy (see next edge case) has different behavior.
- What happens when the SSE proxy (server-side) does not have an incoming `X-Amzn-Trace-Id` header? The server-side proxy MUST NOT generate a synthetic trace ID. Let the Lambda runtime assign the trace ID. Generating server-side trace IDs without proper SDK context would produce invalid trace context. The boundary is: browsers generate trace IDs (via RUM SDK); server-side proxies forward but never originate them.
- What happens when X-Ray annotation limits are reached? X-Ray allows a maximum of 50 annotations per subsegment, with values up to 2,048 characters. The annotations defined in FR-006 through FR-009 total fewer than 15 per subsegment. If future extensions approach the limit, non-essential annotations must be moved to X-Ray metadata (non-indexed, no limit).
- What happens to CloudWatch alarms, Log Insights saved queries, or dashboards that reference the old custom correlation ID format or the structured log fields being removed? Any downstream consumers of the removed systems (latency_logger fields, cache_logger fields, `correlation_id` in the old format) MUST be audited and updated as part of this feature. Failing to update them would cause silent breakage.
- What is the relationship between X-Ray sampling and the "any user request" tracing claim? X-Ray uses sampling (default: 1 request/second + 5% of additional requests). SC-001 applies to sampled requests. Dev/preprod uses 100% sampling. Production sampling must guarantee error trace capture (see FR-034) while controlling cost for successful requests.
- **(Round 2)** What happens when the SSE Lambda's X-Ray segment closes before streaming completes? The Lambda runtime creates a segment on invocation and closes it when the handler returns the generator. But `RESPONSE_STREAM` mode means the bootstrap continues polling the generator for chunks AFTER the handler returns. All boto3 calls during streaming (DynamoDB polls, CloudWatch metric emission) happen after segment closure. ~~The system MUST create independent segments during streaming, linked to the original trace ID.~~ **INVALIDATED in Round 3**: `begin_segment()` is a no-op in Lambda (see Assumption 7 invalidation). The system MUST use a tracing mechanism with an independent lifecycle (see FR-026 revised).
- **(Round 2)** What happens when `asyncio.new_event_loop()` is used in the async-to-sync bridge? The default `threading.local()` context storage DOES correctly propagate X-Ray context through `asyncio.new_event_loop().run_until_complete()` on the same thread. However, the X-Ray SDK's `AsyncContext` (which uses `TaskLocalStorage`) loses context across event loop boundaries. The system MUST NOT configure `AsyncContext` (see FR-037).
- **(Round 2)** What happens with X-Ray annotation type validation? The X-Ray SDK accepts `str`, `int`, `float`, and `bool` as annotation values. Any other type (including `None`, `list`, `dict`) is silently dropped with only a `log.warning()`. All annotations defined in FR-006 through FR-009 use valid types (confirmed: `latency_ms` is int, `cache_hit_rate` is float, `is_cold_start` is bool). Implementers MUST NOT pass `None` values — use a sentinel value or omit the annotation.
- **(Round 2)** What happens when raw `@xray_recorder.capture` is used instead of Powertools `@tracer.capture_method`? Raw xray_recorder does NOT automatically capture exceptions as subsegment errors. If an exception is raised inside a `@xray_recorder.capture`-decorated function, the subsegment is closed but not marked as error/fault. Powertools Tracer does this automatically. The spec's FR-005 requirement (mark subsegments as error on exception) is NOT satisfied by raw xray_recorder alone — either use Powertools Tracer or add manual exception capture.
- **(Round 3)** What happens when `@tracer.capture_method` is applied to an async generator function? The decorator does NOT check `inspect.isasyncgenfunction()` (confirmed: zero matches in Powertools codebase). It falls through to `_decorate_sync_function()`, which wraps the generator CREATION (near-zero time) rather than ITERATION. The subsegment opens and closes instantly, capturing no meaningful timing. Additionally, the decorator destroys the async generator's type signature (`inspect.isasyncgenfunction()` returns `False` on the wrapped function). System MUST NOT use `@tracer.capture_method` on async generators (see FR-031).
- **(Round 3)** What happens when the frontend uses `EventSource` for SSE connections? The `EventSource` API does not support custom HTTP headers (WHATWG HTML Living Standard, Section 9.2). The constructor accepts only a URL and optional `withCredentials`. CloudWatch RUM's automatic trace header injection patches `window.fetch()` but NOT `EventSource`. Trace headers CANNOT be propagated via `EventSource`. The frontend MUST use `fetch()` + `ReadableStream` for SSE connections that require trace propagation (see FR-032).
- **(Round 3)** What happens when a malicious client sends `Sampled=1` in the `X-Amzn-Trace-Id` header? X-Ray respects the incoming `Sampled` field as the authoritative sampling decision when it is already decided (not `?`). A client that always sends `Sampled=1` forces 100% server-side sampling, inflating costs at $5 per million traces. Server-side sampling rules MUST override client-supplied decisions (see FR-035).
- **(Round 3)** What happens when X-Ray throughput exceeds the region limit (2,600 segments/second)? `PutTraceSegments` returns HTTP 429 `ThrottledException`. Throttled segments appear in the `UnprocessedTraceSegments` response array — data is silently lost, not queued, not retried. The X-Ray daemon buffers and batches, providing some burst capacity, but sustained throughput above the limit results in permanent data loss with no alarm or notification.
- **(Round 3)** What happens when the SSE Lambda adds the ADOT Lambda Extension for independent lifecycle tracing? Lambda Extensions add cold start overhead (typically 50-200ms for ADOT) and memory overhead (~40-60MB). For the SSE Lambda with a 15-second streaming lifecycle, the relative impact is small. The extension's INIT phase runs concurrently with the Lambda runtime's INIT, partially masking the overhead.
- **(Round 3)** What happens when traffic grows beyond cost-effective 100% sampling? At current traffic levels (<1M requests/month), 100% sampling costs <$5/month. If traffic grows to 100M requests/month, 100% sampling costs ~$500/month. The X-Ray cost budget alarm (FR-038) provides early warning. The scaling path is tail-based sampling via an external OpenTelemetry Collector with a tail sampling processor, which makes sampling decisions AFTER spans complete — always keeping error traces while dropping a percentage of successful ones. This is documented as a future upgrade path, not a current requirement.
- **(Round 4)** What happens if CloudFront is re-introduced to the architecture? CloudFront treats `X-Amzn-Trace-Id` as a restricted header and replaces the client-sent value with its own trace ID. If CloudFront is added between browser and API Gateway, the RUM-generated trace context from the browser would be lost. The mitigation would be to rely on CloudFront's own X-Ray edge segment rather than browser-originated trace IDs. Source: AWS CloudFront documentation — `X-Amzn-Trace-Id` is listed as a restricted header that cannot be overridden via custom headers policies.
- **(Round 4)** What happens when ADOT auto-instrumentation is accidentally enabled on the SSE Lambda via `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler`? ADOT's `AwsLambdaInstrumentor` wraps the handler entry point (conflicting with Powertools `@tracer.capture_lambda_handler`), and `BotocoreInstrumentor` patches botocore (conflicting with X-Ray SDK patching from Powertools). Every boto3 call produces duplicate spans/subsegments in X-Ray. The env var MUST NOT be set on any Lambda that uses Powertools Tracer.
- **(Round 4)** What happens when the OTel `service.name` resource attribute and Powertools `POWERTOOLS_SERVICE_NAME` differ on the SSE Lambda? X-Ray service map aggregates nodes by service name. Mismatched names cause the same Lambda to appear as two disconnected nodes — one for handler-phase subsegments (Powertools) and one for streaming-phase spans (ADOT). Both names MUST be identical for a unified service map.
- **(Round 4)** What happens when an SSE connection drops and the client reconnects with `fetch()` + `ReadableStream`? The new `fetch()` call gets a new trace ID from RUM. The old trace (showing the connection drop) and new trace (showing the reconnection) are disconnected in X-Ray. X-Ray does not support native OpenTelemetry span links — link data stored in segment metadata is not surfaced in the X-Ray console or queryable via API. The system uses annotation-based correlation: a stable `session_id` annotation on all SSE traces enables querying all traces for a logical session, and a `previous_trace_id` annotation on reconnection traces provides explicit backward reference.
- **(Round 4)** What happens when X-Ray sampling rate is <100% in production and an error occurs on an unsampled request? The error is captured by the CloudWatch Lambda `Errors` metric (100% fidelity, independent of X-Ray sampling), but the X-Ray trace for that specific errored request does not exist — unsampled traces (`Sampled=0`) are permanently lost because data is never sent to the X-Ray service. Operators use CloudWatch alarms for alerting (100% error detection) and X-Ray traces for diagnosis (available for sampled requests). At current traffic levels with 100% sampling, this gap does not manifest.
- **(Round 4)** What is the relationship between X-Ray Groups and X-Ray sampling? X-Ray Groups are post-ingestion filters that only operate on already-sampled, already-ingested traces. A Group with filter `fault = true` generates CloudWatch metrics only from faulted traces that were sampled and ingested. If a request errors but was not sampled (`Sampled=0`), no X-Ray data exists and no Group will ever see it. Groups are a monitoring tool for sampled trace data, not a mechanism to ensure error capture. This is why CloudWatch alarms on Lambda built-in metrics (which capture 100% of invocations regardless of X-Ray) are required alongside X-Ray Groups.

## Requirements *(mandatory)*

### Functional Requirements

**Backend Lambda X-Ray Subsegments**

- **FR-001**: System MUST add X-Ray tracing to all SSE Streaming Lambda operations: global stream handling, config stream handling, DynamoDB polling, connection acquisition, connection release, and event dispatch. Because the SSE Lambda uses `RESPONSE_STREAM` invoke mode, the Lambda runtime's auto-created segment closes before streaming begins. Tracing during streaming MUST use a mechanism with an independent lifecycle that does not depend on the Lambda runtime's X-Ray segment being open (see FR-026 revised).
- **FR-002**: System MUST add X-Ray subsegments to all 7 silent failure paths: (1) circuit breaker load, (2) circuit breaker save, (3) audit trail persistence, (4) downstream notification SNS publish, (5) time-series fanout batch write, (6) self-healing item fetch, (7) parallel fetcher error aggregation.
- **FR-003**: All service calls made by the Metrics Lambda (DynamoDB queries, CloudWatch API calls) MUST appear as auto-instrumented subsegments in X-Ray traces. Currently, the Metrics Lambda has zero X-Ray SDK integration despite Active tracing being enabled at the infrastructure level.
- **FR-004**: System MUST add explicit X-Ray subsegments to the Metrics Lambda for DynamoDB queries and CloudWatch `put_metric_data` calls.
- **FR-005**: System MUST mark X-Ray subsegments as error/fault when the wrapped operation catches an exception, including the exception type and message as metadata.

**X-Ray Annotations and Metadata**

- **FR-006**: System MUST replace custom structured latency logging in `latency_logger.py` with X-Ray subsegment annotations containing: `event_type`, `latency_ms`, `is_cold_start`, `is_clock_skew`, `connection_count`.
- **FR-007**: System MUST replace custom structured cache logging in `cache_logger.py` with X-Ray subsegment annotations containing: `cache_hit_rate`, `cache_entry_count`, `cache_max_entries`, `trigger`, `is_cold_start`.
- **FR-008**: System MUST include X-Ray annotations on connection lifecycle subsegments: `connection_id`, `current_count`, `max_connections`.
- **FR-009**: System MUST include X-Ray annotations on DynamoDB polling subsegments: `item_count`, `changed_count`, `poll_duration_ms`, `sentiment_type`.

**Correlation ID Consolidation**

- **FR-010**: System MUST replace the custom `get_correlation_id()` function with X-Ray trace ID retrieval from the active segment.
- **FR-011**: System MUST replace the custom `generate_correlation_id()` function with X-Ray trace ID retrieval.
- **FR-012**: System MUST include the X-Ray trace ID as a top-level field in all operational structured log entries (error logs, warning logs, info-level operational events) so CloudWatch Logs Insights queries can join log entries to X-Ray traces. Note: FR-022 and FR-023 remove tracing-specific structured logs; this requirement applies to the operational logs that remain.

**Cross-Service Trace Propagation**

- **FR-013**: System MUST verify that Active X-Ray tracing is enabled on both the Ingestion Lambda and the Analysis Lambda, and that the SNS subscription between them supports automatic trace context propagation via the `AWSTraceHeader` system attribute. The result is that both Lambda invocations appear under the same trace ID with zero manual MessageAttributes configuration.
- **FR-014**: System MUST propagate the `X-Amzn-Trace-Id` header from the frontend SSE proxy (Next.js API route) to the upstream SSE Lambda call when the header is present on the incoming request.
- **FR-015**: System MUST add `X-Amzn-Trace-Id` to the CORS `Access-Control-Allow-Headers` list for both API Gateway and Lambda Function URLs.
- **FR-016**: The frontend API client MUST include the `X-Amzn-Trace-Id` header on all outgoing requests when the browser has an active trace context. In test environments where RUM sampling is set to 100%, every API request from the browser MUST carry this header.

**Infrastructure Alignment**

- **FR-017**: All Lambda execution roles MUST have sufficient permissions to emit X-Ray trace segments and telemetry records. Currently, only 2 of 6 Lambda roles have explicit X-Ray write permissions; the remaining 4 (Ingestion, Analysis, Dashboard, Metrics) MUST be aligned.
- **FR-018**: X-Ray instrumentation errors MUST propagate to the Lambda runtime unhandled, resulting in Lambda invocation failure visible in standard error metrics. No error-suppression or fallback logic around tracing calls is permitted.

**X-Ray Canary (Watcher of the Watcher)**

- **FR-019**: System MUST implement a canary that periodically submits a batch of test traces to X-Ray and queries for their retrieval, reporting health via a non-X-Ray channel (CloudWatch metric). The canary MUST track both presence (did my test trace arrive?) and completeness (did all N of my test traces arrive?) to detect partial data loss from throttling.
- **FR-020**: System MUST configure the canary's health metric alarm with `treat_missing_data = breaching` so the alarm fires if the canary itself stops running.
- **FR-021**: The canary MUST be the sole non-X-Ray tracing and correlation mechanism in the system. All other custom tracing logs (latency_logger, cache_logger), custom correlation IDs, and custom log-based trace correlation MUST be consolidated onto X-Ray. Standard operational logging (error messages, audit records) and CloudWatch metrics (billing alarms, auto-scaling triggers, SLO dashboards) are not in scope and remain unchanged.

**Removal of Replaced Systems**

- **FR-022**: System MUST remove the custom latency structured logging from `latency_logger.py`. After X-Ray subsegment annotations replace its tracing function, the module and all its call sites MUST be deleted. No adapter or wrapper is permitted — the X-Ray annotations ARE the replacement.
- **FR-023**: System MUST remove the custom cache structured logging from `cache_logger.py`. After X-Ray annotations replace its tracing function, the module and all its call sites MUST be deleted.
- **FR-024**: System MUST remove the custom `get_correlation_id()` and `generate_correlation_id()` functions after X-Ray trace ID retrieval replaces them.

**SSE Streaming Trace Context (Round 2, revised in Round 3)**

- **FR-025** [Round 3 — Revised]: The SSE Lambda MUST preserve trace context across the async-to-sync bridge boundary. The system MUST rely on the default `threading.local()` context storage (which correctly propagates through `asyncio.new_event_loop().run_until_complete()` on the same thread). The system MUST NOT configure the X-Ray SDK's `AsyncContext`, which uses `TaskLocalStorage` that loses context across event loop boundaries (known bugs: aws-xray-sdk-python #164, #310, #446).
- **FR-026** [Round 3 — Replaced]: ~~During SSE streaming, the system MUST create independent X-Ray segments for each poll cycle.~~ **INVALIDATED**: `begin_segment()` is a no-op in Lambda (`LambdaContext.put_segment()` silently discards, `FacadeSegment` raises `FacadeSegmentMutationException`). **Replacement**: The SSE Lambda MUST use a tracing mechanism with an independent lifecycle for operations that execute during response streaming (after the handler returns the generator). This mechanism MUST: (a) create trace spans during active streaming, (b) link spans to the original invocation's trace ID for unified visualization, (c) export spans to X-Ray, (d) function independently of the Lambda runtime's facade segment lifecycle. The mechanism MUST run as a separate process (Lambda Extension) with its own INIT and SHUTDOWN phases, ensuring trace data is flushed even when the Lambda execution environment freezes.
- **FR-027** [Round 3 — Replaced]: ~~Auto-patched boto3 calls during streaming MUST execute within independently created segments.~~ **Replacement**: All service calls during SSE response streaming (DynamoDB queries, CloudWatch metric emission) MUST be captured within traced spans. These calls occur after the Lambda handler returns, when the X-Ray SDK's facade segment is closed. The independent lifecycle tracing mechanism from FR-026 MUST capture these calls so they appear in X-Ray as part of the connection's trace.

**SendGrid Explicit Instrumentation (Round 2 — Emergent)**

- **FR-028**: The SendGrid email sending operation in the Notification Lambda MUST be wrapped in an explicit X-Ray subsegment. The SendGrid SDK uses `urllib`/`python-http-client` for HTTP transport, which is NOT auto-patched by the X-Ray SDK. The subsegment MUST capture: HTTP status code, request duration, and error details on failure.

**Tracer Standardization (Round 2, updated in Round 3)**

- **FR-029** [Round 3 — Updated]: All non-streaming Lambda functions (Ingestion, Analysis, Dashboard, Notification, Metrics) MUST use a consistent X-Ray instrumentation approach that automatically captures exceptions as subsegment errors. The SSE Streaming Lambda MUST use the independent lifecycle tracing mechanism from FR-026, which has different instrumentation requirements due to the RESPONSE_STREAM segment lifecycle constraint. Both approaches MUST produce traces that appear in the same X-Ray console with unified trace IDs.
- **FR-030**: The system MUST eliminate double-patching of HTTP/AWS SDK clients. Currently, the Dashboard Lambda calls both explicit `patch_all()` and initializes a Tracer with `auto_patch=True` (the default), causing boto3 and requests to be patched twice. After standardization, each Lambda MUST have exactly one patching mechanism.

**Async Generator Tracing Safety (Round 3 — New)**

- **FR-031**: The system MUST NOT apply `@tracer.capture_method` or any equivalent function-wrapping decorator to async generator functions. The Powertools Tracer dispatcher does not check `inspect.isasyncgenfunction()` and silently routes async generators to the synchronous wrapper, which captures only generator creation time (near-zero) rather than iteration time. All async generator tracing MUST use manual subsegment or span context managers within the generator body. Source: `aws_lambda_powertools/tracing/tracer.py` — `isasyncgenfunction()` is never called in the dispatch chain.

**Frontend SSE Trace Propagation (Round 3 — New)**

- **FR-032**: The frontend SSE client MUST use `fetch()` with `ReadableStream` consumption instead of the `EventSource` API for connections that require trace header propagation. The `EventSource` API does not support custom HTTP headers per the WHATWG HTML Living Standard (Section 9.2). Using `fetch()` enables CloudWatch RUM's automatic `X-Amzn-Trace-Id` header injection (when `addXRayTraceIdHeader: true` is configured in the RUM http telemetry) and provides a mechanism for manual header attachment.
- **FR-033**: Since the `EventSource` API's built-in auto-reconnection is lost when switching to `fetch()` + `ReadableStream` (FR-032), the frontend SSE client MUST implement equivalent reconnection logic: exponential backoff with jitter on connection failure, `Last-Event-ID` header propagation for stream resumption, and connection state management matching the reliability guarantees of the replaced `EventSource`.

**Sampling Strategy (Round 3 — New)**

- **FR-034**: The system MUST configure X-Ray sampling rules per environment: 100% sampling (reservoir=1, fixed_rate=1.0) in dev/preprod for complete debuggability, and a documented production rate that balances cost with trace availability. The system MUST configure an X-Ray Group with filter expression `fault = true OR error = true` that automatically generates CloudWatch metrics (ApproximateErrorCount, FaultCount, latency percentiles) from errored traces, enabling error rate monitoring and alarming directly from trace data.
- **FR-035**: The system MUST configure server-side X-Ray sampling rules at the API Gateway and Lambda level that make independent sampling decisions, regardless of client-supplied `Sampled=1` in the `X-Amzn-Trace-Id` header. A malicious client MUST NOT be able to force 100% sampling and inflate X-Ray costs. The server-side sampling configuration is the authoritative source of truth for sampling decisions.

**Trace Data Integrity (Round 3 — New)**

- **FR-036**: The X-Ray canary (FR-019) MUST additionally track the ratio of submitted test traces to successfully retrieved test traces across consecutive intervals. When the retrieval ratio drops below a configured threshold (indicating systematic data loss from throttling, daemon failure, or SDK errors), the canary MUST emit a dedicated `trace_data_loss` CloudWatch metric that triggers an alarm.
- **FR-037**: The system MUST NOT manually configure the X-Ray SDK's `AsyncContext` on any Lambda function. The default `threading.local()` context storage correctly propagates through `asyncio.new_event_loop().run_until_complete()` calls on the same thread. Manually configuring `AsyncContext` uses `TaskLocalStorage`, which stores context on `asyncio.Task` objects — new tasks in a new event loop have no inherited context, breaking the async-to-sync bridge pattern used by the SSE Lambda. Known open issues: aws-xray-sdk-python #164 (concurrent async subsegments cause `AlreadyEndedException`), #310 (concurrent asyncio tasks + X-Ray in Lambda), #446 (context not propagated with `run_in_executor`).

**Cost Guard (Round 3 — New)**

- **FR-038**: The system MUST have CloudWatch billing alarms for X-Ray costs at thresholds of $10, $25, and $50 per month. At 100% sampling, X-Ray costs scale linearly at $5 per million traces recorded plus $0.50 per million traces retrieved/scanned. The free tier covers 100,000 traces recorded and 1,000,000 retrieved per month.

**Scope Clarification (Round 4 — New)**

- **FR-039**: "X-Ray exclusive" applies to **tracing** — the mechanism for distributed request tracing, latency analysis, and dependency visualization. CloudWatch alarms on Lambda built-in metrics (Errors, Duration, Throttles) and custom application metrics are a separate, complementary system for operational alerting. Alarms tell operators "something is wrong"; X-Ray traces tell operators "what went wrong and where." Both systems are required for complete observability. CloudWatch alarms are NOT duplicative with X-Ray and MUST NOT be removed as part of the X-Ray consolidation effort. Standard operational logging (error messages, audit records) also remains unchanged per FR-021.

**Operational Alarm Coverage (Round 4 — New)**

- **FR-040**: All 6 Lambda functions MUST have CloudWatch error alarms on the `AWS/Lambda` `Errors` metric. Currently, SSE Streaming Lambda and Metrics Lambda have zero error alarms (audit Section 4.3).
- **FR-041**: All 6 Lambda functions MUST have CloudWatch latency alarms on the `AWS/Lambda` `Duration` metric at the p95 statistic. Currently, Ingestion Lambda, Notification Lambda, SSE Streaming Lambda, and Metrics Lambda are missing latency alarms (audit Section 9.3).
- **FR-042**: The following custom metrics currently emitted without alarms MUST each have a CloudWatch alarm configured: `StuckItems` (items stuck in "pending" >5min), `ConnectionAcquireFailures` (SSE connection pool exhaustion), `EventLatencyMs` (SSE live update latency p95 > 3000ms SLO), `MetricsLambdaErrors` (monitoring system errors), `HighLatencyAlert` (ingestion latency >30s), `PollDurationMs` (DynamoDB poll duration), `AnalysisErrors` (analysis processing errors). Source: audit Section 4.2.
- **FR-043**: The 7 silent failure paths identified in audit Section 8 MUST emit dedicated CloudWatch metrics in addition to X-Ray subsegments (FR-002, FR-005). X-Ray subsegments provide trace context for debugging; CloudWatch metrics provide 100% occurrence capture for alarming regardless of X-Ray sampling configuration. The required metrics are: `CircuitBreakerPersistenceFailure` (paths 1-2), `AuditEventPersistenceFailure` (path 3), `DownstreamNotificationFailure` (path 4), `TimeseriesFanoutPartialFailure` (path 5), `SelfHealingItemFetchFailure` (path 6), `ParallelFetcherErrors` (path 7).
- **FR-044**: The CloudWatch dashboard alarm status widget MUST display ALL configured alarms. The audit identified that the current widget shows only 6 of 30+ alarms (audit Section 6.3), giving operators a false sense of "all green" when non-displayed alarms may be firing.
- **FR-045**: All CloudWatch alarms monitoring metrics where absence indicates failure (heartbeat metrics, canary metrics, pipeline throughput metrics such as `NewItemsIngested`) MUST use `treat_missing_data = breaching`. Alarms monitoring error count metrics where zero data points means "no errors occurred" MUST use `treat_missing_data = notBreaching`. The configuration MUST be audited and corrected for all existing alarms.

**ADOT Coexistence Constraints (Round 4 — New)**

- **FR-046**: The SSE Lambda MUST NOT enable ADOT auto-instrumentation via the `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-handler` environment variable. ADOT MUST function solely as an OTLP receiver sidecar (Lambda Extension) that accepts spans on `localhost:4318` and exports them to X-Ray. ADOT auto-instrumentation wraps the handler entry point (conflicting with Powertools `@tracer.capture_lambda_handler` from FR-029) and patches botocore (conflicting with X-Ray SDK patching from Powertools `auto_patch=True`), causing duplicate handler wrapping and duplicate spans for every boto3 call.
- **FR-047**: The OTel `service.name` resource attribute configured for ADOT span export on the SSE Lambda MUST match the `POWERTOOLS_SERVICE_NAME` environment variable used by Powertools Tracer. X-Ray service map aggregates nodes by service name. Mismatched names cause the same Lambda to appear as two disconnected nodes in the service map — one for handler-phase subsegments and one for streaming-phase spans.

**SSE Reconnection Trace Correlation (Round 4 — New)**

- **FR-048**: All SSE connection traces MUST include a stable `session_id` annotation that persists across reconnections, enabling operators to query X-Ray by `session_id` to find all traces for a logical SSE session. On reconnection (new trace ID due to new `fetch()` call), the trace MUST additionally include a `previous_trace_id` annotation referencing the prior connection's X-Ray trace ID and a `connection_sequence` annotation (incrementing integer starting at 1). X-Ray does not support native span links (OpenTelemetry link data stored in segment metadata is not queryable via X-Ray console or API), so annotation-based correlation is the required pattern.

**Meta-Observability (Round 4 — New)**

- **FR-049**: The observability canary (extending FR-019) MUST additionally verify CloudWatch metric emission health on each canary interval. The canary emits a known test metric via `put_metric_data`, waits for the CloudWatch ingestion delay (typically 60-120 seconds), and then queries for it via `get_metric_statistics`. If the test metric is not retrievable within the expected window, the canary reports CloudWatch metric pipeline failure. This check is in addition to the X-Ray trace submission/retrieval check from FR-019.
- **FR-050**: The canary MUST report CloudWatch metric pipeline failure via a channel independent of CloudWatch alarms. If CloudWatch is degraded, a CloudWatch alarm on the canary's own metric may also fail to fire. The canary MUST use an out-of-band alerting mechanism (e.g., SNS direct publish to email/SMS, external monitoring API) for meta-observability failures. Source: AWS Well-Architected Operational Excellence Pillar — "never alert on failure using the same system that failed."
- **FR-051**: The canary Lambda MUST use a separate IAM role from all application Lambdas. If an IAM policy change revokes X-Ray or CloudWatch permissions from application Lambda roles, the canary MUST retain its permissions to detect and report the failure. This isolation ensures the canary is not affected by the same failure mode it is designed to detect.

### Key Entities

- **X-Ray Trace**: A distributed trace spanning one or more service components, identified by a trace ID in the format `1-{hex_timestamp}-{24_hex_digits}`. Propagated via the `X-Amzn-Trace-Id` header.
- **X-Ray Subsegment**: A named, timed span within a trace representing a discrete operation (e.g., a DynamoDB query, a connection acquisition). Can carry annotations (indexed, searchable key-value pairs) and metadata (non-indexed structured data).
- **X-Ray Annotation**: An indexed key-value pair attached to a subsegment. Annotations are searchable in the X-Ray console and API, making them the primary mechanism for filtering traces by business attributes (e.g., `event_type = "bucket_update"`, `cache_hit_rate = 0.85`).
- **X-Ray Canary**: A scheduled probe that validates X-Ray ingestion health and data integrity by submitting and querying test traces, reporting results via a separate (non-X-Ray) channel.
- **X-Ray Group**: A filtered view of traces defined by a filter expression (e.g., `fault = true`). Groups automatically generate CloudWatch metrics, enabling alarm-based monitoring from trace data without manual metric emission.
- **X-Ray Sampling Rule**: A server-side configuration that controls which requests are traced. Rules specify a reservoir (guaranteed minimum per second) and a fixed rate (percentage of additional requests). Rules are evaluated by priority (lowest number first).

## Assumptions

- ~~The X-Ray SDK auto-patches HTTP client libraries including the one used by the SendGrid SDK.~~ **INVALIDATED in Round 2**: The SendGrid SDK uses `python-http-client` which uses Python's stdlib `urllib.request`. The X-Ray SDK does NOT auto-patch `urllib`. SendGrid HTTP calls require explicit X-Ray subsegments (see FR-028).
- The existing CloudWatch RUM configuration (`enable_xray = true`) already generates browser-side X-Ray trace contexts. The frontend needs to extract and propagate these, not generate new ones. CloudWatch RUM's web client auto-injects `X-Amzn-Trace-Id` headers on `fetch()` calls when `addXRayTraceIdHeader: true` is configured in the http telemetry options.
- When both the publishing and subscribing Lambda functions have Active X-Ray tracing enabled, AWS automatically propagates trace context through SNS via the `AWSTraceHeader` system attribute. No manual MessageAttributes configuration is needed for cross-Lambda trace linking.
- Auto-instrumentation patches all supported AWS SDK calls (DynamoDB, SNS, CloudWatch, etc.) transparently. Explicit subsegments are needed only for business logic operations not covered by auto-patching.
- The X-Ray canary's query latency window (time between trace submission and retrievability) is typically 5-30 seconds due to X-Ray's eventual consistency model.
- Standard AWS managed policies for X-Ray provide sufficient permissions for Lambda trace emission and telemetry reporting.
- ~~The X-Ray SDK's `xray_recorder.begin_segment()` API can create independent segments outside the Lambda runtime's auto-created segment. These segments can carry a specified trace ID to link them to the original invocation, appearing as part of the same distributed trace.~~ **INVALIDATED in Round 3**: `begin_segment()` is a documented no-op in Lambda. The SDK's `LambdaContext.put_segment()` silently discards segments with a log warning (source: `aws_xray_sdk/core/lambda_launcher.py:55-59`). The `FacadeSegment` raises `FacadeSegmentMutationException` on all mutation operations including `close()`, `put_annotation()`, `put_metadata()`, `set_aws()`, `add_exception()`, and `serialize()`. Additionally, the X-Ray daemon within the Lambda execution environment may begin shutting down after the handler returns in `RESPONSE_STREAM` mode, making even raw UDP emission unreliable. **Replacement**: The SSE Lambda uses a Lambda Extension-based tracing mechanism (e.g., ADOT — AWS Distro for OpenTelemetry) that runs as a separate process with its own lifecycle. Lambda Extensions receive INIT, INVOKE, and SHUTDOWN lifecycle events and continue running after the handler returns. The extension accepts trace spans via local OTLP endpoint and exports to X-Ray, providing trace data emission during response streaming without depending on the X-Ray SDK's LambdaContext.
- **(Round 2)** The X-Ray SDK supports `str`, `int`, `float`, and `bool` annotation types. All annotations defined in this spec use these types. `None` values are silently dropped, so annotations MUST use explicit sentinel values or be omitted when the value is unavailable.
- **(Round 2)** Adding Powertools Tracer as a dependency to all non-streaming Lambda containers adds approximately 5-10MB to the deployment package and 50-100ms to cold start. This is acceptable given that the Lambdas already include the aws-xray-sdk dependency.
- **(Round 3)** The `EventSource` browser API does not support custom HTTP headers. This is defined in the WHATWG HTML Living Standard, Section 9.2. The constructor signature is `EventSource(url, eventSourceInitDict)` where `eventSourceInitDict` only supports `withCredentials: boolean`. CloudWatch RUM's automatic trace header injection patches `window.fetch()` and `XMLHttpRequest.prototype.open` but does NOT patch `EventSource`. Trace propagation for SSE connections requires using `fetch()` + `ReadableStream` instead.
- **(Round 3)** Adding the ADOT Lambda Extension to the SSE Lambda adds approximately 40-60MB to the execution environment and 50-200ms to cold start (runs concurrently with Lambda INIT, partially masking overhead). The extension provides an OTLP receiver on localhost that accepts trace spans independently of the X-Ray SDK lifecycle.
- **(Round 3)** X-Ray's region-level throughput limit is 2,600 segments per second. Beyond this, `PutTraceSegments` returns `ThrottledException` and affected segments are listed in `UnprocessedTraceSegments` — data is permanently lost, not queued. The X-Ray daemon provides batching and burst capacity but cannot sustain above-limit throughput.
- **(Round 3)** The default `threading.local()` context storage used by the X-Ray SDK correctly propagates across `asyncio.new_event_loop().run_until_complete()` boundaries when called from the same thread. This is because `run_until_complete()` executes coroutines on the calling thread. The X-Ray SDK's `AsyncContext` alternative uses `TaskLocalStorage`, which is scoped to `asyncio.Task` objects and does NOT propagate across event loop boundaries.
- **(Round 3)** At current traffic levels (<1M requests/month), 100% X-Ray sampling costs less than $5/month, well within the cost guard thresholds. The free tier covers the first 100,000 traces recorded per month.
- **(Round 4)** CloudFront is not in the current architecture — removed in Features 1203-1207. Browser-to-backend trace propagation via `X-Amzn-Trace-Id` headers reaches API Gateway and Lambda Function URLs directly without intermediary header manipulation. CloudFront treats `X-Amzn-Trace-Id` as a restricted header and replaces client-sent values with its own; re-introducing CloudFront would break browser-originated trace propagation (see edge case).
- **(Round 4)** ADOT Lambda Extension in "sidecar-only" mode (OTLP receiver without auto-instrumentation) does not conflict with Powertools Tracer or the X-Ray SDK. Conflicts arise only when ADOT auto-instrumentation is enabled via the `AWS_LAMBDA_EXEC_WRAPPER` environment variable, which activates handler wrapping (`AwsLambdaInstrumentor`) and botocore patching (`BotocoreInstrumentor`).
- **(Round 4)** CloudWatch metric ingestion delay (time between `put_metric_data` and metric availability via `get_metric_statistics`) is typically 60-120 seconds. The canary's CloudWatch health check query window must account for this delay. Source: AWS CloudWatch API documentation.
- **(Round 4)** At current traffic levels with 100% X-Ray sampling, the gap between X-Ray trace availability and CloudWatch metric availability for error detection is effectively zero — every error has both an X-Ray trace and a CloudWatch metric. The dual-instrumentation requirement for silent failure paths (FR-043) provides insurance for the future when production sampling may be reduced below 100%.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any sampled user request, an operator can trace it from browser through API Gateway through Lambda through downstream services (DynamoDB, SNS, SendGrid) as a single continuous trace — with zero tool-switching required. Dev/preprod environments sample at 100%; production sampling is configured to balance cost with debuggability.
- **SC-002**: An operator can filter traces by error/fault status and immediately identify which specific operation failed (circuit breaker, audit trail, notification publish, fanout, self-healing) — without grepping logs.
- **SC-003**: 100% of Lambda functions (6 of 6) have auto-instrumented service call subsegments, up from current 5 of 6 (Metrics Lambda missing).
- **SC-004**: 100% of silent failure paths have X-Ray subsegments marked as error when the failure occurs. The 7 paths are: (1) circuit breaker load, (2) circuit breaker save, (3) audit trail persistence, (4) downstream notification SNS publish, (5) time-series fanout partial batch write, (6) self-healing item fetch, (7) parallel fetcher error aggregation.
- **SC-005**: SSE streaming latency and cache performance data is queryable via trace annotations — operators can filter traces by latency thresholds or cache hit rate directly, without separate log query tools.
- **SC-006**: The custom correlation ID system (`get_correlation_id`, `generate_correlation_id`) is fully removed, with zero remaining call sites.
- **SC-007**: The X-Ray canary detects simulated tracing ingestion failure within 2 consecutive canary intervals and fires a non-X-Ray alarm.
- **SC-008**: Cross-Lambda traces through SNS (Ingestion -> Analysis) appear under a single trace ID with the SNS hop visible as a connecting segment, enabling cross-service debugging without log correlation.
- **SC-009**: The system contains exactly one non-X-Ray tracing mechanism: the X-Ray canary. All custom tracing logs and custom correlation IDs previously identified in audit section 9.1 are consolidated onto X-Ray. Standard operational logging and CloudWatch metrics remain unchanged.
- **SC-010** [Round 3 — Revised]: SSE streaming operations (DynamoDB polls, event dispatch, CloudWatch metrics) that occur AFTER the Lambda handler returns the generator are captured in traced spans that appear in X-Ray linked to the original invocation trace ID. Zero orphaned subsegments, zero `SegmentNotFoundException` errors, zero silently discarded segments from `LambdaContext.put_segment()`. The tracing mechanism has an independent lifecycle that survives handler return.
- **SC-011** (Round 2): SendGrid email API calls in the Notification Lambda appear as explicitly instrumented subsegments with HTTP status and duration, not as untraced gaps in the service map.
- **SC-012** (Round 2): All non-streaming Lambda functions use a single, consistent tracing approach. Exceptions raised inside traced functions are automatically captured as subsegment errors. Zero Lambdas use dual/conflicting patching mechanisms. The SSE Lambda uses a distinct approach necessitated by the RESPONSE_STREAM lifecycle constraint, but its traces appear in the same X-Ray console.
- **SC-013** (Round 3): An X-Ray Group with error/fault filter generates CloudWatch metrics for errored traces. Operators can set alarms on error rates derived directly from trace data.
- **SC-014** (Round 3): The X-Ray canary detects partial trace data loss (throttling, daemon failure) by tracking the ratio of submitted-to-retrieved test traces. When data loss exceeds the configured threshold, a dedicated CloudWatch alarm fires.
- **SC-015** (Round 3): The frontend SSE client uses `fetch()` + `ReadableStream` with automatic reconnection logic, propagating `X-Amzn-Trace-Id` headers on every connection — matching or exceeding the reliability of the replaced `EventSource` implementation.
- **SC-016** (Round 3): X-Ray billing alarms fire when monthly costs exceed $10, $25, or $50 thresholds, preventing cost surprises from sampling configuration changes or traffic growth.
- **SC-017** (Round 4): 6/6 Lambda functions have both CloudWatch error alarms and CloudWatch latency alarms configured. Zero Lambda functions exist without operational alerting.
- **SC-018** (Round 4): All custom metrics previously emitted without alarms (7 metrics from audit Section 4.2) now have CloudWatch alarms with documented thresholds. Zero metrics exist in "emitted but unalarmed" state.
- **SC-019** (Round 4): All 7 silent failure paths emit both X-Ray subsegments (for trace context, per SC-004) and CloudWatch metrics (for 100% alarm coverage). An error on any silent failure path triggers both a trace annotation and a CloudWatch alarm — no silent failure is invisible to operators regardless of X-Ray sampling configuration.
- **SC-020** (Round 4): SSE reconnection traces are queryable by `session_id` annotation, returning all traces for a logical SSE session across reconnections. Operators can follow the reconnection chain via `previous_trace_id` annotations.
- **SC-021** (Round 4): The canary detects both X-Ray ingestion failure AND CloudWatch metric emission pipeline failure within 2 consecutive canary intervals. Meta-observability failures are reported via an out-of-band channel independent of CloudWatch alarms.
- **SC-022** (Round 4): The CloudWatch dashboard alarm status widget displays ALL configured alarms. Operators viewing the dashboard see complete alarm status without hidden blind spots.
