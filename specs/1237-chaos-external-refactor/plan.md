# Implementation Plan: Refactor Chaos Injection to External Actor Architecture

**Feature Branch**: `1237-chaos-external-refactor`
**Created**: 2026-03-22
**Estimated Effort**: Medium (~400 lines removed, ~600 lines added across scripts/Terraform/tests)

## Files to Modify

### Production Code -- Deletions

| File | Change | Lines Removed | Risk |
|------|--------|---------------|------|
| `src/lambdas/shared/chaos_injection.py` | **DELETE** entire file | -318 | Medium -- all consumers must be updated first |
| `src/lambdas/ingestion/handler.py` | Remove chaos imports (lines 103-107), chaos gate (lines 194-207), auto-stop (lines 221-222), dynamodb throttle (lines 225-234) | -25 | Low -- removing branching logic, core path unchanged |
| `src/lambdas/analysis/handler.py` | Remove chaos imports (lines 68-72), cold start delay (lines 121-135), dynamodb throttle (lines 138-147), auto-stop (lines 149-150) | -35 | Low -- removing branching logic, core path unchanged |

### Production Code -- Additions

| File | Change | Lines Added | Risk |
|------|--------|-------------|------|
| `scripts/chaos/inject.sh` (new) | External chaos injection for 5 scenarios | ~200 | Low -- standalone script, no prod code coupling |
| `scripts/chaos/restore.sh` (new) | Restore all chaos-injected configs from SSM | ~120 | Low -- idempotent restore operations |
| `scripts/chaos/status.sh` (new) | Display current chaos state | ~60 | Low -- read-only operations |
| `scripts/chaos/andon-cord.sh` (new) | Manual kill switch trigger + restore | ~40 | Low -- delegates to restore.sh |
| `scripts/chaos/lib/common.sh` (new) | Shared functions (SSM, validation, logging) | ~80 | Low -- utility library |
| `src/lambdas/dashboard/chaos.py` | Rewrite `start_experiment()` / `stop_experiment()` to use external AWS APIs | ~50 net | Medium -- existing API contract must be preserved |

### Terraform

| File | Change | Lines Added | Risk |
|------|--------|-------------|------|
| `infrastructure/terraform/modules/chaos/main.tf` | Add chaos-engineer role, SSM parameters, auto-restore Lambda | ~150 | Medium -- new IAM role, review carefully |
| `infrastructure/terraform/modules/chaos/variables.tf` | New variables for chaos-engineer, SNS ARN, Lambda ARNs | ~30 | Low |
| `infrastructure/terraform/modules/chaos/outputs.tf` (new) | Export chaos role ARN, SSM parameter names | ~20 | Low |
| `infrastructure/terraform/main.tf` | Remove `CHAOS_EXPERIMENTS_TABLE` from ingestion and analysis env vars; wire chaos module outputs | ~10 net | Low -- removing env vars |
| `infrastructure/terraform/modules/iam/main.tf` | Update `dashboard_chaos` policy for new permissions (SSM, Lambda config) | ~20 | Low |

### Test Code

| File | Change | Lines |
|------|--------|-------|
| `tests/unit/test_chaos_fis.py` | Rewrite for new architecture (external script testing via subprocess mocks) | ~200 rewritten |
| `tests/unit/test_chaos_injection.py` | **DELETE** -- detection helper no longer exists | -all |
| `tests/unit/test_chaos_ingestion_wiring.py` | **DELETE** -- chaos gate no longer exists in handler | -all |
| `tests/unit/test_chaos_auto_stop.py` | **DELETE** -- auto-stop no longer exists in handler | -all |
| `tests/unit/test_chaos_external.py` (new) | Tests for chaos scripts (SSM snapshot, restore, kill switch) | ~250 |
| `tests/unit/test_chaos_dashboard_rewire.py` (new) | Tests for rewritten dashboard chaos start/stop | ~150 |

### Total Impact

- **1 file deleted** (production: `chaos_injection.py`)
- **3 test files deleted** (`test_chaos_injection.py`, `test_chaos_ingestion_wiring.py`, `test_chaos_auto_stop.py`)
- **5 new files** (4 scripts + 1 shared lib)
- **2 new test files**
- **4 files modified** (production)
- **~5 files modified** (Terraform)
- **Net code change**: ~60 lines removed from handlers, ~600 lines added in scripts/Terraform/tests

