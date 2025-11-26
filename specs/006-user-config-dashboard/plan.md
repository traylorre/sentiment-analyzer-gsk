# Implementation Plan: Financial News Sentiment & Asset Volatility Dashboard

**Branch**: `006-user-config-dashboard` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-user-config-dashboard/spec.md`

## Summary

Feature 006 pivots the sentiment analyzer from general news (NewsAPI/Guardian) to financial news APIs (Tiingo + Finnhub) for privacy compliance. The dashboard correlates financial news sentiment with asset volatility (ATR) for US stock tickers. Key capabilities include:

- **Dual-source sentiment**: Compare Tiingo news (our model) vs Finnhub built-in sentiment
- **Volatility correlation**: ATR calculation from OHLC price data with trend arrows
- **User configurations**: Up to 2 saved configs with 5 tickers each (US markets only)
- **Authentication**: Anonymous localStorage → AWS Cognito OAuth (Google/GitHub) or magic links via SendGrid
- **Notifications**: Email alerts for sentiment/volatility thresholds via SendGrid
- **Observability**: X-Ray tracing (Day 1), CloudWatch RUM, full metrics suite

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, boto3, pydantic, aws-lambda-powertools, requests
**Frontend**: React/Next.js with TailwindCSS (mobile-first responsive)
**Storage**: DynamoDB (users, configurations, sentiment results, alerts), S3 (static assets)
**Testing**: pytest with moto (unit), real AWS dev environment (integration)
**Target Platform**: AWS Lambda (4 functions), CloudFront CDN, Cognito
**Project Type**: Web application (Lambda API + static frontend)
**Performance Goals**: 3s dashboard load on 3G, 2s config switch, 10s first sentiment results
**Constraints**: <$100/mo cost, Tiingo 500 symbols/mo, Finnhub 60 calls/min
**Scale/Scope**: 1,000 concurrent anonymous sessions, 90-day data retention (auth users)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Status | Implementation |
|-------------------------|--------|----------------|
| **Functional: Ingest from external APIs** | ✅ PASS | Tiingo + Finnhub adapters with backoff/retry |
| **Functional: Pluggable adapters** | ✅ PASS | Adapter pattern for Tiingo, Finnhub, future sources |
| **Functional: Deduplicate items** | ✅ PASS | Content hash + ticker+timestamp dedup in DynamoDB |
| **Functional: Return sentiment result** | ✅ PASS | pos/neu/neg + score 0-1 + model_version |
| **Security: Auth on admin endpoints** | ✅ PASS | Cognito OAuth + API key auth |
| **Security: Secrets in managed service** | ✅ PASS | Secrets Manager for Tiingo/Finnhub/SendGrid keys |
| **Security: Parameterized queries** | ✅ PASS | boto3 parameterized DynamoDB expressions |
| **Security: TLS in transit** | ✅ PASS | HTTPS enforced via CloudFront + Lambda URLs |
| **Deployment: Serverless on AWS** | ✅ PASS | Lambda + SNS + DynamoDB + S3 |
| **Deployment: Infrastructure as Code** | ✅ PASS | Terraform with S3 backend |
| **Observability: Structured logs** | ✅ PASS | Lambda Powertools JSON logging |
| **Observability: X-Ray tracing** | ✅ PASS | Day 1 mandatory (all 4 Lambdas) |
| **Observability: CloudWatch metrics** | ✅ PASS | Custom metrics + alarms |
| **Testing: Unit + Integration** | ✅ PASS | pytest + moto (unit), real AWS (integration) |
| **Dashboard: External metrics view** | ✅ PASS | CloudWatch RUM + metrics dashboard |
| **Dashboard: Admin feed controls** | ✅ PASS | Config management for tickers/timeframes |

**Constitution Gate**: ✅ **PASSED** - All minimal requirements satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/006-user-config-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity schemas
├── quickstart.md        # Phase 1 output - local dev setup
├── contracts/           # Phase 1 output - API specifications
│   ├── dashboard-api.md # REST API for dashboard Lambda
│   ├── auth-api.md      # Cognito + magic link flows
│   └── notification-api.md # Alert management endpoints
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Existing structure (preserved and extended)
src/
├── lambdas/
│   ├── ingestion/       # MODIFY: Add Tiingo + Finnhub adapters
│   │   ├── handler.py
│   │   ├── adapters/    # NEW: tiingo.py, finnhub.py
│   │   └── models.py
│   ├── analysis/        # MODIFY: ATR calculation, dual-source comparison
│   │   ├── handler.py
│   │   ├── atr.py       # NEW: ATR volatility calculation
│   │   └── sentiment.py # MODIFY: Support Finnhub built-in scores
│   ├── dashboard/       # MODIFY: User configs, heat map data
│   │   ├── handler.py
│   │   ├── api_v2.py    # NEW: Config management, alerts API
│   │   └── auth.py      # NEW: Cognito integration
│   ├── notification/    # NEW: Alert evaluation + SendGrid email
│   │   ├── handler.py
│   │   └── sendgrid.py
│   ├── metrics/         # EXISTING: CloudWatch metrics aggregation
│   └── shared/
│       ├── models/      # MODIFY: Add User, Configuration, Alert entities
│       ├── auth/        # NEW: Cognito helpers, magic link validation
│       └── cache/       # NEW: Ticker validation cache (~8K symbols)
├── dashboard/           # MODIFY: React frontend with heat maps
│   ├── components/      # NEW: HeatMap, TickerInput, ConfigSwitcher
│   ├── pages/           # NEW: Dashboard, Settings, Alerts
│   └── services/        # NEW: API client, localStorage manager
└── lib/
    └── logging_utils.py # EXISTING: Structured logging

tests/
├── unit/
│   ├── lambdas/
│   │   ├── ingestion/   # NEW: Tiingo/Finnhub adapter tests
│   │   ├── analysis/    # NEW: ATR calculation tests
│   │   ├── dashboard/   # MODIFY: Config API tests
│   │   └── notification/ # NEW: Alert evaluation tests
│   └── dashboard/       # NEW: React component tests
├── integration/
│   ├── test_ingestion_preprod.py  # MODIFY: Financial API tests
│   └── test_dashboard_preprod.py  # MODIFY: Config flow tests
└── e2e/
    └── test_user_flows.py  # NEW: Anonymous → Auth conversion tests

infrastructure/
└── terraform/
    ├── main.tf          # MODIFY: Add Cognito, CloudFront, new secrets
    ├── modules/
    │   ├── cognito/     # NEW: User pool, OAuth providers
    │   ├── cloudfront/  # NEW: CDN for static assets
    │   └── xray/        # NEW: X-Ray tracing configuration
    └── variables.tf     # MODIFY: Add new API keys, Cognito config
```

