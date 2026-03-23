# Feature 1241: Implementation Checklist

## Phase 1: Core Diff Engine (P1)

### 1.1 Data Models
- [ ] Create `src/lambdas/dashboard/chaos_diff.py` module
- [ ] Define `DiffThresholds` dataclass with default regression thresholds
- [ ] Define `RegressionEntry` dataclass (scenario, field, baseline, current, change_pct, severity)
- [ ] Define `ImprovementEntry` dataclass (same shape as RegressionEntry)
- [ ] Define `StableEntry` dataclass (field, value)
- [ ] Define `ReportDiff` dataclass (full diff output schema per FR-08)
- [ ] Define `VERDICT_ORDER` constant for verdict severity ranking (EC-07)

### 1.2 Diff Engine Implementation
- [ ] Implement `diff_reports(baseline, current, thresholds=None) -> ReportDiff`
- [ ] Implement `_compare_verdicts(baseline_verdict, current_verdict) -> RegressionEntry | ImprovementEntry | StableEntry`
- [ ] Implement `_compare_health(baseline_health, current_health) -> list[RegressionEntry | ImprovementEntry | StableEntry]`
- [ ] Implement `_compare_numeric(field, baseline_val, current_val, threshold_pct) -> RegressionEntry | ImprovementEntry | StableEntry`
- [ ] Implement `_classify_severity(change_pct, thresholds) -> str` for numeric fields
- [ ] Implement `_compute_overall_verdict(regressions) -> str` (REGRESSION | STABLE | IMPROVED)
- [ ] Handle missing fields (FR-06): return warning, not error
- [ ] Handle zero baseline (EC-06): cap change_pct at 9999
- [ ] Handle dry-run awareness (FR-07): flag and warn
- [ ] Handle cross-scenario comparison (FR-05): compare only common fields, add warning

### 1.3 Integration with Existing Report System
- [ ] Import `get_experiment_report` from `chaos.py`
- [ ] Implement `diff_experiments(baseline_id, current_id, thresholds=None) -> ReportDiff`
  - [ ] Fetch both reports via `get_experiment_report()`
  - [ ] Validate both experiments exist (404 handling)
  - [ ] Validate both experiments have report data (400 for pending/running -- EC-05)
  - [ ] Call `diff_reports()` and return result

## Phase 2: API Endpoint (P2)

### 2.1 Handler Endpoint
- [ ] Add `GET /chaos/reports/diff` route to `handler.py`
- [ ] Parse `baseline` and `current` query parameters
- [ ] Validate both parameters present (return 400 if missing)
- [ ] Require authenticated (non-anonymous) session
- [ ] Call `diff_experiments()` and serialize response with `orjson`
- [ ] Handle `ChaosError` (404) and `ValueError` (400) appropriately
- [ ] Add endpoint to API index listing in `api_index()`

### 2.2 Import Updates
- [ ] Add `diff_experiments` to imports in `handler.py` from `chaos_diff`
- [ ] Verify no circular import issues

## Phase 3: CLI Script (P2)

### 3.1 CLI Implementation
- [ ] Create `scripts/chaos_diff.py` module
- [ ] Implement argparse with `--baseline`, `--current`, `--format` (json|text), `--thresholds-file`
- [ ] Implement `format_text()` for human-readable output (colored terminal output)
- [ ] Implement `format_json()` for machine-readable output
- [ ] Set exit code: 0 for STABLE/IMPROVED, 1 for REGRESSION
- [ ] Read `CHAOS_EXPERIMENTS_TABLE` from environment
- [ ] Support `--env` flag to set environment (dev/preprod)

### 3.2 CLI Integration
- [ ] Add `__main__.py` to `scripts/` if not exists (for `python -m scripts.chaos_diff`)
- [ ] Test CLI with mock DynamoDB data

## Phase 4: Documentation

- [ ] Add inline docstrings to all public functions
- [ ] Update chaos API reference in handler.py api_index
- [ ] Add diff endpoint to chaos-testing-system.md API Reference section
