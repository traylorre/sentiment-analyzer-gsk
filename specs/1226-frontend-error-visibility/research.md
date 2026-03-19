# Research: Frontend Error Visibility

## R1: React Query Global Error Handling Pattern

**Decision**: Use React Query's `QueryCache.onError` callback to intercept all query failures globally, feeding them into the API health store.

**Rationale**: React Query v5 provides `QueryCache` and `MutationCache` callbacks that fire on every error across all queries. This is the idiomatic way to observe request outcomes without modifying individual query hooks. The existing `retry: 1` config means `onError` fires after the retry fails — so a single transient error won't reach the health store (it retries first).

**Alternatives considered**:
- Axios/fetch interceptor: Would require wrapping the API client. More invasive, duplicates React Query's error handling.
- Custom hook wrapping every `useQuery`: Verbose, error-prone, requires touching every existing hook.

## R2: Failure Window Tracking Strategy

**Decision**: Sliding window of last 60 seconds. Track timestamps of failures. Banner threshold: 3+ failures in window. Recovery: first successful request clears the window and dismisses banner.

**Rationale**: A count-based threshold without a time window would accumulate failures indefinitely (3 failures over an hour isn't an outage). A time window ensures the threshold reflects *current* health. 60 seconds balances detection speed with false-positive avoidance.

**Alternatives considered**:
- Consecutive failures only: Too sensitive — a single success between failures resets the counter, masking intermittent outages.
- Exponential backoff detection: Over-engineered for the problem. The frontend doesn't retry independently (React Query handles retry).

## R3: Zustand Store Design for API Health

**Decision**: New `api-health-store.ts` following the existing `create<Store>((set, get) => {...})` pattern used by `auth-store.ts` and `runtime-store.ts`. State: `{ failures: {timestamp: number}[], isUnreachable: boolean, bannerDismissed: boolean }`. Actions: `recordFailure()`, `recordSuccess()`, `dismissBanner()`.

**Rationale**: Zustand is already the state management library. The store pattern is established. Keeping health state in Zustand allows any component to subscribe (banner, search dropdown, chart) without prop drilling.

**Alternatives considered**:
- React Context: Would work but Zustand is already established and provides selector-based re-rendering.
- Module-level singleton: Wouldn't integrate with React rendering lifecycle.

## R4: Ticker Search Error State UX

**Decision**: The `ticker-input.tsx` component uses React Query's `isError` state (from `useQuery`) to render a distinct error state in the dropdown. Error state shows warning icon + message + retry button. Existing "No tickers found" message unchanged for empty results.

**Rationale**: React Query already exposes `isError` and `error` on every query result. The ticker search currently ignores these. Adding a conditional render for `isError` is minimal — no new hooks, no new state management.

**Alternatives considered**:
- Custom error boundary around search: Over-scoped — error boundaries catch render errors, not async query errors.
- Toast on search failure: Doesn't provide in-context feedback. The error needs to appear in the dropdown where the customer is looking.

## R5: Structured Console Events

**Decision**: Emit `console.warn()` with a structured JSON-like object for each error state transition. Format: `{ event: string, timestamp: string, details: Record<string, unknown> }`. Events: `api_health_banner_shown`, `api_health_banner_dismissed`, `search_error_displayed`, `auth_degradation_warning`.

**Rationale**: `console.warn` (not `console.log` or `console.error`) is the right level — it's visible in DevTools, capturable by Playwright via `page.on('console')`, and semantically correct (warning, not crash). The structured format enables Playwright to filter and assert on specific events.

**Alternatives considered**:
- Custom event emitter / EventTarget: More testable in unit tests but Playwright can't intercept it without extra wiring.
- `console.error`: Semantically incorrect and would pollute error tracking tools.

## R6: Auth Degradation Tracking

**Decision**: Modify `auth-store.ts` to track consecutive `refreshSession()` failures. After 2 consecutive failures, set a `sessionDegraded: boolean` flag. A new component renders a sonner toast when this flag transitions to `true`. Reset on successful refresh.

**Rationale**: The auth store already catches refresh errors (silently). Adding a counter and a flag is minimal. Using sonner (already installed) for the notification matches the existing tier-upgrade toast pattern. The toast is non-blocking and auto-dismisses, appropriate for "your session may expire" which is informational, not critical.

**Alternatives considered**:
- Persistent banner (like the health banner): Over-scoped for auth degradation. Auth issues are per-session, not systemic.
- Modal dialog: Too disruptive for a background process. Session refresh happens automatically — interrupting the user with a modal is poor UX.

## R7: Banner Component Design

**Decision**: Fixed-position banner rendered at the top of the layout (above the sidebar/content area) in `providers.tsx`. Dark amber/orange background consistent with the existing dark theme. Dismissible via X button. Re-appears only after recovery + new failure cycle.

**Rationale**: The banner must be visible regardless of which page/route the customer is on. Placing it in the root layout (providers.tsx) ensures global visibility. The amber color signals "warning" without the severity of red (which the chart error overlay uses for endpoint-specific errors).

**Alternatives considered**:
- Bottom sheet / drawer: Less visible, could be missed.
- Full-page overlay: Too aggressive for a connectivity issue where some features may still work.
