# Feature Specification: OHLC & Sentiment History E2E Test Suite

**Feature Branch**: `012-ohlc-sentiment-e2e-tests`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "Comprehensive integration and E2E tests for OHLC and sentiment history endpoints. Cover all happy paths, exhaust error cases assuming erratic data sources, and exhaust edge cases including off-by-1, data outside expected bounds, inconsistent data, and out-of-order data."

## Overview

This specification defines a comprehensive test suite for the OHLC price data and sentiment history endpoints introduced in Feature 011 (Price-Sentiment Overlay). The test suite must validate system behavior under normal conditions, erratic data source behavior, and edge cases that could cause production failures.

### Endpoints Under Test

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/tickers/{ticker}/ohlc` | GET | Historical OHLC candlestick data |
| `/api/v2/tickers/{ticker}/sentiment/history` | GET | Historical sentiment scores |

### Data Sources

| Source | Role | Known Failure Modes |
|--------|------|---------------------|
| Tiingo | Primary OHLC | Rate limits (500/month), timeouts, malformed JSON, missing fields |
| Finnhub | Fallback OHLC | Rate limits (60/min), timeouts, data gaps, different field names |
| DynamoDB | Sentiment storage | Throttling, eventual consistency, missing partitions |

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OHLC Happy Path Validation (Priority: P1)

QA engineers need to verify that the OHLC endpoint returns correct, well-formed data for all supported parameter combinations under normal operating conditions.

**Why this priority**: OHLC data is the foundation of the price-sentiment overlay chart. Any defect here renders the entire feature unusable.

**Independent Test**: Can be fully tested by calling the OHLC endpoint with various valid parameters and verifying response structure, data integrity, and contract compliance.

**Acceptance Scenarios**:

1. **Given** a valid ticker (AAPL) and default parameters, **When** GET /ohlc is called, **Then** response contains candles array sorted oldest-first with all required fields (date, open, high, low, close)

2. **Given** a valid ticker and range=1W, **When** GET /ohlc is called, **Then** response contains approximately 5-7 trading days of data

3. **Given** a valid ticker and range=1M, **When** GET /ohlc is called, **Then** response contains approximately 20-23 trading days of data

4. **Given** a valid ticker and range=3M, **When** GET /ohlc is called, **Then** response contains approximately 60-66 trading days of data

5. **Given** a valid ticker and range=6M, **When** GET /ohlc is called, **Then** response contains approximately 120-132 trading days of data

6. **Given** a valid ticker and range=1Y, **When** GET /ohlc is called, **Then** response contains approximately 250-260 trading days of data

7. **Given** a valid ticker with custom start_date and end_date, **When** GET /ohlc is called, **Then** response contains candles within the specified date range

8. **Given** a lowercase ticker (aapl), **When** GET /ohlc is called, **Then** response normalizes ticker to uppercase (AAPL)

9. **Given** a valid request, **When** GET /ohlc is called, **Then** response includes cache_expires_at field indicating next market open

10. **Given** Tiingo returns valid data, **When** GET /ohlc is called, **Then** response source field is "tiingo"

11. **Given** Tiingo fails but Finnhub succeeds, **When** GET /ohlc is called, **Then** response source field is "finnhub" and data is valid

12. **Given** a valid response, **When** checking count field, **Then** count exactly equals length of candles array

13. **Given** a valid response, **When** checking start_date field, **Then** start_date equals the date of the first candle

14. **Given** a valid response, **When** checking end_date field, **Then** end_date equals the date of the last candle

---

### User Story 2 - Sentiment History Happy Path Validation (Priority: P1)

QA engineers need to verify that the sentiment history endpoint returns correct, well-formed data for all supported parameter combinations under normal operating conditions.

**Why this priority**: Sentiment data is essential for the overlay chart. Defects here break the core user value proposition.

**Independent Test**: Can be fully tested by calling the sentiment history endpoint with various valid parameters and verifying response structure, data ranges, and label consistency.

**Acceptance Scenarios**:

1. **Given** a valid ticker (AAPL) and default parameters, **When** GET /sentiment/history is called, **Then** response contains history array with all required fields (date, score, source)

2. **Given** a valid ticker and source=tiingo, **When** GET /sentiment/history is called, **Then** all history points have source="tiingo"

3. **Given** a valid ticker and source=finnhub, **When** GET /sentiment/history is called, **Then** all history points have source="finnhub"

4. **Given** a valid ticker and source=our_model, **When** GET /sentiment/history is called, **Then** all history points have source="our_model"

5. **Given** a valid ticker and source=aggregated (default), **When** GET /sentiment/history is called, **Then** all history points have source="aggregated"

6. **Given** a valid ticker and range=1W, **When** GET /sentiment/history is called, **Then** response contains exactly 8 days of data (includes weekends)

7. **Given** a valid ticker and range=1M, **When** GET /sentiment/history is called, **Then** response contains exactly 31 days of data

8. **Given** a valid ticker with custom start_date and end_date, **When** GET /sentiment/history is called, **Then** response contains history within the specified date range

9. **Given** a lowercase ticker (msft), **When** GET /sentiment/history is called, **Then** response normalizes ticker to uppercase (MSFT)

10. **Given** any valid request, **When** GET /sentiment/history is called, **Then** all scores are within [-1.0, 1.0] range inclusive

11. **Given** any valid request, **When** GET /sentiment/history is called, **Then** all confidence values (if present) are within [0.0, 1.0] range inclusive

12. **Given** any valid request, **When** GET /sentiment/history is called, **Then** all labels are one of: "positive", "neutral", "negative"

13. **Given** a score >= 0.33, **When** checking label, **Then** label is "positive"

14. **Given** a score <= -0.33, **When** checking label, **Then** label is "negative"

15. **Given** a score between -0.33 and 0.33 exclusive, **When** checking label, **Then** label is "neutral"

16. **Given** a valid response, **When** checking count field, **Then** count exactly equals length of history array

---

### User Story 3 - Data Source Error Resilience (Priority: P1)

System operators need confidence that the endpoints gracefully handle erratic behavior from external data sources including network failures, malformed responses, rate limiting, and partial data.

**Why this priority**: External APIs are inherently unreliable. Production stability depends on robust error handling.

**Independent Test**: Can be fully tested by injecting various failure modes into mock adapters and verifying appropriate error responses or fallback behavior.

**Acceptance Scenarios - Network Failures**:

1. **Given** Tiingo returns HTTP 500, **When** GET /ohlc is called, **Then** system falls back to Finnhub

2. **Given** Tiingo returns HTTP 502 (Bad Gateway), **When** GET /ohlc is called, **Then** system falls back to Finnhub

3. **Given** Tiingo returns HTTP 503 (Service Unavailable), **When** GET /ohlc is called, **Then** system falls back to Finnhub

4. **Given** Tiingo returns HTTP 504 (Gateway Timeout), **When** GET /ohlc is called, **Then** system falls back to Finnhub

5. **Given** Tiingo connection times out (>30s), **When** GET /ohlc is called, **Then** system falls back to Finnhub within reasonable time

6. **Given** Tiingo connection is refused, **When** GET /ohlc is called, **Then** system falls back to Finnhub

7. **Given** Tiingo DNS resolution fails, **When** GET /ohlc is called, **Then** system falls back to Finnhub

8. **Given** both Tiingo and Finnhub return HTTP 500, **When** GET /ohlc is called, **Then** response is HTTP 404 with message "No price data available"

9. **Given** both Tiingo and Finnhub timeout, **When** GET /ohlc is called, **Then** response is HTTP 404 within acceptable time limit (<90s)

**Acceptance Scenarios - Rate Limiting**:

10. **Given** Tiingo returns HTTP 429 (Too Many Requests), **When** GET /ohlc is called, **Then** system falls back to Finnhub

11. **Given** Finnhub returns HTTP 429 after Tiingo failure, **When** GET /ohlc is called, **Then** response is HTTP 404 (no retry flood)

12. **Given** Tiingo returns HTTP 429 with Retry-After header, **When** checking logs, **Then** rate limit event is logged with retry delay

**Acceptance Scenarios - Malformed Responses**:

13. **Given** Tiingo returns invalid JSON (syntax error), **When** GET /ohlc is called, **Then** system falls back to Finnhub

14. **Given** Tiingo returns empty JSON object {}, **When** GET /ohlc is called, **Then** system falls back to Finnhub

15. **Given** Tiingo returns empty array [], **When** GET /ohlc is called, **Then** system falls back to Finnhub

16. **Given** Tiingo returns HTML error page instead of JSON, **When** GET /ohlc is called, **Then** system falls back to Finnhub

17. **Given** Tiingo returns truncated JSON (incomplete), **When** GET /ohlc is called, **Then** system falls back to Finnhub

18. **Given** Tiingo returns JSON with unexpected structure, **When** GET /ohlc is called, **Then** system falls back to Finnhub

19. **Given** Tiingo returns JSON with extra unexpected fields, **When** GET /ohlc is called, **Then** extra fields are ignored, valid data processed

**Acceptance Scenarios - Missing/Invalid Fields**:

20. **Given** Tiingo returns candles missing "open" field, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

21. **Given** Tiingo returns candles missing "close" field, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

22. **Given** Tiingo returns candles missing "high" field, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

23. **Given** Tiingo returns candles missing "low" field, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

24. **Given** Tiingo returns candles missing "date" field, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

25. **Given** Tiingo returns candles with null price values, **When** GET /ohlc is called, **Then** those candles are skipped or system falls back

26. **Given** Tiingo returns candles with string price values ("123.45"), **When** GET /ohlc is called, **Then** values are coerced or candles skipped

27. **Given** Tiingo returns candles with negative prices, **When** GET /ohlc is called, **Then** those candles are rejected (invalid market data)

28. **Given** Tiingo returns candles with zero prices, **When** GET /ohlc is called, **Then** those candles are rejected (invalid market data)

29. **Given** Tiingo returns candles with NaN prices, **When** GET /ohlc is called, **Then** those candles are rejected

30. **Given** Tiingo returns candles with Infinity prices, **When** GET /ohlc is called, **Then** those candles are rejected

---

### User Story 4 - Edge Case Boundary Testing (Priority: P1)

QA engineers need to verify system behavior at boundary conditions where off-by-one errors, data inconsistencies, and unexpected input could cause failures.

**Why this priority**: Edge cases are the most common source of production bugs. Exhaustive boundary testing prevents customer-facing failures.

**Independent Test**: Can be fully tested by constructing specific boundary inputs and verifying correct handling.

**Acceptance Scenarios - Date Range Boundaries**:

1. **Given** start_date equals end_date (single day), **When** GET /ohlc is called, **Then** response contains 0-1 candles for that day

2. **Given** start_date is yesterday and end_date is today, **When** GET /ohlc is called, **Then** response contains 1-2 candles

3. **Given** end_date is today (market not yet closed), **When** GET /ohlc is called, **Then** response may or may not include today's partial candle

4. **Given** end_date is tomorrow (future), **When** GET /ohlc is called, **Then** response contains data up to most recent available date

5. **Given** end_date is 1 year in future, **When** GET /ohlc is called, **Then** response contains data up to most recent available date

6. **Given** start_date is before ticker IPO (e.g., AAPL before 1980), **When** GET /ohlc is called, **Then** response contains data from earliest available date

7. **Given** start_date is 1800-01-01, **When** GET /ohlc is called, **Then** response contains data from earliest available date or HTTP 404

8. **Given** start_date is after end_date, **When** GET /ohlc is called, **Then** response is HTTP 400 with message "start_date must be before end_date"

9. **Given** start_date equals end_date for sentiment, **When** GET /sentiment/history is called, **Then** response contains exactly 1 data point

10. **Given** only start_date provided (no end_date), **When** GET /ohlc is called, **Then** end_date defaults to today

11. **Given** only end_date provided (no start_date), **When** GET /ohlc is called, **Then** request uses range parameter or defaults

**Acceptance Scenarios - Ticker Symbol Boundaries**:

12. **Given** ticker is exactly 1 character (A), **When** GET /ohlc is called, **Then** request is processed (valid ticker length)

13. **Given** ticker is exactly 5 characters (GOOGL), **When** GET /ohlc is called, **Then** request is processed (valid ticker length)

14. **Given** ticker is 6 characters (GOOGLE), **When** GET /ohlc is called, **Then** response is HTTP 400

15. **Given** ticker is empty string, **When** GET /ohlc is called, **Then** response is HTTP 400 or 404

16. **Given** ticker contains digits (ABC1), **When** GET /ohlc is called, **Then** response is HTTP 400

17. **Given** ticker contains hyphen (AB-C), **When** GET /ohlc is called, **Then** response is HTTP 400

18. **Given** ticker contains period (BRK.A), **When** GET /ohlc is called, **Then** response is HTTP 400 (current validation requires alpha only)

19. **Given** ticker contains underscore (AB_C), **When** GET /ohlc is called, **Then** response is HTTP 400

20. **Given** ticker contains space (AB C), **When** GET /ohlc is called, **Then** response is HTTP 400

21. **Given** ticker has leading whitespace ( AAPL), **When** GET /ohlc is called, **Then** ticker is trimmed and processed

22. **Given** ticker has trailing whitespace (AAPL ), **When** GET /ohlc is called, **Then** ticker is trimmed and processed

23. **Given** ticker has mixed case (AaPl), **When** GET /ohlc is called, **Then** ticker is normalized to AAPL

24. **Given** ticker is valid but unknown/delisted (ZZZZ), **When** GET /ohlc is called, **Then** response is HTTP 404

25. **Given** ticker is unicode characters (ΑΑΑΑ - Greek), **When** GET /ohlc is called, **Then** response is HTTP 400

**Acceptance Scenarios - Price Data Boundaries**:

26. **Given** candle has high < low (impossible), **When** processing response, **Then** candle is rejected as invalid

27. **Given** candle has close > high, **When** processing response, **Then** candle is rejected as invalid

28. **Given** candle has close < low, **When** processing response, **Then** candle is rejected as invalid

29. **Given** candle has open > high, **When** processing response, **Then** candle is rejected as invalid

30. **Given** candle has open < low, **When** processing response, **Then** candle is rejected as invalid

31. **Given** candle has high = low = open = close (doji), **When** processing response, **Then** candle is accepted (valid pattern)

32. **Given** candle has extremely high price (>1,000,000), **When** processing response, **Then** candle is accepted (BRK.A is ~$600k)

33. **Given** candle has extremely low price (0.0001), **When** processing response, **Then** candle is accepted (penny stocks)

34. **Given** candle has price = 0.00, **When** processing response, **Then** candle is rejected (zero price invalid)

35. **Given** candle has volume = 0, **When** processing response, **Then** candle is accepted (low liquidity days)

36. **Given** candle has negative volume (-1000), **When** processing response, **Then** candle is rejected as invalid

37. **Given** candle has volume exceeding MAX_INT, **When** processing response, **Then** handled gracefully (no overflow)

**Acceptance Scenarios - Sentiment Score Boundaries**:

38. **Given** sentiment score is exactly -1.0, **When** checking validation, **Then** score is accepted

39. **Given** sentiment score is exactly 1.0, **When** checking validation, **Then** score is accepted

40. **Given** sentiment score is exactly 0.0, **When** checking validation, **Then** score is accepted

41. **Given** sentiment score is -1.0000001, **When** checking validation, **Then** score is rejected (below minimum)

42. **Given** sentiment score is 1.0000001, **When** checking validation, **Then** score is rejected (above maximum)

43. **Given** sentiment score is exactly 0.33, **When** checking label, **Then** label is "positive" (boundary)

44. **Given** sentiment score is exactly -0.33, **When** checking label, **Then** label is "negative" (boundary)

45. **Given** sentiment score is 0.3299999, **When** checking label, **Then** label is "neutral" (just below)

46. **Given** sentiment score is -0.3299999, **When** checking label, **Then** label is "neutral" (just above)

47. **Given** sentiment score is 0.330001, **When** checking label, **Then** label is "positive" (just above)

48. **Given** sentiment score is -0.330001, **When** checking label, **Then** label is "negative" (just below)

49. **Given** confidence is exactly 0.0, **When** checking validation, **Then** confidence is accepted

50. **Given** confidence is exactly 1.0, **When** checking validation, **Then** confidence is accepted

51. **Given** confidence is -0.0001, **When** checking validation, **Then** confidence is rejected

52. **Given** confidence is 1.0001, **When** checking validation, **Then** confidence is rejected

---

### User Story 5 - Data Consistency and Ordering (Priority: P1)

QA engineers need to verify that data is returned in correct order and maintains internal consistency even when source data is inconsistent.

**Why this priority**: Chart rendering depends on correctly ordered data. Inconsistent data causes visual artifacts and user confusion.

**Independent Test**: Can be fully tested by injecting out-of-order or inconsistent mock data and verifying response normalization.

**Acceptance Scenarios - Data Ordering**:

1. **Given** Tiingo returns candles in random order, **When** GET /ohlc is called, **Then** response candles are sorted by date ascending (oldest first)

2. **Given** Tiingo returns candles in descending order (newest first), **When** GET /ohlc is called, **Then** response candles are sorted by date ascending

3. **Given** Tiingo returns duplicate dates with different prices, **When** GET /ohlc is called, **Then** duplicates are deduplicated consistently

4. **Given** Tiingo returns duplicate dates with identical data, **When** GET /ohlc is called, **Then** duplicates are removed

5. **Given** sentiment history is generated, **When** GET /sentiment/history is called, **Then** history is sorted by date ascending

**Acceptance Scenarios - Data Gaps**:

6. **Given** Tiingo returns data with missing trading days (gaps), **When** GET /ohlc is called, **Then** response reflects actual available data (gaps preserved)

7. **Given** a market holiday falls within requested range, **When** GET /ohlc is called, **Then** holiday has no candle

8. **Given** weekend days (Sat/Sun) fall within requested range, **When** GET /ohlc is called, **Then** weekend days have no candles

9. **Given** sentiment request spans a weekend, **When** GET /sentiment/history is called, **Then** weekend days ARE included (sentiment exists all days)

10. **Given** Tiingo returns only every other day of data, **When** GET /ohlc is called, **Then** response contains only the days actually returned

**Acceptance Scenarios - Date Field Consistency**:

11. **Given** price data starts later than requested start_date, **When** GET /ohlc is called, **Then** response start_date equals first candle date

12. **Given** price data ends earlier than requested end_date, **When** GET /ohlc is called, **Then** response end_date equals last candle date

13. **Given** price and sentiment requested for same date range, **When** both endpoints called, **Then** sentiment has more points (includes weekends)

14. **Given** candles array is non-empty, **When** checking start_date, **Then** start_date equals candles[0].date

15. **Given** candles array is non-empty, **When** checking end_date, **Then** end_date equals candles[candles.length-1].date

**Acceptance Scenarios - Count Field Consistency**:

16. **Given** any valid OHLC response, **When** checking count, **Then** count === candles.length

17. **Given** any valid sentiment response, **When** checking count, **Then** count === history.length

18. **Given** OHLC query returns zero candles, **When** checking response, **Then** HTTP 404 is returned (not empty 200)

19. **Given** sentiment query returns zero history, **When** checking response, **Then** HTTP 404 is returned (not empty 200)

---

### User Story 6 - Authentication and Security (Priority: P1)

QA engineers need to verify that endpoints correctly enforce authentication requirements and handle security edge cases.

**Why this priority**: Security requirements are non-negotiable. Authentication bypasses must be detected.

**Independent Test**: Can be fully tested by calling endpoints with various authentication states and verifying correct rejection or acceptance.

**Acceptance Scenarios - Missing Authentication**:

1. **Given** request has no X-User-ID header, **When** GET /ohlc is called, **Then** response is HTTP 401 with message "Missing user identification"

2. **Given** request has no X-User-ID header, **When** GET /sentiment/history is called, **Then** response is HTTP 401 with message "Missing user identification"

3. **Given** request has X-User-ID header with empty string value, **When** GET /ohlc is called, **Then** response is HTTP 401

4. **Given** request has X-User-ID header with only whitespace, **When** GET /ohlc is called, **Then** response is HTTP 401

**Acceptance Scenarios - Valid Authentication**:

5. **Given** request has valid X-User-ID header (UUID format), **When** GET /ohlc is called, **Then** response is HTTP 200

6. **Given** request has valid X-User-ID header (simple string), **When** GET /ohlc is called, **Then** response is HTTP 200

**Acceptance Scenarios - Edge Cases**:

7. **Given** X-User-ID is extremely long (10000 chars), **When** GET /ohlc is called, **Then** request is handled gracefully (no crash)

8. **Given** X-User-ID contains special characters (!@#$%), **When** GET /ohlc is called, **Then** request is processed without injection

9. **Given** X-User-ID contains SQL injection attempt, **When** GET /ohlc is called, **Then** no SQL injection occurs

10. **Given** X-User-ID contains XSS attempt, **When** GET /ohlc is called, **Then** no XSS in response

11. **Given** X-User-ID contains null byte (\x00), **When** GET /ohlc is called, **Then** request handled safely

12. **Given** X-User-ID contains newlines, **When** GET /ohlc is called, **Then** no log injection occurs

---

### User Story 7 - E2E Preprod Validation (Priority: P2)

Operations team needs to verify that endpoints work correctly against real preprod infrastructure with actual external API integrations.

**Why this priority**: Integration tests with mocks cannot catch all real-world issues. E2E validates the complete system.

**Independent Test**: Can be fully tested by running against preprod environment and verifying real data retrieval.

**Acceptance Scenarios - Basic Functionality**:

1. **Given** preprod environment is available, **When** GET /ohlc for AAPL, **Then** real Tiingo/Finnhub data is returned within 5 seconds

2. **Given** preprod environment is available, **When** GET /ohlc for MSFT, **Then** real data is returned with valid OHLC structure

3. **Given** preprod environment is available, **When** GET /sentiment/history for AAPL, **Then** sentiment data is returned within 3 seconds

4. **Given** preprod environment is available, **When** GET /sentiment/history for GOOGL, **Then** sentiment data is returned with valid structure

**Acceptance Scenarios - Data Validation**:

5. **Given** real OHLC data is returned, **When** validating candles, **Then** all prices are positive

6. **Given** real OHLC data is returned, **When** validating candles, **Then** high >= low for all candles

7. **Given** real OHLC data is returned, **When** validating candles, **Then** open and close are between low and high

8. **Given** real OHLC data is returned, **When** checking dates, **Then** most recent candle is within 3 trading days

9. **Given** real sentiment data is returned, **When** validating scores, **Then** all scores are within [-1, 1]

**Acceptance Scenarios - Performance**:

10. **Given** 10 concurrent requests for different tickers, **When** all sent simultaneously, **Then** all complete within 15 seconds

11. **Given** repeated requests for same ticker within 1 minute, **When** second request made, **Then** response is faster (cache hit)

12. **Given** preprod under normal load, **When** GET /ohlc is called, **Then** response latency is under 2 seconds (p95)

**Acceptance Scenarios - Fallback Verification**:

13. **Given** preprod with Tiingo returning data, **When** GET /ohlc called, **Then** source is "tiingo"

14. **Given** request for obscure ticker Tiingo doesn't have, **When** GET /ohlc called, **Then** Finnhub fallback is attempted

---

### Edge Cases

**Date/Time Edge Cases**:
- What happens when requesting data for a date before the ticker existed?
- What happens when requesting data spanning a stock split or reverse split?
- What happens on a market half-day (early close like July 3rd)?
- What happens for a ticker that was recently delisted?
- What happens during market pre-open (4am-9:30am ET)?
- What happens at exactly market open (9:30:00.000 ET)?
- What happens at exactly market close (4:00:00.000 ET)?
- What happens during daylight saving time transitions?

**Data Source Edge Cases**:
- What happens when Tiingo and Finnhub return different prices for the same date?
- What happens when data source returns prices in different currencies?
- What happens when data source returns adjusted vs. unadjusted prices?
- What happens when adapter cache expires mid-request?
- What happens when API key is expired/revoked?
- What happens when API returns different timezone than expected?

**Concurrency Edge Cases**:
- What happens when cache is being written while another request reads?
- What happens when rate limit resets during request processing?
- What happens when two requests trigger fallback simultaneously?
- What happens with 100 concurrent requests for same ticker?
- What happens when Lambda cold start occurs mid-batch?

**Precision Edge Cases**:
- What happens with floating-point precision for prices like $0.0001?
- What happens with very large prices exceeding float32 precision?
- What happens when sentiment scores have 10+ decimal places?
- What happens when date has millisecond precision vs. day precision?

**Data Integrity Edge Cases**:
- What happens when candle count doesn't match actual array length?
- What happens when start_date/end_date don't match actual data range?
- What happens when source field doesn't match actual data origin?
- What happens when ticker in response doesn't match request?

---

## Requirements *(mandatory)*

### Functional Requirements

**Test Infrastructure**:
- **FR-001**: Test suite MUST support running against mocked adapters for unit/integration tests
- **FR-002**: Test suite MUST support running against real preprod endpoints for E2E tests
- **FR-003**: Test suite MUST generate detailed reports with pass/fail counts and failure details
- **FR-004**: Test suite MUST be runnable from CI/CD pipeline with exit code 0 for success, non-zero for failure
- **FR-005**: Test suite MUST complete all integration tests within 5 minutes
- **FR-006**: Test suite MUST complete all E2E tests within 10 minutes
- **FR-007**: Test suite MUST support pytest markers to run subsets (e.g., `pytest -m "integration"`)

**Mock Adapters**:
- **FR-008**: Mock adapters MUST support injecting HTTP error codes (4xx, 5xx)
- **FR-009**: Mock adapters MUST support injecting timeout scenarios
- **FR-010**: Mock adapters MUST support returning malformed JSON
- **FR-011**: Mock adapters MUST support returning empty responses
- **FR-012**: Mock adapters MUST support returning partial/invalid field data
- **FR-013**: Mock adapters MUST track call counts for verification
- **FR-014**: Mock adapters MUST simulate configurable latency

**Test Data**:
- **FR-015**: Test suite MUST use deterministic test data with seeded random for reproducibility
- **FR-016**: Test suite MUST include synthetic OHLC data generators with configurable parameters
- **FR-017**: Test suite MUST include synthetic sentiment data generators with configurable parameters
- **FR-018**: Test suite MUST validate generated test data against schema before use
- **FR-019**: Test suite MUST support parameterized tests for boundary value testing

**Coverage Requirements**:
- **FR-020**: Test suite MUST cover all HTTP status codes: 200, 400, 401, 404
- **FR-021**: Test suite MUST cover all query parameters: range, start_date, end_date, source
- **FR-022**: Test suite MUST cover all TimeRange enum values: 1W, 1M, 3M, 6M, 1Y
- **FR-023**: Test suite MUST cover all SentimentSource enum values: tiingo, finnhub, our_model, aggregated
- **FR-024**: Test suite MUST cover primary (Tiingo) and fallback (Finnhub) code paths
- **FR-025**: Test suite MUST cover cache expiration header validation

**Error Injection**:
- **FR-026**: Test suite MUST test HTTP 500, 502, 503, 504 from data sources
- **FR-027**: Test suite MUST test HTTP 429 rate limiting from data sources
- **FR-028**: Test suite MUST test connection timeout (>30s)
- **FR-029**: Test suite MUST test connection refused
- **FR-030**: Test suite MUST test DNS resolution failure
- **FR-031**: Test suite MUST test invalid JSON responses
- **FR-032**: Test suite MUST test empty responses ({}, [])
- **FR-033**: Test suite MUST test truncated/partial responses
- **FR-034**: Test suite MUST test null, NaN, Infinity field values

**Boundary Testing**:
- **FR-035**: Test suite MUST test date range edge cases (same day, adjacent days, far past, far future)
- **FR-036**: Test suite MUST test ticker length boundaries (1 char, 5 chars, 6 chars)
- **FR-037**: Test suite MUST test ticker character restrictions (alpha only, no digits/symbols)
- **FR-038**: Test suite MUST test score boundaries (-1.0, 1.0, boundary crossing at ±0.33)
- **FR-039**: Test suite MUST test confidence boundaries (0.0, 1.0)
- **FR-040**: Test suite MUST test OHLC relationship constraints (high >= low, open/close between)
- **FR-041**: Test suite MUST test data ordering (verify ascending sort)
- **FR-042**: Test suite MUST test duplicate date handling

### Key Entities

- **Test Case**: Individual test with setup, execution, assertions, and cleanup
- **Test Suite**: Collection of related test cases with shared fixtures and markers
- **Mock Adapter**: Configurable fake data source implementing real adapter interface
- **Failure Injector**: Component that configures mock adapters with specific failure modes
- **Test Oracle**: Expected result generator for synthetic data validation
- **Test Report**: Summary of execution with pass/fail/skip counts and failure details

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of integration tests pass in CI/CD pipeline consistently
- **SC-002**: >95% of E2E tests pass against preprod (allowing for external API flakiness)
- **SC-003**: Integration test suite completes in under 5 minutes
- **SC-004**: E2E test suite completes in under 10 minutes
- **SC-005**: Zero false positives - any failure indicates a real defect or documented environmental issue
- **SC-006**: 100% of acceptance scenarios from this specification have corresponding test implementations
- **SC-007**: Test suite detects at least 80% of injected defects (validated via mutation testing)
- **SC-008**: All edge cases enumerated in this specification have test coverage
- **SC-009**: Failed test reports include enough information to identify root cause without additional debugging
- **SC-010**: New test cases can be added with less than 20 lines of boilerplate code

---

## Assumptions

1. **Adapter interfaces are stable**: TiingoAdapter and FinnhubAdapter have stable public interfaces
2. **Test environment isolation**: Integration tests run in isolation without affecting production data
3. **Preprod availability**: Preprod environment is available during CI/CD runs with >99% uptime
4. **External API quotas**: Test execution uses caching to minimize API quota consumption
5. **Deterministic behavior**: Using seeded random (hash of ticker) for reproducible test data
6. **Market calendar**: Using standard NYSE trading calendar for expected trading day calculations
7. **Timezone**: All dates handled in UTC; market hours calculations use America/New_York
8. **Test data realism**: Synthetic data generators produce realistic but not real market data

---

## Out of Scope

1. Performance/load testing beyond basic concurrency verification
2. Security penetration testing and vulnerability scanning
3. Frontend chart rendering tests (separate feature)
4. Database migration and schema evolution tests
5. Infrastructure provisioning and Terraform tests
6. API versioning tests (only v2 endpoints covered)
7. OAuth/Cognito authentication flow tests (only X-User-ID header tested)
8. Billing/quota enforcement tests for external APIs
