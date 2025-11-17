# Tasks: Interactive Dashboard Demo

**Input**: Design documents from `/specs/001-interactive-dashboard-demo/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Integration tests are included per spec requirements. Unit tests are optional and included for critical components.

**Organization**: Tasks are grouped by functional requirement (treated as user stories) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which functional area this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Per plan.md, this is a serverless project with structure:
- `src/lambdas/` - Lambda function handlers
- `src/dashboard/` - Dashboard UI files
- `src/lib/` - Shared libraries
- `infrastructure/terraform/` - IaC
- `tests/` - Test files

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure per plan.md (src/, tests/, infrastructure/)
- [ ] T002 Initialize Python 3.11 project with requirements.txt (boto3, transformers, torch, fastapi, mangum, requests, python-json-logger)
- [ ] T003 [P] Initialize requirements-dev.txt (pytest, moto, pytest-asyncio, black, ruff)
- [ ] T004 [P] Create .gitignore for Python (venv/, __pycache__/, *.pyc, .env, *.zip)
- [ ] T005 [P] Create README.md with project overview and link to quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY functional requirement can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Store NewsAPI key in AWS Secrets Manager (sentiment-analyzer/newsapi)
- [ ] T007 Create S3 bucket for model artifacts (sentiment-models-{ACCOUNT_ID})
- [ ] T008 Build HuggingFace DistilBERT model layer using infrastructure/scripts/build-model-layer.sh
- [ ] T009 Upload model layer to S3 bucket
- [ ] T010 Create Terraform backend configuration in infrastructure/terraform/backend.tf
- [ ] T011 Create Terraform variables in infrastructure/terraform/variables.tf (aws_region, newsapi_secret_arn, watch_tags, model_version)
- [ ] T012 Create shared Lambda IAM role module in infrastructure/terraform/modules/lambda/iam.tf
- [ ] T013 [P] Create DynamoDB table Terraform module in infrastructure/terraform/modules/dynamodb/main.tf
- [ ] T014 [P] Implement shared DynamoDB helpers in src/lambdas/shared/dynamodb.py (parse_items, conditional_write)
- [ ] T015 [P] Implement Secrets Manager helper in src/lambdas/shared/secrets.py (get_secret)
- [ ] T016 [P] Implement data schemas in src/lambdas/shared/schemas.py (SentimentItem, validate_source_id, validate_score, validate_sentiment)
- [ ] T017 [P] Implement deduplication logic in src/lib/deduplication.py (generate_source_id, content_hash)
- [ ] T018 [P] Implement CloudWatch metrics helper in src/lib/utils.py (emit_metric, log_structured)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Data Ingestion (Priority: P1) 🎯 MVP Core

**Goal**: Fetch items from NewsAPI matching 5 watch tags, deduplicate, and store in DynamoDB

**Independent Test**: Manually invoke ingestion Lambda → verify items appear in DynamoDB with correct schema

### Implementation for User Story 1

- [ ] T019 [P] [US1] Create base adapter interface in src/lambdas/ingestion/adapters/base.py (AbstractAdapter with fetch_items method)
- [ ] T020 [P] [US1] Implement NewsAPI adapter in src/lambdas/ingestion/adapters/newsapi.py (fetch_articles, handle rate limits, backoff)
- [ ] T021 [US1] Create ingestion config module in src/lambdas/ingestion/config.py (parse watch tags from env, validate tags)
- [ ] T022 [US1] Implement ingestion Lambda handler in src/lambdas/ingestion/handler.py (EventBridge trigger, fetch from NewsAPI, dedup, insert to DynamoDB, publish SNS)
- [ ] T023 [US1] Create Terraform for ingestion Lambda in infrastructure/terraform/modules/lambda/ingestion.tf (function, EventBridge rule, SNS topic, IAM permissions)
- [ ] T024 [US1] Create Terraform outputs for ingestion Lambda ARN and SNS topic ARN in infrastructure/terraform/outputs.tf
- [ ] T025 [US1] Add ingestion Lambda CloudWatch log group and metrics in infrastructure/terraform/modules/lambda/ingestion.tf

### Integration Test for User Story 1

- [ ] T026 [US1] Create integration test for end-to-end ingestion flow in tests/integration/test_ingestion_flow.py (mock NewsAPI, verify DynamoDB insert, verify deduplication)

**Checkpoint**: At this point, User Story 1 should be fully functional - items can be ingested and stored

---

## Phase 4: User Story 2 - Sentiment Analysis (Priority: P1) 🎯 MVP Core

**Goal**: Analyze sentiment of ingested items using HuggingFace DistilBERT and update DynamoDB

**Independent Test**: Publish SNS message with test item → verify DynamoDB updated with sentiment/score

### Implementation for User Story 2

- [ ] T027 [P] [US2] Implement sentiment inference logic in src/lambdas/analysis/sentiment.py (load_model with caching, analyze_sentiment, map to positive/neutral/negative)
- [ ] T028 [P] [US2] Create analysis models module in src/lambdas/analysis/models.py (model path config, neutral detection threshold)
- [ ] T029 [US2] Implement analysis Lambda handler in src/lambdas/analysis/handler.py (SNS trigger, run inference, update DynamoDB, emit metrics)
- [ ] T030 [US2] Create Terraform for analysis Lambda in infrastructure/terraform/modules/lambda/analysis.tf (function with 1024MB memory, Lambda layer attachment, SNS subscription, DLQ, IAM permissions)
- [ ] T031 [US2] Add analysis Lambda CloudWatch log group and metrics in infrastructure/terraform/modules/lambda/analysis.tf
- [ ] T032 [US2] Create Terraform for Lambda layer in infrastructure/terraform/modules/lambda/layer.tf (publish model layer from S3)

### Integration Test for User Story 2

- [ ] T033 [US2] Create integration test for sentiment analysis in tests/integration/test_sentiment_analysis.py (insert pending item, trigger analysis, verify sentiment updated)

**Checkpoint**: At this point, User Stories 1 AND 2 should work end-to-end - items ingested and analyzed

---

## Phase 5: User Story 3 - Live Dashboard (Priority: P1) 🎯 MVP Core

**Goal**: Display real-time sentiment analysis results with charts and SSE streaming

**Independent Test**: Open dashboard URL → verify charts load → verify SSE connection shows new items within 10 seconds

### Implementation for User Story 3

- [ ] T034 [P] [US3] Create dashboard HTML in src/dashboard/index.html (layout with metrics cards, Chart.js charts, items table)
- [ ] T035 [P] [US3] Create dashboard CSS in src/dashboard/styles.css (grid layout, metric cards styling, responsive design)
- [ ] T036 [P] [US3] Create dashboard JavaScript in src/dashboard/app.js (Chart.js initialization, SSE connection, update charts/table)
- [ ] T037 [P] [US3] Create dashboard config in src/dashboard/config.js (API endpoints, region, update intervals)
- [ ] T038 [US3] Implement metrics aggregation helpers in src/lambdas/dashboard/metrics.py (calculate_sentiment_distribution, calculate_tag_distribution, calculate_ingestion_rate)
- [ ] T039 [US3] Implement dashboard Lambda handler in src/lambdas/dashboard/handler.py (FastAPI app, serve HTML, /api/metrics endpoint, /api/stream SSE endpoint)
- [ ] T040 [US3] Create Terraform for dashboard Lambda in infrastructure/terraform/modules/lambda/dashboard.tf (function, Function URL with CORS, IAM permissions)
- [ ] T041 [US3] Add dashboard Lambda CloudWatch log group in infrastructure/terraform/modules/lambda/dashboard.tf
- [ ] T042 [US3] Create Terraform output for dashboard URL in infrastructure/terraform/outputs.tf

### Integration Test for User Story 3

- [ ] T043 [US3] Create integration test for dashboard endpoints in tests/integration/test_dashboard_query.py (test /api/metrics, test HTML load, test SSE stream)

**Checkpoint**: All core user stories complete - full demo flow works end-to-end

---

## Phase 6: User Story 4 - Tag Watch Configuration (Priority: P2)

**Goal**: Allow admin to update watch tags via Lambda environment variables

**Independent Test**: Update WATCH_TAGS env var → trigger ingestion → verify new tags are fetched

### Implementation for User Story 4

- [ ] T044 [US4] Add tag validation logic in src/lambdas/ingestion/config.py (validate_tag_format, max 5 tags, max 200 chars, no control chars)
- [ ] T045 [US4] Add tag update helper script in infrastructure/scripts/update_watch_tags.sh (AWS CLI command to update Lambda env)
- [ ] T046 [US4] Document tag configuration in specs/001-interactive-dashboard-demo/quickstart.md (already exists, verify completeness)

**Checkpoint**: Tags can be updated for demo customization

---

## Phase 7: User Story 5 - Observability (Priority: P2)

**Goal**: Emit CloudWatch metrics and structured logs for monitoring

**Independent Test**: Trigger ingestion and analysis → verify CloudWatch metrics appear → verify structured logs are queryable

### Implementation for User Story 5

- [ ] T047 [P] [US5] Add CloudWatch alarms for ingestion Lambda in infrastructure/terraform/modules/lambda/ingestion.tf (high error rate, rate limit hit, execution timeout, no new items)
- [ ] T048 [P] [US5] Add CloudWatch alarms for analysis Lambda in infrastructure/terraform/modules/lambda/analysis.tf (high latency, analysis errors, DLQ depth)
- [ ] T049 [P] [US5] Add CloudWatch alarms for dashboard Lambda in infrastructure/terraform/modules/lambda/dashboard.tf (high error rate, slow metrics API)
- [ ] T050 [US5] Create CloudWatch dashboard JSON in infrastructure/terraform/cloudwatch_dashboard.tf (ingestion rate, sentiment distribution, error rates, latency)

**Checkpoint**: Full observability in place for demo monitoring

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T051 [P] Create unit tests for adapters in tests/unit/test_adapters.py (test NewsAPI adapter, test deduplication)
- [ ] T052 [P] Create unit tests for sentiment inference in tests/unit/test_sentiment.py (test positive/neutral/negative detection, test threshold)
- [ ] T053 [P] Create unit tests for DynamoDB helpers in tests/unit/test_deduplication.py (test source_id generation, test content hashing)
- [ ] T054 [P] Create test fixtures in tests/fixtures/sample_items.json (sample NewsAPI responses)
- [ ] T055 Create deployment script in infrastructure/scripts/deploy.sh (terraform init, plan, apply, output dashboard URL)
- [ ] T056 [P] Create seed data script in infrastructure/scripts/seed_data.py (populate DynamoDB with test data)
- [ ] T057 [P] Add code formatting check to CI (.github/workflows/lint.yml with black and ruff)
- [ ] T058 Run full quickstart.md validation (deploy from scratch, verify demo flow)
- [ ] T059 Create demo day checklist script in infrastructure/scripts/demo_checklist.sh (verify secrets, update tags, trigger ingestion, check dashboard)
- [ ] T060 Add architecture diagram to docs (EventBridge → Ingestion → SNS → Analysis → DynamoDB → Dashboard)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Stories 1, 2, 3 are tightly coupled (MVP core) - should be done sequentially
  - User Story 4 (Tag Config) can be done after US1
  - User Story 5 (Observability) can be done in parallel with US3
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (Ingestion)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (Analysis)**: Depends on US1 completion (needs SNS topic from US1)
- **User Story 3 (Dashboard)**: Depends on US1 and US2 completion (needs DynamoDB data)
- **User Story 4 (Tag Config)**: Can start after US1 completion
- **User Story 5 (Observability)**: Can start after US1 completion, parallel with US2/US3

### Within Each User Story

- Models/adapters before handlers
- Handlers before Terraform
- Terraform before integration tests
- Core implementation before tests
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1 Setup**: T003, T004, T005 can run in parallel
- **Phase 2 Foundational**: T013, T014, T015, T016, T017, T018 can run in parallel after T006-T012 complete
- **US1 Implementation**: T019, T020 can run in parallel
- **US2 Implementation**: T027, T028 can run in parallel
- **US3 Implementation**: T034, T035, T036, T037 can run in parallel
- **US5 Observability**: T047, T048, T049 can run in parallel
- **Phase 8 Polish**: T051, T052, T053, T054, T056, T057 can run in parallel

---

## Parallel Example: User Story 3 (Dashboard)

```bash
# Launch all static dashboard files together:
Task: "Create dashboard HTML in src/dashboard/index.html"
Task: "Create dashboard CSS in src/dashboard/styles.css"
Task: "Create dashboard JavaScript in src/dashboard/app.js"
Task: "Create dashboard config in src/dashboard/config.js"

