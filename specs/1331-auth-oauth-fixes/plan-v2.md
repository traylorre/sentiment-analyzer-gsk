# Plan v2: Feature 1331 -- auth-oauth-fixes (Post-AR#2)

## Changes from Plan v1

1. Tests A2-A4 may not need mocks -- verify page catches all errors. Try without first.
2. Test B3 reclassified as dual-issue (needs /urls mock + assertion fix).
3. Added validation step: run A2-A4 without mocks before adding them.
4. Need to verify auth store's `verifyMagicLink` has `finally { setLoading(false) }`.

## Execution Sequence

### Phase 1: Pure Assertion Fixes (Zero Risk)

**Task 1.1**: Fix auth.spec.ts B1 (line 247)
- Change `page.getByText('User denied access')` to `page.getByText(/Sign-in was cancelled/)`

**Task 1.2**: Fix auth.spec.ts B2 (line 263)
- Change `page.getByText('Authentication was cancelled')` to `page.getByText(/Something went wrong with sign-in/)`

### Phase 2: Verify A2-A4 Without Mocks

**Task 2.1**: Run magic-link.spec.ts tests 2-4 locally to check if they pass without
route mocks. The verify page's catch-all error handler should render error state even
on network failures.

- If they pass: skip mock addition for A2-A4.
- If they fail: check if `isLoading` stays stuck true. Add verify API mock if needed.

### Phase 3: Add OAuth /urls Mock (Required for 4 tests)

**Task 3.1**: Create shared mock helper in `auth-helper.ts`

```typescript
export async function mockOAuthUrls(page: Page): Promise<void> {
  await page.route('**/api/v2/auth/oauth/urls', route =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        providers: {
          google: {
            authorize_url: 'https://cognito.example.com/oauth2/authorize?client_id=test&response_type=code&scope=openid+email+profile&redirect_uri=http://localhost:3000/auth/callback&code_challenge_method=S256&code_challenge=mock-challenge',
            icon: 'google',
            state: 'mock-csrf-state-google',
          },
          github: {
            authorize_url: 'https://cognito.example.com/oauth2/authorize?client_id=test&identity_provider=GitHub&response_type=code&scope=openid+email+profile&redirect_uri=http://localhost:3000/auth/callback',
            icon: 'github',
            state: 'mock-csrf-state-github',
          },
        },
        state: 'mock-csrf-state-google',
      }),
    })
  );
}
```

**Task 3.2**: Add `mockOAuthUrls(page)` to oauth-flow.spec.ts tests that need it:
- "Google OAuth redirect contains state and code_challenge" (A5)
- "successful OAuth callback creates session" (A5b)
- "OAuth callback with provider denial shows friendly error" (B3)
- "GitHub OAuth flow works with same pattern"

**Task 3.3**: Fix oauth-flow.spec.ts B3 assertion: change `getByRole('link', ...)`
to `getByRole('button', { name: /try again/i })`.

### Phase 4: Add Magic Link API Mock

**Task 4.1**: Add route mock for POST `/api/v2/auth/magic-link` in magic-link.spec.ts
test "requesting magic link shows confirmation" (A1):

```typescript
await page.route('**/api/v2/auth/magic-link', route => {
  if (route.request().method() === 'POST') {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'Magic link sent', expiresIn: 900 }),
    });
  }
  return route.continue();
});
```

### Phase 5: Add OAuth Callback Mock (if needed for A5b)

**Task 5.1**: For "successful OAuth callback creates session", add mock for POST
`/api/v2/auth/oauth/callback` returning success response with tokens.

### Phase 6: Fix signin-interaction.spec.ts B4

**Task 6.1**: Verify test "session recovers after failed OAuth redirect" passes after
callback page properly renders error state. The `/guest|continue/i` regex should match
"Continue as guest". If timing issue, add explicit timeout.

### Phase 7: Verification

**Task 7.1**: Run all 4 spec files:
```bash
cd frontend && npx playwright test magic-link.spec.ts oauth-flow.spec.ts auth.spec.ts signin-interaction.spec.ts
```

**Task 7.2**: Run full E2E suite to verify no regressions:
```bash
cd frontend && npx playwright test
```

## Files Modified

| File | Changes |
|------|---------|
| `frontend/tests/e2e/auth.spec.ts` | Fix 2 assertion strings (B1, B2) |
| `frontend/tests/e2e/oauth-flow.spec.ts` | Add /urls mock, fix button role assertion |
| `frontend/tests/e2e/magic-link.spec.ts` | Add magic-link API mock |
| `frontend/tests/e2e/signin-interaction.spec.ts` | Possibly add timeout (B4) |
| `frontend/tests/e2e/helpers/auth-helper.ts` | Add `mockOAuthUrls()` helper |
