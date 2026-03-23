# Feature 1241: Chaos Report Diffing and Regression Detection

**Status:** DRAFT
**Created:** 2026-03-22
**Owner:** Engineering
**Parent:** chaos-testing-system.md (Feature 1238: Gate + Report)
**Branch:** `1241-chaos-report-diffing`

---

## Problem Statement

After running chaos experiments over time, there is no way to compare results across runs. An engineer cannot answer: "Did our recovery time get worse since last sprint?" or "Did that deploy break our DLQ alarm response?" Without diffing, regressions in resilience go undetected until a real outage.

## Solution

A diff engine that compares two chaos experiment reports (baseline vs current) and produces a structured regression analysis. The engine identifies scenarios that got worse, improved, or remained stable -- and computes an overall verdict.

---

## User Stories

### US1 (P1): Diff Two Reports by ID

**As** an engineer running chaos experiments,
**I want** to diff a baseline report against a current report by their experiment IDs,
**So that** I can see what changed between two chaos runs.

**Acceptance Criteria:**
- AC1.1: Given two valid experiment IDs, the diff returns a structured comparison
- AC1.2: Given a non-existent experiment ID, the diff returns a 404 with clear message
- AC1.3: Given an experiment that has no report (status=pending), the diff returns a 400 with reason
- AC1.4: The diff output includes `baseline_report_id`, `current_report_id`, `compared_at` (ISO8601), `regressions`, `improvements`, `stable`, and `overall` verdict

### US2 (P1): Detect Regressions Automatically

**As** an on-call engineer,
**I want** the system to automatically flag regressions based on configurable thresholds,
**So that** I do not have to manually eyeball report differences.

**Acceptance Criteria:**
- AC2.1: Recovery time increase >50% from baseline is flagged as regression (severity HIGH)
- AC2.2: Alarm fire time increase >100% from baseline is flagged as regression (severity HIGH)
- AC2.3: Verdict downgrade (CLEAN -> COMPROMISED, CLEAN -> RECOVERY_INCOMPLETE) is flagged (severity CRITICAL)
- AC2.4: Each regression entry includes: `scenario`, `field`, `baseline` value, `current` value, `change_pct`, `severity`
- AC2.5: Improvements (metrics that got better by the same thresholds) are listed separately
- AC2.6: Unchanged fields (within threshold) are listed as `stable`

### US3 (P2): CLI Script for Ad-Hoc Diffing

**As** a developer debugging a resilience regression,
**I want** a CLI script I can run locally to diff two reports,
**So that** I can compare experiments without opening the dashboard.

**Acceptance Criteria:**
- AC3.1: `python -m scripts.chaos_diff --baseline <id> --current <id>` produces a formatted diff
- AC3.2: Output supports `--format json` (machine-readable) and `--format text` (human-readable, default)
- AC3.3: Exit code 0 if STABLE or IMPROVED, exit code 1 if REGRESSION
- AC3.4: Script reads from DynamoDB using existing `CHAOS_EXPERIMENTS_TABLE` env var

### US4 (P2): API Endpoint for Report Diffing

**As** a frontend developer building the chaos dashboard,
**I want** a GET endpoint that returns the diff between two reports,
**So that** I can display regression information in the chaos UI.

**Acceptance Criteria:**
- AC4.1: `GET /chaos/reports/diff?baseline={id}&current={id}` returns the diff JSON
- AC4.2: Requires authenticated (non-anonymous) session
- AC4.3: Returns 400 if either parameter is missing
- AC4.4: Returns 404 if either experiment is not found
- AC4.5: Returns 400 if either experiment has no report data (not stopped/completed)

---

## Functional Requirements

### FR-01: Report Diff Engine (Core)

The `diff_reports()` function accepts two experiment report dicts and returns a structured diff.

```python
def diff_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    thresholds: DiffThresholds | None = None,
) -> ReportDiff:
```

**Fields compared:**
| Field | Regression Threshold | Improvement Threshold | Source |
|-------|---------------------|-----------------------|--------|
| `duration_seconds` | N/A (informational) | N/A | experiment metadata |
| `verdict` | Any downgrade | Any upgrade | report verdict |
| `baseline.all_healthy` | True -> False | False -> True | baseline health |
| `post_chaos.all_healthy` | True -> False | False -> True | post-chaos health |
| `post_chaos.new_issues` | Count increased | Count decreased | post-chaos comparison |
| `post_chaos.recovered` | Count decreased | Count increased | post-chaos comparison |

### FR-02: Configurable Thresholds

Default thresholds with override support:

```python
@dataclass
class DiffThresholds:
    recovery_time_regression_pct: float = 50.0    # >50% worse = regression
    alarm_time_regression_pct: float = 100.0      # >100% worse = regression
    verdict_downgrade_severity: str = "CRITICAL"
    new_issues_severity: str = "HIGH"
```

### FR-03: Severity Classification

