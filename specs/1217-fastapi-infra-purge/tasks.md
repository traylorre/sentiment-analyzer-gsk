# Tasks: FastAPI Infrastructure Purge

**Input**: Design documents from `/specs/1217-fastapi-infra-purge/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Not explicitly requested. Banned-term scanner serves as the verification gate.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## User Story Mapping

- **US1**: Deploy Without Legacy Framework Artifacts (P1) — Infrastructure cleanup
- **US2**: Codebase Contains Zero Legacy References (P2) — Full sweep of all files
- **US3**: Deployment Verification Confirms Native Operation (P3) — Smoke tests
- **US4**: Rollback Plan Exists for Failed Deployment (P3) — Runbook

## Scope Exclusions (agreed with stakeholder)

The following paths are **excluded** from this purge and from the banned-term scanner:

| Path | Reason |
|------|--------|
| `.specify/` | Contains WIP specs (ohlc-cache-remediation) and template examples |
| `docs/cache/` | WIP cache work — banned terms will be addressed when that feature resumes |
| `CONTEXT-CARRYOVER-*` | Session carryover files — ephemeral, not part of codebase |
| `specs/archive/` | Archived historical specs (post-move destination) |
| `docs/archive/` | Archived historical docs (post-move destination) |
| `docs/archived-specs/` | Pre-existing archived specs |
| `specs/1217-fastapi-infra-purge/` | This feature's own spec (self-referential) |

---

## Phase 1: Setup

**Purpose**: Create archive directories and the banned-term validation script (foundational infrastructure for all user stories)

- [x] T001 Create archive directories: `mkdir -p docs/archive` and `mkdir -p specs/archive`
- [x] T002 Create banned-term validation script at `scripts/check-banned-terms.sh` — scan for `fastapi`, `mangum`, `uvicorn`, `starlette`, `lambda.web.adapter`, `LambdaAdapterLayer`, `AWS_LWA` with case-insensitive grep; exclude `.git/`, `specs/archive/`, `docs/archive/`, `docs/archived-specs/`, `specs/1217-fastapi-infra-purge/`, `.specify/`, `docs/cache/`, and files matching `CONTEXT-CARRYOVER-*`; exit 1 on any match, exit 0 on clean (FR-020, FR-021)
- [x] T003 Add `check-banned-terms` target to `Makefile` and add it as dependency of the `validate` target (FR-022)
- [x] T004 Run `scripts/check-banned-terms.sh` to capture baseline — expect FAIL with full list of matching files (this establishes the work queue for subsequent phases)

**Checkpoint**: Validation infrastructure is in place. All subsequent phases work toward making T004's scanner pass.

---

## Phase 2: User Story 1 — Deploy Without Legacy Framework Artifacts (Priority: P1)

**Goal**: All deployment infrastructure (Terraform, Dockerfiles, CI/CD workflows, requirements.txt) contains zero references to banned framework terms.

**Independent Test**: Run `scripts/check-banned-terms.sh` scoped to `infrastructure/`, `src/lambdas/*/Dockerfile`, `src/lambdas/*/requirements.txt`, `.github/workflows/` — expect exit 0.

### Terraform Cleanup (FR-001 through FR-004)

- [x] T005 [P] [US1] Rewrite comment in `infrastructure/terraform/main.tf` lines 730-732: change `Lambda Web Adapter runs Python in a subprocess` to `the custom runtime bootstrap runs Python in a subprocess` (FR-004)
- [x] T006 [P] [US1] Rewrite comment in `infrastructure/terraform/modules/api_gateway/main.tf` line 24: change `Mangum adapter in Lambda handles both Function URL and API Gateway` to `Lambda handler manages both Function URL and API Gateway requests` (FR-001)
- [x] T007 [P] [US1] Rewrite comment in `infrastructure/terraform/modules/api_gateway/main.tf` line 26: change `CORS configured at both API Gateway and FastAPI levels` to `CORS configured at both API Gateway and application levels` (FR-001)

### Dockerfile Cleanup (FR-005 through FR-008)

- [x] T008 [P] [US1] Rewrite comment in `src/lambdas/sse_streaming/Dockerfile` line 3: change `Replaces Lambda Web Adapter + Uvicorn with native Runtime API bootstrap` to `Native Runtime API bootstrap for streaming responses` (FR-007)

### Requirements Cleanup (FR-008)

- [x] T009 [P] [US1] Rewrite comment in `src/lambdas/dashboard/requirements.txt` line 32: remove `(001-fastapi-purge, R3)` suffix — keep `# JSON serialization - Fast native datetime/dataclass handling` (FR-008)
- [x] T010 [P] [US1] Rewrite comment in `src/lambdas/dashboard/requirements.txt` line 35: remove `(001-fastapi-purge, R1)` suffix — keep `# AWS Lambda Powertools - Routing and middleware` (FR-008)
- [x] T011 [P] [US1] Rewrite comment in `src/lambdas/sse_streaming/requirements.txt` line 7: remove `(001-fastapi-purge, R3)` suffix — keep `# JSON serialization - Fast native datetime/dataclass handling` (FR-008)

