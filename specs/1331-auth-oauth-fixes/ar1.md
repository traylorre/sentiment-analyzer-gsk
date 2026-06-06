# AR#1: Adversarial Review -- Route Mocking Strategy

## Challenge: Are mocked auth endpoints hiding real integration bugs?

### Concern

Adding Playwright route mocks for `/api/v2/auth/magic-link`, `/api/v2/auth/magic-link/verify`,
`/api/v2/auth/oauth/urls`, and `/api/v2/auth/oauth/callback` means these tests will never
exercise the real API. If the API contract changes, these tests will still pass with stale
mocks, creating false confidence.

### Assessment: LOW RISK

**Why mocking is correct here:**

1. **These are E2E *frontend* tests, not integration tests.** Their purpose is to verify
   the UI renders correct states (success, error, loading) given specific API responses.
   They test the React components' behavior, not the API.

2. **Real API testing exists in a separate tier.** The testing pyramid has:
   - Unit tests: mock everything (moto, localstack)
   - Integration tests: real Lambda + LocalStack DynamoDB
   - E2E preprod: real Amplify + real API Gateway + real Lambda
   The E2E tests in this feature are tier 1 (CI) tests that run against `localhost:3000`.

3. **The tests that are failing *already* have this problem.** The tests were written to
   run against a local Next.js dev server with no backend. They just forgot the mocks.
   This isn't a philosophical change -- it's completing the existing test design.

4. **Contract drift is caught elsewhere.** The `auth-api.md` contract spec and the
   bidirectional validation methodology catch API contract changes.

### Concern: Should magic-link tests run against real API in CI?

**No.** Magic link verification requires:
- A running Lambda backend
- DynamoDB tables (dev-loop-queue or similar)
- Email delivery (or DynamoDB direct query for token extraction)
- Real cryptographic token generation

This is a preprod concern, not a CI concern. The comment in magic-link.spec.ts already
acknowledges this: "Full token extraction requires dynamo-helper.ts with AWS SDK."

### Concern: Mock response shapes may drift from real API

**Mitigation**: Use the same TypeScript types from `frontend/src/lib/api/auth.ts` as
reference when constructing mock responses. The mock responses should match the exact
shape that `authApi.requestMagicLink()` etc. return after mapping.

### Verdict: PROCEED

The route mocking approach is sound. These tests verify UI state transitions, not API
integration. Add contract-shaped mocks and fix the broken assertions.
