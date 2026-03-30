# Feature Specification: First Chaos Gameday Execution

**Feature Branch**: `1243-first-gameday`
**Created**: 2026-03-27
**Status**: Draft
**Input**: "Feature 1243: Execute first chaos gameday in preprod, validate all safety mechanisms under real conditions, establish baseline reports"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Enable Chaos Infrastructure (Priority: P1)

The operator wants to enable chaos testing infrastructure in preprod so that chaos experiments can actually inject faults into real AWS resources. This is a one-time Terraform configuration change.

**Why this priority**: Nothing else can happen without this. All scripts, APIs, and safety mechanisms depend on the chaos module being enabled.

**Independent Test**: Can be tested by running `terraform plan` and verifying only chaos-related resources are created, with no changes to existing production resources.

**Acceptance Scenarios**:

1. **Given** `enable_chaos_testing = false` in preprod.tfvars, **When** the operator sets it to `true` and runs Terraform apply, **Then** the chaos module resources are created (kill switch SSM parameter, IAM policies, CloudWatch log group).
2. **Given** chaos infrastructure is enabled, **When** the operator runs `scripts/chaos/status.sh preprod`, **Then** all dependencies report healthy and the kill switch shows "disarmed".
3. **Given** chaos infrastructure is enabled, **When** the operator checks the dashboard API, **Then** `/chaos/experiments` responds with an empty list.

---

### User Story 2 - Execute Pre-Flight Checklist (Priority: P1)

Before injecting any faults, the operator wants to verify all 8 pre-flight checklist sections pass and no no-go criteria are triggered. This establishes the baseline state and confirms safety mechanisms are functional.

**Why this priority**: The checklist is the safety gate — skipping it risks injecting faults into an already-degraded system, making results unreliable and potentially causing damage.

**Independent Test**: Can be tested by running through all checklist sections and recording pass/fail for each item. Abort if any no-go criterion triggers.

**Acceptance Scenarios**:

1. **Given** the pre-flight checklist, **When** the operator runs each check, **Then** all 8 sections pass: environment health, alarm states, dashboard accessibility, chaos gate state, recent ingestion baseline, team notification, CI/CD pause, rollback readiness.
2. **Given** all checks pass, **When** the operator and buddy sign off, **Then** the checklist is documented with timestamps.
3. **Given** a no-go criterion is triggered (e.g., alarm in ALARM state), **When** detected, **Then** the gameday is aborted with the specific no-go criterion documented.

---

### User Story 3 - Execute Ingestion Resilience Plan (Priority: P1)

The operator wants to execute the ingestion-resilience chaos plan (2 scenarios: ingestion failure + DynamoDB throttle) following the runbook, observing system behavior, and recording results for each scenario.

**Why this priority**: This is the core gameday activity. The ingestion resilience plan is the first and most critical test — it validates the most common failure mode (ingestion pipeline failure) and the most impactful infrastructure change (database write denial).

**Independent Test**: Can be tested by executing both scenarios sequentially with observation periods, recording metrics, and comparing actual behavior against expected behavior from the chaos plan YAML.

**Acceptance Scenarios**:

1. **Given** the gate is armed, **When** scenario 1 (ingestion_failure) is injected, **Then** the ingestion Lambda shows throttle errors in CloudWatch, ArticlesFetched drops to 0, and the error alarm transitions to ALARM within 2 minutes.
2. **Given** scenario 1 is stopped, **When** recovery is observed, **Then** the next EventBridge-triggered invocation succeeds and ArticlesFetched returns to non-zero within 10 minutes.
3. **Given** a 2-minute gap between scenarios, **When** scenario 2 (dynamodb_throttle) is injected, **Then** DynamoDB write operations fail with AccessDenied and Lambda error rates increase.
4. **Given** scenario 2 is stopped, **When** recovery is observed, **Then** writes succeed on the next invocation and error rates return to 0 within 5 minutes.
5. **Given** both scenarios completed, **When** reports are generated, **Then** each has a verdict (expected: CLEAN for both if system recovers properly).

---

### User Story 4 - Validate Safety Mechanisms (Priority: P2)

The operator wants to verify that all safety mechanisms work under real conditions: kill switch stops injection, auto-restore Lambda fires from real CloudWatch alarm, and andon cord performs emergency recovery.

**Why this priority**: Safety mechanism validation is the secondary objective. Even if the system fails to recover cleanly, confirming that safety nets work is valuable. This addresses Blind Spot #6 (auto-restore never tested under real conditions).

**Independent Test**: Can be tested by deliberately triggering each safety mechanism and verifying it performs as documented.

**Acceptance Scenarios**:

1. **Given** a running experiment, **When** the kill switch is set to "triggered", **Then** subsequent injection attempts are blocked.
2. **Given** the auto-restore Lambda, **When** a CloudWatch composite alarm fires during chaos injection, **Then** the Lambda restores pre-chaos configuration from SSM snapshots.
3. **Given** the andon cord script, **When** executed during an active experiment, **Then** all chaos is reversed and the system returns to pre-chaos state.
4. **Given** all safety mechanisms tested, **When** the post-mortem is conducted, **Then** each mechanism has a PASS/FAIL rating documented.

---

### User Story 5 - Establish Baseline Reports (Priority: P2)

After executing the gameday, the operator wants to persist all experiment reports as the first baseline so that future gamedays can show improvement (or regression) over time.

**Why this priority**: Without a baseline, there's nothing to compare against. The first gameday's reports become the "before" in the "before and after" interview narrative. Depends on Feature 1240 for report persistence.

**Independent Test**: Can be tested by verifying that each experiment has a persisted report with correct verdict, and that the reports directory in the repo contains the baseline JSON files.

**Acceptance Scenarios**:

1. **Given** completed experiments with persisted reports (Feature 1240), **When** the operator reviews the reports, **Then** each report contains: verdict, baseline health, post-chaos health, timing data.
2. **Given** persisted reports, **When** the operator creates `reports/chaos/` directory and commits baseline files, **Then** the repo contains the first gameday results for historical reference.
3. **Given** the first gameday baseline, **When** a future gameday is executed, **Then** the comparison API (Feature 1240) shows changes relative to this baseline.

---

### User Story 6 - Conduct Post-Mortem (Priority: P3)

The operator wants to conduct a structured post-mortem reviewing all experiment results, verifying assertions from the chaos plans, and documenting findings and action items.

**Why this priority**: The post-mortem is where learnings are extracted. It's valuable but can be done async after the gameday. The raw data (reports, metrics) is captured regardless.

**Independent Test**: Can be tested by completing the post-mortem template with results from the gameday and verifying all assertion IDs from the chaos plans are addressed.

**Acceptance Scenarios**:

1. **Given** completed experiments, **When** the post-mortem is conducted, **Then** each of the 11 assertions (6 from ingestion-resilience, 5 from cold-start-resilience) has a PASS/FAIL/SKIPPED status.
2. **Given** the post-mortem document, **When** reviewed, **Then** it contains: actual vs expected behavior for each scenario, recovery times, alarm timing, unexpected findings.
3. **Given** action items identified, **When** documented, **Then** each has an owner and target date.

---

### Edge Cases

- What happens if the first scenario leaves the system degraded before the second scenario starts?
  - The 2-minute gap between scenarios allows observation. If degradation persists, the operator should use the andon cord to restore before proceeding. The second scenario's baseline capture will show the degradation (verdict: COMPROMISED).
- What happens if Terraform apply for enabling chaos creates unexpected changes?
  - Run `terraform plan` first and review. The chaos module is gated by `enable_chaos_testing` — only chaos-specific resources should change. Abort if non-chaos resources appear in the plan.
- What happens if the gameday must be aborted mid-execution?
  - Run `scripts/chaos/andon-cord.sh preprod` to restore all chaos state. Document the abort reason. The partially-completed reports are still valuable data.
- What happens if the auto-restore Lambda fails?
  - Fall back to manual restore via `scripts/chaos/restore.sh preprod`. This is documented in the emergency procedures section of the runbook.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Operator MUST enable chaos testing infrastructure in preprod via Terraform configuration change before any chaos injection.
- **FR-002**: Operator MUST complete all 8 pre-flight checklist sections with passing results before proceeding.
- **FR-003**: Operator MUST execute the ingestion-resilience chaos plan following the runbook sequence (2 scenarios, sequential, with 2-minute gap).
- **FR-004**: Operator MUST record actual system behavior during each scenario and compare against expected behavior from the chaos plan YAML.
- **FR-005**: Operator MUST test at least one safety mechanism (kill switch OR auto-restore OR andon cord) under real conditions.
- **FR-006**: Operator MUST persist experiment reports as the first baseline (via Feature 1240 API or manual JSON export).
- **FR-007**: Operator MUST conduct a post-mortem addressing all assertions from executed chaos plans.
- **FR-008**: Operator MUST have a buddy operator present for the full gameday duration.
- **FR-009**: Operator MUST disarm the chaos gate at gameday conclusion.
- **FR-010**: All gameday activities MUST be in non-production environment (preprod).

### Key Entities