### CI/CD Cleanup (FR-009, FR-010)

- [x] T012 [P] [US1] Rewrite comment in `.github/workflows/deploy.yml` line 1169: change `SSE Lambda uses Docker image with Lambda Web Adapter, needs warmup` to `SSE Lambda uses Docker image with custom runtime, needs warmup` (FR-009)

**Checkpoint**: All deployment infrastructure is clean. `terraform plan`, Docker builds, and CI/CD contain zero banned terms.

---

## Phase 3: User Story 2 — Codebase Contains Zero Legacy References (Priority: P2)

**Goal**: A case-insensitive grep for all banned terms across the entire repository (excluding paths listed in Scope Exclusions table) returns zero matches.

**Independent Test**: Run `scripts/check-banned-terms.sh` — expect exit 0.

### Source Code Comments (FR-012, FR-013, FR-014)

- [x] T013 [P] [US2] Rewrite docstring in `src/lambdas/shared/dependencies.py` line 3: change `Replaces FastAPI's Depends() injection with module-level singletons.` to `Module-level singleton dependency providers.`
- [x] T014 [P] [US2] Rewrite comment in `src/lambdas/shared/utils/response_builder.py` line 9: change `FR-009: 422 validation errors in FastAPI-parity format` to `FR-009: 422 validation errors in standard format`
- [x] T015 [P] [US2] Rewrite docstring in `src/lambdas/shared/utils/response_builder.py` line 55: change `Build a 422 validation error response in FastAPI-parity format.` to `Build a 422 validation error response in standard format.`
- [x] T016 [P] [US2] Rewrite docstring in `src/lambdas/shared/utils/response_builder.py` line 58: change `This format is byte-identical to FastAPI's automatic 422 responses,` to `This format follows the standard Pydantic ValidationError structure,`
- [x] T017 [P] [US2] Rewrite docstring in `src/lambdas/shared/utils/cookie_helpers.py` line 3: change `Replaces FastAPI's Request.cookies and Response.set_cookie with` to `Cookie parsing and set-cookie header construction using`
- [x] T018 [P] [US2] Rewrite comment in `src/lambdas/dashboard/handler.py` line 89: change `# Module-level init logging (FR-028: replaces FastAPI lifespan no-op)` to `# Module-level init logging (FR-028)`
- [x] T019 [P] [US2] Rewrite comment in `src/lambdas/dashboard/router_v2.py` line 137: change `# Helper functions (migrated from FastAPI Request/Response to raw event dicts)` to `# Helper functions for raw API Gateway event dicts`
- [x] T020 [P] [US2] Rewrite comment in `src/lambdas/dashboard/router_v2.py` line 229: change `to avoid exception-based flow control with FastAPI HTTPException.` to `to avoid exception-based flow control with HTTP exceptions.`
- [x] T021 [P] [US2] Rewrite comment in `src/lambdas/sse_streaming/handler.py` line 516: change `# Normalize double slashes (legacy Lambda Web Adapter artifact)` to `# Normalize double slashes in request paths`
- [x] T022 [P] [US2] Rewrite line in `src/README.md` line 10: change `│   ├── dashboard/     # FastAPI dashboard (Function URL)` to `│   ├── dashboard/     # Dashboard API (Function URL)` (FR-014)

### Test File Comments (FR-012)

