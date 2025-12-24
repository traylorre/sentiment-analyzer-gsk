# Feature 1039: Tasks

## Implementation Tasks

- [ ] **1.1** Add import for `get_user_id_from_request` to handler.py
- [ ] **1.2** Update `get_metrics_v2` to use session auth (line 545)
- [ ] **1.3** Update `get_sentiment_v2` to use session auth (line 612)
- [ ] **1.4** Update `get_trends_v2` to use session auth (line 692)
- [ ] **1.5** Update `get_articles_v2` to use session auth (line 794)
- [ ] **2.1** Update 6 chaos endpoints to use `get_authenticated_user_id`
- [ ] **3.1** Delete `verify_api_key` function and `api_key_header` declaration
- [ ] **3.2** Remove `get_api_key()` from config.py
- [ ] **3.3** Remove API_KEY from Terraform dashboard-lambda.tf
- [ ] **3.4** Update serve_index() to remove API key injection
- [ ] **4.1** Update unit tests to use session tokens
- [ ] **4.2** Update conftest.py fixtures
- [ ] **4.3** Update E2E api_client.py

## Verification

- [ ] `ruff check src/lambdas/dashboard/handler.py`
- [ ] `pytest tests/unit/dashboard/test_handler.py -v`
- [ ] `grep -r "verify_api_key" src/` returns nothing
- [ ] `grep -r "API_KEY" infrastructure/terraform/dashboard-lambda.tf` returns nothing
