# Feature 1241: Verification Checklist

## Pre-Implementation Verification

- [ ] Existing `get_experiment_report()` returns all fields needed for diffing (verdict, baseline, post_chaos_health, dry_run, scenario_type)
- [ ] Existing chaos experiment statuses are well-defined (pending, running, completed, failed, stopped)
- [ ] No existing `/chaos/reports/diff` endpoint (no collision)
- [ ] DynamoDB read permissions sufficient for fetching two experiments in one request

## Code Quality

- [ ] All public functions have docstrings with Args/Returns/Raises
- [ ] Type hints on all function signatures (PEP 604 union syntax `X | Y`)
- [ ] No `from typing import` for deprecated imports (use `collections.abc` per Ruff UP035)
- [ ] Dataclasses use `@dataclass` or pydantic `BaseModel` consistently with project
- [ ] No hardcoded strings for verdicts -- use constants or enum
- [ ] `orjson` used for JSON serialization (consistent with handler.py)

## Security

- [ ] API endpoint requires authenticated (non-anonymous) session
- [ ] Experiment IDs validated/sanitized before DynamoDB query
- [ ] No sensitive data leaked in diff output (no IAM ARNs, no SSM parameter values)
- [ ] Error messages do not expose internal implementation details to API consumers

## Integration

- [ ] `chaos_diff.py` imports only from `chaos.py` (no circular imports)
- [ ] Handler imports `diff_experiments` correctly
- [ ] API index updated with new endpoint
- [ ] CLI script importable as `python -m scripts.chaos_diff`

## Regression Safety

- [ ] Existing chaos tests still pass (`test_chaos_gate.py`, `test_chaos_restore.py`, `test_chaos_fis.py`)
- [ ] No modifications to existing `chaos.py` functions
- [ ] No modifications to existing DynamoDB table schema
- [ ] No new DynamoDB tables created
- [ ] No new IAM permissions required

## Performance

- [ ] Diff computation is pure in-memory (no additional DynamoDB queries beyond initial report fetch)
- [ ] Two DynamoDB `get_item` calls maximum per diff request
- [ ] No unbounded loops in diff logic

## Edge Case Coverage

- [ ] EC-01 (different scenarios) produces warning, not error
- [ ] EC-02 (missing post_chaos_health) produces warning, not error
- [ ] EC-03 (dry-run comparison) flagged in output
- [ ] EC-04 (identical reports) returns STABLE
- [ ] EC-05 (pending/running experiment) returns 400
- [ ] EC-06 (zero baseline) caps change_pct at 9999
- [ ] EC-07 (verdict ordering) uses defined severity ranking

## Deployment

- [ ] No Terraform changes required
- [ ] No new environment variables required
- [ ] No Lambda layer changes
- [ ] Feature is backwards-compatible (no breaking changes to existing chaos endpoints)
