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

**Updated**: 2025-11-17 - Incorporated "Best of All Worlds" multi-tier architecture

### Overview

This implementation uses a production-grade redundancy strategy combining:
1. **Global Tables** for multi-region disaster recovery
2. **DynamoDB Streams** for read/write separation
3. **Read-Optimized Table** for dashboard performance
4. **DAX Cache** (Phase 2) for sub-10ms read latency

### Architecture Tiers

```
TIER 1: PRIMARY WRITE TABLE (sentiment-items-primary)
├── Purpose: Write-optimized, strong consistency
├── Location: us-east-1 (primary region)
├── GSIs: NONE (reduces write latency)
├── Streams: Enabled (NEW_AND_OLD_IMAGES)
└── Operations: All ingestion + analysis writes

TIER 2: GLOBAL TABLE REPLICAS (Disaster Recovery)
├── us-west-2 replica (standby, < 1 sec replication lag)
├── eu-west-1 replica (standby, < 1 sec replication lag)
└── ap-south-1 replica (standby, < 1 sec replication lag)
    └── Failover: Can be promoted if us-east-1 unavailable

TIER 3: READ-OPTIMIZED TABLE (sentiment-items-dashboard)
├── Purpose: Dashboard queries, denormalized schema
├── Source: Populated via DynamoDB Streams
├── PK: day_partition (YYYY-MM-DD) for efficient time queries
├── GSIs: by_sentiment (filter by positive/negative/neutral)
│         by_tag (query by matched tags)
├── TTL: 7 days (auto-cleanup for cost control)
└── Lag: 200-500ms behind primary table (acceptable)

TIER 4: DAX CACHE (Phase 2 - Optional)
├── Purpose: Sub-10ms read performance
├── Cluster: 3 nodes (multi-AZ HA)
├── Cache TTL: 5 minutes
├── Target: sentiment-items-dashboard ONLY
└── Enable When: Dashboard reads > 10 queries/sec
```

### Data Flow

```
1. WRITE PATH (Ingestion Lambda)
   ┌──────────────────────────┐
   │ External API (NewsAPI)   │
   └────────┬─────────────────┘
            ↓ (fetch items)
   ┌──────────────────────────┐
   │  Ingestion Lambda        │
   │  • Deduplication check   │
   │  • Conditional PutItem   │
   └────────┬─────────────────┘
            ↓ (write to primary table ONLY)
   ┌──────────────────────────┐
   │ sentiment-items-primary  │
   │ (us-east-1)              │
   │ status = "pending"       │
   └────────┬────────┬────────┘
            │        │
            │        └─► Global Replicas (async, < 1 sec)
            │            • us-west-2
            │            • eu-west-1
            │            • ap-south-1
            │
            └─► DynamoDB Streams (real-time)
                     ↓
   ┌──────────────────────────┐
   │ Stream Processor Lambda  │
   │ • Skip if status=pending │
   │ • Transform schema       │
   │ • Day-partition          │
   │ • Denormalize tags       │
   └────────┬─────────────────┘
            ↓ (batch write, 100 records/5 sec)
   ┌──────────────────────────┐
   │ sentiment-items-dashboard│
   │ • PK: day_partition      │
   │ • One item per tag       │
   │ • TTL: 7 days            │
   └──────────────────────────┘

2. ANALYSIS PATH (Analysis Lambda)
   ┌──────────────────────────┐
   │  SNS Topic (new item)    │
   └────────┬─────────────────┘
            ↓ (trigger)
   ┌──────────────────────────┐
   │  Analysis Lambda         │
   │  • Run sentiment model   │
   │  • Conditional Update    │
   └────────┬─────────────────┘
            ↓ (update primary table ONLY)
   ┌──────────────────────────┐
   │ sentiment-items-primary  │
   │ SET status = "analyzed"  │
   │ SET sentiment, score     │
   └────────┬─────────────────┘
            └─► DynamoDB Streams (triggers update to dashboard table)

3. READ PATH (Dashboard Lambda)
   ┌──────────────────────────┐
   │  Dashboard User Request  │
   └────────┬─────────────────┘
            ↓ (API Gateway invoke)
   ┌──────────────────────────┐
   │  Dashboard Lambda        │
   │  • Query by day_partition│
   │  • Use by_sentiment GSI  │
   │  • Limit=20              │
   └────────┬─────────────────┘
            ↓ (read from dashboard table, NOT primary)
   ┌──────────────────────────┐
   │ Phase 1: Direct Query    │
   │ sentiment-items-dashboard│
   │ (eventually consistent)  │
   └──────────────────────────┘
            ↓ (Phase 2: add cache)
   ┌──────────────────────────┐
   │ DAX Cache (3-node)       │
   │ • 5-minute TTL           │
   │ • Sub-10ms reads         │
   └──────────────────────────┘
```

