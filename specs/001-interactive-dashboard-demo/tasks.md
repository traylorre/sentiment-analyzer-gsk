# Tasks: Interactive Dashboard Demo

**Input**: Design documents from `/specs/001-interactive-dashboard-demo/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Testing Philosophy**:
- **MANDATORY**: Every component MUST have unit tests
- **E2E grows incrementally**: Start with single-component E2E, expand as components are added
- **Test-first commits**: Each implementation task includes unit tests in the same commit
- **CI/CD enforced**: Tests run on every commit, deployment blocked if tests fail

**Deployment Strategy**:
- **Dev environment**: Test all changes here first
- **Prod environment**: Promotes only after dev validates
- **Zero-downtime**: Blue/green Lambda deployments with graceful schema evolution
- **Grey area handling**: Components tolerate deployment ordering (either component can deploy first)

**Organization**: Tasks are atomic, standalone features with tests. Components implement in sequence so E2E test grows incrementally.

## Format: `[ID] [Story] Description`

- **[Story]**: Which functional area (US1, US2, US3, etc.)
- **[P]** removed: Single contributor, parallelism not needed
- Include exact file paths in descriptions

## Path Conventions

Per plan.md, this is a serverless project with structure:
- `src/lambdas/` - Lambda function handlers
- `src/dashboard/` - Dashboard UI files
- `src/lib/` - Shared libraries
- `infrastructure/terraform/` - IaC (dev/ and prod/ workspaces)
- `tests/` - Test files
- `.github/workflows/` - CI/CD pipelines

---

## Phase 1: Setup & CI/CD Foundation

**Purpose**: Project initialization, CI/CD pipelines, and environment scaffolding

**Checkpoint**: CI/CD runs tests on every commit, README shows pipeline status

### Project Structure

- [ ] T001 Create project directory structure per plan.md (src/, tests/, infrastructure/, .github/workflows/)
- [ ] T002 Initialize Python 3.11 project with requirements.txt (boto3==1.34.0, transformers==4.35.0, torch==2.1.0, fastapi==0.104.0, mangum==0.17.0, requests==2.31.0, python-json-logger==2.0.7)
- [ ] T003 Initialize requirements-dev.txt (pytest==7.4.3, moto==4.2.0, pytest-asyncio==0.21.1, pytest-cov==4.1.0, black==23.11.0, ruff==0.1.6)
- [ ] T004 Create .gitignore for Python (venv/, __pycache__/, *.pyc, .env, *.zip, .terraform/, terraform.tfstate*)
- [ ] T005 Create pytest.ini configuration (testpaths, python_files, coverage settings)

**Commit**: "chore: Initialize Python project structure and dependencies"

### CI/CD Pipelines

- [ ] T006 Create GitHub Actions workflow for unit tests in .github/workflows/test.yml (runs pytest on push/PR, Python 3.11, cov report)
- [ ] T007 Create GitHub Actions workflow for linting in .github/workflows/lint.yml (black, ruff checks)
- [ ] T008 Create GitHub Actions workflow for dev deployment in .github/workflows/deploy-dev.yml (terraform apply on dev workspace, triggered on main branch push)
- [ ] T009 Create GitHub Actions workflow for prod deployment in .github/workflows/deploy-prod.yml (terraform apply on prod workspace, manual approval required, only runs if dev is green)
- [ ] T010 Create GitHub Actions workflow for integration tests in .github/workflows/integration.yml (runs after dev deployment, uses dev env)

**Commit**: "ci: Add GitHub Actions workflows for test, lint, and deploy pipelines"

### README with Dynamic Status

- [ ] T011 Create README.md with project overview, pipeline status badges, quickstart link, and architecture diagram
  - Include badges: ![Tests](https://github.com/.../workflows/test.yml/badge.svg), ![Deploy Dev](https://github.com/.../workflows/deploy-dev.yml/badge.svg), ![Deploy Prod](https://github.com/.../workflows/deploy-prod.yml/badge.svg)
  - Link to specs/001-interactive-dashboard-demo/quickstart.md
  - Document dev/prod promotion workflow

**Commit**: "docs: Add README with CI/CD status badges and project overview"

---

## Phase 2: Infrastructure Foundation (Dev + Prod)

**Purpose**: Core infrastructure (DynamoDB, S3, IAM, Terraform workspaces) that blocks all application code

**Checkpoint**: Dev and Prod Terraform workspaces exist, DynamoDB tables deployed, CI/CD can deploy to both

### Terraform Multi-Environment Setup

- [ ] T012 Create Terraform backend configuration in infrastructure/terraform/backend.tf (S3 backend with workspace support)
- [ ] T013 Create Terraform variables in infrastructure/terraform/variables.tf (environment, aws_region, newsapi_secret_arn, watch_tags, model_version)
- [ ] T014 Create Terraform dev.tfvars and prod.tfvars with environment-specific values
- [ ] T015 Create Terraform main.tf that calls all modules with environment prefix
- [ ] T016 Initialize Terraform workspaces (dev and prod) in CI/CD deployment scripts

**Commit**: "infra: Configure Terraform backend and multi-environment workspaces"

### DynamoDB Schema (Backwards-Compatible)

- [ ] T017 Create DynamoDB table Terraform module in infrastructure/terraform/modules/dynamodb/main.tf (sentiment-items-{env}, PK: source_id, SK: ingested_at, GSIs: by_timestamp, by_model_version, on-demand billing, PITR enabled, encryption at rest)
- [ ] T018 Write unit tests for DynamoDB schema validation in tests/unit/test_dynamodb_schema.py (validate PK/SK, GSI structure, attributes)

**Commit**: "infra: Add DynamoDB table with GSIs and unit tests"

### Shared Libraries & Helpers

- [ ] T019 Implement shared DynamoDB helpers in src/lambdas/shared/dynamodb.py (parse_items, conditional_write, query_recent_items)
- [ ] T020 Write unit tests for DynamoDB helpers in tests/unit/test_dynamodb_helpers.py (test parse_items, test conditional_write with mock boto3)

**Commit**: "feat: Add DynamoDB helper library with unit tests"

- [ ] T021 Implement Secrets Manager helper in src/lambdas/shared/secrets.py (get_secret with caching)
- [ ] T022 Write unit tests for Secrets Manager in tests/unit/test_secrets.py (test get_secret with moto mock)

**Commit**: "feat: Add Secrets Manager helper with unit tests"

- [ ] T023 Implement data schemas in src/lambdas/shared/schemas.py (SentimentItem dataclass, validate_source_id, validate_score, validate_sentiment, validate_matched_tags)
- [ ] T024 Write unit tests for schemas in tests/unit/test_schemas.py (test all validation functions with valid/invalid inputs)

**Commit**: "feat: Add data validation schemas with unit tests"

- [ ] T025 Implement deduplication logic in src/lib/deduplication.py (generate_source_id with SHA256, content_hash)
- [ ] T026 Write unit tests for deduplication in tests/unit/test_deduplication.py (test deterministic source_id, test hash stability)

**Commit**: "feat: Add deduplication library with unit tests"

- [ ] T027 Implement CloudWatch metrics helper in src/lib/utils.py (emit_metric, log_structured with JSON formatter)
- [ ] T028 Write unit tests for utils in tests/unit/test_utils.py (test metric emission, test structured logging format)

**Commit**: "feat: Add CloudWatch utilities with unit tests"

### AWS Secrets & Model Artifacts

- [ ] T029 Store NewsAPI key in AWS Secrets Manager for dev environment (sentiment-analyzer/newsapi-dev)
- [ ] T030 Store NewsAPI key in AWS Secrets Manager for prod environment (sentiment-analyzer/newsapi-prod)
- [ ] T031 Create S3 bucket for model artifacts in infrastructure/terraform/modules/s3/models.tf (sentiment-models-{env}-{account_id}, versioning enabled)

**Commit**: "infra: Add Secrets Manager entries and S3 model bucket"

- [ ] T032 Create model layer build script in infrastructure/scripts/build-model-layer.sh (download DistilBERT, package in layer/python/model/, zip, upload to S3)
- [ ] T033 Build and upload HuggingFace DistilBERT model layer to S3 for dev (sentiment-models-dev-{account_id}/layers/distilbert-v1.0.0.zip)
- [ ] T034 Build and upload model layer to S3 for prod (sentiment-models-prod-{account_id}/layers/distilbert-v1.0.0.zip)

**Commit**: "infra: Add model layer build script and upload to S3"

- [ ] T035 Create Terraform for Lambda layer in infrastructure/terraform/modules/lambda/layer.tf (publish distilbert-v1.0.0 layer from S3, separate layers for dev/prod)

**Commit**: "infra: Add Lambda layer Terraform module for DistilBERT"

### Shared IAM Roles

- [ ] T036 Create shared Lambda IAM role module in infrastructure/terraform/modules/lambda/iam.tf (base execution role, DynamoDB read/write policy, Secrets Manager read policy, CloudWatch logs policy)

**Commit**: "infra: Add shared Lambda IAM roles and policies"

**Checkpoint**: Terraform can deploy DynamoDB + S3 + IAM to dev and prod. Shared libraries have 100% test coverage.

---

## Phase 3: Data Ingestion (US1 - Sequential Implementation with Growing E2E)

**Goal**: Fetch items from NewsAPI, deduplicate, store in DynamoDB, publish to SNS

**Testing Strategy**:
1. T037-T042: Upstream (NewsAPI fetch) with unit tests + E2E stub
2. T043-T048: Core handler (dedup + DynamoDB) with unit tests + E2E extension
3. T049-T053: Downstream (SNS publish) with unit tests + E2E complete

**Grey Area Handling**: Ingestion Lambda handles missing SNS topic gracefully (logs warning, continues processing)

### Part 1: Upstream Ingestion (NewsAPI Fetch)

- [ ] T037 [US1] Create base adapter interface in src/lambdas/ingestion/adapters/base.py (AbstractAdapter with fetch_items abstract method, rate_limit_backoff)
- [ ] T038 [US1] Write unit tests for base adapter in tests/unit/test_base_adapter.py (test abstract method enforcement)

**Commit**: "feat(ingestion): Add base adapter interface with unit tests"

- [ ] T039 [US1] Implement NewsAPI adapter in src/lambdas/ingestion/adapters/newsapi.py (fetch_articles, parse response, handle 429 rate limits with exponential backoff, circuit breaker after 3 failures)
- [ ] T040 [US1] Write unit tests for NewsAPI adapter in tests/unit/test_newsapi_adapter.py (test fetch with mocked requests, test rate limit backoff, test circuit breaker, test malformed response)

**Commit**: "feat(ingestion): Add NewsAPI adapter with unit tests and rate limiting"

- [ ] T041 [US1] Create ingestion config module in src/lambdas/ingestion/config.py (parse WATCH_TAGS env var, validate_tag_format, max 5 tags validation, sanitize input)
- [ ] T042 [US1] Write unit tests for config in tests/unit/test_ingestion_config.py (test tag parsing, test validation, test edge cases: empty, too many, control chars)

**Commit**: "feat(ingestion): Add watch tags config with validation and unit tests"

- [ ] T043 [US1] Create E2E test stub for ingestion in tests/integration/test_ingestion_e2e.py (setup: mock NewsAPI + DynamoDB, test: invoke handler → verify fetch called)

**Commit**: "test(ingestion): Add E2E test stub for upstream NewsAPI fetch"

### Part 2: Core Handler (Deduplication + DynamoDB Write)

- [ ] T044 [US1] Implement ingestion Lambda handler (upstream only) in src/lambdas/ingestion/handler.lambda_handler (EventBridge trigger, fetch from NewsAPI, iterate articles, generate source_id, log structured results)
- [ ] T045 [US1] Write unit tests for upstream handler in tests/unit/test_ingestion_handler_upstream.py (test EventBridge event parsing, test NewsAPI adapter call, test error handling)

**Commit**: "feat(ingestion): Add Lambda handler upstream (NewsAPI fetch) with unit tests"

- [ ] T046 [US1] Extend ingestion handler with deduplication and DynamoDB write in src/lambdas/ingestion/handler.py (conditional_write for each item, handle duplicates gracefully, emit dedup metrics)
- [ ] T047 [US1] Write unit tests for DynamoDB write logic in tests/unit/test_ingestion_handler_dynamodb.py (test conditional write success, test duplicate handling, test DynamoDB error handling with moto)

**Commit**: "feat(ingestion): Add deduplication and DynamoDB write with unit tests"

- [ ] T048 [US1] Extend E2E test to verify DynamoDB inserts in tests/integration/test_ingestion_e2e.py (assert items in DynamoDB, assert deduplication works, assert schema correctness)

**Commit**: "test(ingestion): Extend E2E to verify DynamoDB writes"

### Part 3: Downstream Propagation (SNS Publish)

- [ ] T049 [US1] Extend ingestion handler with SNS publish in src/lambdas/ingestion/handler.py (publish message to SNS topic for each new item, include source_id + text + metadata, handle missing topic gracefully with try/except + log warning)
- [ ] T050 [US1] Write unit tests for SNS publish in tests/unit/test_ingestion_handler_sns.py (test SNS message format, test publish success with moto, test missing topic handling)

**Commit**: "feat(ingestion): Add SNS publish for downstream analysis with unit tests"

- [ ] T051 [US1] Add final error handling and metrics to ingestion handler in src/lambdas/ingestion/handler.py (emit CloudWatch metrics: articles_fetched, new_items, duplicates_skipped, errors, execution_time_ms; structured logging for all operations)
- [ ] T052 [US1] Write unit tests for metrics and logging in tests/unit/test_ingestion_metrics.py (test metric emission, test log structure, test error scenarios)

**Commit**: "feat(ingestion): Add CloudWatch metrics and structured logging with unit tests"

- [ ] T053 [US1] Complete E2E test with SNS verification in tests/integration/test_ingestion_e2e.py (assert SNS messages published, assert message format correct)

**Commit**: "test(ingestion): Complete E2E test with SNS publish verification"

### Infrastructure Deployment

- [ ] T054 [US1] Create Terraform for SNS topic in infrastructure/terraform/modules/sns/analysis_requests.tf (topic: sentiment-analysis-requests-{env}, DLQ for failed deliveries)
- [ ] T055 [US1] Create Terraform for ingestion Lambda in infrastructure/terraform/modules/lambda/ingestion.tf (function with 512MB memory, EventBridge rule every 10 minutes, env vars: WATCH_TAGS, DYNAMODB_TABLE, SNS_TOPIC_ARN, NEWSAPI_SECRET_ARN, timeout 60s, IAM permissions)
- [ ] T056 [US1] Create Terraform for EventBridge schedule in infrastructure/terraform/modules/eventbridge/ingestion_schedule.tf (rule: every 10 minutes, target: ingestion Lambda with retry policy)
- [ ] T057 [US1] Add CloudWatch log group and alarms in infrastructure/terraform/modules/lambda/ingestion.tf (log retention 7 days, alarms: high error rate >5 in 10min, rate limit hit >0, execution timeout >50s)
- [ ] T058 [US1] Create Terraform outputs in infrastructure/terraform/outputs.tf (ingestion_lambda_arn, sns_topic_arn)

**Commit**: "infra(ingestion): Add Terraform for Lambda, SNS, EventBridge, and CloudWatch alarms"

**Checkpoint**: Ingestion Lambda deployed to dev. E2E test passes. Items fetched, deduped, stored, published to SNS.

---

## Phase 4: Sentiment Analysis (US2 - Sequential with E2E Growth)

**Goal**: Consume SNS messages, run DistilBERT inference, update DynamoDB with sentiment

**Testing Strategy**:
1. T059-T064: Sentiment inference logic with unit tests
2. T065-T070: Lambda handler with DynamoDB updates and unit tests
3. T071-T073: Infrastructure and E2E extension

**Grey Area Handling**: Analysis Lambda handles old/new DynamoDB schema (sentiment field optional for backwards compat during deployment)

### Part 1: Sentiment Inference Engine

- [ ] T059 [US2] Implement model loading in src/lambdas/analysis/sentiment.py (load_model function with global caching, load from /opt/model path, return HF pipeline)
- [ ] T060 [US2] Write unit tests for model loading in tests/unit/test_sentiment_model.py (test caching behavior, test model path configuration)

**Commit**: "feat(analysis): Add DistilBERT model loading with caching and unit tests"

- [ ] T061 [US2] Implement sentiment inference in src/lambdas/analysis/sentiment.py (analyze_sentiment function, truncate to 512 tokens, run inference, map POSITIVE/NEGATIVE to schema, handle neutral via <0.6 threshold)
- [ ] T062 [US2] Write unit tests for sentiment inference in tests/unit/test_sentiment_inference.py (test positive/negative/neutral classification, test threshold boundary, test truncation, test error handling with malformed text)

**Commit**: "feat(analysis): Add sentiment inference with neutral detection and unit tests"

- [ ] T063 [US2] Create analysis models config in src/lambdas/analysis/models.py (MODEL_PATH constant, NEUTRAL_THRESHOLD=0.6, MODEL_VERSION)
- [ ] T064 [US2] Write unit tests for models config in tests/unit/test_analysis_models.py (test config values, test version string format)

**Commit**: "feat(analysis): Add analysis configuration with unit tests"

### Part 2: Lambda Handler (SNS → Inference → DynamoDB)

- [ ] T065 [US2] Implement analysis Lambda handler (SNS trigger) in src/lambdas/analysis/handler.lambda_handler (parse SNS message, extract source_id + text, call analyze_sentiment)
- [ ] T066 [US2] Write unit tests for handler SNS parsing in tests/unit/test_analysis_handler_sns.py (test SNS event parsing, test message extraction, test malformed message handling)

**Commit**: "feat(analysis): Add Lambda handler for SNS trigger with unit tests"

- [ ] T067 [US2] Extend handler with DynamoDB update in src/lambdas/analysis/handler.py (update_item with sentiment + score + model_version, use conditional update to prevent overwriting if already analyzed, handle missing source_id gracefully for grey area)
- [ ] T068 [US2] Write unit tests for DynamoDB update in tests/unit/test_analysis_handler_dynamodb.py (test update success with moto, test conditional check, test missing source_id, test schema compatibility: old items missing sentiment field)

**Commit**: "feat(analysis): Add DynamoDB update with schema compatibility and unit tests"

- [ ] T069 [US2] Add metrics and error handling to analysis handler in src/lambdas/analysis/handler.py (emit metrics: analysis_count, positive/neutral/negative counts, inference_latency_ms, errors; structured logging; retry logic for transient errors)
- [ ] T070 [US2] Write unit tests for metrics and errors in tests/unit/test_analysis_metrics.py (test metric emission, test error handling, test retry logic)

**Commit**: "feat(analysis): Add CloudWatch metrics and error handling with unit tests"

### Infrastructure & E2E

- [ ] T071 [US2] Create Terraform for analysis Lambda in infrastructure/terraform/modules/lambda/analysis.tf (function with 1024MB memory, timeout 30s, Lambda layer attachment, SNS subscription, DLQ for failures, env vars: DYNAMODB_TABLE, MODEL_PATH, MODEL_VERSION, IAM permissions)
- [ ] T072 [US2] Add CloudWatch alarms for analysis Lambda in infrastructure/terraform/modules/lambda/analysis.tf (alarms: high latency >500ms P95, errors >5 in 10min, DLQ depth >10, neutral_rate >50% for model drift)

**Commit**: "infra(analysis): Add Terraform for Lambda with SNS subscription and alarms"

- [ ] T073 [US2] Extend E2E test to include analysis in tests/integration/test_full_pipeline_e2e.py (trigger ingestion → wait for SNS → verify DynamoDB updated with sentiment, assert positive/neutral/negative values, assert score range 0-1)

**Commit**: "test(analysis): Extend E2E test to verify end-to-end sentiment analysis"

**Checkpoint**: Analysis Lambda deployed to dev. Full ingestion → analysis pipeline works E2E. Sentiment scores in DynamoDB.

---

## Phase 5: Dashboard (US3 - Sequential with E2E Completion)

**Goal**: Serve live dashboard with FastAPI + SSE, display metrics and recent items

**Testing Strategy**:
1. T074-T078: Static UI files (HTML/CSS/JS) - no tests needed
2. T079-T084: Metrics aggregation backend with unit tests
3. T085-T089: FastAPI endpoints with unit tests
4. T090-T093: Infrastructure and E2E completion

**Grey Area Handling**: Dashboard handles missing DynamoDB fields gracefully (defaults for sentiment if not present)

### Part 1: Static Dashboard UI

- [ ] T074 [US3] Create dashboard HTML in src/dashboard/index.html (layout with metrics cards for total/positive/neutral/negative, Chart.js canvas for pie + bar charts, table for recent items)
- [ ] T075 [US3] Create dashboard CSS in src/dashboard/styles.css (grid layout, metric card styling, chart containers, responsive design, sentiment color coding)
- [ ] T076 [US3] Create dashboard JavaScript in src/dashboard/app.js (Chart.js initialization, fetch /api/metrics, update charts, connect to /api/stream SSE, handle SSE events, update table with new items)
- [ ] T077 [US3] Create dashboard config in src/dashboard/config.js (API base URL from env, update intervals, chart colors)
- [ ] T078 [US3] Create static file serving helper in src/dashboard/static.py (read index.html from filesystem, cache in memory)

**Commit**: "feat(dashboard): Add static UI files (HTML/CSS/JS) and file server"

### Part 2: Metrics Aggregation Backend

- [ ] T079 [US3] Implement metrics aggregation in src/lambdas/dashboard/metrics.py (calculate_sentiment_distribution, calculate_tag_distribution, calculate_ingestion_rate, get_recent_items with DynamoDB query)
- [ ] T080 [US3] Write unit tests for metrics in tests/unit/test_dashboard_metrics.py (test sentiment distribution calc, test tag aggregation, test ingestion rate, test recent items with moto DynamoDB)

**Commit**: "feat(dashboard): Add metrics aggregation functions with unit tests"

- [ ] T081 [US3] Implement SSE delta calculator in src/lambdas/dashboard/metrics.py (calculate_metrics_delta for incremental updates, track last_check timestamp)
- [ ] T082 [US3] Write unit tests for SSE delta in tests/unit/test_dashboard_sse.py (test delta calculation, test timestamp tracking, test empty delta)

**Commit**: "feat(dashboard): Add SSE delta calculator with unit tests"

### Part 3: FastAPI Endpoints

- [ ] T083 [US3] Create FastAPI app in src/lambdas/dashboard/handler.py (app initialization, serve static HTML at /, CORS configuration)
- [ ] T084 [US3] Write unit tests for FastAPI app initialization in tests/unit/test_dashboard_app.py (test CORS settings, test static file serving)

**Commit**: "feat(dashboard): Add FastAPI app initialization with unit tests"

- [ ] T085 [US3] Implement /api/metrics endpoint in src/lambdas/dashboard/handler.py (query DynamoDB, call metrics functions, return JSON with summary + distributions + recent items, handle missing fields gracefully for grey area)
- [ ] T086 [US3] Write unit tests for /api/metrics in tests/unit/test_dashboard_metrics_endpoint.py (test response schema, test DynamoDB query, test missing field handling with FastAPI TestClient)

**Commit**: "feat(dashboard): Add /api/metrics endpoint with unit tests"

- [ ] T087 [US3] Implement /api/stream SSE endpoint in src/lambdas/dashboard/handler.py (async generator, poll DynamoDB every 5s, emit new items as SSE events, handle client disconnect, 15min timeout)
- [ ] T088 [US3] Write unit tests for /api/stream in tests/unit/test_dashboard_sse_endpoint.py (test SSE event format, test polling interval, test client disconnect handling)

**Commit**: "feat(dashboard): Add /api/stream SSE endpoint with unit tests"

- [ ] T089 [US3] Add Mangum adapter for Lambda in src/lambdas/dashboard/handler.py (lambda_handler = Mangum(app, lifespan="off"))

**Commit**: "feat(dashboard): Add Mangum Lambda adapter"

### Infrastructure & E2E Completion

- [ ] T090 [US3] Create Terraform for dashboard Lambda in infrastructure/terraform/modules/lambda/dashboard.tf (function with 512MB memory, timeout 60s, Function URL with CORS, env vars: DYNAMODB_TABLE, IAM permissions for DynamoDB read-only)
- [ ] T091 [US3] Add CloudWatch alarms for dashboard in infrastructure/terraform/modules/lambda/dashboard.tf (alarms: error rate >10 in 5min, metrics API latency >1000ms P95)
- [ ] T092 [US3] Create Terraform output for dashboard URL in infrastructure/terraform/outputs.tf (dashboard_url from Function URL)

**Commit**: "infra(dashboard): Add Terraform for Lambda with Function URL and alarms"

- [ ] T093 [US3] Complete E2E test with dashboard verification in tests/integration/test_full_pipeline_e2e.py (HTTP GET /api/metrics → assert summary values, assert recent items present, test /api/stream SSE → assert events received within 10s)

**Commit**: "test(dashboard): Complete E2E test with full pipeline validation"

**Checkpoint**: Dashboard deployed to dev. Full demo flow works: Ingestion → Analysis → Dashboard displays results with live updates.

---

## Phase 6: Deployment Strategy & Zero-Downtime

**Goal**: Ensure dev/prod promotion with zero downtime, schema compatibility, graceful rollouts

**Deployment Order** (enforced in CI/CD):
1. DynamoDB schema changes (add attributes, never remove)
2. SNS topic (if new)
3. Lambda layers (new versions)
4. Downstream Lambdas first (Analysis, Dashboard)
5. Upstream Lambdas last (Ingestion)
6. Clean up old Lambda versions after 24h

### Blue/Green Lambda Deployment

- [ ] T094 Create Lambda alias module in infrastructure/terraform/modules/lambda/alias.tf (blue and green aliases for each Lambda, traffic shifting configuration)
- [ ] T095 Update all Lambda modules to use aliases for EventBridge/SNS triggers (ingestion, analysis, dashboard)
- [ ] T096 Create deployment script for blue/green in infrastructure/scripts/deploy-lambda-blue-green.sh (deploy new version, update green alias, shift traffic 10%/50%/100%, monitor errors, rollback if >5% error rate)

**Commit**: "infra: Add blue/green Lambda deployment with traffic shifting"

### Schema Compatibility Validation

- [ ] T097 Create schema compatibility checker in tests/schema/test_backwards_compatibility.py (verify new schema is superset of old, no required fields removed, test old Lambda can read new DynamoDB items)
- [ ] T098 Add schema check to CI pipeline in .github/workflows/schema-check.yml (runs on PR, blocks merge if incompatible)

**Commit**: "test: Add schema backwards compatibility validation"

### Dev → Prod Promotion

- [ ] T099 Update prod deployment workflow in .github/workflows/deploy-prod.yml (require manual approval, check dev deployment status is green, check dev integration tests passed, enforce blue/green rollout)
- [ ] T100 Add deployment checklist in infrastructure/scripts/pre-deploy-checklist.sh (verify secrets exist, verify model layer uploaded, verify alarms configured, check dev metrics for anomalies)

**Commit**: "ci: Add prod promotion workflow with approval gates"

---

## Phase 7: Observability & Monitoring

**Goal**: Full observability stack for demo monitoring and troubleshooting

- [ ] T101 [US5] Create CloudWatch dashboard JSON in infrastructure/terraform/cloudwatch_dashboard.tf (widgets: ingestion rate, sentiment distribution, error rates, latency P50/P90/P99, Lambda invocations, DynamoDB throttles)
- [ ] T102 [US5] Create SNS topic for alarms in infrastructure/terraform/modules/sns/alarms.tf (topic: cloudwatch-alarms-{env}, email subscription)
- [ ] T103 [US5] Update all CloudWatch alarms to publish to SNS topic (ingestion, analysis, dashboard alarms)
- [ ] T104 [US5] Create CloudWatch Logs Insights queries in infrastructure/terraform/logs_insights_queries.tf (saved queries: error logs, slow requests, dedup stats, sentiment distribution)

**Commit**: "feat(observability): Add CloudWatch dashboard, alarm SNS topic, and Logs Insights queries"

- [ ] T105 [US5] Create demo monitoring script in infrastructure/scripts/monitor-demo.sh (poll CloudWatch metrics, display ingestion rate, sentiment counts, error rates, refresh every 5s)

**Commit**: "feat(observability): Add demo monitoring script for live metrics"

---

## Phase 8: Documentation & Demo Readiness

**Goal**: Complete documentation, demo scripts, validation tooling

### Demo Day Scripts

- [ ] T106 Create demo setup script in infrastructure/scripts/demo-setup.sh (update watch tags via AWS CLI, trigger manual ingestion, verify dashboard accessible, seed initial data if needed)
- [ ] T107 Create demo validation script in infrastructure/scripts/demo-validate.sh (check secrets exist, check Lambdas deployed, check DynamoDB has items, check dashboard loads, check SSE connection works)
- [ ] T108 Create demo teardown script in infrastructure/scripts/demo-teardown.sh (optional: clear DynamoDB items for fresh demo)

**Commit**: "docs: Add demo day setup, validation, and teardown scripts"

### Deployment Documentation

- [ ] T109 Update quickstart.md with dev/prod deployment instructions (Terraform workspace commands, CI/CD pipeline triggers, blue/green rollout process)
- [ ] T110 Create DEPLOYMENT.md with zero-downtime strategy (deployment order, rollback procedures, schema evolution guidelines, troubleshooting common issues)
- [ ] T111 Create ARCHITECTURE.md with system diagram (EventBridge → Ingestion → SNS → Analysis → DynamoDB → Dashboard, include grey areas and graceful degradation)

**Commit**: "docs: Add deployment and architecture documentation"

### Final Validation

- [ ] T112 Run full quickstart.md end-to-end on clean dev environment (deploy from scratch, verify demo flow, document any issues)
- [ ] T113 Run full quickstart.md end-to-end on clean prod environment (requires manual approval, verify production deployment)
- [ ] T114 Create demo day checklist in specs/001-interactive-dashboard-demo/DEMO_CHECKLIST.md (30 min before, during demo, post-demo steps)

**Commit**: "docs: Add final validation results and demo day checklist"

---

## Phase 9: Polish & Refinement

**Goal**: Code quality, additional tests, performance optimization

- [ ] T115 Run black formatter on entire codebase (src/, tests/)
- [ ] T116 Run ruff linter and fix all issues
- [ ] T117 Achieve 90%+ test coverage across all modules (run pytest --cov, add missing tests)
- [ ] T118 Add type hints to all public functions (use mypy for validation)
- [ ] T119 Create architecture diagram (PNG) in docs/architecture.png (EventBridge → Lambda → SNS → Lambda → DynamoDB → Lambda/Dashboard)
- [ ] T120 Update README.md with final architecture diagram and demo video link placeholder

**Commit**: "chore: Final polish - formatting, linting, type hints, docs"

---

## Dependencies & Execution Order

### Phase Dependencies (STRICT - Must follow sequence)

1. **Phase 1 (Setup & CI/CD)**: START HERE - No dependencies
2. **Phase 2 (Infrastructure)**: After Phase 1 complete
3. **Phase 3 (Ingestion)**: After Phase 2 complete
4. **Phase 4 (Analysis)**: After Phase 3 complete (needs SNS topic)
5. **Phase 5 (Dashboard)**: After Phase 4 complete (needs sentiment data)
6. **Phase 6 (Deployment)**: After Phase 5 complete
7. **Phase 7 (Observability)**: After Phase 5 complete (can overlap with Phase 6)
8. **Phase 8 (Documentation)**: After Phase 7 complete
9. **Phase 9 (Polish)**: After Phase 8 complete

### Within Each Component (US1, US2, US3)

**STRICT ORDER**: Upstream → Core → Downstream (with tests in same commit)

**Example (Ingestion)**:
1. T037-T043: Upstream (NewsAPI) + unit tests + E2E stub
2. T044-T048: Core (handler + DynamoDB) + unit tests + E2E extension
3. T049-T053: Downstream (SNS) + unit tests + E2E complete
4. T054-T058: Infrastructure deployment

**Grey Area Safety**: Each part handles missing downstream gracefully

### E2E Test Growth Pattern

```
T043: E2E stub (NewsAPI fetch)
       ↓
