# Real-Time Multi-Resolution Time-Series: Tradeoff Analysis

## The Vision

```
┌────────────────────────────────────────────────────────────────────────────┐
│  REAL-TIME MULTI-RESOLUTION ARCHITECTURE                                   │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   Tiingo WS ─────┐                                                         │
│                  │     ┌─────────────────┐      ┌──────────────────┐      │
│   Finnhub WS ────┼────▶│  Aggregator     │─────▶│  ElastiCache     │      │
│                  │     │  Lambda         │      │  (Redis)         │      │
│   (Real-time     │     │                 │      │                  │      │
│    tick data)    │     │  • 1min buckets │      │  • Hot data      │      │
│                  │     │  • Boundary     │      │  • Multi-res     │      │
│                  │     │    aligned      │      │  • Shared cache  │      │
│                  │     └────────┬────────┘      └────────┬─────────┘      │
│                                 │                        │                 │
│                                 ▼                        │                 │
│                        ┌────────────────┐                │                 │
│                        │  DynamoDB      │                │                 │
│                        │  (1min base)   │◀───────────────┘                 │
│                        │  PK: TICKER    │     (write-through)              │
│                        │  SK: timestamp │                                  │
│                        └────────────────┘                                  │
│                                                                            │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                    API GATEWAY WEBSOCKET                            │  │
│   │  • Topic-based subscriptions: AAPL:1m, GOOG:5m, etc.               │  │
│   │  • Fan-out to all subscribers of a topic                            │  │
│   │  • Partial bucket updates every 1-3 seconds                        │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                 │                                          │
│         ┌───────────────────────┼───────────────────────┐                  │
│         ▼                       ▼                       ▼                  │
│   ┌───────────┐           ┌───────────┐           ┌───────────┐           │
│   │  User 1   │           │  User 2   │           │  User 3   │           │
│   │  AAPL 1m  │           │  GOOG 1m  │           │  AAPL 5m  │           │
│   │           │           │  (cached) │           │ (derived) │           │
│   └───────────┘           └───────────┘           └───────────┘           │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Cost Analysis: Is It Ridiculous?

**Short answer: NO. It's surprisingly cheap.**

Scenario: 13 tickers, 100 concurrent users, 8 hours/day market hours

| Component             | Calculation                                            | Monthly Cost |
|-----------------------|--------------------------------------------------------|--------------|
| DynamoDB (1-min base) |                                                        |              |
| └─ Writes             | 13 tickers × 390 min/day × 22 days × $0.00000125       | $0.14        |
| └─ Reads              | 100 users × 50 queries/session × 22 days × $0.00000025 | $0.03        |
| └─ Storage            | 13 × 390 × 22 × 12mo × 1KB = 1.3GB                     | $0.33        |
| ElastiCache (Redis)   |                                                        |              |
| └─ cache.t4g.micro    | Smallest instance                                      | $11.52       |
| API Gateway WebSocket |                                                        |              |
| └─ Connection minutes | 100 users × 8hr × 60min × 22 days = 1.06M              | $1.06        |
| └─ Messages           | 100 × 1msg/sec × 8hr × 3600 × 22 = 63M                 | $15.75       |
| Lambda (Aggregator)   |                                                        |              |
| └─ Invocations        | 13 tickers × 1/sec × 8hr × 3600 × 22 = 33M             | $6.60        |
| └─ Duration           | 33M × 100ms × 128MB                                    | $5.50        |
| Tiingo WebSocket      | Starter plan                                           | $10.00       |
|                       |                                                        |              |
| **TOTAL**             |                                                        | **~$51/month** |

That's less than a nice dinner for iPhone-level real-time charts.

For comparison, your current architecture probably costs $20-30/month. The delta is ~$20-30 for:
- True real-time (sub-second latency vs 5-second polling)
- 8 resolution levels instead of 1
- Shared caching across all users
- Preloading for instant resolution switching

---

## Bucket Strategy: Store 1-Min, Derive Everything Else

**Key Insight**: Only store 1-minute resolution. All other resolutions are aggregations.

```
1-min (stored)     ──┬──▶ 5-min  (aggregate 5)
                    ├──▶ 10-min (aggregate 10)
                    ├──▶ 1-hr   (aggregate 60)
                    ├──▶ 3-hr   (aggregate 180)
                    ├──▶ 6-hr   (aggregate 360)
                    ├──▶ 12-hr  (aggregate 720)
                    └──▶ 24-hr  (aggregate 1440)
