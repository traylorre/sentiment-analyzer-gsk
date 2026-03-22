# Implementation Checklist: First Chaos GameDay

## Artifact Checklist

### Chaos Plans
- [ ] `chaos-plans/ingestion-resilience.yaml` -- valid YAML, all required fields
- [ ] `chaos-plans/cold-start-resilience.yaml` -- valid YAML, all required fields
- [ ] Both plans have `name`, `version`, `scenarios`, `assertions`, `observation_period_seconds`
- [ ] Each scenario has `id`, `type`, `duration_seconds`, `blast_radius`, `expected_behavior`, `observation_metrics`
- [ ] Each assertion has `id`, `description`, `metric`, `condition`, `threshold` (where applicable)
- [ ] Scenario `type` values match valid set: `ingestion_failure`, `dynamodb_throttle`, `lambda_cold_start`, `trigger_failure`, `api_timeout`

### Operational Documentation
- [ ] `docs/chaos-testing/preflight-checklist.md` -- all 8 sections present
- [ ] `docs/chaos-testing/gameday-runbook.md` -- all 8 sections present
- [ ] Runbook references pre-flight checklist
- [ ] Runbook includes emergency procedures with copy-paste commands
- [ ] Runbook includes fallback path (direct script execution)
- [ ] Pre-flight checklist includes No-Go criteria table

### YAML Validation
- [ ] `python -c "import yaml; yaml.safe_load(open('chaos-plans/ingestion-resilience.yaml'))"` succeeds
- [ ] `python -c "import yaml; yaml.safe_load(open('chaos-plans/cold-start-resilience.yaml'))"` succeeds

## Execution Checklist

### Pre-GameDay
- [ ] All artifacts committed to feature branch
- [ ] Pre-flight checklist reviewed by buddy operator
- [ ] GameDay window scheduled (60 min block)
- [ ] Slack channel notified

### During GameDay
- [ ] Pre-flight checklist completed (all items, no No-Go conditions)
- [ ] Gate armed
- [ ] Scenario 1 (ingestion_failure) executed and report generated
- [ ] Scenario 2 (dynamodb_throttle) executed and report generated
- [ ] Gate disarmed

### Post-GameDay
- [ ] Baseline reports stored in `reports/chaos/`
- [ ] All assertions verified and annotated
- [ ] Post-mortem summary written
- [ ] Team notified of results
- [ ] Reports committed to repo

## Success Criteria Verification

| Criteria | Status |
|----------|--------|
| SC-001: ingestion-resilience.yaml valid | [ ] |
| SC-002: runbook complete with all sections | [ ] |
| SC-003: checklist complete with no-go criteria | [ ] |
| SC-004: cold-start-resilience.yaml valid | [ ] |
| SC-005: baseline report exists with non-INCONCLUSIVE verdict | [ ] |
| SC-006: verdict is CLEAN | [ ] |
| SC-007: all assertions verified | [ ] |
