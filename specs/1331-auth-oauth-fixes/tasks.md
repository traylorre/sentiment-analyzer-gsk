# Tasks: Feature 1331 -- auth-oauth-fixes

## Phase 1: Pure Assertion Fixes

- [ ] **T1**: Fix auth.spec.ts line 247 -- change `'User denied access'` assertion to `/Sign-in was cancelled/`
  - File: `frontend/tests/e2e/auth.spec.ts`
  - Deps: none

- [ ] **T2**: Fix auth.spec.ts line 263 -- change `'Authentication was cancelled'` assertion to `/Something went wrong with sign-in/`
  - File: `frontend/tests/e2e/auth.spec.ts`
  - Deps: none

## Phase 2: Validate A2-A4 Without Mocks

- [ ] **T3**: Run magic-link.spec.ts tests 2-4 locally; verify if they pass without route mocks
  - Command: `cd frontend && npx playwright test magic-link.spec.ts --grep "valid magic link|reused|expired"`
  - If pass: mark T4 as SKIP
  - If fail: proceed to T4
  - Deps: none

- [ ] **T4**: (CONDITIONAL) Add POST `/api/v2/auth/magic-link/verify` route mock to magic-link.spec.ts tests 2-4
  - File: `frontend/tests/e2e/magic-link.spec.ts`
  - Deps: T3 (only if T3 fails)

## Phase 3: OAuth /urls Mock

- [ ] **T5**: Add `mockOAuthUrls()` helper function to `auth-helper.ts`
  - File: `frontend/tests/e2e/helpers/auth-helper.ts`
  - Returns mock response matching `OAuthUrlsResponse` type
  - `authorize_url` values must include `oauth2/authorize` path for existing route interceptors
  - Deps: none

- [ ] **T6**: Add `mockOAuthUrls(page)` call to oauth-flow.spec.ts test "Google OAuth redirect contains state and code_challenge"
  - File: `frontend/tests/e2e/oauth-flow.spec.ts`
  - Insert before `page.goto('/auth/signin')`
  - Deps: T5

- [ ] **T7**: Add `mockOAuthUrls(page)` call to oauth-flow.spec.ts test "successful OAuth callback creates session"
  - File: `frontend/tests/e2e/oauth-flow.spec.ts`
  - Also add POST `/api/v2/auth/oauth/callback` mock returning success with tokens
  - Deps: T5

- [ ] **T8**: Add `mockOAuthUrls(page)` to oauth-flow.spec.ts test "OAuth callback with provider denial" AND fix `getByRole('link')` to `getByRole('button', { name: /try again/i })`
  - File: `frontend/tests/e2e/oauth-flow.spec.ts`
  - Dual fix: mock + assertion
  - Deps: T5

- [ ] **T9**: Add `mockOAuthUrls(page)` to oauth-flow.spec.ts test "GitHub OAuth flow works with same pattern"
  - File: `frontend/tests/e2e/oauth-flow.spec.ts`
  - Deps: T5

## Phase 4: Magic Link API Mock

- [ ] **T10**: Add POST `/api/v2/auth/magic-link` route mock to magic-link.spec.ts test "requesting magic link shows confirmation"
  - File: `frontend/tests/e2e/magic-link.spec.ts`
  - Mock returns `{ message: "Magic link sent", expiresIn: 900 }`
  - Deps: none

## Phase 5: signin-interaction Fix

- [ ] **T11**: Verify/fix signin-interaction.spec.ts test "session recovers after failed OAuth redirect"
  - File: `frontend/tests/e2e/signin-interaction.spec.ts`
  - Check if `getByRole('link', { name: /guest|continue/i })` matches "Continue as guest"
  - Add explicit timeout if needed: `.toBeVisible({ timeout: 5000 })`
  - Deps: none

## Phase 6: Verification

- [ ] **T12**: Run all 4 affected spec files and verify all 9 previously-failing tests pass
  - Command: `cd frontend && npx playwright test magic-link.spec.ts oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts`
  - Deps: T1, T2, T3/T4, T5-T11

- [ ] **T13**: Run full E2E suite to verify no regressions in passing tests
  - Command: `cd frontend && npx playwright test`
  - Deps: T12
