# Data Flow Efficiency Audit

**Audit Date:** 2025-11-26
**Status:** IN PROGRESS

## Executive Summary

Comprehensive audit identified **12 efficiency issues** across data flow patterns.
Estimated impact: **30-50% latency reduction**, **20-30% cost reduction** after fixes.

---

## System Data Flow Diagram

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TB
    subgraph External["External Data Sources"]
        Tiingo[("Tiingo API<br/>Primary")]
        Finnhub[("Finnhub API<br/>Secondary")]
        SendGrid[("SendGrid<br/>Email")]
    end

    subgraph IngestionFlow["Ingestion Flow (Every 5 min)"]
        EB[("EventBridge<br/>Scheduler")]
        ING["Ingestion Lambda"]

        subgraph IngestionCache["Caching Layer"]
            CB["Circuit Breaker<br/>State Cache"]
            QT["Quota Tracker<br/>Cache"]
            APIC["API Response<br/>Cache (1hr TTL)<br/>⚠️ PENDING"]
        end
    end

    subgraph ProcessingFlow["Analysis Flow"]
        SNS[("SNS Topic")]
        ANA["Analysis Lambda<br/>DistilBERT"]
        S3M[("S3<br/>ML Model")]
    end

    subgraph StorageLayer["DynamoDB Storage"]
        DDB[("sentiment-items<br/>News & Sentiment")]
        UDDB[("sentiment-users<br/>User Data")]

        subgraph GSIs["Global Secondary Indexes"]
            GSI1["by_sentiment"]
            GSI2["by_tag"]
            GSI3["by_status"]
            GSI4["by_email<br/>✅ NEW"]
            GSI5["by_entity_status<br/>✅ NEW"]
        end
    end

    subgraph DashboardFlow["Dashboard API Flow"]
        DASH["Dashboard Lambda<br/>FastAPI"]

        subgraph DashCache["Caching Layer"]
            MC["Metrics Cache<br/>30s TTL<br/>✅ FIXED"]
            TC["Table Object<br/>Cache<br/>✅ FIXED"]
            SC["Secrets Cache<br/>5min TTL"]
        end

        SSE["SSE Stream<br/>Real-time Updates"]
    end

    subgraph NotificationFlow["Notification Flow"]
        NOT["Notification Lambda"]
        NOTC["SendGrid Client<br/>Cache"]
    end

    subgraph Clients["Clients"]
        Browser["Web Browser"]
        API["API Consumers"]
    end

    %% Ingestion Flow
    EB -->|"Trigger"| ING
    Tiingo -->|"Fetch News"| ING
    Finnhub -->|"Fetch News"| ING
    ING -->|"Check State"| CB
    ING -->|"Check Quota"| QT
    ING -.->|"Cache Resp"| APIC
    ING -->|"Store"| DDB
    ING -->|"Publish"| SNS

    %% Processing Flow
    SNS -->|"Subscribe"| ANA
    S3M -->|"Load Model"| ANA
    ANA -->|"Update"| DDB

    %% Dashboard Flow
    Browser -->|"HTTPS"| DASH
    API -->|"REST"| DASH
    DASH -->|"Check Cache"| MC
    DASH -->|"Reuse"| TC
    DASH -->|"Get Key"| SC
    MC -->|"Cache Miss"| DDB
    TC -->|"Query"| GSIs
    DASH -->|"Stream"| SSE
    SSE -->|"Events"| Browser

    %% Notification Flow
    DASH -->|"Trigger"| NOT
    NOT -->|"Lookup"| UDDB
    NOT -->|"Send"| SendGrid
    NOT -->|"Reuse"| NOTC

    %% Styling
    classDef layerBox fill:#fff8e1,stroke:#c9a227,stroke-width:2px,color:#333
    classDef lambdaStyle fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef storageStyle fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e
    classDef cacheStyle fill:#b39ddb,stroke:#673ab7,stroke-width:2px,color:#1a0a3e
    classDef externalStyle fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef pendingStyle fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800

    class External,IngestionFlow,ProcessingFlow,StorageLayer,DashboardFlow,NotificationFlow,Clients layerBox
    class ING,ANA,DASH,NOT lambdaStyle
    class DDB,UDDB,S3M storageStyle
    class MC,TC,SC,CB,QT,NOTC cacheStyle
    class Tiingo,Finnhub,SendGrid,Browser,API externalStyle
    class APIC pendingStyle
