# Caches

> **QUARRYSOME**: unaudited; verify against code before trusting.

Every cache in the system: what it holds, how it expires, how it evicts, how it fails. One
section per cache. Code references are to the current tree; where a claim was ported from an
older document without re-verification it is marked (ported, unverified).

## Cross-cutting machinery

- **TTL jitter**: `jittered_ttl()` in `src/lib/cache_utils.py` adds random jitter of ±10% by
  default (`CACHE_JITTER_PCT`, default `0.1`) to prevent thundering-herd expiry. Nearly every
  in-memory cache below stores its jittered TTL alongside the entry.
- **CloudWatch stats**: caches register a `CacheStats` (`src/lib/cache_utils.py:65`) with the
  global `CacheMetricEmitter`. The emitter batches all registered caches into one flush every
  60 seconds (`CACHE_METRICS_FLUSH_INTERVAL`), emitting metrics named `Cache/<Metric>` with
  dimension `Cache=<name>`. Emission failures are swallowed; metrics never break a request.
- **Eviction shapes**: most dict-based caches evict the entry with the **oldest write
  timestamp** when full (`min()` over stored timestamps). That is insertion-age eviction, not
  LRU; a hot entry written long ago is evicted before a cold one written recently. The SSE
  `ResolutionCache` is the exception and does true LRU.

## OHLC L1: in-memory response cache (dashboard Lambda)

`src/lambdas/dashboard/ohlc.py:59-190`. Module-level dict caching full OHLC response payloads
in the dashboard Lambda's warm global scope.

- **Key**: `ohlc:{TICKER}:{resolution}:{range}:{end_date}`; custom ranges carry both dates
  (`_get_ohlc_cache_key`, `ohlc.py:80-114`). Day-anchoring on `end_date` prevents cross-day
  staleness for named ranges.
- **TTL per resolution** (`OHLC_CACHE_TTLS`, `ohlc.py:60-68`), jittered on write:

  | Resolution | TTL |
  |---|---|
  | 1m | 300s |
  | 5m / 15m / 30m | 900s |
  | 60m | 1800s |
  | D | 3600s |
  | fallback | 300s (`OHLC_CACHE_DEFAULT_TTL`) |

- **Bound**: `OHLC_CACHE_MAX_ENTRIES` env var, default 256. Eviction removes the
  oldest-written entry and increments an `evictions` counter (`ohlc.py:157-161`).
- **Invalidation**: `invalidate_ohlc_cache(ticker | None)` clears one ticker's entries by key
  prefix, or everything (`ohlc.py:171-189`).
- **Stats**: local hit/miss/eviction counters via `get_ohlc_cache_stats()`, plus a
  `CacheStats(name="ohlc_response")` registered with the global emitter.

## OHLC L2: DynamoDB persistent cache

`src/lambdas/shared/cache/ohlc_cache.py`, table `{env}-ohlc-cache` (`OHLC_CACHE_TABLE` env
var, else `{ENVIRONMENT}-ohlc-cache`; terraform at
`infrastructure/terraform/modules/dynamodb/main.tf:594`, PITR and `prevent_destroy` on).
Write-through: the dashboard Lambda reads here on an L1 miss, then falls back to the adapter
and writes fetched candles back synchronously.

- **Schema**: `PK = {TICKER}#{source}` (e.g. `AAPL#tiingo`), `SK = {resolution}#{ISO8601 UTC}`
  (`_build_pk`/`_build_sk`, `ohlc_cache.py:131-144`). Prices quantized to 4 decimals on write
  (`ohlc_cache.py:316-319`). Items carry `fetched_at` and a `ttl` attribute.
- **TTL** (`_compute_ttl`, `ohlc_cache.py:76-107`), stored in the DynamoDB TTL attribute
  `ttl`: daily resolution 90 days; intraday batches containing any current-day candle 5
  minutes; intraday historical 90 days. Mixed batches take the shortest TTL because TTL is
  computed per batch, not per item. "Today" is evaluated in **UTC**, so between 4 PM ET and
  midnight UTC, finalized intraday data still gets the 5-minute TTL.
- **Read gate**: a query hit is discarded and treated as a miss when returned candles cover
  less than 80% of the expected count for the range (`ohlc.py:307-319`).
