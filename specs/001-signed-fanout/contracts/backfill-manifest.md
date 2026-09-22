# Contract: backfill run manifest (FR-004)

Emitted by `scripts/backfill_timeseries.py` as JSON to stdout and to a local file
the operator keeps (`backfill-manifest-<env>-<startisoZ>.json`). Fields:

- `assumed_role_arn`, `session_name`: identity the run executed under.
- `environment`: preprod | prod.
- `started_at`, `finished_at`: ISO8601 UTC.
- `quiescence`: {`rule_name`, `disabled_at`, `drain_verified_at`,
  `reenabled_at`, `forced`: bool}. `forced` is true only with `--force`, which the
  manifest records as an operator override.
- `window`: {`from`, `to`}: the recomputed horizon.
- `scope`: {`ticker_filter`: null | [tickers], `window_filter`: null |
  {`from`, `to`}, `argv`: [the full command line]}. A full-horizon run records
  nulls; a targeted FR-009 repair records its `--ticker`/`--window` arguments.
  `per_resolution` comparisons are meaningful only between runs of identical
  scope.
- `per_resolution`: map resolution -> {`buckets_written`, `buckets_skipped_ttl`,
  `failures`} (skipped = TTL already past, FR-004 scope rule).
- `items_read`: count of sentiment-items records consumed.
- `rejected_timestamps`: count of source records outside FR-010 bounds (logged
  individually in the run log, counted here).
- `failures`: list of {ticker, resolution, window, error_class}; empty on success.
- `dry_run`: bool. The script supports `--dry-run` producing the manifest with
  zero writes.

Idempotency contract: two consecutive quiesced runs over the same item set produce
identical bucket states (SC-004). Per resolution, `buckets_written` plus
`buckets_skipped_ttl` is stable across such runs; the split between the two may
shift as windows age across the TTL boundary between runs, with `buckets_written`
falling by exactly what `buckets_skipped_ttl` gains.
