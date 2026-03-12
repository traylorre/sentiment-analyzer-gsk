# Tasks: Financial News Sentiment & Asset Volatility Dashboard

**Feature**: 006-user-config-dashboard | **Date**: 2025-11-26
**Input**: Design documents from `/specs/006-user-config-dashboard/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Testing requirements (TR-001 to TR-008) are specified - tests are INCLUDED per spec.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, new dependencies, and Terraform modules

- [x] T001 Create feature branch structure and update requirements.txt with new dependencies (aws-xray-sdk, sendgrid, httpx) in requirements.txt
- [x] T002 [P] Create Tiingo API secret in Secrets Manager via Terraform in infrastructure/terraform/modules/secrets/main.tf
- [x] T003 [P] Create Finnhub API secret in Secrets Manager via Terraform in infrastructure/terraform/modules/secrets/main.tf
- [x] T004 [P] Create SendGrid API secret in Secrets Manager via Terraform in infrastructure/terraform/modules/secrets/main.tf
- [x] T005 [P] Create hCaptcha secret in Secrets Manager via Terraform in infrastructure/terraform/modules/secrets/main.tf
- [x] T006 Create Cognito User Pool Terraform module in infrastructure/terraform/modules/cognito/main.tf
- [x] T007 [P] Configure Cognito Google OAuth identity provider in infrastructure/terraform/modules/cognito/google.tf
- [x] T008 [P] Configure Cognito GitHub OAuth identity provider in infrastructure/terraform/modules/cognito/github.tf
- [x] T009 Create CloudFront distribution Terraform module in infrastructure/terraform/modules/cloudfront/main.tf
- [x] T010 Configure X-Ray tracing on all Lambda functions in infrastructure/terraform/modules/lambda/xray.tf
- [x] T011 Create CloudWatch RUM application monitor in infrastructure/terraform/modules/cloudwatch-rum/main.tf
- [x] T012 Update main.tf to include new modules in infrastructure/terraform/main.tf
- [ ] T013 ⏸️ DEFERRED: Run terraform init and apply for dev environment
  - **Reason**: Dev environment creates real AWS resources but tests use moto (mocked AWS). Only value is terraform syntax validation, which preprod deploy provides. Cost savings by skipping.

**Checkpoint**: Infrastructure foundation ready - secrets, Cognito, CDN, and X-Ray configured

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Shared Models & Utilities

- [x] T014 Create User model with DynamoDB keys in src/lambdas/shared/models/user.py
- [x] T015 [P] Create Configuration model with DynamoDB keys in src/lambdas/shared/models/configuration.py
- [x] T016 [P] Create AlertRule model with DynamoDB keys in src/lambdas/shared/models/alert_rule.py
- [x] T017 [P] Create Notification model with DynamoDB keys in src/lambdas/shared/models/notification.py
- [x] T018 [P] Create SentimentResult model with DynamoDB keys in src/lambdas/shared/models/sentiment_result.py
- [x] T019 [P] Create VolatilityMetric model with DynamoDB keys in src/lambdas/shared/models/volatility_metric.py
- [x] T020 [P] Create MagicLinkToken model with validation in src/lambdas/shared/models/magic_link_token.py
- [x] T021 Create models __init__.py exporting all models in src/lambdas/shared/models/__init__.py

### Circuit Breaker & Quota Management

- [x] T022 Implement CircuitBreakerState class in src/lambdas/shared/circuit_breaker.py
- [x] T023 [P] Implement QuotaTracker class in src/lambdas/shared/quota_tracker.py
- [x] T024 Unit tests for circuit breaker in tests/unit/shared/test_circuit_breaker.py
- [x] T025 [P] Unit tests for quota tracker in tests/unit/shared/test_quota_tracker.py

### Ticker Cache

- [x] T026 Create TickerCache class with S3 loading in src/lambdas/shared/cache/ticker_cache.py
- [x] T027 [P] Create initial US symbols JSON file (~8K symbols) in infrastructure/data/us-symbols.json
- [x] T028 [P] Upload ticker cache to S3 via Terraform in infrastructure/terraform/modules/s3/ticker_cache.tf
- [x] T029 Unit tests for ticker cache in tests/unit/shared/test_ticker_cache.py

### Financial API Adapters

- [x] T030 Create base adapter interface in src/lambdas/ingestion/adapters/base.py
- [x] T031 Implement TiingoAdapter with rate limiting and caching in src/lambdas/shared/adapters/tiingo.py
- [x] T032 [P] Implement FinnhubAdapter with rate limiting and caching in src/lambdas/shared/adapters/finnhub.py
- [x] T033 Unit tests for TiingoAdapter with mocked responses in tests/unit/shared/adapters/test_tiingo.py
- [x] T034 [P] Unit tests for FinnhubAdapter with mocked responses in tests/unit/shared/adapters/test_finnhub.py

### ATR Calculation

- [x] T035 Implement ATR calculator with OHLC input in src/lambdas/shared/volatility.py
- [x] T036 Unit tests for ATR calculation in tests/unit/shared/test_volatility.py

### Notification Lambda Scaffold

- [x] T037 Create notification Lambda handler scaffold in src/lambdas/notification/handler.py
- [x] T038 [P] Implement SendGrid email service in src/lambdas/notification/sendgrid_service.py
- [x] T039 Unit tests for SendGrid service with mocked API in tests/unit/lambdas/notification/test_sendgrid_service.py
- [x] T040 Add notification Lambda to Terraform in infrastructure/terraform/modules/lambda/notification.tf

### Synthetic Test Data Framework (E2E Testing Infrastructure)

- [x] T040a Create synthetic data generator for ticker prices/OHLC in tests/fixtures/synthetic/ticker_generator.py
- [x] T040b [P] Create synthetic data generator for sentiment scores in tests/fixtures/synthetic/sentiment_generator.py
- [x] T040c [P] Create synthetic data generator for news articles in tests/fixtures/synthetic/news_generator.py
- [x] T040d Create test oracle that computes expected outcomes from synthetic data in tests/fixtures/synthetic/test_oracle.py
- [x] T040e [P] Create mock Tiingo adapter that returns synthetic data in tests/fixtures/mocks/mock_tiingo.py
- [x] T040f [P] Create mock Finnhub adapter that returns synthetic data in tests/fixtures/mocks/mock_finnhub.py
- [x] T040g [P] Create mock SendGrid adapter for email verification in tests/fixtures/mocks/mock_sendgrid.py
- [x] T040h Create E2E test base class with synthetic data setup in tests/e2e/conftest.py
- [x] T040i Unit tests for synthetic data generators in tests/unit/fixtures/test_synthetic_generators.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Instant Anonymous Access (Priority: P1) 🎯 MVP

**Goal**: Zero-friction anonymous access with dual-source sentiment visualization and ATR correlation

**Independent Test**: Visit site on mobile, enter 5 tickers and timeframe, see dual-source sentiment charts with volatility correlation render within 10 seconds.

**Acceptance Criteria**:
1. New visitor sees clean ticker input without login prompts + "upgrade to save" prompt
2. User enters 5 tickers, selects timeframe, sees Tiingo AND Finnhub results in <10s
3. Charts reflow responsively on device rotation
4. Returning user on same device sees restored config via localStorage
5. Heat map matrix, ATR correlation with trend arrows, color-coded scores visible

### Tests for User Story 1

- [x] T041 [P] [US1] Contract tests for anonymous session endpoints in tests/contract/test_anonymous_session.py
- [x] T042 [P] [US1] Contract tests for configuration CRUD endpoints in tests/contract/test_configuration_api.py
- [x] T043 [P] [US1] Contract tests for sentiment data endpoints in tests/contract/test_sentiment_api.py
- [x] T044 [P] [US1] Contract tests for volatility endpoints in tests/contract/test_volatility_api.py
- [x] T045 [P] [US1] Contract tests for heat map data endpoint in tests/contract/test_heatmap_api.py
- [x] T046 [US1] Integration test for anonymous user full journey in tests/integration/test_us1_anonymous_journey.py

### Backend Implementation for User Story 1

- [x] T047 [US1] Implement anonymous session creation endpoint (POST /api/v2/auth/anonymous) in src/lambdas/dashboard/api_v2.py
- [x] T048 [US1] Implement anonymous session validation endpoint (GET /api/v2/auth/validate) in src/lambdas/dashboard/api_v2.py
- [x] T049 [US1] Implement configuration creation endpoint (POST /api/v2/configurations) in src/lambdas/dashboard/api_v2.py
- [x] T050 [US1] Implement configuration list endpoint (GET /api/v2/configurations) in src/lambdas/dashboard/api_v2.py
- [x] T051 [US1] Implement single configuration endpoint (GET /api/v2/configurations/{id}) in src/lambdas/dashboard/api_v2.py
- [x] T052 [US1] Implement configuration update endpoint (PATCH /api/v2/configurations/{id}) in src/lambdas/dashboard/api_v2.py
- [x] T053 [US1] Implement configuration delete endpoint (DELETE /api/v2/configurations/{id}) in src/lambdas/dashboard/api_v2.py
- [x] T054 [US1] Implement ticker validation endpoint (GET /api/v2/tickers/validate) in src/lambdas/dashboard/api_v2.py
- [x] T055 [US1] Implement ticker search/autocomplete endpoint (GET /api/v2/tickers/search) in src/lambdas/dashboard/api_v2.py
- [x] T056 [US1] Implement sentiment by configuration endpoint (GET /api/v2/configurations/{id}/sentiment) in src/lambdas/dashboard/api_v2.py
- [x] T057 [US1] Implement heat map data endpoint (GET /api/v2/configurations/{id}/heatmap) in src/lambdas/dashboard/api_v2.py
- [x] T058 [US1] Implement volatility/ATR endpoint (GET /api/v2/configurations/{id}/volatility) in src/lambdas/dashboard/api_v2.py
- [x] T059 [US1] Implement sentiment-volatility correlation endpoint (GET /api/v2/configurations/{id}/correlation) in src/lambdas/dashboard/api_v2.py
- [x] T060 [US1] Implement refresh status endpoint (GET /api/v2/configurations/{id}/refresh/status) in src/lambdas/dashboard/api_v2.py
- [x] T061 [US1] Implement manual refresh trigger endpoint (POST /api/v2/configurations/{id}/refresh) in src/lambdas/dashboard/api_v2.py
- [x] T062 [US1] Implement market status endpoint (GET /api/v2/market/status) in src/lambdas/dashboard/api_v2.py
- [x] T063 [US1] Implement pre-market estimates endpoint (GET /api/v2/configurations/{id}/premarket) in src/lambdas/dashboard/api_v2.py

### Ingestion Pipeline Updates for User Story 1

- [x] T064 [US1] Update ingestion handler to use Tiingo/Finnhub adapters in src/lambdas/ingestion/financial_handler.py
- [x] T065 [US1] Implement dual-source sentiment aggregation in src/lambdas/analysis/sentiment.py
- [x] T066 [US1] Add X-Ray tracing to ingestion handler in src/lambdas/ingestion/handler.py
- [x] T067 [US1] Add X-Ray tracing to analysis handler in src/lambdas/analysis/handler.py

### Frontend Implementation for User Story 1

- [ ] T068 [P] [US1] Create TickerInput component with autocomplete in src/dashboard/components/TickerInput.tsx
- [ ] T069 [P] [US1] Create TimeframeSelector component in src/dashboard/components/TimeframeSelector.tsx
- [ ] T070 [P] [US1] Create SentimentChart component for dual-source display in src/dashboard/components/SentimentChart.tsx
- [ ] T071 [P] [US1] Create HeatMap component with Recharts in src/dashboard/components/HeatMap.tsx
- [ ] T072 [P] [US1] Create VolatilityDisplay component with ATR and trend arrows in src/dashboard/components/VolatilityDisplay.tsx
- [ ] T073 [P] [US1] Create RefreshTimer component with countdown in src/dashboard/components/RefreshTimer.tsx
- [ ] T074 [P] [US1] Create UpgradePrompt component for anonymous users in src/dashboard/components/UpgradePrompt.tsx
- [ ] T075 [US1] Create localStorage service for anonymous session in src/dashboard/services/localStorage.ts
- [ ] T076 [US1] Create API client service in src/dashboard/services/api.ts
- [ ] T077 [US1] Create Dashboard page assembling all components in src/dashboard/pages/Dashboard.tsx
- [ ] T078 [US1] Implement mobile-first responsive layout in src/dashboard/styles/responsive.css
- [ ] T079 [US1] Add loading skeletons and progress indicators in src/dashboard/components/LoadingSkeleton.tsx

### Frontend Tests for User Story 1

- [ ] T080 [P] [US1] Component tests for TickerInput at key breakpoints in tests/unit/dashboard/test_TickerInput.tsx
- [ ] T081 [P] [US1] Component tests for HeatMap responsiveness in tests/unit/dashboard/test_HeatMap.tsx
- [ ] T082 [P] [US1] Component tests for SentimentChart in tests/unit/dashboard/test_SentimentChart.tsx
- [ ] T083 [US1] E2E test for anonymous user flow in tests/e2e/test_anonymous_flow.py

**Checkpoint**: User Story 1 complete - anonymous users can view dual-source sentiment with ATR correlation

---

## Phase 4: User Story 2 - Persist Identity & Cross-Device Access (Priority: P2)

**Goal**: Users can upgrade from anonymous to authenticated via magic link or OAuth, with data merge

**Independent Test**: Create anonymous config, authenticate via email or Google, verify data persists across devices/browsers.

**Acceptance Criteria**:
1. Anonymous user with config can enter email and receive magic link within 60s
2. Magic link click within 1 hour merges data and shows authenticated view
3. "Sign in with Google" completes OAuth flow and associates data
4. Authenticated user on Device A sees data when signing in on Device B
5. localStorage cleared shows "Sign in to restore" prompt

### Tests for User Story 2

- [x] T084 [P] [US2] Contract tests for magic link request/verify in tests/contract/test_magic_link_api.py
- [x] T085 [P] [US2] Contract tests for OAuth URLs and callback in tests/contract/test_oauth_api.py
- [x] T086 [P] [US2] Contract tests for token refresh in tests/contract/test_token_refresh_api.py
- [x] T087 [P] [US2] Contract tests for session management in tests/contract/test_session_api.py
- [x] T088 [US2] Integration test for magic link full flow in tests/integration/test_us2_magic_link.py
- [x] T089 [US2] Integration test for OAuth flow with Cognito in tests/integration/test_us2_oauth.py

### Backend Implementation for User Story 2

- [x] T090 [US2] Implement magic link request endpoint (POST /api/v2/auth/magic-link) in src/lambdas/dashboard/auth.py
- [x] T091 [US2] Implement magic link verification endpoint (GET /api/v2/auth/magic-link/verify) in src/lambdas/dashboard/auth.py
- [x] T092 [US2] Implement OAuth URLs endpoint (GET /api/v2/auth/oauth/urls) in src/lambdas/dashboard/auth.py
- [x] T093 [US2] Implement OAuth callback endpoint (POST /api/v2/auth/oauth/callback) in src/lambdas/dashboard/auth.py
- [x] T094 [US2] Implement token refresh endpoint (POST /api/v2/auth/refresh) in src/lambdas/dashboard/auth.py
- [x] T095 [US2] Implement sign out endpoint (POST /api/v2/auth/signout) in src/lambdas/dashboard/auth.py
- [x] T096 [US2] Implement session info endpoint (GET /api/v2/auth/session) in src/lambdas/dashboard/auth.py
- [x] T097 [US2] Implement account linking check endpoint (POST /api/v2/auth/check-email) in src/lambdas/dashboard/auth.py
- [x] T098 [US2] Implement account linking endpoint (POST /api/v2/auth/link-accounts) in src/lambdas/dashboard/auth.py
- [x] T099 [US2] Implement merge status endpoint (GET /api/v2/auth/merge-status) in src/lambdas/dashboard/auth.py
- [x] T100 [US2] Implement anonymous data merge logic in src/lambdas/shared/auth/merge.py
- [x] T101 [US2] Implement Cognito token validation helper in src/lambdas/shared/auth/cognito.py
- [x] T102 [US2] Create magic link email template for SendGrid in src/lambdas/notification/templates/magic_link.html
- [x] T103 [US2] Add X-Ray tracing to auth handler in src/lambdas/dashboard/auth.py

### Frontend Implementation for User Story 2

- [ ] T104 [P] [US2] Create AuthFlow component with magic link and OAuth buttons in src/dashboard/components/AuthFlow.tsx
- [ ] T105 [P] [US2] Create MagicLinkInput component for email entry in src/dashboard/components/MagicLinkInput.tsx
- [ ] T106 [P] [US2] Create OAuthButtons component for Google/GitHub in src/dashboard/components/OAuthButtons.tsx
- [ ] T107 [US2] Create auth callback page for magic link verification in src/dashboard/pages/AuthCallback.tsx
- [ ] T108 [US2] Create OAuth callback page for Cognito redirect in src/dashboard/pages/OAuthCallback.tsx
- [ ] T109 [US2] Update localStorage service for token management in src/dashboard/services/localStorage.ts
- [ ] T110 [US2] Create auth context provider for session state in src/dashboard/contexts/AuthContext.tsx
- [ ] T111 [US2] Update Dashboard page with auth-aware UI in src/dashboard/pages/Dashboard.tsx

### Frontend Tests for User Story 2

- [ ] T112 [P] [US2] Component tests for AuthFlow in tests/unit/dashboard/test_AuthFlow.tsx
- [ ] T113 [US2] E2E test for magic link authentication flow in tests/e2e/test_magic_link_auth.py
- [ ] T114 [US2] E2E test for OAuth authentication flow in tests/e2e/test_oauth_auth.py

**Checkpoint**: User Stories 1 AND 2 complete - users can authenticate and persist data across devices

---

## Phase 5: User Story 3 - Dual Configuration Comparison (Priority: P3)

**Goal**: Users can create and switch between 2 configurations with independent tickers and timeframes

**Independent Test**: Create Config A (5 tech tickers, 30 days), then Config B (5 EV tickers, 14 days), verify both appear in config switcher with independent chart views.

**Acceptance Criteria**:
1. User with one config can click "Add new configuration" to create second
2. User with two configs sees configuration switcher (tabs/dropdown)
3. Switching configs updates charts to show selected config's data
4. Each config maintains independent timeframe
5. Attempting third config shows "max 2 configurations" message
6. Heat map toggle between "Sources" and "Time Periods" views works

### Tests for User Story 3

- [x] T115 [P] [US3] Contract tests for multiple configurations in tests/contract/test_multi_config_api.py
- [x] T116 [US3] Integration test for config switching in tests/integration/test_us3_config_switch.py

### Backend Implementation for User Story 3

- [x] T117 [US3] Add max 2 config validation to configuration endpoints in src/lambdas/dashboard/configurations.py
  - Implemented in create_configuration() lines 106-113: checks existing_count >= max_configs_per_user
- [x] T118 [US3] Implement config count validation on create in src/lambdas/dashboard/configurations.py
  - Implemented in _count_user_configurations() lines 429-441: counts active configs

### Frontend Implementation for User Story 3

- [ ] T119 [P] [US3] Create ConfigSwitcher component (tabs/dropdown) in src/dashboard/components/ConfigSwitcher.tsx
- [ ] T120 [P] [US3] Create ConfigCard component for config display in src/dashboard/components/ConfigCard.tsx
- [ ] T121 [P] [US3] Create AddConfigButton component in src/dashboard/components/AddConfigButton.tsx
- [ ] T122 [US3] Create ConfigManager page for CRUD operations in src/dashboard/pages/ConfigManager.tsx
- [ ] T123 [US3] Update HeatMap component with view toggle (Sources/Time Periods) in src/dashboard/components/HeatMap.tsx
- [ ] T124 [US3] Update Dashboard page with config switching logic in src/dashboard/pages/Dashboard.tsx

### Frontend Tests for User Story 3

- [ ] T125 [P] [US3] Component tests for ConfigSwitcher in tests/unit/dashboard/test_ConfigSwitcher.tsx
- [ ] T126 [US3] E2E test for dual config workflow in tests/e2e/test_dual_config.py

**Checkpoint**: User Stories 1, 2, AND 3 complete - full config management with switching

---

## Phase 6: User Story 4 - Volatility & Sentiment Alerts (Priority: P4)

**Goal**: Authenticated users can set sentiment and volatility threshold alerts with email notifications

**Independent Test**: Set low threshold, wait for trigger, verify email delivery with deep link.

**Acceptance Criteria**:
1. Authenticated user sees "Set up alerts" option per ticker
2. Sentiment threshold alert (-0.3) triggers email within 15 minutes
3. ATR volatility alert (3%) triggers email on spike
4. Email contains deep link to relevant config view
5. User can toggle off alerts per ticker or globally

### Tests for User Story 4

- [x] T127 [P] [US4] Contract tests for alert CRUD endpoints in tests/contract/test_alerts_api.py
- [x] T128 [P] [US4] Contract tests for notification endpoints in tests/contract/test_notifications_api.py
- [x] T129 [P] [US4] Contract tests for digest endpoints in tests/contract/test_digest_api.py
- [x] T130 [US4] Integration test for alert trigger and email delivery in tests/integration/test_us4_alert_flow.py

### Backend Implementation for User Story 4

- [x] T131 [US4] Implement alert list endpoint (GET /api/v2/alerts) in src/lambdas/dashboard/alerts.py
- [x] T132 [US4] Implement alert create endpoint (POST /api/v2/alerts) in src/lambdas/dashboard/alerts.py
- [x] T133 [US4] Implement alert get endpoint (GET /api/v2/alerts/{id}) in src/lambdas/dashboard/alerts.py
- [x] T134 [US4] Implement alert update endpoint (PATCH /api/v2/alerts/{id}) in src/lambdas/dashboard/alerts.py
- [x] T135 [US4] Implement alert delete endpoint (DELETE /api/v2/alerts/{id}) in src/lambdas/dashboard/alerts.py
- [x] T136 [US4] Implement alert toggle endpoint (POST /api/v2/alerts/{id}/toggle) in src/lambdas/dashboard/alerts.py
- [x] T137 [US4] Implement notification list endpoint (GET /api/v2/notifications) in src/lambdas/dashboard/notifications.py
- [x] T138 [US4] Implement notification detail endpoint (GET /api/v2/notifications/{id}) in src/lambdas/dashboard/notifications.py
- [x] T139 [US4] Implement notification preferences endpoints (GET/PATCH /api/v2/notifications/preferences) in src/lambdas/dashboard/notifications.py
- [x] T140 [US4] Implement disable all notifications endpoint (POST /api/v2/notifications/disable-all) in src/lambdas/dashboard/notifications.py
- [x] T141 [US4] Implement unsubscribe endpoint (GET /api/v2/notifications/unsubscribe) in src/lambdas/dashboard/notifications.py
- [x] T142 [US4] Implement resubscribe endpoint (POST /api/v2/notifications/resubscribe) in src/lambdas/dashboard/notifications.py
- [x] T143 [US4] Implement digest settings endpoints (GET/PATCH /api/v2/notifications/digest) in src/lambdas/dashboard/notifications.py
- [x] T144 [US4] Implement test digest endpoint (POST /api/v2/notifications/digest/test) in src/lambdas/dashboard/notifications.py
- [x] T145 [US4] Implement alert evaluation logic in notification Lambda in src/lambdas/notification/alert_evaluator.py
- [x] T146 [US4] Implement internal alert evaluation endpoint (POST /api/internal/alerts/evaluate) in src/lambdas/notification/alert_evaluator.py
- [x] T147 [US4] Implement internal email quota endpoint (GET /api/internal/email-quota) in src/lambdas/notification/alert_evaluator.py
- [x] T148 [US4] Create sentiment alert email template in src/lambdas/notification/templates/sentiment_alert.html
- [x] T149 [US4] Create volatility alert email template in src/lambdas/notification/templates/volatility_alert.html
- [x] T150 [US4] Create daily digest email template in src/lambdas/notification/templates/daily_digest.html
- [x] T151 [US4] Implement daily digest scheduler (EventBridge) in infrastructure/terraform/modules/eventbridge/main.tf
- [x] T152 [US4] Add CloudWatch alarm for SendGrid quota (50%) in infrastructure/terraform/main.tf
- [x] T153 [US4] Add X-Ray tracing to notification handler in src/lambdas/notification/handler.py

### Frontend Implementation for User Story 4

- [ ] T154 [P] [US4] Create AlertManager component for CRUD operations in src/dashboard/components/AlertManager.tsx
- [ ] T155 [P] [US4] Create AlertRuleForm component for threshold entry in src/dashboard/components/AlertRuleForm.tsx
- [ ] T156 [P] [US4] Create AlertList component showing active alerts in src/dashboard/components/AlertList.tsx
- [ ] T157 [P] [US4] Create NotificationHistory component in src/dashboard/components/NotificationHistory.tsx
- [ ] T158 [P] [US4] Create NotificationPreferences component in src/dashboard/components/NotificationPreferences.tsx
- [ ] T159 [US4] Create Alerts page assembling alert components in src/dashboard/pages/Alerts.tsx
- [ ] T160 [US4] Update Dashboard with alert setup entry point per ticker in src/dashboard/pages/Dashboard.tsx

### Frontend Tests for User Story 4

- [ ] T161 [P] [US4] Component tests for AlertManager in tests/unit/dashboard/test_AlertManager.tsx
- [ ] T162 [US4] E2E test for alert creation and notification flow in tests/e2e/test_alert_notification.py

**Checkpoint**: All user stories complete - full alerting functionality with email notifications

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, security hardening, and final validation

### Security & Validation

- [x] T163 [P] Implement hCaptcha integration for anonymous config creation in src/lambdas/shared/middleware/hcaptcha.py
- [x] T164 [P] Add IP-based rate limiting middleware in src/lambdas/shared/middleware/rate_limit.py
- [x] T165 Add security headers to all Lambda responses in src/lambdas/shared/middleware/security_headers.py
- [ ] T166 Implement inline field validation error display in src/dashboard/components/FieldError.tsx
- [ ] T167 Add OWASP security audit checklist validation

### Observability

- [ ] T168 [P] Integrate CloudWatch RUM in frontend in src/dashboard/services/rum.ts
- [ ] T169 [P] Create CloudWatch dashboard for sentiment analyzer in infrastructure/terraform/modules/cloudwatch/dashboard.tf
- [ ] T170 Add cost burn rate alarm ($3.33/day threshold) in infrastructure/terraform/modules/cloudwatch/cost_alarm.tf
- [ ] T171 Add Tiingo/Finnhub error rate alarms (>5%) in infrastructure/terraform/modules/cloudwatch/api_alarms.tf
- [ ] T172 Add notification delivery success alarm (<95%) in infrastructure/terraform/modules/cloudwatch/notification_alarm.tf

### Documentation & Cleanup

- [ ] T173 [P] Update CLAUDE.md with new commands and patterns
- [ ] T174 [P] Update quickstart.md with actual test commands and outputs in specs/006-user-config-dashboard/quickstart.md
- [ ] T175 Remove deprecated NewsAPI adapter code in src/lambdas/ingestion/adapters/ (if exists)
- [ ] T176 Verify all API endpoints match contracts in contracts/*.md

### Final Testing

- [ ] T177 Run full integration test suite against preprod
- [ ] T178 Verify 3s dashboard load on simulated 3G in performance test
- [ ] T179 Verify 2s config switch for 95th percentile
- [ ] T180 Verify mobile responsiveness at 320px, 768px, 1024px, 1440px breakpoints
- [ ] T181 Run quickstart.md validation end-to-end
- [ ] T182 Final coverage check (maintain >80% threshold)

**Checkpoint**: Feature 006 complete and production-ready

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup          → No dependencies - can start immediately
                        ↓
Phase 2: Foundational   → Depends on Phase 1 - BLOCKS all user stories
                        ↓
        ┌───────────────┼───────────────┬───────────────┐
        ↓               ↓               ↓               ↓
Phase 3: US1 (P1)   Phase 4: US2 (P2)   Phase 5: US3 (P3)   Phase 6: US4 (P4)
  🎯 MVP               Depends on US1      Depends on US1     Depends on US2
                       for auth UI         for config logic   for email delivery
        │               │               │               │
        └───────────────┴───────────────┴───────────────┘
                                ↓
Phase 7: Polish         → Depends on all desired user stories
```

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 2 - No dependencies on other stories ✅
- **User Story 2 (P2)**: Can start after Phase 2 - Integrates with US1 auth UI but independently testable
- **User Story 3 (P3)**: Can start after Phase 2 - Uses config logic from US1 but independently testable
- **User Story 4 (P4)**: Requires US2 complete (needs authenticated user for email alerts)

