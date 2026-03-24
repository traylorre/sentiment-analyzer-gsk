# Tasks: Admin Dashboard Lockdown

## Phase 1: Core Implementation (handler.py)

- [ ] T001 Add `_is_dev_environment()` helper to `src/lambdas/dashboard/handler.py` (after line 91): returns `True` only if `os.environ.get("ENVIRONMENT", "").lower()` is in `{"local", "dev", "test"}`. Fail-closed: unset/empty/unknown = locked. Use `.lower()` for case-insensitive matching.

- [ ] T002 Add environment gate to admin routes in `src/lambdas/dashboard/handler.py`:
  - `serve_index()` (GET /): if not `_is_dev_environment()`, return 404 with `{"detail": "Not found"}`
  - `serve_chaos()` (GET /chaos): same
  - `serve_static()` (GET /static/*): same
  - `api_index()` (GET /api): same
  - Add new route `GET /favicon.ico`: return 404 if not dev, else serve favicon

- [ ] T003 Strip `/health` response in non-dev: modify `health_check()` (handler.py:374) to return only `{"status":"healthy"}` when not `_is_dev_environment()`. Keep full response (table, env) in dev. Keep status value as `"healthy"` — deploy smoke tests (deploy.yml:1167, 2033) check valid JSON and grep for `"status"` key only. Also strip the unhealthy/503 response branch: return `{"status":"unhealthy"}` without `table` or `error` details in non-dev.

- [ ] T004 Strip `/api/v2/runtime` response in non-dev: modify `get_runtime_config()` (handler.py:410) to return `{"sse_url": null, "environment": "production"}` when not `_is_dev_environment()`. Full response in dev only. The literal string `"production"` is a generic label — never expose the actual ENVIRONMENT value.

## Phase 2: Auth Fixes

- [ ] T005 Add auth + ownership to refresh/status endpoint in `src/lambdas/dashboard/router_v2.py:1261`:
  ```python
  @config_router.get("/api/v2/configurations/<config_id>/refresh/status")
  def get_refresh_status(config_id: str):
      event = config_router.current_event.raw_event
      table = get_users_table()
      user_id, err = _require_user_id(event, table=table)
      if err:
          return err
      # Ownership check: verify config belongs to this user
      configs_table = get_sentiments_table()
      config_item = configs_table.get_item(Key={"PK": f"CONFIG#{config_id}", "SK": "METADATA"}).get("Item")
      if not config_item or config_item.get("user_id") != user_id:
          return error_response(403, "Not authorized to access this configuration")
      result = market_service.get_refresh_status(config_id=config_id)
      return json_response(200, result.model_dump())
  ```
  Note: Check the actual config key schema before implementing — the PK/SK pattern above is illustrative. Verify against existing config CRUD endpoints in router_v2.py for the correct key structure.

- [ ] T006 Implement session validation in `_get_user_id_from_event()` (handler.py:129):
  1. Add imports at top of handler.py (after line 69):
     ```python
     from src.lambdas.dashboard import auth as auth_service
     from src.lambdas.shared.errors import SessionRevokedException
     ```
  2. Modify function to validate session when `validate_session=True`:
     ```python
     def _get_user_id_from_event(event: dict, validate_session: bool = True) -> str:
         auth_context = extract_auth_context(event)
         user_id = auth_context.get("user_id")
         if not user_id:
             return ""
         if validate_session:
             try:
                 table = get_table(USERS_TABLE)
                 validation = auth_service.validate_session(
                     table=table, anonymous_id=user_id
                 )
                 if not validation.valid:
                     return ""
             except SessionRevokedException:
                 return ""
             except Exception:
                 logger.warning("Session validation failed", exc_info=True)
                 return ""
         return user_id
     ```
  3. Return `""` (not None) for consistency with existing callers that check `if not _user_id:`.
  4. Catch `Exception` broadly to prevent session validation failures from crashing data endpoints — degraded access is better than 500.

- [ ] T007 Remove `validate_session=False` from the 4 data endpoints in handler.py:
  - Line 431: `get_metrics_v2()` — change to `_get_user_id_from_event(event)` (default True)
  - Line 483: `get_sentiment_v2()` — same
  - Line 547: `get_trends_v2()` — same
  - Line 656: `get_articles_v2()` — same
  - DO NOT change router_v2.py:718 (`refresh_session()`) — it intentionally uses `validate_session=False` because a session that's about to expire still needs to be refreshable. The CSRF middleware (`require_csrf_middleware`) provides its own validation layer. Add a code comment explaining this rationale at line 718.

## Phase 3: Tests

- [ ] T008 Add unit test `tests/unit/test_admin_lockdown.py`:
  1. `test_is_dev_environment_local` — ENVIRONMENT=local → True
  2. `test_is_dev_environment_dev` — ENVIRONMENT=dev → True
  3. `test_is_dev_environment_test` — ENVIRONMENT=test → True
  4. `test_is_dev_environment_preprod` — ENVIRONMENT=preprod → False
  5. `test_is_dev_environment_prod` — ENVIRONMENT=prod → False
  6. `test_is_dev_environment_unset` — ENVIRONMENT="" → False (fail-closed)
  7. `test_is_dev_environment_unknown` — ENVIRONMENT="staging" → False
  8. `test_is_dev_environment_case_insensitive` — ENVIRONMENT="DEV" → True, ENVIRONMENT="Local" → True
  9. `test_root_returns_404_in_preprod` — mock ENVIRONMENT=preprod, GET / → 404
  10. `test_chaos_returns_404_in_preprod` — mock ENVIRONMENT=preprod, GET /chaos → 404
  11. `test_health_stripped_in_preprod` — mock ENVIRONMENT=preprod, GET /health → only `{"status":"healthy"}`, no `table` or `environment` keys
  12. `test_health_full_in_dev` — mock ENVIRONMENT=dev, GET /health → table + environment keys present
  13. `test_runtime_stripped_in_preprod` — mock ENVIRONMENT=preprod, GET /api/v2/runtime → `{"sse_url": null, "environment": "production"}`
  14. `test_runtime_full_in_dev` — mock ENVIRONMENT=dev, GET /api/v2/runtime → real sse_url present
  15. `test_refresh_status_requires_auth` — GET /api/v2/configurations/{id}/refresh/status without token → 401
  16. `test_refresh_status_ownership_check` — GET with user A's token for user B's config → 403
  17. `test_session_validation_rejects_expired` — mock expired session, call `_get_user_id_from_event(event, validate_session=True)` → returns ""
  18. `test_session_validation_allows_valid` — mock valid session → returns user_id
  19. `test_session_validation_graceful_on_error` — mock DynamoDB error during validation → returns "" (not 500)

- [ ] T009 Add E2E test `tests/e2e/test_admin_lockdown_preprod.py` with marker `@pytest.mark.preprod`:
  1. `test_root_returns_404` — GET / returns 404
  2. `test_chaos_returns_404` — GET /chaos returns 404
  3. `test_static_returns_404` — GET /static/app.js returns 404
  4. `test_api_index_returns_404` — GET /api returns 404
  5. `test_health_stripped` — GET /health returns 200, response has `status` key but NOT `table` or `environment` keys
  6. `test_runtime_stripped` — GET /api/v2/runtime returns 200 with `sse_url` null and `environment` "production"
  7. `test_refresh_status_requires_auth` — GET /api/v2/configurations/fake-id/refresh/status returns 401
  8. `test_api_v2_still_works` — POST /api/v2/auth/anonymous returns 201

- [ ] T010 Update existing test fixtures that call the 4 data endpoints (metrics, sentiment, trends, articles). These tests may pass `validate_session=False` explicitly or rely on no validation. After T006/T007, they must provide mock session validation to pass. Check `tests/unit/test_dashboard_handler.py` for any assertions on the old health response shape (`"table"` key, etc.) and update to match new stripped shape.

## Phase 4: Verify

- [ ] T011 Run backend unit tests: `python -m pytest tests/unit/ -x -q --timeout=120`
- [ ] T012 Run `make validate`
- [ ] T013 **[MANUAL]** After deploy: verify each success criterion (SC-001 through SC-008)