- **Expired items are served**: `get_cached_candles` queries by key range only, with no filter
  on `ttl` (`ohlc_cache.py:212-225`; the projection does not even fetch `ttl`). DynamoDB TTL
  reaping is asynchronous, so expired-but-unreaped items come back as normal hits until the
  reaper deletes them.
- **Writes**: `BatchWriteItem` in chunks of 25, up to 3 retries with exponential backoff (base
  100ms) on unprocessed items, then `RuntimeError` (`ohlc_cache.py:326-360`).
- **Never caches errors or empty results**: writes happen only inside successful-fetch
  branches (`ohlc.py:721-824`), an empty candle list returns 0 without writing
  (`ohlc_cache.py:297-298`), and empty responses early-return upstream (`ohlc.py:221-223`).
- **Failure behavior**: read failure logs ERROR and falls through to the live API with
  `X-Cache-Source: live-api-degraded` and `X-Cache-Error`; write failure is non-fatal and sets
  `X-Cache-Write-Error: true` (`ohlc.py:663-706, 728-743`).
- **Response headers** (`_build_cache_headers`, `ohlc.py:422-448`): `X-Cache-Source` is one of
  `in-memory`, `persistent-cache`, `live-api`, `live-api-degraded`, plus `X-Cache-Age`, and
  the error headers above.
- `cache_expires_at` on responses comes from `get_cache_expiration()`
  (`src/lambdas/shared/utils/market.py:12`), which expires at the next market open or close.

## Tiingo adapter response cache

`src/lambdas/shared/adapters/tiingo.py:27-77`. In-memory dict keyed by MD5 of endpoint plus
params, caching raw API responses across warm invocations. Bound: 100 entries
(`_MAX_CACHE_ENTRIES`), oldest-write eviction. Jittered TTLs. Registers
`CacheStats(name="tiingo")`.

| Endpoint | TTL | Config |
|---|---|---|
| News | 1800s | `API_CACHE_TTL_NEWS_SECONDS` |
| Daily OHLC | 3600s | `API_CACHE_TTL_OHLC_SECONDS` |
| Intraday OHLC (IEX) | 300s | hardcoded in `get_intraday_ohlc` |

Empty responses are never cached (404s return `[]`). The intraday path uses its own 300s TTL,
so this cache does not undercut the L2 5-minute intraday TTL. Daily OHLC can be served up to
an hour stale from here regardless of the L1 daily TTL, since both are 3600s and this one sits
below L1.

## Finnhub adapter response cache

`src/lambdas/shared/adapters/finnhub.py:28-80`. Same shape as the Tiingo cache: MD5-keyed
dict, 100-entry bound, oldest-write eviction, jittered TTLs. News and sentiment 1800s
(`API_CACHE_TTL_NEWS_SECONDS`, `API_CACHE_TTL_SENTIMENT_SECONDS`), OHLC 3600s
(`API_CACHE_TTL_OHLC_SECONDS`).

## Sentiment history cache (shared)

`src/lambdas/shared/cache/sentiment_cache.py`. In-memory tier over DynamoDB for sentiment
history; there is no live-API tier because sentiment is populated by background ingestion.
Consumed by the dashboard sentiment-history path (`src/lambdas/dashboard/ohlc.py:1026-1033`,
write-back at `ohlc.py:1142`).

- **Key**: `{ticker}:{source}:{start_date}:{end_date}`.
- **TTL**: 300s jittered.
- **No size bound**: the dict has no max-entries check. Entries leave only via expiry-on-read
  or `clear_cache()`. Growth is bounded in practice by the key space of queried ranges.
- **Stats**: `CacheStats(name="sentiment_history")`, registered with the global emitter.

## Sentiment response cache (dashboard)

`src/lambdas/dashboard/sentiment.py:40-100`. In-memory cache of aggregated sentiment
responses keyed by config, tickers, and resolution. TTL 300s (`SENTIMENT_CACHE_TTL`),
jittered, matching the frontend's 5-minute refresh interval. Bound 50 entries
(`SENTIMENT_CACHE_MAX_ENTRIES`), oldest-write eviction.

## Metrics cache (dashboard)

