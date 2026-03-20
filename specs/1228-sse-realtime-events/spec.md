# Feature Specification: Wire SSE Real-Time Events

**Feature Branch**: `1228-sse-realtime-events`
**Created**: 2026-03-20
**Status**: Draft
**Input**: Wire SSE real-time events — sentiment_update and partial_bucket. Connect existing dead code infrastructure to live data streams.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Sentiment Updates on Dashboard (Priority: P1)

A user watching the sentiment dashboard sees individual ticker sentiment updates arrive in real time as new articles are analyzed, without needing to refresh the page. When the analysis pipeline processes a new article about AAPL, the dashboard updates AAPL's sentiment indicator within seconds.

**Why this priority**: This is the core value proposition — the "real-time" in "real-time streaming." Without individual ticker updates, the SSE stream is just a slower version of periodic REST polling. The frontend already listens for these events but never receives them.

**Independent Test**: Can be tested by triggering the ingestion pipeline for a single ticker, then verifying the SSE stream emits a `sentiment_update` event with that ticker's data within one polling cycle.

**Acceptance Scenarios**:

1. **Given** a user is connected to a global SSE stream, **When** the analysis pipeline processes a new article for AAPL, **Then** a `sentiment_update` event is emitted containing AAPL's ticker, aggregate score, majority label, and article count.
2. **Given** a user is connected to a config-specific stream filtered to [AAPL, MSFT], **When** new articles are analyzed for AAPL and TSLA, **Then** only the AAPL update is delivered; TSLA is filtered out.
3. **Given** a user is connected to a global stream, **When** no new articles have been analyzed since the last poll, **Then** no `sentiment_update` events are emitted (only heartbeats and metrics as before).
4. **Given** a user reconnects with a Last-Event-ID, **When** `sentiment_update` events were emitted during the disconnection, **Then** missed events are replayed from the event buffer.

---

### User Story 2 - Partial Bucket Progress for Time-Series Charts (Priority: P2)

A user viewing a time-series chart with 5-minute resolution sees the current in-progress bucket update in real time with a progress indicator, showing how far through the current time window the data extends. This gives users confidence that data is flowing and provides early visibility into trends before buckets close.

**Why this priority**: Builds on Story 1's change detection but targets the timeseries table. Partial buckets are a visual UX enhancement that requires the timeseries polling path — a separate data source from the sentiment items table.

**Independent Test**: Can be tested by verifying that during an active 5-minute bucket window, the SSE stream emits `partial_bucket` events with increasing `progress_pct` values and current bucket aggregates.

**Acceptance Scenarios**:

1. **Given** a user is connected to a stream, **When** new timeseries records are written to the current bucket, **Then** a `partial_bucket` event is emitted with the ticker, resolution, bucket data, and current `progress_pct`.
2. **Given** a polling cycle detects changes across multiple tickers and resolutions, **When** partial_bucket events are generated for the same ticker/resolution within a single emission pass, **Then** the debouncer ensures at most one event per ticker/resolution per debounce interval (100ms).
3. **Given** a config-specific stream filtered to [GME], **When** partial bucket updates arrive for GME and AAPL, **Then** only GME events pass through the ticker filter.
4. **Given** the timeseries table is empty or unreachable, **When** the polling cycle runs, **Then** no `partial_bucket` events are emitted and existing stream behavior (heartbeats, metrics) is unaffected.

---

### User Story 3 - Consistent Behavior Across Stream Types (Priority: P2)

Both global streams and config-specific streams receive `sentiment_update` and `partial_bucket` events. Config-specific streams apply ticker filtering so users only receive events matching their portfolio configuration.

**Why this priority**: The config stream currently only sends heartbeats. Wiring both event types into config streams is essential for the per-portfolio dashboard experience.

**Independent Test**: Can be tested by connecting two streams — one global, one config-specific with ticker filters — and verifying both receive events but the config stream correctly filters by ticker.

**Acceptance Scenarios**:

1. **Given** a global stream connection, **When** sentiment updates and partial bucket events occur, **Then** all events are delivered unfiltered.
2. **Given** a config-specific stream with ticker_filters = [AAPL, MSFT], **When** sentiment updates arrive for AAPL, MSFT, and TSLA, **Then** only AAPL and MSFT events are delivered.
3. **Given** a config-specific stream with empty ticker_filters, **When** events occur, **Then** all events are delivered (empty filter = receive all).

---

### Edge Cases

- What happens when multiple articles for the same ticker are analyzed in the same polling cycle? Aggregate comparison naturally produces one change detection per ticker, so one `sentiment_update` is emitted with the ticker's current aggregate data.
- What happens when the timeseries table query times out? The partial_bucket polling fails gracefully — existing metrics and heartbeat streams continue unaffected.
- What happens when the event buffer is full and new sentiment/partial events arrive? The buffer size should be increased to accommodate the higher event volume. With 22 tickers and 8 resolutions, a single poll cycle could produce up to ~200 events. The buffer should hold at least 2-3 polling cycles worth of events to support meaningful Last-Event-ID replay.
- What happens during Lambda cold start? First poll establishes the baseline — no change events are emitted until subsequent polls detect actual changes.
- What happens when debouncer state grows unbounded? Debouncer keys are ticker#resolution pairs. With ~22 tickers and 8 resolutions, this is bounded at ~176 entries — negligible memory.

## Scope Boundaries

**Firmly out of scope:**
- Frontend changes (the frontend already listens for `sentiment_update` and `partial_bucket` events)
- WebSocket integration (future paid feature — this is an interim polling-based approach)

