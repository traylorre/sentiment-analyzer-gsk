# Feature 1373: Sign-In Error Visibility

**Status**: Draft
**Created**: 2026-04-29
**Source**: `specs/oauth-provisioning-plan.md` (W11)
**Depends On**: none
**Blocks**: none (orthogonal to 1370/1371/1372/1374)

## Summary

The customer dashboard sign-in page (`frontend/src/app/auth/signin/page.tsx`)
silently swallows errors from `authApi.getOAuthUrls()`, collapsing four
distinct failure modes into the same UI state ("buttons not rendered").
This makes triage impossible from the browser — a 500 from the backend, a
CORS rejection, an empty providers response, and a fetch timeout all look
identical.

This feature adds observable diagnostics (console logging, optional
non-blocking UI hint) without changing the graceful-degradation behavior.

## Problem

`signin/page.tsx:25-29`:
```typescript
} catch {
  // Graceful degradation (FR-009): if API unreachable, show email only
  if (!cancelled) {
    setAvailableProviders([]);
  }
}
```

Three problems:

1. The bare `catch` discards the error object. Type, status code, message —
   all lost.
2. `availableProviders = []` and the success path `availableProviders =
   Object.keys({})` produce identical UI. An operator looking at the page
   can't distinguish "OAuth intentionally off" from "OAuth broken."
3. Browser console is silent. The only signal that something failed is the
   absence of buttons, which is also the success signal when OAuth is
   intentionally disabled.

This was a contributing factor to the original audit confusion (root cause
was Lambda env var, but the symptom was indistinguishable from an API
error).

## User Stories

### US1: Browser console shows the OAuth fetch failure (P1)

As a developer or operator triaging "no OAuth buttons," I want a console
error message with the failed URL, status, and message, so I can immediately
distinguish "providers configured = 0" from "API errored."

**Acceptance**: When `authApi.getOAuthUrls()` rejects, the catch block calls
`console.error('[signin] OAuth providers fetch failed', { url, status,
message, cause })`. When the fetch succeeds with empty providers, the catch
block does not fire — the success path logs an info message at debug level
(or no log at all, depending on FE logging conventions).

### US2: An optional non-blocking hint surfaces a true API failure (P2)

As a user who hits the sign-in page during a backend outage, I want a small,
non-blocking notice ("Some sign-in options are temporarily unavailable")
when the API failed, so I understand why the page looks different from
yesterday.

**Acceptance**: When `authApi.getOAuthUrls()` rejects (vs returns empty),
render a small muted-text hint above the magic-link form: "Some sign-in
options are temporarily unavailable." When the response succeeds with empty
providers (intentional config), no hint shown. The hint does not block the
email form.

### US3: No regression to graceful degradation (P1)

As a user, I want the sign-in page to work via email even when OAuth is
fully broken, so I'm never blocked from accessing my account.

**Acceptance**: All existing E2E tests in `frontend/tests/e2e/` that pass
today continue to pass. The magic-link form remains functional regardless
of `getOAuthUrls()` outcome.

## Requirements

### R1: Capture and log the error in the catch block

