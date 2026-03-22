# Feature Specification: Chaos Injection End-to-End Wiring

**Feature Branch**: `1236-chaos-injection-wiring`
**Created**: 2026-03-21
**Status**: Draft
**Input**: The chaos testing infrastructure is 75% built (dashboard UI, API routes, experiment lifecycle, DynamoDB table, detection helper, 1400+ lines of tests) but no chaos scenario actually affects production Lambda behavior. The `ingestion_failure` scenario sets a DynamoDB flag but the ingestion Lambda never checks it. The `lambda_cold_start` scenario raises `NotImplementedError` on start. The analysis handler imports `get_chaos_delay_ms` and calls it, but the experiment cannot be started. This feature wires the last-mile connections so experiments produce observable effects.

## Adversarial Review Findings

### Scenario 1: ingestion_failure

**Dashboard side (chaos.py lines 594-603)**: `start_experiment()` correctly sets the experiment status to "running" with `injection_method: "dynamodb_flag"`. `stop_experiment()` (lines 667-672) correctly sets status to "stopped". The DynamoDB-based flag mechanism is sound.

**Lambda side (ingestion/handler.py)**: The handler has **zero references** to `chaos_injection`, `is_chaos_active`, or any chaos detection. The import does not exist. The handler proceeds directly to ticker loading and article fetching with no chaos gate. This is the primary gap.

**Detection helper (shared/chaos_injection.py lines 47-122)**: `is_chaos_active(scenario_type)` is fully implemented and tested (16 tests). It queries the `by_status` GSI for running experiments matching the scenario type, returns `True`/`False`, and fails safe (returns `False` on any error). Production safety is enforced (returns `False` if `ENVIRONMENT` not in `["preprod", "dev", "test"]`).

**Gap**: Insert `is_chaos_active("ingestion_failure")` check in `lambda_handler()` before article fetching begins, after config loading. When active, skip all fetching and return an early response with a chaos indicator.

### Scenario 2: lambda_cold_start

**Dashboard side (chaos.py lines 605-607)**: `start_experiment()` raises `ChaosError("lambda_cold_start scenario not yet implemented (Phase 4)")`. Same for `stop_experiment()` at line 674-676. These are hard blocks that prevent the scenario from ever running.

**Lambda side (analysis/handler.py lines 116-126)**: The handler already imports `get_chaos_delay_ms` and calls it at the top of `lambda_handler()`. The delay injection code is complete and correct: `time.sleep(delay_ms / 1000.0)` with structured logging. This code is **already wired** but can never activate because the experiment cannot be started.

**Detection helper (shared/chaos_injection.py lines 125-204)**: `get_chaos_delay_ms(scenario_type)` is fully implemented and tested (12 tests). It queries the same GSI, extracts `delay_ms` from experiment results, and returns `int(delay_ms)` or 0 on any error.

**Gap 1**: Replace `NotImplementedError` in chaos.py `start_experiment()` with actual implementation. When starting `lambda_cold_start`, compute `delay_ms` from experiment parameters (default: 3000ms for simulating cold start), store it in results, and set status to "running".

**Gap 2**: Replace `NotImplementedError` in chaos.py `stop_experiment()` with implementation. When stopping `lambda_cold_start`, set status to "stopped" and record stop time in results.

**Gap 3**: The `delay_ms` value needs to be stored in the experiment's results so that `get_chaos_delay_ms()` can read it. The detection helper reads `experiment.get("results", {}).get("delay_ms", 0)` (chaos_injection.py line 176). The `start_experiment()` implementation must set `results.delay_ms` accordingly.

### Scenario 3: dynamodb_throttle (DEFERRED)

AWS FIS is blocked by a Terraform provider bug that prevents creating FIS experiment templates targeting DynamoDB. The app-level alternative (adding delays before DynamoDB writes) would require modifying both ingestion and analysis handlers in multiple locations, increasing scope significantly. Deferring to a future feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingestion Failure Scenario Works End-to-End (Priority: P1)

When an operator starts an `ingestion_failure` chaos experiment from the dashboard, the ingestion Lambda must detect the active experiment and skip all article fetching. When the operator stops the experiment, ingestion must resume normally on the next invocation.

**Why this priority**: This is the primary chaos scenario for validating that the system can detect and recover from ingestion pipeline failures. Without this wiring, the entire chaos infrastructure is non-functional.

**Independent Test**: Can be tested by mocking `is_chaos_active` to return True/False and verifying the handler's early-return behavior.

**Acceptance Scenarios**:

