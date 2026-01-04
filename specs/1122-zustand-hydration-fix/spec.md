# Feature Specification: Fix Zustand Persist Hydration

**Feature Branch**: `1122-zustand-hydration-fix`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Fix zustand persist hydration issue in session initialization. The dashboard is stuck on 'Initializing session...' forever because the useSessionInit hook reads zustand state before persist middleware rehydrates from localStorage. This is a known issue with zustand persist + Next.js App Router SSR. Need to implement proper hydration handling using onRehydrateStorage callback or hasHydrated pattern to ensure the session initialization useEffect only runs after zustand has fully rehydrated from localStorage."

## Problem Statement

The dashboard application fails to load for users, displaying "Initializing session..." indefinitely. This is a critical bug that prevents all users from accessing any dashboard functionality.

**Root Cause**: The session initialization hook reads zustand store state before the persist middleware has completed rehydrating from localStorage. In Next.js App Router with SSR:
1. Server renders with initial state (empty)
2. Client hydrates and React mounts components
3. `useEffect` runs immediately, reading zustand state
4. But zustand persist middleware hasn't finished async rehydration from localStorage yet
5. Session init sees "no session" and tries to create one, but state never updates correctly

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-time User Dashboard Load (Priority: P1)

A new user visits the dashboard for the first time. They should see the dashboard UI load within a few seconds, with the full header containing sign-in button, refresh button, and connection status indicator visible.

**Why this priority**: This is the core user experience - if the dashboard doesn't load, no other feature works. 100% of users are blocked by this bug.

**Independent Test**: Can be tested by opening the dashboard URL in an incognito browser window (no localStorage) and verifying the page loads with all UI elements visible within 5 seconds.

**Acceptance Scenarios**:

1. **Given** a new user with no session data in localStorage, **When** they navigate to the dashboard URL, **Then** the dashboard UI loads with header, navigation, and content area visible within 5 seconds
2. **Given** a new user with no session data, **When** the dashboard loads, **Then** an anonymous session is automatically created and the sign-in button is visible in the header
3. **Given** a new user, **When** the page loads, **Then** the user never sees "Initializing session..." for more than 3 seconds

---

### User Story 2 - Returning User with Valid Session (Priority: P1)

A returning user with a valid session stored in localStorage visits the dashboard. Their session should be restored from localStorage without any network call, and they should see their authenticated state immediately.

**Why this priority**: Most users are returning users. Their experience must be seamless with instant session restoration.

**Independent Test**: Can be tested by creating a session, closing the browser tab, reopening the dashboard, and verifying instant load with session intact.

**Acceptance Scenarios**:

1. **Given** a returning user with valid session in localStorage, **When** they navigate to the dashboard, **Then** their session is restored from localStorage without an API call
2. **Given** a returning user with valid session, **When** the dashboard loads, **Then** they see their authenticated state (user menu, not sign-in button) immediately
3. **Given** a returning user, **When** the page loads, **Then** the dashboard is fully interactive within 2 seconds

---

### User Story 3 - User with Expired Session (Priority: P2)

A user whose session has expired in localStorage visits the dashboard. The system should detect the expired session, clear it, and create a fresh anonymous session automatically.

**Why this priority**: Expired sessions are a common scenario but less frequent than valid sessions. Users should still have a smooth experience.

**Independent Test**: Can be tested by manually setting an expired session in localStorage and verifying automatic session refresh.

**Acceptance Scenarios**:

1. **Given** a user with expired session in localStorage, **When** they navigate to the dashboard, **Then** a new anonymous session is created automatically
2. **Given** a user with expired session, **When** the new session is created, **Then** the old expired data is cleared from localStorage
3. **Given** a user with expired session, **When** the dashboard loads, **Then** the transition happens seamlessly without error messages

---

### Edge Cases

- What happens when localStorage is unavailable (private browsing, storage quota exceeded)?
  - System should fall back to in-memory session and still function
  - Dashboard UI still renders immediately; only session-dependent features degrade
- What happens when session creation API is slow (>5 seconds)?
  - Dashboard UI remains fully visible and interactive
  - UserMenu shows skeleton/loading state
  - After 15 seconds: inline error banner with retry button appears (not blocking)
- What happens when multiple browser tabs are open?
  - Sessions should be shared correctly via localStorage
- What happens when user rapidly refreshes the page during initialization?
  - System should handle gracefully without duplicate sessions
- What happens during hydration timeout?
  - Dashboard UI remains visible with all non-session-dependent elements functional
  - Inline error banner appears with retry button
  - User can still interact with navigation, view cached data

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST wait for zustand persist rehydration to complete before reading session state
- **FR-002**: System MUST provide a reliable indicator that store hydration is complete
- **FR-003**: Session initialization logic MUST only execute after hydration is confirmed complete
- **FR-004**: System MUST handle the case where localStorage is unavailable gracefully
- **FR-005**: System MUST complete dashboard initialization within 5 seconds under normal conditions
- **FR-006**: System MUST show inline error banner with retry button if initialization exceeds 15 seconds (dashboard UI remains visible and interactive)
- **FR-007**: System MUST restore valid sessions from localStorage without making API calls
- **FR-008**: System MUST create anonymous sessions automatically when no valid session exists
- **FR-009**: System MUST render the dashboard layout (header, navigation, content area) immediately on page load
- **FR-010**: Global "Initializing..." state MUST only be used for initial skeleton setup (sub-second duration)
- **FR-011**: Each UI component MUST hydrate independently via callback, not blocking other components
- **FR-012**: Header MUST always render regardless of session initialization state; only session-dependent elements (e.g., UserMenu) show loading/skeleton state during initialization