### Consistency Model

**Strong Consistency Requirements**:
- ✅ Deduplication checks (primary table writes)
- ✅ Analysis updates (conditional write prevents race conditions)
- ✅ Failover promotion (global replica promotion requires manual intervention)

**Eventual Consistency Acceptable**:
- ✅ Dashboard reads (200-500ms lag acceptable)
- ✅ Metrics aggregation (5-minute staleness with DAX cache)
- ✅ Global table replication (< 1 second lag)

**Write-after-Read Scenarios**:
- ❌ NOT NEEDED: No use case requires immediate read after write
- Ingestion → Dashboard display can tolerate 500ms lag
- Analysis update → Dashboard refresh can tolerate 500ms lag

### Traffic Interleaving & Load Management

**Problem**: Prevent stream processor from overwhelming dashboard table during traffic spikes.

**Solution**: Batched stream processing with configurable limits

**Lambda Event Source Mapping Configuration**:
```hcl
batch_size = 100  # Process 100 stream records per invocation
maximum_batching_window_in_seconds = 5  # Wait up to 5 seconds to fill batch
maximum_retry_attempts = 3
bisect_batch_on_function_error = true  # Split failed batches
```

**Traffic Patterns**:
- **Ingestion rate**: 500 writes/hour → 0.14 writes/sec (demo scale)
- **Stream processing**: Batches of 100 records every ~5-10 seconds
- **Dashboard writes**: Smoothed by batching (no spikes)
- **Dashboard reads**: 2 queries/sec (demo scale)

**Failover Strategy**:
1. **Primary region failure** (us-east-1 down):
   - Manual promotion of us-west-2 replica to primary
   - Update Lambda environment variables to point to us-west-2
   - RTO (Recovery Time Objective): ~15 minutes
   - RPO (Recovery Point Objective): < 1 second (last replicated write)

2. **Dashboard table unavailable**:
   - Fallback to primary table queries (slower, but functional)
   - Implement circuit breaker pattern in Dashboard Lambda

3. **Stream processor failure**:
   - DynamoDB Streams retain records for 24 hours
   - Lambda automatic retry (3 attempts)
   - CloudWatch alarm triggers manual investigation

### Cost Analysis

**Phase 1 (Demo Scale)**: $1.19/month
- Primary table writes: $0.09
- Global replicas (3 regions): $0.27
- Dashboard table writes: $0.54
- Dashboard table reads: $0.26
- Stream processor Lambda: $0.02
- Data transfer: $0.01

**Phase 2 (Add DAX)**: +$97/month (enable when reads > 10/sec)

**Phase 3 (Production Scale)**: $538/month
- Saves $1,462/month vs. DynamoDB-only architecture (73% reduction)

### Rollout Plan

See: `/specs/001-interactive-dashboard-demo/traffic-migration.md` (created separately)

**Phased Rollout**:
1. **Phase 1A (Demo)**: Primary table + dashboard table (no replicas, no DAX)
2. **Phase 1B (Staging)**: Add global table replicas
3. **Phase 2 (Production)**: Add DAX cache when reads > 10/sec
4. **Phase 3 (Scale)**: Optimize batch sizes, add monitoring dashboards

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
