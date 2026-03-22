# Tasks: Chaos Execution Reports

**Branch**: `1240-chaos-reports` | **Date**: 2026-03-22
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Task 1: Add `generate_plan_report()` to chaos.py

**FR**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006
**SC**: SC-001, SC-002, SC-003, SC-004, SC-009, SC-010
**File**: `src/lambdas/dashboard/chaos.py`

### Description

Add a `generate_plan_report()` function that accepts a list of experiment IDs and plan metadata, fetches each experiment from DynamoDB, aggregates their results into a structured report, computes the overall verdict, and runs the green-dashboard-syndrome detection.

### Subtasks

- [ ] 1.1: Define `generate_plan_report(experiment_ids, plan_name, plan_version, executor)` function signature
- [ ] 1.2: Implement experiment fetching loop -- call `get_experiment()` for each ID, handle missing experiments gracefully
- [ ] 1.3: Extract per-scenario data from each experiment's results (scenario_type, started_at, stopped_at, dry_run, baseline, post_chaos_health)
- [ ] 1.4: Compute `duration_actual_seconds` from started_at/stopped_at timestamps
- [ ] 1.5: Compute `recovery_time_seconds` from experiment results (stopped_at minus started_at minus configured duration, floor at 0)
- [ ] 1.6: Map experiment verdicts to scenario verdicts using existing `get_experiment_report()` logic
- [ ] 1.7: Implement assertion pass-through -- accept assertions as optional parameter per scenario, include in report
- [ ] 1.8: Implement `_compute_overall_verdict(scenario_verdicts)` following precedence: INCOMPLETE > COMPROMISED > DRY_RUN > EMPTY > PASS > PARTIAL_PASS
- [ ] 1.9: Implement `_check_green_dashboard_syndrome(metadata, scenarios)` returning "CLEAN", "DRY_RUN", or "SUSPECT"
- [ ] 1.10: Assemble the complete report dict with all required fields (report_id, plan_name, plan_version, executed_at, environment, executor, baseline, scenarios, overall_verdict, green_dashboard_check, metadata)
- [ ] 1.11: Use the baseline from the first experiment (all scenarios in a plan share the same baseline capture)

### Acceptance Criteria

- `generate_plan_report()` returns a dict with all fields from FR-002
- Each scenario entry has all fields from FR-003
- Verdict precedence follows FR-005
- Green dashboard check follows FR-006

---

## Task 2: Add DynamoDB report persistence functions to chaos.py

**FR**: FR-007, FR-008, FR-009
**SC**: SC-005, SC-007, SC-008
**File**: `src/lambdas/dashboard/chaos.py`

### Description

Add `store_report()`, `get_report()`, and `list_reports_by_plan()` functions for DynamoDB persistence of chaos reports using the existing `chaos-experiments` table with entity_type discrimination.

### Subtasks

- [ ] 2.1: Implement `store_report(report)` -- write to chaos-experiments table with entity_type="report", PK=report-{uuid}, ttl_timestamp=now+90days
- [ ] 2.2: Implement `get_report(report_id)` -- read from chaos-experiments table using PK=report-{report_id}, filter by entity_type="report"
- [ ] 2.3: Implement `list_reports_by_plan(plan_name, limit=20)` -- Scan with FilterExpression for entity_type="report" AND plan_name=:plan, sorted by executed_at desc
- [ ] 2.4: Handle DynamoDB Decimal serialization in report storage (nested dicts, lists)
- [ ] 2.5: Handle the composite key -- `experiment_id` column stores `report-{uuid}`, `created_at` stores the report's `executed_at`
- [ ] 2.6: Add `list_reports(limit=20)` -- Scan with FilterExpression for entity_type="report" only (for the general GET /chaos/reports endpoint)

### Acceptance Criteria