- [x] T023 [P] [US2] Rewrite comment in `tests/conftest.py` line 115: change `# Mock Lambda Event & Context Fixtures (001-fastapi-purge, FR-058)` to `# Mock Lambda Event & Context Fixtures (FR-058)`
- [x] T024 [P] [US2] Rewrite docstring in `tests/unit/sse_streaming/test_config_stream.py` line 7: change `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` to `Uses direct handler invocation for testing.`
- [x] T025 [P] [US2] Rewrite docstring in `tests/unit/sse_streaming/test_global_stream.py` line 5: change `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` to `Uses direct handler invocation for testing.`
- [x] T026 [P] [US2] Rewrite docstring in `tests/unit/sse_streaming/test_path_normalization.py` — remove all references to FastAPI TestClient, Lambda Web Adapter, and Starlette from module docstring; describe current test pattern using direct handler invocation
- [x] T027 [P] [US2] Rewrite docstring in `tests/unit/sse_streaming/test_connection_limit.py` line 6: change `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` to `Uses direct handler invocation for testing.`
- [x] T028 [P] [US2] Rewrite comments in `tests/integration/test_e2e_lambda_invocation_preprod.py` — find and rewrite all 4 lines referencing FastAPI (lines ~108, 111, 199, 392); replace with descriptions of current behavior without framework names
- [x] T029 [P] [US2] Rewrite comment in `tests/e2e/test_anonymous_restrictions.py` line 497: change `# FastAPI uses "detail" for error messages, other APIs may use "error" or "message"` to `# Error responses use "detail" field for error messages`
- [x] T030 [P] [US2] Rewrite comment in `tests/e2e/test_dashboard_buffered.py` line 5: change `# uses BUFFERED invoke mode (via Mangum), ensuring REST API responses` to `# uses BUFFERED invoke mode, ensuring REST API responses`

### Documentation Archive — Purge History (FR-015, FR-016)

- [x] T031 [US2] Archive purge documentation: `git mv docs/fastapi-purge docs/archive/fastapi-purge` (12 files)
- [x] T032 [US2] Archive purge specs: `git mv specs/001-fastapi-purge specs/archive/001-fastapi-purge` (8 files)

### Root Documentation Updates (FR-017, FR-018, FR-019)

- [x] T033 [US2] Update `README.md` — rewrite line 227 (`Dashboard Lambda<br/>FastAPI` → `Dashboard Lambda`) and line 918 (`Dashboard Lambda (FastAPI REST)` → `Dashboard Lambda (REST API)`); scan for and rewrite any other banned-term references (FR-017)
- [x] T034 [US2] Update `SPEC.md` — rewrite line 198 (`FastAPI + Mangum` → `Lambda Powertools`) and line 201 (`FastAPI + sse-starlette` → `custom runtime bootstrap`); scan for and rewrite any other banned-term references (FR-019)
- [x] T035 [US2] Update `CLAUDE.md` — remove `(001-fastapi-purge)` suffixes from Active Technologies entries (lines ~86-87, 854-855) and remove/rewrite any lines referencing banned terms; scan entire file for completeness (FR-018)

### Architecture Documentation Updates

- [x] T036 [P] [US2] Update `docs/architecture/DATA_FLOW_AUDIT.md` line 55: change `Dashboard Lambda<br/>FastAPI` to `Dashboard Lambda` in Mermaid diagram
- [x] T037 [P] [US2] Update `docs/architecture/ARCHITECTURE_DECISIONS.md` line 24: change `FastAPI web API` to `REST API` in Lambda description
- [x] T038 [US2] Archive `docs/architecture/LAMBDA_DEPENDENCY_ANALYSIS.md` to `docs/archive/` — contains pervasive FastAPI/Mangum references throughout (lines 4, 11, 43-47, 62-66, 77-78, 90, 304-306, 407, 425-426); too many to rewrite, historical analysis document
- [x] T039 [US2] Archive `docs/architecture/ADR-005-LAMBDA-PACKAGING-STRATEGY.md` to `docs/archive/` — contains FastAPI/Mangum package references throughout (lines 185-187, 580, 640, 1025); historical decision record, superseded by current Powertools architecture

### Security Documentation Updates

- [x] T040 [P] [US2] Archive `docs/security/CONTAINER_MIGRATION_SECURITY_ANALYSIS.md` to `docs/archive/` — contains pervasive FastAPI/Mangum references (lines 109-111, 477, 486, 973-974, 1242, 1550)
- [x] T041 [P] [US2] Update `docs/security/DASHBOARD_SECURITY_ANALYSIS.md` line 37: change `FastAPI verify_api_key()` to `verify_api_key()` or describe current auth mechanism
- [x] T042 [P] [US2] Archive `docs/security/PREPROD_HTTP_502_ROOT_CAUSE.md` to `docs/archive/` — historical root cause analysis referencing FastAPI TestClient (line 130)
- [x] T043 [P] [US2] Update `docs/security/ZERO_TRUST_PERMISSIONS_AUDIT.md` line 110: change `Serve FastAPI dashboard` to `Serve dashboard`

