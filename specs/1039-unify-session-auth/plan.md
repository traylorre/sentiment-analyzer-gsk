# Feature 1039: Implementation Plan

## Phase 1: Public Endpoints Migration (handler.py)

### Step 1.1: Update get_metrics_v2 endpoint
**File**: `src/lambdas/dashboard/handler.py:545-610`
- Remove `_: bool = Depends(verify_api_key)` from signature
- Add `user_id = get_user_id_from_request(request, validate_session=False)` at function start
- Add import: `from src.lambdas.dashboard.router_v2 import get_user_id_from_request`
- Log user_id in existing logging

### Step 1.2: Update get_sentiment_v2 endpoint
**File**: `src/lambdas/dashboard/handler.py:612-690`
- Same pattern as Step 1.1

### Step 1.3: Update get_trends_v2 endpoint
**File**: `src/lambdas/dashboard/handler.py:692-792`
- Same pattern as Step 1.1

### Step 1.4: Update get_articles_v2 endpoint
**File**: `src/lambdas/dashboard/handler.py:794-885`
- Same pattern as Step 1.1

## Phase 2: Chaos Endpoints Migration

### Step 2.1: Update all 6 chaos endpoints
**File**: `src/lambdas/dashboard/handler.py:887-1150`
- Remove `Depends(verify_api_key)`
- Add `user_id = get_authenticated_user_id(request)` (requires non-anonymous)
- Import `get_authenticated_user_id` from router_v2

Affected endpoints:
- `create_chaos_experiment` (line 887)
- `list_chaos_experiments` (line 945)
- `get_chaos_experiment` (line 971)
- `start_chaos_experiment` (line 1021)
- `stop_chaos_experiment` (line 1063)
- `delete_chaos_experiment` (line 1104)

## Phase 3: Remove API Key Infrastructure

### Step 3.1: Delete verify_api_key function
**File**: `src/lambdas/dashboard/handler.py:193-274`
- Delete entire function
- Delete `api_key_header = APIKeyHeader(...)` declaration (find it)

### Step 3.2: Remove API_KEY from config
**File**: `src/lambdas/dashboard/config.py`
- Remove `get_api_key()` function
- Remove `API_KEY` loading

### Step 3.3: Remove API_KEY from Terraform
**File**: `infrastructure/terraform/dashboard-lambda.tf`
- Remove `API_KEY` from environment variables

### Step 3.4: Update HTML serving (if applicable)
**File**: `src/lambdas/dashboard/handler.py:serve_index()`
- Remove API key injection into JavaScript global

## Phase 4: Update Tests

### Step 4.1: Update unit tests
**File**: `tests/unit/dashboard/test_handler.py`
- Change all `Authorization: Bearer {API_KEY}` to session format
- Add mock for `extract_auth_context` or use test session tokens

### Step 4.2: Update conftest
**File**: `tests/conftest.py`
- Remove `API_KEY` fixture if present
- Ensure session token fixtures exist

### Step 4.3: Update E2E helpers
**File**: `tests/e2e/helpers/api_client.py`
- Use session auth instead of API key

## Testing Checklist

1. [ ] Unit tests pass: `pytest tests/unit/dashboard/test_handler.py -v`
2. [ ] Integration tests pass: `pytest tests/integration/ -v`
3. [ ] E2E smoke test: public endpoints accept anonymous UUID in X-User-ID
4. [ ] E2E smoke test: chaos endpoints reject anonymous, accept authenticated
5. [ ] No references to `verify_api_key` remain in codebase
6. [ ] No references to `API_KEY` in Lambda env config

## Rollback Plan

If issues found in preprod:
1. Git revert the PR
2. Terraform apply to restore API_KEY env var
3. Redeploy Lambda
