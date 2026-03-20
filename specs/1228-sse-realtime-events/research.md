# Research: Wire SSE Real-Time Events

**Feature**: 1228-sse-realtime-events
**Date**: 2026-03-20

## R1: Timeseries Table Schema and Query Pattern

**Decision**: Use `GetItem` / `BatchGetItem` for current-bucket reads.

**Rationale**: The timeseries table PK = `{ticker}#{resolution}` (e.g., "AAPL#5m"), SK = ISO8601 bucket timestamp. For detecting changes in the current bucket, we compute the bucket start time using `floor_to_bucket(now, resolution)` and read that specific item. This is O(1) per ticker#resolution.

**Alternatives considered**:
- `Query` with SK >= bucket_start: Unnecessary since we only need the current bucket, not a range. More expensive.
- `Scan` with filter: O(table) — completely unacceptable for a 5-second poll interval.

**Key finding**: DynamoDB `BatchGetItem` supports up to 100 items per request. With 22 tickers × 8 resolutions = 176 items, we need 2 batch calls per poll cycle. Each call is ~5ms latency (on-demand DynamoDB in us-east-1), so ~10ms total added latency.

## R2: Per-Ticker Aggregate from by_sentiment GSI

**Decision**: Compute per-ticker aggregates in the same `_aggregate_metrics()` pass.

**Rationale**: The existing `by_sentiment` GSI returns ALL projected attributes, including `matched_tickers` (list of ticker symbols), `score` (Decimal), and `sentiment` (string). We can compute per-ticker aggregates (weighted avg score, majority label, count) while iterating the same items — zero additional DynamoDB cost.

**Pre-existing bug**: `polling.py:92` uses `item.get("ticker")` but sentiment items use `matched_tickers` (list). The `by_tag` dict in `MetricsEventData` has been empty since the SSE Lambda was deployed. Fix: iterate `item.get("matched_tickers", [])` and attribute each ticker its own count/score.

**Alternatives considered**:
- Query `by_tag` GSI instead: Would require 22 separate queries (one per ticker). More expensive and more code than extracting tickers from the already-fetched items.
- Separate polling service for per-ticker data: Unnecessary duplication when items are already in memory.

## R3: Change Detection Strategy

**Decision**: Snapshot comparison (aggregate-level diff).

**Rationale**: Per clarification session — continuous float scores virtually guarantee that any new article changes the aggregate, so item-level cursor tracking is unnecessary. Store `dict[str, TickerAggregate]` (score, label, count) from each poll. On next poll, compare each ticker's current aggregate to the snapshot. Emit `sentiment_update` for changed tickers.

**For timeseries**: Same pattern. Store `dict[str, dict]` mapping `{ticker}#{resolution}` to the bucket's OHLC data. Compare each poll. Emit `partial_bucket` for changed buckets.

**Alternatives considered**:
- DynamoDB Streams: Would provide real-time change notifications without polling. However, DynamoDB Streams is a separate integration (Lambda trigger), not compatible with the SSE Lambda's architecture (long-running response streaming). Would require an entirely different approach.
- Timestamp-based high-water mark: More complex, requires all items to have monotonically increasing timestamps. Snapshot comparison is simpler and works with the existing data shape.

## R4: Debouncer Applicability

**Decision**: Debouncer is relevant within a single poll's emission pass, not between polls.

**Rationale**: With a 5-second polling interval, events can't arrive faster than once per 5 seconds for the same key. The debouncer (100ms interval) is relevant when a single poll cycle detects changes across many ticker#resolution pairs and emits them in rapid succession. The debouncer ensures no single key gets more than 10 events/second even if the emission loop is very fast.

**In practice**: Since each poll cycle produces at most one change per ticker#resolution, the debouncer will rarely suppress events. It serves as a safety valve for edge cases.

## R5: Event Buffer Capacity

**Decision**: Increase buffer from 100 to 500 events.

**Rationale**: A single poll cycle could produce up to 22 `sentiment_update` + 176 `partial_bucket` = 198 events. At 100 events, the buffer would overflow in a single cycle, making Last-Event-ID replay unreliable. At 500 events, the buffer holds ~2.5 polling cycles — enough for a client to reconnect within 10-15 seconds and catch up.

**Memory impact**: Each `SSEEvent` is ~500 bytes serialized. 500 events ≈ 250KB — negligible for Lambda memory.

## R6: SentimentUpdateData Payload Mapping

**Decision**: Populate with aggregate data. Set `source = "aggregate"`.

**Rationale**: Per FR-012, the payload contains: weighted average score (from all articles for that ticker), majority label (most common sentiment), average confidence (mean of all confidence scores), and `source = "aggregate"`. The existing `SentimentUpdateData` model's `score` field (range -1.0 to 1.0) maps to the weighted average. `confidence` maps to the average confidence across items.

**Note**: The `score` field in `SentimentUpdateData` allows [-1.0, 1.0] but DynamoDB items store score as [0.0, 1.0]. The mapping should use the DynamoDB value directly (no transformation needed — the broader range accommodates both).