`src/lambdas/dashboard/metrics.py:52-95`. In-memory cache of GSI query results. TTL 300s
(`METRICS_CACHE_TTL`), jittered. Bound 100 entries (`METRICS_CACHE_MAX_ENTRIES`),
oldest-write eviction. On DynamoDB failure the handler serves whatever is still within TTL;
expired entries are misses and the query is retried (ported, unverified beyond the TTL path).

## Configuration cache (dashboard)

`src/lambdas/dashboard/configurations.py:52-160`. Two in-memory caches: per-user
configuration lists and single configurations. TTL 60s (`CONFIG_CACHE_TTL`), jittered. List
cache bounded to 100 users (`CONFIG_CACHE_MAX_USERS`), oldest-write eviction. Explicitly
invalidated on create, update, and delete (`_invalidate_user_config_cache`,
`configurations.py:141+`); the list cache is always invalidated because counts may change.

## Ticker cache (S3)

`src/lambdas/shared/cache/ticker_cache.py`. Single-entry cache of the ~8K US symbol list from
`s3://<bucket>/ticker-cache/us-symbols.json`, held in Lambda global scope behind a lock.

- **TTL**: 300s (`TICKER_CACHE_TTL`), jittered. On expiry it HEADs the S3 object and compares
  ETags; unchanged means reset the timer without downloading, changed means download,
  validate the new list is non-empty, then swap.
- **Failure**: fail-open. On S3 failure it records a refresh failure in
  `CacheStats(name="ticker")`, logs a warning, and serves the stale list indefinitely, retrying
  on the next TTL cycle (`ticker_cache.py:311-319`).
- **Recovery when users report missing tickers**: confirm the S3 object exists
  (`aws s3 ls s3://<bucket>/ticker-cache/us-symbols.json`), check Lambda IAM for
  `s3:GetObject` and `s3:HeadObject`, and force refresh by cycling Lambda containers with a
  no-op deploy. Impact is cosmetic; existing tickers keep working.

## SSE ResolutionCache

`src/lib/timeseries/cache.py`. In-memory cache of time-series sentiment data in the SSE
Lambda's global scope, singleton via `get_global_cache()`.

- **Key**: `(ticker, Resolution)`.
- **TTL equals the resolution's duration**, jittered (`cache.py:155`): 1m data expires after
  60s, 5m after 300s, up to 24h after 86400s. Once a time bucket closes its data is stable, so
  longer resolutions safely carry longer TTLs.
- **Eviction**: true LRU. Hits move the entry to the end of an `OrderedDict`; at capacity the
  front entry is popped (`cache.py:127-150`). Bound 256 entries (`max_entries` constructor
  arg, `cache.py:91`). 256 supports 13 tickers across 6 resolutions with room for multiple
  ranges; more tickers need a larger bound.
- **Expiry on read**: an expired entry is deleted and counted as a miss.
- **Stats and emission**: `CacheStats` with `hit_rate`. `CacheMetricsLogger` emits structured
  `event_type="cache_metrics"` log lines every 60 seconds
  (`src/lambdas/sse_streaming/stream.py:176`), and cold-start metrics are logged at connection
  time (`stream.py:184`).

### Hit-rate target (SC-008)

Target is a hit rate above 80% in steady state, **excluding roughly the first 30 seconds after
a cold start**. A cold Lambda starts empty; expect near-0% initially, warming through ~50-70%
in the first half minute before stabilizing. E2E measurement excludes that window.

### Logs Insights queries

The SSE Lambda's log group is `/aws/lambda/{env}-sentiment-sse-streaming` (function name from
`infrastructure/terraform/main.tf:645`). Substitute the environment prefix when querying.

Aggregate hit rate:

```
fields @timestamp, hit_rate, hits, misses
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate,
        sum(hits) as total_hits,
        sum(misses) as total_misses
        by bin(1h)
| sort @timestamp desc
| limit 24
```

Low hit-rate detection:

```
fields @timestamp, hit_rate, is_cold_start, trigger
| filter event_type = "cache_metrics" and hit_rate < 0.80
| sort @timestamp desc
| limit 100
```

Cold vs warm comparison:

```
fields @timestamp, hit_rate, is_cold_start
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate by is_cold_start
```

### Troubleshooting hit rate below 80%

Work the causes in this order.

1. **Cold starts.** `stats count() by is_cold_start` over `cache_metrics`. Many cold starts
   drag the average; consider provisioned concurrency.
