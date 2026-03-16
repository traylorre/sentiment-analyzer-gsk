# Data Model: E2E Test Coverage Expansion (1223)

## Test Data Entities

This feature creates test data, not application data. All entities use existing DynamoDB table schemas with test-prefixed identifiers.

### Test User

Created via `POST /api/v2/auth/anonymous` during test setup.

| Field | Format | Purpose |
|-------|--------|---------|
| user_id | `E2E_{run_id}_user_{n}` | Unique per test run |
| auth_type | `anonymous` → `free` after verification | Lifecycle under test |
| TTL | 24 hours | Auto-cleanup |

### Test Alert

Created via `POST /api/v2/alerts` during US3 tests.

| Field | Format | Purpose |
|-------|--------|---------|
| alert_name | `E2E_{run_id}_alert_{n}` | Unique per test run |
| ticker | `AAPL` (fixed) | Deterministic test ticker |
| threshold | Varies per test | CRUD validation |

### Test Configuration

Created via `POST /api/v2/configurations` during US5 account linking tests.

| Field | Format | Purpose |
|-------|--------|---------|
| config_name | `E2E_{run_id}_config_{n}` | Unique per test run |
| tickers | `["AAPL"]` | Minimal config for data preservation checks |

### Magic Link Token (Read-Only)

Queried from DynamoDB after requesting magic link. Not created by tests.

| Field | Access | Purpose |
|-------|--------|---------|
| PK | `TOKEN#{token_id}` | Direct lookup for verification URL |
| email | Query via `by_email` GSI | Find token for test email |
| used | Filter condition | Ensure unused token |

## Test Run Isolation

Each test run generates a unique `run_id`:
```
E2E_{YYYYMMDD}_{HHmmss}_{4-char-random}
```
Example: `E2E_20260316_143022_a7f3`

All test data uses this prefix. Cleanup happens via:
1. `afterAll()` hooks in Playwright tests (primary)
2. DynamoDB TTL (24h fallback if tests crash)
3. `test_cleanup.py` manual sweep (existing infrastructure)
