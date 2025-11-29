# Data Model: E2E Validation Suite

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28

## Overview

This document defines the data models used by the E2E test suite. These are test-specific entities (not production data models) that support test execution, data isolation, and synthetic data generation.

---

## Test Entities

### TestRun

Represents a single E2E test suite execution. Used for data isolation and cleanup.

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | str | Unique identifier (UUID hex prefix, e.g., `e2e-a1b2c3d4`) |
| `started_at` | datetime | Test run start timestamp |
| `environment` | str | Target environment (`preprod`) |
| `branch` | str | Git branch being tested |
| `commit_sha` | str | Git commit SHA |
| `workflow_run_id` | str | GitHub Actions run ID |

**Lifecycle**: Created at test session start, used for all test data prefixing.

---

### TestContext

Shared state across test cases within a test run. Passed via pytest fixtures.

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | str | Reference to TestRun |
| `base_url` | str | Preprod API base URL |
| `anonymous_user_id` | str | Current anonymous session ID |
| `access_token` | str | Current authenticated user's access token |
| `refresh_token` | str | Current authenticated user's refresh token |
| `config_ids` | list[str] | Created configuration IDs for cleanup |
| `alert_ids` | list[str] | Created alert IDs for cleanup |
| `created_users` | list[str] | Created user IDs for cleanup |

**Lifecycle**: Scoped to test session, mutated during test execution, cleared during cleanup.

---

### SyntheticUser

Test user with predictable, unique credentials.

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | str | UUID for the user |
| `email` | str | Format: `{run_id}-{index}@test.sentiment-analyzer.local` |
| `auth_type` | enum | `anonymous`, `email`, `google`, `github` |
| `created_at` | datetime | Creation timestamp |

**Uniqueness**: Email is unique per test run via run_id prefix.

---

### SyntheticTicker

Fake ticker symbol for testing. Uses reserved test ticker names that don't conflict with real symbols.

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | str | Test symbol (e.g., `TEST1`, `TEST2`, `FAKE1`) |
| `name` | str | Company name (e.g., `Test Company One`) |
| `exchange` | str | Exchange (e.g., `TEST`) |
| `is_valid` | bool | Whether validation should pass |
| `is_delisted` | bool | Whether symbol appears delisted |
| `successor` | str | Successor symbol if delisted |

**Reserved Symbols**:
- `TEST1` - `TEST5`: Valid test tickers
- `INVALID1` - `INVALID5`: Invalid test tickers
- `DELIST1`: Delisted ticker with successor `NEWTEST1`

---

### SyntheticSentiment

Generated sentiment data with configurable scores for test oracle pattern.

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | str | Ticker symbol |
| `source` | enum | `tiingo`, `finnhub`, `our_model` |
| `score` | float | Sentiment score (-1.0 to 1.0) |
| `label` | enum | `positive`, `neutral`, `negative` |
| `confidence` | float | Confidence score (0.0 to 1.0) |
| `timestamp` | datetime | Data timestamp |
| `seed` | int | Random seed used for generation |

**Label Derivation**:
- `score >= 0.33` → `positive`
- `score <= -0.33` → `negative`
- Otherwise → `neutral`

---

### SyntheticOHLC

Generated price data for ATR (Average True Range) calculation testing.

| Field | Type | Description |
|-------|------|-------------|
| `ticker` | str | Ticker symbol |
| `date` | date | Trading date |
| `open` | float | Opening price |
| `high` | float | High price |
| `low` | float | Low price |
| `close` | float | Closing price |
| `volume` | int | Trading volume |
| `seed` | int | Random seed used for generation |

**ATR Calculation**:
- True Range = max(high - low, |high - prev_close|, |low - prev_close|)
- ATR = SMA(True Range, 14)

---

### SyntheticNewsArticle

Generated news article for Tiingo mock responses.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Article ID (format: `test-{seed}-{ticker}-{index}`) |
| `title` | str | Article headline |
| `description` | str | Article summary |
| `published_date` | datetime | Publication timestamp |
| `source` | str | News source name |
| `tickers` | list[str] | Related ticker symbols |
| `url` | str | Article URL |
| `crawl_date` | datetime | When article was crawled |
| `_expected_sentiment` | float | Pre-computed sentiment for test oracle |

---

### SyntheticEmailEvent

Generated SendGrid email event for notification testing.

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | str | SendGrid message ID |
| `event_type` | enum | `processed`, `delivered`, `opened`, `clicked`, `bounced` |
| `email` | str | Recipient email |
| `timestamp` | datetime | Event timestamp |
| `user_agent` | str | User agent (for opened/clicked) |
| `ip` | str | IP address (for opened/clicked) |

---

## DynamoDB Key Patterns (Test Data)

Test data follows the same key patterns as production but with prefixed values for isolation.

| Entity | PK Pattern | SK Pattern |
|--------|------------|------------|
| Test User | `USER#{run_id}-{user_id}` | `PROFILE` |
| Test Config | `USER#{run_id}-{user_id}` | `CONFIG#{config_id}` |
| Test Alert | `CONFIG#{config_id}` | `ALERT#{alert_id}` |
| Test Notification | `USER#{run_id}-{user_id}` | `NOTIF#{timestamp}#{id}` |

**Cleanup Query**: Scan with `begins_with(pk, 'USER#e2e-{run_id}')` to find all test data.

---

## Synthetic Data Generation

### Deterministic Seeding

All synthetic data uses deterministic seeding for reproducibility:

```python
def generate_synthetic_data(seed: int) -> SyntheticDataSet:
    """Generate full synthetic dataset from seed."""
    random.seed(seed)

    users = [SyntheticUser(...) for _ in range(5)]
    tickers = [SyntheticTicker(...) for _ in range(10)]
    sentiment = [SyntheticSentiment(...) for t in tickers for s in SOURCES]
    ohlc = [SyntheticOHLC(...) for t in tickers for d in DATE_RANGE]
    news = [SyntheticNewsArticle(...) for t in tickers]

    return SyntheticDataSet(users, tickers, sentiment, ohlc, news)
```

### Test Oracle Pattern

Expected values are computed from the same synthetic data:

```python
def compute_expected_sentiment(synthetic_data: SyntheticDataSet, ticker: str) -> dict:
    """Compute expected API response from synthetic inputs."""
    tiingo_articles = [a for a in synthetic_data.news if ticker in a.tickers]
    expected_score = mean([a._expected_sentiment for a in tiingo_articles])
    return {
        "ticker": ticker,
        "sentiment": {
            "tiingo": {"score": expected_score, "label": score_to_label(expected_score)}
        }
    }
```

---

## State Transitions

### TestRun Lifecycle

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CREATED    │────▶│  RUNNING    │────▶│  COMPLETED  │     │   FAILED    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           │                   ▼                   ▼
                           │            ┌─────────────┐     ┌─────────────┐
                           └───────────▶│  CLEANUP    │◀────│  CLEANUP    │
                                        └─────────────┘     └─────────────┘
```

### Test User Auth State

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ANONYMOUS  │────▶│  UPGRADING  │────▶│AUTHENTICATED│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   FAILED    │
                    └─────────────┘
```

---

## Data Cleanup Rules

1. **Session-scoped cleanup**: All test data cleaned up at end of pytest session
2. **Prefix-based identification**: All test data has `run_id` prefix
3. **Orphan detection**: Daily job queries for stale `e2e-*` prefixed data older than 24h
4. **Cleanup order**: Alerts → Configs → Users (respect foreign key semantics)
5. **Failure tolerance**: Cleanup continues on individual item failures, logs errors