---

## Phase 1: Remove Embedded Chaos Code from Handlers

**Goal**: Clean separation -- handlers contain zero chaos awareness.

### 1a. Remove chaos from ingestion handler

Remove from `src/lambdas/ingestion/handler.py`:

```python
# REMOVE these imports (lines 103-107):
from src.lambdas.shared.chaos_injection import (
    auto_stop_expired,
    get_chaos_delay_ms,
    is_chaos_active,
)

# REMOVE chaos gate (lines 194-207):
if is_chaos_active("ingestion_failure"):
    ...  # entire block

# REMOVE auto-stop calls (lines 221-222):
auto_stop_expired("ingestion_failure")
auto_stop_expired("dynamodb_throttle")

# REMOVE dynamodb throttle block (lines 225-234):
if is_chaos_active("dynamodb_throttle"):
    ...  # entire block
```

**Why all at once**: Partial removal creates inconsistency. The external scripts replace ALL embedded scenarios.

### 1b. Remove chaos from analysis handler

Remove from `src/lambdas/analysis/handler.py`:

```python
# REMOVE imports (lines 68-72):
from src.lambdas.shared.chaos_injection import (
    auto_stop_expired,
    get_chaos_delay_ms,
    is_chaos_active,
)

# REMOVE cold start delay block (lines 121-135):
delay_ms = get_chaos_delay_ms("lambda_cold_start")
...  # entire block

# REMOVE dynamodb throttle block (lines 138-147):
if is_chaos_active("dynamodb_throttle"):
    ...  # entire block

# REMOVE auto-stop calls (lines 149-150):
auto_stop_expired("lambda_cold_start")
auto_stop_expired("dynamodb_throttle")
```

### 1c. Delete chaos_injection.py shared module

```bash
rm src/lambdas/shared/chaos_injection.py
```

### 1d. Remove CHAOS_EXPERIMENTS_TABLE from ingestion/analysis Terraform

In `infrastructure/terraform/main.tf`, remove `CHAOS_EXPERIMENTS_TABLE = module.dynamodb.chaos_experiments_table_name` from the ingestion Lambda (line 276) and analysis Lambda (line 334) environment blocks. The dashboard Lambda retains it (line 407).

### 1e. Delete obsolete tests

```bash
rm tests/unit/test_chaos_injection.py
rm tests/unit/test_chaos_ingestion_wiring.py
rm tests/unit/test_chaos_auto_stop.py
```

### 1f. Verify no regressions

```bash
pytest tests/unit/ -k "not chaos" -v  # all non-chaos tests pass
grep -r "chaos_injection" src/lambdas/ingestion/ src/lambdas/analysis/  # zero matches
```

**Risk**: Low. Removing branching logic from handlers. Core paths are unchanged.

---

## Phase 2: Create External Chaos Scripts

**Goal**: Replace embedded code with infrastructure-level chaos injection.

### 2a. Create shared library (`scripts/chaos/lib/common.sh`)

Shared functions used by all chaos scripts:

- `check_kill_switch()` -- Read SSM, abort if "triggered"
- `snapshot_config()` -- Read current Lambda config and save to SSM as JSON
- `restore_config()` -- Read SSM snapshot and apply AWS API calls
- `log_experiment()` -- Write audit entry to chaos-experiments DynamoDB table
- `validate_environment()` -- Refuse prod unless `--force-prod`
- `get_function_name()` -- Resolve Lambda function name from environment + service name
- `get_rule_name()` -- Resolve EventBridge rule name from environment

### 2b. Create inject script (`scripts/chaos/inject.sh`)

```bash
scripts/chaos/inject.sh <scenario> <environment> [options]

Scenarios:
  ingestion-failure   Set reserved concurrency to 0 on ingestion Lambda
  dynamodb-throttle   Attach deny-write IAM policy to Lambda execution role
  cold-start          Set memory to 128MB on target Lambda
  trigger-failure     Disable EventBridge ingestion schedule rule
  api-timeout         Set timeout to 1s on target Lambda

Options:
  --target <lambda>   Target Lambda (default: ingestion)
  --dry-run           Show commands without executing
  --force-prod        Allow injection in prod (requires MFA)
  --duration <sec>    Auto-restore after N seconds (default: 300)
```