```

---

## Caching Strategy Diagram

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart LR
    subgraph CacheTypes["Cache Types & TTLs"]
        direction TB

        subgraph InMemory["In-Memory (Lambda Container)"]
            M1["Metrics Cache<br/>TTL: 30s<br/>✅ IMPLEMENTED"]
            M2["Table Object<br/>TTL: Container lifetime<br/>✅ IMPLEMENTED"]
            M3["ML Model<br/>TTL: Container lifetime<br/>✅ EXISTING"]
            M4["Ticker Cache<br/>TTL: Container lifetime<br/>✅ EXISTING"]
        end

        subgraph SecretsCache["Secrets Manager Cache"]
            S1["API Keys<br/>TTL: 5 min<br/>✅ EXISTING"]
            S2["SendGrid Key<br/>TTL: 5 min<br/>✅ EXISTING"]
        end

        subgraph Pending["Pending Implementation"]
            P1["API Response Cache<br/>TTL: 1 hour<br/>⚠️ DFA-004"]
            P2["Circuit Breaker<br/>TTL: In-memory<br/>⚠️ DFA-008"]
            P3["Active Tickers<br/>TTL: 1 hour<br/>⚠️ DFA-003"]
        end
    end

    subgraph Impact["Query Impact"]
        direction TB

        subgraph Before["Before Caching"]
            B1["SSE: 72K queries/min"]
            B2["API: 500 calls/day"]
            B3["Config: Scan all items"]
        end

        subgraph After["After Caching"]
            A1["SSE: 4 queries/min<br/>99.99% reduction"]
            A2["API: ~50 calls/day<br/>90% reduction"]
            A3["Config: Query GSI<br/>100x faster"]
        end
    end

    M1 -.->|"Reduces"| B1
    B1 -->|"To"| A1
    P1 -.->|"Will Reduce"| B2
    B2 -->|"To"| A2
    P3 -.->|"Will Reduce"| B3
    B3 -->|"To"| A3

    classDef implemented fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e
    classDef existing fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef pending fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef impact fill:#b39ddb,stroke:#673ab7,stroke-width:2px,color:#1a0a3e
    classDef reduction fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff

    class M1,M2 implemented
    class M3,M4,S1,S2 existing
    class P1,P2,P3 pending
    class B1,B2,B3 impact
    class A1,A2,A3 reduction
```

---

## SSE Data Flow (Before vs After Fix)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
sequenceDiagram
    autonumber

    participant C as Client (Browser)
    participant L as Dashboard Lambda
    participant Cache as Metrics Cache
    participant DB as DynamoDB

    rect rgb(239, 83, 80, 0.1)
        Note over C,DB: BEFORE FIX (DFA-001)
        C->>L: SSE Connect
        loop Every 5 seconds (per client)
            L->>DB: get_table()
            L->>DB: Query recent_items
            L->>DB: Query by_sentiment (positive)
            L->>DB: Query by_sentiment (neutral)
            L->>DB: Query by_sentiment (negative)
            L->>DB: Query ingestion_rate (1h)
            L->>DB: Query ingestion_rate (24h)
            DB-->>L: Results (6-7 queries)
            L->>L: Parse & Sanitize
            L-->>C: SSE Event
        end
        Note over DB: 1000 clients × 12/min × 6 queries = 72,000 queries/min
    end

    rect rgb(168, 213, 162, 0.2)
        Note over C,DB: AFTER FIX (with Metrics Cache)
        C->>L: SSE Connect
        loop Every 5 seconds (per client)
            L->>Cache: Check cache (< 30s old?)
            alt Cache Hit
                Cache-->>L: Cached metrics
            else Cache Miss
                L->>DB: Query recent_items
                L->>DB: Query by_sentiment (×3)
                L->>DB: Query ingestion_rate (×2)
                DB-->>L: Results
                L->>L: Parse & Sanitize (once)
                L->>Cache: Store (30s TTL)
            end
            L-->>C: SSE Event
        end
        Note over DB: Shared cache: ~4 queries/min (99.99% reduction)
    end