- Reports stored with 90-day TTL (FR-007, SC-008)
- Reports retrievable by ID with full nested structure preserved (FR-008, SC-005)
- Reports filterable by plan_name (FR-009, SC-007)
- Limit parameter clamped to 1-100 range

---

## Task 3: Add API route handlers to handler.py

**FR**: FR-010
**SC**: SC-006
**File**: `src/lambdas/dashboard/handler.py`

### Description

Add three new route handlers for chaos reports: POST (generate+store), GET by ID, and GET list. Follow the existing chaos endpoint patterns for authentication, error handling, and response formatting.

### Subtasks

- [ ] 3.1: Add imports for new report functions (`generate_plan_report`, `store_report`, `get_report`, `list_reports_by_plan`, `list_reports`) to handler.py
- [ ] 3.2: Implement `POST /chaos/reports` handler -- parse body for experiment_ids, plan_name, plan_version; call generate_plan_report(); call store_report(); return 201 with report
- [ ] 3.3: Implement `GET /chaos/reports/<report_id>` handler -- call get_report(); return 200 or 404
- [ ] 3.4: Implement `GET /chaos/reports` handler -- parse query params (plan, limit); call list_reports_by_plan() or list_reports(); return 200
- [ ] 3.5: Add authentication checks (require non-anonymous session) to all report endpoints
- [ ] 3.6: Add error handling: ChaosError -> 500, ValueError -> 400, EnvironmentNotAllowedError -> 403
- [ ] 3.7: Update the `/api` index endpoint to include new report routes in the chaos section
- [ ] 3.8: Use orjson for JSON serialization (consistent with existing handlers)

### Acceptance Criteria

- All 3 endpoints require authentication (NFR-003)
- GET by ID returns 200 or 404 (FR-010)
- POST returns 201 with generated report
- GET list supports ?plan=X&limit=N query parameters

---

## Task 4: Add unit tests for report generation

**SC**: SC-001, SC-002, SC-003, SC-004, SC-009, SC-010
**File**: `tests/unit/test_chaos_reports.py`

### Description

Create comprehensive unit tests for `generate_plan_report()`, verdict aggregation, and green-dashboard-syndrome detection. Use mock experiment data to test all verdict paths.

### Subtasks

- [ ] 4.1: Create test fixtures: mock experiments with various statuses (stopped/CLEAN, stopped/COMPROMISED, running/INCOMPLETE, dry-run)
- [ ] 4.2: Test `generate_plan_report()` with 3 CLEAN scenarios -- verify overall_verdict="PASS" (SC-002)
- [ ] 4.3: Test with mixed verdicts (1 CLEAN + 1 RECOVERY_INCOMPLETE) -- verify overall_verdict="PARTIAL_PASS" (SC-003)
- [ ] 4.4: Test with all dry-run scenarios -- verify overall_verdict="DRY_RUN" (SC-004)
- [ ] 4.5: Test with compromised baseline -- verify overall_verdict="COMPROMISED"
- [ ] 4.6: Test with in-progress experiment -- verify overall_verdict="INCOMPLETE"
- [ ] 4.7: Test with empty experiment list -- verify overall_verdict="EMPTY" (SC-010)
- [ ] 4.8: Test green-dashboard-syndrome: dry-run -> "DRY_RUN" (SC-009)
- [ ] 4.9: Test green-dashboard-syndrome: all recovery times < 1s -> "SUSPECT"
- [ ] 4.10: Test green-dashboard-syndrome: normal execution -> "CLEAN"
- [ ] 4.11: Test report JSON schema -- all required fields present (SC-001)
- [ ] 4.12: Test assertion pass-through -- assertions included in scenario entries
- [ ] 4.13: Test missing experiment handling -- nonexistent IDs produce scenario with verdict="NOT_FOUND"

---

## Task 5: Add unit tests for DynamoDB report persistence

**SC**: SC-005, SC-007, SC-008
**File**: `tests/unit/test_chaos_reports.py`

### Description

