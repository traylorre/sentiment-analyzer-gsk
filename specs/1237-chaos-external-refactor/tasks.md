# Tasks: Refactor Chaos Injection to External Actor Architecture

**Feature Branch**: `1237-chaos-external-refactor`
**Created**: 2026-03-22

## Phase 1: Remove Embedded Chaos Code from Handlers

### T-001: Remove chaos imports and gate from ingestion handler
- [ ] Remove `from src.lambdas.shared.chaos_injection import (auto_stop_expired, get_chaos_delay_ms, is_chaos_active)` (lines 103-107)
- [ ] Remove `if is_chaos_active("ingestion_failure"):` block and all contained logic (lines 194-207)
- [ ] Remove `auto_stop_expired("ingestion_failure")` and `auto_stop_expired("dynamodb_throttle")` calls (lines 221-222)
- [ ] Remove `if is_chaos_active("dynamodb_throttle"):` block and all contained logic (lines 225-234)
- [ ] Verify `import time` is still needed (used elsewhere for `time.perf_counter()`)
- File: `src/lambdas/ingestion/handler.py`
- Acceptance: FR-001; `grep -n "chaos" src/lambdas/ingestion/handler.py` returns zero matches

### T-002: Remove chaos imports and logic from analysis handler
- [ ] Remove `from src.lambdas.shared.chaos_injection import (auto_stop_expired, get_chaos_delay_ms, is_chaos_active)` (lines 68-72)
- [ ] Remove cold start delay block: `delay_ms = get_chaos_delay_ms("lambda_cold_start")` through the `log_structured()` call (lines 121-135)
- [ ] Remove DynamoDB throttle block: `if is_chaos_active("dynamodb_throttle"):` through `emit_metric()` (lines 138-147)
- [ ] Remove auto-stop calls: `auto_stop_expired("lambda_cold_start")` and `auto_stop_expired("dynamodb_throttle")` (lines 149-150)
- [ ] Verify `import time` is still needed (used for `time.perf_counter()` on lines 117, 183, 219)
- File: `src/lambdas/analysis/handler.py`
- Acceptance: FR-002; `grep -n "chaos" src/lambdas/analysis/handler.py` returns zero matches

### T-003: Delete chaos_injection.py shared module
- [ ] Delete `src/lambdas/shared/chaos_injection.py`
- [ ] Verify no other modules import from it: `grep -r "chaos_injection" src/`
- File: `src/lambdas/shared/chaos_injection.py` (delete)
- Acceptance: FR-003; file does not exist; no import errors

### T-004: Remove CHAOS_EXPERIMENTS_TABLE from ingestion and analysis Terraform
- [ ] Remove `CHAOS_EXPERIMENTS_TABLE = module.dynamodb.chaos_experiments_table_name` from ingestion Lambda environment block (line 276 in main.tf)
- [ ] Remove `CHAOS_EXPERIMENTS_TABLE = module.dynamodb.chaos_experiments_table_name` from analysis Lambda environment block (line 334 in main.tf)
- [ ] Keep `CHAOS_EXPERIMENTS_TABLE` in dashboard Lambda environment block (line 407) -- needed for audit log
- File: `infrastructure/terraform/main.tf`
- Acceptance: FR-014; SC-010

### T-005: Delete obsolete chaos test files
- [ ] Delete `tests/unit/test_chaos_injection.py` (detection helper tests -- helper is deleted)
- [ ] Delete `tests/unit/test_chaos_ingestion_wiring.py` (ingestion chaos gate tests -- gate is deleted)
- [ ] Delete `tests/unit/test_chaos_auto_stop.py` (auto-stop tests -- auto-stop is deleted)
- Files: 3 test files deleted
- Acceptance: Deleted files do not exist; `pytest tests/unit/ -k "not chaos"` passes

### T-006: Verify non-chaos tests pass after removal
- [ ] Run `pytest tests/unit/ -k "not chaos" -v` -- all tests pass
- [ ] Run `grep -r "chaos_injection" src/lambdas/ingestion/ src/lambdas/analysis/` -- zero matches
- [ ] Run `python -c "from src.lambdas.ingestion.handler import lambda_handler"` -- no import error
- [ ] Run `python -c "from src.lambdas.analysis.handler import lambda_handler"` -- no import error
- Acceptance: SC-001, SC-002, SC-008

