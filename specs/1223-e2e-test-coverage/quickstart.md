# Quickstart: E2E Test Coverage Expansion (1223)

## Overview

This feature adds ~40 new E2E test cases across 6 test files, organized by user flow. All tests use Playwright against the preprod environment.

## Running Tests

```bash
# All new tests (Chromium only)
npx playwright test --project=chromium frontend/tests/auth/ frontend/tests/alerts/ frontend/tests/session/ frontend/tests/account/

# Specific user story
npx playwright test frontend/tests/auth/oauth-flow.spec.ts     # US1
npx playwright test frontend/tests/auth/magic-link.spec.ts     # US2
npx playwright test frontend/tests/alerts/crud.spec.ts         # US3
npx playwright test frontend/tests/session/lifecycle.spec.ts   # US4
npx playwright test frontend/tests/account/linking.spec.ts     # US5

# Cross-browser (existing sanity suite)
npx playwright test frontend/tests/sanity.spec.ts --project=firefox
npx playwright test frontend/tests/sanity.spec.ts --project=webkit

# All browsers, all tests
npx playwright test
```

## Environment Requirements

- `DASHBOARD_FUNCTION_URL` — preprod Dashboard Lambda Function URL
- `SSE_LAMBDA_URL` — preprod SSE Lambda Function URL
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — for DynamoDB token query (magic link tests)
- `AWS_REGION` — us-east-1

## Implementation Order

1. **Helpers** (auth-helper.ts, dynamo-helper.ts) — shared utilities
2. **US1: OAuth flow** — route interception pattern, foundational for US4/US5
3. **US2: Magic link** — DynamoDB token extraction, foundational for US5
4. **US3: Alert CRUD** — independent, no auth flow dependency
5. **US4: Session lifecycle** — depends on US1 auth helper
6. **US5: Account linking** — depends on US1 + US2 patterns
7. **US6: Cross-browser** — config change only, run existing tests

## Risks

- **Cold start timeouts**: Lambda Function URLs may take 10-20s on cold start. Tests use retry/wait patterns from existing sanity.spec.ts.
- **Route interception timing**: Playwright route must be registered before navigation. Use `page.route()` in `beforeEach()`.
- **DynamoDB eventual consistency**: Magic link token query may return stale results. Add 1s delay after requesting link.
- **Cross-browser CSS differences**: WebKit may render differently. Accept minor visual differences; assert on functionality, not pixels.
