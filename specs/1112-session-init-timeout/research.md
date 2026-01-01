# Research: Session Initialization Timeout

**Feature**: 1112-session-init-timeout
**Date**: 2025-12-31

## Research Tasks

### 1. Current Implementation Analysis

**Question**: How does the frontend currently handle session initialization?

**Findings**:
- `signInAnonymous()` in `auth-store.ts` calls `authApi.createAnonymousSession()`
- `apiClient` in `client.ts` performs raw `fetch()` without timeout
- No AbortController or timeout currently implemented
- State management via Zustand with `isLoading` and `error` flags

**Evidence**:
- `client.ts:105` - direct fetch call with no signal option
- `runtime.ts:20-49` - existing pattern using `AbortSignal.timeout(5000)`

### 2. Best Practices for Fetch Timeout

**Question**: What is the recommended approach for HTTP request timeouts in modern browsers?

**Decision**: Use `AbortController` with `AbortSignal.timeout()`

**Rationale**:
1. Native browser API - no dependencies needed
2. Properly cancels the request (not just ignoring the response)
3. Works with all fetch-based code
4. Already used in codebase (`runtime.ts`)

**Alternatives Rejected**:
| Alternative | Reason Rejected |
|-------------|-----------------|
| `setTimeout` wrapper | Doesn't cancel actual request, connection stays open |
| `Promise.race` with timeout | Same issue - request continues in background |
| axios/fetch libraries | Adds dependency when native solution exists |

### 3. Error Handling Integration

**Question**: How should timeout errors integrate with existing error handling?

**Decision**: Extend `ApiClientError` with 'TIMEOUT' code

**Rationale**:
- Consistent with existing error handling pattern
- Auth store already catches `ApiClientError` and sets `error` state
- Hook already displays error message to user
- No changes needed to error display logic

### 4. Timeout Duration Selection

**Question**: What timeout duration is appropriate for session initialization?

**Decision**: 10 seconds default, configurable

**Rationale**:
- Backend typically responds in 1-3 seconds under normal conditions
- 10 seconds allows for:
  - Network latency (up to 3 seconds)
  - Cold start scenarios (up to 5 seconds)
  - Safety margin (2 seconds)
- 15 seconds max total init time (per spec FR-004)
- Leaves 5 seconds for UI transition and retry prompt

**Evidence from spec**:
- FR-001: Configurable timeout (default 10 seconds)
- FR-004: Complete within 15 seconds max
- SC-002: 95% of users see dashboard within 5 seconds

### 5. Request Cancellation

**Question**: How to ensure no orphaned connections?

**Decision**: AbortController handles this automatically

**Rationale**:
- When `AbortSignal.timeout()` fires, it aborts the fetch
- Browser closes the TCP connection
- No manual cleanup needed
- Fulfills FR-006 requirement

## Resolved Clarifications

All clarifications resolved - no [NEEDS CLARIFICATION] markers in spec.

## Implementation Recommendations

1. **Add timeout to RequestOptions interface** in `client.ts`
2. **Use AbortSignal.timeout()** for timeout handling
3. **Catch AbortError** and convert to ApiClientError with 'TIMEOUT' code
4. **Set 10-second default** for session initialization in `auth.ts`
5. **Add constants** to `constants.ts` for configurability
6. **No changes needed** to auth-store.ts or use-session-init.ts