## Phase 2: Create External Chaos Scripts

### T-007: Create shared chaos library
- [ ] Create `scripts/chaos/lib/common.sh` with shared functions:
  - `check_kill_switch()` -- reads SSM `/chaos/{env}/kill-switch`, exits 1 if "triggered"
  - `snapshot_config()` -- reads Lambda function config via `aws lambda get-function-configuration`, saves JSON to SSM `/chaos/{env}/snapshot/{scenario}`
  - `restore_config()` -- reads SSM snapshot, applies original config via AWS CLI
  - `log_experiment()` -- writes audit entry to chaos-experiments DynamoDB table
  - `validate_environment()` -- refuses "prod" unless `--force-prod` flag
  - `get_function_name()` -- resolves `{env}-sentiment-{service}` pattern
  - `get_rule_name()` -- resolves `{env}-sentiment-ingestion-schedule` pattern
  - `die()` -- print error and exit 1
  - `info()` / `warn()` -- colored output helpers
- File: `scripts/chaos/lib/common.sh` (new)
- Acceptance: `shellcheck scripts/chaos/lib/common.sh` passes

### T-008: Create inject script for all 5 scenarios
- [ ] Create `scripts/chaos/inject.sh` with usage: `inject.sh <scenario> <environment> [options]`
- [ ] Implement `ingestion-failure` scenario: `aws lambda put-function-concurrency --function-name {name} --reserved-concurrent-executions 0`
- [ ] Implement `dynamodb-throttle` scenario: Create inline deny-DynamoDB-write policy and attach to Lambda execution role
- [ ] Implement `cold-start` scenario: `aws lambda update-function-configuration --function-name {name} --memory-size 128`
- [ ] Implement `trigger-failure` scenario: `aws events disable-rule --name {rule}`
- [ ] Implement `api-timeout` scenario: `aws lambda update-function-configuration --function-name {name} --timeout 1`
- [ ] Each scenario: validate kill switch, snapshot config, log experiment, execute action
- [ ] Support `--dry-run` flag that prints commands without executing
- [ ] Support `--target <lambda>` to specify which Lambda (default: ingestion)
- [ ] Support `--duration <seconds>` for auto-restore scheduling
- File: `scripts/chaos/inject.sh` (new)
- Acceptance: FR-004, FR-007, FR-008, FR-009; SC-003, SC-006

### T-009: Create restore script
- [ ] Create `scripts/chaos/restore.sh` with usage: `restore.sh <environment> [--scenario <name>]`
- [ ] Without `--scenario`: list all SSM snapshots under `/chaos/{env}/snapshot/` and restore each
- [ ] With `--scenario`: restore only the specified scenario's snapshot
- [ ] For each snapshot: apply reverse AWS CLI calls based on snapshot JSON
- [ ] Delete SSM snapshot parameter after successful restore
- [ ] Update DynamoDB experiment audit log with restore timestamp
- [ ] Set kill switch to "disarmed" after all restores complete
- [ ] Handle missing snapshots gracefully (warn and continue)
- File: `scripts/chaos/restore.sh` (new)
- Acceptance: FR-005; SC-004

### T-010: Create status script
- [ ] Create `scripts/chaos/status.sh` with usage: `status.sh <environment>`
- [ ] Read and display kill switch state from SSM
- [ ] List all SSM snapshots under `/chaos/{env}/snapshot/` with scenario names
- [ ] Query chaos-experiments DynamoDB table for running experiments
- [ ] Display formatted output with scenario name, start time, duration
- File: `scripts/chaos/status.sh` (new)
- Acceptance: FR-006

### T-011: Create andon cord script
- [ ] Create `scripts/chaos/andon-cord.sh` with usage: `andon-cord.sh <environment>`
- [ ] Set kill switch to "triggered"
- [ ] Call `restore.sh <environment>` (restore all active scenarios)
- [ ] Log andon cord activation to DynamoDB experiment table
- [ ] Print summary of what was restored
- File: `scripts/chaos/andon-cord.sh` (new)
- Acceptance: FR-012

