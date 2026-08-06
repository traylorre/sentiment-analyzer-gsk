# Tasks: Signed, Aggregating Sentiment Timeseries Fanout

**Input**: Design documents from `/specs/001-signed-fanout/`
**Prerequisites**: plan.md, spec.md, research.md (D1-D9), data-model.md, contracts/, quickstart.md

**Tests**: Included. FR-007 explicitly mandates tests at the handler-to-fanout hop,
accumulation, sign mapping, backfill idempotency, and a failure path. Test tasks are
written first within each story and must fail before the implementation task lands.

**Organization**: Grouped by user story from spec.md. US1 = signed direction (P1),
US2 = accumulation (P2), US3 = backfill repair (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 for user story phases only

## Phase 1: Setup

**Purpose**: attributable baseline before any change

- [ ] T001 Confirm green baseline on branch 001-signed-fanout: `source .venv/bin/activate`, run `make validate` and `make test-local`, record pass counts so later regressions are attributable to this feature

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared signed mapping and bucket model shape that every story needs

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Write failing unit tests for `label_to_signed` in tests/unit/test_timeseries_fanout.py: positive label maps to +confidence, negative to -confidence, neutral to 0.0, unknown label to 0.0, outputs bounded to [-1, 1]
- [ ] T003 Create src/lib/timeseries/signed.py implementing `label_to_signed(label, confidence)` by moving the existing `_label_to_score` logic (research D2); imports nothing from src/lib except (if needed) metrics.py, per the SSE cold-start invariant; T002 passes
- [ ] T004 [P] Extend src/lib/timeseries/models.py per data-model.md: add `version`, `open_ts`, `close_ts` fields; correct field descriptions falsified by the change (sources becomes a bounded provider-name set; value ranges signed, `ge=-1.0, le=1.0` now exercised) (FR-006 floor, model portion)

**Checkpoint**: shared mapping exists with one source of truth; model shape ready

---

## Phase 3: User Story 1 - Sentiment direction is visible (Priority: P1) MVP

**Goal**: bucket contributions are signed; negative news plots below zero

**Independent Test**: ingest one high-confidence negative article; the bucket value
and plotted point are negative (spec US1 independent test)

### Tests for User Story 1

- [ ] T005 [US1] Write failing hop tests in tests/unit/test_analysis_handler.py: for each label, the value reaching the fanout call is signed (negative 0.9 arrives as -0.9, neutral as 0.0, positive 0.8 as +0.8); the stored per-article record's `score` field remains unsigned confidence (FR-008 assertion in the same test); freeze time so fixture timestamps stay inside the FR-010 window once T012 lands (constitution section 3 Dates)

### Implementation for User Story 1

- [ ] T006 [US1] Make src/lambdas/analysis/sentiment.py `_label_to_score` a thin delegate to `label_to_signed` (research D2; its test-only aggregation callers keep working)
- [ ] T007 [US1] Pass the signed contribution at the fanout hop in src/lambdas/analysis/handler.py via `label_to_signed`; T005 passes

**Checkpoint**: a negative article produces a negative bucket contribution end to end
through the existing writer; US1 independently testable

---

## Phase 4: User Story 2 - Days aggregate instead of forgetting (Priority: P2)

**Goal**: buckets accumulate population statistics instead of overwriting; exactly one
fanout writer exists

**Independent Test**: three articles (positive 0.8, negative 0.9, positive 0.6) into
one window end with count 3, sum 0.5, avg ~0.167, high 0.8, low -0.9, label_counts
{positive: 2, negative: 1} (spec US2 independent test)

### Tests for User Story 2

- [ ] T008 [US2] Rewrite tests/unit/test_timeseries_fanout.py against `accumulate_fanout` semantics (failing first): count/sum/avg maintenance, OHLC ordered by article timestamp using `open_ts`/`close_ts` (out-of-order arrivals), label_counts merge, `sources` as provider-name string set, `is_partial` always True on write, the two-branch D1 guard (`version = :expected` when the read returned a version, `attribute_not_exists(version)` when it did not, covering absent AND legacy-unversioned buckets), bounded retry with jitter on ConditionalCheckFailedException
- [ ] T009 [P] [US2] Write failing tests in tests/unit/test_analysis_handler.py for FR-010 bounds (timestamp beyond now+5min or older than 30d: fanout skipped, item still stored, structured warning without raw text, `TimeseriesFanoutRejectedTimestamp` incremented) and FR-009 recording (retries exhausted: one structured log record with ticker/resolution/window/error class, `TimeseriesFanoutErrors` incremented with NO added dimension per research D4); freeze time (freezegun or injected clock, constitution section 3 Dates) since the bounds compare against now

### Implementation for User Story 2

- [ ] T010 [US2] Implement `accumulate_fanout()` in src/lib/timeseries/fanout.py per research D1: read bucket, compute complete next state locally, single conditional PutItem with the two-branch guard, bounded jittered retries; D8 sources set from provider names; T008 passes
- [ ] T011 [US2] Delete `write_fanout`, `write_fanout_with_update`, and `generate_fanout_items` (zero live callers after this change and it produces the overwrite bucket shape, D7 rationale, ar3-006) from src/lib/timeseries/fanout.py AND rewrite src/lib/timeseries/__init__.py in the same change: drop the deleted exports, export `accumulate_fanout` and `label_to_signed` (ar2-003: SSE imports the package at every cold start, a stale export is an ImportError in SSE); rewrite tests/integration/timeseries/test_timeseries_pipeline.py against `accumulate_fanout` in the same change (it imports write_fanout and generate_fanout_items at :27 and calls them at :56/:82/:119/:380; left alone, `make test-local` fails at collection from here to ship, ar3-001); verify fanout.py/signed.py import no top-level src/lib module other than metrics.py (research D2 invariant)
- [ ] T012 [US2] Wire src/lambdas/analysis/handler.py to `accumulate_fanout`: replace the `write_fanout` import and call; read the SNS body `sources` field for provider names (D8, handler currently ignores it); implement FR-010 bounds and FR-009 recording at the hop; T009 passes, and T005/T013 are migrated to assert against the `accumulate_fanout` hop and pass (ar3-005)
- [ ] T013 [US2] Add idempotency regression test in tests/unit/test_analysis_handler.py: a redelivered message does not double count because the analyzed-status gate still guards fanout (FR-003, spec A2); freeze time per constitution section 3 Dates
- [ ] T014 [US2] LocalStack integration tests in tests/integration/timeseries/test_accumulation.py, run via `make test-integration`: two concurrent writers on one bucket (loser retries, final count 2, statistics consistent), crash shape leaves no partial state (every observable bucket is a complete state at a single version), live accumulation onto a legacy-unversioned bucket adopts it via `attribute_not_exists(version)`; fixed dates only, per constitution section 3

**Checkpoint**: accumulation is the only writer; US1 and US2 independently testable

---

## Phase 5: User Story 3 - Recent history is repaired (Priority: P3)

**Goal**: quiesced, re-runnable 30-day backfill under a scoped role with an auditable
manifest

**Independent Test**: run the backfill twice against an environment; trailing-30-day
buckets show signed averages with count > 1 on multi-article days, and the second run
changes zero bucket values (spec US3 independent test, SC-004)

### Implementation for User Story 3

- [ ] T015 [P] [US3] Add the `${var.environment}-backfill-timeseries-role` IAM role (env prefix per iam-module convention; both environments deploy from one account, ar3-004) per research D6, across the full file set (ar3-003): infrastructure/terraform/modules/iam/main.tf (role plus policy: Query/Scan on sentiment_items, GetItem/PutItem on sentiment_timeseries, DescribeRule/DisableRule/EnableRule on the ingestion schedule rule ARN, cloudwatch:GetMetricData necessarily on Resource '*'), modules/iam/variables.tf (new variables: ingestion schedule rule ARN, operator principal ARN for the trust policy), root main.tf iam module block wiring (rule ARN from `module.eventbridge.ingestion_schedule_arn`, root main.tf:1530), AND infrastructure/terraform/ci-user-policy.tf (extend the IAMRoles statement patterns to match the backfill role name, ar3-002; that policy change reaches the live CI user only via the operator-run admin bootstrap apply documented at ci-user-policy.tf:20-35, an explicit prerequisite of deploying US3). Venv active for the checkov hook
- [ ] T016 [US3] Write failing unit tests in tests/unit/test_backfill_timeseries.py (moto): recomputed buckets equal accumulating the same items through `label_to_signed` (shared oracle), re-run over an unchanged item set is bucket-identical (SC-004), windows whose TTL already passed are skipped and counted (`buckets_skipped_ttl`), buckets outside the horizon untouched (FR-005), manifest carries every contracts/backfill-manifest.md field including `scope` {ticker_filter, window_filter, argv}, `rejected_timestamps` counts FR-010 rejects, legacy-unversioned buckets are rewritten via the `attribute_not_exists(version)` branch, a failing bucket write lands in the manifest `failures` list while the run continues, `--dry-run` emits a manifest with zero writes; fixed dates/freezegun throughout (TTL comparisons are time-relative)
- [ ] T017 [US3] Implement scripts/backfill_timeseries.py: `--env`, `--assume-role`, `--dry-run`, `--force` (recorded in manifest), `--ticker`/`--window` targeted repair (FR-009); preflight enforces quiescence per spec Clarifications Q3 (rule disabled or disabled with confirmation, then the three-part drain criterion via one GetMetricData call: 240s zero Invocations, zero Throttles trailing 6h, zero Errors trailing 30m, evaluated after the wait); recompute from sentiment_items through `label_to_signed`; conditional versioned writes per D1; manifest emission per contract; re-enable the rule; T016 passes

**Checkpoint**: quickstart runbook executable end to end (`--dry-run` locally); actual
backfill runs stay gated on explicit operator go per environment (spec A5)

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T018 [P] FR-006 CANON doc amendments (owner sign-off gates these, SC-005): docs/MODELING.md score-is-a-probability section split (item claims stay unsigned, bucket claims become signed) and the "no replay, rescore or backfill path in src/" sentence amended to name the aggregate-recompute backfill without claiming re-inference; docs/SERVICE-SHAPE.md output-schema warning; README.md confidence wording
- [ ] T019 [P] FR-006 code docstring amendments: the two analysis handler docstrings asserting 0.0-1.0; the fanout module docstring (write_fanout docstrings go with the T011 deletion); src/lambdas/dashboard/api_v2.py module docstring's claim of a historical backfill endpoint that never existed, labeled pre-existing drift repair in the commit
- [ ] T020 Fold the Active Technologies entry appended to CLAUDE.md into docs/ACTIVE-TECHNOLOGIES.md per the project CLAUDE.md rule
- [ ] T021 Full gates: `make validate`, `make test-local`, coverage floor 80% (constitution), quickstart.md unit and integration commands pass as written; after deploy, run the quickstart manual smoke (versioned signed bucket via the newest-first query; chart line leaves the top band on the Amplify customer dashboard) as the SC-001/SC-006 live check; note the coverage metric measures src/ only (Makefile `--cov=src`), so scripts/backfill_timeseries.py sits outside the floor and relies on T016's suite (ar3-007)
- [ ] T022 At ship: delete this feature's card specs/001-signed-fanout/card.md (cards lifecycle; the superseded 001-signed-sentiment-fanout card was already folded into it at planning close); CloudTrail data events offered to the owner as explicit accept/decline (FR-004); backfill execution per environment only on separate explicit operator go

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup; BLOCKS all stories (T002 before T003; T004 parallel with either)
- **US1 (Phase 3)**: after Foundational (needs signed.py)
- **US2 (Phase 4)**: after Foundational; T012 rewires the hop T007 touched, so run US2 after US1 (single developer) or coordinate on handler.py
- **US3 (Phase 5)**: after Phase 2 and T010/T011 (backfill shares `label_to_signed` and the D1 write shape; T015 terraform is independent and can start any time)
- **Polish (Phase 6)**: T018/T019 after behavior lands (docs amend to match code); T020 any time; T021 after all stories; T022 at ship only

### Within stories

- Test tasks fail before their implementation task lands (T002 before T003, T005 before T006/T007, T008/T009 before T010-T012, T016 before T017)
- T011 (deletion + __init__ rewrite) lands with or immediately after T010, never before T012 is ready to rewire the handler in the same PR, or the tree breaks at import time

### Parallel opportunities

- T004 with T002/T003; T009 with T008; T015 with anything after Phase 2; T018 with T019

## FR coverage map

| FR | Tasks |
|---|---|
| FR-001 signed contributions | T005, T007, T010 |
| FR-002 accumulation, crash-consistent avg | T008, T010, T012, T014 |
| FR-003 once-per-article gate | T013 |
| FR-004 quiesced backfill, role, manifest | T015, T016, T017 |
| FR-005 untouched outside horizon | T016, T017 |
| FR-006 CANON amendments | T004, T018, T019 |
| FR-007 mandated tests | T002, T005, T008, T009, T013, T014, T016 |
| FR-008 item record unchanged | T005 |
| FR-009 observable and repairable failures | T009, T012, T017 |
| FR-010 timestamp bounds | T009, T012 |

## Implementation Strategy

MVP is Phase 1 + 2 + 3 (US1): signed direction through the existing writer, visible
on the chart immediately. US2 replaces the writer with accumulation. US3 repairs
history. Each checkpoint is independently testable and shippable; SC-001 through
SC-006 map onto the three checkpoints plus the Polish gates. Commit per task or
logical group; sub-agents never push (constitution section 4).

## Adversarial Review #3 (implementation readiness)

Reviewer subagent over the combined spec+plan+tasks set against the live tree,
five activities: task-artifact coherence, dependency and ordering attack,
completeness attack, constitution compliance, risk calls. Verdict: 0 CRITICAL,
2 HIGH, 3 MEDIUM, 2 LOW. Per-item record with evidence in reviews/ar3.json. Both
HIGHs were adjudicated by the orchestrator against primary evidence (grep of the
named files confirmed the import sites and the CI policy role-name patterns
verbatim); a refuter subagent was deliberately skipped on operator budget
grounds, recorded here as a process deviation.

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| ar3-001 | HIGH | Integration pipeline test imports write_fanout; no task owned it; make test-local breaks at collection from T011 to ship | fixed: T011 rewrites test_timeseries_pipeline.py in the same change |
| ar3-002 | HIGH | CI deploy user cannot create the backfill role (IAMRoles name patterns); policy extension needs the admin bootstrap apply | fixed: T015 extends ci-user-policy.tf and names the bootstrap apply as a US3 deploy prerequisite; carried as an open question for ship |
| ar3-003 | MEDIUM | T015 under-scoped: module variables, root wiring, operator principal source all missing | fixed: T015 names the full file set |
| ar3-004 | MEDIUM | Bare role name collides across environments in one account | fixed: env-prefixed name in T015, research D6, quickstart |
| ar3-005 | MEDIUM | US1 hop tests break unowned at the US2 rewire; freeze-time instruction missing from T005/T013 | fixed: T012 acceptance includes migrating T005/T013; freeze-time added to both |
| ar3-006 | LOW | generate_fanout_items survives with zero live callers, overwrite shape | fixed: deletion folded into T011 |
| ar3-007 | LOW | Coverage floor never measures scripts/backfill_timeseries.py | fixed: measurement scope stated in T021, T016 suite relied on |

Highest-risk task per reviewer: T011 (four consumer surfaces on deleted symbols;
T010/T011/T012 must land as one change or SSE cold start breaks). Likeliest
rework driver: the US3 terraform scope, where three independent defects converged
and would all have surfaced at apply time.

## Gate verdict

READY FOR IMPLEMENTATION. 0 CRITICAL, 0 HIGH open across AR#1 (spec), AR#2
(plan/design), AR#3 (tasks/readiness); all MEDIUM and LOW findings fixed in the
artifacts. Implementation starts only on explicit operator go (First-Feature
Gate). Open questions carried to the gate: the admin bootstrap apply for the CI
policy extension (ar3-002, operator-run, before US3 terraform deploys);
CloudTrail data events accept/decline (FR-004); legacy-bucket deletion for chart
honesty (spec A3); the dormant ingestion-grant drop, now framed as the
enforcement half of the version mechanism (ar2-010); the live-path double-count
residual for partially completed retries, detection via SC-003 spot recompute
(AR#2 refuter residual, candidate future card); backfill execution per
environment on separate explicit go (spec A5).
