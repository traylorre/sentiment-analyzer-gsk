# Tasks: Wire SSE Real-Time Events

**Input**: Design documents from `/specs/1228-sse-realtime-events/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/sse-events.md, quickstart.md

**Tests**: Required per constitution (Implementation Accompaniment Rule).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Verify branch state and existing code

- [x] T001 Verify branch `1228-sse-realtime-events` is on latest main and all existing SSE tests pass by running `python -m pytest tests/unit/ -k sse -v`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core changes that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Fix pre-existing bug: change `item.get("ticker")` to iterate `item.get("matched_tickers", [])` in `_aggregate_metrics()` in `src/lambdas/sse_streaming/polling.py` (line 92). Each item can match multiple tickers — accumulate count and score per ticker from the list. This fixes the empty `by_tag` dict in `MetricsEventData`.
- [x] T003 Update `SSEEvent.validate_data_type()` in `src/lambdas/sse_streaming/models.py` to add `"PartialBucketEvent"` and `"BucketUpdateEvent"` to the `allowed_types` set so partial_bucket events pass validation.
- [x] T004 Increase `EventBuffer` default `max_size` from 100 to 500 in `src/lambdas/sse_streaming/stream.py` (line 98) to accommodate higher event volume per FR-007.
- [x] T005 Extend `PollingService.poll()` return type in `src/lambdas/sse_streaming/polling.py` to return a `PollResult` named tuple: `(metrics: MetricsEventData, metrics_changed: bool, per_ticker: dict[str, TickerAggregate], timeseries_buckets: dict[str, dict])`. Add `TickerAggregate` dataclass with fields: ticker, score, label, confidence, count. Keep existing `_last_metrics` / `_metrics_changed()` for backwards compatibility.
- [x] T006 [P] Write unit tests for bug fix T002 in `tests/unit/test_sse_sentiment_events.py`: verify `by_tag` is correctly populated when items have `matched_tickers` list with single and multi-ticker articles. Use moto mock for DynamoDB.
- [x] T007 [P] Write unit tests for `TickerAggregate` dataclass and `PollResult` named tuple in `tests/unit/test_sse_sentiment_events.py`: verify construction and field access.

**Checkpoint**: Foundation ready — `PollingService` returns enriched data, models accept new event types, buffer is sized correctly.

---

## Phase 3: User Story 1 — Live Sentiment Updates (Priority: P1) MVP

**Goal**: Emit `sentiment_update` events when per-ticker aggregate sentiment changes between polling cycles.

**Independent Test**: Trigger ingestion for a ticker, verify SSE stream emits `sentiment_update` with that ticker's aggregate data within one poll cycle.

### Tests for User Story 1

- [x] T008 [P] [US1] Write unit tests for `_compute_per_ticker_aggregates(items)` in `tests/unit/test_sse_sentiment_events.py`: verify correct weighted average score, majority label, average confidence, and count for single-ticker and multi-ticker items. Include edge case: item with empty `matched_tickers`.
- [x] T009 [P] [US1] Write unit tests for per-ticker change detection logic in `tests/unit/test_sse_sentiment_events.py`: verify that diffing current vs. previous `TickerAggregate` snapshots correctly identifies changed tickers, new tickers, and removed tickers. Verify no changes detected when aggregates are identical.
- [x] T010 [P] [US1] Write unit tests for `sentiment_update` event emission in `generate_global_stream()` in `tests/unit/test_sse_stream_wiring.py`: verify that changed tickers produce `sentiment_update` SSE events with correct payload (FR-012: score, label, confidence, source="aggregate"). Verify baseline establishment: first poll emits no sentiment_update events (FR-011).
- [x] T011 [P] [US1] Write unit test for event buffer replay in `tests/unit/test_sse_stream_wiring.py`: verify `sentiment_update` events are added to EventBuffer and can be replayed via `get_events_after()` for Last-Event-ID reconnection (FR-007).

### Implementation for User Story 1

- [x] T012 [US1] Implement `_compute_per_ticker_aggregates(items: list[dict]) -> dict[str, TickerAggregate]` in `src/lambdas/sse_streaming/polling.py`. Iterate items, extract `matched_tickers` list, accumulate per-ticker: sum of scores, count per sentiment label, total count, sum of confidence scores. Return dict mapping ticker to `TickerAggregate` with weighted average score, majority label, average confidence, total count.
- [x] T013 [US1] Wire `_compute_per_ticker_aggregates()` into `PollingService.poll()` in `src/lambdas/sse_streaming/polling.py`. Call it with the same `items` list used for `_aggregate_metrics()`. Include result in `PollResult` return value.
- [x] T014 [US1] Add per-connection local state and sentiment change detection to `generate_global_stream()` in `src/lambdas/sse_streaming/stream.py`. First, update the poll loop destructuring from `async for metrics, changed in self._poll_service.poll_loop()` to unpack the new `PollResult` fields (metrics, metrics_changed, per_ticker, timeseries_buckets). Then add local variables: `local_last_per_ticker: dict = {}`, `local_is_baseline: bool = True`. After existing metrics handling: diff current `per_ticker` against `local_last_per_ticker`, identify changed tickers, update snapshot. On first poll (baseline), skip event emission.
- [x] T015 [US1] Wire `_create_sentiment_event()` for each changed ticker in `generate_global_stream()` in `src/lambdas/sse_streaming/stream.py`. For each changed ticker: call `_create_sentiment_event(ticker, aggregate.score, aggregate.label, aggregate.confidence, "aggregate")`, add to `_event_buffer`, update connection's last_event_id, yield event dict.
- [x] T016 [US1] Verify T008-T011 tests pass. Run `python -m pytest tests/unit/test_sse_sentiment_events.py tests/unit/test_sse_stream_wiring.py -v`.

**Checkpoint**: Global stream emits `sentiment_update` events when per-ticker aggregates change. First poll establishes baseline silently.

---

## Phase 4: User Story 2 — Partial Bucket Progress (Priority: P2)

**Goal**: Emit `partial_bucket` events when timeseries OHLC bucket data changes between polling cycles.

**Independent Test**: During an active 5-minute bucket window, verify SSE stream emits `partial_bucket` events with `progress_pct` and OHLC data.

### Tests for User Story 2

- [x] T017 [P] [US2] Write unit tests for `_fetch_timeseries_buckets(tickers, dynamodb_resource)` in `tests/unit/test_sse_timeseries_polling.py`: verify `BatchGetItem` constructs correct keys (PK=`{ticker}#{resolution}`, SK=`floor_to_bucket(now, resolution).isoformat()`), handles pagination for >100 items, and returns dict mapping `{ticker}#{resolution}` to bucket OHLC data. Use moto mock for DynamoDB. Use `freezegun` for deterministic bucket timestamps.
- [x] T018 [P] [US2] Write unit tests for timeseries bucket change detection in `tests/unit/test_sse_timeseries_polling.py`: verify diffing current vs. previous bucket snapshots identifies changed buckets (count increased, close value changed), new buckets, and missing buckets. Verify no changes detected for identical snapshots.
- [x] T019 [P] [US2] Write unit tests for `partial_bucket` event emission in `generate_global_stream()` in `tests/unit/test_sse_stream_wiring.py`: verify changed buckets produce `partial_bucket` SSE events with correct payload (ticker, resolution, bucket OHLC, progress_pct). Verify debouncer suppresses rapid events for same ticker#resolution. Use `freezegun` for deterministic `progress_pct`.
- [x] T020 [P] [US2] Write unit test for timeseries query failure graceful degradation in `tests/unit/test_sse_timeseries_polling.py`: verify that when `BatchGetItem` raises `ClientError`, the poll returns empty timeseries_buckets and existing metrics/heartbeat stream is unaffected (FR-009).

