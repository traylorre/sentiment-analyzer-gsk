# Feature Specification: Real-Time Multi-Resolution Sentiment Time-Series

**Feature Branch**: `1009-realtime-multi-resolution`
**Created**: 2025-12-20
**Updated**: 2025-12-21
**Status**: Draft
**Input**: User description: "Real-time multi-resolution time-series architecture for sentiment data with live streaming, multiple time granularities, instant resolution switching, and shared caching for iPhone-level user experience"

---

## Canonical Sources & Citations

This specification's design decisions are grounded in authoritative sources. All architectural choices MUST be traceable to these references.

### Primary References

| ID | Source | Title | URL/Reference | Relevance |
|----|--------|-------|---------------|-----------|
| [CS-001] | AWS Documentation | Best Practices for Designing with DynamoDB | https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html | Write fanout, key design, TTL |
| [CS-002] | AWS Blog | Choosing the Right DynamoDB Partition Key | https://aws.amazon.com/blogs/database/choosing-the-right-dynamodb-partition-key/ | Composite key pattern |
| [CS-003] | Rick Houlihan (AWS) | Advanced Design Patterns for DynamoDB (re:Invent 2018) | AWS re:Invent DAT401 | Time-series patterns |
| [CS-004] | Alex DeBrie | The DynamoDB Book (Chapter 9) | https://www.dynamodbbook.com/ | Time-series key design |
| [CS-005] | AWS Documentation | Lambda Best Practices | https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html | Global scope caching |
| [CS-006] | Yan Cui | AWS Lambda: The Complete Guide | https://theburningmonk.com/ | Warm invocation caching |
| [CS-007] | MDN | Server-Sent Events | https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events | SSE patterns |
| [CS-008] | MDN | IndexedDB API | https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API | Client-side storage |
| [CS-009] | Prometheus Docs | Time-Series Alignment | https://prometheus.io/docs/prometheus/latest/querying/basics/ | Bucket alignment |
| [CS-010] | VLDB 2015 (Facebook) | Gorilla: A Fast, Scalable Time Series Database | https://vldb.org/pvldb/vol8/p1816-teller.pdf | Time bucket alignment |
| [CS-011] | Netflix Tech Blog | Streaming Time-Series Data | https://netflixtechblog.com/ | OHLC for non-financial metrics |
| [CS-012] | ACM Queue 2017 | Time-Series Databases: New Ways to Store and Access Data | https://queue.acm.org/ | OHLC aggregation efficiency |
| [CS-013] | AWS Documentation | DynamoDB TTL | https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html | Retention policies |
| [CS-014] | AWS Architecture Blog | Time-Series Data Retention Strategies | https://aws.amazon.com/architecture/ | Resolution-dependent TTL |

### Citation Format in This Document

References appear as `[CS-XXX]` throughout. When a design decision cites a source, it indicates the decision is grounded in that authoritative reference.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Live Sentiment Updates (Priority: P1)

As a dashboard user, I want to see sentiment data update in real-time as new articles are analyzed, so I can observe market sentiment changes as they happen without manually refreshing.

**Why this priority**: The core value proposition is "live breathing data" - users need to feel the dashboard is alive and current. Without real-time updates, users cannot trust they're seeing the latest sentiment and must constantly refresh.

**Independent Test**: Can be fully tested by observing the dashboard for 60 seconds and verifying sentiment values update automatically when new data arrives, delivering immediate awareness of sentiment shifts.

**Acceptance Scenarios**:

1. **Given** a user is viewing the AAPL sentiment chart, **When** new sentiment data is processed for AAPL, **Then** the chart updates within 3 seconds without user action
2. **Given** a user is viewing live sentiment data, **When** the current time bucket is partially complete, **Then** the user sees a visual indicator showing progress through the current period (e.g., "47% through this minute")
3. **Given** a user is connected to the live feed, **When** network connectivity is temporarily lost, **Then** the system reconnects automatically and resumes updates without data loss

---

### User Story 2 - Switch Resolution Levels Instantly (Priority: P1)

As a dashboard user, I want to switch between different time resolutions (1 minute, 5 minute, 1 hour, etc.) and see data instantly, so I can analyze sentiment patterns at different granularities without waiting for data to load.

**Why this priority**: Resolution switching is the primary interaction pattern for time-series analysis. Delays during switching break the analytical flow and frustrate users exploring patterns at different scales.

**Independent Test**: Can be fully tested by switching from 1-minute to 1-hour resolution and measuring perceived delay, delivering fluid exploration of sentiment trends across time scales.

**Acceptance Scenarios**:

1. **Given** a user is viewing 1-minute sentiment data, **When** they select 5-minute resolution, **Then** the chart updates within 100 milliseconds with no visible loading indicator
2. **Given** a user selects any supported resolution (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h), **When** the resolution change completes, **Then** all historical data for that resolution is displayed correctly aggregated
3. **Given** a user frequently switches between adjacent resolutions (e.g., 5m ↔ 10m), **When** switching back to a previously viewed resolution, **Then** the data appears instantly from cache

---

### User Story 3 - View Historical Sentiment Trends (Priority: P2)