# Then launch backend:
Task: "Implement dashboard Lambda handler in src/lambdas/dashboard/handler.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 3 Only)

1. Complete Phase 1: Setup (~30 minutes)
2. Complete Phase 2: Foundational (~2 hours - CRITICAL blocks all stories)
3. Complete Phase 3: User Story 1 - Ingestion (~1 hour)
4. Complete Phase 4: User Story 2 - Analysis (~1.5 hours)
5. Complete Phase 5: User Story 3 - Dashboard (~2 hours)
6. **STOP and VALIDATE**: Test full demo flow end-to-end
7. Deploy and run through demo day checklist

**Total MVP time**: ~7 hours (2-4 hours setup + 4-5 hours implementation)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready (~2.5 hours)
2. Add User Story 1 → Test independently → Items can be ingested
3. Add User Story 2 → Test independently → Items are analyzed
4. Add User Story 3 → Test independently → Dashboard shows results (MVP complete!)
5. Add User Story 4 → Tag configuration works
6. Add User Story 5 → Observability in place
7. Polish phase → Production-ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (~2.5 hours)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (Ingestion) - MUST complete first
   - Then **Developer A**: User Story 4 (Tag Config)
3. After US1 complete:
   - **Developer B**: User Story 2 (Analysis) - MUST complete second
   - **Developer C**: User Story 5 (Observability) - can start in parallel
