# Feature Specification: SSE Connection Status Store

**Feature Branch**: `1124-sse-connection-store`
**Created**: 2026-01-03
**Status**: Draft
**Input**: Risk analysis identified that SSE connection status is stored locally in `useSSE()` hook but never exposed globally. `Header` component receives hard-coded `'connected'` status.

**Related Specs**:
- `1126-auth-httponly-migration` - **BLOCKER** - Security fix must be done FIRST
- `1123-skeleton-architecture` - Depends on this for connection status display

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate Connection Status Display (Priority: P1)

As a user, I want to see accurate connection status so that I know whether the dashboard is receiving live data or is disconnected.

**Why this priority**: Misleading status indicators erode trust. A hard-coded "connected" status when the backend is down causes users to question all information on the dashboard.

**Independent Test**: Can be tested by disconnecting network (DevTools → Network → Offline) and verifying the connection indicator changes from "Connected" to "Offline" within 5 seconds.

**Acceptance Scenarios**:

1. **Given** the SSE connection is established and healthy, **When** the user views the connection indicator, **Then** it shows "Connected" status with green styling
2. **Given** the SSE connection drops or fails, **When** the user views the connection indicator, **Then** it shows "Offline" or "Disconnected" status within 5 seconds of connection loss
3. **Given** the SSE connection is being established, **When** the user views the connection indicator, **Then** it shows "Connecting" status with appropriate animation
4. **Given** the dashboard loads with no backend connectivity, **When** the user views the page, **Then** the connection status shows "Offline" immediately, not a false "Connected"

---

### User Story 2 - Connection Status Debouncing (Priority: P2)

As a user, I want the connection status to be stable so that I don't see flickering between states during network instability.

**Why this priority**: Rapid status changes (connected → disconnected → connected) cause visual noise and anxiety.

**Independent Test**: Simulate network flapping (toggle offline mode rapidly) and verify status changes are debounced (minimum 2 seconds between state changes).

**Acceptance Scenarios**:

1. **Given** the SSE connection flaps rapidly (connects/disconnects every 500ms), **When** the user views the connection indicator, **Then** status changes are debounced to prevent flickering (minimum 2 second delay between visible changes)
2. **Given** a brief network hiccup (<2 seconds), **When** the connection recovers, **Then** the user never sees the "Offline" status

---

### Edge Cases

- What happens when SSE endpoint returns 5xx errors? Status should show "Error" with appropriate styling
- What happens when SSE connection times out during initial connect? Status should show "Connecting" then "Offline" after timeout

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create a global zustand store (`useSseStore`) to hold SSE connection status
- **FR-002**: System MUST update the SSE store whenever connection status changes in `useSSE()` hook
- **FR-003**: System MUST expose SSE status as one of: `'connected'`, `'connecting'`, `'disconnected'`, `'error'`
- **FR-004**: System MUST debounce status changes with minimum 2 second delay to prevent flickering
- **FR-005**: System MUST update the dashboard layout to read connection status from the global store instead of hard-coded value
- **FR-006**: System MUST initialize connection status as `'connecting'` (not `'connected'`) on app load

### Key Entities

- **SSE Store**: Global zustand store containing connection status and last connected timestamp
- **Connection Status**: Enum of `'connected'` | `'connecting'` | `'disconnected'` | `'error'`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Connection status accurately reflects backend connectivity state with no false positives (never shows "connected" when disconnected)
- **SC-002**: Status changes are visible to user within 5 seconds of actual connection state change
- **SC-003**: No status flickering during network instability (debounce working)
- **SC-004**: Initial page load shows "Connecting" not "Connected" until SSE actually connects

## Assumptions

- The existing `useSSE()` hook already tracks connection status internally
- The `ConnectionStatus` component already supports all required status values
- Zustand is already a project dependency
