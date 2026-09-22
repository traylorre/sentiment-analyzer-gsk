# Contract: timeseries bucket (post-change)

Consumers (SSE polling, dashboard timeseries/sentiment/ohlc endpoints, admin JS,
customer chart) may rely on:

- `avg`, `open`, `high`, `low`, `close` are signed floats in [-1, 1]; `avg` equals
  `sum / count` at every observable state.
- `count >= 1`; `sum` in [-count, count].
- `high >= low`; `open`/`close` are the values of the earliest/latest contributing
  article by article timestamp.
- `label_counts` keys drawn from {positive, neutral, negative}; values sum to
  `count`.
- `sources` is a string set of provider names; membership test
  `"tiingo" in sources` is valid; no `dedup:` prefixed entries after cutover
  (legacy buckets may carry them until TTL).
- `version` is present on every bucket written after cutover; consumers MUST
  ignore unknown attributes (all current readers parse attribute-wise, verified).
  Writers never assume it: a bucket that exists without `version` (any
  pre-cutover bucket) is written conditionally on attribute_not_exists(version),
  the same condition that guards creation of absent buckets.
- `is_partial`: stored True carries no completeness information (every fanout
  write sets it True); stored False means explicitly complete and is
  authoritative. Completeness is otherwise computed at query time from window end
  vs now, which is what the dashboard already does
  (src/lambdas/dashboard/timeseries.py:131-132, 366-368). Do not trust stored True.
- Buckets written before cutover and outside the backfill window may hold legacy
  semantics (count=1, unsigned values in [0.5, 1]) until TTL expiry, at latest 90
  days post-cutover.

Breaking-change note: any consumer asserting non-negative values would break; the
consumer sweep (reviews/ar1.json context, refuted claim set) found none: SSE casts
to float, dashboard divides sum/count, thresholds are already signed at +/-0.33.
