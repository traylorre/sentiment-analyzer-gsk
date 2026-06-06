# AR#3: Final Readiness Review

## Completeness Check

| Failing Test | Root Cause Identified | Fix Specified | Task Assigned |
|---|:---:|:---:|:---:|
| magic-link: "requesting magic link shows confirmation" | YES (no POST mock) | YES | T10 |
| magic-link: "valid magic link token authenticates user" | YES (no verify mock) | YES (conditional) | T3/T4 |
| magic-link: "reused token shows already-used error" | YES (no verify mock) | YES (conditional) | T3/T4 |
| magic-link: "expired token shows expiry error" | YES (no verify mock) | YES (conditional) | T3/T4 |
| oauth-flow: "Google OAuth redirect contains state..." | YES (no /urls mock) | YES | T6 |
| oauth-flow: "successful OAuth callback creates session" | YES (no /urls + /callback mock) | YES | T7 |
| auth: "should handle provider denial" | YES (wrong assertion) | YES | T1 |
| auth: "should handle provider error without description" | YES (wrong assertion) | YES | T2 |
| signin-interaction: "session recovers after failed OAuth" | PARTIALLY (timing/selector) | YES | T11 |

## Risk Assessment

### Low Risk (Pure text changes)
- T1, T2: Assertion string replacements. Component source is definitive. Zero ambiguity.

### Medium Risk (Route mocks)
- T5-T10: Route mocks must match API response shapes. Mitigated by using exact types
  from `frontend/src/lib/api/auth.ts` as reference.

### Unknown Risk
- T3/T4: A2-A4 tests may or may not need mocks. The conditional approach handles this.
- T11: B4 test may have a subtle issue we haven't identified. The `/guest|continue/i`
  regex should match but might not due to Playwright's accessible name computation.
  If `getByRole('link', { name: /guest|continue/i })` doesn't find the `<a>` element,
  it could be because the `<a>` doesn't have an explicit `role="link"` attribute (though
  `<a href="...">` has implicit link role). Fallback: use `page.locator('a').filter({ hasText: /continue as guest/i })`.

## Scope Creep Guard

The following are explicitly OUT OF SCOPE:
- Fixing tests that currently pass
- Adding new test coverage
- Changing component behavior to match tests (tests are wrong, not components)
- Modifying API endpoints or contracts
- Refactoring the auth-helper.ts beyond adding `mockOAuthUrls()`

## Remaining Questions

1. **oauth-flow.spec.ts "successful OAuth callback" test**: The full flow
   (click button -> store sessionStorage -> intercept redirect -> callback page reads
   sessionStorage -> exchanges code) has many moving parts. The `mockOAuthRedirect`
   helper preserves the state parameter from the Cognito URL, but the `signInWithOAuth`
   function must first call `/urls` to get the authorize_url. If our mock `/urls` returns
   a URL that matches `**/oauth2/authorize**` pattern, the existing route interceptor
   should work. Need to verify the authorize_url in the mock matches the interceptor glob.

2. **Parallel test runs**: Playwright may run tests in parallel. Route mocks are
   page-scoped (not global), so no interference between tests.

## Verdict: READY FOR IMPLEMENTATION

All 9 failures have identified root causes, specified fixes, and assigned tasks.
The conditional approach for A2-A4 reduces unnecessary work.
Task dependency chain is linear and straightforward.
No blocking questions remain -- remaining unknowns are resolved during implementation.