1. **Given** an `ingestion_failure` experiment is running, **When** the ingestion Lambda is invoked, **Then** it returns early with `{"status": "chaos_active", "scenario": "ingestion_failure"}` and processes zero articles
2. **Given** an `ingestion_failure` experiment is running, **When** the ingestion Lambda skips fetching, **Then** it emits a `ChaosInjectionActive` CloudWatch metric with dimension `Scenario=ingestion_failure`
3. **Given** an `ingestion_failure` experiment is running, **When** the ingestion Lambda skips fetching, **Then** it logs a structured warning: `{"message": "Chaos: skipping ingestion", "scenario": "ingestion_failure", "experiment_active": true}`
4. **Given** an `ingestion_failure` experiment was stopped, **When** the ingestion Lambda is invoked on the next cycle, **Then** it fetches and processes articles normally
5. **Given** no chaos table is configured (production), **When** `is_chaos_active()` is called, **Then** it returns `False` and ingestion proceeds normally (zero production impact)

---

### User Story 2 - Lambda Cold Start Scenario Works End-to-End (Priority: P1)

When an operator starts a `lambda_cold_start` chaos experiment from the dashboard, the analysis Lambda must experience artificial latency (configurable delay). When the operator stops the experiment, latency returns to normal.

**Why this priority**: Cold start simulation validates that downstream consumers (SSE, dashboard) handle slow analysis gracefully. The analysis handler wiring is already done -- the only blocker is that chaos.py cannot start the experiment.

**Independent Test**: Start a `lambda_cold_start` experiment via the chaos API, verify the DynamoDB record has `results.delay_ms`, verify `get_chaos_delay_ms()` returns that value.

**Acceptance Scenarios**:

1. **Given** a `lambda_cold_start` experiment is created with `parameters.delay_ms=3000`, **When** the operator starts it, **Then** the experiment status becomes "running" and `results.delay_ms=3000` is stored
2. **Given** a `lambda_cold_start` experiment is running with `delay_ms=3000`, **When** the analysis Lambda is invoked, **Then** execution is delayed by 3000ms and a structured log includes `{"scenario": "lambda_cold_start", "delay_ms": 3000}`
3. **Given** a `lambda_cold_start` experiment is created with no `parameters.delay_ms`, **When** the operator starts it, **Then** a default delay of 3000ms is used
4. **Given** a `lambda_cold_start` experiment is running, **When** the operator stops it, **Then** the experiment status becomes "stopped" and subsequent analysis invocations have no injected delay
5. **Given** a `lambda_cold_start` experiment is running, **When** the analysis Lambda emits the delay, **Then** a `ChaosInjectionActive` CloudWatch metric with dimension `Scenario=lambda_cold_start` is emitted

---

### User Story 3 - Operator Can Observe Chaos Effects in CloudWatch (Priority: P2)

When chaos experiments are active, operators must be able to see the effects in CloudWatch metrics and logs without inspecting individual Lambda invocations.

**Why this priority**: Chaos testing without observability is just breaking things. Operators need to confirm that the experiment is having the intended effect and detect when it should be stopped.

**Acceptance Scenarios**:

1. **Given** an `ingestion_failure` experiment is active, **When** the operator views CloudWatch metrics, **Then** `ChaosInjectionActive` count is incrementing every 5 minutes (ingestion schedule)
2. **Given** a `lambda_cold_start` experiment is active, **When** the operator views CloudWatch metrics, **Then** `InferenceLatencyMs` shows a visible spike corresponding to the injected delay
3. **Given** any chaos experiment is active, **When** the operator queries CloudWatch Logs Insights with `filter scenario_type = "ingestion_failure"`, **Then** matching log entries appear with structured chaos context

---

### Edge Cases

