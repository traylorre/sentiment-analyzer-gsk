# Plan: Feature 1331 -- auth-oauth-fixes

## Approach

Two workstreams executed sequentially:

1. **Fix wrong assertions (Category B)** -- Quick text changes, zero risk of breaking
   passing tests.
2. **Add route mocks (Category A)** -- More involved, need to add `page.route()` calls
   with correct response shapes.

## Workstream 1: Fix Wrong Assertions

### 1a. auth.spec.ts line 247 (B1: provider denial)

**Current**: `await expect(page.getByText('User denied access')).toBeVisible();`

**Actual UI**: Callback page maps `access_denied` to
`'Sign-in was cancelled. You can try again or continue as guest.'`

**Fix**: Replace with `await expect(page.getByText(/Sign-in was cancelled/)).toBeVisible();`

### 1b. auth.spec.ts line 263 (B2: provider error without description)

**Current**: `await expect(page.getByText('Authentication was cancelled')).toBeVisible();`

**Actual UI**: Callback page maps `server_error` to
`'Something went wrong with sign-in. Please try again.'`

**Fix**: Replace with `await expect(page.getByText(/Something went wrong with sign-in/)).toBeVisible();`

### 1c. oauth-flow.spec.ts line 69 (B3: link vs button role)

**Current**: `await expect(page.getByRole('link', { name: /try again|sign in|back/i })).toBeVisible();`

**Actual UI**: "Try again" is a `<Button>` (role=button). "Continue as guest" is an `<a>`
(role=link) but text doesn't match `/try again|sign in|back/i`.

**Fix**: Change to `await expect(page.getByRole('button', { name: /try again/i })).toBeVisible();`

This test also needs the `/api/v2/auth/oauth/urls` mock to render OAuth buttons in the
first place (it uses `mockOAuthRedirect` which intercepts the Cognito redirect but the
buttons won't appear without the URLs API). BUT -- looking more carefully, the test
navigates to `/auth/signin`, clicks Google button, then the `mockOAuthRedirect` helper
redirects to `/auth/callback` with `error=access_denied`. The callback page doesn't need
OAuth buttons -- it just renders error state. The actual issue is that the sign-in page
needs the `/urls` mock to show the Google button in the first place.

**Revised fix**: Add `/urls` mock before `page.goto('/auth/signin')`, AND fix the link
assertion.

### 1d. signin-interaction.spec.ts line 108 (B4: guest link)

**Current**: `const recoveryLink = page.getByRole('link', { name: /guest|continue/i });`

**Actual UI**: The `<a>` element says "Continue as guest". The regex `/guest|continue/i`
should match "Continue" or "guest" in the text.

**Potential issue**: The `<a>` at line 234-239 of callback/page.tsx is:
```html
<a href="/" class="text-sm text-muted-foreground ...">Continue as guest</a>
```

The `getByRole('link', { name: /guest|continue/i })` should find this. The failure may be
a timing issue -- the callback page uses `<Suspense>` and `useSearchParams()` which
requires client-side hydration. The error state renders after `useEffect` runs.

**Fix**: Increase timeout on the assertion. If still failing, the issue is that
`/auth/callback?error=access_denied` triggers the `useEffect` which checks
`errorParam`, sets status to 'error', and cleans up sessionStorage. The "Continue as
guest" link only appears in the error state JSX. Ensure we wait for the error state to
fully render before checking for the link.

## Workstream 2: Add Route Mocks

### 2a. magic-link.spec.ts: Add beforeEach mock for magic-link API

Add `page.route()` mock for POST `/api/v2/auth/magic-link` in the test that submits the
form. Mock response: `{ message: "Magic link sent", expiresIn: 900 }`.

Note: `authApi.requestMagicLink()` uses `api.post()` which expects the response to be the
parsed body. The actual endpoint path is `/api/v2/auth/magic-link`.

### 2b. magic-link.spec.ts: Add verify API mock for token tests

Add `page.route()` mock for POST `/api/v2/auth/magic-link/verify` that returns an error
response (400 or 401). This causes `verifyMagicLink()` to throw, which sets the verify
page to error state showing "Invalid or expired link".

The verify page (verify/page.tsx) catches the error in line 32 (`catch { setStatus('error') }`)
and renders "Invalid or expired link" heading with the error message from the hook.

For this to work, the mock needs to return an HTTP error status (not 200) so that
`api.post()` throws.

### 2c. oauth-flow.spec.ts: Add /urls mock for OAuth button rendering

Add `page.route()` for GET `/api/v2/auth/oauth/urls` returning:
```json
{
  "providers": {
    "google": {
      "authorize_url": "https://cognito.example.com/oauth2/authorize?client_id=test&redirect_uri=...",
      "icon": "google",
      "state": "mock-state-123"
    },
    "github": {
      "authorize_url": "https://cognito.example.com/oauth2/authorize?identity_provider=GitHub&...",
      "icon": "github",
      "state": "mock-state-456"
    }
  },
  "state": "mock-state-123"
}
```

This mock must be registered BEFORE `page.goto('/auth/signin')` so the sign-in page's
`useEffect` fetch succeeds.

### 2d. oauth-flow.spec.ts: "successful OAuth callback" needs additional mocks

For the successful callback test, the mock flow is:
1. `/urls` mock -> OAuth buttons appear
2. Click Google -> `signInWithOAuth('google')` calls `/urls` again, stores state in
   sessionStorage, redirects to `authorize_url`
3. `mockOAuthRedirect` intercepts the Cognito redirect, redirects to `/auth/callback?code=...&state=...`
4. Callback page reads sessionStorage (provider, state), calls
   `authApi.exchangeOAuthCode()` (POST `/api/v2/auth/oauth/callback`)
5. Need mock for `/api/v2/auth/oauth/callback` returning success

Also need to ensure sessionStorage has the correct values. The `signInWithOAuth` flow
should handle this IF the `/urls` mock returns correctly and the route interception
preserves the state parameter.

## Shared Mock Helper

Consider adding to `auth-helper.ts`:

```typescript
export async function mockAuthApis(page: Page) {
  // Mock OAuth URLs endpoint
  await page.route('**/api/v2/auth/oauth/urls', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ providers: { google: {...}, github: {...} }, state: '...' }),
  }));
}
```

## Execution Order

1. Fix B1, B2 in auth.spec.ts (pure assertion fixes)
2. Fix B3 in oauth-flow.spec.ts (assertion + needs /urls mock)
3. Fix B4 in signin-interaction.spec.ts (timing/selector fix)
4. Add magic-link API mocks (A1)
5. Add verify API mocks (A2, A3, A4)
6. Add OAuth /urls and /callback mocks (A5, A5b)
7. Run full test suite, verify all 9 pass

## Risk Assessment

- **Low risk**: Assertion text fixes (B1, B2) -- pure string replacement
- **Medium risk**: Route mocks -- response shape must match what the components expect
- **Low risk**: oauth-flow tests may have additional timing issues with Suspense boundaries
