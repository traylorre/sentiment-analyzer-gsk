# Tasks: First Chaos Gameday Execution

**Feature**: 1243-first-gameday
**Generated**: 2026-03-27
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Enable Infrastructure (Pre-Gameday)

### [X] T-001: Set enable_chaos_testing to true in preprod.tfvars
**File**: `infrastructure/terraform/preprod.tfvars`
**Depends on**: None
**Requirements**: FR-001
**Description**: Change `enable_chaos_testing = false` to `enable_chaos_testing = true`. This is the only code change in the feature.

### T-002: Run terraform plan and review chaos resources
**File**: N/A (operational)
**Depends on**: T-001
**Requirements**: FR-001
**Description**: Run `terraform plan -var-file=preprod.tfvars`. Review output to confirm ONLY chaos-related resources are created (SSM parameter, IAM policies/roles, CloudWatch log group). Abort if non-chaos resources appear. Per constitution: no terraform apply without plan review.

### T-003: Run terraform apply
**File**: N/A (operational)
**Depends on**: T-002
**Requirements**: FR-001
**Description**: Apply the Terraform plan. Verify resources created successfully.

### T-004: Verify chaos infrastructure with status script
**File**: N/A (operational)
**Depends on**: T-003
**Requirements**: FR-001
**Description**: Run `scripts/chaos/status.sh preprod`. Verify all dependencies healthy, kill switch shows "disarmed", no active experiments. Verify dashboard API `/chaos/experiments` returns empty list.

## Phase 2: Pre-Flight (Gameday Day)

### T-005: Complete pre-flight checklist
**File**: N/A (operational, reference `docs/chaos-testing/preflight-checklist.md`)
**Depends on**: T-004
**Requirements**: FR-002, SC-001
**Description**: Execute all 8 checklist sections:
1. Environment health (run status.sh)
2. Alarm states (no ALARM state alarms)
3. Dashboard accessibility (HTTP 200 on function URL)
4. Chaos gate state (kill switch exists, "disarmed")
5. Recent ingestion baseline (ArticlesFetched > 0 in last 30 min)
6. Team notification (Slack)
7. CI/CD pause (no pending deploys)
8. Rollback readiness (scripts executable)

Document results with timestamps.

### T-006: Buddy operator sign-off
**File**: N/A (operational)
**Depends on**: T-005
**Requirements**: FR-008, SC-009
**Description**: Buddy operator confirms availability for full gameday duration. Both operator and buddy sign the pre-flight checklist.

### T-007: Arm chaos gate
**File**: N/A (operational)
**Depends on**: T-006
**Requirements**: FR-002
**Description**: `aws ssm put-parameter --name /chaos/preprod/kill-switch --value armed --overwrite --type String`. Verify with status.sh.

## Phase 3: Execute Ingestion Resilience Plan

### T-008: Scenario 1 — Inject ingestion failure
**File**: N/A (operational, reference `chaos-plans/ingestion-resilience.yaml`)
**Depends on**: T-007
**Requirements**: FR-003, FR-004
**Description**: Create experiment via dashboard API or `scripts/chaos/inject.sh preprod ingestion-failure --duration 120`. Observe for 2 minutes: CloudWatch Throttles, Errors, ArticlesFetched. Record actual behavior vs expected.

### T-009: Scenario 1 — Stop and record results
**File**: N/A (operational)
**Depends on**: T-008
**Requirements**: FR-003, FR-004
**Description**: Stop experiment via dashboard API or `scripts/chaos/restore.sh preprod`. Wait for recovery observation (up to 10 min). Record: recovery time, alarm transitions, verdict. Export report JSON.

### T-010: Wait 2+ minutes between scenarios
**File**: N/A (operational)
**Depends on**: T-009
**Requirements**: FR-003
**Description**: Wait minimum 2 minutes. Verify system is healthy (status.sh). Confirm no residual alarms before proceeding.