### Implementation for User Story 2

- [x] T021 [US2] Implement `_fetch_timeseries_buckets(tickers: list[str], dynamodb_resource) -> dict[str, dict]` in `src/lambdas/sse_streaming/polling.py`. Read `TIMESERIES_TABLE` env var. For each ticker × 8 resolutions, compute PK and SK using `floor_to_bucket()`. Use `BatchGetItem` (100 items per call, 2 calls needed for 176 items). Return dict mapping `{ticker}#{resolution}` to bucket OHLC data. Wrap in try/except `ClientError` — return empty dict on failure with warning log (FR-009).
- [x] T022 [US2] Wire `_fetch_timeseries_buckets()` into `PollingService.poll()` in `src/lambdas/sse_streaming/polling.py`. Call with tickers derived from `per_ticker.keys()` (the tickers discovered from sentiment items). Include result in `PollResult`. Run in executor to avoid blocking async loop.
- [x] T023 [US2] Add timeseries bucket change detection to `generate_global_stream()` in `src/lambdas/sse_streaming/stream.py`. Add local variable `local_last_buckets: dict = {}`. After sentiment event handling: diff current `timeseries_buckets` against `local_last_buckets`, identify changed bucket keys. Apply debouncer via `self.should_emit_bucket_update(ticker, resolution)` before emitting. Update snapshot. Skip on baseline poll.
- [x] T024 [US2] Wire `_create_partial_bucket_event()` for each changed bucket in `generate_global_stream()` in `src/lambdas/sse_streaming/stream.py`. Parse ticker and resolution from bucket key (`key.split("#")`). Call existing `_create_partial_bucket_event(ticker, resolution_enum, bucket_data)`. Add to `_event_buffer`, yield event dict.
- [x] T025 [US2] Verify T017-T020 tests pass. Run `python -m pytest tests/unit/test_sse_timeseries_polling.py tests/unit/test_sse_stream_wiring.py -v`.