### Within Each User Story

1. Tests written FIRST and must FAIL before implementation (TDD)
2. Models before services
3. Backend endpoints before frontend components
4. Core implementation before integration
5. Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```bash
# Can run in parallel:
Task T002: Create Tiingo secret
Task T003: Create Finnhub secret
Task T004: Create SendGrid secret
Task T005: Create hCaptcha secret
Task T007: Configure Google OAuth
Task T008: Configure GitHub OAuth
```

**Phase 2 (Foundational)**:
```bash
# Can run in parallel:
Task T015-T020: All model files (different files)
Task T022-T023: Circuit breaker and quota tracker
Task T024-T025: Tests for above
Task T026-T028: Ticker cache components
Task T031-T032: Tiingo and Finnhub adapters
Task T033-T034: Adapter tests
```

**Phase 3 (US1)**:
```bash
# Tests can run in parallel:
Task T041-T045: All contract tests

# Frontend components can run in parallel:
Task T068-T074: All React components (different files)
```

---

## Parallel Example: User Story 1 Implementation

```bash
# Step 1: Launch all contract tests in parallel (should FAIL initially)
Task T041: Contract tests for anonymous session
Task T042: Contract tests for configuration CRUD
Task T043: Contract tests for sentiment data
Task T044: Contract tests for volatility
Task T045: Contract tests for heat map

# Step 2: Implement backend endpoints (some sequential, some parallel)
Task T047-T063: All API endpoints (sequential by dependency)

# Step 3: Launch all frontend components in parallel
Task T068: TickerInput component
Task T069: TimeframeSelector component
Task T070: SentimentChart component
Task T071: HeatMap component
Task T072: VolatilityDisplay component
Task T073: RefreshTimer component
Task T074: UpgradePrompt component

# Step 4: Integrate and test
Task T075-T079: Services and page assembly
Task T080-T083: Component and E2E tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (infrastructure foundation)
2. Complete Phase 2: Foundational (shared models, adapters, services)
3. Complete Phase 3: User Story 1 (anonymous access, sentiment display)
4. **STOP and VALIDATE**: Test US1 independently
5. Deploy to preprod for demo/review

**MVP Deliverable**: Anonymous users can view dual-source sentiment with ATR correlation

### Incremental Delivery

| Increment | User Stories | Value Delivered |
|-----------|--------------|-----------------|
| MVP       | US1 only     | Core sentiment visualization |
| Iteration 2 | US1 + US2  | Data persistence, auth |
| Iteration 3 | US1-3      | Multiple configurations |
| Full Release | US1-4    | Alerting and notifications |

### Parallel Team Strategy

With 2+ developers:

1. **Week 1**: Team completes Phase 1 + Phase 2 together
2. **Week 2-3**:
   - Developer A: User Story 1 (MVP)
   - Developer B: User Story 2 (can start backend while A does US1 frontend)
3. **Week 4**:
   - Developer A: User Story 3
   - Developer B: User Story 4
4. **Week 5**: Both on Phase 7 Polish

---

## Notes

- **[P] tasks** = different files, no dependencies - can run in parallel
- **[Story] label** maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests MUST fail before implementation (TDD per TR-001 to TR-008)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **80% coverage threshold** required (TR-008)

## Summary

| Phase | Tasks | Completed | Remaining | Notes |
|-------|-------|-----------|-----------|-------|
| Phase 1: Setup | 13 | 12 | 1 | Terraform apply pending |
| Phase 2: Foundational | 36 | 36 | 0 | ✅ Complete |
| Phase 3: US1 (Backend) | 27 | 27 | 0 | ✅ Backend complete |
| Phase 3: US1 (Frontend) | 16 | 0 | 16 | Frontend not started |
| Phase 4: US2 (Backend) | 20 | 20 | 0 | ✅ Backend complete |
| Phase 4: US2 (Frontend) | 11 | 0 | 11 | Frontend not started |
| Phase 5: US3 (Backend) | 4 | 2 | 2 | Tests done, backend pending |
| Phase 5: US3 (Frontend) | 8 | 0 | 8 | Frontend not started |
| Phase 6: US4 (Backend) | 23 | 13 | 10 | Alert evaluator done, API pending |
| Phase 6: US4 (Frontend) | 9 | 0 | 9 | Frontend not started |
| Phase 7: Security | 5 | 3 | 2 | Middleware complete |
| Phase 7: Observability | 5 | 0 | 5 | Not started |
| Phase 7: Docs & Final | 10 | 0 | 10 | Not started |
| **Total** | **191** | **113** | **78** | **59% Complete** |

**Backend Status**: ~90% complete (Phase 1-4 backend done, US3/US4 API endpoints remaining)
**Frontend Status**: 0% complete (No React components created yet)
**Infrastructure**: ~90% complete (Terraform apply for dev pending)

## Constitution Compliance Notes

Per constitution v1.1 (2025-11-26), all implementation follows:
- **Environment Matrix**: LOCAL/DEV = unit tests with mocks; PREPROD/PROD = E2E tests with real AWS
- **External Mocking**: Tiingo, Finnhub, SendGrid mocked in ALL environments (except canary/smoke)
- **Synthetic Data**: E2E tests use generated deterministic data with test oracle for assertions
- **Git Workflow**: Lint → Format → Sign → Push to feature branch → Monitor pipeline (30s retry)
- **No Bypass**: Pipeline checks are mandatory; fix failures, don't skip them
