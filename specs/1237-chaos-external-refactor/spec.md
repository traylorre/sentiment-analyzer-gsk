# Feature Specification: Refactor Chaos Injection to External Actor Architecture

**Feature Branch**: `1237-chaos-external-refactor`
**Created**: 2026-03-22
**Status**: Draft
**Input**: The current chaos injection architecture embeds fault detection inside Lambda handlers (`is_chaos_active()`, `get_chaos_delay_ms()`, `auto_stop_expired()` in `src/lambdas/shared/chaos_injection.py`). Handlers query a DynamoDB `chaos-experiments` table on every invocation to decide whether to degrade themselves. This violates zero-trust principles and separation of concerns: application code should not contain self-sabotage logic. Chaos injection should be a purely external operation that degrades infrastructure through AWS API calls, with no application code awareness.

## Adversarial Review Findings

### Current Embedded Chaos Code Inventory

**Shared module** (`src/lambdas/shared/chaos_injection.py` -- 318 lines):
- `is_chaos_active(scenario_type)` -- Queries `chaos-experiments` DynamoDB table via `by_status` GSI for running experiments matching a scenario type. Returns `True`/`False`. Fail-safe.
- `get_chaos_delay_ms(scenario_type)` -- Same query pattern, extracts `results.delay_ms` from the experiment item. Returns `int` milliseconds or 0.
- `auto_stop_expired(scenario_type)` -- Queries running experiments, checks if `started_at + duration_seconds < now`, updates expired ones to `completed` status. Called from handler hot path on every invocation.
- Cached `_dynamodb_client` global.

**Ingestion handler** (`src/lambdas/ingestion/handler.py` lines 103-107, 194-207, 221-234):
- Imports: `auto_stop_expired`, `get_chaos_delay_ms`, `is_chaos_active` from `chaos_injection`
- Line 194: `if is_chaos_active("ingestion_failure")` -- skips all article fetching, returns early with `{"status": "chaos_active"}`
- Lines 200-201: Emits `ChaosInjectionActive` metric with `Scenario=ingestion_failure`
- Lines 221-222: `auto_stop_expired("ingestion_failure")` and `auto_stop_expired("dynamodb_throttle")`
- Lines 225-234: `is_chaos_active("dynamodb_throttle")` with `get_chaos_delay_ms("dynamodb_throttle")` and `time.sleep()`

**Analysis handler** (`src/lambdas/analysis/handler.py` lines 68-72, 121-150):
- Imports: `auto_stop_expired`, `get_chaos_delay_ms`, `is_chaos_active` from `chaos_injection`
- Lines 121-135: `get_chaos_delay_ms("lambda_cold_start")` with `time.sleep(delay_ms / 1000.0)` and metric emission
- Lines 138-147: `is_chaos_active("dynamodb_throttle")` with `get_chaos_delay_ms("dynamodb_throttle")` and `time.sleep()`
- Lines 149-150: `auto_stop_expired("lambda_cold_start")` and `auto_stop_expired("dynamodb_throttle")`

**Dashboard chaos module** (`src/lambdas/dashboard/chaos.py` -- 690 lines):
- `create_experiment()`, `get_experiment()`, `list_experiments()`, `update_experiment_status()`, `delete_experiment()` -- CRUD for DynamoDB `chaos-experiments` table
- `start_experiment()` -- Routes by `scenario_type` to set DynamoDB flag (status="running") with `injection_method: "dynamodb_flag"`
- `stop_experiment()` -- Sets status to "stopped" with `stopped_at` timestamp
- FIS integration: `start_fis_experiment()`, `stop_fis_experiment()`, `get_fis_experiment_status()` (currently unused; FIS blocked by Terraform provider bug)
- `ChaosError`, `EnvironmentNotAllowedError` exception classes

**Dashboard UI** (`src/dashboard/chaos.html`):
- Full experiment management UI with create, start, stop, view, delete
- Currently wired to dashboard Lambda API routes