Each scenario implementation:
1. Validate environment and kill switch
2. Snapshot current config to SSM
3. Set kill switch to "armed"
4. Execute the AWS API call
5. Log experiment to DynamoDB
6. If `--duration` specified, schedule a `restore.sh` call via `at` or background process

### 2c. Create restore script (`scripts/chaos/restore.sh`)

```bash
scripts/chaos/restore.sh <environment> [--scenario <name>]

# Without --scenario: restores ALL active chaos scenarios
# With --scenario: restores only the specified scenario
```

Implementation:
1. Read all snapshot SSM parameters under `/chaos/{env}/snapshot/`
2. For each snapshot, apply the reverse AWS API calls
3. Delete the snapshot SSM parameter
4. Update the DynamoDB experiment audit log with restore timestamp
5. Set kill switch to "disarmed"

### 2d. Create status script (`scripts/chaos/status.sh`)

```bash
scripts/chaos/status.sh <environment>
```

Output format:
```
Kill Switch: armed
Active Scenarios:
  ingestion-failure  started: 2026-03-22T10:00:00Z  duration: 300s
  cold-start         started: 2026-03-22T10:02:00Z  duration: 600s
Snapshots:
  /chaos/preprod/snapshot/ingestion-failure  (valid)
  /chaos/preprod/snapshot/cold-start         (valid)
```

### 2e. Create andon cord script (`scripts/chaos/andon-cord.sh`)

```bash
scripts/chaos/andon-cord.sh <environment>
```

Implementation:
1. Set kill switch to "triggered"
2. Call `restore.sh <environment>` (restore all)
3. Log andon cord activation to DynamoDB

---

## Phase 3: Terraform for IAM Role + SSM Parameters

**Goal**: Infrastructure-as-code for the chaos control plane.

### 3a. SSM Parameters

```hcl
resource "aws_ssm_parameter" "chaos_kill_switch" {
  count = var.environment != "prod" ? 1 : 0
  name  = "/chaos/${var.environment}/kill-switch"
  type  = "String"
  value = "disarmed"

  lifecycle {
    ignore_changes = [value]  # Scripts manage the value at runtime
  }
}
```

### 3b. Chaos Engineer IAM Role

```hcl
resource "aws_iam_role" "chaos_engineer" {
  count = var.environment != "prod" ? 1 : 0
  name  = "${var.environment}-chaos-engineer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = var.chaos_engineer_principals }
      Action    = "sts:AssumeRole"
      Condition = {
        Bool = { "aws:MultiFactorAuthPresent" = "true" }
      }
    }]
  })

  max_session_duration = 3600  # 1 hour
}
```

Permissions:
- `lambda:UpdateFunctionConfiguration` (memory, timeout changes)
- `lambda:PutFunctionConcurrency` / `lambda:DeleteFunctionConcurrency` (concurrency changes)
- `lambda:GetFunctionConfiguration` (snapshot current config)
- `iam:AttachRolePolicy` / `iam:DetachRolePolicy` (DynamoDB throttle via deny policy)
- `events:DisableRule` / `events:EnableRule` (trigger failure)
- `ssm:PutParameter` / `ssm:GetParameter` (kill switch + snapshots)
- `dynamodb:PutItem` on chaos-experiments table (audit log)

All permissions scoped to the environment's resources via resource ARN conditions.

### 3c. Auto-Restore Lambda (optional -- can be deferred)

A minimal Lambda that:
1. Subscribes to the critical composite alarm's SNS topic
2. On alarm, reads SSM snapshots
3. Restores all configurations
4. Sets kill switch to "disarmed"

This can be a simple Python Lambda (~50 lines) or the same bash script wrapped in a Lambda runtime.

---

## Phase 4: Andon Cord Implementation

**Goal**: Automated safety net for chaos experiments.

### 4a. Auto-restore Lambda code

Create `src/lambdas/chaos_restore/handler.py`:
- Parse SNS alarm notification
- Verify alarm is from chaos-related metric (prevent false triggers)
- Call restore logic for all active snapshots
- Emit CloudWatch metric `ChaosAutoRestore` with count=1

### 4b. Wire alarm to restore Lambda

Add SNS subscription in Terraform:
```hcl
resource "aws_sns_topic_subscription" "chaos_auto_restore" {
  topic_arn = var.alarm_topic_arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.chaos_restore.arn
}
```

### 4c. Manual andon cord testing

