# Candlestick (OHLC) Data Behaviour

> **CANON**: verified against code.

How OHLC data actually behaves on the live path. The endpoint is
`GET /api/v2/tickers/{ticker}/ohlc` (`src/lambdas/dashboard/ohlc.py:479`). Both dashboards
consume this same endpoint: the customer dashboard through
`frontend/src/lib/api/ohlc.ts:42`, the admin dashboard through `src/dashboard/ohlc.js:257`
(base path in `src/dashboard/config.js:41`).

## Resolutions and limits

`OHLCResolution` accepts `1`, `5`, `15`, `30`, `60`, `D`
(`src/lambdas/shared/models/ohlc.py:44-49`). Each resolution caps the queryable window via
`RESOLUTION_MAX_DAYS` (`src/lambdas/shared/models/ohlc.py:62-69`):

| Resolution | Max days |
|---|---|
| 1 | 7 |
| 5 | 30 |
| 15 | 90 |
| 30 | 90 |
| 60 | 180 |
| D | 365 |

A wider request is not rejected. The handler silently moves `start_date` forward so the
window fits the cap (`src/lambdas/dashboard/ohlc.py:602-605`).

Tiingo serves every resolution: the daily endpoint for `D`, the IEX endpoint for intraday
(`ohlc.py:713-754`). When an intraday fetch returns nothing, the handler falls back to daily
and marks the response with `resolution_fallback: true` and a `fallback_message`; the
`resolution` field then reports `D`, not what was asked
(`ohlc.py:784-791`, response fields at `ohlc.py:880-882`). When daily also returns nothing,
the response is a 404, still carrying the `X-Cache-*` headers (`ohlc.py:826-838`).

## Locked vs forming bars

Closed intervals are immutable; today's bars are still forming. The system has no realtime
path and no forming-bar flag: the DynamoDB item holds only PK, SK, the four prices, volume,
`fetched_at`, and `ttl` (`src/lambdas/shared/cache/ohlc_cache.py:313-323`). Forming bars are
handled purely by short-TTL overwrite: writes are plain puts that replace existing items
(`ohlc_cache.py:286`), so a re-fetch of today's data overwrites the forming bar in place.

`_compute_ttl` (`ohlc_cache.py:76-107`) draws the line:

- Daily resolution: 90-day TTL, always, including today's still-forming daily bar.
- Intraday batch containing any candle from today: 5-minute TTL for the whole batch.
- Intraday batch that is all historical: 90-day TTL.

"Today" here is the UTC date (`ohlc_cache.py:101`), not the exchange's trading day.

## Staleness budget end to end

Three layers, each with its own clock.

**L1, in-memory response cache** (`ohlc.py:60-69`): per-resolution TTLs of 300s (`1`),
900s (`5`/`15`/`30`), 1800s (`60`), 3600s (`D`), jittered on store, LRU-evicted at
`OHLC_CACHE_MAX_ENTRIES` (env var, default 256) (`ohlc.py:147-163`). Keys are day-anchored:
`ohlc:{TICKER}:{res}:{range}:{end_date}`, with custom ranges carrying both dates
(`ohlc.py:104-114`). The anchor makes yesterday's "1W" entry a miss today instead of stale
data.

**L2, DynamoDB** (`{env}-ohlc-cache`, `infrastructure/terraform/modules/dynamodb/main.tf:594`,
TTL attribute `ttl` enabled at `main.tf:618-621`): item TTLs per the `_compute_ttl` rules
above. A read is only served when it covers at least 80% of the candle count estimated for
the window (`ohlc.py:307-319`); a thinner result is treated as a miss and refetched.
Batched writes retry unprocessed items up to 3 times with exponential backoff, then raise
(`ohlc_cache.py:329-360`). Prices are quantized to 4 decimal places on write
(`ohlc_cache.py:316-319`). Error responses and empty candle lists are never cached: L1
stores only successful responses (`ohlc.py:696`, `ohlc.py:895`), write-through no-ops on an
empty list (`ohlc.py:221-223`), and the 404 path caches nothing.

**Response contract**: every success carries `cache_expires_at` from
`get_cache_expiration()` (`src/lambdas/shared/utils/market.py:12`): during market hours it
expires at 4:00 PM ET close, outside them at the next 9:30 AM ET open, skipping weekends.

**Client**: the customer dashboard's TanStack queries use a 5-minute `staleTime`
(`STALE_TIME_MS`, `frontend/src/lib/constants.ts:11`, applied in
`frontend/src/hooks/use-chart-data.ts:49`) and expose `isStale` to the UI
(`use-chart-data.ts:158`).

Net effect: a locked historical bar can be served for up to an hour from L1 and 90 days
from L2 without a refetch. A forming intraday bar is at most ~5 minutes behind at L2, plus
the L1 TTL of its resolution, plus the client's 5 minutes. A forming daily bar is bounded
only by the L1 1-hour TTL and `cache_expires_at`, because its L2 TTL is already 90 days.

## Degradation and the X-Cache-* header contract

`X-Cache-Source` takes exactly four values (`ohlc.py:422-447`, defaults at
`ohlc.py:623-626`):

| Value | Meaning |
|---|---|
| `in-memory` | Served from L1 |
| `persistent-cache` | Served from DynamoDB |
| `live-api` | Fetched from Tiingo, caches missed cleanly |
| `live-api-degraded` | DynamoDB read failed; fetched from Tiingo anyway |

A DynamoDB read failure logs ERROR, sets `live-api-degraded`, puts the error description in
`X-Cache-Error`, and continues to the live API (`ohlc.py:663-683`). A DynamoDB write failure
is non-fatal: the response still succeeds and carries `X-Cache-Write-Error: true`
(`ohlc.py:735-743`). `X-Cache-Age` is real only for `in-memory` hits (`ohlc.py:645-647`);
`persistent-cache` responses report age 0 (`ohlc.py:698-700`).

## Market-calendar behaviour

There is no market calendar. The only calendar logic is weekday arithmetic against fixed
9:30 AM and 4:00 PM ET (`market.py:8-9`); holidays and half-days do not exist anywhere on
the OHLC path, and `is_market_open` in `ohlc_cache.py:157` reports open on bank holidays.
Consequences:

- The L2 query is a plain SK `BETWEEN` over timestamps (`ohlc_cache.py:212-225`). Weekends
  and holidays inside a range simply contribute no candles; nothing filters or special-cases
  them.
- A range whose trading days yield no data at all returns 404, not an empty 200
  (`ohlc.py:826-838`).
- On a half-day, `cache_expires_at` still points at the normal 4:00 PM close, so the last
  real bar reads as forming until then.
- Candle counts vary with the calendar. The 80% coverage estimate assumes 5 trading days a
  week and 6.5 market hours a day (`ohlc.py:333-368`); it is an estimate, not a calendar.
