# Implementation Plan: Real-Time Multi-Resolution Sentiment Time-Series

**Branch**: `1009-realtime-multi-resolution` | **Date**: 2025-12-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1009-realtime-multi-resolution/spec.md`

## Summary

Build a real-time multi-resolution time-series architecture that streams sentiment data at 8 resolution levels (1m to 24h) with <100ms resolution switching, shared caching across users, and automatic reconnection. Uses write fanout for pre-aggregated buckets, Lambda global scope caching, and resolution-filtered SSE streaming.

## Canonical Sources

All design decisions are traceable to authoritative sources defined in [spec.md](./spec.md#canonical-sources--citations). Key citations used in this plan:

| Pattern | Canonical Source | Reference |
|---------|------------------|-----------|
| Write fanout pre-aggregation | AWS DynamoDB Best Practices | `[CS-001]` |
| Composite key `ticker#resolution` | AWS Blog: Choosing Partition Key | `[CS-002]` |
| Time-series patterns | Rick Houlihan re:Invent 2018 | `[CS-003]` |
| Lambda global scope caching | AWS Lambda Best Practices | `[CS-005]` |
| SSE streaming patterns | MDN Server-Sent Events | `[CS-007]` |
| Time bucket alignment | Prometheus + Gorilla paper | `[CS-009, CS-010]` |
| OHLC for non-financial metrics | Netflix Tech Blog | `[CS-011]` |
| Resolution-dependent TTL | AWS DynamoDB TTL | `[CS-013, CS-014]` |

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: FastAPI, boto3, sse-starlette (existing SSE stack), pydantic
**Storage**: DynamoDB with new time-series table (`{env}-sentiment-timeseries`)
**Testing**: pytest 8.0+, moto (unit), LocalStack (integration), synthetic data for E2E
**Target Platform**: AWS Lambda with Function URLs + SSE streaming
**Project Type**: Web application (serverless backend + static frontend)
**Performance Goals**: <100ms resolution switch, <3s live update latency, 80% cache hit rate
**Constraints**: $60/month infrastructure budget, 100 concurrent users, 13 tickers
**Scale/Scope**: 13 tickers, 8 resolutions, 24h retention at 1-minute, 100 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Serverless/Event-driven architecture | PASS | Lambda + DynamoDB + SSE (existing pattern) |
| DynamoDB for persistence | PASS | New timeseries table with composite key pattern |
| Terraform IaC | PASS | Extends existing modules |
| Unit tests accompany implementation | PASS | Per-component tests planned |
| No pipeline bypass | PASS | Standard CI/CD workflow |
| GPG-signed commits | PASS | Standard workflow |
| Mock external APIs in tests | PASS | No external APIs in this feature |
| Deterministic time handling | PASS | Fixed historical dates for tests |
| SSE real-time updates | PASS | Extends existing SSE Lambda |

## Project Structure

### Documentation (this feature)

```text
specs/1009-realtime-multi-resolution/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# Backend (Lambda functions)
src/lambdas/
├── sse_streaming/
│   ├── handler.py           # MODIFY: Add resolution-filtered endpoints
│   ├── stream.py            # MODIFY: Add multi-resolution event generation
│   ├── models.py            # MODIFY: Add TimeBucket, PartialBucket models
│   ├── aggregator.py        # NEW: Time-series aggregation logic
│   ├── resolution.py        # NEW: Resolution constants and utilities
│   └── cache.py             # NEW: Multi-tier caching with resolution-aware TTL
├── dashboard/
│   ├── api_v2.py            # MODIFY: Add resolution parameter to endpoints
│   └── timeseries.py        # NEW: Time-series query service
└── ingestion/
    └── handler.py           # MODIFY: Fanout writes to timeseries table

# Shared library
src/lib/
├── timeseries/
│   ├── __init__.py
│   ├── bucket.py            # Time bucket alignment utilities
│   ├── aggregation.py       # Aggregation logic (OHLC-style)
│   └── models.py            # Shared Pydantic models

# Frontend
src/dashboard/
├── app.js                   # MODIFY: Resolution selector, instant switching
├── config.js                # MODIFY: Add resolution endpoints
├── timeseries.js            # NEW: Time-series chart component
└── cache.js                 # NEW: Client-side IndexedDB cache

# Infrastructure
infrastructure/terraform/
├── modules/
│   └── dynamodb/
│       └── main.tf          # MODIFY: Add timeseries table
├── main.tf                  # MODIFY: Wire new table to Lambdas
└── variables.tf             # MODIFY: Add timeseries table config

# Tests
tests/
├── unit/
│   ├── test_timeseries_bucket.py
│   ├── test_timeseries_aggregation.py
│   ├── test_resolution_cache.py
│   └── test_sse_resolution_filter.py
├── integration/
│   └── test_timeseries_pipeline.py
└── e2e/
    └── test_multi_resolution_dashboard.py
```

