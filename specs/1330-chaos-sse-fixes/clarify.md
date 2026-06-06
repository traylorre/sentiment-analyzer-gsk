# Stage 4: Clarification — Answers from Codebase

## Q1: Does /api/v2/stream exist in the local API?

**YES.** The backend Lambda handler at `src/lambdas/dashboard/sse.py` defines:
- `GET /api/v2/stream` — Global metrics stream (FR-001)
- `GET /api/v2/configurations/{config_id}/stream` — Config-specific stream (FR-002)
- `GET /api/v2/stream/status` — Connection status

The local API server (`scripts/run-local-api.py`) proxies all requests to the Lambda
handler, so `/api/v2/stream` is available locally.

**However**, the SSE tests don't depend on the backend serving the stream. They use
`page.route('**/api/v2/stream**')` to intercept and mock/abort the SSE connection.
The tests fail because the **frontend SSE client never makes the request** — not because
the backend doesn't serve it.

## Q2: Why doesn't the frontend SSE client connect on page load?

The SSE client (`use-sse.ts`, `sse-connection.ts`) only connects when:
1. The user is authenticated (`hasAccessToken = true`)
2. A specific configuration is being monitored

On a fresh page load with no auth and no ticker selected, no SSE connection is attempted.
The chaos tests assume SSE connects automatically on `/` — this is wrong.

## Q3: What does the error boundary actually render?

The `ErrorFallback` component in `frontend/src/components/ui/error-boundary.tsx` renders:

- Heading: **"Something went wrong"** (h2, line 88)
- Paragraph: "We encountered an unexpected error..." (line 91)
- Three buttons:
  1. "Try Again" (`<Button>` with `RefreshCw` icon, calls `onReset`)
  2. "Reload Page" (`<Button>` with `RefreshCw` icon, calls `onReload`)
  3. "Go Home" (`<Button>` with `Home` icon, calls `onGoHome`)

All three use `<Button type="button">`. None are `<a>` links. The test at
`chaos-accessibility.spec.ts:131` uses `page.getByRole('link', { name: /go home/i })` which
will NOT match because "Go Home" is a `<button>`, not a link. The `.or()` fallback
`page.getByRole('button', { name: /go home/i })` should match.

**Key finding**: The ErrorTrigger component (`error-trigger.tsx`) only activates when
`process.env.NODE_ENV !== 'production'`. The Next.js dev server sets `NODE_ENV=development`,
so ErrorTrigger works in local dev and CI (which also runs dev server).

## Q4: What is the auth mock response format mismatch?

**CRITICAL FINDING.** The `mockTickerDataApis()` function in `mock-api-data.ts` returns:

```json
{
  "access_token": "mock-test-token",
  "token_type": "bearer",
  "auth_type": "anonymous",
  "user_id": "anon-test-user",
  "session_expires_in_seconds": 3600
}
```

But the actual API contract (`AnonymousSessionResponse` in `types/auth.ts`) is:

```json
{
  "user_id": "string",
  "token": "string",
  "auth_type": "anonymous",
  "created_at": "string",
  "session_expires_at": "string",
  "storage_hint": "localStorage"
}
```

The `mapAnonymousSession()` function reads `response.token` (not `response.access_token`).
The mock returns `access_token` but NOT `token`. So `data.token` is `undefined`.

The auth store then calls `setTokens({ accessToken: undefined, ... })`, making
`hasAccessToken` false, and `useChartData` queries never fire.

**This is the root cause of the "0 price candles" failure in chaos-cached-data.spec.ts.**

The same wrong format exists in:
- Feature 1329's planned `mockAnonymousAuth()` (not yet implemented)
- `chart-edge-cases.spec.ts` inline mock
- `chart-zoom-data.spec.ts` inline mock

## Q5: Has Feature 1329 been implemented?

**NO.** The `auth-helper.ts` file exists but does NOT contain `mockAnonymousAuth()`.
It only has `createAnonymousSession()` (real API call), `setupAuthSession()`, and
`mockOAuthRedirect()`. Feature 1329 is spec-only, not yet implemented.

This means Feature 1330 should fix the mock response format in `mockTickerDataApis()`
and note that Feature 1329 has the same bug in its planned `mockAnonymousAuth()`.

## Q6: What does `triggerHealthBanner()` do to page state?

It:
1. Registers `page.route('**/api/**')` to block all API calls (503)
2. Fills search input 3 times (AAPL, GOOG, MSFT)
3. Waits for 503 responses after each fill
4. Waits for banner to be visible

It does NOT call `page.goto()` or navigate. The API block route remains active.
When T023 then calls `page.goto('/')`, the API block is still active. This means
`useSessionInit()` calling `/api/v2/auth/anonymous` gets 503, the auth store gets an
error, and `setInitialized(true)` is called. But `hasAccessToken` stays false.

This is fine for the error boundary test — the ErrorTrigger doesn't need auth. It just
needs `window.__TEST_FORCE_ERROR = true` via `addInitScript`.

## Impact on Plan

### Phase 2 update: Fix mock response format
The cached-data test fix is NOT an "auth timing race" — it's a **mock response format
mismatch**. The fix is to correct the mock response in `mockTickerDataApis()` to match
the actual `AnonymousSessionResponse` contract:

```typescript
await page.route('**/api/v2/auth/anonymous', async (route) => {
  await route.fulfill({
    status: 201,
    contentType: 'application/json',
    body: JSON.stringify({
      user_id: 'anon-test-user',
      token: 'mock-test-token',
      auth_type: 'anonymous',
      created_at: new Date().toISOString(),
      session_expires_at: new Date(Date.now() + 3600_000).toISOString(),
      storage_hint: 'localStorage',
    }),
  });
});
```

### Phase 3 update: A11y test button selector
The a11y test T027 checks for `page.getByRole('link', { name: /go home/i })` — but
"Go Home" is a `<button>`, not a link. The `.or()` fallback handles this, but the
primary selector is wrong. This may cause timing issues if the `.or()` evaluation adds
latency.

### Cross-feature note: Feature 1329
Feature 1329's planned `mockAnonymousAuth()` also has the wrong response format. When
implementing 1329, the response must use `token` not `access_token`.