- **Experiment timeout auto-stop**: Experiments have a `duration_seconds` field (5-300s). Each Lambda invocation checks if a running experiment has exceeded its duration and auto-stops it by setting status to "completed". This is lightweight (single timestamp comparison) and piggybacks on existing chaos checks.
- **Concurrent experiments**: Multiple experiments of different scenario types could be running simultaneously (e.g., `ingestion_failure` + `lambda_cold_start`). This is safe because each Lambda checks only its relevant scenario type. Multiple experiments of the SAME type could exist; `is_chaos_active()` uses `Limit=1` and returns True if any match, which is correct.
- **Production safety**: All chaos detection functions check `ENVIRONMENT` and return safe defaults (False/0) for production. The chaos API itself (`check_environment_allowed()`) blocks experiment creation in production. Double-gated.
- **DynamoDB table not configured**: If `CHAOS_EXPERIMENTS_TABLE` env var is empty (e.g., in a new environment), both `is_chaos_active()` and `get_chaos_delay_ms()` return safe defaults. No crash, no log spam.
- **Ingestion warmup events**: The `warmup` check (handler.py line 177-186) runs before the chaos check would be inserted. Warmup invocations are not affected by chaos. This is correct -- warmup should always succeed.
- **Blast radius**: The `blast_radius` parameter is stored in experiments but not currently used for partial injection (e.g., affecting only 25% of invocations). For simplicity, all active experiments affect 100% of invocations. Blast radius support is future work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ingestion Lambda handler MUST check `is_chaos_active("ingestion_failure")` before fetching articles. When active, skip all article fetching and return early with status "chaos_active".
- **FR-002**: The ingestion Lambda MUST emit a `ChaosInjectionActive` CloudWatch metric (Count=1, Dimension: Scenario=ingestion_failure) when skipping due to chaos.
- **FR-003**: The ingestion Lambda MUST log a structured warning with fields `scenario`, `experiment_active`, and `lambda_function` when skipping due to chaos.
- **FR-004**: `chaos.py start_experiment()` MUST support the `lambda_cold_start` scenario by setting status to "running" and storing `delay_ms` in the experiment results.
- **FR-005**: `chaos.py start_experiment()` MUST use a default `delay_ms` of 3000 when `parameters.delay_ms` is not provided for `lambda_cold_start`.
- **FR-006**: `chaos.py stop_experiment()` MUST support the `lambda_cold_start` scenario by setting status to "stopped" with a `stopped_at` timestamp.
- **FR-007**: The analysis Lambda MUST emit a `ChaosInjectionActive` CloudWatch metric (Count=1, Dimension: Scenario=lambda_cold_start) when delay is injected. (Note: the `time.sleep` and log are already wired -- only the metric is missing.)
- **FR-008**: The ingestion Lambda MUST import `is_chaos_active` from `src.lambdas.shared.chaos_injection`.
- **FR-009**: The chaos check in ingestion MUST occur after warmup handling but before any external API calls (Secrets Manager, news APIs).
- **FR-010**: All chaos-related code paths MUST have zero production impact -- `is_chaos_active()` returns False when `ENVIRONMENT` is not in `["preprod", "dev", "test"]` or when `CHAOS_EXPERIMENTS_TABLE` is empty.
- **FR-011**: Each chaos check MUST also check if the running experiment has exceeded `duration_seconds` and auto-stop it by calling `stop_experiment()` or updating status to "completed". This prevents experiments from running indefinitely if the operator forgets to stop them.
- **FR-012**: The `dynamodb_throttle` scenario MUST be implemented as a lightweight app-level delay injection. When active, add `time.sleep(delay_ms / 1000)` before DynamoDB write operations in the ingestion and analysis handlers. Default delay: 500ms.
- **FR-013**: `chaos.py start_experiment()` and `stop_experiment()` MUST support `dynamodb_throttle` scenario using the same DynamoDB-flag pattern as `ingestion_failure` (no FIS dependency).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting an `ingestion_failure` experiment causes the ingestion Lambda to return `{"status": "chaos_active"}` with zero articles fetched (verified by unit test)
- **SC-002**: Stopping an `ingestion_failure` experiment causes the next ingestion Lambda invocation to fetch articles normally (verified by unit test)
- **SC-003**: Starting a `lambda_cold_start` experiment succeeds (no `NotImplementedError`) and stores `delay_ms` in results (verified by unit test)
- **SC-004**: `get_chaos_delay_ms("lambda_cold_start")` returns the stored `delay_ms` value when a `lambda_cold_start` experiment is running (verified by integration with existing test infrastructure)
- **SC-005**: Stopping a `lambda_cold_start` experiment succeeds (no `NotImplementedError`) and the analysis Lambda subsequently has zero injected delay (verified by unit test)
- **SC-006**: `ChaosInjectionActive` metrics are emitted for both scenarios with correct dimensions (verified by mocking `emit_metric`)
- **SC-007**: Zero regressions in existing chaos tests (verified by running full test suite: `test_chaos_fis.py`, `test_chaos_injection.py`)
- **SC-008**: Zero production impact -- `is_chaos_active()` returns False when environment is "production" (already verified by existing tests, re-confirmed)

## Assumptions

1. The `CHAOS_EXPERIMENTS_TABLE` environment variable is already configured in the ingestion Lambda's Terraform module for preprod/dev environments. If not, a Terraform change will be needed (out of scope, but flagged).
2. The `emit_metric()` utility from `src.lib.metrics` supports the `dimensions` parameter for adding `Scenario` dimensions.
3. The ingestion Lambda's EventBridge schedule (every 5 minutes) means chaos effects for `ingestion_failure` are observable within 5 minutes of experiment start.
4. The `delay_ms` value for `lambda_cold_start` should be configurable via experiment `parameters` at creation time. Default is 3000ms (typical Lambda cold start range is 1-5 seconds).
5. The analysis handler's existing `get_chaos_delay_ms` call and `time.sleep` at lines 117-126 are correct and do not need modification beyond adding metric emission.

## Out of Scope

- AWS FIS-based `dynamodb_throttle` (provider bug blocks FIS; using app-level workaround instead)
- Blast radius support (partial injection affecting X% of invocations)
- CloudWatch alarm kill switches for automatic experiment termination
- Dashboard UI changes (chaos.html already exists and works with the API)
- Terraform changes for `CHAOS_EXPERIMENTS_TABLE` env var injection (assumed already configured)
- Changes to the ingestion Lambda's core fetching logic, parallel fetcher, or deduplication
