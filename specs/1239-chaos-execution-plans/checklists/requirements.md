# Feature 1239: Requirements Checklist

## Functional Requirements Traceability

| FR | Description | User Story | Priority | Status |
|----|-------------|------------|----------|--------|
| FR-001 | YAML plan schema definition | US1 | P1 | [ ] |
| FR-002 | Plan validation before execution | US1 | P1 | [ ] |
| FR-003 | Sequential scenario execution | US2 | P1 | [ ] |
| FR-004 | Mid-plan failure handling | US2 | P1 | [ ] |
| FR-005 | Assertion: metric_equals_zero | US3 | P2 | [ ] |
| FR-006 | Assertion: metric_increases | US3 | P2 | [ ] |
| FR-007 | Assertion: alarm_fires | US3 | P2 | [ ] |
| FR-008 | Assertion: alarm_ok | US3 | P2 | [ ] |
| FR-009 | Consolidated plan report | US2 | P1 | [ ] |
| FR-010 | Dry-run mode | US2 | P1 | [ ] |
| FR-011 | CLI interface | US2 | P1 | [ ] |
| FR-012 | Concurrent plan execution guard | US2 | P1 | [ ] |

## Edge Cases

| EC | Description | Handling | Status |
|----|-------------|----------|--------|
| EC-001 | Plan validation errors | Clear error message, exit 1, no experiments created | [ ] |
| EC-002 | Mid-plan failure | Stop current experiment, SKIP remaining, partial report | [ ] |
| EC-003 | Assertion timeout | Mark as TIMEOUT (not FAIL), scenario verdict = INCONCLUSIVE | [ ] |
| EC-004 | Concurrent plan execution | Refuse to start, suggest wait or andon cord | [ ] |
| EC-005 | Kill switch triggered mid-plan | Abort immediately, report interruption | [ ] |
| EC-006 | CloudWatch data lag | Warn when within_seconds < 60 for metric_* assertions | [ ] |
| EC-007 | Alarm name resolution | Prepend environment, descriptive error if alarm not found | [ ] |

## Safety Requirements

| # | Requirement | Verified By | Status |
|---|-------------|-------------|--------|
| S-001 | Never allow prod environment | chaos.py check_environment_allowed() | [ ] |
| S-002 | Respect kill switch state | Kill switch checked before each scenario | [ ] |
| S-003 | Respect gate state (armed/disarmed) | start_experiment() handles gate | [ ] |
| S-004 | Always attempt stop_experiment on failure | try/finally in executor | [ ] |
| S-005 | Concurrent execution prevention | DynamoDB consistent read guard | [ ] |
| S-006 | Plan validation before any execution | Validation runs as first step | [ ] |

## Reuse Requirements (Existing Infrastructure)

| # | What is Reused | Source | Verified Exists |
|---|---------------|--------|-----------------|
| R-001 | create_experiment() | chaos.py:125-212 | [x] |
| R-002 | start_experiment() | chaos.py:746-923 | [x] |
| R-003 | stop_experiment() | chaos.py:926-1002 | [x] |
| R-004 | get_experiment_report() | chaos.py:1005-1062 | [x] |
| R-005 | list_experiments() (concurrent guard) | chaos.py:247-290 | [x] |
| R-006 | check_environment_allowed() | chaos.py:106-117 | [x] |
| R-007 | ChaosError exception hierarchy | chaos.py:94-103 | [x] |
| R-008 | Kill switch/gate mechanisms | chaos.py:421-476 | [x] |
| R-009 | CloudWatch alarm names | Terraform cloudwatch-alarms module | [x] |
| R-010 | Custom metric namespaces | Terraform monitoring module | [x] |

## Assertion Data Source Verification

| Assertion Target | CloudWatch Resource | Exists in Terraform | Verified |
|-----------------|--------------------|--------------------|----------|
| ingestion-lambda-throttles | alarm | cloudwatch-alarms/main.tf:119 | [x] |
| ingestion-lambda-errors | alarm | cloudwatch-alarms/main.tf:60 | [x] |
| analysis-lambda-errors | alarm | cloudwatch-alarms/main.tf:60 | [x] |
| critical-composite | composite alarm | cloudwatch-alarms/main.tf:308 | [x] |
| NewItemsIngested | custom metric | monitoring/main.tf (SentimentAnalyzer ns) | [x] |
| Errors (AWS/Lambda) | standard metric | AWS built-in | [x] |
| Throttles (AWS/Lambda) | standard metric | AWS built-in | [x] |
| Duration (AWS/Lambda) | standard metric | AWS built-in | [x] |
| SilentFailure/Count | custom metric | SentimentAnalyzer/Reliability ns | [x] |
| ConnectionCount | custom metric | SentimentAnalyzer/SSE ns | [x] |
| CollisionRate | custom metric | SentimentAnalyzer/Ingestion ns | [x] |

## New Files

| File | Purpose | Phase |
|------|---------|-------|
| `scripts/chaos/plan_schema.py` | Pydantic models for plan validation | 1 |
| `scripts/chaos/assertion_engine.py` | CloudWatch assertion checking | 2 |
| `scripts/chaos/plan_executor.py` | Plan orchestration engine | 3 |
| `scripts/chaos/run-plan.py` | CLI entry point | 4 |
| `scripts/chaos/plans/ingestion-resilience.yaml` | Example plan | 4 |
| `scripts/chaos/plans/data-layer-resilience.yaml` | Example plan | 4 |
| `scripts/chaos/plans/full-stack-resilience.yaml` | Example plan | 4 |
| `tests/unit/test_plan_schema.py` | Schema validation tests | 1 |
| `tests/unit/test_assertion_engine.py` | Assertion engine tests | 2 |
| `tests/unit/test_plan_executor.py` | Executor logic tests | 3 |

## Success Criteria Checklist

| # | Criterion | Verified | Test |
|---|-----------|----------|------|
| SC-001 | Valid YAML plan validates without errors | [ ] | test_plan_schema.py |
| SC-002 | run-plan.py executes scenarios sequentially via chaos.py API | [ ] | test_plan_executor.py |
| SC-003 | Each assertion type correctly checks CloudWatch | [ ] | test_assertion_engine.py |
| SC-004 | Mid-plan failure produces clean partial report | [ ] | test_plan_executor.py |
| SC-005 | Dry-run validates without infrastructure changes | [ ] | test_plan_executor.py |
| SC-006 | Concurrent execution guard prevents overlapping experiments | [ ] | test_plan_executor.py |
| SC-007 | All 5 scenario types work in plans | [ ] | full-stack-resilience.yaml validates |

## Pre-Implementation Checklist

- [x] Existing chaos.py API reviewed and verified
- [x] CloudWatch alarm names verified against Terraform
- [x] Custom metric namespaces verified against Terraform
- [x] Existing test patterns reviewed (moto mocks)
- [x] Safety mechanisms documented (kill switch, gate, env check)
- [x] No prod environment access possible
- [ ] Implementation started
