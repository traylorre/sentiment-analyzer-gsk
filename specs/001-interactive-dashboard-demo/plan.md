# Implementation Plan: Interactive Dashboard Demo

**Branch**: `001-interactive-dashboard-demo` | **Date**: 2025-11-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-interactive-dashboard-demo/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a demonstrable, interactive sentiment analysis system where stakeholders provide 5 custom tags, then watch real-time data ingestion and sentiment analysis results in a live dashboard. This proves the end-to-end architecture works with engaging UX rather than toy examples. Uses AWS Lambda for compute, DynamoDB for storage, and a live-updating dashboard showing ingestion rate, sentiment distribution, and per-tag matches.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**:
- AWS SDK (boto3) for Lambda, DynamoDB, Secrets Manager
- NEEDS CLARIFICATION: Sentiment model choice (OpenAI API vs HuggingFace transformers)
- NEEDS CLARIFICATION: Data source API (NewsAPI vs Twitter API v2)
- NEEDS CLARIFICATION: Dashboard framework (S3-hosted static HTML + Chart.js vs Lambda web app)

**Storage**: DynamoDB (on-demand capacity mode)
**Testing**: pytest for unit tests, moto for AWS service mocking
**Target Platform**: AWS Lambda (serverless compute), S3 (dashboard hosting or artifacts)
**Project Type**: Serverless cloud application (event-driven)
**Performance Goals**:
- Dashboard update latency ≤ 10 seconds from item ingestion
- Sentiment inference ≤ 2 seconds per item
- Support 5 concurrent watch tags with ~100 items/hour ingestion rate (demo scale)

**Constraints**:
- Demo-optimized cost (on-demand billing, minimal always-on infrastructure)
- Real-time UX requirement (no batch-only processing)
- Single data source initially (expandable architecture)

**Scale/Scope**:
- Demo scale: 5 watch tags, ~100-500 items/hour, 1-5 concurrent viewers
- Storage: ~10k items in DynamoDB for demo period
- Lambda concurrency: ≤ 10 concurrent executions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Alignment with Constitution

✅ **Functional Requirements** (Minimal compliance - Demo 1 subset):
- ✅ Ingest text from external publishing endpoints (single source for demo)
- ✅ Support pluggable adapters (architecture supports, will implement one initially)
- ⚠️ **DEFERRED**: Near-real-time ingestion (polling only for demo, no webhooks yet)
- ✅ Deduplication by stable ID
- ✅ Return sentiment result (positive/neutral/negative + score 0-1)
- ⚠️ **SIMPLIFIED**: Admin API to add/remove sources (manual config for demo, API in later phase)

✅ **Non-Functional Requirements**:
- ⚠️ **DEFERRED**: 99.5% SLA (demo environment, no formal SLA)
- ✅ P90 latency ≤ 500ms (target: ≤ 2s for inference, well under requirement)
- ⚠️ **DEFERRED**: Auto-scaling (manual concurrency limits for demo, auto-scaling in Demo 3)

✅ **Security & Access Control** (Minimal compliance):
- ⚠️ **SIMPLIFIED**: Auth for admin endpoints (API keys or skip for demo, full auth later)
- ✅ Secrets in managed service (AWS Secrets Manager)
- ✅ TLS for external calls (HTTPS enforced)
- ✅ SQL injection prevention (DynamoDB with parameterized expressions, no SQL)

✅ **Data & Model Requirements**:
- ✅ Output schema matches minimal spec
- ✅ No full raw text persisted (snippet only, ≤200 chars)
- ✅ Model versioning tracked

✅ **Deployment Requirements**:
- ✅ Serverless (Lambda + DynamoDB)
- ⚠️ **SIMPLIFIED**: IaC (basic Terraform, defer TFC integration to later)
- ✅ Health checks (Lambda built-in health)

✅ **Observability & Monitoring**:
- ✅ Structured logs (CloudWatch)
- ✅ Metrics (request_count, error_count, latency)
- ⚠️ **PARTIAL**: Dashboard (demo dashboard, full features in later phase)

✅ **Dashboard & Public Metrics**:
- ✅ Time-series charts for ingestion, errors, latency
- ✅ Watch filters (5 tags, immediate update)
- ⚠️ **SIMPLIFIED**: Access control (public or simple API key for demo)

