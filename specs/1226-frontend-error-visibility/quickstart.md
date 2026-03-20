# Quickstart: Frontend Error Visibility

## Prerequisites

- Node.js 18+ and npm
- Playwright browsers installed (`npx playwright install chromium`)
- Access to the preprod API URL (for E2E tests)

## Development

```bash
cd frontend
npm install
npm run dev          # Local dev server at http://localhost:3000
```

## Testing

### Unit Tests

```bash
cd frontend
npm test -- --filter "api-health"     # Health store tests
npm test -- --filter "ticker-input"   # Search error state tests
```

### E2E Tests (Playwright)

```bash
cd frontend
# Test with real preprod API:
NEXT_PUBLIC_API_URL=https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws \
  npx playwright test tests/e2e/error-visibility.spec.ts

# Test with blocked API (simulates outage):
# Use Playwright's page.route() to intercept and fail API requests
npx playwright test tests/e2e/error-visibility.spec.ts --grep "banner"
```

### Verifying Console Events (for chaos injection)

```typescript
// In Playwright tests:
const consoleEvents: string[] = [];
page.on('console', msg => {
  if (msg.type() === 'warning' && msg.text().includes('api_health')) {
    consoleEvents.push(msg.text());
  }
});

// After triggering failures:
expect(consoleEvents).toContainEqual(
  expect.stringContaining('api_health_banner_shown')
);
```

## Key Files

| File | Purpose |
|------|---------|
| `src/stores/api-health-store.ts` | Request outcome tracking, failure window, banner state |
| `src/hooks/use-api-health.ts` | Wires store to React Query global callbacks |
| `src/components/ui/api-health-banner.tsx` | Persistent connectivity banner |
| `src/components/dashboard/ticker-input.tsx` | Modified: error vs empty state |
| `src/stores/auth-store.ts` | Modified: refresh failure counter |
| `src/lib/api/client.ts` | Modified: structured console events |
| `src/app/providers.tsx` | Modified: global error handler + banner mount |

## Architecture

```
User interaction (search, chart load)
  → React Query fires request
  → API client executes fetch
  → On error: QueryCache.onError → api-health-store.recordFailure()
  → On success: QueryCache.onSuccess → api-health-store.recordSuccess()

api-health-store evaluates:
  failures in last 60s >= 3?
    → YES: isUnreachable = true → banner shows → console.warn(api_health_banner_shown)
    → NO: isUnreachable = false → no banner

ticker-input reads:
  useQuery.isError?
    → YES: render error state (warning + retry)
    → NO + empty results: render "No tickers found"
    → NO + results: render dropdown

auth-store tracks:
  refreshSession() failed?
    → increment refreshFailureCount
    → count >= 2: sessionDegraded = true → sonner toast → console.warn(auth_degradation_warning)
    → success: reset count, sessionDegraded = false
```