### T-012: Make all scripts executable and add shellcheck CI
- [ ] `chmod +x scripts/chaos/*.sh scripts/chaos/lib/common.sh`
- [ ] Run `shellcheck scripts/chaos/*.sh scripts/chaos/lib/common.sh` -- no errors
- [ ] Add scripts to Makefile: `chaos-inject`, `chaos-restore`, `chaos-status`, `chaos-andon`
- Acceptance: All scripts are executable and lint-clean

## Phase 3: Terraform for IAM Role + SSM Parameters

### T-013: Create SSM Parameter for kill switch
- [ ] Add `aws_ssm_parameter.chaos_kill_switch` resource to chaos module
- [ ] Parameter name: `/chaos/${var.environment}/kill-switch`
- [ ] Default value: `disarmed`, type: `String`
- [ ] `lifecycle { ignore_changes = [value] }` -- scripts manage the value
- [ ] Only create in non-prod environments (count based on environment)
- File: `infrastructure/terraform/modules/chaos/main.tf`
- Acceptance: FR-010

### T-014: Create chaos-engineer IAM role
- [ ] Add `aws_iam_role.chaos_engineer` with MFA condition on assume role
- [ ] Set `max_session_duration = 3600` (1 hour)
- [ ] Add `aws_iam_role_policy.chaos_engineer_permissions` with:
  - `lambda:UpdateFunctionConfiguration`, `lambda:PutFunctionConcurrency`, `lambda:DeleteFunctionConcurrency`, `lambda:GetFunctionConfiguration` scoped to environment Lambda ARNs
  - `iam:AttachRolePolicy`, `iam:DetachRolePolicy` scoped to environment Lambda execution roles
  - `events:DisableRule`, `events:EnableRule` scoped to environment EventBridge rules
  - `ssm:PutParameter`, `ssm:GetParameter` scoped to `/chaos/{env}/*`
  - `dynamodb:PutItem` scoped to chaos-experiments table
- [ ] Only create in non-prod environments
- File: `infrastructure/terraform/modules/chaos/main.tf`
- Acceptance: FR-011; SC-007

### T-015: Add chaos module variables and outputs
- [ ] Add variables: `chaos_engineer_principals` (list of IAM ARNs allowed to assume role), `lambda_execution_role_arns` (for IAM policy scoping), `eventbridge_rule_arns`, `alarm_topic_arn`
- [ ] Add outputs: `chaos_engineer_role_arn`, `kill_switch_parameter_name`
- Files: `infrastructure/terraform/modules/chaos/variables.tf`, `infrastructure/terraform/modules/chaos/outputs.tf` (new)
- Acceptance: Variables and outputs defined; `terraform plan` succeeds

### T-016: Wire chaos module in main.tf
- [ ] Pass new variables to chaos module: `chaos_engineer_principals`, Lambda role ARNs, EventBridge rule ARNs, alarm topic ARN
- [ ] Remove `CHAOS_EXPERIMENTS_TABLE` from ingestion and analysis env vars (if not done in T-004)
- File: `infrastructure/terraform/main.tf`
- Acceptance: `terraform plan` shows expected changes

## Phase 4: Andon Cord Implementation

### T-017: Create auto-restore Lambda handler
- [ ] Create `src/lambdas/chaos_restore/handler.py`
- [ ] Parse SNS notification from CloudWatch alarm
- [ ] Verify alarm is chaos-related (check metric namespace or alarm name pattern)
- [ ] Read all SSM snapshots under `/chaos/{env}/snapshot/`
- [ ] For each snapshot, call AWS APIs to restore original configuration
- [ ] Set kill switch to "disarmed"
- [ ] Emit `ChaosAutoRestore` CloudWatch metric (count=1)
- [ ] Log structured output with scenario names and restore results
- File: `src/lambdas/chaos_restore/handler.py` (new)
- Acceptance: FR-013; SC-009

