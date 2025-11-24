# Tasks: Interactive Dashboard Demo

**Input**: Design documents from `/specs/001-interactive-dashboard-demo/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, ON_CALL_SOP.md

---

## Testing Philosophy

- **MANDATORY**: Every component MUST have unit tests
- **E2E grows incrementally**: Start with single-component E2E, expand as components are added
- **Test-first commits**: Each implementation task includes unit tests in the same commit
- **CI/CD enforced**: Tests run on every commit, deployment blocked if tests fail
- **Coverage gate**: >80% line coverage required

---

## Deployment Strategy

- **Dev environment**: Test all changes here first
- **Prod environment**: Promotes only after dev validates
- **Zero-downtime**: Blue/green Lambda deployments with graceful schema evolution
- **Grey area handling**: Components tolerate deployment ordering (either component can deploy first)

---

## Architecture Reference

**DynamoDB Table**: `${environment}-sentiment-items`
- PK: `source_id` (String)
- SK: `timestamp` (String, ISO8601)
- GSIs: `by_sentiment`, `by_tag`, `by_status`
- TTL: `ttl_timestamp` (30 days)

**Secret Paths**:
- `${environment}/sentiment-analyzer/newsapi`
- `${environment}/sentiment-analyzer/dashboard-api-key`

**SNS Topic**: `${environment}-sentiment-analysis-requests`

---

## Path Conventions

```
src/
├── lambdas/
│   ├── ingestion/       # EventBridge triggered
│   ├── analysis/        # SNS triggered
│   ├── dashboard/       # Function URL
│   └── shared/          # Common utilities
├── lib/                 # Shared libraries
└── dashboard/           # Static UI files

infrastructure/terraform/
├── main.tf
├── variables.tf
├── modules/
│   ├── dynamodb/        # ✅ EXISTS
│   ├── secrets/         # ✅ EXISTS
│   ├── sns/             # ✅ EXISTS
│   ├── iam/             # ✅ EXISTS
│   ├── eventbridge/     # ✅ EXISTS
│   └── monitoring/      # ✅ EXISTS (11 alarms)

tests/
├── unit/
├── integration/
└── e2e/
```

---

## Phase 1: Project Setup & CI/CD

**Goal**: Initialize project, CI/CD pipelines, and basic tooling
**Checkpoint**: CI/CD runs tests on every commit

### Project Structure

- [ ] T001 Create project directory structure per plan.md (src/, tests/, .github/workflows/)
- [ ] T002 Initialize Python 3.13 project with pyproject.toml or requirements.txt
  - boto3==1.34.0, transformers==4.36.0, torch==2.1.0, fastapi==0.104.0
  - mangum==0.17.0, requests==2.31.0, pydantic==2.5.3, python-json-logger==2.0.7
- [ ] T003 Initialize requirements-dev.txt
  - pytest==7.4.3, moto==4.2.0, pytest-asyncio==0.21.1, pytest-cov==4.1.0
  - black==23.13.0, ruff==0.1.6, responses==0.24.0
- [ ] T004 Create .gitignore (venv/, __pycache__/, .env, *.zip, .terraform/, *.tfstate*)
- [ ] T005 Create pytest.ini (testpaths=tests, coverage settings, asyncio_mode=auto)

**Commit**: `chore: Initialize Python project structure and dependencies`

### CI/CD Pipelines

- [ ] T006 Create .github/workflows/test.yml (pytest on push/PR, Python 3.13, coverage report, 80% gate)
- [ ] T007 Create .github/workflows/lint.yml (black --check, ruff check)
- [ ] T008 Create .github/workflows/deploy-dev.yml (terraform apply on main push, dev workspace)
- [ ] T009 Create .github/workflows/deploy-prod.yml (manual approval, prod workspace)
- [ ] T010 Create .github/workflows/integration.yml (runs after dev deploy, uses dev environment)

**Commit**: `ci: Add GitHub Actions workflows for test, lint, and deploy pipelines`

### README & Documentation

- [ ] T011 Create README.md with:
  - Pipeline status badges (Tests, Deploy Dev, Deploy Prod)
  - Architecture overview
  - Link to specs/001-interactive-dashboard-demo/quickstart.md
  - Link to ON_CALL_SOP.md

**Commit**: `docs: Add README with CI/CD badges and documentation links`

---

## Phase 2: Shared Libraries & Helpers

**Goal**: Build reusable components that all Lambdas will use
**Checkpoint**: All helpers have 100% test coverage

### DynamoDB Helpers

- [ ] T012 Implement src/lambdas/shared/dynamodb.py
  - `get_dynamodb_resource()` with retry configuration
  - `parse_dynamodb_item(item)` → dict conversion
  - `build_key(source_id, timestamp)` → proper key structure
- [ ] T013 Write tests/unit/test_dynamodb_helpers.py (moto mocks)

**Commit**: `feat: Add DynamoDB helper library with unit tests`

### Secrets Manager Helper

- [ ] T014 Implement src/lambdas/shared/secrets.py
  - `get_secret(secret_id)` with in-memory caching
  - Cache TTL of 5 minutes
- [ ] T015 Write tests/unit/test_secrets.py (moto mocks)

**Commit**: `feat: Add Secrets Manager helper with caching and unit tests`

### Pydantic Schemas

- [ ] T016 Implement src/lambdas/shared/schemas.py
  - `SentimentItemCreate` (ingestion input)
  - `SentimentItemUpdate` (analysis output)
  - `SentimentItemResponse` (dashboard output)
  - All validation per data-model.md
- [ ] T017 Write tests/unit/test_schemas.py (valid/invalid inputs)

**Commit**: `feat: Add Pydantic validation schemas with unit tests`

### Deduplication Logic

- [ ] T018 Implement src/lib/deduplication.py
  - `generate_source_id(article)` → `newsapi#{sha256[:16]}`
  - Prefer URL, fallback to title+publishedAt
