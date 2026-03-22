# Feature Specification: Chaos Execution Reports

**Feature Branch**: `1240-chaos-reports`
**Created**: 2026-03-22
**Status**: Draft
**Input**: Each chaos plan execution should produce a structured JSON report capturing: baseline health, per-scenario results with assertion pass/fail, recovery times, overall verdict, and green-dashboard-syndrome check. Reports are stored in DynamoDB (chaos-experiments table, new entity type) and retrievable via API.

## Adversarial Review Findings

### Existing `get_experiment_report()` Analysis

The current `get_experiment_report()` in `src/lambdas/dashboard/chaos.py` (lines 1005-1062) generates a report for a **single experiment**. It returns:
- experiment_id, scenario, status, dry_run, duration_seconds
- started_at, stopped_at
- baseline health (pre-chaos)
- post_chaos health comparison
- verdict: CLEAN | COMPROMISED | DRY_RUN_CLEAN | RECOVERY_INCOMPLETE | INCONCLUSIVE
- verdict_reason

**Limitations for plan-level reports**:
1. Single-experiment scope -- cannot aggregate across multiple scenarios in an execution plan
2. No assertion framework -- verdict is derived from health checks only, not from configurable assertions (e.g., "error count must equal zero", "recovery time < 30s")
3. No recovery time tracking -- `stopped_at - started_at` gives total duration, not recovery time
4. No green-dashboard-syndrome detection -- healthy baseline + healthy post-chaos could mask scenarios that never actually injected faults (gate was disarmed, or injection silently failed)
5. No plan metadata -- no plan_name, plan_version, or executor context

**Recommendation**: Build plan-level reports as a new layer on top of existing experiment reports. Reuse `_capture_baseline()` and `_capture_post_chaos_health()`. Do NOT modify `get_experiment_report()` -- it remains useful for single-experiment inspection.

### DynamoDB Table Structure: Reuse vs. New Table

The `chaos-experiments` table uses `experiment_id` (hash key) and `created_at` (range key) with a `by_status` GSI.

**Reuse with entity_type discrimination (RECOMMENDED)**:
- Add `entity_type` attribute: "experiment" (default, backward-compatible) or "report"
- Reports use `report_id` as the `experiment_id` hash key (both are UUIDs, no collision risk)
- Add a new GSI `by_entity_type` with `entity_type` hash key and `created_at` range key for efficient report listing
- TTL: 90 days for reports (vs. 7 days for experiments) -- uses existing `ttl_timestamp` attribute
- Pro: Zero new infrastructure, single table for all chaos data
- Con: Semantic overloading of `experiment_id` column name (but DynamoDB is schemaless, so this is acceptable)

**Why NOT a new table**: A new table requires Terraform changes, IAM policy updates for the dashboard Lambda, new environment variable injection, and module output wiring. For a simple entity type addition, this is unnecessary complexity.

**Why NOT the users table (single-table design)**: The users table uses PK/SK composite keys with entity_type discrimination. The chaos-experiments table uses a different key schema. Mixing them would require migrating existing experiments. Not worth it.

### GSI Requirement for Plan-Name Queries

US3 requires `GET /chaos/reports?plan=X`. The existing `by_status` GSI cannot serve this. Options:
1. Add a new GSI `by_plan_name` (hash: `plan_name`, range: `created_at`) -- efficient but requires Terraform change
2. Use DynamoDB Scan with filter expression -- works for small tables, but O(n) cost
3. Use the `by_entity_type` GSI with post-filter on `plan_name` -- requires scanning all reports

**Recommendation**: Use Scan with `FilterExpression` for now. The chaos-experiments table is small (dozens to hundreds of items). A GSI is premature optimization. If query volume grows, add a GSI in a future feature.

### Green-Dashboard-Syndrome Detection

"Green dashboard syndrome" means all metrics look healthy but the system was never actually tested. Indicators:
1. Gate was `disarmed` (dry-run) -- no infrastructure changes were made
2. All assertions trivially pass because the scenario had no observable effect
3. Baseline and post-chaos health are identical (no perturbation detected)
4. Recovery time is 0 or near-0 (scenario ended instantly)

Detection algorithm:
- If `dry_run=True` AND all assertions pass: verdict is `DRY_RUN` (not `PASS`)
- If all recovery times are < 1s AND gate was armed: flag as `SUSPECT` (possible silent injection failure)
- If baseline == post_chaos for all dependencies: flag as `SUSPECT`

