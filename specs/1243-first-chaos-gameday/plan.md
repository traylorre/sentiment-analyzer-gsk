# Plan: First Chaos GameDay Execution

**Feature Branch**: `1243-first-chaos-gameday`
**Created**: 2026-03-22

## Execution Plan

### Phase 1: Artifact Creation (30 min)

Create all static artifacts that do not require preprod access.

1. **Chaos plan YAML files** -- Define the two chaos plans with scenarios, assertions, and observation metrics. These are the "test scripts" for the GameDay.
   - `chaos-plans/ingestion-resilience.yaml` (P1)
   - `chaos-plans/cold-start-resilience.yaml` (P2)

2. **Operational documentation** -- Create the runbook and checklist. These are the "operator manuals."
   - `docs/chaos-testing/preflight-checklist.md`
   - `docs/chaos-testing/gameday-runbook.md`

### Phase 2: Pre-Flight Verification (10 min)

Execute the pre-flight checklist against preprod. This requires live AWS access.

- Run `scripts/chaos/status.sh preprod`
- Verify alarms, dashboard, gate state
- Confirm buddy operator
- Confirm no deploys scheduled

### Phase 3: GameDay Execution (30 min)

Execute the ingestion-resilience plan step by step.

**Scenario sequence** (sequential, not parallel):
1. `ingestion_failure` -- 2 min injection + 5 min observation = 7 min
2. 2 min cooldown between scenarios
3. `dynamodb_throttle` -- 2 min injection + 5 min observation = 7 min
4. Report generation and review -- 5 min

### Phase 4: Post-Mortem and Baseline Storage (15 min)

1. Disarm gate
2. Review reports, verify assertions
3. Store baseline reports in `reports/chaos/`
4. Write up findings
5. Notify team

## Dependencies

```
Phase 1 (artifacts) -- no dependencies, pure file creation
    |
    v
Phase 2 (pre-flight) -- requires preprod access, completed checklist
    |
    v
Phase 3 (execution) -- requires armed gate, healthy preprod
    |
    v
Phase 4 (post-mortem) -- requires completed execution, reports generated
```

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Start with ingestion-resilience, not cold-start | Ingestion failure is the most impactful scenario (data pipeline stops). Cold start is performance degradation (less severe). |
| 120s injection duration | Long enough to observe 1-2 EventBridge cycles (5 min interval) while the injection is active. Short enough to limit blast radius. |
| 100% blast radius | First GameDay should verify full failure, not partial. Partial blast radius is future work. |
| Sequential scenarios, not parallel | Easier to attribute effects to specific scenarios. Parallel injection makes root cause analysis ambiguous. |
| Store reports in repo (not S3) | Reports are small JSON files (<10KB). Storing in repo makes them diffable and version-controlled. |
| Require buddy operator | Safety requirement. Single-operator chaos is a risk if the operator loses connectivity or makes a mistake. |

## Risk Mitigations Already In Place

| Risk | Mitigation | Implemented In |
|------|-----------|---------------|
| Accidental prod chaos | `check_environment_allowed()` rejects prod | chaos.py line 113 |
| Forgotten experiment | Duration auto-stop (if wired), buddy operator, Slack notification | Runbook |
| SSM unavailable | `_check_gate()` fails closed (blocks injection) | chaos.py line 462 |
| Restore failure | Andon cord script + manual restore commands in runbook | andon-cord.sh, runbook |
| Pre-existing degradation | `_capture_baseline()` detects and flags | chaos.py line 479 |