Test report storage and retrieval using moto's mock_aws for DynamoDB. Verify TTL, nested structure preservation, and query filtering.

### Subtasks

- [ ] 5.1: Create moto DynamoDB table fixture matching chaos-experiments schema (PK: experiment_id, SK: created_at, GSI: by_status)
- [ ] 5.2: Test `store_report()` -- verify item written with entity_type="report" and correct ttl_timestamp (SC-008)
- [ ] 5.3: Test `get_report()` -- store then retrieve, verify all nested structures preserved (SC-005)
- [ ] 5.4: Test `get_report()` with nonexistent ID -- verify returns None
- [ ] 5.5: Test `list_reports_by_plan()` -- store 3 reports for plan A and 2 for plan B, query plan A, verify 3 results (SC-007)
- [ ] 5.6: Test `list_reports_by_plan()` with limit parameter
- [ ] 5.7: Test `list_reports()` -- verify returns only entity_type="report" items, not experiments
- [ ] 5.8: Test Decimal serialization round-trip for numeric fields in nested assertions

---

## Task 6: Add unit tests for API route handlers

**SC**: SC-006
**File**: `tests/unit/test_chaos_reports.py`

### Description

Test the HTTP route handlers for reports, following the existing pattern in `test_dashboard_handler.py` for chaos endpoints.

### Subtasks

- [ ] 6.1: Test `GET /chaos/reports/{id}` with valid report -- verify 200 response with report JSON (SC-006)
- [ ] 6.2: Test `GET /chaos/reports/{id}` with nonexistent ID -- verify 404 response
- [ ] 6.3: Test `GET /chaos/reports?plan=X` -- verify 200 with filtered results
- [ ] 6.4: Test `GET /chaos/reports` without plan filter -- verify 200 with all reports
- [ ] 6.5: Test `POST /chaos/reports` with valid body -- verify 201 with generated report
- [ ] 6.6: Test `POST /chaos/reports` with missing required fields -- verify 400
- [ ] 6.7: Test all endpoints without authentication -- verify 401
- [ ] 6.8: Test all endpoints return valid JSON (orjson serialization)

---

## Task 7: Update handler.py API index

**FR**: N/A (documentation)
**File**: `src/lambdas/dashboard/handler.py`

### Description

Update the `/api` index endpoint to include the new report routes in the chaos section.

### Subtasks

- [ ] 7.1: Add `POST /chaos/reports` entry: "Generate chaos execution report"
- [ ] 7.2: Add `GET /chaos/reports` entry: "List chaos reports"
- [ ] 7.3: Add `GET /chaos/reports/{id}` entry: "Get chaos report by ID"

### Acceptance Criteria

- `/api` response includes all 3 new report routes in the chaos section

---

## Dependency Graph

```
Task 1 (generate_plan_report)
    ↓
Task 2 (DynamoDB persistence)
    ↓
Task 3 (API routes) ← depends on Tasks 1 + 2
    ↓
Task 4 (generation tests) ← depends on Task 1
Task 5 (persistence tests) ← depends on Task 2
Task 6 (API tests) ← depends on Task 3
Task 7 (API index) ← depends on Task 3
```

**Parallelizable**: Tasks 4+5 can be developed in parallel after Tasks 1+2 are complete.

---

## Estimated Effort

| Task | Effort | Risk |
|------|--------|------|
| Task 1: Report generation | Medium | Low -- pure logic, no external deps |
| Task 2: DynamoDB persistence | Low | Low -- follows existing CRUD patterns |
| Task 3: API routes | Low | Low -- follows existing handler patterns |
| Task 4: Generation tests | Medium | Low -- many test cases but straightforward |
| Task 5: Persistence tests | Low | Low -- moto DynamoDB is well-established |
| Task 6: API tests | Low | Low -- follows existing test patterns |
| Task 7: API index update | Trivial | None |

**Total**: ~4-6 hours of implementation time.