### Recovery Time Measurement

Recovery time = time from `stop_experiment()` call to when post-chaos health returns to healthy. Currently, `stop_experiment()` captures post-chaos health immediately after restoration. This is a snapshot, not a continuous measurement.

For accurate recovery time:
1. Record `stop_requested_at` (when operator clicks stop)
2. Record `restore_completed_at` (when SSM restore finishes)
3. Record `health_verified_at` (when post-chaos health check passes)
4. Recovery time = `health_verified_at - stop_requested_at`

The existing `stopped_at` in experiment results serves as `restore_completed_at`. We need to add `health_verified_at` tracking. For this feature, recovery time is approximated as `stopped_at - started_at - duration_seconds_configured` (time spent after planned duration).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 -- Generate Structured Report from Plan Execution (Priority: P1)

After a chaos plan completes (all scenarios in the plan have been executed and stopped), the system generates a structured JSON report that aggregates results from all individual experiments in the plan. The report includes baseline health, per-scenario verdicts, assertion results, recovery times, an overall verdict, and green-dashboard-syndrome detection.

**Why this priority**: Without structured reports, chaos testing results are scattered across individual experiment records. Operators must manually piece together whether a plan succeeded or failed. Reports are the primary output artifact that justifies running chaos experiments.

**Independent Test**: Create a report from mock experiment data and validate its JSON structure against a schema.

**Acceptance Scenarios**:

1. **Given** a completed plan execution with 3 scenarios (all CLEAN), **When** a report is generated, **Then** the report contains `overall_verdict: "PASS"`, all 3 scenarios listed with individual verdicts, and `green_dashboard_check: "CLEAN"`
2. **Given** a completed plan execution with 2 CLEAN and 1 RECOVERY_INCOMPLETE scenario, **When** a report is generated, **Then** the report contains `overall_verdict: "PARTIAL_PASS"` with the failing scenario highlighted
3. **Given** a completed plan execution where the gate was disarmed (dry-run), **When** a report is generated, **Then** `overall_verdict: "DRY_RUN"` and `green_dashboard_check: "DRY_RUN"` -- the report does NOT say "PASS"
4. **Given** a completed plan execution where baseline was degraded, **When** a report is generated, **Then** `overall_verdict: "COMPROMISED"` with `verdict_reason` explaining which dependencies were degraded
5. **Given** a plan execution with 1 scenario that was never stopped (stuck in running), **When** a report is generated, **Then** that scenario is listed with `verdict: "INCOMPLETE"` and `overall_verdict: "INCOMPLETE"`
6. **Given** experiment data, **When** a report is generated, **Then** the report JSON is valid, contains all required fields (`report_id`, `plan_name`, `plan_version`, `executed_at`, `environment`, `executor`, `baseline`, `scenarios`, `overall_verdict`, `green_dashboard_check`, `metadata`), and each scenario contains `assertions` as an array

---

### User Story 2 -- Store Report in DynamoDB with 90-Day TTL (Priority: P1)

Reports are persisted in the existing `chaos-experiments` DynamoDB table using an `entity_type: "report"` discriminator. Reports have a 90-day TTL (significantly longer than the 7-day experiment TTL) because they serve as audit artifacts.

**Why this priority**: Ephemeral reports that vanish when the Lambda recycles are useless. Persistence enables trend analysis ("are we getting more PASS reports over time?"), compliance auditing, and diffing between runs.

**Independent Test**: Write a report to DynamoDB (mocked with moto), read it back, verify all fields preserved including nested structures.

**Acceptance Scenarios**:

1. **Given** a generated report, **When** it is stored, **Then** the DynamoDB item has `entity_type: "report"` and `ttl_timestamp` set to 90 days from now
2. **Given** a stored report, **When** reading it back by `report_id`, **Then** all nested structures (baseline, scenarios, assertions) are preserved without data loss or type corruption (Decimal conversion handled)
3. **Given** two reports for the same plan but different versions, **When** both are stored, **Then** they are separate items with distinct `report_id` values
4. **Given** a report stored 91 days ago, **When** DynamoDB TTL runs, **Then** the item is automatically deleted

---

### User Story 3 -- Retrieve Reports via API (Priority: P2)

