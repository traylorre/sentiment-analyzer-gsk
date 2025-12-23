# Feature Specification: Skeleton Loading UI

**Feature Branch**: `1021-skeleton-loading-ui`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "T069: Add skeleton loading UI components in src/dashboard/app.js per FR-011 (never show loading spinners, skeleton UI only). Implement skeleton placeholder for chart area, ticker list, resolution selector. Show skeleton during initial load and data fetches. Reference existing patterns in codebase or use CSS animation for shimmer effect. Ensure SC-009 (zero loading spinners) is met."

**Parent Spec**: specs/1009-realtime-multi-resolution/spec.md (FR-011, SC-009)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initial Dashboard Load with Skeleton (Priority: P1)

As a user opening the sentiment dashboard for the first time, I see placeholder skeletons immediately while data loads in the background, so I understand the page structure and know content is coming without staring at a blank screen or spinning wheel.

**Why this priority**: First impressions matter - the initial load experience sets user expectations. Skeleton UI provides instant visual feedback that the page is loading, reducing perceived wait time and preventing users from thinking the app is broken.

**Independent Test**: Can be fully tested by loading the dashboard with network throttling enabled and verifying skeleton elements appear within 100ms while actual data loads in background.

**Acceptance Scenarios**:

1. **Given** user navigates to dashboard, **When** page starts loading, **Then** skeleton placeholders appear within 100ms for chart area, ticker list, and resolution selector
2. **Given** user is viewing skeleton UI, **When** data finishes loading, **Then** skeleton smoothly transitions to real content without jarring flicker
3. **Given** user has slow connection (3G), **When** dashboard loads, **Then** skeleton remains visible until all data arrives (no partial spinners)

---

### User Story 2 - Resolution Switch with Skeleton (Priority: P2)

As a user switching between time resolutions (1m, 5m, 1h, etc.), I see skeleton placeholders in the chart area during data fetch, so I know new data is loading without the interface feeling frozen or showing spinners.

**Why this priority**: Resolution switching is a frequent user action. Skeleton feedback during switches maintains the feeling of responsiveness even when fetching new data takes time.

**Independent Test**: Can be tested by clicking resolution buttons and verifying chart area shows skeleton during fetch, with content appearing when data arrives.

**Acceptance Scenarios**:

1. **Given** user viewing 5-minute resolution data, **When** user clicks 1-hour resolution, **Then** chart area shows skeleton placeholder during data fetch
2. **Given** data fetch takes more than 200ms, **When** skeleton is displayed, **Then** skeleton remains until new data is ready (no intermediate states)
3. **Given** user rapidly switches resolutions, **When** multiple fetches queue, **Then** only latest resolution data replaces skeleton (debounced)

---

### User Story 3 - Data Refresh with Skeleton (Priority: P3)

As a user with an active dashboard, when background data refreshes or SSE reconnects, I see subtle skeleton indicators for affected components rather than disruptive loading states, so my workflow is minimally interrupted.

**Why this priority**: Background refreshes should be unobtrusive. Skeleton indicators signal activity without demanding attention or breaking user concentration on existing data.

**Independent Test**: Can be tested by triggering SSE reconnection or manual refresh and verifying skeleton appears in affected areas without disrupting visible data.

**Acceptance Scenarios**:

1. **Given** user viewing dashboard data, **When** background refresh triggers, **Then** only stale components show skeleton overlay (not entire page)
2. **Given** SSE connection drops and reconnects, **When** new data streams in, **Then** chart shows skeleton briefly then updates smoothly
3. **Given** user manually triggers refresh, **When** refresh starts, **Then** appropriate skeleton indicators appear without hiding existing data

---

### Edge Cases

- What happens when data fetch fails? Skeleton transitions to error state (not infinite skeleton)
- How long can skeleton display before timeout? Maximum 30 seconds before showing error message
- What if component has no data to display? Show skeleton briefly then empty state message
- What happens during rapid navigation? Cancel pending fetches, show skeleton for latest request only

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display skeleton placeholder for chart area immediately on page load (within 100ms)
- **FR-002**: System MUST display skeleton placeholder for ticker list during initial load
- **FR-003**: System MUST display skeleton placeholder for resolution selector during initial load
- **FR-004**: System MUST show skeleton in chart area during resolution switches
- **FR-005**: System MUST use CSS shimmer animation effect for skeleton placeholders (subtle left-to-right gradient)
- **FR-006**: System MUST transition from skeleton to real content without visible flicker (smooth fade)
- **FR-007**: System MUST NOT display any loading spinners during normal operation (including fetch errors)
- **FR-008**: System MUST cancel pending skeleton displays when component receives data
- **FR-009**: System MUST show skeleton overlay (not replace) for partial refreshes to preserve visible data
- **FR-010**: System MUST timeout skeleton display after 30 seconds and show error state

### Key Entities

- **SkeletonState**: Tracks loading state for each dashboard component (chart, tickerList, resolution)
- **LoadingContext**: Manages which components are in skeleton state to coordinate transitions

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero loading spinners visible anywhere in the dashboard during any operation
- **SC-002**: Skeleton placeholders appear within 100ms of navigation or action triggering data fetch
- **SC-003**: Skeleton-to-content transition completes in under 300ms with no visible flicker
- **SC-004**: Users perceive page as responsive (no "frozen" feeling) even on 3G networks
- **SC-005**: Dashboard passes accessibility audit for loading states (skeleton has appropriate ARIA attributes)

## Assumptions

- Existing CSS infrastructure supports animation keyframes (standard browser support)
- Dashboard already has component structure for chart, ticker list, and resolution selector
- JavaScript state management can track loading states per component
- SSE connection handling already exists and can trigger skeleton states on reconnection

## Out of Scope

- Server-side loading state management
- Progressive loading of individual data points within a component
- Custom skeleton shapes for complex visualizations (rectangular placeholders are sufficient)
- Loading state persistence across page refreshes
