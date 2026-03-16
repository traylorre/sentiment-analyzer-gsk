# Test Coverage Matrix (1223)

No new API endpoints. This feature adds E2E tests for existing endpoints.

## Coverage Before vs After

| User Flow | Before | After | Test File |
|-----------|--------|-------|-----------|
| Anonymous session creation | Tested (basic) | Tested (unchanged) | sanity.spec.ts |
| OAuth redirect + callback success | **Not tested** | **Tested** | auth/oauth-flow.spec.ts |
| OAuth callback errors | Tested (5 cases) | Tested (unchanged) | auth.spec.ts |
| Magic link request | UI only | **Full flow** | auth/magic-link.spec.ts |
| Magic link verification | **Not tested** | **Tested** | auth/magic-link.spec.ts |
| Magic link reuse/expiry | **Not tested** | **Tested** | auth/magic-link.spec.ts |
| Alert create | **Not tested** | **Tested** | alerts/crud.spec.ts |
| Alert read/list | **Not tested** | **Tested** | alerts/crud.spec.ts |
| Alert update | **Not tested** | **Tested** | alerts/crud.spec.ts |
| Alert delete | **Not tested** | **Tested** | alerts/crud.spec.ts |
| Alert quota enforcement | **Not tested** | **Tested** | alerts/crud.spec.ts |
| Session refresh | **Not tested** | **Tested** | session/lifecycle.spec.ts |
| Sign out | **Not tested** | **Tested** | session/lifecycle.spec.ts |
| Session eviction (max 5) | **Not tested** | **Tested** | session/lifecycle.spec.ts |
| Expired session → 401 | **Not tested** | **Tested** | session/lifecycle.spec.ts |
| Anonymous → authenticated merge | **Not tested** | **Tested** | account/linking.spec.ts |
| Multi-provider linking | **Not tested** | **Tested** | account/linking.spec.ts |
| Email merge (existing account) | **Not tested** | **Tested** | account/linking.spec.ts |
| Firefox compatibility | **Not tested** | **Tested** | sanity.spec.ts (firefox project) |
| WebKit compatibility | **Not tested** | **Tested** | sanity.spec.ts (webkit project) |

## Browser Coverage Before vs After

| Browser | Before | After |
|---------|--------|-------|
| Desktop Chrome | Tested | Tested |
| Mobile Chrome (Pixel 5) | Tested | Tested |
| Mobile Safari (iPhone 13) | Tested | Tested |
| Desktop Firefox | **Not tested** | **Tested** |
| Desktop Safari (WebKit) | **Not tested** | **Tested** |
