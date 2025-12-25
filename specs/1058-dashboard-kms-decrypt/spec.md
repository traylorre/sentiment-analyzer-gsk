# Feature Specification: Dashboard Lambda KMS Decrypt Permission

**Feature Branch**: `1058-dashboard-kms-decrypt`
**Created**: 2025-12-25
**Status**: Draft
**Input**: Dashboard Lambda missing KMS Decrypt permission for Secrets Manager. The dashboard_secrets policy grants secretsmanager:GetSecretValue for tiingo and finnhub secrets but lacks the conditional kms:Decrypt block that ingestion Lambda has. This prevents the OHLC endpoint from fetching API keys.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Dashboard OHLC Data Access (Priority: P1)

As a dashboard user, I want to view OHLC (Open-High-Low-Close) candlestick charts for selected tickers so that I can analyze price movements alongside sentiment data.

**Why this priority**: Without the ability to fetch OHLC data, the dashboard only displays the sentiment donut chart, making the feature incomplete and not demo-able. This is a blocker for the core value proposition of the ONE URL dashboard.

**Independent Test**: Can be fully tested by navigating to the dashboard, entering a ticker symbol (e.g., AAPL), and verifying that candlestick chart data loads and renders. Delivers immediate visual value to users.

**Acceptance Scenarios**:

1. **Given** a user is on the dashboard page with Tiingo/Finnhub API keys configured in Secrets Manager, **When** the user enters a valid ticker symbol, **Then** the OHLC candlestick chart renders with price data within 3 seconds.

2. **Given** the dashboard Lambda attempts to fetch OHLC data, **When** it calls Secrets Manager to retrieve the Tiingo API key, **Then** the decryption succeeds and the API key is returned.

3. **Given** the dashboard Lambda attempts to fetch OHLC data, **When** it calls Secrets Manager to retrieve the Finnhub API key, **Then** the decryption succeeds and the API key is returned.

---

### Edge Cases

- What happens when the KMS key ARN is empty/not configured? The conditional block should evaluate to false and no KMS policy is attached (graceful degradation for non-KMS-encrypted secrets).
- What happens when the secrets exist but don't have the expected JSON structure? The adapters should return a user-friendly error message indicating misconfiguration.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Dashboard Lambda IAM role MUST include `kms:Decrypt` permission for the secrets KMS key when customer-managed encryption is used.
- **FR-002**: The KMS decrypt permission MUST be conditional on `secrets_kms_key_arn` being non-empty (matching the ingestion Lambda pattern).
- **FR-003**: The permission MUST apply to the same KMS key ARN used to encrypt Tiingo and Finnhub secrets.
- **FR-004**: The permission MUST be scoped only to the specific KMS key resource (least-privilege principle).

### Key Entities

- **Dashboard Lambda IAM Role**: The execution role for the dashboard Lambda function that requires Secrets Manager access.
- **Secrets KMS Key**: The customer-managed KMS key used to encrypt Tiingo and Finnhub secrets in Secrets Manager.
- **Tiingo/Finnhub Secrets**: The Secrets Manager secrets containing API keys for external price data providers.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Dashboard users can view OHLC candlestick charts when entering a valid ticker symbol (feature becomes functional).
- **SC-002**: The dashboard Lambda can successfully call `GetSecretValue` for Tiingo and Finnhub secrets without access denied errors.
- **SC-003**: No overly permissive IAM permissions introduced (kms:Decrypt scoped to single KMS key resource, not wildcard).
- **SC-004**: Terraform plan shows only the expected IAM policy change with no unintended drift.

## Assumptions

- Tiingo and Finnhub secrets use the same customer-managed KMS key as other secrets in the system.
- The `secrets_kms_key_arn` variable is already passed to the IAM module (verified from existing ingestion Lambda pattern).
- The ingestion Lambda's conditional KMS decrypt pattern (lines 79-87 in modules/iam/main.tf) is the correct pattern to follow.
