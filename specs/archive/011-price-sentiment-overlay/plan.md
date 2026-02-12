# Implementation Plan: Price-Sentiment Overlay Chart

**Branch**: `011-price-sentiment-overlay` | **Date**: 2025-12-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-price-sentiment-overlay/spec.md`

## Summary

Add a new OHLC price data endpoint and dual-axis chart component that combines candlestick price visualization with sentiment line overlay. Users can view price movements alongside sentiment from selectable sources (Tiingo, Finnhub, our_model, aggregated) with configurable time ranges (1W-1Y). Leverages existing Tiingo/Finnhub adapters that already provide OHLC data for ATR calculations.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5 (frontend)
**Primary Dependencies**: FastAPI 0.121.3, httpx 0.28.1, TradingView Lightweight Charts 5.0.9, React 18, Next.js 14.2.21, Zustand 5.0.8, React Query 5.90.11
**Storage**: DynamoDB (single-table design), in-memory cache for OHLC data
**Testing**: pytest 8.3.4 + moto (backend), Vitest 4.0.14 + Playwright (frontend)
**Target Platform**: AWS Lambda (backend), Vercel/static hosting (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Chart loads within 3 seconds, tooltip response within 200ms
**Constraints**: Cache OHLC data until next market open (~24h), 1 year historical data depth
**Scale/Scope**: Supports existing user base, up to 5 tickers per configuration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **1. Functional Requirements** | PASS | Extends existing ingestion/analysis pattern with OHLC endpoint |
| **2. Non-Functional (99.5% SLA, P90 ≤500ms)** | PASS | Leverages existing Lambda infrastructure with caching |
| **3. Security & Access Control** | PASS | Uses existing X-User-ID authentication, TLS, no new secrets |
| **4. Data & Model Requirements** | PASS | No PII, OHLC is public market data |
| **5. Deployment (Serverless/IaC)** | PASS | Extends existing Lambda, no new infrastructure needed |
| **6. Observability & Monitoring** | PASS | Uses existing CloudWatch/X-Ray integration |
| **7. Testing & Validation** | PASS | Unit tests with moto, E2E with synthetic data |
| **8. Git Workflow & CI/CD** | PASS | Feature branch workflow, GPG-signed commits |
| **9. Tech Debt Tracking** | PASS | Will document any shortcuts in TECH_DEBT_REGISTRY.md |

**Gate Result**: PASS - No violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/011-price-sentiment-overlay/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
│   └── ohlc-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Backend (Python Lambda)
src/lambdas/
├── dashboard/
│   ├── ohlc.py              # NEW: OHLC price data endpoint
│   ├── sentiment.py         # EXISTING: Add historical sentiment by date
│   └── volatility.py        # EXISTING: Reference for OHLC usage
├── shared/
│   ├── adapters/
│   │   ├── tiingo.py        # EXISTING: get_ohlc() method
│   │   └── finnhub.py       # EXISTING: get_ohlc() method
│   └── models/
│       └── ohlc.py          # NEW: OHLC response models

tests/
├── unit/
│   └── dashboard/
│       └── test_ohlc.py     # NEW: Unit tests for OHLC endpoint
├── contract/
│   └── test_ohlc_contract.py # NEW: Schema validation
└── integration/
    └── test_ohlc_flow.py    # NEW: E2E flow test

# Frontend (Next.js)
frontend/
├── src/
│   ├── components/
│   │   └── charts/
│   │       ├── price-sentiment-chart.tsx  # NEW: Dual-axis overlay chart
│   │       ├── sentiment-chart.tsx        # EXISTING: Reference
│   │       └── atr-chart.tsx              # EXISTING: Reference
│   ├── hooks/
│   │   └── use-ohlc-data.ts               # NEW: React Query hook for OHLC
│   └── services/
│       └── ohlc-api.ts                    # NEW: API client for OHLC endpoint
└── tests/
    └── unit/
        └── charts/
            └── price-sentiment-chart.test.tsx  # NEW: Component tests
```

**Structure Decision**: Web application pattern - extends existing backend Lambda handlers and frontend Next.js components. No new infrastructure required, leverages existing adapters and chart libraries.

## Complexity Tracking

> No violations - section not required.

## Phase 0: Research Summary

### Research Tasks Identified

1. **TradingView Lightweight Charts dual-axis support** - Verify candlestick + line overlay capability
2. **Existing adapter OHLC implementation** - Review Tiingo/Finnhub get_ohlc() patterns
3. **Market hours detection** - How to determine cache expiration based on market open/close
4. **Sentiment history endpoint** - Verify sentiment data can be retrieved by date range

### Key Decisions (to be detailed in research.md)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chart library | TradingView Lightweight Charts | Already in use, supports dual-axis via price scale options |
| OHLC data source | Tiingo primary, Finnhub fallback | Matches existing volatility.py pattern |
| Cache strategy | Memory cache with market-hours TTL | OHLC data static after market close |
| Sentiment alignment | Match by trading day | Non-trading days show sentiment without candles |

## Phase 1: Design Artifacts

### Data Model (to be detailed in data-model.md)

**PriceCandle** (extends existing OHLCCandle):
- date: datetime
- open: float
- high: float
- low: float
- close: float
- volume: int | None

**ChartDataResponse**:
- ticker: str
- candles: list[PriceCandle]
- sentiment: list[SentimentPoint]
- time_range: TimeRange
- cache_expires_at: datetime

### API Contracts (to be detailed in contracts/)

**New Endpoint**: `GET /api/v2/tickers/{ticker}/ohlc`

Query params:
- `range`: 1W | 1M | 3M | 6M | 1Y (default: 1M)
- `start_date`: ISO date (optional, overrides range)
- `end_date`: ISO date (optional, defaults to today)

Response: Array of OHLC candles with date, OHLC values, volume

**Modified Endpoint**: `GET /api/v2/configurations/{id}/sentiment`

Add query param:
- `source`: tiingo | finnhub | our_model | aggregated (default: aggregated)

### Frontend Components (to be detailed in quickstart.md)

**PriceSentimentChart**: Dual-axis chart combining:
- Left axis: Candlestick series (price)
- Right axis: Line series (sentiment -1 to +1)
- Controls: Time range selector, sentiment source dropdown, layer toggles
- Interactions: Crosshair with unified tooltip, touch gestures
