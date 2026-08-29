# Quickstart: verify signed fanout locally

```bash
source .venv/bin/activate   # 3.13; terraform hooks need it too

# Unit: mapping, hop, accumulation, backfill recompute
pytest tests/unit/test_timeseries_fanout.py tests/unit/test_analysis_handler.py \
       tests/unit/test_backfill_timeseries.py -q

# Integration (LocalStack; started by the make target): concurrency + crash shapes
make test-integration

# Full pre-push gates
make validate && make test-local
```

Manual smoke against preprod (after deploy, before prod):

```bash
# 1. A bucket written post-cutover carries version + signed values. Newest first:
#    without --no-scan-index-forward the query returns the OLDEST buckets, which
#    stay pre-cutover for up to a week at the 1h TTL and read as a false alarm.
aws dynamodb query --table-name preprod-sentiment-timeseries --region us-east-1 \
  --key-condition-expression 'PK = :pk' \
  --expression-attribute-values '{":pk":{"S":"NVDA#1h"}}' \
  --no-cli-pager --no-scan-index-forward --max-items 3

# 2. Chart line leaves the top band: dashboard NVDA 1M, negative days plot below 0
```

## Backfill runbook (FR-004, operator-run, per environment on explicit go)

```bash
# Preflight is enforced by the script itself; the happy path:
python scripts/backfill_timeseries.py --env preprod --assume-role \
  arn:aws:iam::<acct>:role/preprod-backfill-timeseries-role [--dry-run]
# The script: checks the ingestion rule is disabled (or disables it with
# confirmation), verifies drain via CloudWatch (240s invocation silence plus
# clean trailing Throttles and Errors windows, spec Clarifications Q3),
# recomputes TTL-live windows from
# sentiment-items, writes versioned buckets, re-enables the rule, emits the
# manifest (contracts/backfill-manifest.md). Keep the manifest file.
```

Repairing a recorded fanout failure (FR-009): find the window in the analysis log
group (structured records, `TimeseriesFanoutErrors`), then run the backfill with
`--ticker <T> --window <iso>` for a targeted, still-quiesced repair.