### Testing & Operations Documentation Updates

- [x] T044 [P] [US2] Archive `docs/testing/DASHBOARD_TESTING_BACKLOG.md` to `docs/archive/` — references FastAPI imports and TestClient (lines 47, 57); historical backlog superseded by current test suite
- [x] T045 [P] [US2] Update `docs/testing/TESTING_LESSONS_LEARNED.md` — rewrite lines 282, 300, 308 to describe current test patterns without FastAPI TestClient references
- [x] T046 [P] [US2] Update `docs/operations/TROUBLESHOOTING.md` — rewrite lines 10, 101-112 to describe current troubleshooting steps without FastAPI TestClient and httpx references
- [x] T047 [P] [US2] Update `docs/reference/API_GATEWAY_GAP_ANALYSIS.md` — rewrite lines 96, 358, 362, 395, 397 to describe current CORS and handler architecture without FastAPI/Mangum references

### Diagrams Documentation Updates

- [x] T048 [P] [US2] Update `docs/diagrams/README.md` line 295: change `Lambda Web Adapter enables HTTP/1.1 streaming (not possible with Mangum)` to `Custom runtime bootstrap enables HTTP/1.1 streaming`
- [x] T049 [P] [US2] Update `docs/diagrams/diagram-1-high-level-overview.md` line 141: change `FastAPI/Mangum` to `Lambda Powertools`

### Archive Verification

- [x] T050 [P] [US2] Verify `docs/archive/DEMO_URLS.template.md` is under `docs/archive/` and excluded from scanner; if not, move it there
- [x] T051 [P] [US2] Verify `docs/archive/sessions/PREPROD_DASHBOARD_INVESTIGATION_SUMMARY.md` is under `docs/archive/` and excluded from scanner
- [x] T052 [P] [US2] Verify `docs/archived-specs/` directory is excluded from scanner — confirm `docs/archived-specs/038-ecr-docker-build/plan.md` and `docs/archived-specs/071-fix-codeql-alerts/plan.md` are covered by the `docs/archived-specs/` exclusion

### Spec Files with Banned Terms (Historical Specs)

- [x] T053 [US2] Archive all historical spec directories containing banned terms to `specs/archive/` — move the following directories using `git mv`: `specs/002-mobile-sentiment-dashboard/`, `specs/006-user-config-dashboard/`, `specs/011-price-sentiment-overlay/`, `specs/012-ohlc-sentiment-e2e-tests/`, `specs/014-session-consistency/`, `specs/015-sse-endpoint-fix/`, `specs/016-sse-streaming-lambda/`, `specs/077-fix-config-creation-500/`, `specs/079-e2e-endpoint-roadmap/`, `specs/082-fix-sse-e2e-timeouts/`, `specs/087-test-coverage-completion/`, `specs/090-security-first-burndown/`, `specs/097-sse-content-type-header/`, `specs/098-global-stream-content-type/`, `specs/1008-analysis-lambda-container/`, `specs/1009-realtime-multi-resolution/`, `specs/1032-config-api-stability/`, `specs/1036-dashboard-container-deploy/`, `specs/1040-add-sse-starlette-dep/`, `specs/1042-sse-origin-timestamp/`, `specs/1060-fix-anonymous-auth-422/`, `specs/107-fix-cloudfront-403/`, `specs/1119-fix-anonymous-auth-422/`, `specs/1126-auth-httponly-migration/`, `specs/1130-require-role-decorator/`, `specs/1146-remove-xuserid-fallback/`, `specs/1158-csrf-double-submit/`, `specs/1170-oauth-role-advancement/`, `specs/1181-oauth-auto-link/`, `specs/1182-email-to-oauth-link/`, `specs/1183-oauth-to-oauth-link/`, `specs/1188-session-eviction-transact/`, `specs/1190-security-headers-error-codes/`, `specs/1191-mid-session-tier-upgrade/`
- [x] T054 [US2] Verify `specs/001-1093-static-whitelist/spec.md` — if it contains banned terms, move to `specs/archive/`

### Frontend Files

- [x] T055 [P] [US2] Update `frontend/tests/e2e/PLAYWRIGHT_RESEARCH_CHECKLIST.md` line 110: change `run FastAPI locally` to `run API locally`

### Full Sweep Scan

- [x] T056 [US2] Run `scripts/check-banned-terms.sh` and fix any remaining matches not covered by T005-T055 — iterate until exit code 0
- [ ] T057 [US2] Run full test suite (`make test-local`) to confirm zero regressions from comment-only changes