```

---

## DynamoDB Access Pattern Optimization

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TB
    subgraph Tables["DynamoDB Tables"]
        subgraph SentimentItems["sentiment-items (Legacy)"]
            SI_PK["PK: source_id"]
            SI_SK["SK: timestamp"]

            subgraph SI_GSI["GSIs"]
                SI_G1["by_sentiment<br/>(sentiment, timestamp)"]
                SI_G2["by_tag<br/>(tag, timestamp)"]
                SI_G3["by_status<br/>(status, timestamp)"]
            end
        end

        subgraph SentimentUsers["sentiment-users (Feature 006)"]
            SU_PK["PK: USER#{id}"]
            SU_SK["SK: CONFIG#/ALERT#/etc"]

            subgraph SU_GSI["GSIs ✅ NEW"]
                SU_G1["by_email<br/>(email)"]
                SU_G2["by_cognito_sub<br/>(cognito_sub)"]
                SU_G3["by_entity_status<br/>(entity_type, status)"]
            end
        end
    end

    subgraph Queries["Query Patterns"]
        Q1["User Login<br/>→ by_email GSI"]
        Q2["OAuth Lookup<br/>→ by_cognito_sub GSI"]
        Q3["Filter Notifications<br/>→ by_entity_status GSI"]
        Q4["Filter Alerts<br/>→ by_entity_status GSI"]
        Q5["Get User Data<br/>→ Query PK"]
    end

    subgraph Optimizations["Optimizations"]
        O1["❌ BEFORE: Scan all + filter in Python"]
        O2["✅ AFTER: Query GSI directly"]
        O3["Impact: 90% faster queries"]
    end

    Q1 --> SU_G1
    Q2 --> SU_G2
    Q3 --> SU_G3
    Q4 --> SU_G3
    Q5 --> SU_PK

    O1 -.->|"Replaced by"| O2
    O2 --> O3

    classDef tableStyle fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e
    classDef gsiStyle fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef queryStyle fill:#b39ddb,stroke:#673ab7,stroke-width:2px,color:#1a0a3e
    classDef badStyle fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef goodStyle fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e

    class SentimentItems,SentimentUsers tableStyle
    class SI_G1,SI_G2,SI_G3,SU_G1,SU_G2,SU_G3 gsiStyle
    class Q1,Q2,Q3,Q4,Q5 queryStyle
    class O1 badStyle
    class O2,O3 goodStyle
```

---

## Issue Tracker

### CRITICAL (Deploy Week 1)

| ID | Issue | File | Status | PR |
|----|-------|------|--------|-----|
| DFA-001 | SSE polling bottleneck (72K queries/min) | handler.py:581-643 | ✅ RESOLVED | PR #119 |
| DFA-002 | No SNS message batching | ingestion/handler.py:182-339 | ✅ RESOLVED | PR #119 |

### HIGH (Deploy Week 2)