### T-018: Add auto-restore Lambda to Terraform
- [ ] Add `aws_lambda_function.chaos_restore` resource (Python 3.13, 256MB, 60s timeout)
- [ ] Add IAM role with SSM read/write, Lambda config update, events enable, IAM policy detach
- [ ] Add `aws_sns_topic_subscription` to critical composite alarm SNS topic
- [ ] Add `aws_lambda_permission` for SNS invocation
- [ ] Only create in non-prod environments
- File: `infrastructure/terraform/modules/chaos/main.tf`
- Acceptance: `terraform plan` shows Lambda + SNS subscription

### T-019: Test auto-restore Lambda
- [ ] Write test: SNS alarm message -> Lambda reads SSM -> Lambda restores config
- [ ] Write test: No active snapshots -> Lambda does nothing (idempotent)
- [ ] Write test: SSM read fails -> Lambda logs error and sets kill switch to "triggered" for manual investigation
- [ ] Write test: Kill switch set to "disarmed" after successful restore
- File: `tests/unit/test_chaos_restore.py` (new)
- Acceptance: SC-009

## Phase 5: Dashboard Rewire

### T-020: Rewrite start_experiment() for external architecture
- [ ] Replace the DynamoDB-flag logic in `start_experiment()` with AWS API calls:
  - `ingestion_failure` -> `lambda:PutFunctionConcurrency` with `ReservedConcurrentExecutions=0`
  - `dynamodb_throttle` -> `iam:AttachRolePolicy` with deny-DynamoDB-write policy
  - `lambda_cold_start` -> `lambda:UpdateFunctionConfiguration` with `MemorySize=128`
- [ ] Before executing, snapshot current config to SSM
- [ ] After executing, set kill switch to "armed"
- [ ] Update experiment status to "running" with new results format (include `injection_method: "external_api"`)
- File: `src/lambdas/dashboard/chaos.py`
- Acceptance: US5 scenario 1

### T-021: Rewrite stop_experiment() for external architecture
- [ ] Replace DynamoDB-flag logic with SSM snapshot restore:
  - Read snapshot from SSM for the experiment's scenario
  - Apply restore AWS API calls
  - Delete SSM snapshot
- [ ] Set kill switch to "disarmed"
- [ ] Update experiment status to "stopped" with restore results
- File: `src/lambdas/dashboard/chaos.py`
- Acceptance: US5 scenario 2

### T-022: Update dashboard IAM policy for new permissions
- [ ] Update `aws_iam_role_policy.dashboard_chaos` in IAM module to add:
  - `lambda:UpdateFunctionConfiguration`, `lambda:PutFunctionConcurrency`, `lambda:DeleteFunctionConcurrency`, `lambda:GetFunctionConfiguration` scoped to environment Lambdas
  - `ssm:PutParameter`, `ssm:GetParameter` scoped to `/chaos/{env}/*`
  - `events:DisableRule`, `events:EnableRule` scoped to environment EventBridge rules
  - Remove `fis:*` permissions (no longer needed)
- File: `infrastructure/terraform/modules/iam/main.tf`
- Acceptance: FR-015

### T-023: Remove FIS integration code from chaos.py
- [ ] Remove `start_fis_experiment()`, `stop_fis_experiment()`, `get_fis_experiment_status()` functions
- [ ] Remove `_get_fis_client()` and `_fis_client` global
- [ ] Remove `FIS_DYNAMODB_THROTTLE_TEMPLATE` import
- [ ] Keep CRUD functions: `create_experiment()`, `get_experiment()`, `list_experiments()`, `update_experiment_status()`, `delete_experiment()`
- File: `src/lambdas/dashboard/chaos.py`
- Acceptance: No FIS references in chaos.py

### T-024: Write tests for rewritten dashboard chaos module
- [ ] Test: start_experiment("ingestion_failure") calls PutFunctionConcurrency
- [ ] Test: start_experiment("lambda_cold_start") calls UpdateFunctionConfiguration
- [ ] Test: stop_experiment restores config from SSM snapshot
- [ ] Test: start_experiment snapshots current config to SSM first
- [ ] Test: start_experiment checks kill switch before proceeding
- [ ] Test: experiment audit log entries have `injection_method: "external_api"`
- File: `tests/unit/test_chaos_fis.py` (rewrite) or `tests/unit/test_chaos_dashboard_rewire.py` (new)
- Acceptance: Dashboard start/stop work with mocked AWS API calls