```

Why this works:
- Aggregation is O(n) where n = bucket_size / 1min
- For 24hr: aggregate 1440 items = ~2ms in Lambda
- Cache the result → subsequent requests are instant

**DynamoDB Schema:**
```
PK: TICKER#AAPL
SK: TS#2025-12-21T14:37:00Z   (boundary-aligned to minute)

Attributes:
  sentiment_score: 0.72
  sentiment_label: "positive"
  confidence: 0.89
  article_count: 3
  source: "aggregated"
```

**Cache Key Pattern:**
```
sentiment:{ticker}:{resolution}:{boundary_timestamp}
sentiment:AAPL:1m:2025-12-21T14:37:00Z
sentiment:AAPL:5m:2025-12-21T14:35:00Z  (aligned to 5-min boundary)
sentiment:AAPL:1h:2025-12-21T14:00:00Z  (aligned to hour)
```

---

## Real-Time Partial Bucket: The "Live" Feel

The current (incomplete) bucket is what makes it feel alive:

```typescript
// Partial bucket structure
interface PartialBucket {
  ticker: string;
  resolution: "1m" | "5m" | "10m" | "1h" | "3h" | "6h" | "12h" | "24h";
  boundary_start: string;      // "2025-12-21T14:35:00Z"
  boundary_end: string;        // "2025-12-21T14:40:00Z" (for 5m)
  current_time: string;        // "2025-12-21T14:37:23Z"
  progress_pct: number;        // 47.67% through bucket

  // Running aggregates (update every tick)
  sentiment_score: number;     // Rolling average
  article_count: number;       // Count so far
  confidence: number;          // Weighted average

  // For OHLC-style visualization
  open_score: number;          // First sentiment of bucket
  high_score: number;          // Max sentiment
  low_score: number;           // Min sentiment
  current_score: number;       // Latest sentiment (close)
}
```

**Update Frequency:**
- WebSocket tick data: Every trade/quote (~10-100/sec per ticker)
- Sentiment aggregation: Every article (few per minute)
- Client push: Every 1-3 seconds (batched updates)

---

## Shared Cache Architecture

### The Magic: Topic-Based Fan-Out

```
┌─────────────────────────────────────────────────────────────────┐
│                     REDIS CACHE STRUCTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  KEY: sentiment:AAPL:1m:2025-12-21T14:37:00Z                   │
│  VALUE: {score: 0.72, label: "positive", count: 3, ...}        │
│  TTL: 86400 (24 hours)                                          │
│                                                                 │
│  KEY: sentiment:AAPL:5m:2025-12-21T14:35:00Z                   │
│  VALUE: {score: 0.68, label: "positive", count: 12, ...}       │
│  TTL: 86400                                                     │
│                                                                 │
│  KEY: sentiment:AAPL:partial                                    │
│  VALUE: {boundary: "14:37", progress: 47%, score: 0.71, ...}   │
│  TTL: 300 (5 minutes, constantly refreshed)                     │
│                                                                 │
│  CHANNEL: sentiment:live:AAPL                                   │
│  SUBSCRIBERS: [conn_1, conn_7, conn_23, ...]                   │
│  MESSAGE: {type: "tick", score: 0.73, ts: "14:37:24.123"}      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**User Flow (Cache Hit):**
```
User 1: Subscribe AAPL:1m
  └─▶ Redis: GET sentiment:AAPL:1m:* (last 60 buckets)
      └─▶ Cache HIT (User 2 loaded this 30 seconds ago)
          └─▶ Return immediately (<10ms)
              └─▶ Subscribe to sentiment:live:AAPL channel
                  └─▶ Receive partial bucket updates every 1-3s
```

---

## Preloading Strategy: Anticipate User Intent

**Adjacent Resolution Preload:**
```typescript
const PRELOAD_MAP = {
  "1m":  ["5m", "10m"],      // User might zoom out
  "5m":  ["1m", "10m", "1h"],
  "10m": ["5m", "1h"],
  "1h":  ["10m", "3h", "6h"],
  "3h":  ["1h", "6h"],
  "6h":  ["3h", "12h"],
  "12h": ["6h", "24h"],
  "24h": ["12h"],
};

// On resolution change
function onResolutionChange(ticker: string, newRes: Resolution) {
  // Load requested resolution (blocking)
  const data = await fetchResolution(ticker, newRes);
  render(data);

  // Preload adjacent resolutions (non-blocking)
  PRELOAD_MAP[newRes].forEach(res => {
    prefetch(`/api/v2/sentiment/${ticker}/timeseries?res=${res}`);
  });
}
```

