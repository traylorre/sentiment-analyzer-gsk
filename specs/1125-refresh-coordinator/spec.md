# Feature Specification: Refresh Coordinator

**Feature Branch**: `1125-refresh-coordinator`
**Created**: 2026-01-03
**Status**: Draft
**Input**: Risk analysis identified that RefreshTimer component exists but `onRefresh` callback is never wired in dashboard layout. React Query caches are not invalidated on manual refresh.

**Related Specs**:
- `1126-auth-httponly-migration` - **BLOCKER** - Security fix must be done FIRST
- `1123-skeleton-architecture` - Depends on this for refresh button functionality
- `1124-sse-connection-store` - Both need to work together for full dashboard functionality

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Functional Refresh Button (Priority: P1)

As a user, I want to manually trigger a data refresh so that I can get the latest information on demand without waiting for the automatic refresh cycle.

**Why this priority**: Manual refresh is a standard user expectation. The button exists in the UI but doesn't work, which is worse than not having it at all.

**Independent Test**: Click refresh button, verify network request is made (DevTools → Network), verify UI updates with fresh data.

**Acceptance Scenarios**:

1. **Given** the user is viewing the dashboard, **When** they click the refresh button, **Then** the dashboard fetches fresh data from the backend (visible in Network tab)
2. **Given** a refresh is in progress, **When** the user views the refresh button, **Then** it shows a loading/spinning state and is disabled to prevent duplicate requests
3. **Given** a refresh completes successfully, **When** new data is available, **Then** the dashboard updates and the refresh timer resets
4. **Given** a refresh fails, **When** the error occurs, **Then** the user sees appropriate feedback (error state on button or toast notification)

---

### User Story 2 - Pull-to-Refresh Gesture Support (Priority: P2)

As a mobile user, I want to pull down on the dashboard to refresh data so that I can use familiar mobile gesture patterns.

**Why this priority**: The pull-to-refresh component exists but is not integrated. This is a quality-of-life improvement for mobile users.

**Independent Test**: On mobile viewport, pull down on content area, verify refresh indicator appears and data refresh is triggered.

**Acceptance Scenarios**:

1. **Given** the user is on a touch device viewing the dashboard, **When** they pull down on the content area, **Then** a pull-to-refresh indicator appears showing the gesture is recognized
2. **Given** the user pulls down past the activation threshold, **When** they release, **Then** the dashboard triggers a data refresh
3. **Given** a pull-to-refresh is in progress, **When** the user views the indicator, **Then** it shows a loading animation until the refresh completes

---

### User Story 3 - Refresh Countdown Timer Coordination (Priority: P2)

As a user, I want the refresh countdown timer to coordinate with manual refreshes so that I understand when the next automatic refresh will occur.

**Why this priority**: If manual refresh doesn't reset the countdown, users may see confusing behavior (refresh countdown reaches zero right after manual refresh).

**Independent Test**: Click refresh button, verify countdown timer resets to full interval (5 minutes).

**Acceptance Scenarios**:

1. **Given** the countdown timer shows 2 minutes remaining, **When** the user manually refreshes, **Then** the countdown timer resets to the full interval (5 minutes)
2. **Given** a pull-to-refresh is triggered, **When** the refresh completes, **Then** the countdown timer also resets

---

### Edge Cases

- What happens if refresh is triggered while another refresh is in progress? Should be debounced/ignored
- What happens if backend is unreachable during refresh? Show error state, don't reset timer
- What happens on rate-limited API responses? Handle gracefully with user feedback

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a `useRefreshCoordinator()` hook that centralizes refresh logic
- **FR-002**: System MUST invalidate all relevant React Query caches when refresh is triggered
- **FR-003**: System MUST wire the refresh coordinator to the `Header` component's `onRefresh` prop
- **FR-004**: System MUST integrate the `PullToRefresh` component into the dashboard layout
- **FR-005**: System MUST wire pull-to-refresh to the same refresh coordinator as the button
- **FR-006**: System MUST reset the countdown timer when any refresh completes successfully
- **FR-007**: System MUST debounce refresh requests to prevent multiple simultaneous fetches
- **FR-008**: System MUST provide visual feedback for refresh states (loading, success, error)

### Key Entities

- **Refresh Coordinator**: Central hook that manages refresh state and triggers cache invalidation
- **Refresh State**: Current state of refresh operation: `'idle'` | `'refreshing'` | `'error'`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Manual refresh action completes and updates visible data within 3 seconds under normal network conditions
- **SC-002**: Pull-to-refresh gesture is recognized and functional on touch-enabled devices
- **SC-003**: Countdown timer correctly resets after any successful refresh
- **SC-004**: No duplicate network requests when refresh is triggered rapidly
- **SC-005**: Error states are visible to users when refresh fails

## Assumptions

- React Query is already configured and used for data fetching
- The `RefreshTimer` component already supports `onRefresh` callback
- The `PullToRefresh` component is functionally complete and only requires integration
- Query keys for dashboard data are known and can be invalidated programmatically