- [ ] T019 Write tests/unit/test_deduplication.py (deterministic hashing)

**Commit**: `feat: Add deduplication library with unit tests`

### CloudWatch Utilities

- [ ] T020 Implement src/lib/metrics.py
  - `emit_metric(name, value, unit, dimensions)`
  - `log_structured(level, message, **kwargs)` JSON format
  - `get_correlation_id(source_id, context)`
- [ ] T021 Write tests/unit/test_metrics.py

**Commit**: `feat: Add CloudWatch metrics and logging utilities with unit tests`

### Error Response Helper

- [ ] T022 Implement src/lambdas/shared/errors.py
  - `error_response(status_code, message, code, details)` per plan.md schema
  - Error codes: RATE_LIMIT_EXCEEDED, VALIDATION_ERROR, NOT_FOUND, etc.
- [ ] T023 Write tests/unit/test_errors.py

**Commit**: `feat: Add standardized error response helper with unit tests`

---

## Phase 3: Data Ingestion (US1)

**Goal**: Fetch from NewsAPI, deduplicate, store in DynamoDB, publish to SNS
**Checkpoint**: Items flow from NewsAPI to DynamoDB with SNS notification

### NewsAPI Adapter

- [ ] T024 Implement src/lambdas/ingestion/adapters/base.py
  - `AbstractAdapter` with `fetch_items()` abstract method
- [ ] T025 Implement src/lambdas/ingestion/adapters/newsapi.py
  - `fetch_articles(api_key, tag, page_size=100)`
  - Rate limit handling with exponential backoff
  - Circuit breaker after 3 failures
- [ ] T026 Write tests/unit/test_newsapi_adapter.py (mock requests, rate limits, errors)

**Commit**: `feat(ingestion): Add NewsAPI adapter with rate limiting and unit tests`

### Ingestion Configuration

- [ ] T027 Implement src/lambdas/ingestion/config.py
  - Parse `WATCH_TAGS` environment variable
  - Validate tag format, max 5 tags
- [ ] T028 Write tests/unit/test_ingestion_config.py

**Commit**: `feat(ingestion): Add watch tags configuration with unit tests`

### Ingestion Lambda Handler

- [ ] T029 Implement src/lambdas/ingestion/handler.py `lambda_handler`
  - EventBridge trigger handling
  - Fetch NewsAPI key from Secrets Manager
  - For each tag: fetch articles, generate source_id, deduplicate
  - Insert with `status=pending`, `timestamp`, `ttl_timestamp`
  - Publish to SNS with `timestamp` field (not `ingested_at`)
  - Emit CloudWatch metrics: ArticlesFetched, NewItemsIngested, DuplicatesSkipped
