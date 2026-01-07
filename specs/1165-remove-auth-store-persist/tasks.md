# Tasks: Remove Auth Store persist() Middleware

**Branch**: `1165-remove-auth-store-persist`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Created**: 2026-01-06

## Task Breakdown

### Phase 1: Remove persist() from auth-store.ts

#### Task 1.1: Remove persist wrapper and storage config
**Status**: [X] Complete
**File**: `frontend/src/stores/auth-store.ts`
**Action**: Remove persist() middleware, TOKEN_STORAGE_KEY, createJSONStorage, partialize, onRehydrateStorage
**Acceptance**: Store created with plain `create<AuthStore>()` without persist

#### Task 1.2: Remove _hasHydrated from state
**Status**: [X] Complete
**File**: `frontend/src/stores/auth-store.ts`
**Action**: Remove _hasHydrated field from AuthStore interface and initialState
**Acceptance**: No hydration tracking in store

#### Task 1.3: Remove useHasHydrated selector
**Status**: [X] Complete
**File**: `frontend/src/stores/auth-store.ts`
**Action**: Remove exported useHasHydrated hook
**Acceptance**: Hook no longer exported

### Phase 2: Update Hooks

#### Task 2.1: Simplify useSessionInit
**Status**: [X] Complete
**File**: `frontend/src/hooks/use-session-init.ts`
**Action**: Remove hydration timeout, hasHydrated dependency; call /refresh directly on init
**Acceptance**: Hook initializes immediately without waiting for hydration

#### Task 2.2: Update useAuth
**Status**: [X] Complete
**File**: `frontend/src/hooks/use-auth.ts`
**Action**: Remove hasHydrated from return value and any hydration-related logic
**Acceptance**: Hook works without hydration concept

#### Task 2.3: Update useChartData hooks (added)
**Status**: [X] Complete
**File**: `frontend/src/hooks/use-chart-data.ts`
**Action**: Remove useHasHydrated import and all hydration dependencies
**Acceptance**: Chart hooks work without hydration concept

### Phase 3: Update Tests

#### Task 3.1: Update auth-store tests
**Status**: [X] Complete
**File**: `frontend/tests/unit/stores/auth-store.test.ts`
**Action**: Remove hydration tests, update for memory-only behavior
**Acceptance**: All tests pass

#### Task 3.2: Update hook tests if needed
**Status**: [X] Complete
**Files**: `frontend/tests/unit/hooks/`, `frontend/tests/unit/components/auth/`
**Action**: Update any tests that mock localStorage or hydration
**Acceptance**: All tests pass

#### Task 3.3: Update component tests (added)
**Status**: [X] Complete
**Files**: `frontend/tests/unit/components/auth/user-menu.test.tsx`, `frontend/tests/unit/components/auth/protected-route.test.tsx`, `frontend/tests/unit/components/providers/session-provider.test.tsx`
**Action**: Replace hasHydrated with isInitialized in all useAuth mocks
**Acceptance**: All tests pass

### Phase 4: Verification

#### Task 4.1: Run frontend tests
**Status**: [X] Complete
**Action**: npm run test in frontend directory
**Acceptance**: All 414 tests pass

#### Task 4.2: Run frontend build
**Status**: [X] Complete
**Action**: npm run build in frontend directory
**Acceptance**: Build succeeds without errors

#### Task 4.3: Commit, push, create PR
**Status**: [ ] In Progress
**Action**: Create PR with auto-merge enabled
**Acceptance**: PR created

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Remove persist | 3 | 3/3 Complete |
| Phase 2: Update Hooks | 3 | 3/3 Complete |
| Phase 3: Update Tests | 3 | 3/3 Complete |
| Phase 4: Verification | 3 | 2/3 Complete |
| **Total** | **12** | **11/12 Complete** |
