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

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