✅ **Testing & Validation**:
- ✅ Unit tests planned
- ✅ Integration test planned
- ⚠️ **DEFERRED**: Model eval metrics (use pre-trained model, eval in later phase)

### Gate Decision: **PASS with Documented Deferrals**

**Rationale**: This is explicitly Demo 1 of a multi-phase implementation. The constitution supports progressive delivery. Critical security fundamentals (TLS, secrets management, parameterized queries) are maintained. Deferred items (full auth, SLA, auto-scaling, TFC) are roadmapped for Demos 2 and 3.

### Complexity Tracking

No violations requiring justification. All simplifications are temporary and support the demo-first delivery strategy approved by stakeholder.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Serverless + Dashboard hybrid structure
src/
├── lambdas/
│   ├── ingestion/
│   │   ├── handler.py          # EventBridge scheduled ingestion
│   │   ├── adapters/
│   │   │   ├── base.py
│   │   │   ├── newsapi.py      # NewsAPI adapter (demo)
│   │   │   └── twitter.py      # (future)
│   │   └── config.py
│   ├── analysis/
│   │   ├── handler.py          # DynamoDB stream trigger or direct invoke
│   │   ├── sentiment.py        # Sentiment inference logic
│   │   └── models.py
│   └── shared/
│       ├── dynamodb.py         # DynamoDB helpers
│       ├── secrets.py          # Secrets Manager integration
│       └── schemas.py          # Data models
├── dashboard/
│   ├── index.html              # S3-hosted dashboard UI
│   ├── app.js                  # Chart.js + AWS SDK queries
│   ├── styles.css
│   └── config.js               # API endpoints, region config
└── lib/
    ├── deduplication.py        # Content hashing logic
    └── utils.py

infrastructure/
├── terraform/
│   ├── main.tf                 # DynamoDB, Lambda, IAM, EventBridge
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── lambda/
│       ├── dynamodb/
│       └── s3_dashboard/
└── scripts/
    ├── deploy.sh
    └── seed_data.py            # Optional demo seed script

tests/
├── unit/
│   ├── test_adapters.py
│   ├── test_sentiment.py
│   └── test_deduplication.py
├── integration/
│   ├── test_ingestion_flow.py
│   └── test_dashboard_query.py
└── fixtures/
    └── sample_items.json
```

**Structure Decision**: Serverless-first with separate lambda handlers, shared libraries, and an S3-hosted static dashboard. Terraform IaC in `infrastructure/`. This supports independent Lambda deployment, testability, and clear separation of concerns (ingestion, analysis, dashboard).

---

## Redundancy & Replication Strategy

**Updated**: 2025-11-17 - **REVISED**: Compliant regional architecture

### Overview

This implementation uses a **regional multi-AZ architecture** that:
1. ✅ **Stays within ONE AWS region** (no GDPR/data residency violations)
2. ✅ **Leverages DynamoDB's native redundancy** (automatic multi-AZ replication)
3. ✅ **Includes security controls from day 1** (authentication, validation, monitoring)
4. ✅ **Scales from demo to production** without rearchitecture

**Key Decision**: **NO Global Tables** - they introduce data residency compliance violations without providing meaningful benefit for a demo/MVP system.

### Architecture Tiers

```
TIER 1: PRIMARY TABLE (sentiment-items)
├── Purpose: Source of truth for all sentiment data
├── Location: us-east-1 (single region)
├── Redundancy: Multi-AZ replication (automatic, AWS-managed)
├── Backup: Point-in-time recovery (35 days)
├── PK: source_id (e.g., "newsapi#article123")
├── SK: timestamp (ISO 8601)
├── GSIs:
│   ├── by_sentiment (PK: sentiment, SK: timestamp)
│   ├── by_tag (PK: tag, SK: timestamp)
│   └── by_status (PK: status, SK: timestamp) [for monitoring]
├── Streams: Enabled (NEW_AND_OLD_IMAGES)
├── TTL: 30 days (auto-cleanup)
└── Operations: ALL reads and writes (unified access)

TIER 2: DASHBOARD QUERY CACHE (Optional - Phase 2+)
├── Purpose: Pre-aggregated metrics for dashboard performance
├── Implementation: ElastiCache Redis OR DynamoDB cache table
├── Source: Populated by EventBridge scheduled Lambda (every 5 min)
├── Data: Last 24h aggregates (ingestion rate, sentiment distribution)
├── TTL: 24 hours
└── Enable When: Dashboard queries > 100/hour OR latency > 500ms