Replace `} catch {` with `} catch (err: unknown) {` and add (revised after AR#2 to log `status + code` only, not `message`, per plan AD1):

```typescript
} catch (err: unknown) {
  if (!cancelled) {
    const status = err instanceof ApiClientError ? err.status : undefined;
    const code = err instanceof ApiClientError ? err.code : 'NETWORK';
    console.error('[signin] OAuth providers fetch failed', {
      url: '/api/v2/auth/oauth/urls',
      status,
      code,
    });
    setAvailableProviders([]);
    setProvidersFetchFailed(true);  // new state for US2
  }
}
```

`err.message` is intentionally NOT logged — it can carry backend-controlled
text. `status + code` is enough for triage.

### R2: Track fetch-failed vs configured-empty as distinct states

Add a new state flag `providersFetchFailed: boolean` (default false). Set
true only in the catch block, never in the success path. This lets the
render layer distinguish the two UI states.

### R3: Render the optional hint (US2)

When `providersFetchFailed && providersLoaded`, render a small muted-text
hint above the magic-link form. Use existing Tailwind tokens
(`text-xs text-muted-foreground`). No icon, no border, no toast.

The hint must:
- Not block any other UI element
- Not appear when `providersFetchFailed === false`
- Be readable to screen readers (`role="status"` and `aria-live="polite"`)
- Use the exact text `"Some sign-in options are temporarily unavailable. You can still sign in with email."`

### R4: Preserve all existing behavior

- Magic-link form still rendered immediately (FR-009 preserved).
- "Continue as guest" link unchanged.
- OAuth buttons render exactly as before when providers exist.

## Success Metrics

1. Manual test: with backend returning 500 to `/api/v2/auth/oauth/urls`,
   browser console shows the error object; the hint renders; magic-link
   form still works.
2. Manual test: with backend returning `{providers: {}}` (intentional
   empty), browser console is silent; no hint renders; magic-link form
   works.
3. Manual test: with backend returning 2 providers, OAuth buttons render;
   no console error; no hint.
4. All Playwright tests in `frontend/tests/e2e/` continue to pass.
5. New unit test in `frontend/tests/unit/signin-page.test.tsx` covers the
   three branches above.

## Out of Scope

- Adding telemetry / analytics events (e.g., Sentry, Mixpanel). Console-only
  visibility is enough for this feature.
- Changing the `authApi.getOAuthUrls()` API contract.
- Showing the actual HTTP status code or backend error message to end users
  (that's an information leak).
- Retrying the fetch (the user can refresh).
- Backend changes (e.g., richer error responses).

## Edge Cases

| Scenario | Expected Behavior |
|---|---|
| API returns 200 with empty `{providers: {}}` | No console error. No hint. Buttons hidden. |
| API returns 500 | Console error logged. Hint renders. Buttons hidden. Email form works. |
| API returns 200 with malformed JSON | `await response.json()` throws → caught → console error → hint. |
| Network offline | `fetch` rejects → caught → console error → hint. |
| API returns 200 with `{providers: {google: {...}}}` only | Console silent. No hint. Google button renders, GitHub does not. |
| `authApi.getOAuthUrls` returns before the component unmounts vs after | `cancelled` flag prevents `setState` after unmount. Unchanged. |
| Hint text translated for i18n | This codebase doesn't currently have i18n. Out of scope. |
| Screen reader announces the hint multiple times if the user re-mounts the page | `aria-live="polite"` queues announcements; browsers debounce. Acceptable. |

## Adversarial Review #1

**Reviewer**: Self (adversarial — UX, accessibility, security, signal-to-noise)
**Date**: 2026-04-29

### Findings

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | Console error containing `err.message` could leak backend internals (stack traces, internal hostnames) to anyone with browser devtools open. | The `err` from a fetch is a `TypeError` ("Failed to fetch") or a custom error from `authApi`; not a backend stack trace. Backend errors are JSON bodies; `authApi.get` likely throws based on response status. **Verify in Stage 4 (Clarify)** what shape `err` takes. If it could include backend body, redact to status code only. |
| HIGH | The hint text says "temporarily unavailable" but if OAuth is intentionally disabled (placeholder credentials), this is semantically misleading. The hint will never render in that case (success-with-empty path), but if a future regression flips the success path to a thrown error, users would see a false "outage" message. | Acceptable. R2 (separate state flag) ensures only true fetch failures trigger the hint. Future regressions should be caught by tests. Add a test asserting that 200 + empty does NOT render the hint. |
| MEDIUM | `console.error` is suppressed in some browser configurations (e.g., Chrome with "Errors" filter off). For triage to work, the operator must know to look. | Acceptable for this feature's scope. Telemetry is out of scope. |
| MEDIUM | The hint could be exploited as a phishing surface — an attacker who can inject a hint via XSS could craft a fake "click here to sign in another way" link. | The hint is hardcoded text in the component, no dynamic interpolation, no user-controlled input. Safe from this attack. |
| MEDIUM | Adding `providersFetchFailed` state expands the component's state surface from 2 → 3 booleans. Cyclomatic complexity rises. | Acceptable. Three booleans (`availableProviders`, `providersLoaded`, `providersFetchFailed`) with three render branches (loading, loaded-with-providers, loaded-without). Can refactor to a discriminated union later if it grows. |
| LOW | `aria-live="polite"` on a static hint is mild AT noise. Consider `aria-live="off"` since the hint doesn't change during a session. | Defer to UX preference. Both are acceptable. Stage 4 clarification. |
| LOW | The hint adds 1 DOM node always when fetch failed. On layout-sensitive pages this could cause CLS. | Negligible — the hint is below the fold for most viewport sizes (the magic-link form is the primary focus). Acceptable. |
| LOW | Console messages persist in localhost dev tools across page reloads. A developer iterating on this code will see noise. | Use a structured prefix `[signin]` so the developer can filter. Already in R1. |
| LOW | The hint provides zero remediation guidance. A user who sees it gets a "yes there's a problem" without a "what to do" hint. The text "You can still sign in with email" partially addresses this. | Acceptable. R3's text ends with "You can still sign in with email." |

**Spec edits made in response**: None required (all findings are either acceptable, deferred to Stage 4, or already addressed by R1-R4).

### Gate

**0 CRITICAL, 0 HIGH unresolved.** HIGH #1 (PII / internals leak) deferred to
Stage 4 clarification — verify error shape before committing to console output
format. **Spec is ready for Stage 3 (Plan).**