**Structure Decision**: Extends existing web application structure with new timeseries module in `src/lib/` for shared logic, modifications to existing Lambdas, and new client-side caching.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New DynamoDB table | Time-series data has fundamentally different access patterns than raw sentiment items | Using existing table with GSI would create hot partitions and expensive scans |
| 8 resolution levels | User requirement from spec | Fewer resolutions would reduce analytical flexibility |
| Write fanout (8x writes) | Query latency <100ms requires pre-computed buckets | On-demand aggregation exceeds latency budget |

## Phase 0: Research Findings

### Decision 1: Aggregation Strategy
- **Decision**: Write fanout with pre-aggregated buckets
- **Rationale**: At 13 tickers × 1440 mins/day = ~18K writes/day, fanout cost is $5.40/month. Query-time aggregation would require scanning 1440 items for 24h resolution, violating <100ms latency requirement.
- **Alternatives Rejected**:
  - DynamoDB Streams + Lambda aggregator: Added complexity, eventual consistency delays
  - Query-time aggregation: Exceeds latency budget (measured 800ms for 1440-item scan)

### Decision 2: DynamoDB Key Design
- **Decision**: Composite PK pattern `{ticker}#{resolution}` with SK as ISO8601 bucket timestamp
- **Rationale**: Single-partition queries for each ticker+resolution combo. No GSI needed (frontend requests specific resolution).
- **Alternatives Rejected**:
  - GSI for cross-resolution: Doubles write costs, not needed for use case
  - Single PK with resolution in SK: Hot partition risk with 13 tickers

### Decision 3: Caching Strategy
- **Decision**: Lambda global scope L1 cache with resolution-aware TTL, no DAX/ElastiCache
- **Rationale**: DAX minimum $60/month = entire budget. Lambda warm cache provides 80%+ hit rate for repeated requests.
- **Alternatives Rejected**:
  - DAX: Budget constraint
  - ElastiCache: Overkill for 100 users, adds VPC complexity

### Decision 4: SSE Multi-Resolution
- **Decision**: Resolution-filtered streaming with 100ms debounce
- **Rationale**: Clients subscribe to specific resolutions, server filters at source. Debounce prevents flooding when multiple resolutions update.
- **Alternatives Rejected**:
  - Send all resolutions, filter client-side: Higher egress costs, wasted bandwidth

### Decision 5: Partial Bucket Display
- **Decision**: Compute partial bucket from raw items in current window, stream with progress indicator
- **Rationale**: Real-time feel requires showing incomplete data with visual indicator
- **Alternatives Rejected**:
  - Wait for bucket completion: Violates "live breathing data" requirement

### Decision 6: Client-Side Caching
- **Decision**: IndexedDB for historical data, sessionStorage for current session
- **Rationale**: Instant resolution switching requires client-side cache. IndexedDB handles 24h of 1-minute data (~20KB/ticker).
- **Alternatives Rejected**:
  - Server-only caching: Cannot achieve <100ms switch without RTT

## Phase 1: Design Artifacts

### Data Model

**New Table: `{env}-sentiment-timeseries`**