TIER 3: BACKUP & DISASTER RECOVERY
├── On-demand backups: Daily automated backups (7-day retention)
├── Point-in-time recovery: Continuous backups (35-day retention)
├── Cross-region backup: S3 cross-region replication (compliance copy)
└── RTO: < 4 hours (restore from backup) | RPO: < 1 second (PITR)
```

### Data Flow

```
1. INGESTION PATH
   ┌──────────────────────────────────────┐
   │ EventBridge Schedule (every 5 min)   │
   └────────┬─────────────────────────────┘
            ↓ (trigger)
   ┌──────────────────────────────────────┐
   │  Ingestion Lambda                    │
   │  • Fetch from NewsAPI (US region)    │
   │  • Tag matching (5 watch tags)       │
   │  • Deduplication (hash check)        │
   │  • Input validation (Pydantic)       │
   │  • Rate limiting (100 items/run)     │
   └────────┬─────────────────────────────┘
            ↓ (write with status="pending")
   ┌──────────────────────────────────────┐
   │  DynamoDB: sentiment-items           │
   │  PK: source_id | SK: timestamp       │
   │  • Multi-AZ replicated (automatic)   │
   │  • Point-in-time recovery enabled    │
   └────────┬────────┬────────────────────┘
            │        │
            │        └─► DynamoDB Streams (real-time)
            │                 ↓
            │        ┌─────────────────────┐
            │        │ SNS Topic: new-item │
            │        │ (triggers analysis) │
            │        └─────────────────────┘
            │
            └─► CloudWatch Metrics
                • ingestion_count
                • deduplication_hits
                • errors

2. ANALYSIS PATH
   ┌──────────────────────────┐
   │  SNS Topic: new-item     │
   └────────┬─────────────────┘
            ↓ (trigger)
   ┌──────────────────────────┐
   │  Analysis Lambda         │
   │  • Fetch item from table │
   │  • Sentiment inference   │
   │  • Input validation      │
   │  • Conditional update    │
   └────────┬─────────────────┘
            ↓ (update status="analyzed", add sentiment/score)
   ┌──────────────────────────┐
   │  DynamoDB: sentiment-items│
   │  • UpdateItem (conditional)│
   │  • Prevent overwrite     │
   └────────┬─────────────────┘
            └─► CloudWatch Metrics
                • analysis_latency
                • sentiment_distribution
                • errors

3. DASHBOARD READ PATH
   ┌──────────────────────────┐
   │  User Browser            │
   └────────┬─────────────────┘
            ↓ (HTTPS with API key)
   ┌──────────────────────────┐
   │  Lambda Function URL     │
   │  • API key validation    │
   │  • Rate limiting (100/min)│
   │  • CORS headers          │
   └────────┬─────────────────┘
            ↓
   ┌──────────────────────────┐
   │  Dashboard Lambda        │
   │  • Query GSIs            │
   │  • Filter by tag/sentiment│
   │  • Pagination (limit=20) │
   │  • Response sanitization │
   └────────┬─────────────────┘
            ↓ (query with eventually consistent reads)
   ┌──────────────────────────┐
   │  DynamoDB: sentiment-items│
   │  GSI: by_sentiment        │
   │  GSI: by_tag              │
   └──────────────────────────┘

4. MONITORING PATH
   ┌──────────────────────────┐
   │  EventBridge Schedule    │
   │  (every 1 minute)        │
   └────────┬─────────────────┘
            ↓
   ┌──────────────────────────┐
   │  Metrics Lambda          │
   │  • Query last 1h data    │
   │  • Calculate aggregates  │
   │  • Emit CloudWatch metrics│
   └────────┬─────────────────┘
            └─► CloudWatch Dashboard
                • Ingestion rate (items/hour)
                • Sentiment distribution (%)
                • Analysis latency (P50/P90)
                • Error rates
