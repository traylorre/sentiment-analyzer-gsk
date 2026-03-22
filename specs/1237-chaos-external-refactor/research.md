# Research: Refactor Chaos Injection to External Actor Architecture

**Feature Branch**: `1237-chaos-external-refactor`
**Created**: 2026-03-22

## Codebase Analysis

### Embedded Chaos Code Surface Area

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Detection helper | `src/lambdas/shared/chaos_injection.py` | 318 | `is_chaos_active()`, `get_chaos_delay_ms()`, `auto_stop_expired()` |
| Ingestion handler | `src/lambdas/ingestion/handler.py` | ~40 (of 500+) | Import + chaos gate + auto-stop + throttle |
| Analysis handler | `src/lambdas/analysis/handler.py` | ~35 (of 537) | Import + cold start delay + throttle + auto-stop |
| Dashboard module | `src/lambdas/dashboard/chaos.py` | 690 | Full experiment lifecycle, FIS integration |
| Dashboard UI | `src/dashboard/chaos.html` | ~200 | Experiment management UI |
| Tests | 4 files | ~1400+ | Detection, wiring, auto-stop, FIS tests |
| Terraform chaos | `modules/chaos/main.tf` | 247 | FIS role + templates (disabled) |
| Terraform IAM | `modules/iam/main.tf` | ~40 | Dashboard chaos policy |
| DynamoDB | `modules/dynamodb/` | ~30 | chaos-experiments table + GSI |

**Total embedded chaos code**: ~2,980 lines across 10+ files.

### Per-Invocation Overhead

Current architecture adds overhead to EVERY Lambda invocation:
1. `is_chaos_active()` -- DynamoDB Query on `by_status` GSI (5-15ms per call)
2. `get_chaos_delay_ms()` -- Same DynamoDB Query pattern (5-15ms per call)
3. `auto_stop_expired()` -- DynamoDB Query + conditional Update (10-25ms per call)

The ingestion handler makes 5 chaos-related DynamoDB calls per invocation:
- `is_chaos_active("ingestion_failure")` (line 194)
- `auto_stop_expired("ingestion_failure")` (line 221)
- `auto_stop_expired("dynamodb_throttle")` (line 222)
- `is_chaos_active("dynamodb_throttle")` (line 225)
- `get_chaos_delay_ms("dynamodb_throttle")` (line 226)

The analysis handler makes 6 chaos-related DynamoDB calls:
- `get_chaos_delay_ms("lambda_cold_start")` (line 121)
- `is_chaos_active("dynamodb_throttle")` (line 138)
- `get_chaos_delay_ms("dynamodb_throttle")` (line 139)
- `auto_stop_expired("lambda_cold_start")` (line 149)
- `auto_stop_expired("dynamodb_throttle")` (line 150)
- (Total: 6 calls)

**Estimated overhead per invocation**: 30-90ms of DynamoDB latency added to every single invocation, even when no chaos experiment is active.

### Existing Infrastructure Patterns

**SSM Parameter Store**:
- Already used by canary Lambda for state persistence
- IAM pattern established: `ssm:GetParameter` + `ssm:PutParameter` scoped to `${var.environment}/canary/*`
- Cost: $0.05/parameter/month (negligible)

**CloudWatch Alarms**:
- Critical composite alarm exists: `{env}-critical-composite`
- Fires when any lambda error alarm OR throttle alarm triggers
- Connected to SNS topic: `monitoring/outputs.tf:alarm_topic_arn`
- This alarm is the natural trigger for auto-restore

**EventBridge Rules**:
- Ingestion schedule: `{env}-sentiment-ingestion-schedule` (rate: 5 minutes)
- Pattern: `aws_cloudwatch_event_rule.ingestion_schedule`

**Lambda Function Names**:
- Pattern: `local.ingestion_lambda_name` / `local.analysis_lambda_name` (resolved in main.tf)
- Standard: `{env}-sentiment-{service}`

### Consistency Check: spec vs plan vs tasks

