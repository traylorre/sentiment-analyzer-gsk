# Research: Skeleton Loading UI

**Feature**: 1021-skeleton-loading-ui
**Date**: 2025-12-22

## Research Questions

### RQ-1: CSS Shimmer Animation Pattern

**Question**: What is the standard CSS pattern for skeleton shimmer effects?

**Decision**: Use CSS gradient animation with `@keyframes` and `linear-gradient`

**Rationale**:
- Pure CSS, no JavaScript animation overhead
- Works across all modern browsers
- Performance optimized (GPU-accelerated transform)
- Industry standard pattern (used by Facebook, LinkedIn, etc.)

**Implementation Pattern**:
```css
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

**Alternatives Considered**:
- JavaScript animation: Rejected (unnecessary overhead, harder to maintain)
- SVG animation: Rejected (overkill for simple rectangles)
- CSS `filter` effects: Rejected (less browser support)

---

### RQ-2: Skeleton State Management

**Question**: How to manage skeleton visibility across multiple components without a framework?

**Decision**: Use simple object-based state with event-driven updates

**Rationale**:
- Vanilla JS maintains project's no-framework constraint
- Object state allows independent component tracking
- Custom events enable decoupled component communication

**Implementation Pattern**:
```javascript
const skeletonState = {
  chart: false,
  tickerList: false,
  resolution: false
};

function showSkeleton(component) {
  skeletonState[component] = true;
  document.querySelector(`[data-skeleton="${component}"]`).classList.add('skeleton-visible');
}

function hideSkeleton(component) {
  skeletonState[component] = false;
  document.querySelector(`[data-skeleton="${component}"]`).classList.remove('skeleton-visible');
}
```

**Alternatives Considered**:
- Global boolean: Rejected (can't track per-component)
- Custom element: Rejected (adds complexity for simple use case)
- State library: Rejected (violates no-dependency constraint)

---

### RQ-3: Smooth Transition from Skeleton to Content

**Question**: How to transition from skeleton to real content without flicker?

**Decision**: Use CSS opacity transition with skeleton positioned absolutely behind content

**Rationale**:
- Skeleton fades out as content fades in
- No layout shift (skeleton is absolutely positioned)
- Content loads "underneath" and is revealed smoothly

**Implementation Pattern**:
```css
.component-container {
  position: relative;
}

.skeleton-overlay {
  position: absolute;
  inset: 0;
  opacity: 1;
  transition: opacity 0.3s ease-out;
}

.skeleton-overlay.hidden {
  opacity: 0;
  pointer-events: none;
}
```

**Alternatives Considered**:
- Replace DOM content: Rejected (causes layout shift, flicker)
- Display toggle: Rejected (no smooth transition)
- FLIP animation: Rejected (overkill for this use case)

---

### RQ-4: Accessibility for Loading States

**Question**: What ARIA attributes are needed for skeleton loading states?

**Decision**: Use `aria-busy="true"` on container, `aria-hidden="true"` on skeleton elements

**Rationale**:
- `aria-busy` indicates content is loading (screen readers announce)
- `aria-hidden` prevents skeleton from being read
- Follows WAI-ARIA loading pattern

**Implementation Pattern**:
```html
<div class="chart-container" aria-busy="true" aria-label="Chart loading">
  <div class="skeleton-overlay" aria-hidden="true">
    <!-- skeleton shapes -->
  </div>
  <canvas class="chart-content"><!-- real chart --></canvas>
</div>
```

When loading complete:
```javascript
container.setAttribute('aria-busy', 'false');
```

**Alternatives Considered**:
- `role="progressbar"`: Rejected (skeleton is not a progress indicator)
- Live region announcements: Rejected (too verbose for frequent updates)

---

### RQ-5: Skeleton Timeout and Error States

**Question**: How to handle skeleton timeout (30s) and transition to error state?

**Decision**: Use setTimeout with cleanup, transition to error component on timeout

**Rationale**:
- Simple timer pattern, easy to cancel on success
- Error state uses same overlay pattern for consistency
- Prevents infinite skeleton (user always gets feedback)

**Implementation Pattern**:
```javascript
let timeouts = {};

function startSkeletonWithTimeout(component, timeoutMs = 30000) {
  showSkeleton(component);
  timeouts[component] = setTimeout(() => {
    hideSkeleton(component);
    showError(component, 'Request timed out. Please try again.');
  }, timeoutMs);
}

function skeletonSuccess(component) {
  clearTimeout(timeouts[component]);
  hideSkeleton(component);
}
```

**Alternatives Considered**:
- No timeout: Rejected (violates FR-010)
- Retry automatically: Rejected (spec doesn't require, adds complexity)

## Summary

| RQ | Decision | Key Pattern |
|----|----------|-------------|
| RQ-1 | CSS gradient animation | `@keyframes shimmer` with `linear-gradient` |
| RQ-2 | Object-based state | `skeletonState[component] = true/false` |
| RQ-3 | Opacity transition | Absolute positioned skeleton fades out |
| RQ-4 | ARIA busy pattern | `aria-busy="true"`, `aria-hidden="true"` |
| RQ-5 | Timeout with error | 30s setTimeout, transition to error state |

All research questions resolved. Ready for Phase 1.