- [ ] T030 Write tests/unit/test_ingestion_handler.py (full flow with moto)

**Commit**: `feat(ingestion): Add Lambda handler with deduplication and SNS publish`

### Ingestion E2E Test

- [ ] T031 Write tests/integration/test_ingestion_e2e.py
  - Mock NewsAPI, real DynamoDB (moto), real SNS (moto)
  - Verify items in table with correct schema
  - Verify SNS messages with `timestamp` field

**Commit**: `test(ingestion): Add E2E test for ingestion flow`

---

## Phase 4: Sentiment Analysis (US2)

**Goal**: Consume SNS, run DistilBERT inference, update DynamoDB
**Checkpoint**: Items have sentiment scores after processing

### Model Loading

- [ ] T032 Implement src/lambdas/analysis/sentiment.py
  - `load_model()` with global caching from `/opt/model`
  - `analyze_sentiment(text)` → (sentiment, score)
  - Truncate to 512 tokens
  - Neutral threshold: score < 0.6
- [ ] T033 Write tests/unit/test_sentiment.py (mock pipeline, thresholds)

**Commit**: `feat(analysis): Add DistilBERT model loading and inference with unit tests`

### Analysis Lambda Handler

- [ ] T034 Implement src/lambdas/analysis/handler.py `lambda_handler`
  - Parse SNS message (extract `source_id`, `timestamp`, `text_for_analysis`)
  - Load model (cached)
  - Run inference
  - Update DynamoDB with `sentiment`, `score`, `model_version`, `status=analyzed`
  - Use conditional update: `attribute_not_exists(sentiment)`
  - Emit metrics: AnalysisCount, InferenceLatencyMs, SentimentDistribution
- [ ] T035 Write tests/unit/test_analysis_handler.py (moto, mock model)

**Commit**: `feat(analysis): Add Lambda handler with conditional update and unit tests`

### Analysis E2E Test

