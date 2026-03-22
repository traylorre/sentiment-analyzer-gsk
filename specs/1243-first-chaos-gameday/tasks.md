# Tasks: First Chaos GameDay Execution

**Feature Branch**: `1243-first-chaos-gameday`
**Created**: 2026-03-22

## Phase 1: Create Chaos Plan Artifacts

### T-001: Create ingestion-resilience chaos plan
- [ ] Create `chaos-plans/ingestion-resilience.yaml` with full plan schema
- [ ] Define `ingestion_failure` scenario: duration 120s, blast_radius 100, concurrency_zero injection
- [ ] Define `dynamodb_throttle` scenario: duration 120s, blast_radius 100, deny-write injection
- [ ] Define assertions: invocation count drops, alarm fires, recovery within 5 min, no data loss
- [ ] Validate YAML: `python -c "import yaml; yaml.safe_load(open('chaos-plans/ingestion-resilience.yaml'))"`
- File: `chaos-plans/ingestion-resilience.yaml` (new)
- Acceptance: FR-001, FR-002, FR-003, SC-001

### T-002: Create cold-start-resilience chaos plan
- [ ] Create `chaos-plans/cold-start-resilience.yaml` with full plan schema
- [ ] Define `lambda_cold_start` scenario: duration 180s, target analysis, memory reduction to 128MB
- [ ] Define `api_timeout` scenario: duration 60s, target ingestion, timeout set to 1s
- [ ] Define assertions: latency spike, timeout errors, recovery after restore
- [ ] Validate YAML: `python -c "import yaml; yaml.safe_load(open('chaos-plans/cold-start-resilience.yaml'))"`
- File: `chaos-plans/cold-start-resilience.yaml` (new)
- Acceptance: FR-008, SC-004

## Phase 2: Create Operational Documentation

### T-003: Create pre-flight checklist
- [ ] Create `docs/chaos-testing/preflight-checklist.md`
- [ ] Section: Environment Health (DynamoDB, SSM, CloudWatch, Lambda -- verified via `scripts/chaos/status.sh`)
- [ ] Section: Alarm States (all critical alarms in OK state)
- [ ] Section: Dashboard Accessibility (Function URL reachable, `/chaos` endpoint responds)
- [ ] Section: Gate State (SSM kill switch verified, command to arm)
- [ ] Section: Team Notification (Slack channel notification, buddy operator confirmed)
- [ ] Section: CI/CD Pause (no pending deploys, merge queue paused)
- [ ] Section: No-Go Criteria (abort conditions)
- File: `docs/chaos-testing/preflight-checklist.md` (new)
- Acceptance: FR-005, FR-009, SC-003

### T-004: Create GameDay runbook
- [ ] Create `docs/chaos-testing/gameday-runbook.md`
- [ ] Section: Overview (purpose, estimated duration 60 min, roles: operator + buddy)
- [ ] Section: Pre-Flight (link to checklist, environment verification commands, arm gate command)
- [ ] Section: Execution -- Scenario 1: ingestion_failure (create experiment, start, observe 2 min, stop, verify recovery)
- [ ] Section: Execution -- Scenario 2: dynamodb_throttle (same flow, different observation metrics)
- [ ] Section: Observation Guide (CloudWatch metrics to watch per scenario, what to look for, screenshot reminders)
- [ ] Section: Post-Mortem (generate report, review verdict, annotate findings)
- [ ] Section: Baseline Storage (save report to `reports/chaos/`, commit to repo)
- [ ] Section: Emergency Procedures (andon cord, manual restore, escalation path)
- [ ] Section: Fallback (direct `inject.sh` usage when dashboard unreachable)
- File: `docs/chaos-testing/gameday-runbook.md` (new)
- Acceptance: FR-004, FR-010, SC-002

## Phase 3: Execute GameDay (Manual Operational Steps)

### T-005: Pre-flight verification
- [ ] Run `scripts/chaos/status.sh preprod` -- all dependencies healthy
- [ ] Verify all CloudWatch alarms in OK state
- [ ] Verify dashboard Function URL reachable: `curl -s https://<function-url>/chaos | head -1`
- [ ] Confirm buddy operator available
- [ ] Confirm no pending deploys or merge queue activity
- [ ] Notify team in Slack channel
- [ ] Complete pre-flight checklist (all items checked)
- Acceptance: Pre-flight checklist fully completed with no No-Go items triggered