**Checkpoint**: `scripts/check-banned-terms.sh` exits 0. All 2983 unit tests and 191 integration tests still pass. Zero banned-term matches in non-archived/non-excluded files.

---

## Phase 4: User Story 3 — Deployment Verification Confirms Native Operation (Priority: P3)

**Goal**: Existing smoke tests in the CI/CD pipeline verify native Lambda handler operation without framework references.

**Independent Test**: Review `.github/workflows/deploy.yml` smoke test sections and confirm all assertions validate native handler responses.

- [x] T058 [US3] Review and verify `.github/workflows/deploy.yml` smoke test sections (SSE Lambda /health warmup at line 1172-1186, Dashboard Lambda warmup, ZIP Lambda triggers) — confirm all assertions validate native Lambda responses, not framework-specific responses
- [x] T059 [US3] Review and verify `.github/workflows/deploy.yml` Docker image smoke tests (build-sse-lambda-image, build-analysis-image, build-dashboard-image jobs) — confirm import validation tests check for Powertools/native imports, not FastAPI/Mangum/uvicorn imports
- [x] T060 [US3] Create deployment verification checklist at `docs/runbooks/deployment-verification-checklist.md` documenting: (1) Dashboard Lambda — `curl <FUNCTION_URL>/api/v2/health` returns HTTP 200, (2) SSE Lambda — `curl <FUNCTION_URL>/health` returns HTTP 200 with streaming headers, (3) ZIP Lambdas — CloudWatch logs confirm successful invocations (FR-023, FR-024)

**Checkpoint**: CI/CD smoke tests are framework-agnostic and verify native operation.

---

## Phase 5: User Story 4 — Rollback Plan Exists for Failed Deployment (Priority: P3)

**Goal**: A documented rollback procedure enables recovery within 15 minutes without re-introducing any removed dependency.

**Independent Test**: Review the rollback document and confirm it contains step-by-step commands for reverting each Lambda type.

- [x] T061 [US4] Create rollback procedure at `docs/runbooks/rollback-deployment.md` documenting: (1) Container Lambdas — `aws lambda update-function-code --function-name <name> --image-uri <ecr-repo>@sha256:<previous-hash>`, (2) ZIP Lambdas — `aws lambda update-function-code --function-name <name> --s3-bucket <bucket> --s3-key <previous-version-key>`, (3) Terraform state — `terraform apply -target=module.<lambda>` with prior variable values, (4) Verification — health check each Lambda after rollback (FR-025)

**Checkpoint**: Rollback procedure exists and covers all 6 Lambdas (dashboard, SSE, analysis, ingestion, metrics, notification).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, scanner hardening, and cleanup

- [x] T062 Run `make validate` to confirm banned-term gate passes as part of full validation suite
- [ ] T063 Run `make test-local` to confirm all unit and integration tests pass
- [x] T064 Run manual spot-check: `grep -rni "fastapi\|mangum\|uvicorn\|starlette" --exclude-dir=.git --exclude-dir=specs/archive --exclude-dir=docs/archive --exclude-dir=docs/archived-specs --exclude-dir=.specify --exclude-dir=docs/cache --exclude-dir=specs/1217-fastapi-infra-purge .` — expect zero results (excluding CONTEXT-CARRYOVER-* files)
- [x] T065 Review `scripts/check-banned-terms.sh` exclusion list — ensure all paths from the Scope Exclusions table are correctly excluded
- [x] T066 Run quickstart.md verification steps to confirm the feature works as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on T001 (archive dirs created)
- **US2 (Phase 3)**: Depends on T001 (archive dirs) and T002 (scanner)
- **US3 (Phase 4)**: No dependencies on US1/US2 — can run in parallel
- **US4 (Phase 5)**: No dependencies on US1/US2/US3 — can run in parallel
- **Polish (Phase 6)**: Depends on ALL user stories complete

### User Story Dependencies

- **US1 (P1)**: Independent — infrastructure-only changes
- **US2 (P2)**: Depends on T001 (archive dirs created before `git mv`); depends on T002 (scanner to verify progress)
- **US3 (P3)**: Independent — review-only, no code changes needed unless issues found
- **US4 (P3)**: Independent — creates new document only

### Within Each User Story

- US1: All T005-T012 are parallelizable (different files)
- US2: T013-T055 are mostly parallelizable (different files); T031-T032 and T053 (git mv archive ops) should run before T056 (final scan)
- US3: T058-T059 sequential (same file review), T060 independent
- US4: Single task T061

