# Feature Specification: Market Data Ingestion

**Feature Branch**: `072-market-data-ingestion`
**Created**: 2025-12-09
**Status**: Draft
**Input**: User description: "Market Data Ingestion - Fresh, reliable market sentiment data collection from multiple sources with automatic failover"

## Problem Statement

Analysts need fresh, reliable market sentiment data to make informed trading decisions. Currently, data staleness and source unreliability cause analysts to distrust displayed values, leading to manual verification that wastes 30+ minutes daily.

## User Personas

- **Analyst**: Views sentiment trends, needs data freshness guarantees
- **Operations Engineer**: Monitors system health, needs visibility into failures
- **Portfolio Manager**: Makes decisions based on aggregated sentiment, needs confidence in data quality

## User Scenarios & Testing

### User Story 1 - Fresh Data Availability (Priority: P1)

As an analyst, I want sentiment data that is no older than 15 minutes so that my decisions reflect current market conditions.

**Why this priority**: Data freshness is the core value proposition. Without fresh data, the entire system provides negative value (misleading information is worse than no information).

**Independent Test**: Can be tested by observing data timestamps on dashboard and verifying they are within 15 minutes of current time during market hours.

**Acceptance Scenarios**:

1. **Given** market hours are active (9:30 AM - 4:00 PM ET), **When** analyst views dashboard, **Then** all displayed sentiment data has timestamps within 15 minutes
2. **Given** a data source becomes unavailable, **When** analyst views dashboard, **Then** last-known-good values are shown with a staleness indicator
3. **Given** data is older than 15 minutes, **When** analyst views dashboard, **Then** a visual warning indicates data staleness

---

### User Story 2 - Multi-Source Resilience (Priority: P1)

As an analyst, I want data from multiple sources so that single-source outages don't interrupt my workflow.

**Why this priority**: Source reliability directly impacts data freshness. Without failover, a single source outage breaks the P1 freshness guarantee.

**Independent Test**: Can be tested by simulating primary source failure and verifying data continues flowing from secondary source within 30 seconds.

**Acceptance Scenarios**:

1. **Given** primary data source is available, **When** system collects data, **Then** data is fetched from primary source
2. **Given** primary source fails, **When** system detects failure, **Then** system automatically switches to secondary source within 10 seconds
3. **Given** failover occurred, **When** analyst views dashboard, **Then** source attribution indicates which source provided the data
4. **Given** all sources fail, **When** system cannot collect data, **Then** operations team receives an alert within 5 minutes

---

### User Story 3 - Data Quality Confidence (Priority: P2)

As a portfolio manager, I want confidence scores with each sentiment value so that I can weight decisions appropriately.

**Why this priority**: Important for sophisticated users but the system still provides value without confidence scores. This enhances rather than enables core functionality.

**Independent Test**: Can be tested by verifying each sentiment value displays an accompanying confidence score (0.0-1.0) and low-confidence values are visually distinguished.

**Acceptance Scenarios**:

1. **Given** sentiment data is collected, **When** displayed to user, **Then** a confidence score (0.0-1.0) accompanies each sentiment value
2. **Given** confidence score is below threshold, **When** displayed to user, **Then** value is visually distinguished (e.g., muted color, warning icon)
3. **Given** user views historical data, **When** comparing accuracy, **Then** historical accuracy metrics are available

---

### User Story 4 - Operational Visibility (Priority: P2)

As an operations engineer, I want visibility into collection health so that I can proactively address issues before users are impacted.

**Why this priority**: Supports system reliability but analysts can still use the system without operational dashboards.

**Independent Test**: Can be tested by viewing operational metrics and verifying collection success rates, latency, and error counts are visible.

**Acceptance Scenarios**:

1. **Given** system is collecting data, **When** ops engineer views metrics, **Then** collection success rate is visible
2. **Given** collection errors occur, **When** ops engineer views metrics, **Then** error counts and types are visible
3. **Given** collection latency increases, **When** latency exceeds threshold, **Then** alert is generated

---

### Edge Cases

- What happens when both primary and secondary sources are unavailable? → Display last-known-good data with prominent staleness warning, alert operations team
- What happens when source returns malformed data? → Log error, skip bad data, continue with valid data from other sources
- What happens when network connectivity is intermittent? → Implement retry with exponential backoff, report partial success
- What happens during market close hours? → Reduce collection frequency, don't alert on expected staleness

## Requirements

### Functional Requirements

- **FR-001**: System MUST collect market sentiment data on a recurring schedule during market hours
- **FR-002**: System MUST support multiple data sources with automatic failover when primary source fails
- **FR-003**: System MUST deduplicate news items to prevent reprocessing identical content
- **FR-004**: System MUST notify dependent systems when new data is available
- **FR-005**: System MUST record source attribution for each collected data point
- **FR-006**: System MUST calculate and store confidence scores for each sentiment value
- **FR-007**: System MUST provide operational metrics for monitoring collection health
- **FR-008**: System MUST alert operations team when 3 consecutive collection failures occur within 15 minutes

### Anti-Goals (Explicit Non-Requirements)

- **AG-001**: Real-time streaming is NOT required (batch intervals of 5 minutes are acceptable)
- **AG-002**: Historical backfilling is NOT required (system only collects forward-looking data)
- **AG-003**: Source-specific API rate limit handling is NOT in scope (handled at infrastructure level)
- **AG-004**: User-configurable data sources is NOT required (sources are system-configured)

### Key Entities

- **News Item**: A piece of market news with headline, content, publication time, and source. Uniquely identified by composite key: (headline + source + publication date)
- **Sentiment Score**: A numerical sentiment value (-1.0 to 1.0) with confidence (0.0 to 1.0) and label (positive/neutral/negative)
- **Collection Event**: A record of data collection attempt with timestamp, source, success/failure, and item count
- **Data Source**: A provider of market news with availability status and priority ranking. Failure is detected by: HTTP error (4xx/5xx), request timeout (>10 seconds), or empty/malformed response body (even with 200 OK)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Data freshness remains under 15 minutes during market hours (9:30 AM - 4:00 PM ET)
- **SC-002**: Source failover completes within 30 seconds of primary source failure
- **SC-003**: Zero duplicate news items are processed per day
- **SC-004**: 99.5% collection success rate during market hours
- **SC-005**: Dependent systems receive new data notifications within 30 seconds of storage
- **SC-006**: Operations team receives alerts within 5 minutes of collection failure threshold breach

### User Satisfaction Metrics

- **SC-007**: Analysts report 90%+ confidence in data freshness
- **SC-008**: Manual verification time reduced from 30+ minutes to under 5 minutes daily

## Assumptions

- Market hours are US Eastern Time (9:30 AM - 4:00 PM ET)
- Primary and secondary data sources are pre-configured by system administrators
- Budget limit of $50/month for data source subscriptions
- No PII (Personally Identifiable Information) exists in collected market news data
- Existing dashboard infrastructure will display collected data (no UI redesign required)

## Clarifications

### Session 2025-12-09

- Q: What makes two news items "identical" for deduplication? → A: Headline + source + publication date (composite key)
- Q: What threshold triggers an operations alert for collection failures? → A: 3 consecutive failures within 15 minutes
- Q: How is data source failure detected? → A: HTTP error (4xx/5xx), request timeout (>10 seconds), OR empty/malformed response body (even with 200 OK)

## Open Questions

- Should sentiment be recalculated when the sentiment model is updated? (Assumption: No, historical data retains original scores)
- What is acceptable data staleness outside market hours? (Assumption: 1 hour is acceptable)