#### Progressive Hydration Requirements (Full Refactor)

- **FR-013**: Auth store MUST expose `_hasHydrated` boolean flag via `onRehydrateStorage` callback
- **FR-014**: ProtectedRoute MUST check `_hasHydrated` BEFORE evaluating auth state to prevent flash of unauthorized content
- **FR-015**: React Query hooks (useChartData, etc.) MUST re-enable queries when userId transitions from null to valid value
- **FR-016**: useSessionInit MUST be refactored to centralize initialization and prevent multiple init attempts from different component instances
- **FR-017**: UserMenu MUST render skeleton/placeholder during hydration, not sign-in button
- **FR-018**: All auth-dependent components MUST gracefully handle the `_hasHydrated: false` state without showing incorrect UI

### Key Entities

- **Session State**: User authentication state including userId, tokens, session expiry, and authentication type (anonymous/authenticated)
- **Hydration State**: Boolean indicator (`_hasHydrated`) of whether the zustand store has completed rehydration from localStorage
- **Component Hydration Boundary**: React component that blocks auth-dependent children until `_hasHydrated: true`

### State Transitions

```
Page Load → SSR Render (initial state) → Client Hydration Begins
    ↓
Zustand Persist Rehydrates from localStorage
    ↓
onRehydrateStorage callback fires → sets _hasHydrated: true
    ↓
Components subscribed to _hasHydrated re-render
    ↓
Auth-dependent UI transitions from skeleton → actual state
    ↓
Session init logic executes (if needed)
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard loads and becomes interactive within 5 seconds for 99% of page views
- **SC-002**: Zero users see "Initializing session..." for more than 3 seconds under normal network conditions
- **SC-003**: Returning users with valid sessions see their authenticated state within 2 seconds (no network call)
- **SC-004**: New users see the sign-in button visible in the header within 5 seconds of page load
- **SC-005**: Session initialization timeout errors occur in less than 0.1% of page views

## Clarifications

### Session 2026-01-03

- Q: What should happen when session initialization times out (after 15 seconds)? → A: Show dashboard UI with inline error banner + retry button (Option B)
- Q: Should Header render immediately regardless of session initialization state? → A: Yes - brief global "Initializing..." only for skeleton setup (sub-second), then every element hydrates independently via callback. No element blocks other elements from rendering.
- Q: Minimal fix (hasHydrated flag only) vs Full progressive hydration refactor? → A: Full progressive hydration - each component handles own hydration state with Suspense/skeletons (11+ files affected)

### Design Principles (Canonical Sources)

Per user requirements, this refactor follows:
- **Progressive Disclosure/Rendering** - [Patterns.dev](https://www.patterns.dev/react/progressive-hydration/)
- **Skeleton Screens** - [Wix Engineering](https://www.wix.engineering/post/40-faster-interaction-how-wix-solved-react-s-hydration-problem-with-selective-hydration-and-suspen)
- **Time to First Meaningful Paint** - Reduce blocking time between FCP and TTI
- **Mobile-First Design** - Prioritize perceived performance on slower connections

## Breakage Analysis (Required Reading Before Implementation)

The following components have auth state dependencies that will break with progressive hydration:

### Critical Risk (Must Address)

| Component | File | Issue | Required Fix |
|-----------|------|-------|--------------|
| ProtectedRoute | `components/auth/protected-route.tsx` | Redirect fires after content renders | Add hydration boundary, check `_hasHydrated` before auth check |
| AuthGuard | `components/auth/protected-route.tsx` | Feature gates check unhydrated state | Same as ProtectedRoute |
| useChartData | `hooks/use-chart-data.ts` | `enabled: !!userId` disables permanently | Add re-trigger when userId becomes available |
| useAuth | `hooks/use-auth.ts` | Race condition on init | Refactor to wait for hydration |
| useSessionInit | `hooks/use-session-init.ts` | Multiple init attempts from different components | Centralize init, use hydration callback |

### High Risk (Should Address)

| Component | File | Issue | Required Fix |
|-----------|------|-------|--------------|
| UserMenu | `components/auth/user-menu.tsx` | Sign-in button flashes | Add skeleton state |
| Settings Page | `app/(dashboard)/settings/page.tsx` | Fallback UI flashes | Add hydration-aware rendering |

### Medium/Low Risk (Can Defer)

| Component | File | Issue |
|-----------|------|-------|
| Verify Page | `app/auth/verify/page.tsx` | Load state collision |
| OAuthButtons | `components/auth/oauth-buttons.tsx` | Auth action races init |
| SignOutDialog | `components/auth/sign-out-dialog.tsx` | Button disable state timing |

## Assumptions

1. **Network availability**: Users have functional network connectivity for initial session creation
2. **Browser compatibility**: Users have modern browsers that support localStorage and zustand persist
3. **Standard timeouts**: 10-second timeout for API calls is acceptable per existing configuration
4. **Zustand 5.x patterns**: Using zustand 5.x persist middleware patterns (onRehydrateStorage, hasHydrated)