T048: E2E extends (+ DynamoDB writes)
       ↓
T053: E2E extends (+ SNS publish)
       ↓
T073: E2E extends (+ Analysis)
       ↓
T093: E2E complete (+ Dashboard)
```

### CI/CD Enforcement

- **Every commit**: Unit tests run (T006)
- **Every commit**: Linting runs (T007)
- **Main branch push**: Deploy to dev (T008)
- **After dev deploy**: Integration tests run (T010)
- **Manual approval**: Deploy to prod (T009, only if dev green)

---

## Implementation Strategy

### MVP Timeline (Phases 1-5 only)

**Goal**: Working demo end-to-end in dev environment

- **Phase 1 (Setup)**: 2-3 hours (CI/CD setup, README)
- **Phase 2 (Infrastructure)**: 3-4 hours (Terraform, libraries, 30-45 min model download)
- **Phase 3 (Ingestion)**: 4-5 hours (3 parts × ~1.5h each)
- **Phase 4 (Analysis)**: 4-5 hours (2 parts × ~2h each)
- **Phase 5 (Dashboard)**: 5-6 hours (3 parts × ~2h each)

**Total MVP**: ~18-23 hours (2-3 days solo developer)

### Full Feature Timeline (All Phases)

- **MVP (Phases 1-5)**: 18-23 hours
- **Phase 6 (Deployment)**: 3-4 hours
- **Phase 7 (Observability)**: 2-3 hours
- **Phase 8 (Documentation)**: 2-3 hours
- **Phase 9 (Polish)**: 2-3 hours

**Total Full Feature**: ~27-36 hours (3-5 days solo developer)

### Commit Discipline

**MANDATORY**: Each task = 1 commit with unit tests

**Format**:
```
feat(component): Description