```

### Consistency Model

**Strong Consistency Requirements**:
- ✅ Deduplication checks (use `ConditionalCheckFailedException` on PutItem)
- ✅ Analysis updates (use `attribute_not_exists(sentiment)` condition)
- ✅ Multi-AZ replication (DynamoDB automatic, synchronous within region)

**Eventual Consistency Acceptable**:
- ✅ Dashboard reads (use GSI with eventually consistent reads)
- ✅ Metrics aggregation (CloudWatch metrics have 1-minute granularity)

**No Write-after-Read Requirements**:
- Dashboard can tolerate brief lag between ingestion and display
- Analysis updates don't need immediate visibility in dashboard

### Security Controls (Implemented from Day 1)

**Authentication & Authorization**:
- ✅ Dashboard Lambda: API key authentication (environment variable)
- ✅ IAM roles: Least-privilege permissions per Lambda
- ✅ Secrets Manager: API keys for external services (NewsAPI)
- ✅ No public table access: All access via Lambda proxies

**Input Validation**:
- ✅ Ingestion Lambda: Pydantic schemas for external API responses
- ✅ Analysis Lambda: Pydantic schemas for DynamoDB items
- ✅ Dashboard Lambda: Query parameter validation (no SQL injection possible)

**Rate Limiting**:
- ✅ Ingestion Lambda: EventBridge schedule (every 5 min, not on-demand)
- ✅ Dashboard Lambda: Reserved concurrency (10 max concurrent)
- ✅ Analysis Lambda: Reserved concurrency (5 max concurrent)
- ✅ API key rotation: 90-day expiry in Secrets Manager

**Monitoring & Alerting**:
- ✅ CloudWatch Alarms:
  - Ingestion errors > 5% (5-minute period)
  - Analysis latency > 5 seconds (P90)
  - Dashboard Lambda invocations > 1000/hour (potential abuse)
  - DynamoDB read/write throttles
- ✅ Structured logging: JSON logs with correlation IDs
- ✅ CloudWatch Insights queries for security events

**Data Protection**:
- ✅ No PII stored: Only article snippets (<200 chars), no user data
- ✅ TLS 1.2+ for all external API calls
- ✅ DynamoDB encryption at rest (AWS-managed keys)
- ✅ TTL-based auto-deletion (30 days)

### Disaster Recovery

**Backup Strategy**:
- ✅ **Point-in-time recovery (PITR)**: Continuous backups, 35-day retention
- ✅ **On-demand backups**: Daily at 02:00 UTC, 7-day retention
- ✅ **Cross-region backup copy**: S3 replication to us-west-2 (for compliance)

**Recovery Procedures**:
1. **Table corruption**: Restore from PITR (RPO < 1 second, RTO < 4 hours)
2. **Accidental deletion**: Restore from on-demand backup (RPO < 24 hours, RTO < 4 hours)
3. **Regional failure**: Manual failover using S3 backup in us-west-2 (RPO < 24 hours, RTO < 8 hours)

**Why No Global Tables?**:
- ❌ **Data residency violations**: Automatic replication to EU/Asia violates GDPR/local laws
- ❌ **Unnecessary cost**: 4x write costs for minimal benefit at demo scale
- ❌ **Complexity**: Multi-region conflict resolution not needed for unidirectional writes
- ✅ **Alternative**: Multi-AZ replication provides 99.99% availability within region

### Cost Analysis (Revised)

**Demo Scale** (100 items/hour, 30-day TTL):
- DynamoDB writes: ~72,000 writes/month = $0.36 (on-demand)
- DynamoDB reads: ~1,440 reads/month (dashboard) = $0.007
- DynamoDB storage: ~1GB = $0.25
- Lambda invocations: ~8,640/month = $0.02
- Lambda compute: 1s avg × 8,640 = $0.01
- Secrets Manager: 1 secret = $0.40
- CloudWatch Logs: 1GB = $0.50
- **Total: ~$1.54/month**

**Production Scale** (10,000 items/hour, assume):
- DynamoDB writes: ~7.2M writes/month = $36.00
- DynamoDB reads: ~144,000 reads/month = $0.72
- DynamoDB storage: ~100GB = $25.00
- Lambda compute: ~$5.00
- **Total: ~$67/month** (no DAX, no global tables)

**Comparison**:
- Previous "Best of All Worlds": $538/month (with global tables + DAX)
- Revised architecture: $67/month (87% cost reduction)
- Removed: $400 DAX + $71 global table replication costs

### Cost Controls & Andon Cord

**Purpose**: Prevent runaway charges and automatically alert/throttle on anomalies.

**Budget Alarms** (AWS Budgets):
```
Monthly Budget: $50 (demo environment)
├── 80% threshold ($40): Email notification to ops team
├── 100% threshold ($50): Email notification + PagerDuty alert
└── 120% threshold ($60): Auto-throttle Lambda concurrency to 1
```

**Andon Cord Triggers**:
| Trigger | Threshold | Action |
|---------|-----------|--------|
| Budget exceeded | >100% monthly | Notify + throttle Lambdas |
| Lambda invocations | >10k/hour | CloudWatch alarm + investigate |
| DynamoDB WCU spike | >1000/minute | CloudWatch alarm (already exists) |
| Lambda error rate | >10% over 5 min | CloudWatch alarm + notify |
| Analysis cold starts | >50/hour | Investigate model loading issues |

**Automatic Responses**:
- **Level 1 (Warning)**: SNS notification to ops team
- **Level 2 (Throttle)**: Reduce EventBridge schedule to 1/hour, set Lambda concurrency to 1
- **Level 3 (Stop)**: Disable EventBridge rules (manual restart required)

**Terraform Implementation** (add to `modules/budget/`):
```hcl
resource "aws_budgets_budget" "monthly_cost" {
  name              = "${var.environment}-sentiment-monthly-budget"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_limit  # Default: 50
  limit_unit        = "USD"
  time_unit         = "MONTHLY"

  cost_filters = {
    TagKeyValue = "user:Feature$001-interactive-dashboard-demo"
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alert_emails
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alert_emails
  }
}
```

**Manual Andon Pull**: To immediately stop all ingestion:
```bash
# Disable ingestion schedule
aws events disable-rule --name ${ENVIRONMENT}-ingestion-schedule

