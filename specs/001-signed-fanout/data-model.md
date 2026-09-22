# Data Model: Signed, Aggregating Sentiment Timeseries Fanout

## Timeseries bucket (table `sentiment_timeseries`), before and after

Keys unchanged: PK `{ticker}#{resolution}` (e.g. `NVDA#24h`), SK = ISO8601 window
start (floored per resolution). TTL attribute `ttl` unchanged (window start +
resolution TTL; 24h=90d ... 1m=6h).

| Attribute | Before (live today) | After |
|---|---|---|
| count | always 1 (overwrite) | number of contributing articles |
| sum | last article's unsigned confidence | sum of signed contributions |
| avg | = sum (single article) | sum/count, recomputed on every write |
| open | last article's value | signed value of earliest-timestamped article |
| close | last article's value | signed value of latest-timestamped article |
| high | last article's value | max signed contribution |
| low | last article's value | min signed contribution |
| label_counts | map with one key, count 1 | merged map {positive: n, neutral: n, negative: n} |
| sources | list, one `dedup:<hash>` per write (unbounded under accumulation) | string set of provider names, e.g. {"tiingo"} |
| is_partial | always true | always true on write; readers compute completeness at query time (dashboard/timeseries.py:131-132 distrusts the stored flag by design; unchanged) |
| original_timestamp | last article's timestamp | latest contributing article's timestamp |
| version | absent | NEW: monotonically increasing int, optimistic-concurrency guard |
| open_ts / close_ts | absent | NEW: timestamps backing open/close ordering (needed to order out-of-order arrivals) |

Value range: every contribution in [-1, 1] (positive label -> +confidence in
[0.5, 1], negative -> -confidence in [-1, -0.5], neutral -> 0.0). `sum` in
[-count, count]; `avg` in [-1, 1]. Pydantic `ge=-1.0, le=1.0` on the score model
becomes exercised rather than vacuous.

Validation rules: writes rejected unless article timestamp in
[now - 30d, now + 5min] (FR-010); write accepted only under the D1 guard: version = :expected
when the read returned a version, attribute_not_exists(version) when it did not,
which covers absent buckets and legacy pre-cutover buckets alike (conditional
write, D1); every accepted write leaves all statistics mutually
consistent (single atomic put of complete state).

State transitions: absent -> created, and legacy-unversioned -> adopted. Both
entry transitions are conditional on attribute_not_exists(version), which holds
for a missing item and for an existing item without the attribute.
Legacy-unversioned (every bucket written before cutover) is a first-class
pre-state for the live path and the backfill alike. From created or adopted:
accumulating (version increments per contribution, conditional on
version = :expected) -> expired (TTL). Backfill writes follow the same shape:
complete recomputed state, versioned.

## Sentiment item (table `sentiment_items`), unchanged (FR-008)

`sentiment` (label string), `score` (unsigned confidence, 4dp), `model_version`,
`status`, `matched_tickers`, `ttl_timestamp` (30d). Backfill reads label + score +
matched_tickers + timestamp and derives signed contributions through the same
`label_to_signed` function as the live path.

## Signed sentiment (derived, `src/lib/timeseries/signed.py`)

`label_to_signed(label, confidence) -> float`: positive -> +confidence, negative ->
-confidence, anything else -> 0.0. Single source of truth for handler, backfill,
and the test oracle.