**Time-Range Preload:**
```
// When user loads "last 1 hour" of 1-min data
// Preload "previous 1 hour" in background
// Result: Scroll left is instant
```

---

## WebSocket Architecture: Tiingo + Finnhub

**Tiingo WebSocket** (requires paid plan ~$10/mo):
```javascript
// Real-time quote data
wss://api.tiingo.com/iex
{
  "messageType": "A",  // Trade
  "data": ["AAPL", "2025-12-21T14:37:23.123Z", 238.45, 100]
}
```

**Finnhub WebSocket** (free tier, 60 symbols):
```javascript
// Real-time trades
wss://ws.finnhub.io?token=YOUR_KEY
{
  "type": "trade",
  "data": [{"s": "AAPL", "p": 238.45, "v": 100, "t": 1703168243123}]
}
```

**Hybrid Strategy:**
- Use Finnhub free tier for 13 tracked tickers (within 60 limit)
- Fall back to Tiingo if Finnhub disconnects
- Both provide trade-level granularity

---

## Client Architecture: The iPhone Feel

**Key Principles:**
1. **Optimistic UI**: Show stale data immediately, update when fresh arrives
2. **Skeleton Loading**: Never show spinners, show chart skeleton
3. **Smooth Transitions**: Animate between resolutions
4. **Background Refresh**: WebSocket updates don't trigger re-renders, they update data store

```typescript
// React Query + WebSocket hybrid
function useSentimentTimeSeries(ticker: string, resolution: Resolution) {
  // Static historical data (cached)
  const { data: historical } = useQuery({
    queryKey: ['sentiment', ticker, resolution],
    queryFn: () => fetchHistorical(ticker, resolution),
    staleTime: 60_000,  // Consider fresh for 1 minute
    cacheTime: 24 * 60 * 60_000,  // Keep in cache 24 hours
  });

  // Live partial bucket (WebSocket)
  const partial = useSentimentWebSocket(ticker, resolution);

  // Merge: historical + live partial
  return useMemo(() => {
    if (!historical) return null;
    return [...historical, partial].filter(Boolean);
  }, [historical, partial]);
}

// WebSocket hook with automatic reconnection
function useSentimentWebSocket(ticker: string, resolution: Resolution) {
  const [partial, setPartial] = useState<PartialBucket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`wss://api.example.com/sentiment/live`);
    ws.onopen = () => ws.send(JSON.stringify({
      action: 'subscribe',
      ticker,
      resolution
    }));
    ws.onmessage = (e) => setPartial(JSON.parse(e.data));
    return () => ws.close();
  }, [ticker, resolution]);

  return partial;
}
```

---

## Performance Targets

| Metric                 | Target             | How                             |
|------------------------|--------------------|---------------------------------|
| Initial load           | <500ms             | CDN + Redis cache               |
| Resolution switch      | <100ms             | Preloaded data                  |
| Live update latency    | <100ms             | WebSocket                       |
| Partial bucket refresh | Every 1-3s         | Batched WebSocket               |
| Historical scroll      | Instant            | Prefetched adjacent time ranges |
| Multi-ticker view      | <1s for 10 tickers | Parallel fetches + shared cache |

---

## What Makes This "Wow"

1. **Zero Loading States**: Skeleton UI + optimistic rendering = no spinners ever
2. **Instant Resolution Switching**: Preloaded adjacent resolutions
3. **Live Breathing Data**: Partial bucket animates as new data arrives
4. **Shared Intelligence**: Your AAPL cache benefits all AAPL viewers
5. **Graceful Degradation**: WebSocket fails → falls back to polling seamlessly
6. **Offline Support**: IndexedDB caches historical data for instant cold starts

---

## Implementation Phases

### Phase 1: Foundation
- WebSocket service connecting to Finnhub
- 1-minute bucket aggregation Lambda
- Redis cache layer
- DynamoDB schema with timestamp range key

### Phase 2: Multi-Resolution
- On-demand aggregation from 1-min base
- Cache warming for common resolutions
- Preload logic

### Phase 3: Client Excellence
- TradingView Lightweight Charts integration
- WebSocket client with reconnection
- Resolution picker with instant switching
- Partial bucket live updates

### Phase 4: Polish
- Skeleton UI
- Smooth animations
- Error boundaries
- Performance profiling