# Throttle all Lambdas to 0
aws lambda put-function-concurrency --function-name ${ENVIRONMENT}-ingestion --reserved-concurrent-executions 0
aws lambda put-function-concurrency --function-name ${ENVIRONMENT}-analysis --reserved-concurrent-executions 0
```

### Model Versioning Strategy

**Current Model**: DistilBERT fine-tuned on SST-2 (distilbert-base-uncased-finetuned-sst-2-english)

**Version Management**:
```
Lambda Layer versioning tracks model versions:
├── sentiment-model-layer:1  → v1.0.0 (DistilBERT SST-2, ~250MB)
├── sentiment-model-layer:2  → v1.1.0 (quantized INT8, ~125MB)
└── sentiment-model-layer:3  → v2.0.0 (RoBERTa, requires Container Image)
```

**Deployment Process**:
1. Build new model layer: `scripts/build-model-layer.sh v1.1.0`
2. Publish layer version: `aws lambda publish-layer-version`
3. Update Lambda to new layer: `terraform apply -var="model_layer_version=2"`
4. Verify: Check CloudWatch metrics for inference latency/accuracy

**Rollback Process**:
1. Identify issue: Monitor `InferenceLatencyMs`, `AnalysisErrors`, sentiment distribution drift
2. Rollback: `terraform apply -var="model_layer_version=1"` (revert to previous)
3. Verify: Confirm metrics return to baseline

**Environment Variable**:
- `MODEL_VERSION`: Tracked in Lambda environment, recorded in DynamoDB items
- Enables filtering/querying by model version for A/B analysis

**Upgrade Path**:
| Model | Size | Accuracy | Cold Start | Deployment |
|-------|------|----------|------------|------------|
| DistilBERT (current) | 250MB | 91% | ~2.5s | Lambda Layer |
| DistilBERT INT8 | 125MB | 90% | ~1.5s | Lambda Layer |
| RoBERTa-base | 500MB | 94% | ~5s | Container Image |
| OpenAI API | N/A | 95%+ | <100ms | API call (no layer) |

### Watch Tags Configuration

**Current Approach (Demo)**: Static environment variable

```python
# Ingestion Lambda reads from environment
WATCH_TAGS = os.environ.get('WATCH_TAGS', 'AI,climate,economy,health,sports')
tags = [tag.strip() for tag in WATCH_TAGS.split(',')]
```

**Changing Tags**:
1. Update Terraform variable: `watch_tags = "AI,technology,finance,health,energy"`
2. Apply: `terraform apply`
3. Lambda cold start picks up new environment variable

**Limitations**:
- Requires Lambda redeployment to change tags
- No runtime validation of tag format
- Maximum ~10 tags (NewsAPI query limits)

**Future Approach (Phase 2)**: DynamoDB configuration table

```
Table: sentiment-config
├── PK: config_type
├── SK: config_key
└── value: JSON

