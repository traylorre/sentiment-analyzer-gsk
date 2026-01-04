# Feature Specification: Dashboard Skeleton Architecture Fix

**Feature Branch**: `1123-skeleton-architecture`
**Created**: 2026-01-03
**Status**: Draft
**Input**: User description: "Dashboard Skeleton Architecture Fix: The dashboard has a fundamental design flaw where UI elements (sign-in button, refresh button, connection status) are hidden behind hydration gates, showing only animated circles instead of functional skeletons."

**Related Specs**:
- `1126-auth-httponly-migration` - **BLOCKER** - Security fix must be done FIRST
- `1124-sse-connection-store` - SSE connection status infrastructure (DEPENDENCY)
- `1125-refresh-coordinator` - Refresh button and pull-to-refresh wiring (DEPENDENCY)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Immediate Visual Feedback on Page Load (Priority: P1)

As a user loading the dashboard, I want to see recognizable UI elements immediately (even if non-interactive) so that I understand the interface layout and available actions before the application is fully hydrated.

**Why this priority**: First impression is critical. Users who see only blinking circles cannot understand the interface, leading to confusion and perceived slowness. This is the foundational UX issue.

**Independent Test**: Can be tested by throttling network in DevTools (Slow 4G), hard-refreshing, and verifying skeleton elements show recognizable shapes with text placeholders (e.g., button-shaped "Sign in" skeleton, not just a pulsing circle).

**Acceptance Scenarios**:

1. **Given** the dashboard is loading, **When** the page renders before hydration completes, **Then** users see skeleton elements that match the dimensions and visual structure of final elements (button shapes for buttons, text placeholders for text)
2. **Given** the dashboard is loading, **When** a skeleton element represents a button with text (like "Sign in"), **Then** the skeleton shows a button-shaped outline with a text placeholder, not just an animated circle
3. **Given** hydration takes longer than expected (e.g., 2+ seconds), **When** users view the page, **Then** they can still identify what actions will be available (sign in, refresh, status indicator)

---

### User Story 2 - Skeleton Dimensions Match Final Elements (Priority: P1)

As a user, I want the page layout to remain stable when content loads so that I don't experience jarring layout shifts.

**Why this priority**: Layout shift is a core web vital (CLS) and causes poor UX. Current skeletons (circles) don't match final elements (buttons with text).

**Independent Test**: Screenshot skeleton state, screenshot hydrated state, overlay and compare dimensions. No visible shift should occur.

**Acceptance Scenarios**:

1. **Given** the UserMenu skeleton is visible, **When** hydration completes and the "Sign in" button appears, **Then** the button occupies the same space as the skeleton (no layout shift)
2. **Given** the desktop nav user section skeleton is visible, **When** hydration completes, **Then** the user info section occupies the same space as the skeleton
3. **Given** any skeleton with `animate-pulse`, **When** hydration completes, **Then** the animation stops and real content appears in the same position

---

### Edge Cases

- What happens when hydration times out (5+ seconds)? Skeletons should remain visible with subtle "Loading..." text overlay
- What happens on extremely slow networks? Skeletons remain visible; no infinite loading states without status text

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST render skeleton elements that visually match the dimensions and structure of their corresponding final elements (buttons shaped like buttons, not circles)
- **FR-002**: System MUST show text placeholders within skeleton elements where the final element contains text (e.g., "Sign in" button skeleton shows button shape with grayed text or text-width bar)
- **FR-003**: System MUST render navigation chrome (header, nav items, action buttons) as static layout elements, with only their internal state being dynamically hydrated
- **FR-004**: System MUST provide graceful degradation when hydration exceeds 2 seconds, showing a subtle loading indicator text alongside functional skeletons
- **FR-005**: System MUST ensure all skeleton animations have finite duration or clear purpose (no infinitely blinking elements without content after 2 seconds)
- **FR-006**: Skeleton elements MUST use the same CSS classes for width/height as their final counterparts to prevent layout shift

### Key Entities

- **Skeleton Element**: A placeholder UI component that renders during hydration, matching the visual structure of its final counterpart
- **Hydration State**: Boolean flag indicating whether the client-side application has completed rehydrating from persisted state

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can identify all primary actions (sign in, refresh, navigation) within 500ms of initial page render, even before hydration completes
- **SC-002**: 100% of skeleton elements match the visual footprint of their final rendered state (zero layout shift, CLS = 0)
- **SC-003**: No UI elements show infinite loading animations without accompanying status text after 2 seconds
- **SC-004**: Skeleton-to-final transition is imperceptible (no flash, no jump, no visible reflow)

## Assumptions

- Session initialization is a single API call (`/api/auth/refresh`). Hydration is complete when `isInitialized` becomes true. No localStorage hydration needed (per spec 1126 architecture).
- Skeleton-to-final-element transitions should be seamless without layout shift (existing Tailwind utilities support this)
- SSE connection status and refresh button functionality are handled by separate specs (1124, 1125)

## Hydration Model (Post-1126)

The zustand persist hydration mechanism (PR #588) is **REMOVED** by spec 1126. The new hydration model is simpler:

```
Page Load
    │
    ▼
SessionProvider calls /api/auth/refresh
    │
    ├─ 200 OK → User authenticated, isInitialized = true
    └─ 401    → User not authenticated, isInitialized = true
    │
    ▼
Skeletons replaced with real content
```

Key changes:
- No `_hasHydrated` flag from zustand persist
- No localStorage timing issues
- No 5-second hydration timeout
- Session init is a single HTTP call (~100-500ms typically)

## Out of Scope

- SSE connection status infrastructure (see spec 1124)
- Refresh button wiring and pull-to-refresh integration (see spec 1125)
- localStorage fallback for private browsing (not a real problem - see risk analysis)