| ID | Issue | File | Status | PR |
|----|-------|------|--------|-----|
| DFA-003 | Scan instead of Query for active tickers | handler.py:408-444 | PENDING | - |
| DFA-004 | No API response caching (Tiingo/Finnhub) | adapters/*.py | PENDING | - |
| DFA-005 | Multiple metrics queries (6+ per request) | metrics.py:336-417 | PENDING | - |
| DFA-006 | Per-tag N+1 query pattern | api_v2.py:91-197 | PENDING | - |

### MEDIUM (Deploy Week 3-4)

| ID | Issue | File | Status | PR |
|----|-------|------|--------|-----|
| DFA-007 | Redundant item existence check | dynamodb.py:208-242 | PENDING | - |
| DFA-008 | Circuit breaker DynamoDB persistence | handler.py:164-169 | PENDING | - |

### LOW (Deploy Week 4-5)

| ID | Issue | File | Status | PR |
|----|-------|------|--------|-----|
| DFA-009 | Repeated parse_dynamodb_item calls | handler.py:502-506 | PENDING | - |
| DFA-010 | API key lazy loading cold start | handler.py:107-138 | PENDING | - |
| DFA-011 | SendGrid client recreation | sendgrid_service.py:84-88 | PENDING | - |
| DFA-012 | Missing GSIs for analytics | - | PENDING | - |

---

## Detailed Findings

### DFA-001: SSE Polling Bottleneck (CRITICAL)

**Location:** `src/lambdas/dashboard/handler.py:581-643`

**Problem:**
```python
async def event_generator():
    while True:
        table = get_table(DYNAMODB_TABLE)  # Reconnect every cycle
        metrics = aggregate_dashboard_metrics(table, hours=24)  # 6+ queries
        await asyncio.sleep(5)  # Every 5 seconds
```

**Impact:**
- 1000 concurrent clients = 72,000-84,000 DynamoDB queries/min
- No caching between requests
- Table object recreated every cycle

**Fix:**
1. Add 30-second TTL cache for metrics
2. Reuse table object across cycles
3. Implement delta updates (only send changes)

**Estimated Gain:** 90% reduction in DynamoDB queries

---

### DFA-002: No SNS Message Batching (CRITICAL)

**Location:** `src/lambdas/ingestion/handler.py:183-318`

**Problem:**
```python
for article in articles:  # 100+ articles
    sns_client.publish(...)  # 100+ sequential publishes
```

**Impact:**
- Linear latency with article count
- SNS pricing per publish (could batch 10-25)
- Sequential publishing is bottleneck

**Fix (✅ IMPLEMENTED):**
```python
# Collect messages during processing
pending_sns_messages: list[dict[str, Any]] = []
for article in articles:
    sns_msg = _process_article(article, source, table, model_version)
    if sns_msg is not None:
        pending_sns_messages.append(sns_msg)

# Batch publish at end using SNS publish_batch API
_publish_sns_batch(sns_client, sns_topic_arn, pending_sns_messages)
```

Key changes:
1. `_process_article()` now returns SNS message dict (or None for duplicates)
2. Messages collected during article processing loop
3. `_publish_sns_batch()` uses SNS `publish_batch` API (max 10 per call)
4. Handles partial failures gracefully

**Actual Gain:** 90% reduction in SNS API calls (100 articles → 10 batch calls)

---

### DFA-003: Scan Instead of Query (HIGH)

**Location:** `src/lambdas/ingestion/handler.py:408-444`

**Problem:**
```python
response = table.scan(  # Expensive scan!
    FilterExpression="entity_type = :et AND is_active = :active",
)
```

**Impact:**
- Scan reads ALL items
- 1-5 seconds for large tables
- 100x more RCU than query

**Fix:**
1. Add GSI: `by_entity_type` (entity_type, is_active)
2. Use Query with new GSI
3. Cache results (configs change infrequently)

**Estimated Gain:** 10-50 second improvement

---

### DFA-004: No API Response Caching (HIGH)

**Location:** `src/lambdas/shared/adapters/tiingo.py`, `finnhub.py`

**Problem:**
Every 5-minute ingestion cycle fetches same 7-day window of news.

**Impact:**
- Tiingo free tier: 500 symbol lookups/month (depleted in 3 days)
- 100-500ms per API call
- Hits rate limits unnecessarily

**Fix:**
1. Add 1-hour cache for API responses
2. Narrow time window to `[now-1h, now]`
3. Batch requests (10 tickers per Tiingo call)

**Estimated Gain:** Save 300+ API calls/day

---

### DFA-005: Multiple Metrics Queries (HIGH)

**Location:** `src/lambdas/dashboard/metrics.py:336-417`

**Problem:**
```python
def aggregate_dashboard_metrics(table, hours=24):
    recent_items = get_recent_items(table, limit=MAX_RECENT_ITEMS)  # Query 1
    for sentiment in SENTIMENT_VALUES:  # 3 more queries
        items = get_items_by_sentiment(table, sentiment, hours)
    rates = calculate_ingestion_rate(table, hours)  # 2 more queries
```

**Impact:**
- 6-7 DynamoDB queries per /api/metrics request
- ~6 RCU per request

**Fix:**
1. Combine queries into single scan with filter
2. Cache for 30 seconds
3. Use CloudWatch metrics for aggregation

**Estimated Gain:** 80% latency reduction

---

### DFA-006: Per-Tag N+1 Query Pattern (HIGH)

**Location:** `src/lambdas/dashboard/api_v2.py:91-197`

**Problem:**
```python
for tag in tags:  # 5 tags = 5 queries
    response = table.query(IndexName="by_tag", ...)
```

**Impact:**
- 5+ queries minimum
- Up to 10+ with pagination
- Classic N+1 pattern

**Fix:**
1. BatchGetItem for multiple tags (if supported)
2. Single query with IN filter
3. Cache tag→item mappings

**Estimated Gain:** 80% query reduction

---

### DFA-007: Redundant Item Existence Check (MEDIUM)

**Location:** `src/lambdas/shared/dynamodb.py:208-242`

**Problem:**
```python
def item_exists(table, source_id, timestamp):
    response = table.get_item(...)  # Unnecessary check
    return "Item" in response
```

**Fix:** Rely on conditional writes only (atomic, no race condition)

**Estimated Gain:** 50% DynamoDB cost for deduplication

---

## Resolution Log

| Date | ID | Action | Result |
|------|-----|--------|--------|
| 2025-11-26 | - | Initial audit completed | 12 issues identified |
| 2025-11-26 | DFA-* | GSI added for Feature 006 users table | by_entity_status GSI resolves notification filtering |

---

## Metrics to Track

After fixes deployed, monitor:

```bash
# DynamoDB consumed capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -d '7 days ago' -u +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 86400 --statistics Sum

# Lambda duration p95
aws logs start-query \
  --log-group-name /aws/lambda/preprod-dashboard \
  --query-string 'stats pct(@duration, 95) by bin(1h)'
```

---

## Related Documents

- [SECURITY_REVIEW.md](./SECURITY_REVIEW.md) - Security audit
- [ON_CALL_SOP.md](./ON_CALL_SOP.md) - Operational procedures
- [specs/006-user-config-dashboard/](../specs/006-user-config-dashboard/) - Feature 006 spec