**Tests** (4 files, ~1400+ lines total):
- `tests/unit/test_chaos_fis.py` -- 268+ lines testing FIS integration and experiment lifecycle
- `tests/unit/test_chaos_injection.py` -- Detection helper tests (is_chaos_active, get_chaos_delay_ms)
- `tests/unit/test_chaos_ingestion_wiring.py` -- 200 lines testing ingestion handler chaos gate
- `tests/unit/test_chaos_auto_stop.py` -- 335 lines testing auto-stop expired experiments

**Terraform**:
- `infrastructure/terraform/modules/chaos/main.tf` -- FIS execution IAM role (disabled via `enable_chaos_testing=false`), FIS experiment templates (commented out due to provider bug)
- `infrastructure/terraform/modules/iam/main.tf` -- Dashboard Lambda has `dashboard_chaos` policy with FIS + chaos-experiments DynamoDB CRUD
- `CHAOS_EXPERIMENTS_TABLE` env var injected into ingestion, analysis, and dashboard Lambdas (main.tf lines 276, 334, 407)

**DynamoDB**:
- `chaos-experiments` table with `experiment_id` hash key and `by_status` GSI

### Terraform IAM Role Structure

Current Lambda execution roles are defined in `infrastructure/terraform/modules/iam/main.tf`:
- `{env}-ingestion-lambda-role` -- DynamoDB (items table), Secrets Manager, SNS, CloudWatch, S3, SQS DLQ
- `{env}-analysis-lambda-role` -- DynamoDB (items table), CloudWatch, SQS DLQ, S3 model, time-series
- `{env}-dashboard-lambda-role` -- DynamoDB (items table + chaos-experiments), Secrets Manager, FIS, CloudWatch

The chaos-engineer IAM role will be a new standalone role (not attached to any Lambda), assumable by humans/CI with MFA.

### SSM Parameter Store Usage

SSM is already used by the canary Lambda for state persistence (`infrastructure/terraform/modules/iam/main.tf` lines 1052-1071): `ssm:GetParameter` and `ssm:PutParameter` on `arn:aws:ssm:*:*:parameter/${var.environment}/canary/*`. This confirms SSM is available and the pattern is established.

### CloudWatch Alarms for Andon Cord

The `cloudwatch-alarms` module already has:
- Lambda error alarms per function (`{env}-{service}-lambda-errors`)
- Lambda throttle alarms per function (`{env}-{service}-lambda-throttles`)
- Critical composite alarm (`{env}-critical-composite`) -- fires when ANY critical alarm fires
- SNS topic for alarm notifications (`monitoring/outputs.tf:alarm_topic_arn`)

The critical composite alarm is the natural trigger for the andon cord auto-restore. When chaos injection causes error rate to exceed threshold, the composite alarm fires, SNS publishes, and a restore Lambda can subscribe.

### EventBridge Rules

Ingestion schedule rule: `{env}-sentiment-ingestion-schedule` (rate: 5 minutes). This is the rule that would be disabled for the "trigger failure" chaos scenario.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 -- Remove All Embedded Chaos Code from Lambda Handlers (Priority: P1)

Lambda handlers must contain zero chaos awareness. All imports of `chaos_injection`, all calls to `is_chaos_active()`, `get_chaos_delay_ms()`, and `auto_stop_expired()`, and all chaos-related branching logic must be removed from the ingestion and analysis handlers. The `chaos_injection.py` shared module must be deleted.

**Why this priority**: This is the foundational change. External chaos mechanisms cannot be trusted if application code also contains self-sabotage logic. The embedded code adds latency (DynamoDB query per invocation), increases the blast radius of chaos table issues, and couples business logic to test infrastructure.

**Independent Test**: Handlers should pass all existing non-chaos unit tests without modification after removal. The handler tests that exercise normal paths do not depend on chaos imports.

**Acceptance Scenarios**:

1. **Given** the ingestion handler source code, **When** searching for any import from `chaos_injection`, **Then** zero matches are found
2. **Given** the analysis handler source code, **When** searching for any import from `chaos_injection`, **Then** zero matches are found
3. **Given** the `src/lambdas/shared/` directory, **When** listing files, **Then** `chaos_injection.py` does not exist
4. **Given** the ingestion handler is invoked normally, **When** no external chaos is active, **Then** the handler processes articles identically to pre-refactor behavior (latency reduced by eliminating DynamoDB chaos table query)
5. **Given** the analysis handler is invoked normally, **When** no external chaos is active, **Then** the handler performs inference and DynamoDB update identically to pre-refactor behavior
6. **Given** the Terraform Lambda environment variables, **When** reviewing `CHAOS_EXPERIMENTS_TABLE`, **Then** it is no longer injected into ingestion or analysis Lambdas (only dashboard retains it for audit log)

---

### User Story 2 -- Create External Chaos Scripts for All 5 Scenarios (Priority: P1)

Create a `scripts/chaos/` directory with scripts that inject faults by making AWS API calls to degrade infrastructure. No application code changes are required for these scripts to work.

**Scenarios**:
1. **Ingestion failure**: `aws lambda put-function-concurrency --function-name {ingestion} --reserved-concurrent-executions 0` (throttles all invocations; Lambda returns Throttle error)
2. **DynamoDB throttle**: Attach a deny-write IAM policy to the Lambda execution role (writes fail with AccessDenied)
3. **Cold start simulation**: `aws lambda update-function-configuration --memory-size 128 --timeout 3` (forces cold start on next invoke + degrades performance)
4. **Trigger failure**: `aws events disable-rule --name {rule}` (EventBridge stops triggering ingestion Lambda)
5. **API timeout**: `aws lambda update-function-configuration --timeout 1` (forces timeout on all invocations)

Each script must:
- Accept environment and function name as parameters
- Snapshot the current configuration to SSM before making changes
- Log all actions to the chaos-experiments DynamoDB table (audit trail)
- Validate the kill switch is not in "triggered" state before proceeding
- Support a `--dry-run` flag that shows what would change

**Why this priority**: External scripts are the replacement for the embedded code. Without them, removing the embedded code would eliminate all chaos testing capability.

**Independent Test**: Each script can be tested against LocalStack by verifying the AWS API calls it would make.

**Acceptance Scenarios**:

1. **Given** the ingestion Lambda is running normally, **When** `scripts/chaos/inject.sh ingestion-failure preprod` is executed, **Then** the Lambda's reserved concurrency is set to 0 and all subsequent invocations return Throttle errors
2. **Given** the ingestion Lambda has concurrency set to 0, **When** `scripts/chaos/restore.sh preprod` is executed, **Then** the original concurrency setting is restored from SSM snapshot
3. **Given** any chaos scenario is active, **When** the operator runs `scripts/chaos/status.sh preprod`, **Then** the output shows which scenarios are active, when they started, and the SSM snapshot location
4. **Given** the kill switch SSM parameter is set to "triggered", **When** any inject script is run, **Then** it refuses to execute and prints "Kill switch is triggered -- resolve before injecting new chaos"
5. **Given** `--dry-run` flag is passed, **When** the inject script runs, **Then** it prints the AWS commands it would execute without actually executing them
6. **Given** a cold-start injection was performed, **When** `restore.sh` is run, **Then** the Lambda's memory size and timeout are restored to their pre-chaos values from the SSM snapshot

---

### User Story 3 -- Implement Andon Cord with SSM Kill Switch and Auto-Restore (Priority: P1)

Implement a safety mechanism using SSM Parameter Store as a kill switch with automatic restoration when CloudWatch alarms fire.