**Checkpoint**: Global stream emits both `sentiment_update` and `partial_bucket` events. Timeseries failures are gracefully handled.

---

## Phase 5: User Story 3 — Consistent Config Stream Behavior (Priority: P2)

**Goal**: Wire both event types into config-specific streams with ticker filtering.

**Independent Test**: Connect global + config-specific streams. Verify config stream filters events by ticker_filters while global stream delivers all.

### Tests for User Story 3

- [x] T026 [P] [US3] Write unit tests for ticker-filtered `sentiment_update` delivery in `generate_config_stream()` in `tests/unit/test_sse_stream_wiring.py`: verify events for matching tickers pass through, non-matching tickers are filtered out, and empty ticker_filters delivers all events (FR-006).
- [x] T027 [P] [US3] Write unit tests for ticker-filtered `partial_bucket` delivery in `generate_config_stream()` in `tests/unit/test_sse_stream_wiring.py`: verify bucket events for matching tickers pass through, non-matching tickers are filtered out, and debouncer is applied (FR-005, FR-006).
- [x] T028 [P] [US3] Write unit test for config stream baseline establishment in `tests/unit/test_sse_stream_wiring.py`: verify first poll in config stream emits no `sentiment_update` or `partial_bucket` events, only heartbeat (FR-011).

### Implementation for User Story 3

- [x] T029 [US3] Replace heartbeat-only loop in `generate_config_stream()` in `src/lambdas/sse_streaming/stream.py` (lines 537-549) with a polling loop using `self._poll_service.poll_loop()`. Add local state: `local_last_per_ticker`, `local_last_buckets`, `local_is_baseline`. NOTE: Do NOT emit `metrics` events in config streams — only use the poll results for `sentiment_update` and `partial_bucket` change detection. Heartbeats remain on the existing interval. This preserves the current config stream contract (heartbeats only + new filtered events).
- [x] T030 [US3] Add ticker-filtered `sentiment_update` emission to `generate_config_stream()` in `src/lambdas/sse_streaming/stream.py`. For each changed ticker: check `connection.matches_ticker(ticker)` before emitting. Add to buffer, yield if passes filter.
- [x] T031 [US3] Add ticker-filtered `partial_bucket` emission to `generate_config_stream()` in `src/lambdas/sse_streaming/stream.py`. For each changed bucket: parse ticker from key, check `connection.matches_ticker(ticker)` and debouncer before emitting.
- [x] T032 [US3] Add `partial_bucket` event type to config stream replay filtering in `generate_config_stream()` (lines 520-528). Currently only replays `sentiment_update` events matching tickers — add `partial_bucket` with same ticker filtering logic.
- [x] T033 [US3] Verify T026-T028 tests pass. Run `python -m pytest tests/unit/test_sse_stream_wiring.py -v`.