**Soft boundaries (not expected, but not excluded if discovered necessary):**
- Terraform / IAM changes — SSE Lambda already has Query + GetItem on both tables, but if a new permission is needed, it should be included rather than working around it
- Ingestion pipeline changes — not anticipated, but if data shape or indexing gaps are found during implementation, fixing at the source is preferred over compensating in the SSE Lambda

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST emit `sentiment_update` events when a ticker's per-ticker aggregate sentiment (score, label, or article count) changes between polling cycles.
- **FR-002**: System MUST emit `partial_bucket` events when new or changed timeseries records are detected in the current time bucket across all 8 resolutions, including `progress_pct` indicating how far through the bucket period the data extends. All resolutions are polled regardless of active subscriptions (interim approach before future WebSocket-based push).
- **FR-003**: System MUST track per-ticker aggregate sentiment between polling cycles and detect changes by comparing current vs. previous aggregates (no item-level cursor needed — continuous float scores virtually guarantee a change when new articles arrive).
- **FR-004**: System MUST query the timeseries table (already configured as TIMESERIES_TABLE environment variable) for bucket change detection.
- **FR-004a**: System MUST track previous timeseries bucket state between polling cycles and detect changes by comparing current bucket data against the previous snapshot (parallel to FR-003 for sentiments).
- **FR-005**: System MUST apply the existing debouncer (100ms interval) to `partial_bucket` events to prevent flooding clients with rapid updates.
- **FR-006**: System MUST apply connection-level ticker filters to both `sentiment_update` and `partial_bucket` events on config-specific streams.
- **FR-007**: System MUST include `sentiment_update` and `partial_bucket` events in the event buffer for Last-Event-ID reconnection replay. The buffer size MUST accommodate the increased event volume (at least 500 events to cover 2-3 polling cycles with all event types).
- **FR-008**: System MUST add tracing spans for both new event types using the existing OTel tracing infrastructure.
- **FR-009**: System MUST handle timeseries table query failures gracefully without disrupting the existing metrics and heartbeat stream.
- **FR-010**: System MUST emit at most one `sentiment_update` per ticker per polling cycle, containing the ticker's current aggregate sentiment data.
- **FR-011**: System MUST NOT emit `sentiment_update` or `partial_bucket` events on the first polling cycle (baseline establishment only).
- **FR-012**: The `sentiment_update` event payload MUST contain the ticker's current aggregate data: weighted average score, majority sentiment label, total article count, and average confidence. The `source` field MUST indicate "aggregate" since the data spans multiple articles and sources.

### Key Entities

- **Sentiment Item**: A single analyzed article with ticker, sentiment score, label, confidence, and source. Stored in the sentiments table.
- **Timeseries Bucket**: A pre-aggregated time-series record at a specific resolution (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h). Contains OHLC-style sentiment aggregates. Stored in the timeseries table.
- **Per-Ticker Aggregate Snapshot**: Previous poll's per-ticker sentiment aggregates (score, label, count) used to detect changes by comparison. Resets on Lambda cold start.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard users see individual ticker sentiment updates within 10 seconds of article analysis completion.
- **SC-002**: Partial bucket events include accurate `progress_pct` reflecting the elapsed fraction of the current bucket window.
- **SC-003**: Config-specific streams deliver only events matching the connection's ticker filters — zero leakage of unsubscribed tickers.
- **SC-004**: Existing stream behavior (heartbeats every 30s, aggregate metrics on change, reconnection replay) continues to function identically.
- **SC-005**: The debouncer suppresses rapid partial_bucket updates for the same ticker/resolution to at most 10 events per second.
- **SC-006**: Timeseries table unavailability does not degrade or disrupt the existing metrics and heartbeat stream.
- **SC-007**: All new event types include tracing spans for end-to-end observability.

## Clarifications

### Session 2026-03-20

- Q: Should sentiment_update events fire on every new article (item-level) or only when per-ticker aggregate sentiment changes (aggregate-level)? → A: Aggregate-level comparison. Continuous float scores virtually guarantee a change on new data, so no item-level cursor is needed — just diff per-ticker aggregates between polls.
- Q: Which timeseries resolutions should partial_bucket poll — all 8, a subset, or subscription-driven? → A: All 8 resolutions. This is interim before future WebSocket-based push (paid feature with per-ticker subscriptions). No production traffic, so no cost concern. Keep it simple — the entire polling path will be replaced later.
- Q: Should the spec declare hard out-of-scope boundaries for Terraform/IAM and ingestion pipeline? → A: No — only frontend changes and WebSocket integration are firmly out of scope. Terraform/IAM and ingestion are soft boundaries (not expected but not excluded if needed during implementation).

## Assumptions

- **A-001**: Per-ticker sentiment change detection uses aggregate comparison (score/label/count diff between polls) rather than item-level cursors. With continuous float scores, any new article virtually guarantees a detectable aggregate change.
- **A-002**: The timeseries table schema supports querying for records in the current time bucket by ticker and resolution. The existing `Resolution` enum and `floor_to_bucket()` utility can derive the appropriate query parameters.
- **A-003**: Cold start baseline establishment (FR-011) prevents a flood of "new" events when the Lambda scales from zero and sees all existing data for the first time.
- **A-004**: The existing 5-second polling interval is sufficient for near-real-time event detection. No sub-second polling is required.
- **A-005**: Lambda memory (currently configured) is sufficient for the additional polling path without increase.
