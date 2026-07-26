# Quickstart: verifying Lambda log visibility

# Target: backend Lambdas (CloudWatch log groups) — not either dashboard UI

## Local (before deploy)

```bash
source .venv/bin/activate
pytest tests/unit/shared/test_logging_config.py -v          # helper contract C-1..C-6
pytest tests/unit/test_entrypoint_logging_coverage.py -v    # C-7 guard
```

## Preprod (after deploy)

1. Dashboard on-demand probe (also the SC-006 drill — three refresh outcomes):

```bash
AWS_REGION=us-east-1 .venv/bin/python scripts/verify-log-visibility.py --function dashboard
# exercises refresh with: no cookie / garbage cookie / valid session
# then filter_log_events for refresh.cookie_absent, refresh.rejected, refresh.success
```

2. Canary (fires every 5 min — just wait and query):

```bash
aws logs filter-log-events --log-group-name /aws/lambda/preprod-sentiment-canary \
  --start-time $(($(date +%s -d '-20 min')*1000)) --filter-pattern '"[INFO]"' --max-items 5
```

3. Content-safety spot check (SC-007; expect ZERO hits):

```bash
for fn in dashboard ingestion analysis metrics notification canary; do
  aws logs filter-log-events --log-group-name /aws/lambda/preprod-sentiment-$fn \
    --start-time $(($(date +%s -d '-24 hours')*1000)) \
    --filter-pattern '"token="' --max-items 3
done
```

4. FR-004 baseline comparison: see tasks — captured pre-deploy, re-run
   post-deploy on the metrics log group; assert no additional duplication.

## Rollback

```bash
git revert <feature-commit> && git push  # root returns to WARNING on next deploy
```