- [ ] T036 Write tests/integration/test_analysis_e2e.py
  - Insert pending item, publish SNS message
  - Verify item updated with sentiment/score
  - Verify idempotency (second run doesn't overwrite)

**Commit**: `test(analysis): Add E2E test for analysis flow`

### Model Layer Build

- [ ] T037 Create infrastructure/scripts/build-model-layer.sh
  - Download DistilBERT from HuggingFace
  - Package in layer/python/model/
  - Verify model hash (supply chain security)
  - Create ZIP for Lambda layer
- [ ] T038 Document model layer upload process in quickstart.md

**Commit**: `infra: Add model layer build script with hash verification`

---

## Phase 5: Dashboard (US3)

**Goal**: Serve live dashboard with FastAPI, SSE updates, metrics display
**Checkpoint**: Users can view real-time sentiment data

### Static Dashboard UI

- [ ] T039 Create src/dashboard/index.html
  - Metrics cards (total, positive, neutral, negative)
  - Chart.js pie chart (sentiment distribution)
  - Chart.js bar chart (by tag)
  - Recent items table
- [ ] T040 Create src/dashboard/styles.css (responsive, sentiment colors)
- [ ] T041 Create src/dashboard/app.js
  - Fetch /api/metrics on load
  - Connect to /api/stream SSE
  - Update charts and table on events
  - Use `timestamp` field (not `ingested_at`)
- [ ] T042 Create src/dashboard/config.js (API URL, colors)

**Commit**: `feat(dashboard): Add static UI files with Chart.js visualizations`

### Dashboard Metrics Backend

- [ ] T043 Implement src/lambdas/dashboard/metrics.py
  - `calculate_sentiment_distribution(items)`
  - `calculate_tag_distribution(items)`
  - `get_recent_items(table, limit=20)` using `by_status` GSI
- [ ] T044 Write tests/unit/test_dashboard_metrics.py

**Commit**: `feat(dashboard): Add metrics aggregation functions with unit tests`

### Dashboard FastAPI App

- [ ] T045 Implement src/lambdas/dashboard/handler.py
  - FastAPI app with CORS
  - `GET /` - serve index.html
  - `GET /health` - health check with DynamoDB connectivity
  - `GET /api/metrics` - query `by_status` GSI, return aggregated metrics
  - `GET /api/stream` - SSE endpoint, poll every 5s
  - API key validation via `secrets.compare_digest()`
  - Mangum adapter for Lambda
- [ ] T046 Write tests/unit/test_dashboard_handler.py (TestClient)

**Commit**: `feat(dashboard): Add FastAPI endpoints with SSE and unit tests`

### Dashboard E2E Test

- [ ] T047 Write tests/integration/test_dashboard_e2e.py
  - Seed DynamoDB with test items
  - GET /api/metrics → verify response schema
  - GET /health → verify DynamoDB check
  - Test API key validation

**Commit**: `test(dashboard): Add E2E test for dashboard endpoints`

---

## Phase 6: Lambda Deployment Infrastructure

**Goal**: Terraform modules for Lambda functions
**Checkpoint**: All Lambdas deployable via Terraform

### Lambda Module

- [ ] T048 Create infrastructure/terraform/modules/lambda/main.tf
  - Reusable Lambda function resource
  - Environment variables from variables
  - IAM role attachment
  - CloudWatch log group with retention (30 days dev, 90 days prod)
- [ ] T049 Create infrastructure/terraform/modules/lambda/variables.tf
- [ ] T050 Create infrastructure/terraform/modules/lambda/outputs.tf

**Commit**: `infra: Add reusable Lambda Terraform module`

### Ingestion Lambda Terraform

- [ ] T051 Create Terraform for ingestion Lambda
  - 512MB memory, 60s timeout, reserved concurrency 1
  - Env vars: WATCH_TAGS, DYNAMODB_TABLE, SNS_TOPIC_ARN, NEWSAPI_SECRET_ARN, MODEL_VERSION
  - Attach ingestion IAM role from iam module

**Commit**: `infra(ingestion): Add Terraform for ingestion Lambda`

### Analysis Lambda Terraform

- [ ] T052 Create Terraform for analysis Lambda
  - 1024MB memory, 30s timeout, reserved concurrency 5
  - Lambda layer for DistilBERT model
  - SNS subscription to analysis topic
  - DLQ configuration
  - Env vars: DYNAMODB_TABLE, MODEL_VERSION

**Commit**: `infra(analysis): Add Terraform for analysis Lambda with SNS subscription`

### Dashboard Lambda Terraform

- [ ] T053 Create Terraform for dashboard Lambda
  - 512MB memory, 60s timeout, reserved concurrency 10
  - Function URL with CORS
  - Env vars: DYNAMODB_TABLE, DASHBOARD_API_KEY_SECRET_ARN

**Commit**: `infra(dashboard): Add Terraform for dashboard Lambda with Function URL`

---

## Phase 7: Full Pipeline Integration

**Goal**: Connect all components, enable EventBridge schedules
**Checkpoint**: Complete data flow from NewsAPI to Dashboard

### Enable EventBridge & SNS

- [ ] T054 Uncomment and configure SNS module in main.tf
- [ ] T055 Uncomment and configure IAM module in main.tf
- [ ] T056 Uncomment and configure EventBridge module in main.tf
- [ ] T057 Update outputs in main.tf

**Commit**: `infra: Enable SNS, IAM, and EventBridge modules`

### Full E2E Test

- [ ] T058 Write tests/e2e/test_full_pipeline.py
  - Deploy to dev environment
  - Trigger ingestion manually
  - Wait for analysis completion
  - Query dashboard API
  - Verify data flow end-to-end

**Commit**: `test: Add full pipeline E2E test`

---

## Phase 8: Deployment & Operations

**Goal**: Deployment scripts, blue/green, validation
**Checkpoint**: Can deploy safely to dev and prod

### Deployment Scripts

- [ ] T059 Create infrastructure/scripts/deploy.sh
  - Build Lambda packages
  - Upload to S3
  - Run Terraform apply
  - Verify deployment
- [ ] T060 Create infrastructure/scripts/rollback.sh
  - Roll back Lambda to previous version
  - Document in ON_CALL_SOP.md

**Commit**: `infra: Add deployment and rollback scripts`

### Demo Day Scripts

- [ ] T061 Create infrastructure/scripts/demo-setup.sh
  - Verify secrets exist
  - Trigger initial ingestion
  - Wait for data population
- [ ] T062 Create infrastructure/scripts/demo-validate.sh
  - Check all Lambdas deployed
  - Check DynamoDB has items
  - Check dashboard loads
  - Check alarms configured
- [ ] T063 Create infrastructure/scripts/demo-teardown.sh (optional cleanup)

**Commit**: `docs: Add demo day setup and validation scripts`

### Pre-Deploy Checklist

- [ ] T064 Create infrastructure/scripts/pre-deploy-checklist.sh
  - Verify secrets: `dev/sentiment-analyzer/newsapi`, `dev/sentiment-analyzer/dashboard-api-key`
  - Verify model layer uploaded
  - Verify all alarms exist (11 from monitoring module)
  - Check no active alarms firing

**Commit**: `infra: Add pre-deploy checklist script`

---

## Phase 9: Documentation & Polish

**Goal**: Complete documentation, final quality checks
**Checkpoint**: Ready for demo and handoff

### Architecture Documentation

- [ ] T065 Create docs/architecture.png (system diagram)
- [ ] T066 Update README.md with architecture diagram
- [ ] T067 Create DEPLOYMENT.md with:
  - Zero-downtime deployment process
  - Rollback procedures
  - Secret rotation process

**Commit**: `docs: Add architecture diagram and deployment documentation`

### Code Quality

- [ ] T068 Run black formatter on entire codebase
- [ ] T069 Run ruff linter and fix all issues
- [ ] T070 Add type hints to all public functions
- [ ] T071 Verify >80% test coverage (pytest --cov)

**Commit**: `chore: Final polish - formatting, linting, type hints`

### Demo Checklist

- [ ] T072 Create DEMO_CHECKLIST.md
  - 30 minutes before: verify alarms, check secrets, test dashboard
  - During demo: monitoring commands, troubleshooting
  - After demo: collect feedback, note issues

**Commit**: `docs: Add demo day checklist`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ──────────────────────────────────┐
                                                   │
Phase 2 (Shared Libraries) ◄──────────────────────┘
     │
     ├──► Phase 3 (Ingestion)
     │         │
     │         ▼
     ├──► Phase 4 (Analysis)
     │         │
     │         ▼
     └──► Phase 5 (Dashboard)
               │
               ▼
         Phase 6 (Lambda Terraform)
               │
               ▼
         Phase 7 (Integration)
               │
               ▼
         Phase 8 (Deployment)
               │
               ▼
         Phase 9 (Documentation)
```

### Pre-Existing Infrastructure

The following Terraform modules already exist and are ready to use:
- `modules/dynamodb` - Table with 3 GSIs ✅
- `modules/secrets` - NewsAPI + Dashboard API key ✅
- `modules/sns` - Analysis requests topic ✅
- `modules/iam` - Lambda execution roles ✅
- `modules/eventbridge` - Ingestion schedule ✅
- `modules/monitoring` - 11 CloudWatch alarms ✅

---

## Task Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1 | T001-T011 | Setup & CI/CD |
| 2 | T012-T023 | Shared Libraries |
| 3 | T024-T031 | Ingestion Lambda |
| 4 | T032-T038 | Analysis Lambda |
| 5 | T039-T047 | Dashboard Lambda |
| 6 | T048-T053 | Lambda Terraform |
| 7 | T054-T058 | Integration |
| 8 | T059-T064 | Deployment |
| 9 | T065-T072 | Documentation |

**Total Tasks**: 72
**Estimated Time**: 20-30 hours

---

## Notes

### Grey Area Safety

Each component handles missing dependencies gracefully:
- Ingestion → SNS: Log warning if topic doesn't exist, continue
- Analysis → DynamoDB: Handle old schema (sentiment field optional)
- Dashboard → DynamoDB: Default values for missing fields

### Existing Alarms (from modules/monitoring)

All 11 alarms map to ON_CALL_SOP.md scenarios:
- `lambda-ingestion-errors` (SC-03)
- `lambda-analysis-errors` (SC-04)
- `lambda-dashboard-errors` (SC-05)
- `analysis-latency-high` (SC-11)
- `dashboard-latency-high` (SC-12)
- `sns-delivery-failures` (SC-06)
- `newsapi-rate-limit` (SC-07)
- `no-new-items-1h` (SC-10)
- `dlq-depth-exceeded` (SC-09)
- Budget alarms (SC-08)

### Cost Estimate

- Dev environment: ~$2-5/month
- Prod environment: ~$5-10/month (same scale)

---

Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
