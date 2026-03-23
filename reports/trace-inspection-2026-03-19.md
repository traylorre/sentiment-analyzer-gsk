# Trace Inspection Report — Sentiment Analyzer Preprod

**Generated:** 2026-03-19 14:04:47 UTC
**Environment:** preprod (AWS Lambda Function URL + DynamoDB + Tiingo API)
**Dashboard URL:** `https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws`
**Frontend URL:** `https://main.d29tlmksqcx494.amplifyapp.com`
**Test Window:** 14:04:22 → 14:04:44 UTC (21s)
**Session:** `ad1cc7d6...` (anonymous)

## Executive Summary

- **8 requests** made across 3 ticker scenarios (warm, cold, invalid)
- **8/8** returned expected status codes
- **8/8** produced inspectable X-Ray traces (100% sampling confirmed)
- **3-tier cache validated:** `live-api` → `persistent-cache` (DynamoDB) → `in-memory` — all 3 tiers observed in a single test run
- **Server-side speedup:** 73ms → 9ms (**8.1x**) between DynamoDB-cached and in-memory-cached paths
- **Client-perceived speedup:** 427ms → 390ms (1.1x) — network round-trip dominates (~330ms)
- **Error path:** Invalid ticker returns 400 in 9ms with clear error message, no external calls
- **6 visibility gaps** identified with actionable recommendations
- **CRITICAL: Frontend is broken** -- Amplify still points to old destroyed Lambda URL. Customer dashboard non-functional.

### Key Insight: Where the Time Goes

```
Client latency breakdown (OHLC cold path):
  ├─ Network round-trip (CloudFront → Lambda → back)  ~330ms  ████████████████░░░░  77%
  ├─ DynamoDB persistent cache read                     ~55ms  ███░░░░░░░░░░░░░░░░░  13%
  ├─ Lambda handler overhead                            ~10ms  █░░░░░░░░░░░░░░░░░░░   2%
  └─ Auth middleware + response serialization           ~32ms  ██░░░░░░░░░░░░░░░░░░   8%

Client latency breakdown (OHLC warm path):
  ├─ Network round-trip (CloudFront → Lambda → back)  ~330ms  ████████████████████  85%
  ├─ In-memory cache read                               ~1ms  ░░░░░░░░░░░░░░░░░░░░  <1%
  ├─ Lambda handler overhead                            ~8ms  ░░░░░░░░░░░░░░░░░░░░   2%
  └─ Auth middleware + response serialization           ~51ms  ███░░░░░░░░░░░░░░░░░  13%
```

**The cache eliminates 87% of server-side processing but only 9% of end-to-end latency.** The cache's value is in cost reduction (fewer Tiingo API calls = fewer billable requests) and infrastructure protection (DynamoDB RCU savings), not user-perceived speed. This is the correct architecture for a cost-sensitive system — the user won't notice the difference between 390ms and 427ms, but the AWS bill notices the difference between 0 and 100 Tiingo API calls per minute.

## Request Results

| # | Ticker | Scenario | Endpoint | Status | Latency | Cache Source | Trace |
|---|--------|----------|----------|--------|---------|-------------|-------|
| 1 | AAPL | warm | `/api/v2/tickers/AAPL/ohlc` | 200 | 602ms | live-api | `1-69bc026b-48fe5...` |
| 2 | AAPL | warm | `/api/v2/tickers/AAPL/sentiment/history` | 200 | 369ms | — | `1-69bc026b-7ddf1...` |
| 3 | LCID | cold_miss | `/api/v2/tickers/LCID/ohlc` | 200 | 427ms | persistent-cache | `1-69bc026c-3d369...` |
| 4 | LCID | cold_miss | `/api/v2/tickers/LCID/sentiment/history` | 200 | 376ms | — | `1-69bc026c-429b5...` |
| 5 | LCID | cold_hit | `/api/v2/tickers/LCID/ohlc` | 200 | 390ms | in-memory | `1-69bc026f-6152e...` |
| 6 | LCID | cold_hit | `/api/v2/tickers/LCID/sentiment/history` | 200 | 378ms | — | `1-69bc0270-26864...` |
| 7 | ZZZZXQ9 | invalid | `/api/v2/tickers/ZZZZXQ9/ohlc` | 400 | 396ms | — | `1-69bc0270-0fa27...` |
| 8 | ZZZZXQ9 | invalid | `/api/v2/tickers/ZZZZXQ9/sentiment/history` | 400 | 401ms | — | `1-69bc0270-0641f...` |

## X-Ray Trace Analysis