4. After US1 and US2 complete:
   - **Developer A or B**: User Story 3 (Dashboard)
5. **All developers**: Polish phase (parallel tasks)

**Critical path**: Setup → Foundational → US1 → US2 → US3 (cannot be parallelized)

---

## Terraform Deployment Order

The infrastructure tasks follow this dependency order:

1. **Backend & Variables** (T010, T011) - Must be first
2. **IAM & DynamoDB Module** (T012, T013) - Parallel after backend
3. **Shared helpers** (T014-T018) - Parallel, no Terraform deps
4. **Ingestion Lambda** (T023-T025) - After T012, T013
5. **Model Layer** (T032) - Independent, can be parallel
6. **Analysis Lambda** (T030, T031) - After ingestion Lambda (needs SNS topic ARN), needs model layer
7. **Dashboard Lambda** (T040-T042) - After DynamoDB table exists

**Terraform apply strategy**:
- Run `terraform apply` after T013 (DynamoDB exists)
- Re-run after T023 (ingestion Lambda exists)
- Re-run after T030 (analysis Lambda exists)
- Final run after T040 (dashboard Lambda exists)

OR run single `terraform apply` after all Terraform files are created (T042)

---

## Testing Strategy

### Unit Tests (Optional - included for critical components)

- **Adapters**: Verify NewsAPI parsing, rate limit handling
- **Sentiment**: Verify positive/neutral/negative classification, threshold logic
- **Deduplication**: Verify stable source_id generation

