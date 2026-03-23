# Implementation Plan: Chaos Execution Reports

**Branch**: `1240-chaos-reports` | **Date**: 2026-03-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1240-chaos-reports/spec.md`

## Summary

Add plan-level chaos report generation, DynamoDB persistence, and API retrieval to the existing chaos testing infrastructure. Reports aggregate per-scenario results from multiple experiments into a single structured JSON document with verdict logic, assertion tracking, green-dashboard-syndrome detection, and 90-day TTL. All storage reuses the existing `chaos-experiments` DynamoDB table with an `entity_type: "report"` discriminator.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: boto3 (DynamoDB), orjson (JSON serialization), aws-lambda-powertools (routing)
**Storage**: DynamoDB `{env}-chaos-experiments` table (existing, reused with entity_type discriminator)
**Testing**: pytest with moto mock_aws for DynamoDB, monkeypatch for environment
**Target Platform**: AWS Lambda (dashboard Lambda, existing)
**Project Type**: Single project (extend existing chaos module + handler)
**Performance Goals**: Report generation < 5s for 10 scenarios
**Constraints**: No new Terraform resources, no new DynamoDB tables or GSIs
**Scale/Scope**: ~3 new functions in chaos.py, ~2 new route handlers in handler.py, ~1 new test file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Status | Notes |
|--------------------------|--------|-------|
| **7) Testing & Validation** | PASS | Unit tests with moto mocks (LOCAL/DEV rule) |
| Implementation Accompaniment | PASS | Tests accompany all new functions |
| Functional Integrity | PASS | Report generation is pure logic + DynamoDB CRUD |
| Deterministic Time Handling | PASS | Uses datetime.now(UTC) consistently |
| **8) Git Workflow** | PASS | Feature branch workflow, GPG signing |
| Pre-Push Requirements | PASS | Will run make validate before push |
| **10) Local SAST** | PASS | No security-sensitive code changes |

**Gate Result**: PASS - No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1240-chaos-reports/
├── spec.md              # Feature specification
├── plan.md              # This file
├── tasks.md             # Task breakdown
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── chaos.py             # EXTEND: add generate_plan_report(), store_report(), get_report(), list_reports_by_plan()
└── handler.py           # EXTEND: add GET /chaos/reports/<id>, GET /chaos/reports routes

tests/unit/
└── test_chaos_reports.py  # NEW: unit tests for report generation, storage, API
```

**Structure Decision**: Extend `chaos.py` with new report functions rather than creating a separate module. The chaos module is already 1063 lines but report functions are logically cohesive with experiment functions. They share `_deserialize_dynamodb_item()`, `_get_dynamodb()`, `CHAOS_TABLE`, and `ChaosError`.

## Complexity Tracking

> **No violations requiring justification** - Extends existing module with new functions following established patterns.

## Phase 0: Research

### Research Tasks

1. **Existing experiment report**: Analyze `get_experiment_report()` for reusable patterns (DONE in adversarial review)
2. **DynamoDB entity_type pattern**: Verify existing chaos-experiments table supports additional entity types (DONE in adversarial review)
3. **Verdict aggregation logic**: Define how per-scenario verdicts roll up to overall verdict

### Research Findings

**Decision**: Extend `chaos.py` with plan-level report functions
**Rationale**: Keeps all chaos logic in one module, reuses existing DynamoDB client and helpers
**Alternatives considered**:
- Separate `chaos_reports.py` module (rejected: tight coupling with experiment data, would duplicate imports)
- New DynamoDB table (rejected: unnecessary infrastructure complexity)

## Phase 1: Design

### Report Data Model

```python
{
    # DynamoDB storage fields
    "experiment_id": "report-{uuid}",     # PK (prefixed to avoid collision with experiment UUIDs)
    "created_at": "2026-03-22T...",       # SK
    "entity_type": "report",             # Discriminator
    "ttl_timestamp": 1729123456,          # 90 days from now
    "status": "completed",                # For by_status GSI compatibility

    # Report content
    "report_id": "{uuid}",               # Clean ID without prefix
    "plan_name": "ingestion-resilience",
    "plan_version": 1,
    "executed_at": "2026-03-22T...",
    "environment": "preprod",
    "executor": "user-id",
    "baseline": {
        "dependencies": {...},
        "all_healthy": true
    },
    "scenarios": [
        {
            "scenario": "ingestion_failure",
            "experiment_id": "original-experiment-uuid",
            "verdict": "CLEAN",
            "assertions": [
                {"type": "metric_equals_zero", "pass": true, "actual": 0, "expected": 0}
            ],
            "duration_actual_seconds": 62,
            "recovery_time_seconds": 8,
            "started_at": "...",
            "stopped_at": "..."
        }
    ],
    "overall_verdict": "PASS",
    "green_dashboard_check": "CLEAN",
    "metadata": {
        "gate_state": "armed",
        "dry_run": false,
        "experiment_ids": ["uuid1", "uuid2"],
        "generated_at": "..."
    }
}
```

**Key design decisions**:
1. `experiment_id` PK is prefixed with `report-` to avoid UUID collision with actual experiments
2. `entity_type: "report"` enables filtering when scanning or querying
3. `status: "completed"` makes reports discoverable via the existing `by_status` GSI
4. Nested structures (baseline, scenarios, assertions) are stored as DynamoDB Maps/Lists

### Verdict Aggregation Algorithm

```
Input: list of per-scenario verdicts
Output: overall_verdict

if any scenario verdict is INCOMPLETE:
    return INCOMPLETE
if any scenario verdict is COMPROMISED:
    return COMPROMISED
if all scenario verdicts are DRY_RUN_CLEAN:
    return DRY_RUN
if no scenarios:
    return EMPTY
if all scenario verdicts are CLEAN:
    return PASS
else:
    return PARTIAL_PASS
```

### Green-Dashboard-Syndrome Algorithm

```
Input: report metadata, scenario results
Output: green_dashboard_check ("CLEAN" | "DRY_RUN" | "SUSPECT")

if metadata.dry_run or metadata.gate_state != "armed":
    return "DRY_RUN"
if all scenarios have recovery_time_seconds < 1:
    return "SUSPECT"
return "CLEAN"
```

### API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST   | /chaos/reports | Generate and store a new report |
| GET    | /chaos/reports | List reports (optional `?plan=X&limit=N`) |
| GET    | /chaos/reports/<report_id> | Get a specific report |

### Assertion Framework

Assertions are evaluated by the caller (plan executor) and passed into `generate_plan_report()` as part of each scenario's data. The report generator does not evaluate assertions -- it records and aggregates them.

Supported assertion types:
- `metric_equals_zero`: A CloudWatch metric should be 0
- `metric_below_threshold`: A metric should be below a threshold
- `recovery_time_below`: Recovery time should be below a target
- `alarm_state_equals`: A CloudWatch alarm should be in a specific state

## Phase 2: Tasks

Tasks are detailed in [tasks.md](./tasks.md).

## Phase 3: Implementation Sequence

1. **Report generation logic** (chaos.py) -- `generate_plan_report()`, verdict aggregation, green-dashboard check
2. **DynamoDB storage** (chaos.py) -- `store_report()`, `get_report()`, `list_reports_by_plan()`
3. **API routes** (handler.py) -- POST /chaos/reports, GET /chaos/reports, GET /chaos/reports/<id>
4. **Unit tests** (test_chaos_reports.py) -- all functions and API routes
5. **Integration verification** -- manual test with existing experiment data
