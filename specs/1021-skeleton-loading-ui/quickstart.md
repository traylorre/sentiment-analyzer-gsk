# Quickstart: Skeleton Loading UI

## Overview

This feature adds skeleton loading placeholders to the sentiment dashboard, replacing all loading spinners with smooth skeleton animations during data fetches.

## Verify Skeleton Behavior

### 1. Initial Page Load

```bash
# Start local dashboard (if available)
cd src/dashboard
python -m http.server 8080

# Open browser with network throttling
# Chrome DevTools → Network tab → Throttle → Slow 3G
```

**Expected**: Skeleton placeholders appear within 100ms for chart, ticker list, and resolution selector. Real content fades in when data arrives.

### 2. Resolution Switch

1. Load dashboard normally
2. Click a different resolution (e.g., 1h → 5m)
3. **Expected**: Chart area shows skeleton during fetch, then smoothly transitions to new data

### 3. Verify Zero Spinners

```javascript
// Run in browser console
document.querySelectorAll('.spinner, .loading-spinner, [class*="spin"]').length
// Expected: 0
```

## Run E2E Tests

```bash
# From repo root
pytest tests/e2e/test_skeleton_loading.py -v --headed
```

**Test Coverage**:
- Initial load shows skeleton within 100ms
- Skeleton-to-content transition under 300ms
- Zero spinners present during any operation
- Accessibility attributes present (`aria-busy`, `aria-hidden`)

## CSS Classes Reference

| Class | Purpose |
|-------|---------|
| `.skeleton` | Base skeleton styling with shimmer animation |
| `.skeleton-chart` | Chart area placeholder dimensions |
| `.skeleton-ticker-item` | Ticker list item placeholder |
| `.skeleton-resolution` | Resolution selector placeholder |
| `.skeleton-visible` | Shows skeleton overlay |
| `.skeleton-overlay` | Absolutely positioned skeleton container |

## JavaScript API

```javascript
// Show skeleton for a component
showSkeleton('chart');

// Hide skeleton (with smooth transition)
hideSkeleton('chart');

// Start skeleton with 30s timeout
startSkeletonWithTimeout('chart');

// Cancel timeout and hide (call when data arrives)
skeletonSuccess('chart');

// Check if component is in skeleton state
skeletonState.chart // true/false
```

## Troubleshooting

### Skeleton Not Appearing
- Check that `data-skeleton` attribute matches component name
- Verify `.skeleton-overlay` has `position: absolute`
- Ensure parent container has `position: relative`

### Flicker During Transition
- Confirm `transition: opacity 0.3s` is present on skeleton overlay
- Verify content is rendered before skeleton is hidden

### Skeleton Stays Forever
- Check timeout is working: should show error after 30s
- Verify `skeletonSuccess()` is called when data arrives
- Check for JavaScript errors in console

### Screen Reader Issues
- Verify `aria-busy="true"` on container during load
- Confirm `aria-busy="false"` set when complete
- Check `aria-hidden="true"` on skeleton elements
