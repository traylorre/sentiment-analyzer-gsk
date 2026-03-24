# Tasks: Route Frontend Through API Gateway + Enable Cognito Auth

**Input**: Design documents from `/specs/1253-api-gateway-cognito-auth/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — spec requires unit + E2E tests for auth behavior.

**Organization**: Tasks grouped by user story for independent implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US5)
- Exact file paths included

---

## Phase 1: Setup

**Purpose**: Prepare the API Gateway module to accept public route configurations

- [x] T001 Add `public_routes` variable to `infrastructure/terraform/modules/api_gateway/variables.tf` with `path_parts`, `has_proxy`, `is_endpoint`, `endpoint_auth` fields
- [x] T002 Add `api_gateway_url` variable to `infrastructure/terraform/modules/amplify/variables.tf`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create `locals` block in `infrastructure/terraform/modules/api_gateway/main.tf` that computes intermediate resources, leaf resources, and FR-012 endpoint resources from `public_routes` variable
- [x] T004 [P] Create intermediate API Gateway resources (`/api`, `/api/v2`, `/api/v2/auth`, `/api/v2/auth/oauth`, `/api/v2/tickers`, `/api/v2/market`, `/api/v2/timeseries`) via `for_each` in `infrastructure/terraform/modules/api_gateway/main.tf` — parent nodes only, no methods
- [x] T005 [P] Create FR-012 intermediate-as-endpoint resources (`/api/v2/notifications` with COGNITO auth, `/api/v2/auth/magic-link` with NONE auth) with `ANY` method + Lambda proxy integration + `OPTIONS` method + MOCK integration in `infrastructure/terraform/modules/api_gateway/main.tf`
- [x] T006 Wire `enable_cognito_auth = true` and `cognito_user_pool_arn = module.cognito.user_pool_arn` in API Gateway module call in `infrastructure/terraform/main.tf` (lines ~800-830)
- [x] T007 Wire `public_routes` list with all 11 route group configs (plus 2 FR-012 entries) in API Gateway module call in `infrastructure/terraform/main.tf`

**Checkpoint**: `terraform plan` should show intermediate resources + authorizer activation. No public leaf resources yet.

---

## Phase 3: User Story 1 — Protected Endpoints Reject Invalid Tokens (Priority: P1) MVP

**Goal**: Cognito JWT validation on `{proxy+}` catch-all; invalid/missing/expired tokens get 401 before Lambda invocation.

**Independent Test**: `curl` protected endpoint without token → 401; with valid JWT → 200.

### Tests for User Story 1

- [x] T008 [P] [US1] Create unit test `tests/unit/test_api_gateway_cognito.py` — test that protected endpoints return 401 without JWT (mock API Gateway responses)
- [x] T009 [P] [US1] Create E2E test `tests/e2e/test_cognito_auth.py` — test `GET /api/v2/configurations` without token → 401, with expired JWT → 401, with UUID token → 401, with valid JWT → 200

### Implementation for User Story 1

- [x] T010 [US1] Verify existing Cognito authorizer resource in `infrastructure/terraform/modules/api_gateway/main.tf` activates correctly when `enable_cognito_auth = true` — check `{proxy+}` method switches from `NONE` to `COGNITO_USER_POOLS`
- [x] T011 [US1] Verify root method also switches auth when `enable_cognito_auth = true` in `infrastructure/terraform/modules/api_gateway/main.tf`
- [ ] T012 [US1] Run `terraform plan` and verify `{proxy+}` ANY method shows `authorization = "COGNITO_USER_POOLS"`, authorizer ID is set

**Checkpoint**: Protected endpoints return 401 for invalid tokens. Orphaned endpoints also protected (they fall through to `{proxy+}`). Public endpoints currently broken (no overrides yet).

---

## Phase 4: User Story 2 — Public Endpoints Remain Accessible (Priority: P1)

**Goal**: 11 public resource groups bypass Cognito auth via explicit `authorization = "NONE"` overrides.

**Independent Test**: `curl` public endpoints without token → 200.

### Tests for User Story 2

- [x] T013 [P] [US2] Add test cases to `tests/e2e/test_cognito_auth.py` — test `POST /auth/anonymous` → 201, `GET /health` → 200, `GET /tickers/search` with UUID → 200, `GET /notifications/unsubscribe?token=x` → 200 (all without Cognito JWT)

### Implementation for User Story 2

- [x] T014 [P] [US2] Create leaf public resources for auth endpoints (`/anonymous`, `/refresh`, `/validate`) with `ANY` + `NONE` + Lambda integration + `OPTIONS` + MOCK in `infrastructure/terraform/modules/api_gateway/main.tf`
- [x] T015 [P] [US2] Create `{proxy+}` public resources for grouped endpoints (`/auth/magic-link/{proxy+}`, `/auth/oauth/{proxy+}`, `/tickers/{proxy+}`, `/market/{proxy+}`, `/timeseries/{proxy+}`) with `ANY` + `NONE` + Lambda integration + `OPTIONS` + MOCK in `infrastructure/terraform/modules/api_gateway/main.tf`
- [x] T016 [P] [US2] Create leaf public resources for infrastructure endpoints (`/health`, `/api/v2/runtime`, `/api/v2/notifications/unsubscribe`) with `ANY` + `NONE` + Lambda integration + `OPTIONS` + MOCK in `infrastructure/terraform/modules/api_gateway/main.tf`
- [ ] T017 [US2] Run `terraform plan` and verify ~85 new resources, all public routes show `authorization = "NONE"`, all protected routes show `authorization = "COGNITO_USER_POOLS"`
- [ ] T018 [US2] Verify FR-012: `/api/v2/notifications` has `ANY` + `COGNITO_USER_POOLS` and `/api/v2/auth/magic-link` has `ANY` + `NONE` in plan output

**Checkpoint**: Both protected (401) and public (200) endpoints work correctly. Full API Gateway resource tree deployed.

---

## Phase 5: User Story 3 — Frontend Routes Through API Gateway (Priority: P1)

**Goal**: Amplify frontend uses API Gateway URL instead of Lambda Function URL.

**Independent Test**: Check Amplify env var `NEXT_PUBLIC_API_URL` points to API Gateway with `/v1` stage.

### Implementation for User Story 3

- [x] T019 [US3] Change `NEXT_PUBLIC_API_URL` from `var.dashboard_lambda_url` to `var.api_gateway_url` in `infrastructure/terraform/modules/amplify/main.tf` (line ~42) — update the Feature 1114 comment
- [x] T020 [US3] Pass `api_gateway_url = module.api_gateway.api_endpoint` to `module.amplify_frontend` in `infrastructure/terraform/main.tf` (lines ~1097-1120)
- [x] T021 [US3] Add `module.api_gateway` to Amplify's `depends_on` list in `infrastructure/terraform/main.tf`
- [ ] T022 [US3] Verify `terraform plan` shows Amplify env var change from Lambda URL to API Gateway URL

**Checkpoint**: Frontend will route through API Gateway after next deploy. Rate limiting and Cognito auth active on all traffic.

---

## Phase 6: User Story 4 — 401 Responses Include CORS Headers (Priority: P1)

**Goal**: Browser can detect and handle 401 responses (CORS headers on error responses).

**Independent Test**: `curl -D-` protected endpoint → 401 with `Access-Control-Allow-Origin` header.

### Tests for User Story 4

- [x] T023 [P] [US4] Add CORS test cases to `tests/e2e/test_cognito_auth.py` — verify 401 response includes `Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials: true`, explicit `Access-Control-Allow-Headers` (not `*`)

### Implementation for User Story 4

- [x] T024 [US4] Update `aws_api_gateway_gateway_response.unauthorized` in `infrastructure/terraform/modules/api_gateway/main.tf` — add CORS headers to `response_parameters`: `Access-Control-Allow-Origin` (from `method.request.header.origin`), `Access-Control-Allow-Headers` (explicit list), `Access-Control-Allow-Credentials` (`'true'`), `Access-Control-Allow-Methods`
- [x] T025 [P] [US4] Update `aws_api_gateway_gateway_response.missing_auth_token` in `infrastructure/terraform/modules/api_gateway/main.tf` — same CORS headers as unauthorized
- [x] T026 [P] [US4] Create `aws_api_gateway_gateway_response.access_denied` (403) in `infrastructure/terraform/modules/api_gateway/main.tf` — with CORS headers (doesn't exist yet)
- [x] T027 [US4] Verify CORS headers use explicit list NOT wildcard: `"Content-Type, Authorization, Accept, Cache-Control, Last-Event-ID, X-Amzn-Trace-Id, X-User-ID"`

**Checkpoint**: Frontend can detect 401/403 via JavaScript. Auth error → redirect to sign-in flow works.

---

## Phase 7: User Story 5 — Anonymous Sessions Continue Working (Priority: P2)

**Goal**: Existing anonymous users with UUID tokens can still use public endpoints.

**Independent Test**: UUID token on `GET /tickers/search` → 200; UUID on `GET /configurations` → 401.

### Tests for User Story 5

- [x] T028 [US5] Add anonymous session test cases to `tests/e2e/test_cognito_auth.py` — UUID token on public endpoint → 200, UUID token on protected endpoint → 401

### Implementation for User Story 5

- [x] T029 [US5] Verify no implementation needed — anonymous flow works by design (public endpoints don't check Cognito, protected endpoints reject non-JWT tokens). Document verification in test results.

**Checkpoint**: Full feature complete. All 5 user stories independently verified.

---

## Phase 8: Deploy Pipeline & Smoke Tests

**Purpose**: Update CI/CD to verify API Gateway health

- [x] T030 Add API Gateway health check URL retrieval (`terraform output -raw dashboard_api_url`) to `outputs` step in `.github/workflows/deploy.yml` (after line ~1084)
- [x] T031 Add API Gateway smoke test (curl `${API_GW_URL}/v1/health`) to smoke test section in `.github/workflows/deploy.yml` (after line ~1175)
- [x] T032 Add protected endpoint 401 check (curl `${API_GW_URL}/v1/api/v2/configurations` → expect 401) to smoke test section

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T033 [P] Add `lifecycle { prevent_destroy = true }` to Cognito authorizer resource in `infrastructure/terraform/modules/api_gateway/main.tf`
- [ ] T034 [P] Run `terraform plan` full validation — verify resource count, no unexpected changes
- [ ] T035 [P] Run existing Playwright E2E test suite to verify zero functional regression
- [ ] T036 Run `terraform apply` and execute quickstart.md verification commands
- [ ] T037 Update security zone map if any changes from implementation (verify spec accuracy)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1
- **Phase 3 (US1: Protected)**: Depends on Phase 2. Creates the Cognito auth layer.
- **Phase 4 (US2: Public)**: Depends on Phase 2 (T003-T007). Can run in parallel with Phase 3 but logically should follow (public overrides don't help without Cognito enabled).
- **Phase 5 (US3: Frontend)**: Depends on Phases 3+4 (needs both protected and public working)
- **Phase 6 (US4: CORS)**: Can run in parallel with Phases 3+4 (independent gateway responses)
- **Phase 7 (US5: Anonymous)**: Depends on Phases 3+4 (needs both protected and public)
- **Phase 8 (Pipeline)**: Depends on Phases 3+4+5
- **Phase 9 (Polish)**: Depends on all previous

### User Story Dependencies

- **US1 (Protected)**: Independent — only needs foundational
- **US2 (Public)**: Independent — only needs foundational
- **US3 (Frontend)**: Depends on US1+US2 (needs working auth before switching traffic)
- **US4 (CORS)**: Independent — gateway responses are separate from route resources
- **US5 (Anonymous)**: Depends on US1+US2 (verification only, no implementation)

### Parallel Opportunities

- T004 + T005: Intermediates and FR-012 resources in parallel
- T008 + T009: US1 tests in parallel
- T014 + T015 + T016: All public resource groups in parallel
- T024 + T025 + T026: All gateway response CORS updates in parallel
- T033 + T034 + T035: Polish tasks in parallel

---

## Implementation Strategy

### MVP First (User Stories 1+2)

1. Phase 1: Setup variables
2. Phase 2: Foundational intermediates + module wiring
3. Phase 3: US1 — Cognito enabled on `{proxy+}`
4. Phase 4: US2 — Public overrides deployed
5. **VALIDATE**: `terraform plan` shows correct auth on all routes

### Full Delivery

6. Phase 5: US3 — Frontend switched to API Gateway
7. Phase 6: US4 — CORS on 401/403
8. Phase 7: US5 — Anonymous verification
9. Phase 8: Pipeline updates
10. Phase 9: Polish + regression tests

---

## Notes

- All Terraform changes must be in a single `terraform apply` (FR-007). Tasks are split for review clarity but deploy together.
- ~85 new Terraform resources expected.
- Rollback: Set `enable_cognito_auth = false` + revert Amplify URL.
- FR-012 (T005, T018): Critical — `/api/v2/notifications` and `/api/v2/auth/magic-link` must have methods as intermediates.