### Integration Tests (Required per spec)

- **Ingestion flow**: End-to-end NewsAPI → DynamoDB
- **Sentiment analysis**: SNS → Analysis → DynamoDB update
- **Dashboard query**: Metrics API and SSE stream

### Manual Demo Validation (Required)

Per quickstart.md:
1. Update watch tags
2. Trigger ingestion
3. Verify dashboard shows results
4. Check CloudWatch metrics and logs

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific functional requirement for traceability
- User Stories 1, 2, 3 form the MVP core and must be completed sequentially
- User Stories 4, 5 are enhancements that can be added incrementally
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Cost target: $3.85-7.85/month for demo scale
- Timeline target: 2-4 hours setup + 4-5 hours implementation = 6-9 hours total

---

## Task Count Summary

- **Total Tasks**: 60
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 13 tasks (BLOCKING)
- **Phase 3 (US1 - Ingestion)**: 8 tasks (MVP core)
- **Phase 4 (US2 - Analysis)**: 7 tasks (MVP core)
- **Phase 5 (US3 - Dashboard)**: 10 tasks (MVP core)
- **Phase 6 (US4 - Tag Config)**: 3 tasks
- **Phase 7 (US5 - Observability)**: 4 tasks
- **Phase 8 (Polish)**: 10 tasks

**MVP scope (Phases 1-5)**: 43 tasks (~6-9 hours)
**Full feature (All phases)**: 60 tasks (~10-15 hours)

**Parallel opportunities identified**: 25 tasks can run in parallel (marked with [P])
