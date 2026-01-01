# Implementation Plan: Session Initialization Timeout

**Branch**: `1112-session-init-timeout` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1112-session-init-timeout/spec.md`

## Summary

Add timeout handling to anonymous session initialization to prevent infinite loading state. The frontend currently shows "Initializing session..." forever when the backend is slow or unreachable. The solution adds AbortController-based timeout at the API client level, with configurable duration (default 10 seconds) and graceful error handling with retry capability.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js 14 frontend)
**Primary Dependencies**: Zustand (state), fetch API, AbortController
**Storage**: localStorage (session persistence via Zustand persist)
**Testing**: Jest/React Testing Library (frontend unit tests)
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge - IE11 not supported)
**Project Type**: Web application (frontend-only changes)
**Performance Goals**: Dashboard visible within 15 seconds worst-case, 5 seconds typical
**Constraints**: Must not break existing session restoration from localStorage
**Scale/Scope**: Single-user session management, no concurrent session concerns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Amendment | Status | Notes |
|-----------|--------|-------|
| 1.6 - No Quick Fixes | PASS | Using full speckit workflow |
| 1.12 - Mandatory Speckit Workflow | PASS | At /speckit.plan phase |
| 1.14 - Validator Usage | PENDING | Will run /validate after implementation |

**Verification Gates**:
- Spec coherence: PASS (no [NEEDS CLARIFICATION] markers)
- Bidirectional verification: Will verify post-implementation

**Validation Gates**:
- format-validate: Will run before PR
- security-validate: Will run before PR

## Project Structure

### Documentation (this feature)

```text
specs/1112-session-init-timeout/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no new API contracts)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts      # ADD: timeout support to RequestOptions
│   │   │   └── auth.ts        # ADD: timeout parameter to createAnonymousSession
│   │   └── constants.ts       # ADD: SESSION_TIMEOUT_MS constant
│   ├── stores/
│   │   └── auth-store.ts      # No changes needed (error handling exists)
│   └── hooks/
│       └── use-session-init.ts # No changes needed (error propagation works)
└── tests/
    └── unit/
        └── lib/
            └── api/
                └── client.test.ts  # ADD: timeout behavior tests
```

**Structure Decision**: Frontend-only changes. API client layer receives timeout support; higher layers (store, hook) already have error handling that will propagate timeout errors automatically.

## Complexity Tracking

No constitution violations. Implementation is minimal and follows existing patterns.

## Research Findings

### Decision: AbortController-based Timeout at API Client Level

**Rationale**:
1. Follows existing pattern in `runtime.ts` which uses `AbortSignal.timeout(5000)`
2. Centralizes timeout handling - all endpoints benefit automatically
3. Backwards compatible - timeout is optional with sensible defaults
4. Proper request cancellation - no orphaned connections

**Alternatives Considered**:
1. **setTimeout wrapper around fetch**: Rejected - doesn't cancel the actual request
2. **Per-endpoint timeout handling**: Rejected - violates DRY, error-prone
3. **Hook-level timeout**: Rejected - too late in the flow, doesn't cancel requests

### Implementation Approach

```
Layer 1: apiClient (client.ts)
├─ Add timeout?: number to RequestOptions interface
├─ Create AbortController with AbortSignal.timeout(ms)
├─ Handle AbortError → ApiClientError with code 'TIMEOUT'
└─ Default timeout: undefined (no timeout by default)

Layer 2: authApi (auth.ts)
├─ createAnonymousSession accepts timeout parameter
├─ Default to 10000ms (10 seconds) for session init
└─ Passes through to apiClient options

Layer 3: Constants (constants.ts)
├─ SESSION_INIT_TIMEOUT_MS = 10000
└─ MAX_INIT_TIME_MS = 15000 (for documentation)
```

## Data Model

No new entities required. Existing entities:

| Entity | Changes |
|--------|---------|
| Session | None - existing structure sufficient |
| InitializationState | Error state already handles timeout via `error` field |
| ApiClientError | Add 'TIMEOUT' to error code union type |

## Contracts

No new API contracts. This is a client-side timeout implementation.

## Quickstart

### Development

```bash
cd frontend
npm install  # No new dependencies needed
npm run dev
```

### Testing Timeout Behavior

```bash
# Unit tests
npm test -- --testPathPattern=client.test

# Manual testing
# 1. Open browser dev tools → Network → Offline mode
# 2. Navigate to dashboard
# 3. Expect: Error message appears within 15 seconds with retry option
```

### Configuration

```typescript
// frontend/src/lib/constants.ts
export const SESSION_INIT_TIMEOUT_MS = 10000;  // 10 seconds
```