2. **Utilization.** `stats max(entry_count) as peak`. Peak at `max_entries` means the cache is
   full and evicting; raise `max_entries` (constructor default at `cache.py:91`).
3. **Per-ticker skew.** `stats avg(hit_rate) by ticker | sort hit_rate asc`. One low ticker
   points to an unusual access pattern for that ticker, not a cache problem.
4. **Time of day.** `stats avg(hit_rate) by bin(1h)`. Low rates off-hours are expected; fewer
   users means less cache sharing.

If metrics are missing entirely: confirm the log group name above, confirm `stream.py` imports
`CacheMetricsLogger` from `cache_logger`, and spot-check with
`filter @message like /cache_metrics/`.

## Secrets cache

`src/lambdas/shared/secrets.py`. In-memory cache of Secrets Manager values, TTL 300s
(`SECRETS_CACHE_TTL_SECONDS`, default `DEFAULT_CACHE_TTL_SECONDS = 300`). Fail-closed: once an
entry expires there is no stale-serving grace; a failed fetch raises immediately
(`SecretNotFoundError`, `SecretAccessDeniedError`, or `SecretRetrievalError`,
`secrets.py:180-217`). `force_refresh=True` bypasses the cache. Auth uses self-issued HMAC
JWTs (`JWT_SECRET`), not Cognito JWKS, so there is no JWKS cache; if `JWT_SECRET` is
unavailable all auth fails immediately.

## Quota tracker cache

`src/lambdas/shared/quota_tracker.py`. In-memory read cache of the DynamoDB-backed quota
tracker, TTL 10s (`QUOTA_TRACKER_CACHE_TTL`), jittered, guarded by an `RLock`. Failure policy
is fail-conservative: after 3 consecutive DynamoDB failures it enters reduced-rate mode at 25%
of the normal API call rate (`REDUCED_RATE_FRACTION`), and exits after 5 consecutive
successes. Reads during an outage use the last cached count at the current rate.

Recovery when the tracker disconnects (ported, unverified): check DynamoDB table health
(`aws dynamodb describe-table`), check throttling metrics, then Lambda IAM for
`dynamodb:UpdateItem`. Instances exit reduced-rate mode automatically on the next successful
write. Impact during the outage is slower data updates, not an outage.

## Circuit breaker state cache

`src/lambdas/shared/circuit_breaker.py`. In-memory cache of per-service breaker state, TTL 60s
(`CIRCUIT_BREAKER_CACHE_TTL`), jittered, lock-guarded, deep-copied on read to prevent shared
mutable state. When DynamoDB is unreachable the breaker defaults to **closed** and allows
traffic (fail-open, `circuit_breaker.py:399-406`); the failure is logged with
`state_source: default_fail_open`. Registers `CacheStats(name="circuit_breaker")`.

## Client side (customer dashboard)

TanStack Query `staleTime` is 5 minutes (`STALE_TIME_MS`,
`frontend/src/lib/constants.ts:11`), matching `REFRESH_INTERVAL_SECONDS = 300`
(`constants.ts:9`) and the server-side sentiment TTLs. Chart hooks expose `isStale` for the
"data from X min ago" indicator. Whether OHLC responses also set `Cache-Control: no-store` is
unverified.

## What is not cached

SSE live updates are deliberately uncached. The streaming path exists to deliver fresh data;
caching it would defeat the freshness requirement it serves. The `ResolutionCache` above sits
under the SSE Lambda's historical/aggregate reads, not the live update stream.

## Sharp edges

Current behavior worth knowing before touching TTLs.

- L2 `_compute_ttl` evaluates "today" in UTC (`ohlc_cache.py:101`), so finalized post-close
  intraday data gets a 5-minute TTL between 4 PM ET and midnight UTC.
- L2 readers serve expired-but-unreaped items as hits (no `ttl` filter on query).
- Today's forming daily bar is written with the 90-day TTL during market hours; only the L1
  1-hour daily TTL and `cache_expires_at` bound its staleness.
- The shared sentiment history cache has no entry bound.
- Two `is_market_open` implementations exist (`ohlc_cache.py:157` and
  `shared/utils/market.py:63`); `shared/cache/__init__.py` exports the `ohlc_cache` one.
