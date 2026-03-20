# Data Model: Real Sentiment Pipeline

## Entities

### Sentiment Timeseries Record (EXISTING — no changes)

Table: `{env}-sentiment-timeseries`

| Field | Type | Description |
|-------|------|-------------|
| PK | String | `{ticker}#{resolution}` (e.g., `AAPL#24h`) |
| SK | String | ISO 8601 timestamp (e.g., `2025-12-20T00:00:00+00:00`) |
| avg | Number | Average sentiment score for the bucket (-1 to +1) |
| sum | Number | Sum of scores (for re-aggregation) |
| count | Number | Number of articles/sources contributing to this bucket |
| open | Number | First score in the bucket period |
| close | Number | Last score in the bucket period |
| sources | List[String] | Source identifiers (e.g., `["tiingo:91120376"]`) |
| is_partial | Boolean | True if bucket is still accumulating data (current period) |
| original_timestamp | String | ISO 8601 timestamp of the original data point |
| ttl | Number | Unix epoch for DynamoDB TTL expiration |

**Access Patterns:**
- Query by ticker + date range: PK = `{ticker}#24h`, SK BETWEEN `{start}` AND `{end}`
- No GSIs needed — primary key + sort key range query covers all use cases

### Sentiment History Response (endpoint output — matches existing contract)

| Field | Type | Description |
|-------|------|-------------|
| ticker | String | Queried ticker symbol |
| source | String | Source filter: `aggregated`, `tiingo`, `finnhub`, `our_model` |
| history | List[SentimentPoint] | Time-series data points |
| start_date | String | Start of queried range |
| end_date | String | End of queried range |
| count | Number | Number of data points returned |

### SentimentPoint (individual data point — matches existing contract)

| Field | Type | Description |
|-------|------|-------------|
| date | String | ISO date (YYYY-MM-DD) |
| score | Number | Sentiment score (-1.0 to +1.0) |
| source | String | Data source name |
| confidence | Number | Confidence level (0.0 to 1.0) |
| label | String | `positive`, `neutral`, or `negative` |

**Mapping: DynamoDB record → SentimentPoint:**
- `date` ← SK (truncated to date)
- `score` ← `avg`
- `source` ← derived from `sources` list. **IMPORTANT**: `sources` stores `{provider}:{article_id}` format (e.g., `tiingo:91120376`). Extract the prefix before `:` for source attribution. Source filter must use prefix matching.
- `confidence` ← default 0.8 (existing data has `count: 1` for all records, making count-based derivation uninformative)
- `label` ← derived from `score` (>= 0.33 = positive, <= -0.33 = negative, else neutral)

**Data Quality Observations (from existing 678 records):**
- Score range: 0.87 to 1.00 (all highly positive, narrow range). This is the real output of DistilBERT on financial news — not a bug, but the sentiment chart will show a nearly flat line at the top of the range.
- All records are Tiingo-only. No Finnhub sentiment data exists. The `aggregated` and `finnhub` source filters return the same as `tiingo` until multi-source ingestion is implemented.
- All records have `count: 1` (one article per bucket).

### Sentiment In-Memory Cache (NEW)

| Field | Type | Description |
|-------|------|-------------|
| key | String | `{ticker}:{source}:{start_date}:{end_date}` |
| value | SentimentHistoryResponse | Cached response |
| cached_at | Number | Epoch timestamp when cached |
| ttl_ms | Number | Jittered TTL (5 min ± 10% = 270,000-330,000ms) |

**CacheStats registration:** Name = `sentiment_history`, registered with global `CacheMetricEmitter`.