| Spec FR | Plan Section | Tasks | Status |
|---------|-------------|-------|--------|
| FR-001: Remove chaos from ingestion | Phase 1, 1a | T-001 | Covered |
| FR-002: Remove chaos from analysis | Phase 1, 1b | T-002 | Covered |
| FR-003: Delete chaos_injection.py | Phase 1, 1c | T-003 | Covered |
| FR-004: inject.sh for 5 scenarios | Phase 2, 2b | T-008 | Covered |
| FR-005: restore.sh | Phase 2, 2c | T-009 | Covered |
| FR-006: status.sh | Phase 2, 2d | T-010 | Covered |
| FR-007: Snapshot to SSM before inject | Phase 2 (in inject.sh) | T-008 | Covered |
| FR-008: Validate kill switch | Phase 2 (in inject.sh) | T-008 | Covered |
| FR-009: Audit log to DynamoDB | Phase 2 (in inject.sh) | T-008 | Covered |
| FR-010: SSM kill-switch parameter in Terraform | Phase 3, 3a | T-013 | Covered |
| FR-011: chaos-engineer IAM role | Phase 3, 3b | T-014 | Covered |
| FR-012: andon-cord.sh | Phase 2, 2e | T-011 | Covered |
| FR-013: Auto-restore Lambda | Phase 4 | T-017, T-018 | Covered |
| FR-014: Remove CHAOS_EXPERIMENTS_TABLE from handlers | Phase 1, 1d | T-004 | Covered |
| FR-015: Update dashboard IAM | Phase 5, 5b | T-022 | Covered |

**All 15 FRs are covered by plan and tasks.** No orphaned requirements.

### Consistency Check: user stories vs success criteria

| User Story | Acceptance Scenarios | Success Criteria |
|-----------|---------------------|------------------|
| US1 (remove embedded code) | 6 scenarios | SC-001, SC-002, SC-008, SC-010 |
| US2 (external scripts) | 6 scenarios | SC-003, SC-004, SC-005, SC-006 |
| US3 (andon cord) | 5 scenarios | SC-009 |
| US4 (IAM role) | 4 scenarios | SC-007 |
| US5 (dashboard rewire) | 4 scenarios | (covered by functional tests) |

All user stories have corresponding success criteria.

### Risk Analysis: What Could Go Wrong

1. **Handler tests that mock chaos functions will break**: Tests in `test_chaos_ingestion_wiring.py` and related files mock `is_chaos_active`. These tests are deleted in T-005, but any OTHER test files that mock chaos imports will also fail. Mitigation: `grep -r "chaos" tests/` before committing Phase 1.

2. **Dashboard chaos API breaks**: The `/chaos/experiments/{id}/start` endpoint calls `start_experiment()`. If the rewrite in Phase 5 changes the function signature or error behavior, the dashboard UI may break. Mitigation: Keep the same function signature and return type; test with the existing chaos.html UI.

3. **Terraform state drift**: Removing `CHAOS_EXPERIMENTS_TABLE` from Lambda env vars will trigger a Lambda update during next apply. This is expected but must be coordinated with any running chaos experiments.

4. **SSM parameter naming collision**: The pattern `/chaos/{env}/snapshot/{scenario}` could collide with future features using `/chaos/` prefix. Mitigation: Document the namespace in the chaos module README.

5. **Auto-restore Lambda permissions are broad**: The restore Lambda needs `lambda:UpdateFunctionConfiguration` and `iam:DetachRolePolicy` -- powerful permissions. Mitigation: Scope to environment-specific resources; only create in non-prod.

### Questions for User

1. **Phase 4 auto-restore Lambda**: Should this be a separate Lambda function or could it reuse the dashboard Lambda with a special event path? A separate function is cleaner but adds infrastructure.

2. **Dashboard rewire (Phase 5)**: Should we go with Option A (full rewire, dashboard can inject/restore chaos) or Option B (deprecate to read-only, scripts-only interface)? Option A preserves the current UX but requires broader IAM permissions on the dashboard Lambda.

3. **Deny policy for DynamoDB throttle**: The inject script needs to create and attach an inline IAM policy to the Lambda execution role. Should this be a managed policy pre-created in Terraform (safer, no dynamic policy creation) or an inline policy created by the script (more flexible)?

4. **Duration auto-restore**: Should `inject.sh --duration 300` actually schedule a background restore, or should it just record the intended duration in the audit log for the operator to manually restore?