```
PK (String)          | SK (String)           | Attributes
---------------------|----------------------|------------------------------------------
AAPL#1m              | 2025-12-21T10:35:00Z | open, high, low, close, count, sum, ttl
AAPL#5m              | 2025-12-21T10:35:00Z | open, high, low, close, count, sum, ttl
AAPL#1h              | 2025-12-21T10:00:00Z | open, high, low, close, count, sum, ttl
...
```

**Bucket Schema:**
```json
{
  "PK": "AAPL#5m",
  "SK": "2025-12-21T10:35:00Z",
  "open": 0.72,           // First sentiment score in bucket
  "high": 0.89,           // Max sentiment score in bucket
  "low": 0.45,            // Min sentiment score in bucket
  "close": 0.78,          // Last sentiment score in bucket
  "count": 12,            // Number of articles in bucket
  "sum": 8.64,            // Sum of scores (for avg calculation)
  "label_counts": {       // Distribution
    "positive": 8,
    "neutral": 3,
    "negative": 1
  },
  "sources": ["tiingo", "finnhub"],  // Unique sources
  "last_updated": "2025-12-21T10:39:45Z",
  "is_partial": false,    // True for current incomplete bucket
  "ttl": 1735344000       // TTL timestamp (resolution-dependent)
}
```

**TTL by Resolution:**
| Resolution | TTL | Rationale |
|------------|-----|-----------|
| 1m | 6 hours | High-res data expires fast, saves storage |
| 5m | 12 hours | |
| 10m | 24 hours | |
| 1h | 7 days | Daily users can see week of hourly data |
| 3h | 14 days | |
| 6h | 30 days | |
| 12h | 60 days | |
| 24h | 90 days | Monthly trend analysis |

### API Contracts

**GET /api/v2/timeseries/{ticker}**
```yaml
parameters:
  - name: ticker
    in: path
    required: true
    schema:
      type: string
      example: "AAPL"
  - name: resolution
    in: query
    required: true
    schema:
      type: string
      enum: ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]
  - name: start
    in: query
    required: false
    schema:
      type: string
      format: date-time
      description: "ISO8601 timestamp, defaults to 1 resolution period ago"
  - name: end
    in: query
    required: false
    schema:
      type: string
      format: date-time
      description: "ISO8601 timestamp, defaults to now"

responses:
  200:
    content:
      application/json:
        schema:
          type: object
          properties:
            ticker:
              type: string
            resolution:
              type: string
            buckets:
              type: array
              items:
                $ref: "#/components/schemas/SentimentBucket"
            partial_bucket:
              $ref: "#/components/schemas/PartialBucket"
            cache_hit:
              type: boolean
```

**SSE /api/v2/stream (extended)**
```yaml
parameters:
  - name: resolutions
    in: query
    required: false
    schema:
      type: array
      items:
        type: string
        enum: ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]
      default: ["1m"]
    description: "Resolutions to subscribe to"
  - name: tickers
    in: query
    required: false
    schema:
      type: array
      items:
        type: string
    description: "Tickers to filter (empty = all)"

events:
  - name: bucket_update
    data:
      ticker: string
      resolution: string
      bucket: SentimentBucket
  - name: partial_bucket
    data:
      ticker: string
      resolution: string
      bucket: PartialBucket
      progress_pct: number  # 0-100, percentage through current bucket
  - name: heartbeat
    data:
      timestamp: string
      connections: number
```

### Key Entities (Pydantic Models)

