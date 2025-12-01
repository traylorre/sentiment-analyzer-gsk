# Quickstart: Interview Dashboard Swipe Gestures

**Feature**: 013-interview-swipe-gestures
**File to Modify**: `interview/index.html`

## Overview

This guide explains how to implement swipe gesture navigation for the interview dashboard. The implementation uses vanilla JavaScript TouchEvent API with no external dependencies.

## Implementation Checklist

- [ ] Add CSS for swipe transitions
- [ ] Add touch detection and gesture state management
- [ ] Implement edge swipe exclusion (20px from edges)
- [ ] Implement interactive transitions (content follows finger)
- [ ] Implement completion threshold (30% viewport OR velocity)
- [ ] Implement rubber-band resistance at boundaries
- [ ] Integrate with existing navigation (hamburger menu sync)
- [ ] Test on mobile devices

## CSS Additions

Add these styles to the `<style>` section:

```css
/* Swipe transition support */
.section {
  will-change: transform;
  touch-action: pan-y; /* Allow vertical scroll, capture horizontal */
}

.section.swiping {
  transition: none; /* Disable transitions during active swipe */
}

.section.transitioning {
  transition: transform 250ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* Rubber-band bounce animation */
.section.bouncing {
  transition: transform 300ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
```

## JavaScript Implementation

Add this script before the closing `</body>` tag:

```javascript
// Swipe Gesture Navigation
(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    edgeThreshold: 20,        // Pixels from screen edge to ignore
    swipeThreshold: 0.3,      // 30% of viewport width to complete swipe
    velocityThreshold: 0.5,   // px/ms for flick detection
    rubberBandResistance: 0.3,
    maxRubberBand: 100,       // Max stretch in pixels
    transitionDuration: 250   // ms
  };

  // State
  let touchStartX = 0;
  let touchStartY = 0;
  let touchCurrentX = 0;
  let touchStartTime = 0;
  let isSwiping = false;
  let isHorizontalSwipe = null;
  let currentSectionIndex = 0;

  // Get all section IDs in order
  const sectionIds = [];
  document.querySelectorAll('.nav-item[data-section]').forEach(item => {
    sectionIds.push(item.dataset.section);
  });

  // Fallback: get from DOM if data-section not available
  if (sectionIds.length === 0) {
    document.querySelectorAll('.section').forEach(section => {
      sectionIds.push(section.id);
    });
  }

  // Touch capability detection
  const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  if (!isTouchDevice) return; // Exit early on desktop

  // Get main content area
  const mainContent = document.querySelector('.main');
  if (!mainContent) return;

  // Helper: Get current section index
  function getCurrentSectionIndex() {
    const activeSection = document.querySelector('.section.active');
    if (!activeSection) return 0;
    return sectionIds.indexOf(activeSection.id);
  }

  // Helper: Check if touch started near edge
  function isEdgeTouch(x) {
    return x < CONFIG.edgeThreshold || x > window.innerWidth - CONFIG.edgeThreshold;
  }

  // Helper: Apply rubber-band effect
  function applyRubberBand(delta, atBoundary) {
    if (!atBoundary) return delta;
    const sign = Math.sign(delta);
    const abs = Math.abs(delta);
    return sign * Math.min(abs * CONFIG.rubberBandResistance, CONFIG.maxRubberBand);
  }

  // Helper: Navigate to section
  function navigateToSection(index, animate = true) {
    if (index < 0 || index >= sectionIds.length) return;

    const targetId = sectionIds[index];
    const targetSection = document.getElementById(targetId);
    const currentSection = document.querySelector('.section.active');

    if (!targetSection || targetSection === currentSection) return;

    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
      if (item.dataset.section === targetId || item.getAttribute('onclick')?.includes(targetId)) {
        item.classList.add('active');
      }
    });

    // Switch sections
    if (currentSection) {
      currentSection.classList.remove('active', 'swiping', 'transitioning', 'bouncing');
      currentSection.style.transform = '';
    }

    targetSection.classList.add('active');
    if (animate) {
      targetSection.classList.add('transitioning');
      setTimeout(() => targetSection.classList.remove('transitioning'), CONFIG.transitionDuration);
    }

    currentSectionIndex = index;
  }

  // Touch start handler
  function handleTouchStart(e) {
    // Ignore if menu is open (check for sidebar overlay)
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && getComputedStyle(sidebar).transform !== 'none') {
      // Sidebar might be transformed for mobile menu
    }

    const touch = e.touches[0];

    // Ignore edge touches
    if (isEdgeTouch(touch.clientX)) return;

    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    touchCurrentX = touch.clientX;
    touchStartTime = Date.now();
    isSwiping = true;
    isHorizontalSwipe = null;

    currentSectionIndex = getCurrentSectionIndex();

    const activeSection = document.querySelector('.section.active');
    if (activeSection) {
      activeSection.classList.add('swiping');
      activeSection.classList.remove('transitioning', 'bouncing');
    }
  }

  // Touch move handler
  function handleTouchMove(e) {
    if (!isSwiping) return;

    const touch = e.touches[0];
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;

    // Determine swipe direction on first significant movement
    if (isHorizontalSwipe === null) {
      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);

      if (absX > 10 || absY > 10) {
        // Horizontal if X > Y * 1.5
        isHorizontalSwipe = absX > absY * 1.5;
      }
    }

    // If vertical swipe, abort
    if (isHorizontalSwipe === false) {
      cancelSwipe();
      return;
    }

    // If horizontal swipe confirmed
    if (isHorizontalSwipe === true) {
      e.preventDefault(); // Prevent scroll

      touchCurrentX = touch.clientX;

      // Check boundary conditions
      const atLeftBoundary = currentSectionIndex === 0 && deltaX > 0;
      const atRightBoundary = currentSectionIndex === sectionIds.length - 1 && deltaX < 0;
      const atBoundary = atLeftBoundary || atRightBoundary;

      // Apply transform (with rubber-band if at boundary)
      const transformX = applyRubberBand(deltaX, atBoundary);

      const activeSection = document.querySelector('.section.active');
      if (activeSection) {
        activeSection.style.transform = `translateX(${transformX}px)`;
      }
    }
  }

  // Touch end handler
  function handleTouchEnd(e) {
    if (!isSwiping || isHorizontalSwipe !== true) {
      cancelSwipe();
      return;
    }

    const deltaX = touchCurrentX - touchStartX;
    const deltaTime = Date.now() - touchStartTime;
    const velocity = Math.abs(deltaX) / deltaTime;
    const viewportWidth = window.innerWidth;

    const activeSection = document.querySelector('.section.active');

    // Determine if swipe should complete
    const swipeRatio = Math.abs(deltaX) / viewportWidth;
    const shouldComplete = swipeRatio > CONFIG.swipeThreshold || velocity > CONFIG.velocityThreshold;

    // Determine direction
    const goingLeft = deltaX < 0; // Swipe left = next section
    const goingRight = deltaX > 0; // Swipe right = previous section

    // Check boundaries
    const canGoNext = currentSectionIndex < sectionIds.length - 1;
    const canGoPrev = currentSectionIndex > 0;

    if (activeSection) {
      activeSection.classList.remove('swiping');
    }

    if (shouldComplete && goingLeft && canGoNext) {
      // Complete swipe to next section
      navigateToSection(currentSectionIndex + 1, true);
    } else if (shouldComplete && goingRight && canGoPrev) {
      // Complete swipe to previous section
      navigateToSection(currentSectionIndex - 1, true);
    } else {
      // Snap back (rubber-band or cancelled swipe)
      if (activeSection) {
        activeSection.classList.add('bouncing');
        activeSection.style.transform = 'translateX(0)';
        setTimeout(() => {
          activeSection.classList.remove('bouncing');
          activeSection.style.transform = '';
        }, 300);
      }
    }

    resetSwipeState();
  }

  // Cancel swipe
  function cancelSwipe() {
    const activeSection = document.querySelector('.section.active');
    if (activeSection) {
      activeSection.classList.remove('swiping');
      activeSection.style.transform = '';
    }
    resetSwipeState();
  }

  // Reset state
  function resetSwipeState() {
    isSwiping = false;
    isHorizontalSwipe = null;
    touchStartX = 0;
    touchStartY = 0;
    touchCurrentX = 0;
  }

  // Bind events
  mainContent.addEventListener('touchstart', handleTouchStart, { passive: true });
  mainContent.addEventListener('touchmove', handleTouchMove, { passive: false });
  mainContent.addEventListener('touchend', handleTouchEnd, { passive: true });
  mainContent.addEventListener('touchcancel', cancelSwipe, { passive: true });

  // Sync with existing navigation
  // Override or wrap existing showSection function if it exists
  const originalShowSection = window.showSection;
  window.showSection = function(sectionId) {
    if (originalShowSection) {
      originalShowSection(sectionId);
    }
    currentSectionIndex = sectionIds.indexOf(sectionId);
  };

})();
```

## Testing

### Desktop (should NOT trigger swipes)
1. Open dashboard in Chrome/Firefox
2. Click and drag in main content area
3. Verify: No section transitions occur
4. Verify: Keyboard shortcuts (Ctrl+1-9) still work

### Mobile (Chrome DevTools)
1. Open DevTools > Toggle Device Toolbar
2. Select mobile device (e.g., iPhone 12)
3. Test swipe gestures in main content area
4. Verify: Content follows finger during swipe
5. Verify: Releases past 30% complete transition
6. Verify: Releases before 30% snap back

### Mobile (Real Device)
1. Deploy to preprod or use `python -m http.server`
2. Open on physical iOS/Android device
3. Test all acceptance scenarios from spec
4. Verify: Edge swipes (from screen edge) do NOT trigger navigation
5. Verify: Rubber-band effect at first/last section

## Integration Notes

### Hamburger Menu

The existing hamburger menu navigation should continue to work. The swipe implementation:
- Updates `currentSectionIndex` when sections change via any method
- Wraps `window.showSection` to stay in sync
- Updates `.nav-item.active` class after swipe navigation

### Existing Keyboard Shortcuts

Keyboard shortcuts (Ctrl+1-9) remain unchanged. The swipe handler only binds to touch events.
