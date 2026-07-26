# Tasks: Lambda Log Visibility

**Input**: Design documents from `/specs/001-lambda-log-visibility/`
**Prerequisites**: plan.md (post-AR#2), spec.md (post-Clarifications), research.md, data-model.md, contracts/logging-config.md, quickstart.md
**Tests**: TDD explicitly requested — contract tests precede implementation.
**Ordering constraint (hard)**: T004/T005 pre-deploy baselines MUST complete before the merge/deploy task T020.

## Phase 1: Setup & Pre-Deploy Baselines

- [ ] T001 Verify branch `001-lambda-log-visibility` is current with origin/main; venv active (`source .venv/bin/activate`)
- [ ] T002 [P] Record pre-deploy log-shape samples: capture 50 recent events from each of the six log groups (`/aws/lambda/preprod-sentiment-{dashboard,ingestion,analysis,metrics,notification,canary}`) into `specs/001-lambda-log-visibility/evidence/pre-deploy/` (SC-003 comparison input)
- [ ] T003 [P] FR-004 baseline: count StructuredLogger duplicate emissions over 24h on `/aws/lambda/preprod-sentiment-metrics` (same logical event appearing 2x); record count + query in `specs/001-lambda-log-visibility/evidence/pre-deploy/metrics-dup-baseline.md`
- [ ] T004 [P] SC-005 baseline: run 20 identical dashboard requests (alias-qualified invoke, same route), count INFO events per request-id, record p50 in `specs/001-lambda-log-visibility/evidence/pre-deploy/dashboard-p50-baseline.md`
- [ ] T005 [P] SC-003 positive control (pre): fire one synthetic ImportModuleError-shaped log line at the dashboard log group's active stream context (or locate a historical one); record whether metric `dashboard_import_errors` incremented in `specs/001-lambda-log-visibility/evidence/pre-deploy/filter-control.md` (research R-9 question)

**Checkpoint**: evidence/pre-deploy/ populated — deploy-gating baselines exist.

## Phase 2: Foundational (helper + contract tests — blocks all user stories)

- [ ] T006 Write failing contract tests C-1..C-6, C-8 in `tests/unit/shared/test_logging_config.py`: C-1 re-assert level every call; C-2 httpx/httpcore WARNING pins survive LOG_LEVEL=DEBUG; C-3 zero handler mutations; C-4 self-test line emits exactly once per process (latch scoped to emission only, reset hook for tests); C-5 import of module is side-effect-free; C-6 other loggers' levels untouched; C-8 self-test line goes through `logging.getLogger("src.lambdas.shared.logging_config")`, static message
- [ ] T007 Implement `src/lambdas/shared/logging_config.py::configure_lambda_logging()` to pass T006: root setLevel from LOG_LEVEL env (unset→INFO), explicit own-level pins httpx/httpcore=WARNING, once-per-process self-test INFO emission, documented test reset hook, no handlers/formatters/propagation touched
- [ ] T008 Write failing coverage-guard test in `tests/unit/test_entrypoint_logging_coverage.py`: glob `src/lambdas/*/handler.py`, exclude exactly `{sse_streaming, chaos_restore}` (documented in-test), assert each remaining handler module source contains a top-level `configure_lambda_logging(` call before any handler def (C-7; AR#2 F4 — no hardcoded function list)

**Checkpoint**: helper green under contract tests; guard red (no entrypoint wired yet).

## Phase 3: User Story 1 — Operator debugs from logs (P1) 🎯 MVP

**Goal**: INFO from first-party modules visible in all six functions' log groups.
**Independent test**: quickstart preprod steps 1-2 post-deploy; guard green locally.

- [ ] T009 [P] [US1] Wire `configure_lambda_logging()` at import top-level in `src/lambdas/dashboard/handler.py` (before Powertools app/resolver setup; powertools Logger untouched)
- [ ] T010 [P] [US1] Wire in `src/lambdas/ingestion/handler.py` (keep existing module-logger setLevel(INFO) at ~:116 — FR-011)
- [ ] T011 [P] [US1] Wire in `src/lambdas/analysis/handler.py` (keep ~:78 setLevel; log_structured print path untouched)
- [ ] T012 [P] [US1] Wire in `src/lambdas/metrics/handler.py` (currently configures nothing; StructuredLogger untouched)
- [ ] T013 [P] [US1] Wire in `src/lambdas/notification/handler.py` (keep LOG_LEVEL env read at ~:33 — same semantics, no duplicate config)
- [ ] T014 [P] [US1] Wire in `src/lambdas/canary/handler.py` (keep ~:25 setLevel)
- [ ] T015 [US1] Run T008 guard → green; run full unit suite (`pytest tests/unit/ -v`) → no regressions (FR-011/C-6 verified across suites)

**Checkpoint**: all six entrypoints wired; guard + contract tests green — US1 code-complete.

## Phase 4: User Story 3 — Content safety riders (P3 but pre-deploy-blocking per FR-012)

**Goal**: nothing newly visible leaks secrets/PII (FR-012, SC-007).
**Independent test**: unit tests for masked shapes; grep-audit recorded.

- [ ] T016 [P] [US3] Mask recipient email in `src/lambdas/notification/sendgrid_service.py` lines ~136/141 (`s***@domain` shape); unit test the masked line shape in `tests/unit/notification/test_sendgrid_service.py` (create or extend)
- [ ] T017 [P] [US3] Confirm httpx pin closes the finnhub key-in-URL path: unit test in `tests/unit/shared/test_logging_config.py` — with root=DEBUG (worst case), an httpx-logger INFO record is NOT emitted (pin holds); reference research R-5/R-8
- [ ] T018 [US3] Card the two out-of-scope defects on the owner board follow-up list (do NOT fix here): (a) notification entrypoint raw-event dump + full-email lines (handler.py:56/170/220 + error paths) — pre-existing CWE-312; (b) finnhub API key passed as URL query param (adapter hygiene). Record card refs in `specs/001-lambda-log-visibility/evidence/cards.md`

**Checkpoint**: FR-012 satisfied; SC-007 pre-conditions in place.

## Phase 5: User Story 2 — Consumers keep working (P2) + verification tooling

**Goal**: byte-compatible existing lines; on-demand dashboard proof exists.
**Independent test**: script runs against preprod pre-deploy (refresh lines absent) and post-deploy (present).

- [ ] T019 [US2] Write `scripts/verify-log-visibility.py`: alias-qualified dashboard invokes for the three refresh outcomes (no cookie / garbage cookie / valid session via server-mint pattern from tests/e2e conftest), then `filter_log_events` asserting `refresh.cookie_absent`, `refresh.rejected`, `refresh.success` and the C-8 self-test line; exit non-zero on any missing (FR-008 dashboard + SC-006 drill)
- [ ] T020 [US2] Write preprod E2E `tests/e2e/test_log_visibility.py` (marker `preprod`): per-function dark-line assertions — dashboard: refresh.* lines; ingestion: `storage.py` "Storage operation complete"; analysis: sentiment.py INFO site; metrics: C-8 self-test line; notification: synthetic empty-digest invoke (flat payload) then digest_service "Found users due for digest"/"Digest processing complete"; canary: C-8 self-test line within 15 min window

**Checkpoint**: verification artifacts exist and fail against current preprod (proves they discriminate).

## Phase 6: Merge, Deploy & Post-Deploy Verification

- [ ] T021 Pre-push gate: `make validate` + `pytest tests/unit/` + security-alert check per CLAUDE.md pre-push checklist; PR with plan-linked description; owner-gated push per standing rule
- [ ] T022 Merge → deploy pipeline; monitor Deploy-to-Preprod + Preprod Integration Tests (Monitor tool pattern; stuck-credentials watch)
- [ ] T023 Post-deploy: run `scripts/verify-log-visibility.py` (SC-001 + SC-006); run `pytest tests/e2e/test_log_visibility.py -m preprod` (FR-008 all six; SC-002 start)
- [ ] T024 [P] SC-003 comparison: re-capture the six log-group samples (as T002) post-deploy; diff warning/error line shapes (FR-003), powertools/StructuredLogger JSON byte-shape (FR-004 vs T003 baseline — no ADDITIONAL duplication), re-run T005 positive control identically; record verdicts in `specs/001-lambda-log-visibility/evidence/post-deploy/`
- [ ] T025 [P] SC-005 close: re-run T004's 20-request workload, p50 delta ≤10 INFO lines; project monthly ingestion delta <$1; record in evidence/post-deploy/
- [ ] T026 [P] SC-004/SC-007 week-one watch: scheduled queries (token= pattern AND @-address pattern AND `[DEBUG]`) across six groups; record daily results in evidence/post-deploy/week-one.md; SC-004 caveat: a deliberate LOG_LEVEL=DEBUG window, if any, must be recorded

**Checkpoint**: SC-001..SC-007 all evidenced; feature DONE pending week-one watch closure.

## Dependencies & Execution Order

- Phase 1 (T002-T005) parallel; independent of Phases 2-5 EXCEPT T020/T022: baselines MUST exist before deploy (hard gate).
- Phase 2 strictly sequential (T006 → T007 → T008 red).
- Phase 3: T009-T014 parallel (six files, disjoint); T015 after all.
- Phase 4: T016/T017 parallel after T007; T018 anytime.
- Phase 5: T019/T020 after T007 (reference the self-test line name); both must FAIL against pre-deploy preprod (discrimination proof) — run before merge.
- Phase 6 strictly sequential from T021; T024-T026 parallel after T023.

## Requirement → Task Map

| Req | Tasks | | Req | Tasks |
|---|---|---|---|---|
| FR-001 | T007, T009-T014, T023 | | FR-008 | T019, T020, T023 |
| FR-002 | T006(C-1), T026 | | FR-009 | T024 |
| FR-003 | T024 | | FR-010 | T006(C-2), T007, T017 |
| FR-004 | T003, T024 | | FR-011 | T006(C-6), T010/T011/T013/T014, T015 |
| FR-005 | (no infra tasks — satisfied by construction; T021 review confirms) | | FR-012 | T016, T017, T018 |
| FR-006 | T008 exclusion + T006(C-5) | | SC-001 | T023 |
| FR-007 | T021/T022 (normal pipeline; no console mutation anywhere) | | SC-002 | T023, T026 |
| SC-003 | T002, T005, T024 | | SC-004 | T026 |
| SC-005 | T004, T025 | | SC-006 | T019, T023 |
| SC-007 | T016, T017, T026 | | | |

## Implementation Strategy

MVP = Phases 1-3 (visibility live, guard green). Phases 4-5 are
pre-merge-blocking riders (FR-012 content safety + discriminating
verification), NOT optional polish — the merge task T021 requires
T003/T004/T005/T016/T017/T019/T020 complete. Single PR; single revert
restores status quo.
