# Feature Specification: First Chaos GameDay Execution

**Feature Branch**: `1243-first-chaos-gameday`
**Created**: 2026-03-22
**Status**: Draft
**Input**: The chaos testing infrastructure is fully built: external actor architecture (Feature 1237), SSM kill switch, gate/dry-run system (Feature 1238), execution plans and reports (Features 1239/1240), 5 chaos scenarios wired via `scripts/chaos/inject.sh`, `chaos.py` dashboard API, and Playwright e2e tests. What is missing is the first real execution. No chaos plan YAML file exists. No GameDay runbook exists. No baseline report has ever been generated. This feature creates the operational artifacts and executes the first controlled chaos experiment against preprod, producing the baseline report that all future runs diff against.

**Nature**: This is an operational milestone, not a code feature. The "implementation" is artifacts (YAML plans, runbook, checklist) and the execution of the first real chaos plan with the gate armed.

## Adversarial Review Findings

### Chaos Infrastructure Readiness Audit

**External actor scripts** (`scripts/chaos/inject.sh`, `restore.sh`, `status.sh`, `andon-cord.sh`):
All four scripts exist and follow the external actor pattern. `inject.sh` supports 5 scenarios: `ingestion-failure`, `dynamodb-throttle`, `cold-start`, `trigger-failure`, `api-timeout`. Each scenario snapshots to SSM before degrading, validates the kill switch, and supports `--dry-run`. The `restore.sh` script reads SSM snapshots and reverses changes. The `andon-cord.sh` manually triggers the kill switch and restores all active experiments.

**Dashboard chaos API** (`src/lambdas/dashboard/chaos.py` -- 1063 lines):
Full CRUD for experiments, external actor `start_experiment()` and `stop_experiment()` with gate pattern, `_capture_baseline()` and `_capture_post_chaos_health()` for pre/post health comparison, and `get_experiment_report()` for structured verdicts (`CLEAN`, `COMPROMISED`, `DRY_RUN_CLEAN`, `RECOVERY_INCOMPLETE`, `INCONCLUSIVE`).

**Gate system** (SSM `/chaos/{env}/kill-switch`):
Three states: `armed` (proceed with real infrastructure changes), `disarmed` (dry-run mode -- record signals, skip infrastructure changes), `triggered` (emergency stop -- block all chaos operations). The gate defaults to `disarmed` if the SSM parameter does not exist.

**Gap 1: No chaos plan YAML files exist.** The execution plans feature (1239) created the directory structure but no actual plan files. The first plan must define the `ingestion-resilience` scenario covering `ingestion_failure` and `dynamodb_throttle`.

**Gap 2: No GameDay runbook exists.** Operators have no step-by-step guide for executing a chaos plan. The existing docs (`docs/chaos-testing/PHASE3_API_FAILURE.md`, `PHASE4_LAMBDA_DELAY.md`) document individual scenarios but not the full GameDay lifecycle (pre-flight, execution, observation, post-mortem).

**Gap 3: No pre-flight checklist exists.** There is no formal verification that the environment is healthy and safe before injecting chaos. The `_capture_baseline()` function checks dependencies programmatically, but operators need a human-readable checklist covering alarms, dashboard accessibility, andon cord readiness, and team notification.

**Gap 4: No baseline report exists.** `get_experiment_report()` can generate reports, but no report has ever been produced. The first report establishes the baseline that future GameDays diff against to detect resilience regressions.

### Pre-Conditions for Execution

1. **Preprod environment must be deployed and healthy.** The dashboard Lambda must be reachable at its Function URL, DynamoDB tables must exist, CloudWatch alarms must be in OK state.
2. **SSM kill switch must be explicitly armed.** The gate defaults to `disarmed` (dry-run). To execute a real chaos experiment, an operator must set `/chaos/preprod/kill-switch` to `armed`.
3. **At least one ingestion cycle must have completed recently.** The `ingestion_failure` scenario throttles the ingestion Lambda. To observe the effect, there must be a recent baseline of successful ingestion cycles.
4. **CloudWatch dashboard must be accessible.** The operator must be able to observe metrics in real-time during the experiment.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 -- Create Ingestion Resilience Chaos Plan (Priority: P1)