Operators can retrieve reports through two endpoints:
- `GET /chaos/reports/{id}` -- get a specific report by ID
- `GET /chaos/reports?plan=X` -- list reports for a specific plan name

**Why this priority**: Reports need to be accessible to operators and CI pipelines. The API enables programmatic access for trend dashboards and automated gate checks ("did the last chaos report PASS?").

**Independent Test**: Call the API endpoints with valid/invalid parameters and verify response codes and body structure.

**Acceptance Scenarios**:

1. **Given** a stored report with `report_id: "abc-123"`, **When** `GET /chaos/reports/abc-123` is called, **Then** HTTP 200 with the full report JSON
2. **Given** no report with `report_id: "nonexistent"`, **When** `GET /chaos/reports/nonexistent` is called, **Then** HTTP 404 with `{"detail": "Report not found"}`
3. **Given** 5 reports for plan "ingestion-resilience", **When** `GET /chaos/reports?plan=ingestion-resilience` is called, **Then** HTTP 200 with array of 5 reports sorted by `executed_at` descending
4. **Given** no reports for plan "nonexistent-plan", **When** `GET /chaos/reports?plan=nonexistent-plan` is called, **Then** HTTP 200 with empty array `[]`
5. **Given** an unauthenticated request, **When** any reports endpoint is called, **Then** HTTP 401 with `{"detail": "Authentication required"}`
6. **Given** a `GET /chaos/reports?plan=X&limit=2` request, **When** there are 5 matching reports, **Then** only 2 are returned

---

### Edge Cases

- **Partial plan failure**: Some scenarios pass, some fail. The overall verdict is `PARTIAL_PASS`, not `FAIL`. This distinguishes between "everything broke" and "some things need work". If ANY scenario is `COMPROMISED` (pre-existing degradation), the overall verdict is `COMPROMISED`.
- **Dry-run vs. armed**: A report for a dry-run execution has `overall_verdict: "DRY_RUN"`, never `"PASS"`. This prevents operators from claiming resilience validation on a dry-run. The `metadata.dry_run` and `metadata.gate_state` fields make the distinction explicit and machine-readable.
- **Empty plan (zero scenarios)**: If a plan has no scenarios, the report has `overall_verdict: "EMPTY"` and `green_dashboard_check: "EMPTY"`. This prevents vacuous truth ("all zero scenarios passed, therefore PASS").
- **Concurrent report generation**: Two operators could generate reports for the same plan simultaneously. Each gets a unique `report_id`, so there is no conflict. Both are stored.
- **Report for in-progress plan**: If some experiments are still running when the report is generated, those scenarios are marked `verdict: "INCOMPLETE"` and `overall_verdict: "INCOMPLETE"`.
- **Assertion types**: The assertion framework supports: `metric_equals_zero`, `metric_below_threshold`, `recovery_time_below`, `alarm_state_equals`. Each assertion has `type`, `pass` (boolean), `actual` (observed value), and optional `expected` fields.
- **DynamoDB Decimal serialization**: Nested numeric values in assertions and recovery times must be properly deserialized from DynamoDB Decimal types. The existing `_deserialize_dynamodb_item()` handles this recursively.
- **Large reports**: A plan with many scenarios could produce a report exceeding 400KB (DynamoDB item size limit). For plans with >20 scenarios, the report should be paginated or the scenario details compressed. This is flagged but deferred -- current plans have 3-5 scenarios.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A `generate_plan_report()` function MUST accept a list of experiment IDs and plan metadata (plan_name, plan_version, executor) and return a structured report dict.
- **FR-002**: The report MUST contain all required top-level fields: `report_id` (UUID), `plan_name`, `plan_version` (int), `executed_at` (ISO8601), `environment`, `executor`, `baseline`, `scenarios` (array), `overall_verdict`, `green_dashboard_check`, `metadata`.
- **FR-003**: Each entry in the `scenarios` array MUST contain: `scenario` (string), `verdict` (CLEAN|COMPROMISED|RECOVERY_INCOMPLETE|INCONCLUSIVE|INCOMPLETE|DRY_RUN_CLEAN), `assertions` (array of assertion results), `duration_actual_seconds` (number), `recovery_time_seconds` (number), `started_at` (ISO8601), `stopped_at` (ISO8601).
- **FR-004**: Each assertion result MUST contain: `type` (string), `pass` (boolean), `actual` (any), and optional `expected` (any).
- **FR-005**: The `overall_verdict` MUST follow this precedence: INCOMPLETE > COMPROMISED > PARTIAL_PASS > DRY_RUN > PASS > EMPTY.
- **FR-006**: The `green_dashboard_check` MUST return "DRY_RUN" if gate was disarmed, "SUSPECT" if all recovery times are < 1s with armed gate, and "CLEAN" otherwise.
- **FR-007**: A `store_report()` function MUST persist the report to the `chaos-experiments` DynamoDB table with `entity_type: "report"` and `ttl_timestamp` set to 90 days.
- **FR-008**: A `get_report()` function MUST retrieve a report by `report_id` from DynamoDB, returning None if not found.
- **FR-009**: A `list_reports_by_plan()` function MUST return all reports matching a given `plan_name`, sorted by `executed_at` descending, with a configurable limit (default: 20, max: 100).
- **FR-010**: API endpoint `GET /chaos/reports/<report_id>` MUST return the report as JSON with HTTP 200, or HTTP 404 if not found. MUST require authentication.

