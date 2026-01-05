# Implementation Plan: Remove Zustand Persist Middleware

**Branch**: `1131-remove-zustand-persist` | **Date**: 2026-01-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1131-remove-zustand-persist/spec.md`

## Summary

Remove authentication tokens (accessToken, refreshToken, idToken) from the zustand persist() middleware's `partialize` function to prevent XSS attacks from stealing credentials via localStorage. Tokens will remain in-memory only, while non-sensitive session flags can optionally persist for UX continuity. Additionally, implement a migration cleanup to clear any existing tokens from localStorage on application initialization.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: zustand 4.x, zustand/middleware (persist)
**Storage**: localStorage (to be restricted), memory (for tokens)
**Testing**: Jest/Vitest with React Testing Library
**Target Platform**: Browser (Next.js SSR + client-side)
**Project Type**: Web application (frontend component)
**Performance Goals**: No performance impact expected (simpler persistence)
**Constraints**: Must not break existing authentication flows
**Scale/Scope**: Single file change + migration cleanup + unit tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status |
|------|-------------|--------|
| Security & Access Control | Secrets stored securely, not in browser storage | **PASS** - This fix addresses the violation |
| TLS in Transit | N/A for this frontend change | **N/A** |
| Secrets Management | Tokens must not be in source control or localStorage | **PASS** - Removing from localStorage |
| Testing Requirements | Unit tests accompany implementation | **PENDING** - Will be created |
| Pre-Push Requirements | Code linted/formatted | **PENDING** - Will be validated |
| Pipeline Check Bypass | Never bypass | **PASS** - Standard merge flow |

**Gate Result**: PASS - No violations. This fix improves security posture.

## Project Structure

### Documentation (this feature)

```text
specs/1131-remove-zustand-persist/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── checklists/
│   └── requirements.md  # Specification checklist
└── tasks.md             # Phase 2 task breakdown
```

### Source Code (repository root)

```text
frontend/
├── src/
│   └── stores/
│       └── auth-store.ts    # MODIFY: Remove tokens from partialize
└── tests/
    └── unit/
        └── stores/
            └── auth-store.test.ts  # ADD: Tests for token non-persistence
```

**Structure Decision**: This is a frontend-only change affecting the zustand auth store. No backend changes required.

## Complexity Tracking

> No violations requiring justification. Single-file modification with straightforward implementation.

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Persist vs Remove | Modify partialize | Keep persist() but exclude tokens - simpler than removing entire middleware |
| Migration | Clear existing tokens | One-time cleanup on app load ensures clean state |
| Session continuity | Non-sensitive flags persist | Preserves UX while securing tokens |

---

## Phase 0: Research Output

### Decision 1: Zustand Persist Partialize Pattern

**Decision**: Modify the `partialize` function to exclude `tokens` field from persistence.

**Rationale**:
- The `partialize` option in zustand persist middleware controls exactly which state fields are persisted
- Current code explicitly includes `tokens` in partialize - simply remove it
- No need to remove the entire persist middleware - other fields (user, session flags) can stay

**Alternatives Rejected**:
- Remove persist entirely: Would lose all session state across refreshes (poor UX)
- Use sessionStorage: Still vulnerable to XSS (no security improvement)

### Decision 2: Migration Cleanup Strategy

**Decision**: Add a one-time migration to clear existing tokens from localStorage on app initialization.

**Rationale**:
- Users who have already authenticated have tokens stored in localStorage
- Simply changing partialize won't clear existing data
- Need explicit cleanup to remove old tokens

**Implementation**:
- In zustand persist `onRehydrate` callback, check for and clear token fields
- Or use a separate initialization effect to clean localStorage

### Decision 3: Session Continuity

**Decision**: Keep non-sensitive fields (user, isAuthenticated, isAnonymous, sessionExpiresAt) in persistence.

**Rationale**:
- FR-003 allows non-sensitive session flags to persist
- Improves UX by remembering session state across refreshes
- No security risk - these flags don't grant access

---

## Phase 1: Design Output

### Data Model

See [data-model.md](./data-model.md) for complete entity definitions.

**Key Changes to AuthState persistence**:

| Field | Before | After |
|-------|--------|-------|
| `user` | Persisted | Persisted (unchanged) |
| `tokens` | Persisted | **NOT Persisted** |
| `sessionExpiresAt` | Persisted | Persisted (unchanged) |
| `isAuthenticated` | Persisted | Persisted (unchanged) |
| `isAnonymous` | Persisted | Persisted (unchanged) |

### API Contracts

No API changes - this is a frontend-only modification.

### Quickstart

See [quickstart.md](./quickstart.md) for usage examples.

The change is transparent to application code. After implementation:
- Tokens remain in memory during the session
- Page refresh may require re-authentication
- httpOnly cookies (if implemented) provide session continuity

---

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Specification | specs/1131-remove-zustand-persist/spec.md | Complete |
| Plan | specs/1131-remove-zustand-persist/plan.md | Complete |
| Research | specs/1131-remove-zustand-persist/research.md | Complete |
| Data Model | specs/1131-remove-zustand-persist/data-model.md | Pending |
| Quickstart | specs/1131-remove-zustand-persist/quickstart.md | Pending |
| Tasks | specs/1131-remove-zustand-persist/tasks.md | Pending (Phase 2) |