Create the first chaos plan YAML file defining a two-scenario execution sequence: `ingestion_failure` followed by `dynamodb_throttle`. The plan specifies scenario parameters, duration, expected behaviors, and assertion criteria.

**Why this priority**: Without a plan file, there is no structured, repeatable, auditable way to execute chaos. Ad-hoc experiments via the dashboard API are not auditable and cannot be diffed across runs.

**Independent Test**: Validate the YAML file against the plan schema (well-formed YAML, required fields present, scenario types match valid set, durations within bounds).

**Acceptance Scenarios**:

1. **Given** the chaos plan file `chaos-plans/ingestion-resilience.yaml` exists, **When** parsed as YAML, **Then** it contains `name`, `version`, `scenarios` (list), and `assertions` fields
2. **Given** the plan defines scenario `ingestion_failure`, **When** reading its parameters, **Then** `duration_seconds` is 120, `blast_radius` is 100, and `expected_behavior` describes throttled invocations and EventBridge DLQ routing
3. **Given** the plan defines scenario `dynamodb_throttle`, **When** reading its parameters, **Then** `duration_seconds` is 120, `blast_radius` is 100, and `expected_behavior` describes write failures and retry/DLQ behavior
4. **Given** the plan defines assertions, **When** reading them, **Then** they include: (a) ingestion Lambda invocation count drops to 0 during `ingestion_failure`, (b) CloudWatch error alarm transitions to ALARM state, (c) system recovers within 5 minutes after restore, (d) no data loss (DLQ messages are reprocessed)
5. **Given** the plan, **When** an operator reads it, **Then** the `observation_period_seconds` is at least 300 (5 minutes) to allow recovery verification

---

### User Story 2 -- Create GameDay Runbook (Priority: P1)

Create a comprehensive operator guide (`docs/chaos-testing/gameday-runbook.md`) with three sections: pre-flight, execution, and post-mortem. The runbook references the chaos plan, the pre-flight checklist, and the chaos scripts.

**Why this priority**: The runbook is the operational contract. Without it, operators make judgment calls during a high-stress chaos experiment. Every decision should be pre-made and documented.

**Independent Test**: The runbook can be reviewed for completeness by verifying all referenced commands exist and all linked files are valid paths.

**Acceptance Scenarios**:

1. **Given** the runbook exists at `docs/chaos-testing/gameday-runbook.md`, **When** an operator reads the pre-flight section, **Then** they find: (a) link to pre-flight checklist, (b) command to verify environment health (`scripts/chaos/status.sh preprod`), (c) command to arm the gate (`aws ssm put-parameter --name /chaos/preprod/kill-switch --value armed`), (d) team notification instructions
2. **Given** the runbook execution section, **When** an operator follows it step-by-step, **Then** they can: (a) create an experiment via the dashboard API, (b) start the experiment, (c) observe metrics in CloudWatch, (d) stop the experiment, (e) verify recovery
3. **Given** the runbook post-mortem section, **When** the experiment completes, **Then** the operator knows how to: (a) generate the experiment report (`GET /api/chaos/experiments/{id}/report`), (b) save the report as the baseline, (c) disarm the gate, (d) write up findings

---

### User Story 3 -- Execute Plan and Generate First Baseline Report (Priority: P1)

Execute the ingestion-resilience chaos plan against preprod with the gate armed. This is a manual operational step that produces the first baseline report stored in `reports/chaos/`.

**Why this priority**: The baseline report is the deliverable. Without it, future chaos runs have nothing to diff against, and there is no evidence that the chaos infrastructure actually works end-to-end in a real environment.

**Independent Test**: The report file exists in `reports/chaos/`, contains a valid JSON structure with verdict, and the verdict is not `INCONCLUSIVE`.

**Acceptance Scenarios**:

1. **Given** the gate is armed and preprod is healthy, **When** the operator executes the `ingestion_failure` scenario, **Then** the ingestion Lambda's reserved concurrency is set to 0 and subsequent invocations are throttled
2. **Given** the `ingestion_failure` experiment is running, **When** the operator checks CloudWatch, **Then** the ingestion Lambda error count increases and the ingestion success metric drops to 0
3. **Given** the operator stops the experiment, **When** they check the experiment report, **Then** the verdict is `CLEAN` (system recovered to healthy state) or `RECOVERY_INCOMPLETE` (with documented reason)
4. **Given** the first report is generated, **When** stored at `reports/chaos/baseline-ingestion-resilience-YYYY-MM-DD.json`, **Then** it contains `experiment_id`, `scenario`, `verdict`, `baseline`, `post_chaos`, `started_at`, `stopped_at`
5. **Given** all scenarios in the plan are executed, **When** the operator reviews all reports, **Then** there is one report per scenario and a summary report for the full GameDay

---

### User Story 4 -- Create Cold-Start Resilience Chaos Plan (Priority: P2)

Create a second chaos plan YAML file for the `lambda_cold_start` and `api_timeout` scenarios. This plan tests the analysis pipeline's resilience to performance degradation.

**Why this priority**: P2 because the ingestion-resilience plan must be executed first to validate the GameDay process. The cold-start plan can be executed in a subsequent GameDay.

**Acceptance Scenarios**:

1. **Given** the chaos plan file `chaos-plans/cold-start-resilience.yaml` exists, **When** parsed as YAML, **Then** it contains scenarios for `lambda_cold_start` (memory reduction to 128MB) and `api_timeout` (timeout set to 1s)
2. **Given** the plan defines `lambda_cold_start` scenario, **When** reading its parameters, **Then** `duration_seconds` is 180, `target` is `analysis`, and `expected_behavior` describes increased latency and potential cold start overhead
3. **Given** the plan defines `api_timeout` scenario, **When** reading its parameters, **Then** `duration_seconds` is 60, `target` is `ingestion`, `timeout` is 1, and `expected_behavior` describes all invocations timing out

---

### Edge Cases

- **Preprod not in healthy state**: The `_capture_baseline()` function detects degraded dependencies and sets `baseline.all_healthy = false`. The pre-flight checklist requires all dependencies healthy before proceeding. If the baseline shows degradation, the runbook instructs the operator to ABORT and investigate the pre-existing issue first. A chaos experiment on a degraded system produces a `COMPROMISED` verdict that is useless as a baseline.
- **Alarms already firing**: If CloudWatch alarms are in ALARM state before chaos injection, the operator cannot distinguish chaos-induced failures from pre-existing ones. The pre-flight checklist requires all critical alarms in OK state. The `status.sh` script checks alarm states.
- **Dashboard unreachable**: If the dashboard Lambda's Function URL is unreachable, the operator cannot create/start/stop experiments via the API. Fallback: use `scripts/chaos/inject.sh` directly (bypasses the dashboard API, still logs to DynamoDB). The runbook documents this fallback path.
- **Kill switch SSM parameter not found**: The gate defaults to `disarmed` (dry-run) if the SSM parameter does not exist. The operator must explicitly create and arm it before the first GameDay. The pre-flight checklist verifies the parameter exists.
- **Operator unavailable during experiment**: Experiments have `duration_seconds`. The dashboard API's auto-stop mechanism (if wired) or manual `andon-cord.sh` execution by another team member provides safety. The runbook requires a buddy operator for every GameDay.
- **Concurrent GameDay with production deploy**: A Terraform apply during chaos could overwrite the chaos-injected config. The pre-flight checklist requires confirming no deploys are scheduled during the GameDay window. The runbook instructs the operator to pause CI/CD merge queues.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A chaos plan file `chaos-plans/ingestion-resilience.yaml` MUST exist with `name`, `version`, `description`, `scenarios` (list of scenario objects), `assertions` (list of assertion objects), and `observation_period_seconds` fields.
- **FR-002**: Each scenario object in the plan MUST contain `id`, `type` (matching a valid scenario from `inject.sh`), `duration_seconds`, `blast_radius`, `expected_behavior` (human-readable), and `observation_metrics` (list of CloudWatch metric names to watch).
- **FR-003**: Each assertion object MUST contain `id`, `description`, `metric`, `condition` (e.g., "equals_zero", "transitions_to_alarm", "recovers_within"), and `threshold` where applicable.
- **FR-004**: A GameDay runbook MUST exist at `docs/chaos-testing/gameday-runbook.md` with sections: Overview, Pre-Flight, Execution (per-scenario steps), Post-Mortem, Baseline Storage, and Emergency Procedures.
- **FR-005**: A pre-flight checklist MUST exist at `docs/chaos-testing/preflight-checklist.md` with verifiable items: environment health, alarm states, dashboard accessibility, gate state, team notification, buddy operator confirmation, and CI/CD pause.
- **FR-006**: The first baseline report MUST be stored at `reports/chaos/baseline-ingestion-resilience-YYYY-MM-DD.json` after successful execution.
- **FR-007**: The baseline report MUST contain at minimum: `experiment_id`, `scenario`, `status`, `verdict`, `verdict_reason`, `baseline` (pre-chaos health), `post_chaos` (post-chaos health comparison), `started_at`, `stopped_at`, `dry_run`, and `duration_seconds`.
- **FR-008**: A second chaos plan file `chaos-plans/cold-start-resilience.yaml` MUST exist with scenarios for `lambda_cold_start` and `api_timeout`.
- **FR-009**: The pre-flight checklist MUST include a "No-Go Criteria" section listing conditions that abort the GameDay (degraded dependencies, alarms firing, no buddy operator, pending deploys).
- **FR-010**: The runbook MUST document the fallback path for executing chaos when the dashboard is unreachable (direct `inject.sh` usage).