### T-006: Arm the chaos gate
- [ ] Set SSM kill switch: `aws ssm put-parameter --name /chaos/preprod/kill-switch --value armed --type String --overwrite`
- [ ] Verify gate state: `aws ssm get-parameter --name /chaos/preprod/kill-switch --query "Parameter.Value" --output text` returns "armed"
- Acceptance: Gate confirmed armed

### T-007: Execute ingestion_failure scenario
- [ ] Create experiment via dashboard API or `inject.sh ingestion-failure preprod --duration 120`
- [ ] Start timer (120 seconds)
- [ ] Observe CloudWatch: ingestion Lambda error count increases, invocation success drops to 0
- [ ] Verify EventBridge shows throttled invocations
- [ ] Stop experiment after 120s (or when observations complete)
- [ ] Wait 5 minutes for recovery observation period
- [ ] Verify ingestion Lambda resumes normal operation
- [ ] Generate experiment report: `GET /api/chaos/experiments/{id}/report`
- Acceptance: FR-006, report generated with non-INCONCLUSIVE verdict

### T-008: Execute dynamodb_throttle scenario
- [ ] Create experiment via dashboard API or `inject.sh dynamodb-throttle preprod --duration 120`
- [ ] Start timer (120 seconds)
- [ ] Observe CloudWatch: DynamoDB write errors increase, Lambda errors increase
- [ ] Verify DLQ depth increases (if applicable)
- [ ] Stop experiment after 120s
- [ ] Wait 5 minutes for recovery observation period
- [ ] Verify writes resume successfully
- [ ] Generate experiment report
- Acceptance: Report generated with non-INCONCLUSIVE verdict

### T-009: Disarm gate and store baseline
- [ ] Disarm gate: `aws ssm put-parameter --name /chaos/preprod/kill-switch --value disarmed --type String --overwrite`
- [ ] Create `reports/chaos/` directory if it does not exist
- [ ] Store baseline report: `reports/chaos/baseline-ingestion-resilience-YYYY-MM-DD.json`
- [ ] Verify report contains all required fields per FR-007
- [ ] Commit reports and plan files to the feature branch
- Acceptance: SC-005, SC-006, FR-006, FR-007

## Phase 4: Post-Mortem and Documentation

### T-010: Write GameDay summary
- [ ] Document actual vs. expected behavior for each scenario
- [ ] Note any surprises, timing issues, or unexpected metric behavior
- [ ] Record recovery times for each scenario
- [ ] If verdict is not CLEAN, document specific gaps and create follow-up issues
- [ ] Update runbook with any process improvements discovered during execution
- File: Annotations in the baseline report + runbook updates
- Acceptance: SC-007

## Dependency Graph

```
T-001 (plan) ──┐
T-002 (plan) ──┼── T-003 (checklist) ── T-004 (runbook) ── T-005 (preflight)
               │                                              │
               │                                              ▼
               │                                      T-006 (arm gate)
               │                                              │
               │                                              ▼
               │                                      T-007 (ingestion_failure)
               │                                              │
               │                                              ▼
               │                                      T-008 (dynamodb_throttle)
               │                                              │
               │                                              ▼
               │                                      T-009 (disarm + store)
               │                                              │
               │                                              ▼
               └──────────────────────────────────── T-010 (post-mortem)
```

## Estimated Effort Per Phase

| Phase | Tasks | Artifacts | Time |
|-------|-------|-----------|------|
| Phase 1: Plans | T-001, T-002 | 2 YAML files | 30 min |
| Phase 2: Docs | T-003, T-004 | 2 Markdown files | 45 min |
| Phase 3: Execute | T-005 -- T-009 | 1 baseline report | 60 min (real-time) |
| Phase 4: Post-Mortem | T-010 | Report annotations | 15 min |
| **Total** | **10 tasks** | **5 artifacts** | **~2.5 hours** |
