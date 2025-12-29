# Implementation Plan: SSE Runtime URL Discovery

**Branch**: `1100-sse-runtime-url` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1100-sse-runtime-url/spec.md`

## Summary

Fix 502 error on SSE stream by fetching runtime config from `/api/v2/runtime` to get the correct SSE Lambda URL. Currently the frontend uses `NEXT_PUBLIC_API_URL` (Dashboard Lambda, BUFFERED mode) for SSE connections, but should use the dedicated SSE Lambda (RESPONSE_STREAM mode) URL returned by the runtime endpoint.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: React, zustand (state), React Query
**Storage**: N/A (client-side state only)
**Testing**: Jest, React Testing Library
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: web (frontend-only change)
**Performance Goals**: SSE connection established within 5s of page load
**Constraints**: No blocking of initial page render
**Scale/Scope**: Single-page application, ~10 affected files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: TLS | ✅ PASS | All URLs use HTTPS |
| No secrets in code | ✅ PASS | No secrets involved |
| Least privilege | ✅ PASS | Frontend has no elevated permissions |
| Error handling | ✅ PASS | Existing reconnection logic preserved |

No violations. Proceed with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/1100-sse-runtime-url/
├── spec.md              # Feature specification
├── plan.md              # This file
├── checklists/          # Quality checklists
│   └── requirements.md  # Spec quality validation
└── tasks.md             # Implementation tasks (next phase)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── sse.ts           # SSE client (MODIFY: use config URL)
│   │   │   └── runtime.ts       # NEW: Runtime config fetcher
│   │   └── constants.ts         # (MODIFY: add SSE_URL constant)
│   ├── hooks/
│   │   └── use-sse.ts           # SSE hook (MODIFY: use config URL)
│   └── stores/
│       └── config-store.ts      # NEW: Runtime config store
└── tests/
    └── unit/
        └── lib/api/
            └── runtime.test.ts  # NEW: Runtime config tests
```

**Structure Decision**: Frontend web application. Changes isolated to SSE connection initialization.

## Complexity Tracking

No constitution violations - table not required.

## Implementation Approach

### Phase 1: Add Runtime Config Fetcher

1. Create `frontend/src/lib/api/runtime.ts`:
   - `fetchRuntimeConfig()`: Fetch `/api/v2/runtime`
   - Return `{ sse_url: string | null, environment: string }`
   - Handle errors gracefully (return null sse_url on failure)

2. Create `frontend/src/stores/config-store.ts`:
   - Zustand store for runtime configuration
   - `sseUrl` state (initially null)
   - `setSseUrl(url)` action
   - `isConfigLoaded` derived state

### Phase 2: Integrate with SSE Client

3. Modify `frontend/src/hooks/use-sse.ts`:
   - Import config store
   - Use `sseUrl` from store instead of `NEXT_PUBLIC_API_URL`
   - Fall back to `NEXT_PUBLIC_API_URL` if `sseUrl` is null

4. Modify `frontend/src/lib/api/sse.ts`:
   - Update `getSSEClient()` to accept optional baseUrl
   - Use provided URL or fall back to env var

### Phase 3: Initialize on App Load

5. Add config fetching to app initialization:
   - Fetch runtime config on app mount (non-blocking)
   - Update config store with SSE URL
   - SSE connection waits for or uses fallback

### Testing

6. Unit tests for:
   - `fetchRuntimeConfig()` success/failure cases
   - Config store state management
   - SSE hook URL selection logic

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/api/runtime.ts` | CREATE | Runtime config fetch function |
| `frontend/src/stores/config-store.ts` | CREATE | Runtime config state store |
| `frontend/src/hooks/use-sse.ts` | MODIFY | Use config store for SSE URL |
| `frontend/src/lib/api/sse.ts` | MODIFY | Accept URL parameter in factory |
| `frontend/src/app/layout.tsx` or providers | MODIFY | Add config initialization |
| `frontend/tests/unit/lib/api/runtime.test.ts` | CREATE | Unit tests |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Runtime endpoint unavailable | Low | Medium | Fallback to NEXT_PUBLIC_API_URL |
| Race condition (SSE before config) | Medium | Low | Use zustand subscribe or await |
| CORS issues on runtime endpoint | Low | High | Backend already supports CORS |

## Success Validation

1. Load dashboard in browser
2. Open Network tab
3. Verify `/api/v2/runtime` fetched first
4. Verify SSE connection to `lenmswrtbk7aoeot2p75rwhvmq0jcvjz.lambda-url.us-east-1.on.aws`
5. Verify no 502 errors
6. Verify "Connected" status displayed
