# Feature Specification: Dashboard Lambda OHLC Secrets Configuration

**Feature Branch**: `1056-dashboard-ohlc-secrets`
**Created**: 2025-12-25
**Status**: Draft
**Input**: Add TIINGO_SECRET_ARN and FINNHUB_SECRET_ARN environment variables to Dashboard Lambda for OHLC endpoint

## Problem Statement

The Dashboard Lambda OHLC endpoint (`GET /api/v2/tickers/{ticker}/ohlc`) returns HTTP 503 "Tiingo data source unavailable" because the Lambda is missing the `TIINGO_SECRET_ARN` and `FINNHUB_SECRET_ARN` environment variables required to fetch API keys from AWS Secrets Manager.

**Root Cause**: The Ingestion Lambda has these environment variables configured, but the Dashboard Lambda (which also serves OHLC data) does not.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View OHLC Price Data (Priority: P1)

As a dashboard user, I want to view OHLC (Open/High/Low/Close) candlestick data for stock tickers so I can analyze price movements alongside sentiment data.

**Why this priority**: This is the core functionality - without it, the OHLC chart displays errors instead of data.

**Independent Test**: Can be tested by calling `GET /api/v2/tickers/AAPL/ohlc` and verifying price data is returned instead of 503.

**Acceptance Scenarios**:

1. **Given** the Dashboard Lambda has TIINGO_SECRET_ARN configured, **When** I request OHLC data for a valid ticker, **Then** I receive candlestick price data with open/high/low/close values
2. **Given** Tiingo API is unavailable, **When** I request OHLC data, **Then** the system falls back to Finnhub for data
3. **Given** both APIs are unavailable, **When** I request OHLC data, **Then** I receive a graceful error message (not a 503 configuration error)

---

### User Story 2 - Resolution Selection Works (Priority: P1)

As a dashboard user, I want to select different time resolutions (1min, 5min, 15min, 30min, 60min, Daily) and see the chart update with the appropriate candlestick data.

**Why this priority**: Resolution selection is the key feature of the OHLC implementation (Feature 1035).

**Independent Test**: Can be tested by calling `GET /api/v2/tickers/AAPL/ohlc?resolution=5` and verifying 5-minute candles are returned.

**Acceptance Scenarios**:

1. **Given** I select 5-minute resolution, **When** the chart loads, **Then** I see 5-minute candlestick data from Finnhub (intraday source)
2. **Given** I select Daily resolution, **When** the chart loads, **Then** I see daily candlestick data from Tiingo (daily source)

---

### Edge Cases

- What happens when the secret ARN exists but the secret value is empty? The endpoint returns 503 with clear error message
- What happens when the IAM role lacks permission to read the secret? Error is logged, endpoint returns 503
- What happens when the secret JSON is malformed (missing "api_key" field)? Error is logged, endpoint returns 503

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard Lambda MUST have `TIINGO_SECRET_ARN` environment variable configured pointing to the Tiingo API key secret
- **FR-002**: Dashboard Lambda MUST have `FINNHUB_SECRET_ARN` environment variable configured pointing to the Finnhub API key secret
- **FR-003**: Dashboard Lambda IAM role MUST have `secretsmanager:GetSecretValue` permission for both secrets
- **FR-004**: OHLC endpoint MUST return price data when secrets are properly configured
- **FR-005**: OHLC endpoint MUST fall back to Finnhub when Tiingo is unavailable

### Key Entities

- **TIINGO_SECRET_ARN**: Environment variable containing the ARN of the Tiingo API key secret in Secrets Manager
- **FINNHUB_SECRET_ARN**: Environment variable containing the ARN of the Finnhub API key secret in Secrets Manager
- **Dashboard Lambda**: The Lambda function serving `/api/v2/*` endpoints including OHLC

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: OHLC endpoint returns HTTP 200 with price data (not 503) when called with valid ticker
- **SC-002**: Dashboard Lambda environment includes both `TIINGO_SECRET_ARN` and `FINNHUB_SECRET_ARN` variables
- **SC-003**: Dashboard Lambda IAM role policy includes secretsmanager:GetSecretValue for tiingo and finnhub secrets
- **SC-004**: Resolution selector UI displays candlestick data for all resolutions (1, 5, 15, 30, 60, D)

## Technical Scope

### Files to Modify

1. `infrastructure/terraform/main.tf` - Add environment variables to `module.dashboard_lambda`
2. `infrastructure/terraform/modules/iam/main.tf` - Ensure Dashboard Lambda role has secrets access (may already exist)

### Pattern Reference

Copy pattern from Ingestion Lambda configuration:
```hcl
# From ingestion_lambda (line ~289)
TIINGO_SECRET_ARN  = module.secrets.tiingo_secret_arn
FINNHUB_SECRET_ARN = module.secrets.finnhub_secret_arn
```

## Assumptions

- The secrets (`preprod/sentiment-analyzer/tiingo` and `preprod/sentiment-analyzer/finnhub`) already exist in AWS Secrets Manager
- The secrets module already outputs `tiingo_secret_arn` and `finnhub_secret_arn`
- The IAM module may already grant the necessary permissions (needs verification)

## Out of Scope

- Creating the actual secrets in Secrets Manager (admin responsibility)
- Storing actual API key values (admin responsibility)
- Modifying the OHLC endpoint code (already works, just needs config)