### Non-Functional Requirements

- **NFR-001**: All chaos plan YAML files MUST be valid YAML parseable by PyYAML.
- **NFR-002**: The runbook and checklist MUST be written in Markdown with actionable, copy-paste-ready commands.
- **NFR-003**: The GameDay execution window MUST not exceed 60 minutes (including pre-flight and post-mortem).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `chaos-plans/ingestion-resilience.yaml` exists and is valid YAML with all required fields (verified by `python -c "import yaml; yaml.safe_load(open('chaos-plans/ingestion-resilience.yaml'))"`)
- **SC-002**: `docs/chaos-testing/gameday-runbook.md` exists with all three sections (pre-flight, execution, post-mortem) and all referenced commands are valid
- **SC-003**: `docs/chaos-testing/preflight-checklist.md` exists with verifiable items and no-go criteria
- **SC-004**: `chaos-plans/cold-start-resilience.yaml` exists and is valid YAML
- **SC-005**: After GameDay execution, `reports/chaos/baseline-ingestion-resilience-YYYY-MM-DD.json` exists with a non-INCONCLUSIVE verdict
- **SC-006**: The baseline report verdict is `CLEAN` (system recovered fully) -- if not, the report documents specific recovery gaps for follow-up
- **SC-007**: All assertions in the chaos plan are verified during execution and results annotated in the report

---

## Assumptions

1. Preprod environment is deployed and accessible. The dashboard Lambda Function URL is reachable.
2. The `scripts/chaos/inject.sh`, `restore.sh`, `status.sh`, and `andon-cord.sh` scripts work correctly against preprod (verified in Features 1237/1238).
3. The `chaos.py` dashboard API (`start_experiment`, `stop_experiment`, `get_experiment_report`) works correctly against preprod.
4. CloudWatch alarms are configured for the ingestion and analysis Lambdas.
5. The operator has AWS credentials with sufficient permissions to modify Lambda configurations and read/write SSM parameters.
6. The `reports/chaos/` directory may not exist yet and must be created as part of the first GameDay.

## Out of Scope

- Code changes to Lambda handlers, chaos.py, or chaos scripts (infrastructure is assumed complete)
- New Terraform resources (no infrastructure changes)
- Automated chaos execution (plans are executed manually by operators)
- Load testing or performance benchmarking during chaos
- Multi-region chaos scenarios
- Chaos scheduling or recurring GameDay automation
