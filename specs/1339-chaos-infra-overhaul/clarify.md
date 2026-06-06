# Clarification — Feature 1339: Chaos Test Infrastructure Overhaul

## Q1: What is the exact console event format for telemetry?

**Answer (from codebase)**: The `emitErrorEvent()` function in
`frontend/src/lib/api/client.ts:37-43` emits:

```typescript
console.warn(JSON.stringify({
  event: string,        // e.g., "api_health_banner_shown", "api_health_recovered"
  timestamp: string,    // ISO 8601
  details: Record<string, unknown>,  // e.g., { failureCount: 3 }
}));
```

Known events (from `api-health-banner.tsx` and `ticker-input.tsx`):
- `api_health_banner_shown` — details: `{ failureCount }`
- `api_health_recovered` — details: `{}`
- `api_health_banner_dismissed` — details: `{}`
- `search_error_displayed` — details: `{ errorCode, endpoint }`
- `auth_degradation_warning` — details: `{ failureCount }`

Non-telemetry console.warn messages that must be IGNORED:
- `[authStore] Profile refresh failed: ...` (plain string, not JSON)
- `[useAuthBroadcast] Failed to refresh profile: ...` (plain string)
- `[useTierUpgrade] Transient error, continuing poll: ...` (plain string)
- `[tracing] X-Ray trace ID generation failed...` (plain string)
- `Runtime config fetch failed: ...` (plain string)
- `Failed to fetch runtime config: ...` (plain string)

**Impact on spec**: Confirms `captureTelemetryEvents()` filter strategy is correct: parse
JSON, check for `event` field, ignore parse failures.

## Q2: What does the error boundary's `__TEST_FORCE_ERROR` flag look like?

**Answer (from codebase)**: `frontend/src/components/ui/error-trigger.tsx`:
- Global: `window.__TEST_FORCE_ERROR` (boolean)
- Component: `ErrorTriggerInner` uses `useEffect` to detect the flag post-hydration
- Mechanism: Sets `shouldError` state -> re-render throws `Error('TEST_FORCE_ERROR: ...')`
- SSR-safe: Flag is only checked in `useEffect`, not during SSR/hydration
- Production-stripped: `ErrorTrigger` returns passthrough in production

The test pattern in `chaos-error-boundary.spec.ts:25-33`:
```typescript
await page.addInitScript(() => {
  (window as any).__TEST_FORCE_ERROR = true;
});
await page.goto('/');
```

Uses `addInitScript` (not `evaluate`) because `goto()` loads a new page. The init script
runs before any page JavaScript.

**Impact on spec**: Confirms `forceErrorBoundary()` implementation is straightforward.
The `addInitScript` + `goto` + wait for "something went wrong" pattern is correct.

## Q3: Does chaos.spec.ts run locally or only in preprod?

**Answer (from codebase)**: `chaos.spec.ts` has this guard:

```typescript
const API_BASE = process.env.PREPROD_API_URL || 'http://localhost:8000';
```

And in `beforeAll`:
```typescript
token = await getAuthToken(request);
chaosAvailable = await isChaosAvailable(request, token);
```

Every test then calls `test.skip(!chaosAvailable, ...)`.

Locally, `isChaosAvailable()` calls `GET /chaos/experiments` with an anonymous token. The
chaos endpoints require JWT auth (not anonymous), so they return 401 locally. The function
returns `false` and all tests are skipped.

The playwright config (`playwright.config.ts`) runs ALL spec files in `tests/e2e/` against
all 5 browser projects. There's no project-level filtering for chaos.spec.ts.

**Impact on spec**: The relocated helpers (`getAuthToken`, `isChaosAvailable`,
`createExperiment`) will work from chaos-helpers.ts. They use Playwright's `request`
fixture (not `page`), so they don't interact with browser automation. Import type is
`APIRequestContext`. The `expect` call inside `createExperiment` uses Playwright's
`expect` which is already imported in chaos-helpers.ts.

## Q4: Which data-testid elements exist in the dashboard for content snapshot?

**Answer (from codebase)**: Key data-testid elements in dashboard components:
- `data-freshness-indicator` — data freshness state badge
- `user-menu-trigger` — user menu button
- `admin-nav-link` / `admin-nav-link-mobile` — admin navigation
- `forbidden-page` — 403 page
- Various auth-related: `login-google`, `login-github`, `login-method-*`, `sign-out-button`

The chart uses `role="img"` with `aria-label` containing ticker and candle count:
```
aria-label="Price and sentiment chart for AAPL. 21 price candles and 21 sentiment points."
```

**Impact on spec**: For `captureContentSnapshot()`, the best key content indicators are:
1. Chart container: `[role="img"][aria-label*="chart"]` -- presence + aria-label text
2. `data-testid="data-freshness-indicator"` -- presence + state
3. Main content child count
4. Absence of error text patterns

The dashboard doesn't have many `data-testid` elements on content areas. The chart
`aria-label` is the strongest signal for "real content is rendered."

## Q5: Does triggerHealthBanner() already use response-based waits?

**Answer (from codebase)**: Yes, confirmed. `chaos-helpers.ts:239-247`:

```typescript
await searchInput.fill('AAPL');
await page.waitForResponse((resp) => resp.status() === 503);
await searchInput.fill('');
await searchInput.fill('GOOG');
await page.waitForResponse((resp) => resp.status() === 503);
// ...
```

It uses `page.waitForResponse()` between each search, not `waitForTimeout`.

**Impact on spec**: No changes needed. Just add JSDoc annotation documenting this.

## Summary: Spec Changes from Clarification

1. **FR-002 update**: Use chart `aria-label` as primary key content signal instead of
   `data-testid` elements (few exist on dashboard content). The `keyContent` map should
   capture `role="img"` elements' `aria-label` attributes.

2. **FR-005 update**: Use `APIRequestContext` type (confirmed available). The `expect`
   import in chaos-helpers.ts already exists and can be used by `createExperiment`.

3. No other spec changes needed.