Example:
{
  "config_type": "watch_tags",
  "config_key": "active",
  "value": {
    "tags": ["AI", "climate", "economy", "health", "sports"],
    "updated_at": "2025-11-17T10:00:00Z",
    "updated_by": "admin"
  }
}
```

**Benefits of Phase 2**:
- Dynamic tag management via admin API
- No redeployment required
- Audit trail of configuration changes
- Tag validation before save

### Test Coverage Requirements

**Minimum Coverage Gates**:
- Unit tests: **>80% line coverage** (pytest-cov)
- Integration tests: All Lambda handlers have happy path + error tests
- E2E tests: Full ingestion → analysis → dashboard flow

**Test Categories**:
```
tests/
├── unit/                    # 80% coverage required
│   ├── test_adapters.py     # NewsAPI adapter parsing
│   ├── test_sentiment.py    # Inference logic, neutral threshold
│   ├── test_deduplication.py # Hash generation, collision handling
│   └── test_validation.py   # Pydantic schema validation
├── integration/             # All handlers covered
│   ├── test_ingestion.py    # Mock NewsAPI, real DynamoDB (moto)
│   ├── test_analysis.py     # Mock model, real DynamoDB (moto)
│   └── test_dashboard.py    # Query patterns, GSI usage
└── e2e/                     # Deployed infrastructure
    └── test_full_flow.py    # Seed data → verify dashboard
```

**CI/CD Gates**:
```yaml
# .github/workflows/test.yml
- name: Run tests with coverage
  run: pytest --cov=src --cov-report=xml --cov-fail-under=80

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

**Mocking Strategy**:
- AWS services: `moto` library (DynamoDB, Secrets Manager, SNS)
- External APIs: `responses` library (NewsAPI)
- ML model: Mock `pipeline()` return values

### Supply Chain Security

**Dependency Management**:
```
requirements.txt with pinned versions:
boto3==1.34.20
pydantic==2.5.3
requests==2.31.0
transformers==4.36.0
torch==2.1.0
```

**Security Scanning**:
- **Dependabot**: Enable in GitHub repository settings
- **pip-audit**: Run in CI/CD pipeline
  ```yaml
  - name: Security audit
    run: pip-audit --require-hashes -r requirements.txt
  ```
- **Snyk** (optional): For deeper vulnerability analysis

**Model Artifact Verification**:
```bash
# scripts/build-model-layer.sh
MODEL_NAME="distilbert-base-uncased-finetuned-sst-2-english"
EXPECTED_HASH="sha256:abc123..."  # Pin expected hash

# Download and verify
python -c "from transformers import AutoModel; AutoModel.from_pretrained('$MODEL_NAME')"

# Verify hash
ACTUAL_HASH=$(sha256sum layer/model/pytorch_model.bin | cut -d' ' -f1)
if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
  echo "ERROR: Model hash mismatch!"
  exit 1
fi
```

**Lambda Code Signing** (Phase 2):
- Create AWS Signer signing profile
- Sign deployment packages before upload
- Configure Lambda to reject unsigned code

**Container Image Scanning** (if using Container Images):
```yaml
# ECR scanning enabled
resource "aws_ecr_repository" "lambda" {
  name                 = "sentiment-analysis"
  image_scanning_configuration {
    scan_on_push = true
  }
}
```

### Rollout Plan (Simplified)

**Phase 1 (Demo)** - Week 1:
- ✅ Single DynamoDB table with 3 GSIs
- ✅ Multi-AZ replication (automatic)
- ✅ API key authentication on dashboard
- ✅ Input validation with Pydantic
- ✅ CloudWatch alarms for critical metrics

**Phase 2 (Production)** - Week 4+:
- Add ElastiCache Redis for pre-aggregated metrics (if latency > 500ms)
- Increase Lambda concurrency limits based on traffic
- Add AWS WAF for dashboard Lambda Function URL
- Enable AWS X-Ray for distributed tracing

**Phase 3 (Scale)** - Month 3+:
- Consider regional replicas ONLY if international expansion required
- Implement geo-routing with Route 53 (per-region data isolation)
- Add DynamoDB auto-scaling (if traffic patterns warrant)

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
