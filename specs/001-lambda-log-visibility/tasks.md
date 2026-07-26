# Tasks: Lambda Log Visibility

**Input**: Design documents from `/specs/001-lambda-log-visibility/`
**Prerequisites**: plan.md (post-AR#2), spec.md (post-Clarifications), research.md, data-model.md, contracts/logging-config.md, quickstart.md
**Tests**: TDD explicitly requested — contract tests precede implementation.
**Ordering constraint (hard)**: T002-T005 pre-deploy baselines MUST complete before the deploy task T022.

## Phase 1: Setup & Pre-Deploy Baselines

- [X] T001 Verify branch `001-lambda-log-visibility` is current with origin/main; venv active (`source .venv/bin/activate`)
- [X] T002 [P] Record pre-deploy log-shape samples: capture 50 recent events from each of the six log groups (`/aws/lambda/preprod-sentiment-{dashboard,ingestion,analysis,metrics,notification,canary}`) into `specs/001-lambda-log-visibility/evidence/pre-deploy/` (SC-003 comparison input)
- [X] T003 [P] FR-004 baseline: count StructuredLogger duplicate emissions over 24h on `/aws/lambda/preprod-sentiment-metrics` (same logical event appearing 2x); record count + query in `specs/001-lambda-log-visibility/evidence/pre-deploy/metrics-dup-baseline.md`
- [X] T004 [P] SC-005 baseline: run 20 identical dashboard requests (alias-qualified invoke, same route), count INFO events per request-id, record p50 in `specs/001-lambda-log-visibility/evidence/pre-deploy/dashboard-p50-baseline.md`
- [X] T005 [P] SC-003 positive control (pre): `aws logs put-log-events` one synthetic ImportModuleError-shaped line into a FRESH test stream in the dashboard log group (filters evaluate group-wide at ingestion — AR#3 confirmed viable; needs operator `logs:CreateLogStream`/`PutLogEvents`); record whether metric `dashboard_import_errors` incremented in `specs/001-lambda-log-visibility/evidence/pre-deploy/filter-control.md` (research R-9 question)

**Checkpoint**: evidence/pre-deploy/ populated — deploy-gating baselines exist.

## Phase 2: Foundational (helper + contract tests — blocks all user stories)

- [X] T006 Write failing contract tests C-1..C-6, C-8 in `tests/unit/shared/test_logging_config.py`: C-1 re-assert level every call; C-2 httpx/httpcore WARNING pins survive LOG_LEVEL=DEBUG; C-3 zero handler mutations; C-4 self-test line emits exactly once per process (latch scoped to emission only, reset hook for tests); C-5 import of module is side-effect-free; C-6 other loggers' levels untouched; C-8 self-test line goes through `logging.getLogger("src.lambdas.shared.logging_config")`, static message
- [X] T007 Implement `src/lambdas/shared/logging_config.py::configure_lambda_logging()` to pass T006: root setLevel from LOG_LEVEL env (unset→INFO), explicit own-level pins httpx/httpcore=WARNING, once-per-process self-test INFO emission, documented test reset hook, no handlers/formatters/propagation touched. STATED DEPENDENCY (AR#3): C-8's evidence value assumes awslambdaric bootstrap attaches the root handler BEFORE importing the handler module (research R-1 source read: `main()` runs `_setup_logging` before `_get_handler`) — record this in the module docstring; if it were ever false the self-test would fall to logging.lastResort (WARNING) and drop
- [X] T008 Write failing coverage-guard test in `tests/unit/test_entrypoint_logging_coverage.py`: glob `src/lambdas/*/handler.py`, exclude exactly `{sse_streaming, chaos_restore}` (documented in-test), assert per file: character index of top-level `configure_lambda_logging(` call < index of the first line matching `^def ` in the module source (AR#3 precise criterion — not "before lambda_handler", not docstring-fooled) (C-7; AR#2 F4 — no hardcoded function list)

**Checkpoint**: helper green under contract tests; guard red (no entrypoint wired yet).

## Phase 3: User Story 1 — Operator debugs from logs (P1) 🎯 MVP

**Goal**: INFO from first-party modules visible in all six functions' log groups.
**Independent test**: quickstart preprod steps 1-2 post-deploy; guard green locally.

- [X] T009 [P] [US1] Wire `configure_lambda_logging()` at import top-level in `src/lambdas/dashboard/handler.py` (before Powertools app/resolver setup; powertools Logger untouched)
- [X] T010 [P] [US1] Wire in `src/lambdas/ingestion/handler.py` (keep existing module-logger setLevel(INFO) at ~:116 — FR-011)
- [X] T011 [P] [US1] Wire in `src/lambdas/analysis/handler.py` (keep ~:78 setLevel; log_structured print path untouched)
- [X] T012 [P] [US1] Wire in `src/lambdas/metrics/handler.py` (currently configures nothing; StructuredLogger untouched)
- [X] T013 [P] [US1] Wire in `src/lambdas/notification/handler.py` (keep LOG_LEVEL env read at ~:33 — same semantics, no duplicate config)
- [X] T014 [P] [US1] Wire in `src/lambdas/canary/handler.py` (keep ~:25 setLevel)
- [X] T015 [US1] Run T008 guard → green; run full unit suite (`pytest tests/unit/ -v`) → no regressions (FR-011/C-6 verified across suites)

**Checkpoint**: all six entrypoints wired; guard + contract tests green — US1 code-complete.

## Phase 4: User Story 3 — Content safety riders (P3 but pre-deploy-blocking per FR-012)

**Goal**: nothing newly visible leaks secrets/PII (FR-012, SC-007).
**Independent test**: unit tests for masked shapes; grep-audit recorded.

- [X] T016 [P] [US3] Mask recipient email in `src/lambdas/notification/sendgrid_service.py` lines ~136/141 ONLY (`s***@domain` shape); do NOT touch the handler.py:56/170/220 lines — those are T018's card, already visible today, out of this feature's causal scope (AR#3 over-masking guardrail); unit test the masked line shape in `tests/unit/notification/test_sendgrid_service.py` (create or extend)
- [X] T017 [P] [US3] Confirm httpx pin closes the finnhub key-in-URL path: unit test in `tests/unit/shared/test_logging_config.py` — with root=DEBUG (worst case), an httpx-logger INFO record is NOT emitted (pin holds); reference research R-5/R-8
- [X] T018 [US3] Card the two out-of-scope defects on the owner board follow-up list (do NOT fix here): (a) notification entrypoint raw-event dump + full-email lines (handler.py:56/170/220 + error paths) — pre-existing CWE-312; (b) finnhub API key passed as URL query param (adapter hygiene). Record card refs in `specs/001-lambda-log-visibility/evidence/cards.md`

**Checkpoint**: FR-012 satisfied; SC-007 pre-conditions in place.

## Phase 5: User Story 2 — Consumers keep working (P2) + verification tooling

**Goal**: byte-compatible existing lines; on-demand dashboard proof exists.
**Independent test**: script runs against preprod pre-deploy (refresh lines absent) and post-deploy (present).

- [X] T019 [US2] Write `scripts/verify-log-visibility.py`: alias-qualified dashboard invokes for the three refresh outcomes — (a) POST /api/v2/auth/refresh with no cookie → `refresh.cookie_absent`; (b) same with garbage cookie → `refresh.rejected`; (c) POST /api/v2/auth/anonymous (CSRF-exempt), capture the `refresh_token=anon.…` Set-Cookie, replay it to /refresh → `refresh.success` via the anon branch (AR#3: NO bearer/JWT-secret needed; a bearer cannot reach refresh.success — the branch requires a refresh COOKIE). Then `filter_log_events` asserting all three lines + the C-8 self-test line; exit non-zero on any missing (FR-008 dashboard + SC-006 drill)
- [X] T020 [US2] Write preprod E2E `tests/e2e/test_log_visibility.py` (marker `preprod`): per-function dark-line assertions — dashboard: refresh.* lines; ingestion: `storage.py:185` "Storage operation complete"; analysis: a pinned sentiment.py INFO line (research R-2 set); metrics: C-8 self-test line; notification: synthetic empty-digest invoke (flat payload) then digest_service:154/656 lines; canary: C-8 self-test line. AR#3 flake guard: C-8 is COLD-START-ONLY (once-per-process latch survives freeze/thaw) — window every C-8 `filter_log_events` query from the function's LastModified/publish timestamp, never "now minus N minutes"

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

- Phase 1 (T002-T005) parallel; independent of Phases 2-5. Hard gate: baselines (T002-T005) MUST complete before T022 (deploy) — they do not gate test AUTHORING (T019/T020).
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

## Adversarial Review #3

Independent implementation-readiness reviewer, all claims code-grounded.
Findings: 1 HIGH, 2 MEDIUM, 2 LOW, 1 INFO — all applied to task text above.

- **Highest-risk task**: T007 — not for implementation difficulty but for
  evidential dependencies: (a) C-8's value assumes awslambdaric attaches the
  root handler before handler-module import (true per research R-1 source
  read; now a STATED dependency in T007), and (b) C-8 is cold-start-only, so
  every C-8 query must window from the function's publish timestamp (folded
  into T020). T009 confirmed safe (powertools never touches root, R-4);
  T013 confirmed safe (same env var, same default, one root handler — no
  fight, no duplication).
- **Most likely rework source**: T019 as originally worded — the conftest
  bearer-mint pattern can NEVER reach `refresh.success` (branch requires a
  refresh COOKIE: router_v2.py:732-736) and is locally invalid post-JWT-
  rotation anyway. REQUIRED amendment applied: anonymous-cookie recipe
  (POST /auth/anonymous → capture anon refresh cookie → replay to /refresh
  → auth.py:3479 anon branch → refresh.success at :762). No secret, no
  OAuth, no bearer needed. Note: the existing E2E suite only ever tests
  refresh REJECTION — this recipe is new ground, no in-repo prior art.
- **Sequencing**: no blocking holes; T019/T020 pre-merge fail-first runs
  schedulable (preprod lacks the fix until T022); T005 injection viable
  (filters evaluate PutLogEvents at ingestion); dependency wording fixed
  (baselines gate T022, not T020).
- **Destructive-misinterpretation check**: all six wire targets + every
  line anchor verified against source; T016 over-masking guardrail added;
  T008 criterion pinned (call index < first `^def ` line). No
  two-dashboards confusion: all paths are backend src/lambdas + log groups.
- **Scope integrity**: glob-minus-exclusions yields exactly the six
  in-scope functions; nothing touches SSE; C-5 keeps SSE's shared imports
  inert; no new AWS resources anywhere.

**Gate: READY FOR IMPLEMENTATION** (required T019 amendment applied;
recommended T007/T020 amendments applied).