### Parallel Opportunities

Within US1, all 8 tasks (T005-T012) can execute in parallel — they touch different files.

Within US2, the following parallel groups exist:
- **Group A** (source code, 10 tasks): T013-T022 — all different .py files
- **Group B** (test files, 8 tasks): T023-T030 — all different test files
- **Group C** (archive ops, 2 tasks): T031-T032 — different directories
- **Group D** (root docs, 3 tasks): T033-T035 — different files
- **Group E** (arch docs, 4 tasks): T036-T039 — different files
- **Group F** (security docs, 4 tasks): T040-T043 — different files
- **Group G** (other docs, 4 tasks): T044-T047 — different files
- **Group H** (diagram docs, 2 tasks): T048-T049 — different files
- **Group I** (archive verification, 3 tasks): T050-T052 — different files
- **Group J** (spec archive, 2 tasks): T053-T054 — bulk operation + verification
- **Group K** (frontend, 1 task): T055 — single file

US3 and US4 can run in parallel with each other and with US1/US2.

---

## Parallel Example: User Story 1

```bash
# All 8 infrastructure tasks run in parallel (different files):
Task: T005 "Rewrite terraform main.tf PYTHONPATH comment"
Task: T006 "Rewrite terraform api_gateway/main.tf line 24"
Task: T007 "Rewrite terraform api_gateway/main.tf line 26"
Task: T008 "Rewrite SSE Dockerfile comment"
Task: T009 "Rewrite dashboard requirements.txt line 32"
Task: T010 "Rewrite dashboard requirements.txt line 35"
Task: T011 "Rewrite SSE requirements.txt line 7"
Task: T012 "Rewrite deploy.yml comment"
```

## Parallel Example: User Story 2 (Source Code Group)

```bash
# All 10 source code comment tasks run in parallel:
Task: T013 "Rewrite dependencies.py docstring"
Task: T014 "Rewrite response_builder.py line 9"
Task: T015 "Rewrite response_builder.py line 55"
Task: T016 "Rewrite response_builder.py line 58"
Task: T017 "Rewrite cookie_helpers.py docstring"
Task: T018 "Rewrite handler.py comment"
Task: T019 "Rewrite router_v2.py line 137"
Task: T020 "Rewrite router_v2.py line 229"
Task: T021 "Rewrite sse handler.py line 516"
Task: T022 "Rewrite src/README.md line 10"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: US1 Infrastructure Cleanup (T005-T012)
3. **STOP and VALIDATE**: Run scanner scoped to infrastructure dirs — expect zero matches
4. All deployment infrastructure is now clean

### Incremental Delivery

1. Setup → Scanner and archive dirs ready
2. US1 → Infrastructure clean → Validate
3. US2 → Full codebase clean → Validate with scanner (exit 0)
4. US3 + US4 (parallel) → Verification docs and rollback procedure
5. Polish → Final sweep, full test suite, manual spot-check

### Recommended Execution

Execute US1 first (8 tasks, all parallelizable), then US2 in batch groups (A through K above), then US3+US4 in parallel, then Polish. All comment rewrites are parallelizable within their group. The bulk spec archive (T053) should run early in US2 to reduce scanner noise.

---

## Summary

| Phase | Story | Tasks | Parallel? | Description |
|-------|-------|-------|-----------|-------------|
| 1 | Setup | T001-T004 | Sequential | Archive dirs + scanner + baseline |
| 2 | US1 | T005-T012 | All parallel | Infrastructure cleanup (8 tasks) |
| 3 | US2 | T013-T057 | Groups A-K | Full codebase sweep (45 tasks) |
| 4 | US3 | T058-T060 | Mostly parallel | Deployment verification (3 tasks) |
| 5 | US4 | T061 | N/A | Rollback procedure (1 task) |
| 6 | Polish | T062-T066 | Sequential | Final validation (5 tasks) |
| **Total** | | **T001-T066** | | **66 tasks** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- T053 is the largest single task (archiving ~34 spec directories) — consider splitting into sub-batches if git mv performance is a concern
- T056 is the "catch-all" task — after all planned edits, run the scanner and fix any remaining matches discovered at runtime
- All comment rewrites preserve functional intent — no behavior changes
- Existing test suite (2983 unit + 191 integration) serves as regression gate
- The banned-term scanner itself is the primary acceptance test for US2
- Scope exclusions (`.specify/`, `docs/cache/`, `CONTEXT-CARRYOVER-*`) are documented and agreed — banned terms in those paths will be addressed in their respective feature work