**Structure Decision**: Extend existing Lambda-based architecture. Add `notification/` Lambda for alert processing, extend `ingestion/` with financial API adapters, add React frontend components for heat map visualization.

## Complexity Tracking

No constitution violations requiring justification. Architecture follows existing serverless patterns.

## Phase Outputs

### Phase 0: Research ✅ COMPLETE
- [x] research.md - Technology decisions for Tiingo/Finnhub/Cognito/SendGrid

### Phase 1: Design ✅ COMPLETE
- [x] data-model.md - Entity schemas (User, Configuration, SentimentResult, Alert)
- [x] contracts/dashboard-api.md - REST API specification
- [x] contracts/auth-api.md - Authentication flows
- [x] contracts/notification-api.md - Alert management
- [x] quickstart.md - Local development setup

### Phase 2: Tasks (via /speckit.tasks)
- [ ] tasks.md - Implementation task breakdown

---

## Planning Complete

**Branch**: `006-user-config-dashboard`
**Plan File**: `/specs/006-user-config-dashboard/plan.md`
**Status**: Ready for `/speckit.tasks` to generate implementation tasks

### Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Research | `research.md` | Technology decisions (APIs, auth, visualization) |
| Data Model | `data-model.md` | Entity schemas with DynamoDB key design |
| Dashboard API | `contracts/dashboard-api.md` | REST API for configs, sentiment, volatility |
| Auth API | `contracts/auth-api.md` | OAuth, magic links, session management |
| Notification API | `contracts/notification-api.md` | Alert rules and email notifications |
| Quickstart | `quickstart.md` | Local development setup guide |

### Next Steps

1. Run `/speckit.tasks` to generate implementation task breakdown
2. Review and prioritize tasks
3. Begin implementation following task order
