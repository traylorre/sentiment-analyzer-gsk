# Stage 4: Clarification -- Verified Component Behavior

## Error Message Map (callback/page.tsx lines 55-60)

| errorParam value     | Rendered message                                                      |
|---------------------|-----------------------------------------------------------------------|
| `access_denied`     | "Sign-in was cancelled. You can try again or continue as guest."      |
| `unauthorized_client` | "This sign-in method is not configured. Please try email sign-in."  |
| `server_error`      | "Something went wrong with sign-in. Please try again."                |
| `invalid_request`   | "The sign-in request was invalid. Please try again."                  |
| (unknown)           | "Sign-in failed. Please try again or use email sign-in."              |

The `error_description` query parameter is **completely ignored**. The component uses
its own hardcoded map.

## Error State UI Elements (callback/page.tsx lines 206-243)

- `<h2>` heading: "Sign in failed"
- `<p>` paragraph: `{errorMessage || authError || 'An error occurred...'}`
- `<Button>` (role="button"): "Try again" -- calls `router.push('/auth/signin')`
- `<a>` (role="link"): "Continue as guest" -- href="/"

## Verify Page Error State (verify/page.tsx lines 93-120)

- `<h2>` heading: "Invalid or expired link"
- `<p>` paragraph: `{error || 'This magic link is invalid or has expired. Please request a new one.'}`
- `<Button>` (role="button"): "Request new link" -- calls `router.push('/auth/signin')`

## Magic Link Success State (magic-link-form.tsx lines 57-96)

- `<h3>` heading: "Check your email"
- `<p>` paragraph: "We've sent a magic link to {email}"
- `<p>` sub-text: "Click the link in the email to sign in. The link expires in 15 minutes."
- `<Button>` variant="outline": "Use a different email"

## Sign-in Page Provider Discovery (signin/page.tsx lines 16-39)

- On mount: calls `authApi.getOAuthUrls()`
- On success: sets `availableProviders` to `Object.keys(data.providers)`
- On failure: sets `availableProviders` to `[]` (graceful degradation)
- OAuth buttons only render when `hasOAuthProviders` is true

## Test-by-Test Verification

### B1 (auth.spec.ts:247)
- **Test expects**: `'User denied access'` (the raw error_description)
- **Component renders**: `'Sign-in was cancelled. You can try again or continue as guest.'`
- **Verdict**: WRONG ASSERTION. Fix to `/Sign-in was cancelled/`

### B2 (auth.spec.ts:263)
- **Test expects**: `'Authentication was cancelled'`
- **Component renders**: `'Something went wrong with sign-in. Please try again.'`
- **Verdict**: WRONG ASSERTION. Fix to `/Something went wrong with sign-in/`

### B3 (oauth-flow.spec.ts:69)
- **Test expects**: `getByRole('link', { name: /try again|sign in|back/i })`
- **Component renders**: Button "Try again" (role=button) + Link "Continue as guest" (role=link)
- **Verdict**: WRONG ROLE. The link's text "Continue as guest" doesn't match `/try again|sign in|back/i`. Change to `getByRole('button', { name: /try again/i })`.

### B4 (signin-interaction.spec.ts:108)
- **Test expects**: `getByRole('link', { name: /guest|continue/i })`
- **Component renders**: `<a>Continue as guest</a>` -- text "Continue as guest"
- **Verdict**: SHOULD MATCH. "Continue" matches `/continue/i` and "guest" matches `/guest/i`. This test may actually pass once the first assertion `getByText(/cancelled/i)` succeeds (which requires the error state to render). Likely a timing issue or the test is failing because of Suspense loading state.
  - Potential fix: ensure sufficient timeout on both assertions.

### A1 (magic-link.spec.ts:14-27)
- Form submit calls `requestMagicLink(email, captchaToken)` which calls POST `/api/v2/auth/magic-link`
- Without mock: network error -> form shows error state, never shows "Check your email"
- **Verdict**: NEEDS ROUTE MOCK

### A2-A4 (magic-link.spec.ts:29-80)
- Verify page calls `verifyToken(token)` which calls POST `/api/v2/auth/magic-link/verify`
- Without mock: network error -> component may not transition to error state cleanly
- The verify page catches ANY error and sets `status='error'` (line 32), which shows
  "Invalid or expired link" heading. So a network error SHOULD still work...
- **Wait**: Re-reading verify/page.tsx line 32: `catch { setStatus('error') }`. This
  catches the error and sets error state. The `error` variable comes from
  `useAuth().error` which is set by the auth store. If `verifyMagicLink` throws, the
  store sets the error message.
- The component renders `{error || 'This magic link is invalid or has expired...'}`
- So even without a mock, the network error should trigger catch -> error state ->
  "Invalid or expired link" heading should appear.
- **Re-diagnosis**: The tests check for `/invalid|expired|not found/i` on the heading
  "Invalid or expired link" -- this should match. AND they check for a button
  `/request.*new|try again|new link/i` which matches "Request new link".
- **The tests A2-A4 might actually pass already.** Need to verify during implementation.
  The failure may be that `verifyMagicLink` in the store doesn't throw cleanly when
  the API is unreachable, leaving the component stuck in loading state.

### A5 (oauth-flow.spec.ts:13-37)
- Sign-in page fetches `/api/v2/auth/oauth/urls` on mount
- Without mock: fetch fails -> `availableProviders` set to `[]` -> no OAuth buttons
- Google button never appears -> test times out
- **Verdict**: NEEDS ROUTE MOCK. Confirmed.
