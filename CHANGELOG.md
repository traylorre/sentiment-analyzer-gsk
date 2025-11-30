# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - Feature 009

### Added

- **E2E Test Oracle Validation** (Feature 009)
  - `SyntheticTestOracle` with deterministic sentiment computation
  - `OracleExpectation` and `ValidationResult` dataclasses for tolerance-based assertions (±0.01)
  - `ConfigGenerator` for reproducible seeded test data
  - 7 failure injection tests for error handling paths (Tiingo/Finnhub failures, circuit breaker, timeouts)
  - `TestMetrics` class with 15% skip rate threshold tracking
  - Eliminated dual-outcome assertion anti-patterns (`assert A or B`)

---

## [2.1.0] - Feature 008 (2025-11-28)

### Added

- **E2E Validation Suite** (Feature 008)
  - Full E2E test infrastructure with `pytest-asyncio` and `httpx`
  - `PreprodAPIClient` for authenticated API testing against real AWS
  - Synthetic data generators (`TickerGenerator`, `NewsGenerator`, `SentimentGenerator`)
  - `SyntheticTiingoHandler` and `SyntheticFinnhubHandler` for deterministic test data
  - 117 E2E test tasks covering all API endpoints
  - `@pytest.mark.preprod` marker for real AWS tests (excluded from local runs)

---

## [2.0.0] - Feature 007 (2025-11-25)

### Added

- **Sentiment Dashboard Frontend** (Feature 007)
  - Next.js 14 with App Router and TypeScript 5.x
  - Robinhood-style dark fintech UI with shadcn/ui components
  - Zustand for client state management with persistence
  - React Query (@tanstack/react-query) for server state
  - Framer Motion animations and Lightweight Charts (TradingView)
  - Mobile-first responsive design
  - Vitest for unit tests, Playwright for E2E

---

## [1.5.0] - Feature 006

### Breaking Changes

#### Data Source Pivot: NewsAPI/Guardian -> Financial News APIs

**CRITICAL**: Feature 006 represents a complete architectural pivot from general news sentiment analysis to financial news sentiment and asset volatility correlation.

| Category | Before (001-005) | After (006) |
|----------|------------------|-------------|
| **News Sources** | NewsAPI, The Guardian | Tiingo, Finnhub |
| **Domain Focus** | General news sentiment | Financial news + asset volatility |
| **Data Type** | News articles only | News + OHLC price data for ATR |
| **Compliance** | GDPR concerns (EU news) | Privacy-compliant (financial APIs) |

#### Removed Components

- `NewsAPI` integration (all code paths)
- `The Guardian API` integration
- General news ingestion Lambda
- Legacy news sentiment model endpoints

#### New Components

- **Tiingo News API** - Primary financial news source (500 symbols/month free)
- **Finnhub API** - Secondary financial news + sentiment scores (60 calls/min free)
- **ATR Volatility** - Average True Range calculation from OHLC data
- **AWS Cognito** - OAuth authentication (Google, GitHub)
- **SendGrid** - Email notifications for magic links and alerts
- **AWS X-Ray** - Day 1 mandatory distributed tracing (all 4 Lambdas)
- **CloudWatch RUM** - Client-side user behavior analytics
- **CloudFront + S3** - CDN for dashboard static assets

### Migration Notes

1. **No backward compatibility**: Features 001-005 are archived in `legacy/v1-newsapi-features` branch
2. **No data migration**: Clean slate deployment (legacy features never reached production)
3. **Secret rotation**: Add Tiingo and Finnhub API keys to Secrets Manager
4. **Environment variables**: Remove `NEWSAPI_KEY`, add `TIINGO_API_KEY`, `FINNHUB_API_KEY`

### Security Changes

- **X-Ray tracing**: Changed from Phase 2 deferred to Day 1 mandatory
- **Authentication**: AWS Cognito for OAuth, custom Lambda + SendGrid for magic links
- **Rate limiting**: IP-based + CAPTCHA on anonymous config creation
- **Email security**: SendGrid verified sender with rate limiting

### Cost Budget

Target: <$100/month with 50% headroom (~$50/month estimated)

| Service | Estimate |
|---------|----------|
| Tiingo API | $0 (free tier) |
| Finnhub API | $0 (free tier) |
| SendGrid | $0 (100 emails/day free) |
| Cognito | ~$5 |
| Lambda (4 functions) | ~$10 |
| DynamoDB | ~$15 |
| CloudFront | ~$10 |
| S3 | ~$2 |
| CloudWatch RUM | ~$5 |
| X-Ray | ~$3 |

---

## [1.0.0] - Features 001-005 (Archived)

See `legacy/v1-newsapi-features` branch for historical implementation.

These features used NewsAPI and The Guardian API for general news sentiment analysis. They have been superseded by Feature 006's financial news pivot for privacy compliance reasons.

### Features Archived

- **001-interactive-dashboard-demo**: Original dashboard with NewsAPI
- **002-mobile-sentiment-dashboard**: Mobile-first responsive design
- **003-preprod-metrics-generation**: Lambda warmup for CloudWatch metrics
- **004-remove-test-placeholders**: Test quality improvements
- **005-synthetic-test-data**: E2E test data generator