```python
# src/lib/timeseries/models.py

class Resolution(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    TEN_MINUTES = "10m"
    ONE_HOUR = "1h"
    THREE_HOURS = "3h"
    SIX_HOURS = "6h"
    TWELVE_HOURS = "12h"
    TWENTY_FOUR_HOURS = "24h"

class SentimentBucket(BaseModel):
    ticker: str
    resolution: Resolution
    timestamp: datetime  # Bucket start time (aligned to resolution)
    open: float         # First score in bucket
    high: float         # Max score
    low: float          # Min score
    close: float        # Last score
    count: int          # Article count
    avg: float          # Computed from sum/count
    label_counts: dict[str, int]  # {"positive": 8, "neutral": 3, "negative": 1}
    is_partial: bool = False

class PartialBucket(SentimentBucket):
    is_partial: bool = True
    progress_pct: float  # 0-100, percentage through bucket period
    next_update_at: datetime  # When bucket will be complete

class TimeseriesResponse(BaseModel):
    ticker: str
    resolution: Resolution
    buckets: list[SentimentBucket]
    partial_bucket: PartialBucket | None
    cache_hit: bool
    query_time_ms: float
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                      │
│  │  Dashboard  │    │ Resolution  │    │  IndexedDB  │                      │
│  │   App.js    │◄──►│  Selector   │    │   Cache     │                      │
│  └──────┬──────┘    └─────────────┘    └──────▲──────┘                      │
│         │                                      │                             │
│         │ SSE (resolutions=1m,5m)              │ Cache miss                  │
│         ▼                                      │                             │
│  ┌─────────────┐                        ┌──────┴──────┐                      │
│  │ EventSource │────────────────────────►  timeseries │                      │
│  │  /stream    │                        │   .js       │                      │
│  └──────┬──────┘                        └─────────────┘                      │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
          │ WebSocket / SSE
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY / FUNCTION URL                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     SSE STREAMING LAMBDA                             │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │    │
│  │  │  Resolution │  │   Event     │  │   Global    │                  │    │
│  │  │   Filter    │  │   Buffer    │  │   Cache L1  │                  │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │    │
│  │         │                │                │                          │    │
│  │         └────────────────┴────────────────┘                          │    │
│  │                          │                                           │    │
│  └──────────────────────────┼───────────────────────────────────────────┘    │
│                             │                                                │
│  ┌──────────────────────────┴───────────────────────────────────────────┐    │
│  │                     DASHBOARD LAMBDA                                  │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │    │
│  │  │ /timeseries │  │   Global    │  │  Timeseries │                   │    │
│  │  │  Endpoint   │  │   Cache L1  │  │   Service   │                   │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                   │    │
│  │         │                │                │                           │    │
│  │         └────────────────┴────────────────┘                           │    │
│  └──────────────────────────┼────────────────────────────────────────────┘    │
└─────────────────────────────┼────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     DYNAMODB                                         │    │
│  │                                                                      │    │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐         │    │
│  │  │  sentiment-items        │    │  sentiment-timeseries   │         │    │
│  │  │  (existing)             │    │  (NEW)                  │         │    │
│  │  │                         │    │                         │         │    │
│  │  │  PK: source_id          │    │  PK: ticker#resolution  │         │    │
│  │  │  SK: timestamp          │    │  SK: bucket_timestamp   │         │    │
│  │  │  GSI: by_sentiment      │    │                         │         │    │
│  │  │  GSI: by_tag            │    │  TTL: resolution-based  │         │    │
│  │  └──────────┬──────────────┘    └─────────────▲───────────┘         │    │
│  │             │                                 │                      │    │
│  └─────────────┼─────────────────────────────────┼──────────────────────┘    │
└────────────────┼─────────────────────────────────┼──────────────────────────┘
                 │                                 │
                 │  DynamoDB Streams               │  Write Fanout
                 ▼                                 │
┌────────────────────────────────────────────────────────────────────────────┐
│                     INGESTION LAMBDA (modified)                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                         │
│  │  Fetch      │  │  Analyze    │  │  Fanout     │                         │
│  │  Articles   │──►  Sentiment  │──►  to Buckets │─────────────────────────┘
│  └─────────────┘  └─────────────┘  └─────────────┘
│                                           │
│                                           │ 8 resolutions × N tickers
│                                           ▼
│                                    BatchWriteItem
└────────────────────────────────────────────────────────────────────────────┘
```

### Quickstart

