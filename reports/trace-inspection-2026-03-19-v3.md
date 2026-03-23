# Observability Audit -- Sentiment Analyzer Preprod (v3)

**Generated:** 2026-03-19 18:07:31 UTC
**Environment:** preprod
**Methodology:** Automated diagnostic with code-review-informed assertions

## Verdict

**YELLOW** -- 4 passed, 2 warnings, 1 informational. System functions but has known gaps that would confound chaos injection results.

## Test Results

| # | Test | Status | Confidence | Detail |
|---|------|--------|------------|--------|
| 1 | Cold Start Latency | **INFO** | LOW | Warm instance (no Init segment): 668ms client-side |
| 2 | OHLC Data Correctness | **PASS** | HIGH | 5 candles (2026-03-12 to 2026-03-18); close range $1.02-$1.09; volume range 19,946,731-28,767,882 |
| 3 | Sentiment Data Source | **WARN** | HIGH | SYNTHETIC DATA CONFIRMED. 8 points, deterministic=True, external_calls=0, trace=0ms. Code review: sha256(ticker) seeds R... |
| 4 | Tier 1 In-Memory Cache | **PASS** | HIGH | Rapid sequential: [live-api -> persistent-cache -> in-memory]. Latencies: 515ms -> 420ms -> 347ms. In-memory hit confirm... |
| 5 | Auth Failure Handling | **PASS** | HIGH | Invalid token -> HTTP 401 in 332ms. Body: {"detail":"Missing user identification"} |
| 6 | Input Validation Coverage | **PASS** | HIGH | 6/6 passed. ticker too long: 400 OK (350ms); numeric ticker: 400 OK (351ms); SQL injection: 400 OK (362ms); XSS attempt:... |
| 7 | Observability Header Audit | **WARN** | HIGH | OHLC: x-cache-source=YES, x-cache-age=YES, x-amzn-trace-id=YES, x-amzn-requestid=YES. Sentiment: x-cache-source=NO (MISS... |

## Detailed Findings

### 1. Cold Start Latency -- INFO (confidence: LOW)

Warm instance (no Init segment): 668ms client-side

```json
{
  "latency_ms": 668.2986230007373,
  "is_cold": false
}
```

### 2. OHLC Data Correctness -- PASS (confidence: HIGH)

5 candles (2026-03-12 to 2026-03-18); close range $1.02-$1.09; volume range 19,946,731-28,767,882

```json
{
  "candles": 5,
  "source": "tiingo",
  "cache": "live-api",
  "latency_ms": 609.8414200241677
}
```

### 3. Sentiment Data Source -- **WARN** (confidence: HIGH)

SYNTHETIC DATA CONFIRMED. 8 points, deterministic=True, external_calls=0, trace=0ms. Code review: sha256(ticker) seeds RNG, no DynamoDB/API calls. Score range: 0.075 to 0.598

```json
{
  "points": 8,
  "synthetic": true,
  "trace_ms": 0,
  "latency_ms": 368.4811579878442
}
```

### 4. Tier 1 In-Memory Cache -- PASS (confidence: HIGH)

Rapid sequential: [live-api -> persistent-cache -> in-memory]. Latencies: 515ms -> 420ms -> 347ms. In-memory hit confirmed. Trace external calls: 0

```json
{
  "caches": [
    "live-api",
    "persistent-cache",
    "in-memory"
  ],
  "latencies": [
    515.2890980243683,
    420.01124197850004,
    347.0600640284829
  ],
  "tier1_hit": true
}
```

### 5. Auth Failure Handling -- PASS (confidence: HIGH)

Invalid token -> HTTP 401 in 332ms. Body: {"detail":"Missing user identification"}

```json
{
  "status": 401,
  "latency_ms": 331.72484196256846
}
```

### 6. Input Validation Coverage -- PASS (confidence: HIGH)

6/6 passed. ticker too long: 400 OK (350ms); numeric ticker: 400 OK (351ms); SQL injection: 400 OK (362ms); XSS attempt: 404 OK (365ms); empty range: 200 OK (424ms); invalid resolution: 422 OK (341ms)

```json
{
  "passed": 6,
  "total": 6
}
```

### 7. Observability Header Audit -- **WARN** (confidence: HIGH)

OHLC: x-cache-source=YES, x-cache-age=YES, x-amzn-trace-id=YES, x-amzn-requestid=YES. Sentiment: x-cache-source=NO (MISSING). Gap: sentiment endpoint has no cache observability headers.

```json
{
  "ohlc_headers": true,
  "sentiment_headers": false
}
```

## The Uncomfortable Findings

These are findings that a green dashboard would hide:

### 1. The core product is serving fake data

The sentiment analysis platform's `/sentiment/history` endpoint returns **synthetic data** generated from `sha256(ticker)` as an RNG seed. No external API is called. No DynamoDB is queried. The trace completes in ~1ms because it's pure in-process computation.

The code comment says: *"In production, this would query DynamoDB for historical sentiment records. For now, generate synthetic data."*

**Impact:** Every sentiment chart the customer sees is fake. The same ticker always produces the same curve regardless of actual market conditions. This is the single largest gap in the system and cannot be detected by status-code-level testing.

### 2. In-memory cache effectiveness under real traffic

Tier 1 (in-memory) **was observed** on rapid sequential requests. However, under real traffic with CloudFront distribution across Lambda instances, the hit rate will be lower. Monitor `Cache/Hits` for `ohlc_response` in production to determine actual effectiveness.

### 3. Observability is asymmetric

OHLC endpoints have rich observability: `x-cache-source`, `x-cache-age`, X-Ray subsegments for DynamoDB and Tiingo, CloudWatch metrics. Sentiment endpoints have **none of this**. If the sentiment endpoint breaks, the only signal is a customer complaint. There is no automated way to detect degradation.

## Known Unknowns

Things this audit explicitly did NOT test:

| Unknown | Why It Matters | What Would Break |
|---------|---------------|-----------------|
| Tiingo API failure/timeout | OHLC data depends entirely on Tiingo | Show stale cache? Show error? Unknown without injection |
| DynamoDB throttling | Persistent cache and user sessions live in DynamoDB | Could cascade to auth failures + data failures simultaneously |
| Concurrent cold tickers | 100 users querying different uncached tickers | Tiingo rate limit (500/hr), thundering herd on DynamoDB writes |
| Circuit breaker activation | Never triggered in testing -- 5 consecutive failures required | Unknown if recovery works, unknown if fail-open behavior is correct |
| Authenticated user paths | Only anonymous auth tested | JWT validation, session refresh, CSRF -- all untested under trace inspection |
| SSE streaming endpoint | Not tested at all | Different Lambda, different transport, different failure modes |
| Amplify CDN cache | Frontend static assets cached at edge | Stale JavaScript after deploy (already happened -- Layer 13) |

## Chaos Injection Readiness Assessment

**CONDITIONALLY READY.** The system functions and the OHLC path is well-understood. However, the following gaps will confound chaos results:

- **Sentiment Data Source**: SYNTHETIC DATA CONFIRMED. 8 points, deterministic=True, external_calls=0, trace=0ms. Code review: sh
- **Observability Header Audit**: OHLC: x-cache-source=YES, x-cache-age=YES, x-amzn-trace-id=YES, x-amzn-requestid=YES. Sentiment: x-c

**Recommendation:** Proceed with chaos injection on the OHLC path only (Tiingo failure, DynamoDB throttle). Do NOT chaos-test the sentiment path until it has real data and observability. Injecting failures into a synthetic endpoint proves nothing.

## Methodology

This audit combines automated HTTP testing with code-review-informed assertions:

1. **Cold start measurement** -- health check without pre-warming, trace Init segment detection
2. **Data correctness** -- candle count vs trading days, date range recency, price/volume sanity
3. **Sentiment investigation** -- determinism test (same request twice), trace depth, code review confirmation
4. **Tier 1 cache** -- 3 rapid sequential requests (<500ms apart) to test in-memory hit
5. **Auth failure** -- deliberately invalid token, verify 401/403 response
6. **Input validation** -- SQL injection, XSS, boundary values, invalid parameters
7. **Header audit** -- verify observability headers present on all endpoint types

```bash
# Re-run:
COLD_TICKER=AMC python scripts/trace_inspection_v3.py
```
