# Research: Interview Dashboard Swipe Gestures

**Feature**: 013-interview-swipe-gestures
**Date**: 2025-12-01

## Research Questions

1. Which gesture library best fits a vanilla JS, single-file HTML architecture?
2. How to implement interactive transitions (content follows finger)?
3. How to implement rubber-band resistance at boundaries?
4. How to detect touch vs mouse to disable on desktop?

---

## 1. Gesture Library Selection

### Options Evaluated

| Library | Size | Maintained | CDN Available | Interactive Transitions |
|---------|------|------------|---------------|------------------------|
| Hammer.js | 45KB | No (9+ years) | Yes | Manual implementation |
| AlloyFinger | 3KB | Limited | Yes | Manual implementation |
| @composi/gestures | 5KB | Active | No (npm only) | Manual implementation |
| Vanilla TouchEvent | 0KB | N/A | N/A | Full control |

### Decision: **Vanilla TouchEvent API**

**Rationale**:
- Zero additional dependencies (spec requirement: minimal footprint)
- Full control over interactive transitions (spec requirement: content follows finger)
- No CDN dependency risk (Hammer.js is unmaintained)
- Standard browser API with excellent mobile support
- Easier to implement rubber-band physics without library abstractions

**Alternatives Rejected**:
- **Hammer.js**: Unmaintained for 9+ years, potential Firefox issues, abstracts away pan delta needed for interactive transitions
- **AlloyFinger**: Small but limited community, no interactive transition support out of the box
- **@composi/gestures**: npm-only distribution doesn't fit single-file HTML architecture

---

## 2. Interactive Transition Implementation

### Approach: Direct CSS Transform Manipulation

```javascript
// During touchmove
const deltaX = currentX - startX;
element.style.transform = `translateX(${deltaX}px)`;

// On touchend - animate to final position
element.style.transition = 'transform 250ms ease-out';
element.style.transform = 'translateX(0)'; // or next section offset
```

### Key Implementation Details

1. **Capture touch start position** - Store `touch.clientX` on `touchstart`
2. **Track delta during move** - Calculate `currentX - startX` on each `touchmove`
3. **Apply transform directly** - No animation during drag, just `translateX(deltaX)`
4. **Determine completion threshold** - 30% of viewport width OR velocity > threshold
5. **Animate completion** - Add CSS transition, set final transform value

### Velocity Calculation

```javascript
// Track last few positions with timestamps
const velocityX = (currentX - prevX) / (currentTime - prevTime);
// Threshold: ~0.5px/ms indicates intentional flick
```

---

## 3. Rubber-Band Resistance Implementation

### Physics Model

When at first/last section and user drags beyond boundary:
- Apply diminishing returns to drag distance
- Common formula: `displayOffset = dragDistance * (1 - dragDistance / maxStretch)`
- Or simpler: `displayOffset = dragDistance * 0.3` (30% of actual drag)

### Implementation

```javascript
function applyRubberBand(delta, atBoundary) {
  if (!atBoundary) return delta;

  // Diminishing resistance curve
  const resistance = 0.3;
  const maxStretch = 100; // pixels
  return Math.sign(delta) * Math.min(Math.abs(delta) * resistance, maxStretch);
}
```

### Release Animation

On release at boundary, animate back to 0 with spring-like easing:
```css
transition: transform 300ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
```

---

## 4. Touch vs Mouse Detection

### Approach: Feature Detection + Event Type

```javascript
// Check for touch capability
const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

// Only bind touch events, ignore mouse events entirely
if (isTouchDevice) {
  element.addEventListener('touchstart', handleTouchStart, { passive: false });
  element.addEventListener('touchmove', handleTouchMove, { passive: false });
  element.addEventListener('touchend', handleTouchEnd);
}
```

### Edge Swipe Detection

```javascript
function isEdgeSwipe(startX) {
  const edgeThreshold = 20; // pixels from screen edge
  return startX < edgeThreshold || startX > window.innerWidth - edgeThreshold;
}

// In touchstart handler
if (isEdgeSwipe(touch.clientX)) {
  // Don't handle this gesture - let browser/OS handle it
  return;
}
```

---

## 5. Section Container Architecture

### Current Structure (from index.html)

```html
<div class="main">
  <div class="section" id="section-welcome">...</div>
  <div class="section" id="section-architecture">...</div>
  <!-- ... more sections ... -->
</div>
```

### Modified Structure for Swipe Support

```html
<div class="main swipe-container">
  <div class="swipe-viewport">
    <div class="section" id="section-welcome">...</div>
    <div class="section" id="section-architecture">...</div>
    <!-- ... more sections ... -->
  </div>
</div>
```

The swipe-viewport will be transformed during gestures. Sections remain display:none/block but the active section's container moves.

**Alternative**: Keep current structure, apply transform to `.main` directly.

### Decision: Apply Transform to Active Section Only

- Simpler: No DOM restructure needed
- Works with existing display:none/block toggle
- Transform only the visible `.section.active` element

---

## 6. Hamburger Menu Integration

### Current Behavior

- Sidebar shows/hides via CSS transform or display toggle
- Navigation items have `onclick` to switch sections

### Integration Points

1. **Swipe cancelled on menu open**: Listen for menu toggle, reset any in-progress swipe
2. **Menu indicator sync**: After swipe navigation, update `.nav-item.active` class
3. **Gesture area exclusion**: If sidebar is open and overlays content, disable swipe in that area

---

## Summary of Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Gesture library | Vanilla TouchEvent | Zero deps, full control |
| Interactive transition | Direct CSS transform | 60fps, simple implementation |
| Rubber-band | 30% resistance factor | Industry standard feel |
| Touch detection | Feature detection + touchstart only | Ignores desktop automatically |
| DOM structure | Transform active section | Minimal changes to existing code |