As a dashboard user, I want to scroll through historical sentiment data for any ticker, so I can analyze how sentiment evolved over time and identify patterns.

**Why this priority**: Historical analysis is essential for understanding sentiment trends, but real-time viewing (P1) takes precedence as users need current data first before exploring history.

**Independent Test**: Can be fully tested by scrolling back through 24 hours of 1-minute data and verifying smooth scrolling with no loading interruptions.

**Acceptance Scenarios**:

1. **Given** a user is viewing the last hour of sentiment data, **When** they scroll left to view earlier data, **Then** the previous hour loads seamlessly without visible delay
2. **Given** a user has loaded historical data for a ticker, **When** they return to the same time range later, **Then** the data loads instantly from cache
3. **Given** a user is viewing historical data, **When** new real-time data arrives, **Then** the historical view remains stable and new data is appended at the current-time edge

---

### User Story 4 - Compare Multiple Tickers Simultaneously (Priority: P2)

As a dashboard user, I want to view sentiment data for multiple tickers at once, so I can compare sentiment trends across different stocks.

**Why this priority**: Multi-ticker comparison enables portfolio-level analysis, but single-ticker real-time viewing must work flawlessly first.

**Independent Test**: Can be fully tested by loading a view with 5 tickers and verifying all update in real-time simultaneously.

**Acceptance Scenarios**:

1. **Given** a user requests to view 10 tickers simultaneously, **When** the multi-ticker view loads, **Then** all charts appear within 1 second total
2. **Given** a user is viewing multiple tickers, **When** sentiment updates arrive for different tickers, **Then** each ticker's chart updates independently without affecting others
3. **Given** multiple users are viewing the same ticker (e.g., AAPL), **When** both request historical data, **Then** the second user's request is served from shared cache instantly

---

### User Story 5 - Continue Working During Connectivity Issues (Priority: P3)

As a dashboard user, I want the dashboard to remain functional even when my network connection is unstable, so I can continue analyzing available data without disruption.

**Why this priority**: Resilience is important but secondary to core functionality. Users accept brief outages if the system recovers gracefully.

**Independent Test**: Can be fully tested by simulating network disconnection and verifying historical data remains viewable and reconnection happens automatically.

**Acceptance Scenarios**:

1. **Given** a user has previously loaded sentiment data, **When** network connectivity is lost, **Then** all cached historical data remains viewable and navigable
2. **Given** the live connection is interrupted, **When** connectivity is restored, **Then** the system automatically reconnects and resumes updates within 5 seconds
3. **Given** the live feed fails to connect, **When** the user attempts to view data, **Then** the system falls back to periodic polling and displays a subtle indicator of degraded mode

---

### Edge Cases