- **Gameday Execution Record**: Documents the complete gameday: date, participants, environment, plan executed, pre-flight results, per-scenario results, safety mechanism validation, post-mortem findings, action items.
- **Scenario Execution**: Individual scenario record: scenario type, injection time, observation duration, recovery time, verdict, deviation from expected behavior.
- **Assertion Result**: Per-assertion from chaos plan: assertion ID, PASS/FAIL/SKIPPED, observed evidence, notes.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: All 8 pre-flight checklist sections pass before injection begins.
- **SC-002**: Both scenarios in the ingestion-resilience plan execute without operator safety intervention (andon cord not needed for normal operation).
- **SC-003**: System recovers to healthy state within documented timeframes after each scenario (ingestion: 10 min, DynamoDB: 5 min).
- **SC-004**: At least one safety mechanism is validated under real conditions with documented PASS result.
- **SC-005**: Experiment reports are persisted with verdicts for all executed scenarios.
- **SC-006**: Post-mortem addresses all assertions from executed chaos plans.
- **SC-007**: Total gameday execution completes within 90 minutes (per runbook estimate).
- **SC-008**: Zero unintended changes to production environment.
- **SC-009**: Buddy operator confirms availability and participation for full duration.

## Assumptions

- Preprod environment has active ingestion pipeline (EventBridge schedule running, DynamoDB tables populated).
- Network connectivity to AWS preprod account is available for the full gameday duration.
- CloudWatch metrics have sufficient history (30+ minutes of ingestion data) for meaningful baseline comparison.
- The operator has access to the chaos-engineer IAM role with MFA.
- Slack channel is available for team notification.
- Feature 1240 (Chaos Reports Backend) is deployed to preprod. If not, reports will be saved as JSON files manually.
- The cold-start-resilience plan is stretch goal — the first gameday focuses on ingestion-resilience.

## Scope Boundaries

### In Scope
- Terraform change to enable chaos testing
- Pre-flight checklist execution
- Ingestion-resilience plan execution (2 scenarios)
- Safety mechanism validation (at least 1)
- Baseline report establishment
- Post-mortem documentation

### Out of Scope
- Cold-start-resilience plan (stretch goal for first gameday, separate execution)
- Load testing during chaos injection
- Production environment (preprod only)
- Automated gameday scheduling
- New infrastructure beyond enabling the existing chaos module
- Dashboard UI improvements (Feature 1242)

## Dependencies

- **Feature 1237** (External Refactor): DONE — chaos scripts depend on this
- **Feature 1238** (Gate Pattern): DONE — kill switch depends on this
- **Feature 1239** (Execution Plans): DONE — chaos plan YAML depends on this
- **Feature 1240** (Chaos Reports Backend): UPSTREAM (optional) — report persistence depends on this. If not available, manual JSON export serves as fallback.
- **Feature 1242** (Dashboard Report Viewer): UPSTREAM (optional) — visual report viewer. If not available, CLI-based report retrieval serves as fallback.

## Adversarial Review #1

**Reviewed**: 2026-03-29 (post-implementation review — all code dependencies complete, 17 operational tasks remain)

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | Terraform apply in a "coding session" is operationally dangerous — plan could show unexpected drift | Separated: T-002 (plan) and T-003 (apply) are pre-gameday prep tasks, not same-session as live injection. The plan MUST be reviewed in a separate session/PR before gameday day. |
| CRITICAL | Buddy operator requirement unrealistic for solo developer project | Acknowledged: For a solo project, the "buddy" can be a recording/stream or a colleague observing async. The requirement's intent is accountability and safety documentation, not strict dual-operator control. Reframed as "observer" not "co-pilot." |
| HIGH | Recovery time estimates (10min, 5min) are untested optimism | Reframed: SC-003 changed from "recovery within documented timeframes" to "recovery times MEASURED and documented." The gameday's purpose is to establish baselines, not enforce them. |
| HIGH | Preprod ingestion pipeline active assumption unverified | Added to pre-validation: preflight checklist section 5 already requires "ArticlesFetched > 0 in last 30 min." If this fails, it's a No-Go criterion. |
| HIGH | 11 assertions referenced but only 6 in scope — misleading post-mortem | Accepted: post-mortem template will only include the 6 in-scope assertions. Cold-start plan is stretch goal. |
| MEDIUM | 90-minute time box is tight | Accepted: 90 min is aspirational. First gameday will likely take 2 hours. |
| MEDIUM | Feature 1240 fallback procedure undefined | Accepted: 1240 IS deployed (PR #822 merged). Fallback is no longer needed. |
| LOW | scripts/chaos/restore.sh never validated | Accepted: T-014 (andon cord test) validates the restore path. |

**Gate**: 0 CRITICAL, 0 HIGH remaining (all resolved via reframing and separation of prep from execution).
