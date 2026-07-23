# Misleading Comments & Docstrings, Cleanup Map

Scope: `comments` domain, CONFIRMED and UNKNOWN verdicts only. REFUTED rows (30-day TTL comment, OHLC cache TTL comment, Feature 006 quota/notification header) are accurate and excluded.

All 6 rows below are CONFIRMED misleading. No UNKNOWN rows in this domain.

| # | Comment (as written) | Locus | Reality (file:line) | Verdict |
|---|---|---|---|---|
| 1 | Timeseries table: 8 resolutions `1m:6h, 5m:12h, 10m:24h, 1h:7d, 3h:14d, 6h:30d, 12h:60d, 24h:90d`; sizing `~$8/month … × 8 resolutions` | `infrastructure/terraform/modules/dynamodb/main.tf:547` (also `:526`) | Enum has 6 members `1m,5m,15m,30m,1h,24h`. `src/lib/timeseries/models.py:24-29`; TTLs `models.py:57-64` (1m=6h,5m=12h,15m=24h,30m=3d,1h=7d,24h=90d). Comment's 10m/3h/6h/12h are non-existent; 15m/30m omitted. Only 1h=7d, 24h=90d match. | CONFIRMED |
| 2 | Fanout docstring: `Generate DynamoDB items for all 8 resolutions`; `List of 8 DynamoDB items` | `src/lib/timeseries/fanout.py:31` (also `:39`) | Loop `for resolution in Resolution` over 6-member enum → 6 items. `fanout.py:49`. Same file's module docstring `fanout.py:10` correctly says 6 buckets. | CONFIRMED |
| 3 | Analysis docstrings: `Model loaded from Lambda layer (/opt/model)`; `Verify /opt/model exists in Lambda layer` | `src/lambdas/analysis/sentiment.py:10,36`; `src/lambdas/analysis/handler.py:43` (cite said 44-45) | Model downloaded from S3 to `/tmp`. `sentiment.py:60` `LOCAL_MODEL_PATH='/tmp/model'`; `sentiment.py:70-141` `_download_model_from_s3()` extracts to /tmp; `sentiment.py:181` load = `MODEL_PATH` or `/tmp/model`. No `/opt/model` in any load path. | CONFIRMED |
| 4 | sentiment_items PK attr example: `type = "S" # String (e.g., "newsapi#abc123def456")` | `infrastructure/terraform/modules/dynamodb/main.tf:20` | Prefix is `article#`, not `newsapi#`. `src/lib/deduplication.py:38` `SOURCE_PREFIX='article'`; `deduplication.py:41-81` returns `article#{sha256[:16]}`. `grep 'newsapi' src/**/*.py` → none. | CONFIRMED |
| 5 | by_tag GSI: `Application code must fan-out matched_tags into separate writes` (implies scalar `tag` attr written per-tag) | `infrastructure/terraform/modules/dynamodb/main.tf:55` (cite range 53-61) | No writer sets scalar `tag`. Ingestion writes list `matched_tickers` (`handler.py:987`); analysis update sets only sentiment/score/model_version/status (`handler.py:322-327`). Yet `api_v2.py:95` queries `IndexName='by_tag'` on `Key('tag')`. GSI queried but never populated. | CONFIRMED |
| 6 | by_status GSI: `projection_type = "ALL" # Minimal storage for monitoring` | `infrastructure/terraform/modules/dynamodb/main.tf:69` | `ALL` projects every attribute, the opposite of minimal. `KEYS_ONLY` would be minimal. Comment contradicts the setting on its own line. | CONFIRMED |

## Cleanup Actions

| # | Fix |
|---|---|
| 1 | Rewrite comment to the 6 live resolutions + real TTLs (`main.tf:547`); correct `× 8 resolutions` sizing note (`main.tf:526`) to 6. |
| 2 | Change `fanout.py:31,39` docstring `8` → `6` (align with the correct module docstring at `:10`). |
| 3 | Replace `/opt/model` Lambda-layer wording in `sentiment.py:10,36` and `handler.py:43` with the S3-download-to-`/tmp/model` mechanism. |
| 4 | Change example in `main.tf:20` from `newsapi#…` to `article#…`. |
| 5 | Either implement the `tag` fan-out writer (so `by_tag` at `api_v2.py:95` returns data) or delete the GSI + fan-out comment + scalar `tag` attr (`main.tf:34-36,55`). Behavioral bug, not just a stale comment. |
| 6 | Fix the comment (`# Full projection`) or downgrade `projection_type` to `KEYS_ONLY` if minimal storage was the intent (`main.tf:69`). |

Row 5 is the only one with a functional consequence: the `by_tag` query path is live but the index is never written, so it always returns empty. Rows 1-4 and 6 are documentation drift only.
