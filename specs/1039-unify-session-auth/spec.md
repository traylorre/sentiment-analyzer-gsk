# Feature 1039: Unify Session Authentication

## Problem Statement

The dashboard Lambda currently has **two separate authentication mechanisms**:

1. **API Key Auth** (`verify_api_key()` in handler.py:193-274)
   - Used by: `/api/v2/metrics`, `/api/v2/sentiment`, `/api/v2/trends`, `/api/v2/articles`, `/chaos/*`
   - Mechanism: Shared secret via `Authorization: Bearer <API_KEY>`
   - Issues:
     - Shared secret visible in HTML source (security hole)
     - No per-user audit trail
     - No rate limiting per user
     - No session expiration/revocation

2. **Session Auth** (`get_user_id_from_request()` in router_v2.py:137-184)
   - Used by: configs, alerts, OHLC, user-scoped endpoints
   - Mechanism: `Authorization: Bearer <JWT>` or `X-User-ID` header
   - Benefits:
     - Per-user identity via `extract_auth_context()`
     - Session validation against DynamoDB
     - Expiration and revocation support
     - Audit trail capability

## Goal

Consolidate to **one auth system**: session-based auth for all endpoints.

## Endpoint Classification

| Endpoint | Data Type | Current Auth | Target Auth |
|----------|-----------|--------------|-------------|
| `/api/v2/metrics` | Aggregated public | API Key | Session (anonymous OK) |
| `/api/v2/sentiment` | Aggregated public | API Key | Session (anonymous OK) |
| `/api/v2/trends` | Aggregated public | API Key | Session (anonymous OK) |
| `/api/v2/articles` | Aggregated public | API Key | Session (anonymous OK) |
| `/api/v2/configs` | User-scoped | Session | Session (unchanged) |
| `/api/v2/alerts` | User-scoped | Session | Session (unchanged) |
| `/chaos/*` | Admin | API Key | Session (admin required) |

## Implementation Strategy

### Phase 1: Add Session Auth to Public Endpoints

For `/api/v2/metrics`, `/api/v2/sentiment`, `/api/v2/trends`, `/api/v2/articles`:

1. Remove `Depends(verify_api_key)` from function signature
2. Add `user_id = get_user_id_from_request(request, validate_session=False)`
3. Anonymous sessions (UUID) are accepted - no DynamoDB validation needed
4. Log `user_id` for audit trail

### Phase 2: Chaos Endpoints Migration

For `/chaos/*` endpoints:

1. Remove `Depends(verify_api_key)`
2. Add admin validation via `get_authenticated_user_id(request)` (requires non-anonymous)
3. Add admin role check (new requirement)

### Phase 3: Remove API Key Infrastructure

1. Delete `verify_api_key()` function from handler.py
2. Remove `API_KEY` environment variable from Terraform
3. Remove API key injection in HTML serving
4. Update tests to use session tokens

## Files to Modify

### Backend
- `src/lambdas/dashboard/handler.py` - Remove verify_api_key, update 10 endpoints
- `src/lambdas/dashboard/config.py` - Remove API_KEY loading
- `infrastructure/terraform/dashboard-lambda.tf` - Remove API_KEY env var

### Tests
- `tests/unit/dashboard/test_handler.py` - Update to session tokens
- `tests/conftest.py` - Remove API_KEY fixture
- `tests/e2e/helpers/api_client.py` - Use session auth
- `tests/integration/test_dashboard_dev.py` - Update auth_headers fixture to use X-User-ID header with valid UUID (anonymous session)

## Non-Goals

- Adding OAuth/OIDC (future feature)
- Changing DynamoDB session schema
- Frontend auth flow changes (already uses sessions)

## Success Criteria

1. All 10 endpoints in handler.py use session-based auth
2. `verify_api_key()` function deleted
3. `API_KEY` env var removed from Lambda config
4. All tests pass with session tokens
5. E2E smoke test confirms public endpoints accept anonymous sessions

## Risks

| Risk | Mitigation |
|------|------------|
| External clients using API key | Verify no external integrations exist |
| CI/CD uses API key | Update CI environment to use session tokens |
| Performance regression | Anonymous sessions skip DynamoDB validation |

## Out of Scope

- Admin role system (chaos endpoints can stay on "authenticated only" for now)
- Rate limiting by user (future feature)
- API key deprecation period (no external clients identified)