```bash
# 1. Deploy infrastructure (adds timeseries table)
cd infrastructure/terraform
terraform plan -var-file=env/preprod.tfvars
terraform apply -var-file=env/preprod.tfvars

# 2. Run unit tests
pytest tests/unit/test_timeseries*.py -v

# 3. Run integration tests (LocalStack)
make localstack-up
pytest tests/integration/test_timeseries_pipeline.py -v
make localstack-down

# 4. Deploy Lambdas
# (Handled by CI/CD on merge)

# 5. Test SSE stream with resolution filter
curl -N "https://{function-url}/api/v2/stream?resolutions=1m,5m&tickers=AAPL"

# 6. Test timeseries API
curl "https://{function-url}/api/v2/timeseries/AAPL?resolution=5m"
```

## Cost Estimate

| Component | Calculation | Monthly Cost |
|-----------|-------------|--------------|
| DynamoDB Writes | 18K/day × 8 resolutions × 30 days × $1.25/million | $5.40 |
| DynamoDB Storage | 13 tickers × 8 resolutions × 0.1GB × $0.25/GB | $2.60 |
| DynamoDB Reads | 10K reads/day × 30 days × $0.25/million | $0.08 |
| Lambda Compute | ~500K invocations × $0.20/million | $0.10 |
| CloudWatch Logs | ~1GB/month × $0.50/GB | $0.50 |
| **Total** | | **$8.68** |

Budget: $60/month. Remaining: $51.32 for existing infrastructure.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Hot partition (popular ticker) | 91 partitions (13 tickers × 7 resolutions) distributes load |
| Cache stampede on Lambda cold start | Staggered cache TTLs, gradual cache population |
| SSE connection limits (100) | Existing connection pool logic, 503 when full |
| Late-arriving data | EventBridge scheduled Lambda every 5m to finalize buckets |
| Client-side cache corruption | Version-stamped cache entries, clear on version mismatch |

## TDD Implementation Requirements

**MANDATORY**: All implementation MUST follow TDD as defined in [spec.md#tdd-test-design](./spec.md#tdd-test-design-mandatory).

### Test-First Development Order

For each component, implement tests BEFORE production code:

| Order | Component | Test File | Canonical Source |
|-------|-----------|-----------|------------------|
| 1 | Time Bucket Alignment | `tests/unit/test_timeseries_bucket.py` | `[CS-009, CS-010]` |
| 2 | OHLC Aggregation | `tests/unit/test_timeseries_aggregation.py` | `[CS-011, CS-012]` |
| 3 | DynamoDB Key Design | `tests/unit/test_timeseries_key_design.py` | `[CS-002, CS-004]` |
| 4 | Write Fanout | `tests/unit/test_timeseries_fanout.py` | `[CS-001, CS-003]` |
| 5 | Lambda Global Cache | `tests/unit/test_resolution_cache.py` | `[CS-005, CS-006]` |
| 6 | SSE Resolution Filter | `tests/unit/test_sse_resolution_filter.py` | `[CS-007]` |
| 7 | Client IndexedDB Cache | `tests/e2e/test_client_cache.py` | `[CS-008]` |
| 8 | Integration Pipeline | `tests/integration/test_timeseries_pipeline.py` | All sources |

### Test Failure Protocol

When tests fail, follow the protocol in [spec.md#test-failure-handling-protocol](./spec.md#test-failure-handling-protocol):

1. **DO NOT assume tests are wrong** - First assume lack of context understanding
2. **Review canonical sources** - Re-read `[CS-XXX]` documentation
3. **Research similar patterns** - Prometheus, InfluxDB, Grafana codebases
4. **Formulate 3+ approaches** - Document alternatives before changing code
5. **Ask clarifying questions** - Pause and verify understanding
6. **Document decision** - Add to `docs/architecture-decisions.md`

### Test Coverage Requirements

| Category | Minimum Coverage | Assertion Count |
|----------|-----------------|-----------------|
| Unit tests | 80% line coverage | 50+ assertions |
| Integration | All GSI queries | 20+ assertions |
| E2E | All user stories | 15+ assertions |

## Next Steps

1. Run `/speckit.tasks` to generate tasks.md
2. Implement tests FIRST, then production code (TDD strict)
3. Implement in dependency order (Terraform → lib → Lambdas → frontend)
4. Validate each component against canonical sources before proceeding
