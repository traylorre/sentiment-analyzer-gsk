# Feature 1331: auth-oauth-fixes

## Summary

Fix 9 Playwright E2E test failures across 4 auth spec files. Tests fail due to two root
causes: (a) missing API route mocks causing network errors during form submission/OAuth
flows, and (b) incorrect assertion text that doesn't match actual component rendering.

## Category A: Tests Needing Route Mocks (5 tests)

These tests interact with UI that calls backend APIs, but no route mocks intercept those
calls. In a local/CI E2E environment, the real API is either unavailable or returns errors.

### A1. magic-link.spec.ts: "requesting magic link shows confirmation"

**File**: `frontend/tests/e2e/magic-link.spec.ts:14-27`

**Root cause**: Clicking "Continue with Email" triggers `MagicLinkForm.handleSubmit()` which
calls `authApi.requestMagicLink()` (POST `/api/v2/auth/magic-link`). Without a route mock,
the request fails with a network error, the form goes to error state instead of success
state, and `"Check your email"` never appears.

**Fix**: Add `page.route('**/api/v2/auth/magic-link', ...)` mock returning 200 with
`{ message: "Magic link sent", expiresIn: 900 }` before clicking submit.

### A2. magic-link.spec.ts: "valid magic link token authenticates user"

**File**: `frontend/tests/e2e/magic-link.spec.ts:29-53`

**Root cause**: Test navigates to `/auth/verify?token=test-invalid-token`. The verify page
calls `useAuth().verifyToken()` which calls `authApi.verifyMagicLink()` (POST
`/api/v2/auth/magic-link/verify`). Without a mock, the request fails with a network error
instead of showing the "Invalid or expired link" error message from the component.

**Fix**: Add `page.route('**/api/v2/auth/magic-link/verify', ...)` mock returning 400/401
error response so the component renders its error state properly.

### A3. magic-link.spec.ts: "reused magic link token shows already-used error"

**File**: `frontend/tests/e2e/magic-link.spec.ts:55-67`

**Root cause**: Same as A2 -- navigates to verify page with token but no API mock.

**Fix**: Same mock as A2.

### A4. magic-link.spec.ts: "expired magic link shows expiry error"

**File**: `frontend/tests/e2e/magic-link.spec.ts:69-80`

**Root cause**: Same as A2 -- navigates to verify page with token but no API mock.

**Fix**: Same mock as A2.

### A5. oauth-flow.spec.ts: "Google OAuth redirect contains state and code_challenge"

**File**: `frontend/tests/e2e/oauth-flow.spec.ts:13-37`

**Root cause**: The sign-in page calls `authApi.getOAuthUrls()` (GET
`/api/v2/auth/oauth/urls`) on mount to discover available providers. Without a mock, this
call fails, `availableProviders` remains empty, and OAuth buttons are never rendered.
The test then times out waiting for the "Continue with Google" button.

**Fix**: Add `page.route('**/api/v2/auth/oauth/urls', ...)` mock returning provider data
with `authorize_url` values that include the Cognito-style oauth2/authorize path (which
the test's existing route interceptor expects).

### A5b. oauth-flow.spec.ts: "successful OAuth callback creates session"

**File**: `frontend/tests/e2e/oauth-flow.spec.ts:39-54`

**Root cause**: Same as A5 -- OAuth buttons not rendered without the `/urls` mock. Also
needs `sessionStorage` state setup and `/api/v2/auth/oauth/callback` mock for the
callback page to process.

**Fix**: Add `/urls` mock, ensure `mockOAuthRedirect` stores sessionStorage state, and
add callback API mock.

## Category B: Tests With Wrong Assertions (4 tests)

These tests assert text that doesn't match what the component actually renders. The tests
are fundamentally incorrect about the UI contract.

### B1. auth.spec.ts: "should handle provider denial" (line 237)

**File**: `frontend/tests/e2e/auth.spec.ts:237-250`

**Root cause**: Test navigates to `/auth/callback?error=access_denied&error_description=User%20denied%20access`
and asserts `page.getByText('User denied access')`. But the callback page uses a
hardcoded error message map (line 55 of callback/page.tsx):

```typescript
access_denied: 'Sign-in was cancelled. You can try again or continue as guest.'
```

The `error_description` query param is completely ignored. The component always uses
its own message for known error codes.

**Fix**: Change assertion to match actual rendered text:
`page.getByText(/Sign-in was cancelled/)`.

### B2. auth.spec.ts: "should handle provider error without description" (line 253)

**File**: `frontend/tests/e2e/auth.spec.ts:253-267`

**Root cause**: Test navigates to `/auth/callback?error=server_error` and asserts
`page.getByText('Authentication was cancelled')`. But the component maps `server_error`
to:

```typescript
server_error: 'Something went wrong with sign-in. Please try again.'
```

"Authentication was cancelled" appears nowhere in the codebase.

**Fix**: Change assertion to match actual rendered text:
`page.getByText(/Something went wrong with sign-in/)`.

### B3. oauth-flow.spec.ts: "OAuth callback with provider denial shows friendly error" (line 56)

**File**: `frontend/tests/e2e/oauth-flow.spec.ts:56-70`

**Root cause**: Test expects `page.getByRole('link', { name: /try again|sign in|back/i })`.
But the callback page renders a `<Button>` (role="button") for "Try again" and an `<a>`
link for "Continue as guest". There is no `<a>` link with text matching "try again",
"sign in", or "back".

**Fix**: Change to `page.getByRole('button', { name: /try again/i })` or add the
"Continue as guest" link assertion.

### B4. signin-interaction.spec.ts: "session recovers after failed OAuth redirect" (line 101)

**File**: `frontend/tests/e2e/signin-interaction.spec.ts:101-109`

**Root cause**: Test navigates to `/auth/callback?error=access_denied`, asserts
`page.getByText(/cancelled/i)` (which matches "Sign-in was cancelled..."), then asserts
`page.getByRole('link', { name: /guest|continue/i })`. The "Continue as guest" link
exists as an `<a>` element at line 234-239 of callback/page.tsx, but its full text is
"Continue as guest". The regex `/guest|continue/i` should match "Continue as guest".

**Actual issue**: The link text "Continue as guest" should match `/guest|continue/i`.
Need to verify this isn't a timing issue -- the callback page renders inside `<Suspense>`
and the error state may take a moment to appear.

**Fix**: Add explicit `waitFor` timeout. If the link truly doesn't match, adjust selector.
This may actually pass once the preceding assertion passes -- investigate during
implementation.

## Acceptance Criteria

1. All 9 tests pass when running `npx playwright test magic-link.spec.ts oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts`
2. No test assertions are weakened (e.g., no `.toContain('')` or `expect(true)`)
3. Route mocks return realistic response shapes matching the API contracts
4. Tests that passed before continue to pass (no regressions)

## Non-Goals

- Adding new tests
- Changing component behavior
- Modifying API contracts
- Real API integration testing (deferred to preprod E2E)

## Files Modified

| File | Change |
|------|--------|
| `frontend/tests/e2e/magic-link.spec.ts` | Add route mocks for magic-link and verify APIs |
| `frontend/tests/e2e/oauth-flow.spec.ts` | Add /urls mock; fix link/button role assertion |
| `frontend/tests/e2e/auth.spec.ts` | Fix error message assertions (B1, B2) |
| `frontend/tests/e2e/signin-interaction.spec.ts` | Fix link selector or add timeout (B4) |
| `frontend/tests/e2e/helpers/auth-helper.ts` | Possibly extend with shared mock helpers |
