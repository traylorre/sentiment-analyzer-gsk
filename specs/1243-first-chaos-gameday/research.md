# Research: First Chaos GameDay Execution

**Feature Branch**: `1243-first-chaos-gameday`
**Created**: 2026-03-22

## Infrastructure Audit

### Existing Chaos Components

| Component | Location | Status |
|-----------|----------|--------|
| External actor scripts | `scripts/chaos/{inject,restore,status,andon-cord}.sh` | Complete (Feature 1237) |
| Common library | `scripts/chaos/lib/common.sh` | Complete |
| Dashboard chaos API | `src/lambdas/dashboard/chaos.py` (1063 lines) | Complete (Feature 1237/1238) |
| Dashboard chaos UI | `src/dashboard/chaos.html` | Complete |
| Gate/dry-run system | SSM `/chaos/{env}/kill-switch` | Complete (Feature 1238) |
| Baseline capture | `_capture_baseline()` in chaos.py | Complete (Feature 1238) |
| Post-chaos health | `_capture_post_chaos_health()` in chaos.py | Complete (Feature 1238) |
| Report generation | `get_experiment_report()` in chaos.py | Complete (Feature 1240) |
| SSM snapshots | `_snapshot_to_ssm()` / `_restore_from_ssm()` | Complete (Feature 1237) |
| Unit tests | `tests/unit/test_chaos_{fis,injection,gate,restore}.py` | Complete |
| Playwright e2e tests | `frontend/tests/e2e/chaos.spec.ts` | Complete (Feature 1238) |

### Supported Scenarios

| Scenario | inject.sh name | API name | Injection Method |
|----------|---------------|----------|-----------------|
| Ingestion failure | `ingestion-failure` | `ingestion_failure` | `lambda:PutFunctionConcurrency(0)` |
| DynamoDB throttle | `dynamodb-throttle` | `dynamodb_throttle` | `iam:AttachRolePolicy(deny-write)` |
| Cold start | `cold-start` | `lambda_cold_start` | `lambda:UpdateFunctionConfiguration(Memory=128)` |
| Trigger failure | `trigger-failure` | `trigger_failure` | `events:DisableRule` |
| API timeout | `api-timeout` | `api_timeout` | `lambda:UpdateFunctionConfiguration(Timeout=1)` |

### Missing Components (Gaps)

| Gap | Description | This Feature Creates |
|-----|-------------|---------------------|
| Chaos plan files | No YAML plan files exist in `chaos-plans/` | `ingestion-resilience.yaml`, `cold-start-resilience.yaml` |
| GameDay runbook | No operator guide for executing plans | `docs/chaos-testing/gameday-runbook.md` |
| Pre-flight checklist | No formal pre-flight verification | `docs/chaos-testing/preflight-checklist.md` |
| Baseline report | No report has ever been generated | `reports/chaos/baseline-*.json` (after execution) |

## Chaos Engineering Best Practices (Applied)

### Netflix Principles of Chaos

1. **Build a hypothesis around steady-state behavior** -- Our hypothesis: when ingestion is throttled, alarms fire within 2 minutes and the system recovers within 5 minutes after restore.
2. **Vary real-world events** -- We inject two different types: Lambda throttling (infrastructure-level) and IAM deny (permission-level).
3. **Run experiments in production** -- We run in preprod first to establish baseline. Prod chaos is future work.
4. **Automate experiments to run continuously** -- Future work. This feature establishes the first manual baseline.
5. **Minimize blast radius** -- Gate system prevents accidental injection. Duration limits prevent extended degradation. Andon cord provides emergency recovery.

### GameDay Structure (AWS Well-Architected)

Following AWS's recommended GameDay structure:
- **Pre-flight**: Verify environment health, arm safety mechanisms, notify team
- **Execution**: Sequential scenario injection with observation windows
- **Post-mortem**: Generate report, verify assertions, document findings
- **Baseline**: Store results for future comparison

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Preprod not healthy at GameDay time | Medium | High (abort) | Pre-flight checklist, `status.sh` |
| Experiment causes cascading failure | Low | High | Andon cord, duration limits, buddy operator |
| SSM unavailable (can't snapshot/restore) | Very Low | Critical | `_check_gate()` is fail-closed; inject.sh refuses |
| Concurrent deploy during GameDay | Low | Medium | Pre-flight CI/CD pause check |
| Operator unavailable mid-experiment | Low | Medium | Buddy operator requirement, duration auto-stop |
| Report verdict is COMPROMISED | Medium | Low | Document findings, re-run after fixing pre-existing issues |
