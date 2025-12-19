# Data Model: GSI Query Optimization

**Feature**: 502-gsi-query-optimization
**Date**: 2025-12-18

## Overview

This feature does not introduce new data models. It optimizes existing DynamoDB access patterns by replacing `table.scan()` with `table.query()` using pre-existing GSIs.

## Existing GSI Schema Reference

### Table: sentiment_items

| Attribute | Type | Description |
|-----------|------|-------------|
| source_id | S | Primary hash key - source identifier |
| timestamp | S | Primary range key - ISO 8601 timestamp |
| sentiment | S | Sentiment classification: positive, neutral, negative |
| tag | S | Content tag for categorization |
| status | S | Processing status: pending, analyzed |

**GSIs Used in This Feature**:

#### by_sentiment GSI
- **Hash Key**: sentiment (S)
- **Range Key**: timestamp (S)
- **Projection**: ALL
- **Use Case**: SSE streaming polling - retrieve items by sentiment type

### Table: feature_006_users

| Attribute | Type | Description |
|-----------|------|-------------|
| PK | S | Primary hash key - composite key (e.g., USER#uuid) |
| SK | S | Primary range key - record type (e.g., PROFILE, SETTINGS) |
| entity_type | S | Record classification: USER, CONFIGURATION, ALERT_RULE, DIGEST_SETTINGS |
| status | S | Entity status: active, enabled, pending, disabled |
| email | S | User email address (lowercase normalized) |
| cognito_sub | S | Cognito subject ID for OAuth users |

**GSIs Used in This Feature**:

#### by_entity_status GSI
- **Hash Key**: entity_type (S)
- **Range Key**: status (S)
- **Projection**: ALL
- **Use Cases**:
  - Ingestion: get active configurations (entity_type=CONFIGURATION, status=active)
  - Alerts: find active alert rules (entity_type=ALERT_RULE, status=active)
  - Digest: find enabled digest settings (entity_type=DIGEST_SETTINGS, status=enabled)

#### by_email GSI
- **Hash Key**: email (S)
- **Range Key**: None
- **Projection**: ALL
- **Use Case**: User lookup by email (already implemented in get_user_by_email_gsi)

## Query Access Patterns

| Pattern | GSI | Key Condition | Filter (optional) |
|---------|-----|---------------|-------------------|
| Get active tickers | by_entity_status | entity_type=CONFIGURATION, status=active | - |
| Get sentiment items | by_sentiment | sentiment=:type | timestamp range |
| Find alerts by ticker | by_entity_status | entity_type=ALERT_RULE, status=active | ticker=:ticker |
| Get digest users | by_entity_status | entity_type=DIGEST_SETTINGS, status=enabled | - |
| Get user by email | by_email | email=:email | entity_type=USER |

## Data Validation Rules

### Query Parameters
- `sentiment` values: positive, neutral, negative (case-sensitive)
- `entity_type` values: USER, CONFIGURATION, ALERT_RULE, NOTIFICATION_QUEUE, DIGEST_SETTINGS
- `status` values: active, enabled, pending, disabled, failed
- `email` values: lowercase, RFC 5322 compliant

### Response Handling
- Empty results: Return empty list, not error
- Pagination: Continue querying while `LastEvaluatedKey` present
- Missing GSI: Log error, fail gracefully with appropriate exception

## No Schema Changes Required

All GSIs are already deployed via Terraform. This feature only changes how the application queries the data.