| Severity | Condition |
|----------|-----------|
| CRITICAL | Verdict downgrade (CLEAN -> anything worse) |
| HIGH | Recovery time >50% worse, alarm time >100% worse, new post-chaos issues |
| MEDIUM | Recovery time 25-50% worse, alarm time 50-100% worse |
| LOW | Any measurable degradation below MEDIUM thresholds |

### FR-04: Overall Verdict Computation

```
REGRESSION  - Any CRITICAL or HIGH severity regression exists
STABLE      - No regressions above LOW severity
IMPROVED    - At least one improvement AND no regressions above LOW
```

### FR-05: Cross-Scenario Comparison

When baseline and current experiments used different scenario types, the diff must:
- Report both scenario types in the output
- Compare only the common fields (verdict, duration, health status)
- Flag scenario mismatch as a warning (not an error)

### FR-06: Missing Field Handling

When a field exists in one report but not the other:
- Treat the missing field as `null` in the comparison
- Flag it as `"field_missing_in_baseline"` or `"field_missing_in_current"`
- Do NOT classify missing fields as regressions

### FR-07: Dry-Run Awareness

When either report has `dry_run: true`:
- Include a warning in the diff output: `"warning": "Baseline/current was a dry-run -- comparison may not reflect real system behavior"`
- Still compute the diff (dry-run reports have valid health snapshots)
- Set `dry_run_involved: true` in the diff output

### FR-08: API Response Schema

```json
{
  "baseline_report_id": "uuid",
  "current_report_id": "uuid",
  "compared_at": "2026-03-22T10:00:00Z",
  "baseline_scenario": "ingestion_failure",
  "current_scenario": "ingestion_failure",
  "scenario_match": true,
  "dry_run_involved": false,
  "warnings": [],
  "regressions": [
    {
      "scenario": "ingestion_failure",
      "field": "verdict",
      "baseline": "CLEAN",
      "current": "RECOVERY_INCOMPLETE",
      "change_pct": null,
      "severity": "CRITICAL"
    }
  ],
  "improvements": [
    {
      "scenario": "ingestion_failure",
      "field": "post_chaos.new_issues_count",
      "baseline": 2,
      "current": 0,
      "change_pct": -100,
      "severity": "HIGH"
    }
  ],
  "stable": [
    {
      "field": "baseline.all_healthy",
      "value": true
    }
  ],
  "overall": "REGRESSION"
}
```

---

## Edge Cases

### EC-01: Reports with Different Scenarios
When `baseline.scenario != current.scenario`, the plan may have evolved. Compare only health/verdict fields. Add warning: `"Scenarios differ: comparing health metrics only"`.

### EC-02: Missing Fields
Experiment stopped mid-run may lack `post_chaos_health`. Treat as `null`, do not error. Add warning: `"current report missing post_chaos_health -- experiment may not have completed"`.

### EC-03: Dry-Run vs Armed Comparison
Comparing a dry-run baseline to an armed current is valid but misleading. Flag with `dry_run_involved: true` and warning.

### EC-04: Both Reports Identical
All fields match. Return `overall: "STABLE"` with empty regressions/improvements and all fields in `stable`.

### EC-05: Experiment in Wrong Status
If either experiment is in `pending` or `running` status, return 400: `"Experiment {id} is still {status} -- wait for completion before diffing"`.

### EC-06: Numeric Field is Zero in Baseline
When baseline value is 0 and current is non-zero, `change_pct` would be infinity. Cap at `9999` and add note.

### EC-07: Verdict Ordering
Verdict comparison uses ordering: `CLEAN > DRY_RUN_CLEAN > INCONCLUSIVE > RECOVERY_INCOMPLETE > COMPROMISED`. Moving down the list is a regression, up is an improvement.

---

## Success Criteria

1. **SC-01**: `diff_reports()` correctly identifies regressions, improvements, and stable fields for all 5 existing scenario types
2. **SC-02**: API endpoint returns correct diff for same-scenario and cross-scenario comparisons
3. **SC-03**: CLI script exits with correct code (0 for stable/improved, 1 for regression)
4. **SC-04**: Missing fields and edge cases produce warnings, not errors
5. **SC-05**: All unit tests pass with >95% line coverage on the diff engine
6. **SC-06**: Dry-run comparisons are flagged clearly in output

---

## Non-Functional Requirements

- **NFR-01**: Diff computation must complete in <100ms for two reports (pure in-memory comparison)
- **NFR-02**: API response time <500ms including DynamoDB reads
- **NFR-03**: No new DynamoDB tables required -- reads from existing `chaos-experiments` table
- **NFR-04**: No new IAM permissions required -- uses existing DynamoDB read permissions

---

## Dependencies

- Feature 1238 (Chaos Gate + Report) -- provides `get_experiment_report()` which is the data source
- Existing `chaos.py` module in `src/lambdas/dashboard/`
- Existing chaos experiment DynamoDB table

---

## Out of Scope

- Historical trend analysis (comparing >2 reports over time)
- Automated regression alerting (SNS notification on regression)
- Dashboard UI changes for displaying diffs (separate feature)
- Storing diff results in DynamoDB (diffs are computed on-demand)