- Implementation of X
- Unit tests for X (100% coverage of new code)
- E2E test extension (if applicable)

Refs: T###
```

**CI/CD Gates**:
- Tests must pass before merge
- Coverage must not decrease
- Linting must pass
- Schema check must pass (if DynamoDB changes)

---

## Notes

**Deployment Safety**:
- DynamoDB schema changes are backwards-compatible (add only, never remove)
- Lambdas handle missing fields gracefully (defaults, optional checks)
- Blue/green deployment minimizes risk (rollback in <1 min)
- Dev environment validates before prod promotion

**Testing Philosophy**:
- Unit tests in same commit as implementation (NOT separate)
- E2E test grows incrementally (NOT big bang at end)
- Integration tests run in dev environment after deployment
- 90%+ coverage target across all modules

**Time Estimates**:
- T032-T034 (model download): 30-45 minutes (large file)
- Each Lambda component: 4-6 hours (upstream + core + downstream + tests)
- Infrastructure per component: 1-2 hours
- Documentation: 2-3 hours total

**Grey Areas** (graceful degradation during deployment):
- Ingestion → SNS: Handle missing topic (log warning, continue)
- Analysis → DynamoDB: Handle old schema (sentiment optional)
- Dashboard → DynamoDB: Handle missing fields (default values)

**Cost**: $3.85-7.85/month for dev, ~$5-10/month for prod (similar scale)

---

## Task Count Summary

- **Total Tasks**: 120
- **Phase 1 (Setup & CI/CD)**: 11 tasks
- **Phase 2 (Infrastructure)**: 25 tasks
- **Phase 3 (Ingestion US1)**: 22 tasks
- **Phase 4 (Analysis US2)**: 15 tasks
- **Phase 5 (Dashboard US3)**: 21 tasks
- **Phase 6 (Deployment)**: 7 tasks
- **Phase 7 (Observability)**: 5 tasks
- **Phase 8 (Documentation)**: 8 tasks
- **Phase 9 (Polish)**: 6 tasks

**MVP scope (Phases 1-5)**: 94 tasks (~18-23 hours)
**Full feature (All phases)**: 120 tasks (~27-36 hours)

**Test Coverage**:
- Unit tests: ~40 tasks (every implementation has tests)
- Integration tests: 5 tasks (E2E growth pattern)
- Schema validation: 1 task
- Total test tasks: ~46 (38% of all tasks)