**Components**:
- SSM Parameter: `/chaos/{env}/kill-switch` with values `armed` (chaos ready), `triggered` (alarm fired, restoring), `disarmed` (no chaos)
- SSM Parameter: `/chaos/{env}/snapshot` storing pre-chaos configuration as JSON
- CloudWatch Alarm -> SNS -> Auto-restore Lambda that reads snapshot and restores all configs
- Separate kill switches per environment (preprod has its own, prod has its own)

**Why this priority**: Without an andon cord, chaos experiments can cause extended outages if the operator is unavailable. The auto-restore mechanism ensures that chaos is self-limiting.

**Acceptance Scenarios**:

1. **Given** no chaos is active, **When** reading `/chaos/preprod/kill-switch`, **Then** the value is "disarmed"
2. **Given** a chaos injection script runs, **When** it stores the snapshot, **Then** `/chaos/preprod/snapshot` contains the pre-chaos configuration as valid JSON with Lambda function name, original memory, original timeout, original concurrency, and original IAM policies
3. **Given** chaos is injected and the kill switch is "armed", **When** the critical composite alarm fires, **Then** the auto-restore Lambda is triggered via SNS, sets kill switch to "triggered", reads the snapshot, restores all configurations, and sets kill switch to "disarmed"
4. **Given** the auto-restore Lambda fails to restore a configuration, **When** it catches the error, **Then** it logs the error, continues restoring remaining configurations, and leaves the kill switch in "triggered" state for manual investigation
5. **Given** the kill switch is "triggered" (mid-restore), **When** a new chaos injection script attempts to run, **Then** it refuses to execute until the kill switch returns to "disarmed"

---

### User Story 4 -- Create Chaos-Engineer IAM Role in Terraform (Priority: P2)

Create a dedicated `chaos-engineer` IAM role with least-privilege permissions for chaos operations. The role requires MFA and issues time-boxed STS credentials.

**Why this priority**: Until this role exists, chaos scripts must be run with overly-permissive admin credentials. The dedicated role ensures auditability and least-privilege access.

**Acceptance Scenarios**:

1. **Given** a Terraform plan with the chaos module enabled, **When** the plan is applied, **Then** a `{env}-chaos-engineer` IAM role is created with permissions for: `lambda:UpdateFunctionConfiguration`, `lambda:PutFunctionConcurrency`, `lambda:DeleteFunctionConcurrency`, `lambda:GetFunctionConfiguration`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `events:DisableRule`, `events:EnableRule`, `ssm:PutParameter`, `ssm:GetParameter`, `dynamodb:PutItem` (chaos-experiments table only)
2. **Given** a user without MFA, **When** they attempt to assume the chaos-engineer role, **Then** the assume fails with `AccessDenied` due to MFA condition
3. **Given** a user with MFA, **When** they assume the chaos-engineer role, **Then** STS credentials are issued with a maximum session duration of 1 hour
4. **Given** chaos operations are performed using the chaos-engineer role, **When** CloudTrail is queried, **Then** all API calls show the assumed role ARN as the principal

---

### User Story 5 -- Rewire Dashboard Chaos Module for External Architecture (Priority: P2)

The dashboard chaos module (`src/lambdas/dashboard/chaos.py`) retains its CRUD operations for the chaos-experiments DynamoDB table (audit log), but `start_experiment()` and `stop_experiment()` are rewritten to call external chaos scripts via the AWS APIs instead of setting DynamoDB flags. Alternatively, the dashboard can be simplified to a status viewer that reads experiment audit logs.

**Why this priority**: The UI is secondary to the actual chaos mechanisms. The scripts in US2 are the primary interface; the dashboard provides visibility.

**Acceptance Scenarios**:

1. **Given** the dashboard chaos module, **When** `start_experiment()` is called for `ingestion_failure`, **Then** it calls `lambda:PutFunctionConcurrency` with `ReservedConcurrentExecutions=0` on the ingestion Lambda, stores the snapshot in SSM, and creates an audit log entry in the chaos-experiments table
2. **Given** the dashboard chaos module, **When** `stop_experiment()` is called, **Then** it reads the SSM snapshot, restores the configuration, and updates the audit log entry with `stopped_at` and `restore_results`
3. **Given** the chaos-experiments table, **When** experiments are created or stopped, **Then** the DynamoDB items are populated with the same schema as before (backward-compatible for dashboard UI)
4. **Given** the dashboard `chaos.html`, **When** an operator views it, **Then** they see the experiment history and current status (no functional changes to the UI)

---

### Edge Cases

- **Mid-experiment deploy**: A Terraform apply during active chaos could overwrite the chaos-injected configuration. Mitigation: The inject script checks for active experiments before allowing deploys (documented in runbook). The SSM snapshot records the pre-chaos state, not the desired post-deploy state.
- **Concurrent experiments**: Multiple chaos scenarios can be active simultaneously (e.g., cold-start + trigger failure). Each scenario has its own SSM snapshot key (`/chaos/{env}/snapshot/{scenario}`). The restore script restores all active scenarios.
- **Kill switch failure**: If SSM is unavailable, the inject script fails safe (refuses to inject). The restore script falls back to hardcoded safe defaults (original memory=512, original timeout=30, delete concurrency limit, enable all rules).
- **Prod safety**: The chaos-engineer role is only created in preprod/dev environments. The inject scripts validate the environment parameter and refuse to operate on prod unless `--force-prod` flag is passed with MFA confirmation.
- **Stale SSM snapshots**: Snapshots include a TTL timestamp. The restore script warns if the snapshot is older than the experiment duration + 10 minutes, indicating a potential deploy occurred during chaos.
- **IAM policy attachment race**: When attaching a deny policy for DynamoDB throttle, the Lambda may already have in-flight invocations. The deny takes effect on the next API call, not the current invocation. This is expected behavior and provides a more realistic chaos scenario than instant cutoff.
- **Auto-restore Lambda cold start**: The auto-restore Lambda itself could cold-start during an incident. Keep it small (no heavy dependencies) and pre-warm via a separate EventBridge schedule.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All imports of `chaos_injection` MUST be removed from `src/lambdas/ingestion/handler.py`. The handler MUST NOT contain any reference to `is_chaos_active`, `get_chaos_delay_ms`, or `auto_stop_expired`.
- **FR-002**: All imports of `chaos_injection` MUST be removed from `src/lambdas/analysis/handler.py`. The handler MUST NOT contain any reference to `is_chaos_active`, `get_chaos_delay_ms`, or `auto_stop_expired`.
- **FR-003**: The file `src/lambdas/shared/chaos_injection.py` MUST be deleted.
- **FR-004**: A `scripts/chaos/inject.sh` script MUST support 5 chaos scenarios: `ingestion-failure`, `dynamodb-throttle`, `cold-start`, `trigger-failure`, `api-timeout`.
- **FR-005**: A `scripts/chaos/restore.sh` script MUST restore all chaos-injected configurations from SSM snapshots.
- **FR-006**: A `scripts/chaos/status.sh` script MUST display the current chaos state: active scenarios, kill switch state, and snapshot details.
- **FR-007**: Each chaos injection MUST snapshot the current configuration to SSM Parameter Store at `/chaos/{env}/snapshot/{scenario}` before making changes.
- **FR-008**: Each chaos injection MUST validate that `/chaos/{env}/kill-switch` is not `triggered` before proceeding.
- **FR-009**: Each chaos injection MUST create an audit log entry in the chaos-experiments DynamoDB table.
- **FR-010**: A Terraform resource MUST create SSM parameters `/chaos/{env}/kill-switch` with default value `disarmed`.
- **FR-011**: A Terraform resource MUST create a `{env}-chaos-engineer` IAM role with least-privilege permissions for all chaos operations, requiring MFA and limited to 1-hour sessions.
- **FR-012**: A `scripts/chaos/andon-cord.sh` script MUST allow manual triggering of the kill switch, which reads all snapshots and restores all configurations.
- **FR-013**: An auto-restore Lambda MUST subscribe to the critical composite CloudWatch alarm's SNS topic and automatically restore chaos configurations when the alarm fires.
- **FR-014**: The `CHAOS_EXPERIMENTS_TABLE` environment variable MUST be removed from ingestion and analysis Lambda configurations in Terraform. The dashboard Lambda retains it.
- **FR-015**: The `dashboard_chaos` IAM policy MUST be updated to include SSM and Lambda configuration permissions needed for the new start/stop operations, OR the dashboard delegates to the chaos-engineer role.