- What happens when a ticker has no sentiment data for the selected time range? (Display "No data available" message with suggested alternative time ranges)
- How does the system handle clock skew between server and client? (Align all timestamps to server time, display in user's local timezone)
- What happens when a user switches tickers very rapidly? (Cancel pending requests for abandoned tickers, prioritize current selection)
- How does the system behave at market open when data volume spikes? (Graceful degradation: prioritize live updates over historical queries)
- What happens to partial bucket data if the browser tab is backgrounded? (Pause updates while backgrounded, sync on return to foreground)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST stream sentiment updates to connected users within 3 seconds of data becoming available `[CS-007]`
- **FR-002**: System MUST support 8 resolution levels: 1 minute, 5 minutes, 10 minutes, 1 hour, 3 hours, 6 hours, 12 hours, and 24 hours `[CS-009, CS-010]`
- **FR-003**: System MUST aggregate higher resolutions from base 1-minute data (e.g., 5-minute resolution is the aggregation of 5 consecutive 1-minute buckets) `[CS-001, CS-003]`
- **FR-004**: System MUST display a "partial bucket" indicator showing progress through the current incomplete time period with running aggregates `[CS-011]`
- **FR-005**: System MUST cache sentiment data to serve repeated requests without recomputation `[CS-005, CS-006]`
- **FR-006**: System MUST share cached data across all users viewing the same ticker and resolution `[CS-001]`
- **FR-007**: System MUST preload adjacent resolutions when a user selects a resolution (e.g., selecting 5m preloads 1m and 10m) `[CS-008]`
- **FR-008**: System MUST preload adjacent time ranges when a user views historical data (e.g., viewing 1pm-2pm preloads 12pm-1pm) `[CS-008]`
- **FR-009**: System MUST automatically reconnect after connection loss without user intervention `[CS-007]`
- **FR-010**: System MUST fall back to periodic polling if streaming connection cannot be established `[CS-007]`
- **FR-011**: System MUST display skeleton placeholders during initial load (never show loading spinners)
- **FR-012**: System MUST support at least 13 simultaneous tickers with real-time updates `[CS-002]`
- **FR-013**: System MUST retain historical data for at least 24 hours at 1-minute resolution `[CS-013, CS-014]`
- **FR-014**: System MUST align all time buckets to consistent boundaries (e.g., 5-minute buckets start at :00, :05, :10...) `[CS-009, CS-010]`

### Key Entities

- **Sentiment Bucket**: A time-bounded aggregation of sentiment data containing: ticker symbol, time boundary (start/end), aggregated sentiment score, sentiment label, confidence score, article count, and OHLC-style sentiment values (open/high/low/close scores) `[CS-011, CS-012]`
- **Partial Bucket**: An incomplete sentiment bucket representing the current in-progress time period, including progress percentage and running aggregates that update as new data arrives
- **Ticker Subscription**: A user's active connection to receive real-time updates for a specific ticker at a specific resolution `[CS-007]`
- **Resolution**: A time granularity setting (1m/5m/10m/1h/3h/6h/12h/24h) that determines how sentiment data is aggregated for display `[CS-009]`

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard initial load completes in under 500 milliseconds for returning users
- **SC-002**: Resolution switching completes in under 100 milliseconds (perceived by user)
- **SC-003**: Live sentiment updates appear on dashboard within 3 seconds of data processing completion
- **SC-004**: System supports 100 concurrent users viewing real-time data without degradation
- **SC-005**: Historical scroll/pan operations complete instantly with no visible loading delays
- **SC-006**: Multi-ticker view (10 tickers) loads in under 1 second total
- **SC-007**: Automatic reconnection after network interruption completes within 5 seconds
- **SC-008**: Cache hit rate for shared ticker data exceeds 80% during normal operation
- **SC-009**: Zero loading spinners visible during normal operation (skeleton UI only)
- **SC-010**: Monthly infrastructure cost for real-time features remains under $60 for 13 tickers and 100 users

---

## Assumptions

- Market hours are approximately 8 hours/day (9:30 AM - 4:00 PM ET) with 22 trading days per month
- The existing ingestion pipeline produces sentiment data at article-level granularity (few per minute per ticker)
- Users primarily access the dashboard during market hours when real-time data is most valuable
- Browser tab focus/visibility APIs are reliable for detecting backgrounded tabs
- Users have modern browsers supporting streaming connections and local storage for caching

---

## Scope Boundaries

**In Scope**:
- Real-time sentiment streaming to dashboard
- Multi-resolution time aggregation (8 levels)
- Client-side and server-side caching
- Automatic preloading strategies
- Graceful degradation and reconnection
- Skeleton loading UI patterns

**Out of Scope**:
- Real-time price data integration (separate feature)
- Alerts/notifications based on sentiment thresholds
- Custom resolution definitions by users
- Sentiment data export functionality
- Mobile app native implementation (web-responsive only)
- Historical data beyond 24 hours at 1-minute resolution

---

## TDD Test Design *(mandatory)*

This section defines exhaustive test cases that MUST be implemented BEFORE the corresponding production code. Tests are organized by component and priority.

### Test Philosophy

When tests fail:
1. **DO NOT assume tests are wrong** - First assume lack of understanding of context
2. **Step back to reassess** - Review canonical sources `[CS-XXX]` for the pattern
3. **Research similar patterns** - Look at public projects (Prometheus, InfluxDB, Grafana)
4. **Formulate 3+ approaches** - Never immediately "fix" by changing test expectations
5. **Ask clarifying questions** - If in doubt, pause and clarify before proceeding

### Test Categories

| Category | Location | Mocking Strategy | Priority |
|----------|----------|------------------|----------|
| Unit | `tests/unit/` | All externals mocked (moto, responses) | Run always |
| Integration | `tests/integration/` | Real LocalStack, mock external APIs | Run on PR |
| E2E | `tests/e2e/` | Real preprod AWS, synthetic data | Run on merge |

---

### Component 1: Time Bucket Alignment (`src/lib/timeseries/bucket.py`)

**Canonical Reference**: `[CS-009]` Prometheus time-series alignment, `[CS-010]` Gorilla paper

#### Test Suite: `tests/unit/test_timeseries_bucket.py`

```python
# TDD-BUCKET-001: Floor timestamp to resolution boundary
class TestBucketAlignment:
    """
    Canonical: [CS-009] "Align time buckets to wall-clock boundaries"
    """

    @pytest.mark.parametrize("timestamp,resolution,expected", [
        # 1-minute alignment
        ("2025-12-21T10:35:47Z", "1m", "2025-12-21T10:35:00Z"),
        ("2025-12-21T10:35:00Z", "1m", "2025-12-21T10:35:00Z"),
        ("2025-12-21T10:35:59Z", "1m", "2025-12-21T10:35:00Z"),

        # 5-minute alignment
        ("2025-12-21T10:37:00Z", "5m", "2025-12-21T10:35:00Z"),
        ("2025-12-21T10:34:59Z", "5m", "2025-12-21T10:30:00Z"),
        ("2025-12-21T10:40:00Z", "5m", "2025-12-21T10:40:00Z"),

        # 10-minute alignment
        ("2025-12-21T10:45:30Z", "10m", "2025-12-21T10:40:00Z"),
        ("2025-12-21T10:39:59Z", "10m", "2025-12-21T10:30:00Z"),

        # 1-hour alignment
        ("2025-12-21T10:45:00Z", "1h", "2025-12-21T10:00:00Z"),
        ("2025-12-21T10:00:00Z", "1h", "2025-12-21T10:00:00Z"),

        # 3-hour alignment
        ("2025-12-21T14:30:00Z", "3h", "2025-12-21T12:00:00Z"),
        ("2025-12-21T11:59:59Z", "3h", "2025-12-21T09:00:00Z"),

        # 6-hour alignment
        ("2025-12-21T14:30:00Z", "6h", "2025-12-21T12:00:00Z"),
        ("2025-12-21T05:59:59Z", "6h", "2025-12-21T00:00:00Z"),

        # 12-hour alignment
        ("2025-12-21T14:30:00Z", "12h", "2025-12-21T12:00:00Z"),
        ("2025-12-21T11:59:59Z", "12h", "2025-12-21T00:00:00Z"),

        # 24-hour alignment
        ("2025-12-21T14:30:00Z", "24h", "2025-12-21T00:00:00Z"),
        ("2025-12-21T23:59:59Z", "24h", "2025-12-21T00:00:00Z"),
    ])
    def test_floor_to_resolution_boundary(self, timestamp, resolution, expected):
        """Bucket timestamps MUST align to wall-clock boundaries per [CS-009]."""
        result = floor_to_bucket(parse_iso(timestamp), Resolution(resolution))
        assert result == parse_iso(expected)

    def test_invalid_resolution_raises(self):
        """Unknown resolution MUST raise ValueError with valid options listed."""
        with pytest.raises(ValueError, match="Resolution must be one of"):
            floor_to_bucket(datetime.now(UTC), Resolution("3m"))

    def test_bucket_duration_seconds(self):
        """Each resolution MUST have correct duration in seconds."""
        expected = {
            "1m": 60, "5m": 300, "10m": 600, "1h": 3600,
            "3h": 10800, "6h": 21600, "12h": 43200, "24h": 86400
        }
        for res, seconds in expected.items():
            assert Resolution(res).duration_seconds == seconds
```

#### Test Suite: `tests/unit/test_bucket_progress.py`

```python
# TDD-BUCKET-002: Partial bucket progress calculation
class TestPartialBucketProgress:
    """
    Canonical: [CS-011] "Partial aggregates with progress indicators"
    """

    @freeze_time("2025-12-21T10:37:30Z")
    def test_progress_midway_through_5min_bucket(self):
        """
        Given: Current time is 2:30 into a 5-minute bucket (10:35:00 - 10:40:00)
        Then: Progress should be 50%
        """
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert progress == pytest.approx(50.0, rel=0.01)

    @freeze_time("2025-12-21T10:35:00Z")
    def test_progress_at_bucket_start(self):
        """Progress at exact bucket start should be 0%."""
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert progress == 0.0

    @freeze_time("2025-12-21T10:39:59Z")
    def test_progress_near_bucket_end(self):
        """Progress near bucket end should approach 100% but never exceed."""
        bucket_start = parse_iso("2025-12-21T10:35:00Z")
        progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
        assert 99.0 <= progress < 100.0

    def test_progress_for_completed_bucket_returns_100(self):
        """Completed buckets should return exactly 100%."""
        with freeze_time("2025-12-21T10:45:00Z"):
            bucket_start = parse_iso("2025-12-21T10:35:00Z")
            progress = calculate_bucket_progress(bucket_start, Resolution("5m"))
            assert progress == 100.0
```

---

### Component 2: OHLC Aggregation (`src/lib/timeseries/aggregation.py`)

**Canonical Reference**: `[CS-011]` Netflix on OHLC for non-financial, `[CS-012]` ACM Queue on aggregation

#### Test Suite: `tests/unit/test_timeseries_aggregation.py`

```python
# TDD-OHLC-001: OHLC aggregation from raw scores
class TestOHLCAggregation:
    """
    Canonical: [CS-011] "OHLC effective for any bounded metric where extrema matter"
    [CS-012] "Min/max/open/close captures distribution shape efficiently"
    """

    def test_single_score_all_ohlc_equal(self):
        """Single score: open == high == low == close."""
        scores = [SentimentScore(value=0.75, timestamp=parse_iso("2025-12-21T10:35:15Z"))]
        result = aggregate_ohlc(scores)
        assert result.open == 0.75
        assert result.high == 0.75
        assert result.low == 0.75
        assert result.close == 0.75

    def test_multiple_scores_ordered_by_timestamp(self):
        """
        Given scores: [0.6, 0.9, 0.3, 0.7] in timestamp order
        Then: open=0.6, high=0.9, low=0.3, close=0.7
        """
        scores = [
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.9, timestamp=parse_iso("2025-12-21T10:35:20Z")),
            SentimentScore(value=0.3, timestamp=parse_iso("2025-12-21T10:35:30Z")),
            SentimentScore(value=0.7, timestamp=parse_iso("2025-12-21T10:35:40Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.open == 0.6  # First by timestamp
        assert result.high == 0.9  # Maximum value
        assert result.low == 0.3   # Minimum value
        assert result.close == 0.7 # Last by timestamp

    def test_unordered_input_sorted_by_timestamp(self):
        """Scores provided out-of-order MUST be sorted before aggregation."""
        scores = [
            SentimentScore(value=0.7, timestamp=parse_iso("2025-12-21T10:35:40Z")),
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.9, timestamp=parse_iso("2025-12-21T10:35:20Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.open == 0.6  # Earliest timestamp
        assert result.close == 0.7 # Latest timestamp

    def test_empty_scores_raises_value_error(self):
        """Empty score list MUST raise ValueError, not return zeros."""
        with pytest.raises(ValueError, match="Cannot aggregate empty"):
            aggregate_ohlc([])

    def test_label_counts_aggregation(self):
        """Label counts MUST sum individual sentiment labels."""
        scores = [
            SentimentScore(value=0.8, label="positive", timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.1, label="neutral", timestamp=parse_iso("2025-12-21T10:35:20Z")),
            SentimentScore(value=0.9, label="positive", timestamp=parse_iso("2025-12-21T10:35:30Z")),
            SentimentScore(value=-0.6, label="negative", timestamp=parse_iso("2025-12-21T10:35:40Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.label_counts == {"positive": 2, "neutral": 1, "negative": 1}

    def test_average_calculated_correctly(self):
        """Average MUST be sum/count, not recomputed from OHLC."""
        scores = [
            SentimentScore(value=0.6, timestamp=parse_iso("2025-12-21T10:35:10Z")),
            SentimentScore(value=0.8, timestamp=parse_iso("2025-12-21T10:35:20Z")),
        ]
        result = aggregate_ohlc(scores)
        assert result.avg == pytest.approx(0.7, rel=0.001)
        assert result.count == 2
        assert result.sum == pytest.approx(1.4, rel=0.001)
```

---

### Component 3: DynamoDB Key Design (`src/lib/timeseries/models.py`)

**Canonical Reference**: `[CS-002]` AWS composite key pattern, `[CS-004]` DynamoDB Book

#### Test Suite: `tests/unit/test_timeseries_key_design.py`

```python
# TDD-KEY-001: Composite key generation
class TestTimeseriesKeyDesign:
    """
    Canonical: [CS-002] "Use composite keys with delimiter for hierarchical access"
    [CS-004] "ticker#resolution is standard for multi-dimensional time-series"
    """

    @pytest.mark.parametrize("ticker,resolution,expected_pk", [
        ("AAPL", "1m", "AAPL#1m"),
        ("TSLA", "5m", "TSLA#5m"),
        ("MSFT", "1h", "MSFT#1h"),
        ("GOOGL", "24h", "GOOGL#24h"),
    ])
    def test_partition_key_format(self, ticker, resolution, expected_pk):
        """PK MUST be {ticker}#{resolution} per [CS-002]."""
        key = TimeseriesKey(ticker=ticker, resolution=Resolution(resolution))
        assert key.pk == expected_pk

    def test_sort_key_is_iso8601_timestamp(self):
        """SK MUST be ISO8601 bucket timestamp."""
        key = TimeseriesKey(
            ticker="AAPL",
            resolution=Resolution("5m"),
            bucket_timestamp=parse_iso("2025-12-21T10:35:00Z")
        )
        assert key.sk == "2025-12-21T10:35:00Z"

    def test_key_from_pk_sk_strings(self):
        """MUST be able to reconstruct key from DynamoDB strings."""
        key = TimeseriesKey.from_dynamodb(pk="AAPL#5m", sk="2025-12-21T10:35:00Z")
        assert key.ticker == "AAPL"
        assert key.resolution == Resolution("5m")
        assert key.bucket_timestamp == parse_iso("2025-12-21T10:35:00Z")

    def test_invalid_pk_format_raises(self):
        """Malformed PK MUST raise with descriptive error."""
        with pytest.raises(ValueError, match="PK must match pattern"):
            TimeseriesKey.from_dynamodb(pk="AAPL", sk="2025-12-21T10:35:00Z")

    def test_delimiter_in_ticker_rejected(self):
        """Ticker with # delimiter MUST be rejected."""
        with pytest.raises(ValueError, match="Ticker cannot contain"):
            TimeseriesKey(ticker="AA#PL", resolution=Resolution("5m"))
```

---

### Component 4: Write Fanout (`src/lambdas/ingestion/timeseries_fanout.py`)

**Canonical Reference**: `[CS-001]` AWS pre-aggregation, `[CS-003]` Write amplification pattern

#### Test Suite: `tests/unit/test_timeseries_fanout.py`

```python
# TDD-FANOUT-001: Write fanout to all resolutions
class TestWriteFanout:
    """
    Canonical: [CS-001] "Pre-aggregate at write time for known query patterns"
    [CS-003] "Write amplification acceptable when reads >> writes"
    """

    def test_fanout_creates_8_resolution_items(self):
        """Single sentiment score MUST produce 8 DynamoDB items (one per resolution)."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            label="positive",
            timestamp=parse_iso("2025-12-21T10:35:47Z")
        )
        items = generate_fanout_items(score)
        assert len(items) == 8
        resolutions = {item["PK"]["S"].split("#")[1] for item in items}
        assert resolutions == {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}

    def test_fanout_bucket_timestamps_aligned(self):
        """Each resolution item MUST have correctly aligned bucket timestamp."""
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:37:47Z")
        )
        items = generate_fanout_items(score)

        # Find 1m bucket
        item_1m = next(i for i in items if "1m" in i["PK"]["S"])
        assert item_1m["SK"]["S"] == "2025-12-21T10:37:00Z"

        # Find 5m bucket
        item_5m = next(i for i in items if "5m" in i["PK"]["S"])
        assert item_5m["SK"]["S"] == "2025-12-21T10:35:00Z"

        # Find 1h bucket
        item_1h = next(i for i in items if "1h" in i["PK"]["S"])
        assert item_1h["SK"]["S"] == "2025-12-21T10:00:00Z"

    def test_fanout_ttl_resolution_dependent(self):
        """
        TTL MUST vary by resolution per [CS-014]:
        - 1m: 6 hours
        - 5m: 12 hours
        - 1h: 7 days
        - 24h: 90 days
        """
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            timestamp=parse_iso("2025-12-21T10:35:00Z")
        )
        items = generate_fanout_items(score)

        item_1m = next(i for i in items if "1m" in i["PK"]["S"])
        item_24h = next(i for i in items if "24h" in i["PK"]["S"])

        # 1m TTL should be ~6 hours from now
        ttl_1m = int(item_1m["ttl"]["N"])
        expected_1m = int(parse_iso("2025-12-21T10:35:00Z").timestamp()) + (6 * 3600)
        assert ttl_1m == expected_1m

        # 24h TTL should be ~90 days from now
        ttl_24h = int(item_24h["ttl"]["N"])
        expected_24h = int(parse_iso("2025-12-21T10:35:00Z").timestamp()) + (90 * 86400)
        assert ttl_24h == expected_24h

    @mock_aws
    def test_fanout_uses_batch_write(self):
        """Fanout MUST use BatchWriteItem for efficiency, not individual PutItem."""
        # Setup
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-timeseries",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        score = SentimentScore(ticker="AAPL", value=0.75, timestamp=datetime.now(UTC))

        # Execute
        with patch.object(dynamodb, "batch_write_item", wraps=dynamodb.batch_write_item) as mock_batch:
            write_fanout(dynamodb, "test-timeseries", score)
            mock_batch.assert_called_once()

        # Verify all items written
        response = dynamodb.scan(TableName="test-timeseries")
        assert response["Count"] == 8
```

---

### Component 5: Lambda Global Cache (`src/lambdas/sse_streaming/cache.py`)

**Canonical Reference**: `[CS-005]` Lambda best practices, `[CS-006]` Warm invocation caching

#### Test Suite: `tests/unit/test_resolution_cache.py`

```python
# TDD-CACHE-001: Resolution-aware TTL caching
class TestResolutionAwareCache:
    """
    Canonical: [CS-005] "Initialize outside handler for execution reuse"
    [CS-006] "Global scope persists across warm invocations"
    """

    def test_cache_ttl_matches_resolution(self):
        """Cache TTL MUST equal resolution duration per [CS-006]."""
        cache = ResolutionCache()

        # 1-minute resolution has 60-second TTL
        cache.set("AAPL", Resolution("1m"), data={"test": 1})
        entry = cache._entries[("AAPL", "1m")]
        assert entry.ttl_seconds == 60

        # 1-hour resolution has 3600-second TTL
        cache.set("AAPL", Resolution("1h"), data={"test": 2})
        entry = cache._entries[("AAPL", "1h")]
        assert entry.ttl_seconds == 3600

    @freeze_time("2025-12-21T10:35:00Z")
    def test_cache_hit_within_ttl(self):
        """Cache GET within TTL MUST return cached data."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution("5m"), data={"value": 42})

        with freeze_time("2025-12-21T10:37:00Z"):  # 2 minutes later, within 5m TTL
            result = cache.get("AAPL", Resolution("5m"))
            assert result == {"value": 42}

    @freeze_time("2025-12-21T10:35:00Z")
    def test_cache_miss_after_ttl(self):
        """Cache GET after TTL MUST return None."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution("5m"), data={"value": 42})

        with freeze_time("2025-12-21T10:45:00Z"):  # 10 minutes later, past 5m TTL
            result = cache.get("AAPL", Resolution("5m"))
            assert result is None

    def test_cache_stats_tracking(self):
        """Cache MUST track hits and misses for observability."""
        cache = ResolutionCache()
        cache.set("AAPL", Resolution("1m"), data={"test": 1})

        cache.get("AAPL", Resolution("1m"))  # Hit
        cache.get("AAPL", Resolution("1m"))  # Hit
        cache.get("TSLA", Resolution("1m"))  # Miss

        assert cache.stats.hits == 2
        assert cache.stats.misses == 1
        assert cache.stats.hit_rate == pytest.approx(0.667, rel=0.01)

    def test_cache_size_bounded(self):
        """Cache MUST evict oldest entries when max size reached."""
        cache = ResolutionCache(max_entries=2)

        cache.set("AAPL", Resolution("1m"), data={"a": 1})
        cache.set("TSLA", Resolution("1m"), data={"b": 2})
        cache.set("MSFT", Resolution("1m"), data={"c": 3})  # Should evict AAPL

        assert cache.get("AAPL", Resolution("1m")) is None
        assert cache.get("TSLA", Resolution("1m")) == {"b": 2}
        assert cache.get("MSFT", Resolution("1m")) == {"c": 3}
```

---

### Component 6: SSE Resolution Filtering (`src/lambdas/sse_streaming/stream.py`)

**Canonical Reference**: `[CS-007]` MDN SSE best practices

#### Test Suite: `tests/unit/test_sse_resolution_filter.py`

```python
# TDD-SSE-001: Resolution-filtered event streaming
class TestSSEResolutionFilter:
    """
    Canonical: [CS-007] "Filter events at server to reduce bandwidth"
    """

    def test_filter_passes_subscribed_resolutions(self):
        """Events matching subscribed resolutions MUST pass filter."""
        connection = SSEConnection(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution("1m"), Resolution("5m")]
        )

        event_1m = BucketUpdateEvent(ticker="AAPL", resolution=Resolution("1m"), bucket={})
        event_5m = BucketUpdateEvent(ticker="AAPL", resolution=Resolution("5m"), bucket={})

        assert should_send_event(connection, event_1m) is True
        assert should_send_event(connection, event_5m) is True

    def test_filter_blocks_unsubscribed_resolutions(self):
        """Events NOT matching subscribed resolutions MUST be blocked."""
        connection = SSEConnection(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution("1m")]
        )

        event_1h = BucketUpdateEvent(ticker="AAPL", resolution=Resolution("1h"), bucket={})

        assert should_send_event(connection, event_1h) is False

    def test_heartbeat_always_passes(self):
        """Heartbeat events MUST always pass regardless of resolution filter."""
        connection = SSEConnection(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution("1m")]
        )

        heartbeat = HeartbeatEvent(timestamp=datetime.now(UTC), connections=10)

        assert should_send_event(connection, heartbeat) is True

    def test_ticker_filter_combined_with_resolution(self):
        """Both ticker AND resolution filters MUST be applied."""
        connection = SSEConnection(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution("1m")],
            subscribed_tickers=["AAPL", "TSLA"]
        )

        event_aapl = BucketUpdateEvent(ticker="AAPL", resolution=Resolution("1m"), bucket={})
        event_msft = BucketUpdateEvent(ticker="MSFT", resolution=Resolution("1m"), bucket={})

        assert should_send_event(connection, event_aapl) is True
        assert should_send_event(connection, event_msft) is False

    def test_empty_ticker_filter_allows_all(self):
        """Empty ticker filter MUST allow all tickers."""
        connection = SSEConnection(
            connection_id="conn-123",
            subscribed_resolutions=[Resolution("1m")],
            subscribed_tickers=[]  # Empty = all
        )

        event = BucketUpdateEvent(ticker="GOOGL", resolution=Resolution("1m"), bucket={})

        assert should_send_event(connection, event) is True
```

---

### Component 7: Client-Side IndexedDB Cache (`src/dashboard/cache.js`)

**Canonical Reference**: `[CS-008]` MDN IndexedDB

#### Test Suite: `tests/e2e/test_client_cache.py` (Playwright/Selenium)

```python
# TDD-CLIENT-001: IndexedDB caching for instant resolution switch
class TestClientSideCache:
    """
    Canonical: [CS-008] "IndexedDB optimal for large structured datasets with indexes"
    """

    @pytest.mark.e2e
    async def test_resolution_switch_uses_cache(self, page):
        """
        Given: User has viewed 5m resolution for AAPL
        When: User switches to 1h, then back to 5m
        Then: 5m data loads instantly from IndexedDB (no network request)
        """
        # Load initial data
        await page.goto("/dashboard?ticker=AAPL&resolution=5m")
        await page.wait_for_selector("[data-testid='chart-loaded']")

        # Switch to 1h
        await page.click("[data-testid='resolution-1h']")
        await page.wait_for_selector("[data-testid='chart-loaded']")

        # Track network requests
        requests = []
        page.on("request", lambda r: requests.append(r.url) if "/timeseries" in r.url else None)

        # Switch back to 5m
        await page.click("[data-testid='resolution-5m']")
        await page.wait_for_selector("[data-testid='chart-loaded']")

        # No new timeseries request for 5m (served from cache)
        assert not any("resolution=5m" in r for r in requests)

    @pytest.mark.e2e
    async def test_cache_version_invalidation(self, page):
        """Cache MUST be invalidated when schema version changes."""
        # Set old cache version
        await page.evaluate("""
            localStorage.setItem('timeseries_cache_version', '1.0.0');
        """)

        # Load page (new version is 2.0.0)
        await page.goto("/dashboard?ticker=AAPL&resolution=5m")

        # Verify cache was cleared
        cache_version = await page.evaluate("localStorage.getItem('timeseries_cache_version')")
        assert cache_version == "2.0.0"
```

---

### Integration Tests

#### Test Suite: `tests/integration/test_timeseries_pipeline.py`

```python
# TDD-INT-001: End-to-end timeseries write and query
class TestTimeseriesPipeline:
    """
    Integration test using LocalStack.
    Validates full pipeline: ingest -> fanout -> query -> SSE stream.
    """

    @pytest.fixture(autouse=True)
    def setup_localstack(self, localstack_dynamodb):
        """Create timeseries table in LocalStack."""
        localstack_dynamodb.create_table(
            TableName="test-sentiment-timeseries",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield
        localstack_dynamodb.delete_table(TableName="test-sentiment-timeseries")

    def test_ingestion_triggers_fanout_to_all_resolutions(self, localstack_dynamodb):
        """
        Given: A new sentiment score is ingested
        When: Fanout completes
        Then: 8 items exist in timeseries table (one per resolution)
        """
        # Ingest
        score = SentimentScore(
            ticker="AAPL",
            value=0.75,
            label="positive",
            timestamp=parse_iso("2025-12-21T10:35:47Z")
        )
        write_fanout(localstack_dynamodb, "test-sentiment-timeseries", score)

        # Verify
        response = localstack_dynamodb.scan(TableName="test-sentiment-timeseries")
        assert response["Count"] == 8

        pks = {item["PK"]["S"] for item in response["Items"]}
        assert pks == {
            "AAPL#1m", "AAPL#5m", "AAPL#10m", "AAPL#1h",
            "AAPL#3h", "AAPL#6h", "AAPL#12h", "AAPL#24h"
        }

    def test_query_returns_buckets_in_time_order(self, localstack_dynamodb):
        """
        Given: Multiple buckets exist for AAPL#5m
        When: Query with time range
        Then: Buckets returned in ascending timestamp order
        """
        # Insert 3 buckets
        for ts in ["2025-12-21T10:30:00Z", "2025-12-21T10:35:00Z", "2025-12-21T10:40:00Z"]:
            localstack_dynamodb.put_item(
                TableName="test-sentiment-timeseries",
                Item={
                    "PK": {"S": "AAPL#5m"},
                    "SK": {"S": ts},
                    "open": {"N": "0.5"},
                    "high": {"N": "0.8"},
                    "low": {"N": "0.3"},
                    "close": {"N": "0.6"},
                    "count": {"N": "5"},
                }
            )

        # Query
        buckets = query_timeseries(
            localstack_dynamodb,
            "test-sentiment-timeseries",
            ticker="AAPL",
            resolution=Resolution("5m"),
            start=parse_iso("2025-12-21T10:25:00Z"),
            end=parse_iso("2025-12-21T10:45:00Z")
        )

        # Verify order
        assert len(buckets) == 3
        assert buckets[0].timestamp < buckets[1].timestamp < buckets[2].timestamp

    def test_partial_bucket_flagged_correctly(self, localstack_dynamodb):
        """
        Given: Current time is mid-bucket
        When: Query includes current bucket
        Then: Current bucket is marked is_partial=True
        """
        with freeze_time("2025-12-21T10:37:30Z"):
            # Insert current bucket
            localstack_dynamodb.put_item(
                TableName="test-sentiment-timeseries",
                Item={
                    "PK": {"S": "AAPL#5m"},
                    "SK": {"S": "2025-12-21T10:35:00Z"},
                    "is_partial": {"BOOL": True},
                    "open": {"N": "0.5"},
                    "count": {"N": "3"},
                }
            )

            # Query
            response = query_timeseries(
                localstack_dynamodb,
                "test-sentiment-timeseries",
                ticker="AAPL",
                resolution=Resolution("5m"),
                start=parse_iso("2025-12-21T10:30:00Z"),
                end=parse_iso("2025-12-21T10:40:00Z")
            )

            # Verify partial bucket
            assert len(response.buckets) == 0
            assert response.partial_bucket is not None
            assert response.partial_bucket.is_partial is True
            assert 40.0 <= response.partial_bucket.progress_pct <= 60.0
```

---

## Test Failure Handling Protocol

When any test fails, follow this protocol BEFORE modifying the test:

### Step 1: Diagnose Root Cause

```
□ Read the full error message and stack trace
□ Identify which assertion failed and why
□ Check if the failure is in test setup, execution, or assertion
```

### Step 2: Review Canonical Sources

```
□ Find the [CS-XXX] citation for this test
□ Re-read the canonical source documentation
□ Verify our understanding matches the source
```

### Step 3: Research Similar Implementations

```
□ Check Prometheus source code for time-series patterns
□ Check InfluxDB/TimescaleDB for aggregation patterns
□ Check Grafana for client-side caching patterns
□ Search GitHub for "DynamoDB time-series" implementations
```

### Step 4: Formulate 3+ Approaches

Before making changes, document at least 3 approaches:

```
Approach 1: [Description] - Pros/Cons
Approach 2: [Description] - Pros/Cons
Approach 3: [Description] - Pros/Cons
```

### Step 5: Ask Clarifying Questions

If uncertainty remains:

```
1. Is the test expectation correct according to [CS-XXX]?
2. Does the implementation match the canonical pattern?
3. Are there edge cases we haven't considered?
4. Would a different approach better satisfy requirements?
```

### Step 6: Document Decision

After resolution, add to `docs/architecture-decisions.md`:

```markdown
### ADR-XXX: [Test/Pattern Name]
- **Context**: [What failed, why]
- **Decision**: [What approach was chosen]
- **Canonical Source**: [CS-XXX reference]
- **Alternatives Considered**: [Other approaches]
- **Consequences**: [Impact on design]
```
