# Tasks: X-Ray Instrumentation Hardening

**Status**: Rev 2 -- principal engineer task review applied
**Total**: 28 tasks (4 setup, 2 foundational, 6 US1, 5 US2, 7 US3, 4 polish)

## Rev 2 Corrections
1. T001: New IAM statement (existing *-sentiment-* scope mismatches ADOT)
2. T007: Version pinned via ADOT_COLLECTOR_VERSION env var
3. T008: COPY path fixed (relative to build context src/)
4. T011: Includes .dockerignore for non-SSE builds
5. T012: Downscoped to graceful degradation check
6. T018+T019 merged into T018
7. T017: Clarified local vs preprod

---

## Phase 1: Setup
- [x] T001 Add NEW IAM statement in infrastructure/terraform/ci-user-policy.tf for ADOT layer access. Resources: arn:aws:lambda:*:901920570463:layer:aws-otel-collector-*. Actions: lambda:GetLayerVersion.
- [x] T002 [P] Add x-amzn-trace-id to SSE Lambda Function URL CORS allow_headers + expose_headers in infrastructure/terraform/main.tf (line 764, 769)
- [x] T003 [P] Add x-amzn-trace-id to Dashboard Lambda Function URL CORS allow_headers + expose_headers in infrastructure/terraform/main.tf (line 439, ~445)
- [x] T004 Run terraform plan to verify T001-T003

---

## Phase 2: Foundational
- [x] T005 Verify tracer and emit_metric imports work from src/lib/timeseries/ module path
- [x] T006 [P] Verify ADOT layer download works with updated IAM from T001

---

## Phase 3: US1 - SSE ADOT (P1) MVP
- [ ] T007 [US1] Add ADOT layer download in .github/workflows/deploy.yml BEFORE SSE build. Env var ADOT_COLLECTOR_VERSION=0-102-1. Preprod after line 518, prod after line 1491. Download to src/lambdas/sse_streaming/adot-layer/
- [ ] T008 [US1] Modify src/lambdas/sse_streaming/Dockerfile: COPY lambdas/sse_streaming/adot-layer/extensions/ /opt/extensions/ and collector-config/ to /opt/collector-config/ BEFORE USER lambda (line 66). chmod +x. Replace TODO. Paths relative to context src/.
- [ ] T009 [P] [US1] Add exclusion comment to src/lambdas/analysis/Dockerfile
- [ ] T010 [P] [US1] Add exclusion comment to src/lambdas/dashboard/Dockerfile
- [ ] T011 [US1] Add lambdas/sse_streaming/adot-layer/ to src/.dockerignore and .gitignore
- [ ] T012 [US1] Verify Dockerfile builds without adot-layer/ (graceful degradation)

---

## Phase 4: US2 - Frontend Trace (P2)
**Note**: sse-connection.ts NO changes. client.ts deferred.
- [ ] T013 [US2] Create frontend/src/lib/tracing.ts: generateXRayTraceId() via crypto.getRandomValues(). Import as @/lib/tracing.
- [ ] T014 [US2] Modify frontend/src/hooks/use-sse.ts: pass trace headers to SSEConnection constructor (~line 126). Fix FR-032 comments.
- [ ] T015 [P] [US2] Modify frontend/src/app/api/sse/[...path]/route.ts: fallback trace ID (~3 lines)
- [ ] T016 [US2] Modify frontend/tests/e2e/xray-trace-propagation.spec.ts: assert REQUEST headers + reconnection test
- [ ] T017 [US2] Run Playwright locally (no CORS issue). Preprod E2E needs T002/T003 deployed.

---

## Phase 5: US3 - Fanout Metrics (P3)
- [x] T018 [US3] Add imports (tracer, emit_metric) AND SilentFailure/Count to batch write handler in src/lib/timeseries/fanout.py (~line 186) FailurePath=fanout_batch_write
- [x] T019 [P] [US3] Add SilentFailure/Count to base field update handler (~line 281) FailurePath=fanout_base_update
- [x] T020 [P] [US3] Add SilentFailure/Count to label counts handler (~line 302) FailurePath=fanout_label_update
- [x] T021 [P] [US3] Add ConditionalCheck/Count to conditional high handler (~line 324) + SilentFailure for non-conditional
- [x] T022 [P] [US3] Add ConditionalCheck/Count to conditional low handler (~line 332) + SilentFailure for non-conditional
- [x] T023 [US3] Create tests/unit/test_fanout_metrics.py: test all 5 handlers, mock tracer + emit_metric
- [x] T024 [US3] Run pytest tests/unit/test_fanout_metrics.py -v

---

## Phase 6: Polish
- [ ] T025 Run pre-commit run --all-files
- [ ] T026 Run make validate
- [ ] T027 Run terraform plan
- [ ] T028 Update CLAUDE.md Active Technologies

---

## Dependencies
Phase 1 -> Phase 2 -> [Phase 3 | Phase 4 | Phase 5] -> Phase 6
Phase 4 T017 E2E needs T002/T003 deployed. Phase 5 needs T005 verified.
Phases 3-5 are independent and can run in parallel.

## Strategy
**MVP**: Phase 1+2+3 (12 tasks, ADOT only). **Full**: All 28 tasks.