Create test that:
1. Injects a chaos scenario
2. Manually triggers the andon cord script
3. Verifies all configurations are restored
4. Verifies kill switch is "disarmed"

---

## Phase 5: Dashboard Rewire or Deprecation

**Goal**: Dashboard chaos module works with the new architecture.

### Option A: Rewire (recommended)

Rewrite `start_experiment()` in `src/lambdas/dashboard/chaos.py`:

```python
def start_experiment(experiment_id: str) -> dict[str, Any]:
    experiment = get_experiment(experiment_id)
    scenario_type = experiment["scenario_type"]

    # Snapshot current config to SSM
    _snapshot_to_ssm(scenario_type)

    # Execute external chaos action
    if scenario_type == "ingestion_failure":
        _set_concurrency_zero(ingestion_function_name)
    elif scenario_type == "dynamodb_throttle":
        _attach_deny_policy(lambda_role_arn)
    elif scenario_type == "lambda_cold_start":
        _set_memory_128(analysis_function_name)
    # ... etc

    # Update audit log
    update_experiment_status(experiment_id, "running", results)
    return get_experiment(experiment_id)
```

Similarly for `stop_experiment()`:

```python
def stop_experiment(experiment_id: str) -> dict[str, Any]:
    experiment = get_experiment(experiment_id)
    scenario_type = experiment["scenario_type"]

    # Restore from SSM snapshot
    _restore_from_ssm(scenario_type)

    # Update audit log
    results = experiment.get("results", {})
    results["stopped_at"] = datetime.now(UTC).isoformat() + "Z"
    update_experiment_status(experiment_id, "stopped", results)
    return get_experiment(experiment_id)
```

### Option B: Deprecate to read-only

- Remove `start_experiment()` and `stop_experiment()` from dashboard module
- Dashboard becomes read-only: view experiment history from audit log
- All chaos operations performed via CLI scripts
- Update `chaos.html` to remove start/stop buttons, show "Use CLI scripts" message

**Recommendation**: Start with Option A for feature parity. If dashboard Lambda permissions become too complex, fall back to Option B.

### 5b. Update dashboard IAM policy

If Option A, the dashboard Lambda needs additional permissions:
- `lambda:UpdateFunctionConfiguration`
- `lambda:PutFunctionConcurrency`
- `lambda:DeleteFunctionConcurrency`
- `lambda:GetFunctionConfiguration`
- `ssm:PutParameter`
- `ssm:GetParameter`
- `events:DisableRule`
- `events:EnableRule`

Alternatively, the dashboard Lambda can assume the chaos-engineer role to perform these operations, keeping its own permissions minimal.

---

## Constitution Checklist

- [ ] No secrets hardcoded (scripts use `aws` CLI with IAM role credentials)
- [ ] No `prevent_destroy` changes needed (chaos-experiments table retained)
- [ ] Cost impact: Minimal -- SSM parameters are $0.05/parameter/month, auto-restore Lambda invocations are negligible
- [ ] GPG signing: All commits signed with `git commit -S`
- [ ] Tests: Unit tests for all new code paths
- [ ] No new heavy dependencies introduced (scripts are pure bash + AWS CLI)
- [ ] Fail-safe design: Kill switch prevents injection; restore script is idempotent

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Removing embedded code breaks handlers | Low | High | Phase 1 is purely deletion; handlers pass existing non-chaos tests without modification |
| SSM snapshot becomes stale during deploy | Medium | Medium | Snapshot includes TTL; restore script warns on stale snapshots |
| Auto-restore Lambda fails during incident | Low | High | Manual andon cord script as fallback; alarm notifies operator |
| Dashboard rewire breaks chaos API | Medium | Low | Dashboard is secondary interface; scripts are primary |
| Concurrent chaos + deploy causes config thrash | Low | Medium | Inject script checks for active deploys; document in runbook |

## Rollback Plan

Each phase is independently rollable:
1. **Phase 1 rollback**: Revert handler changes, restore `chaos_injection.py` from git
2. **Phase 2 rollback**: Delete scripts directory (no production impact)
3. **Phase 3 rollback**: `terraform destroy -target=module.chaos.aws_iam_role.chaos_engineer`
4. **Phase 4 rollback**: Remove SNS subscription; auto-restore Lambda is inert
5. **Phase 5 rollback**: Revert chaos.py changes from git

Phases can be shipped incrementally. Phase 1+2 is the minimum viable refactor.