### Non-Functional Requirements

- **NFR-001**: Report generation MUST complete within 5 seconds for plans with up to 10 scenarios.
- **NFR-002**: Report storage MUST use the existing `chaos-experiments` DynamoDB table with no new Terraform resources for the table itself.
- **NFR-003**: All report API endpoints MUST require authenticated (non-anonymous) sessions, consistent with existing chaos endpoints.
- **NFR-004**: Report JSON MUST be valid and parseable by standard JSON libraries. Decimal types from DynamoDB MUST be converted to int/float.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `generate_plan_report()` produces a report with all required fields when given a list of completed experiment IDs (verified by unit test with JSON schema validation)
- **SC-002**: A report with 3 CLEAN scenarios produces `overall_verdict: "PASS"` (verified by unit test)
- **SC-003**: A report with 1 CLEAN and 1 RECOVERY_INCOMPLETE scenario produces `overall_verdict: "PARTIAL_PASS"` (verified by unit test)
- **SC-004**: A report for a dry-run execution produces `overall_verdict: "DRY_RUN"`, never `"PASS"` (verified by unit test)
- **SC-005**: A report stored and retrieved from DynamoDB preserves all nested structures including assertions (verified by moto integration test)
- **SC-006**: `GET /chaos/reports/{id}` returns HTTP 200 with valid report JSON (verified by unit test)
- **SC-007**: `GET /chaos/reports?plan=X` returns reports filtered by plan name (verified by unit test)
- **SC-008**: Report `ttl_timestamp` is set to approximately 90 days from creation (verified by unit test)
- **SC-009**: Green-dashboard-syndrome detection correctly flags dry-run reports as "DRY_RUN" (verified by unit test)
- **SC-010**: Reports for plans with zero scenarios produce `overall_verdict: "EMPTY"` (verified by unit test)

---

## Assumptions

1. The `chaos-experiments` DynamoDB table already exists and has `ttl_timestamp` TTL enabled. (Confirmed: `infrastructure/terraform/modules/dynamodb/main.tf` lines 409-413.)
2. Plan execution is orchestrated externally (by scripts or a future plan executor). This feature generates the report after execution, not during.
3. Experiment IDs are known at report generation time. The caller passes them in.
4. The `plan_name` and `plan_version` are provided by the caller -- there is no plan registry yet.
5. The `executor` field is the authenticated user's ID from the session context.
6. No new DynamoDB GSIs are required for the initial implementation. Plan-name queries use Scan with FilterExpression.

## Out of Scope

- **Plan executor**: Automated execution of chaos plans (sequencing scenarios, waiting between them). This feature only generates reports from completed experiments.
- **Report diffing**: Comparing two reports side-by-side to see regression/improvement. Future feature.
- **Report visualization**: Rendering reports as HTML or dashboard widgets. Reports are JSON-only for now.
- **New DynamoDB GSI**: Adding a `by_plan_name` GSI for efficient plan queries. Deferred until query volume justifies it.
- **Report pagination**: Paginating large reports or large result sets. Tables are small enough for Scan.
- **Terraform changes**: No new infrastructure resources. The existing chaos-experiments table and IAM policies are sufficient.
