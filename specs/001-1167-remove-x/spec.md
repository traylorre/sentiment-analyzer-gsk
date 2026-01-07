# Feature Specification: Remove X-User-ID from OHLC API

**Feature Branch**: `001-1167-remove-x`
**Created**: 2026-01-07
**Status**: Draft
**Security Severity**: CRITICAL (CVSS 9.1)
**Input**: Phase 2 breaking change for 1126-auth-httponly-migration

## Context

Feature 1146 established that X-User-ID header is a CVSS 9.1 vulnerability - it allows session hijacking via header injection. The `client.ts` removal was completed in PR #610, but `ohlc.ts` still contains X-User-ID usage that bypasses the secure Bearer token authentication.

**Related PRs**:
- PR #610: feat(1159): Enable cross-origin cookie transmission with SameSite=None (removed X-User-ID from client.ts)
- PR #611: feat(1160): Extract refresh token from httpOnly cookie

**Why This is Critical**: Any endpoint still accepting X-User-ID allows attackers to impersonate users by simply setting a header value. Bearer tokens are cryptographically signed and time-limited.

## User Scenarios & Testing

### User Story 1 - Authenticated User Views Price Chart (Priority: P1)

A logged-in user navigates to a ticker's price chart. The chart loads using their Bearer token for authentication, without exposing their userId in request headers.

**Why this priority**: Core functionality - charts are the primary user interaction. Security is non-negotiable.

**Independent Test**: Load any ticker's chart page while authenticated. Verify network requests use `Authorization: Bearer <token>` instead of `X-User-ID` header.

**Acceptance Scenarios**:

1. **Given** a user is authenticated with valid tokens, **When** they load the price chart for AAPL, **Then** the OHLC API request uses `Authorization: Bearer <accessToken>` header
2. **Given** a user is authenticated, **When** the chart data loads, **Then** no `X-User-ID` header appears in any network request
3. **Given** a user's access token is expired, **When** they load a chart, **Then** the token refresh flow triggers before the API call

---

### User Story 2 - Sentiment History Loads Securely (Priority: P1)

When viewing a ticker, the sentiment history overlay loads using Bearer token authentication.

**Why this priority**: Same security criticality as OHLC - both use the same vulnerable pattern.

**Independent Test**: Verify sentiment history API calls use Bearer token.

**Acceptance Scenarios**:

1. **Given** a user is authenticated, **When** sentiment history loads for a ticker, **Then** the request uses `Authorization: Bearer <accessToken>` header
2. **Given** the sentiment API returns data, **When** inspecting the request, **Then** no `X-User-ID` header is present

---

### User Story 3 - Unauthenticated User Sees Login Prompt (Priority: P2)

A user without valid tokens who tries to view charts is redirected to login.

**Why this priority**: Proper handling of unauthenticated state after removing userId fallback.

**Independent Test**: Clear auth state, navigate to chart page, verify redirect to login.

**Acceptance Scenarios**:

1. **Given** a user has no tokens, **When** they navigate to a chart page, **Then** the query is disabled (enabled: false) and they see login prompt
2. **Given** a user's session is expired and refresh fails, **When** they try to load a chart, **Then** they are redirected to login

---

### Edge Cases

- What happens when userId exists in store but no accessToken? Query should be disabled.
- How does system handle Bearer token that returns 401? Triggers token refresh or logout.
- What if user clears cookies mid-session? Next API call fails, triggers re-auth flow.

## Requirements

### Functional Requirements

- **FR-001**: `fetchOHLCData` MUST NOT accept userId parameter
- **FR-002**: `fetchOHLCData` MUST NOT send X-User-ID header
- **FR-003**: `fetchSentimentHistory` MUST NOT accept userId parameter
- **FR-004**: `fetchSentimentHistory` MUST NOT send X-User-ID header
- **FR-005**: `useChartData` hook MUST NOT extract userId from auth store for API calls
- **FR-006**: `useChartData` hook MUST disable queries when no accessToken exists (not just userId)
- **FR-007**: API client interceptor (already configured in client.ts) handles Bearer token injection
- **FR-008**: Tests MUST be updated to remove X-User-ID expectations

### Files to Modify

| File | Change |
|------|--------|
| `frontend/src/lib/api/ohlc.ts` | Remove userId param and X-User-ID header from both functions |
| `frontend/src/hooks/use-chart-data.ts` | Remove userId extraction, change enabled condition to check accessToken |
| `frontend/tests/unit/stores/auth-store.test.ts` | Update or remove X-User-ID test (lines 553-566) |

### Key Entities

- **AccessToken**: JWT used for Bearer authentication, injected by client.ts interceptor
- **useChartData Hook**: Orchestrates OHLC and sentiment queries with proper auth gating

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero X-User-ID headers in any network request from chart components
- **SC-002**: All chart API calls include `Authorization: Bearer <token>` header
- **SC-003**: Charts load successfully for authenticated users (no regression)
- **SC-004**: Unit tests pass without X-User-ID assertions
- **SC-005**: `npm run typecheck` passes (TypeScript validates parameter removal)
- **SC-006**: `npm run test` passes (Jest tests updated)

### Security Validation

- **SV-001**: Manual inspection of Network tab shows no X-User-ID header on OHLC requests
- **SV-002**: Grep codebase for "X-User-ID" returns zero matches in production code (test fixtures excepted)

## Implementation Notes

The `client.ts` API client already has an interceptor that adds `Authorization: Bearer <accessToken>` to all requests when tokens exist. This was implemented in PR #610. The OHLC functions just need to stop adding the redundant (and insecure) X-User-ID header.

**Before (vulnerable)**:
```typescript
export async function fetchOHLCData(
  ticker: string,
  params: OHLCParams = {},
  userId: string  // REMOVE
): Promise<OHLCResponse> {
  return api.get<OHLCResponse>(`/api/v2/tickers/${ticker}/ohlc`, {
    params: { ... },
    headers: {
      'X-User-ID': userId,  // REMOVE - security vulnerability
    },
  });
}
```

**After (secure)**:
```typescript
export async function fetchOHLCData(
  ticker: string,
  params: OHLCParams = {}
): Promise<OHLCResponse> {
  return api.get<OHLCResponse>(`/api/v2/tickers/${ticker}/ohlc`, {
    params: { ... },
    // Bearer token added by client.ts interceptor
  });
}
```