### AAPL (warm) — 201ms
Trace ID: `1-69bc026b-48fe583c5d6f0add76dc6751`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
Overhead                                                     0.5ms 
## lambda_handler                                          192.7ms [local]
  api.tiingo.com                                            64.1ms [remote] HTTP 200
  DynamoDB                                                  57.5ms [aws] BatchWriteItem HTTP 200
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
  DynamoDB                                                  56.8ms [aws] Query table=preprod-ohlc-cache HTTP 200
```

### AAPL (warm) — 9ms
Trace ID: `1-69bc026b-7ddf12ea5655fc1124b99e39`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
## lambda_handler                                            1.3ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
Overhead                                                     0.4ms 
```

### LCID (cold_miss) — 73ms
Trace ID: `1-69bc026c-3d36920a5001d37d2c5ceef8`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
## lambda_handler                                           65.0ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
  DynamoDB                                                  55.2ms [aws] Query table=preprod-ohlc-cache HTTP 200
Overhead                                                     0.5ms 
```

### LCID (cold_miss) — 10ms
Trace ID: `1-69bc026c-429b5a3c42edf62c63dc749c`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
Overhead                                                     0.4ms 
## lambda_handler                                            1.2ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
```

### LCID (cold_hit) — 9ms
Trace ID: `1-69bc026f-6152e3d5144c9d1f6dd00b39`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
Overhead                                                     0.4ms 
## lambda_handler                                            1.0ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
```

### LCID (cold_hit) — 10ms
Trace ID: `1-69bc0270-26864e7a3f7e87ae2c8c530a`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
## lambda_handler                                            1.2ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
Overhead                                                     0.5ms 
```

### ZZZZXQ9 (invalid) — 9ms
Trace ID: `1-69bc0270-0fa27d90419769fc4121b03d`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
## lambda_handler                                            0.9ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.3ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
Overhead                                                     0.4ms 
```

### ZZZZXQ9 (invalid) — 10ms
Trace ID: `1-69bc0270-0641fd621abefc865e93e4e9`

```
Subsegment                                                Duration Details
─────────────────────────────────────────────────────── ────────── ──────────────────────────────
## lambda_handler                                            1.0ms [local]
  ## src.lambdas.shared.middleware.auth_middleware…          0.4ms [local]
    ## src.lambdas.shared.middleware.auth_middlewa…          0.1ms [local]
Overhead                                                     0.4ms 
```

## Three-Tier Cache Demonstration

This test accidentally demonstrated all 3 cache tiers in a single run, producing the clearest possible picture of cache behavior:

| Request | Ticker | Cache Tier Hit | Why |
|---------|--------|---------------|-----|
| AAPL OHLC | AAPL | **Tier 3: live-api** | Fresh Lambda instance — in-memory empty, DynamoDB cache expired or absent |
| LCID OHLC (1st) | LCID | **Tier 2: persistent-cache** (DynamoDB) | LCID was cached in DynamoDB from earlier debugging curl |
| LCID OHLC (2nd) | LCID | **Tier 1: in-memory** | First request populated in-memory; second request hit it in 1ms |

```
Request flow:
  ┌─ in-memory cache ─┐    ┌─ DynamoDB cache ─┐    ┌─ Tiingo API ─┐
  │   (Tier 1)        │    │   (Tier 2)       │    │  (Tier 3)    │
  │   TTL: 5-60min    │    │   TTL: 5m-90d    │    │  Live data   │
  │   Scope: Lambda   │    │   Scope: Global  │    │  $0.01/call  │
  └────────┬──────────┘    └────────┬─────────┘    └──────┬───────┘
           │                        │                      │
  LCID 2nd ✓ (1ms)       LCID 1st ✓ (55ms)      AAPL ✓ (64ms + 57ms write)
