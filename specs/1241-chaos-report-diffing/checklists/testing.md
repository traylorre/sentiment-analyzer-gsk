# Feature 1241: Testing Checklist

## Unit Tests: Diff Engine (`tests/unit/test_chaos_diff.py`)

### TestDiffReports (Core Logic)

- [ ] `test_identical_reports_returns_stable` -- Two identical reports produce overall=STABLE, no regressions, no improvements, all fields in stable
- [ ] `test_verdict_downgrade_is_critical_regression` -- CLEAN->RECOVERY_INCOMPLETE produces CRITICAL regression
- [ ] `test_verdict_upgrade_is_improvement` -- RECOVERY_INCOMPLETE->CLEAN produces improvement
- [ ] `test_recovery_time_increase_over_threshold` -- duration_seconds 60->100 (67% increase, >50% threshold) = HIGH regression
- [ ] `test_recovery_time_increase_below_threshold` -- duration_seconds 60->80 (33% increase, <50% threshold) = stable
- [ ] `test_post_chaos_new_issues_increased` -- new_issues [] -> ["lambda"] = HIGH regression
- [ ] `test_post_chaos_new_issues_decreased` -- new_issues ["lambda"] -> [] = improvement
- [ ] `test_baseline_healthy_current_degraded` -- all_healthy True->False = regression
- [ ] `test_overall_verdict_regression_when_any_high` -- Any HIGH/CRITICAL regression => overall REGRESSION
- [ ] `test_overall_verdict_improved_when_no_regression` -- Improvements with no regressions => overall IMPROVED
- [ ] `test_overall_verdict_stable_when_nothing_changed` -- No regressions or improvements => overall STABLE

### TestEdgeCases

- [ ] `test_different_scenarios_warns_and_compares_common` -- Different scenario_type produces warning, compares health/verdict only (EC-01)
- [ ] `test_missing_post_chaos_health_warns` -- Report without post_chaos_health produces warning, not error (EC-02)
- [ ] `test_dry_run_baseline_flags_warning` -- dry_run=True in baseline sets dry_run_involved=True and adds warning (EC-03)
- [ ] `test_dry_run_current_flags_warning` -- dry_run=True in current sets dry_run_involved=True and adds warning (EC-03)
- [ ] `test_both_dry_run_flags_warning` -- Both dry_run=True flagged appropriately
- [ ] `test_zero_baseline_value_caps_change_pct` -- baseline=0, current=45 => change_pct=9999, not infinity (EC-06)
- [ ] `test_both_zero_values_stable` -- baseline=0, current=0 => stable, change_pct=0
- [ ] `test_missing_field_in_baseline_warns` -- Field present in current but not baseline produces warning (FR-06)
- [ ] `test_missing_field_in_current_warns` -- Field present in baseline but not current produces warning (FR-06)

### TestVerdictOrdering (EC-07)

- [ ] `test_verdict_order_clean_to_compromised_is_regression` -- CLEAN -> COMPROMISED = regression
- [ ] `test_verdict_order_compromised_to_clean_is_improvement` -- COMPROMISED -> CLEAN = improvement
- [ ] `test_verdict_order_clean_to_dry_run_clean_is_stable` -- Close verdicts = stable (both "clean" variants)
- [ ] `test_verdict_order_inconclusive_to_recovery_incomplete_is_regression` -- Moving down the severity list
- [ ] `test_verdict_order_same_verdict_is_stable` -- CLEAN -> CLEAN = stable

### TestThresholds

- [ ] `test_custom_thresholds_override_defaults` -- Custom DiffThresholds(recovery_time_regression_pct=25) lowers the bar
- [ ] `test_default_thresholds_used_when_none` -- None thresholds use defaults (50%, 100%)

### TestSeverityClassification

- [ ] `test_severity_critical_for_verdict_downgrade` -- Verdict changes always CRITICAL
- [ ] `test_severity_high_for_over_threshold` -- >50% recovery time = HIGH
- [ ] `test_severity_medium_for_25_to_50_pct` -- 25-50% = MEDIUM
- [ ] `test_severity_low_for_under_25_pct` -- <25% = LOW

## Unit Tests: API Integration (`tests/unit/test_chaos_diff_api.py`)

### TestDiffExperiments

- [ ] `test_diff_experiments_happy_path` -- Two valid stopped experiments return diff
- [ ] `test_diff_experiments_baseline_not_found` -- Non-existent baseline returns ChaosError
- [ ] `test_diff_experiments_current_not_found` -- Non-existent current returns ChaosError
- [ ] `test_diff_experiments_baseline_still_pending` -- Pending experiment returns ValueError
- [ ] `test_diff_experiments_baseline_still_running` -- Running experiment returns ValueError

### TestDiffEndpoint (Handler)

- [ ] `test_get_diff_returns_200` -- Valid baseline+current params return 200 with diff JSON
- [ ] `test_get_diff_missing_baseline_param` -- Missing baseline param returns 400
- [ ] `test_get_diff_missing_current_param` -- Missing current param returns 400
- [ ] `test_get_diff_unauthenticated_returns_401` -- No auth token returns 401
- [ ] `test_get_diff_anonymous_returns_401` -- Anonymous session returns 401
- [ ] `test_get_diff_experiment_not_found_returns_404` -- Non-existent experiment returns 404
- [ ] `test_get_diff_experiment_not_ready_returns_400` -- Pending experiment returns 400

## Unit Tests: CLI (`tests/unit/test_chaos_diff_cli.py`)

- [ ] `test_cli_json_output_format` -- `--format json` produces valid JSON matching ReportDiff schema
- [ ] `test_cli_text_output_format` -- `--format text` produces human-readable summary
- [ ] `test_cli_exit_code_0_on_stable` -- STABLE overall => exit code 0
- [ ] `test_cli_exit_code_0_on_improved` -- IMPROVED overall => exit code 0
- [ ] `test_cli_exit_code_1_on_regression` -- REGRESSION overall => exit code 1
- [ ] `test_cli_missing_baseline_arg` -- Missing --baseline prints usage error
- [ ] `test_cli_missing_current_arg` -- Missing --current prints usage error

## Test Fixtures

### Sample Reports (in conftest.py or fixture file)

- [ ] `clean_report_fixture` -- A report with verdict=CLEAN, all_healthy=True, no issues
- [ ] `compromised_report_fixture` -- A report with verdict=COMPROMISED, degraded_services
- [ ] `recovery_incomplete_fixture` -- A report with verdict=RECOVERY_INCOMPLETE, new_issues
- [ ] `dry_run_report_fixture` -- A report with dry_run=True, verdict=DRY_RUN_CLEAN
- [ ] `inconclusive_report_fixture` -- A report with verdict=INCONCLUSIVE, missing post_chaos
- [ ] `different_scenario_report_fixture` -- A report with scenario=dynamodb_throttle (vs ingestion_failure)

## Coverage Target

- [ ] Line coverage >95% on `chaos_diff.py`
- [ ] Branch coverage >90% on `chaos_diff.py`
- [ ] All edge cases (EC-01 through EC-07) have dedicated tests