## Phase 6: Validation and Regression Testing

### T-025: Write integration tests for chaos scripts
- [ ] Test inject.sh with `--dry-run` flag outputs correct AWS commands for each scenario
- [ ] Test restore.sh reads SSM mock and outputs correct reverse commands
- [ ] Test status.sh displays formatted output
- [ ] Test andon-cord.sh calls restore.sh
- [ ] Test kill switch prevents injection when "triggered"
- File: `tests/unit/test_chaos_external.py` (new)
- Acceptance: SC-003, SC-004, SC-005

### T-026: Run full test suite
- [ ] Run `pytest tests/unit/ -v` -- all tests pass (including new chaos tests, excluding deleted ones)
- [ ] Run `make validate` -- passes
- [ ] Run `terraform plan` in preprod -- shows expected changes (new role, SSM params, no drift)
- Acceptance: SC-008; zero regressions

### T-027: Adversarial review of implementation
- [ ] Verify zero references to `chaos_injection` in handler code
- [ ] Verify SSM snapshots include all fields needed for restore (memory, timeout, concurrency, role policies, EventBridge state)
- [ ] Verify kill switch transitions: disarmed -> armed (inject) -> triggered (alarm) -> disarmed (restore)
- [ ] Verify prod safety: chaos-engineer role not created in prod; scripts refuse prod without `--force-prod`
- [ ] Verify dashboard API contract backward compatibility (same request/response shape for `/chaos/experiments` endpoints)
- [ ] Verify chaos-experiments DynamoDB table is not deleted or modified (schema unchanged)

---

## Dependency Graph

```
Phase 1 (T-001 through T-006) -- can start immediately
  T-001 ──┐
  T-002 ──┤
  T-003 ──┼── T-006 (verify)
  T-004 ──┤
  T-005 ──┘

Phase 2 (T-007 through T-012) -- can start in parallel with Phase 1
  T-007 ── T-008 ──┐
           T-009 ──┼── T-012
           T-010 ──┤
  T-007 ── T-011 ──┘

Phase 3 (T-013 through T-016) -- can start in parallel with Phase 1 and 2
  T-013 ──┐
  T-014 ──┼── T-016
  T-015 ──┘

Phase 4 (T-017 through T-019) -- depends on Phase 3 (alarm topic ARN)
  T-016 ── T-017 ── T-018 ── T-019

Phase 5 (T-020 through T-024) -- depends on Phase 2 (script patterns) and Phase 3 (IAM)
  T-008, T-016 ── T-020 ──┐
                  T-021 ──┼── T-024
                  T-022 ──┤
                  T-023 ──┘

Phase 6 (T-025 through T-027) -- depends on all prior phases
  T-012, T-019, T-024 ── T-025 ── T-026 ── T-027
```

---

## Estimated Effort Per Phase

| Phase | Tasks | Lines (prod) | Lines (test) | Time |
|-------|-------|-------------|-------------|------|
| Phase 1: Remove embedded code | T-001 to T-006 | -378 (delete) | -800 (delete) | 45 min |
| Phase 2: External scripts | T-007 to T-012 | +500 | +100 | 2 hr |
| Phase 3: Terraform IAM/SSM | T-013 to T-016 | +200 (HCL) | 0 | 1 hr |
| Phase 4: Andon cord | T-017 to T-019 | +80 | +100 | 1 hr |
| Phase 5: Dashboard rewire | T-020 to T-024 | +100 net | +150 | 1.5 hr |
| Phase 6: Validation | T-025 to T-027 | 0 | +250 | 1 hr |
| **Total** | **27 tasks** | **~500 net** | **~-200 net** | **~7 hr** |

**Minimum viable delivery**: Phase 1 + Phase 2 (remove embedded code + create scripts) = ~3 hours