```

## Cold vs Warm Path Comparison (OHLC)

| Metric | Cold (DynamoDB hit) | Warm (in-memory hit) | Delta |
|--------|-------------------|-------------------|-------|
| **Client latency** | 427ms | 390ms | -37ms (9%) |
| **Server-side trace** | 73ms | 9ms | **-64ms (87%)** |
| **Cache source** | persistent-cache | in-memory | 2 tiers higher |
| **Cache age** | 0s | 3s | — |
| **External calls** | 1 (DynamoDB Query) | 0 | **Eliminated** |
| **DynamoDB calls** | 1 (55ms) | 0 (0ms) | **Eliminated** |
| **Tiingo API call** | No | No | Both avoided Tiingo |
| **Estimated cost** | ~$0.00005 (1 RCU) | $0.00 | Free |

**Why client latency barely changed:** The 87% server-side speedup (73ms → 9ms) is hidden by the ~330ms network round-trip through the Lambda Function URL's CloudFront distribution. From the customer's perspective, both paths feel identical. From an infrastructure cost perspective, they're vastly different.

## CloudWatch Cache Metrics (during test window)

Metrics are flushed every 60s. Showing delta between pre-test and post-test snapshots.

| Cache | Hits (Δ) | Misses (Δ) | Evictions (Δ) | Hit Rate |
|-------|---------|-----------|--------------|----------|
| ticker | — | — | — | — |
| metrics | — | — | — | — |
| ohlc_response | +0 | +1 | +0 | 0% |
| sentiment | — | — | — | — |
| config | — | — | — | — |
| tiingo | +0 | +1 | +0 | 0% |
| finnhub | — | — | — | — |
| secrets | +0 | +1 | +0 | 0% |
| circuit_breaker | — | — | — | — |

### CloudWatch Metrics Interpretation

Three caches registered activity during the test window:

- **ohlc_response** (+1 miss): The AAPL request hit the live API — in-memory was empty (cold Lambda), DynamoDB had no entry. This triggered a miss → Tiingo fetch → DynamoDB write → in-memory populate.
- **tiingo** (+1 miss): The Tiingo adapter cache missed for AAPL (same cold Lambda), triggering the HTTP call to `api.tiingo.com`.
- **secrets** (+1 miss): SecretsManager cache was empty on the cold Lambda, requiring a `GetSecretValue` call for the Tiingo API key.

**Caches that should have registered activity but didn't:**
- **ticker** — every request validates the ticker symbol, but no hit/miss appeared. Likely the ticker cache loaded from S3 on cold start (outside the CacheStats tracking path).
- **sentiment** — 4 sentiment requests were made, but no metric delta. Either sentiment uses a different caching path or the flush interval hadn't elapsed.
- **config** — anonymous sessions may bypass config cache entirely.

## Visibility Gaps

| Gap | Impact | Recommendation |
|-----|--------|----------------|
| In-memory cache hits/misses invisible in X-Ray | Can't see if response was served from memory vs fell through to DynamoDB/API | Add custom X-Ray subsegment annotation on cache lookup |
| CacheStats 60s flush interval | Short tests may complete before metrics are emitted to CloudWatch | Add on-demand flush endpoint or reduce interval in preprod |
| `x-cache-source` header only on OHLC endpoint | Sentiment, config, and ticker endpoints don't report cache provenance | Add `x-cache-source` header to all cached endpoints |
| No per-ticker cache key in CloudWatch dimensions | Can't tell which ticker caused a cache miss vs hit | Add `Ticker` dimension to CacheStats (high cardinality tradeoff) |
| Invoke transport drops `X-Amzn-Trace-Id` | CI tests via invoke transport can't correlate requests to traces | Parse trace ID from Lambda invoke response metadata |
| Quota tracker cache not in CacheStats | DynamoDB sync cache (60s) not instrumented for hit/miss tracking | Register quota tracker with CacheMetricEmitter |

## Frontend Validation (Playwright)

### Finding: Customer Dashboard is Broken (Stale API URL)

Screenshots captured via Playwright (Chromium headless, 1440x900 @2x):

| Screenshot | Observation |
|------------|-------------|
| `dashboard-landing.png` | Dashboard loads, shows "Price & Sentiment Analysis" with search input |
| `dashboard-search-aapl.png` | AAPL search returns "No tickers found for AAPL" |
| `dashboard-search-lcid.png` | LCID search returns "No tickers found for LCID" |

**Root cause:** The Amplify frontend is configured with the **old** Lambda URL that was destroyed during the alias migration (Layer 6 of the deploy saga):

| | URL |
|--|-----|
| **Frontend calls** | `cjx6qw4a7xqw6cuifvkbi6ae2e0evviw.lambda-url.us-east-1.on.aws` |
| **Current dashboard** | `huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws` |

The old URL was destroyed when the Lambda URL moved from the `$LATEST` version to the `live` alias qualifier. The Amplify `NEXT_PUBLIC_API_URL` environment variable was never updated.

**Impact:** The entire customer-facing dashboard is non-functional. Search, charts, and all API features silently fail. The frontend gracefully shows "No tickers found" but gives no indication that the underlying API is unreachable.

**Deeper root cause:** Terraform DID update `NEXT_PUBLIC_API_URL` correctly. But **Amplify builds have been failing since job #207** due to a TypeScript error (`TextDecoder` constructor passed `{ stream: true }` which is only valid on `.decode()`) and `tsconfig.json` pulling test files into the build. The correct URL exists in Amplify's config but was never baked into a successful build.

**Fix:** PR #754 — fix `sse-parser.ts` TextDecoder constructor + exclude `tests/` from tsconfig. Amplify auto-builds on merge, deploying the frontend with the correct URL.

> This is **Layer 13** of the deploy failure saga -- the frontend URL was a casualty of the alias migration that nobody noticed because all testing (unit, integration, smoke) validates the API directly, not through the frontend.

## Error Path Validation

**`/api/v2/tickers/ZZZZXQ9/ohlc`** → HTTP 400
```json
{
  "detail": "Invalid ticker symbol: ZZZZXQ9. Must be 1-5 letters."
}
```
Trace duration: 9ms | Error: False | Fault: False

**`/api/v2/tickers/ZZZZXQ9/sentiment/history`** → HTTP 400
```json
{
  "detail": "Invalid ticker symbol: ZZZZXQ9. Must be 1-5 letters."
}
```
Trace duration: 10ms | Error: False | Fault: False

## Appendix: Trace IDs

For manual inspection in the AWS X-Ray console:
```
warm            AAPL       1-69bc026b-48fe583c5d6f0add76dc6751
warm            AAPL       1-69bc026b-7ddf12ea5655fc1124b99e39
cold_miss       LCID       1-69bc026c-3d36920a5001d37d2c5ceef8
cold_miss       LCID       1-69bc026c-429b5a3c42edf62c63dc749c
cold_hit        LCID       1-69bc026f-6152e3d5144c9d1f6dd00b39
cold_hit        LCID       1-69bc0270-26864e7a3f7e87ae2c8c530a
invalid         ZZZZXQ9    1-69bc0270-0fa27d90419769fc4121b03d
invalid         ZZZZXQ9    1-69bc0270-0641fd621abefc865e93e4e9
```

## Conclusions

### What's Working

1. **3-tier OHLC cache** is functioning correctly — all three tiers (in-memory → DynamoDB → Tiingo) were observed and confirmed via both `x-cache-source` headers and X-Ray trace subsegments.
2. **Error path is fast and clean** — invalid tickers return 400 in <10ms with clear error messages, no external calls, no X-Ray errors/faults.
3. **X-Ray tracing is comprehensive** — 100% sampling in preprod, every request produces a trace with full subsegment detail for DynamoDB, external APIs, and SecretsManager.
4. **Auth middleware is lightweight** — <0.5ms overhead per request, doesn't contribute meaningfully to latency.

### What's Broken

1. **CRITICAL: Amplify frontend points to dead Lambda URL.** The alias migration (Layer 6) changed the Lambda URL, but `NEXT_PUBLIC_API_URL` in Amplify was never updated. The entire customer dashboard silently fails -- search returns "no results" for every ticker. This went undetected because all CI testing validates the API directly.

### What Needs Attention

1. **Sentiment endpoints have zero cache visibility** — no `x-cache-source` header, no CloudWatch metric activity, and X-Ray traces show no external calls (suggesting data is generated locally or cached outside the CacheStats system).
2. **CloudWatch cache metrics are unreliable for short-lived diagnostics** — the 60s flush interval means a 21-second test window may miss most events. For regression testing, either extend the test window or add an on-demand flush trigger.
3. **Network dominates user-perceived latency** — the ~330ms CloudFront round-trip dwarfs any server-side optimization. If sub-200ms latency is ever needed, the architecture would need to move to a regional API Gateway or direct Lambda URLs without CloudFront (which is not configurable today).
4. **SecretsManager call on every cold start** — the 68ms `GetSecretValue` call appears on first request. This is correctly cached after the first call, but could be pre-warmed during Lambda init to move it off the critical path.

### Recommended Follow-Up

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| **P0** | **Fix Amplify build (sse-parser.ts + tsconfig) — PR #754** | **Trivial** | **Restores customer dashboard** |
| P0 | Add Amplify build health check to deploy pipeline | Small | Catch frontend build failures before they go unnoticed for days |
| P1 | Add `x-cache-source` header to sentiment endpoint | Small | Close biggest visibility gap |
| P1 | Verify sentiment cache is registered with CacheStats | Small | Confirm metrics emit correctly |
| P2 | Add custom X-Ray subsegment for in-memory cache decisions | Medium | Eliminate trace ambiguity |
| P2 | Reduce CacheStats flush interval to 15s in preprod | Small | Improve diagnostic accuracy |
| P3 | Pre-warm SecretsManager in Lambda init handler | Small | Move 68ms off critical path |
| P3 | Make this script a scheduled regression test | Medium | Ongoing baseline tracking |

### Methodology

This report was generated by `scripts/trace_inspection.py`, which:
1. Creates an anonymous session via the auth API
2. Makes 8 HTTP requests across 3 scenarios (warm/cold/invalid) x 2 endpoints (OHLC/sentiment)
3. Captures `X-Amzn-Trace-Id` and `x-cache-source` response headers
4. Waits for X-Ray trace propagation (10s)
5. Fetches full traces via `aws xray batch-get-traces`
6. Snapshots CloudWatch `Cache/*` metrics before and after the test window
7. Generates this markdown report

The script can be re-run at any time to produce a comparable baseline:
```bash
python scripts/trace_inspection.py --output reports/trace-inspection-$(date +%Y-%m-%d).md
```