### T-011: Scenario 2 — Inject DynamoDB throttle
**File**: N/A (operational, reference `chaos-plans/ingestion-resilience.yaml`)
**Depends on**: T-010
**Requirements**: FR-003, FR-004
**Description**: Create experiment via dashboard API or `scripts/chaos/inject.sh preprod dynamodb-throttle --duration 120`. Observe for 2 minutes: Lambda Errors (ingestion + analysis), DynamoDB SystemErrors. Record actual behavior vs expected.

### T-012: Scenario 2 — Stop and record results
**File**: N/A (operational)
**Depends on**: T-011
**Requirements**: FR-003, FR-004
**Description**: Stop experiment. Wait for recovery observation (up to 5 min). Record: recovery time, write success resumption, verdict. Export report JSON.

## Phase 4: Safety Mechanism Validation

### T-013: Test kill switch blocking
**File**: N/A (operational)
**Depends on**: T-012
**Requirements**: FR-005, SC-004
**Description**: Set kill switch to "triggered". Attempt injection via API. Verify it's blocked. Set back to "disarmed". Document PASS/FAIL.

### T-014: Test andon cord (optional, if time permits)
**File**: N/A (operational)
**Depends on**: T-013
**Requirements**: FR-005
**Description**: If time permits: start a dry-run experiment, then run `scripts/chaos/andon-cord.sh preprod`. Verify full restore. Document PASS/FAIL.

## Phase 5: Baseline Reports

### T-015: Verify or export experiment reports
**File**: N/A (operational)
**Depends on**: T-012
**Requirements**: FR-006, SC-005
**Description**: If Feature 1240 deployed: verify reports auto-persisted via `GET /chaos/reports`. If not: export manually via `curl GET /chaos/experiments/{id}/report` for each experiment.

### [X] T-016: Create baseline reports directory and commit
**File**: `reports/chaos/gameday-001/`
**Depends on**: T-015
**Requirements**: FR-006
**Description**: Create directory. Save report JSON files (ingestion-failure.json, dynamodb-throttle.json). Commit to repo with descriptive message.

## Phase 6: Post-Mortem

### T-017: Conduct post-mortem meeting
**File**: N/A (operational)
**Depends on**: T-012
**Requirements**: FR-007, SC-006
**Description**: Review with buddy operator. Address all 6 assertions from ingestion-resilience.yaml. Answer post_mortem questions from the plan. Document actual vs expected for each scenario.

### [X] T-018: Write post-mortem document
**File**: `reports/chaos/gameday-001/post-mortem.md`
**Depends on**: T-017
**Requirements**: FR-007
**Description**: Create structured post-mortem with: date, participants, scenarios executed, per-assertion results table, unexpected findings, action items with owners/dates.

### T-019: Disarm chaos gate and notify
**File**: N/A (operational)
**Depends on**: T-017
**Requirements**: FR-009
**Description**: `aws ssm put-parameter --name /chaos/preprod/kill-switch --value disarmed --overwrite`. Verify with status.sh. Notify team in Slack that gameday is complete.

### T-020: Commit post-mortem and update gameday assessment
**File**: `reports/chaos/gameday-001/post-mortem.md`
**Depends on**: T-018
**Requirements**: FR-007
**Description**: Commit post-mortem document. Update the gameday readiness assessment with results.

## Task Summary

| Phase | Tasks | Duration | Nature |
|-------|-------|----------|--------|
| 1. Enable Infrastructure | T-001 to T-004 | ~20 min | Code + Terraform (pre-gameday) |
| 2. Pre-Flight | T-005 to T-007 | ~10 min | Operational |
| 3. Execute Plan | T-008 to T-012 | ~30 min | Operational (real-time) |
| 4. Safety Validation | T-013 to T-014 | ~10 min | Operational |
| 5. Baseline Reports | T-015 to T-016 | ~10 min | Operational + git |
| 6. Post-Mortem | T-017 to T-020 | ~15 min | Documentation |

**Total**: 20 tasks
**Code changes**: 1 (preprod.tfvars)
**Critical path**: T-001 → T-004 → T-005 → T-007 → T-008 → T-012 → T-015 → T-017
**Estimated wall-clock time**: ~90 minutes (Phases 2-6 are real-time sequential)