**Checkpoint**: Both global and config streams emit `sentiment_update` and `partial_bucket` events. Config streams correctly filter by ticker.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Observability, tracing, and final validation

- [x] T034 Add OTel tracing spans for `sentiment_update` event dispatch in `generate_global_stream()` and `generate_config_stream()` in `src/lambdas/sse_streaming/stream.py` using existing `_trace_event_dispatch()` pattern (FR-008).
- [x] T035 Add OTel tracing spans for `partial_bucket` event dispatch and `_fetch_timeseries_buckets` DynamoDB call in `src/lambdas/sse_streaming/polling.py` and `src/lambdas/sse_streaming/stream.py` using existing tracing patterns (FR-008).
- [x] T036 Add structured logging for new event types: log `sentiment_update` emission count and `partial_bucket` emission count per poll cycle in `src/lambdas/sse_streaming/stream.py` using existing `logger.info()` pattern.
- [x] T037 [P] Write unit test verifying OTel spans are created for `sentiment_update` and `partial_bucket` events in `tests/unit/test_sse_stream_wiring.py`.
- [x] T038 Run full SSE test suite: `python -m pytest tests/unit/test_sse_sentiment_events.py tests/unit/test_sse_timeseries_polling.py tests/unit/test_sse_stream_wiring.py -v` — all tests must pass.
- [x] T039 Run existing SSE tests to verify no regressions: `python -m pytest tests/unit/ -k sse -v` — all pre-existing tests must pass.
- [x] T040 Run `make validate` to verify linting, formatting, and security checks pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verify environment
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 (needs `PollResult`, `TickerAggregate`, bug fix)
- **US2 (Phase 4)**: Depends on Phase 2. Can run in parallel with US1 (different concerns, but both modify `stream.py`)
- **US3 (Phase 5)**: Depends on US1 AND US2 (needs both event types implemented in global stream before wiring into config stream)
- **Polish (Phase 6)**: Depends on all user stories being complete

### Within Each User Story

- Tests are written alongside implementation (constitution requirement)
- Models/data before services
- Services before stream wiring
- Verification checkpoint at end of each phase

### Parallel Opportunities

- Within Phase 2: T006 and T007 can run in parallel (different test concerns)
- Within US1: T008-T011 test tasks can all run in parallel (different test files/concerns)
- Within US2: T017-T020 test tasks can all run in parallel
- Within US3: T026-T028 test tasks can all run in parallel
- US1 and US2 can be parallelized with care (both modify `stream.py` — coordinate on `generate_global_stream()`)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: T008 "Unit tests for _compute_per_ticker_aggregates in tests/unit/test_sse_sentiment_events.py"
Task: T009 "Unit tests for per-ticker change detection in tests/unit/test_sse_sentiment_events.py"
Task: T010 "Unit tests for sentiment_update in generate_global_stream() in tests/unit/test_sse_stream_wiring.py"
Task: T011 "Unit test for event buffer replay in tests/unit/test_sse_stream_wiring.py"

# Then sequentially:
Task: T012 "Implement _compute_per_ticker_aggregates in polling.py"
Task: T013 "Wire into PollingService.poll() in polling.py"
Task: T014 "Add per-connection local state to generate_global_stream() in stream.py"
Task: T015 "Wire _create_sentiment_event() for changed tickers in stream.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify branch)
2. Complete Phase 2: Foundational (bug fix, model updates, buffer, PollResult)
3. Complete Phase 3: User Story 1 (sentiment_update in global stream)
4. **STOP and VALIDATE**: Verify sentiment_update events appear in global stream
5. Deploy if ready — already delivers core value

### Incremental Delivery

1. Phase 2: Foundational → Bug fix + data structures ready
2. Phase 3: US1 → sentiment_update in global stream (MVP!)
3. Phase 4: US2 → partial_bucket in global stream
4. Phase 5: US3 → Both events in config streams with filtering
5. Phase 6: Polish → Tracing, logging, validation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 and US2 both modify `generate_global_stream()` — if parallelizing, coordinate changes
- US3 depends on both US1 and US2 being complete
- All test tasks use moto for DynamoDB and freezegun for time
- Total: 40 tasks (7 foundational, 9 US1, 9 US2, 8 US3, 7 polish)