### Non-Functional Requirements

- **NFR-001**: Removing embedded chaos code MUST reduce median invocation latency by eliminating the DynamoDB chaos table query (estimated 5-15ms savings per invocation).
- **NFR-002**: The inject and restore scripts MUST complete within 30 seconds.
- **NFR-003**: The auto-restore Lambda MUST complete restoration within 60 seconds of alarm firing.
- **NFR-004**: All chaos operations MUST be auditable via CloudTrail.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero references to `chaos_injection` in ingestion or analysis handler source files (verified by `grep -r "chaos_injection" src/lambdas/ingestion/ src/lambdas/analysis/` returning empty)
- **SC-002**: `src/lambdas/shared/chaos_injection.py` does not exist (verified by `test ! -f`)
- **SC-003**: All 5 chaos scenarios executable via `scripts/chaos/inject.sh {scenario} {env}` (verified by dry-run against LocalStack)
- **SC-004**: `scripts/chaos/restore.sh {env}` restores all configurations from SSM (verified by comparing pre/post Lambda configs)
- **SC-005**: Kill switch prevents injection when triggered (verified by unit test)
- **SC-006**: SSM snapshot contains valid JSON with all required fields (verified by schema validation)
- **SC-007**: Chaos-engineer IAM role requires MFA (verified by Terraform plan showing MFA condition)
- **SC-008**: Existing non-chaos tests pass without modification after removing embedded chaos code (verified by `pytest tests/unit/ -k "not chaos"`)
- **SC-009**: Auto-restore Lambda successfully restores a chaos-injected configuration when the composite alarm fires (verified by integration test)
- **SC-010**: `CHAOS_EXPERIMENTS_TABLE` is not present in ingestion or analysis Lambda Terraform configuration (verified by `grep`)

---

## Assumptions

1. The `chaos-experiments` DynamoDB table is retained for audit logging. Only the query pattern changes: Lambdas no longer query it; scripts write to it.
2. SSM Parameter Store is available in all target environments (confirmed: canary Lambda already uses SSM).
3. The critical composite CloudWatch alarm (`{env}-critical-composite`) and its SNS topic are the appropriate trigger for the andon cord.
4. LocalStack supports the SSM and Lambda configuration APIs needed for testing.
5. The dashboard chaos API routes (`/chaos/*`) continue to work; only the backend implementation of `start_experiment()` and `stop_experiment()` changes.

## Out of Scope

- **AWS FIS**: FIS is still blocked by the Terraform provider bug. External scripts achieve the same chaos effects through direct AWS API calls.
- **Blast radius controls**: Partial injection (affecting X% of invocations) is not supported by the external script approach. Concurrency=0 is all-or-nothing. Fine-grained blast radius requires FIS or application-level support, which contradicts the external-actor principle.
- **Multi-region chaos**: Scripts target a single region. Multi-region chaos requires separate invocations per region.
- **Chaos scheduling**: Scheduled/recurring chaos experiments (e.g., "every Tuesday at 2am") are future work. Scripts are manually triggered.
- **Cost analysis of chaos experiments**: Tracking the cost impact of chaos (e.g., Lambda retries, DLQ depth) is an observability concern, not a chaos mechanism concern.
