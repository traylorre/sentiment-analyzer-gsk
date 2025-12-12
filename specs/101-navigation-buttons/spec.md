# Feature 101: Add Navigation Buttons to All Pages

## Summary

Add visible back/forward navigation buttons to all pages in the Interview Dashboard to complement existing swipe gesture navigation.

## Problem Statement

The Interview Dashboard relies solely on swipe gestures for navigation between sections. While this works on touch devices, it's not discoverable and requires users to know the gesture exists. Adding visible navigation buttons improves UX and provides an obvious navigation mechanism.

## Solution

Add a `.section-nav` container at the bottom of each section (except welcome) with:
- "← Back" button linking to the previous section
- "Next →" button linking to the next section
- Last section (infra) only has back button with spacer for layout balance

## Changes

### CSS (interview/index.html)

Added `.section-nav` styles:
```css
.section-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
}

.section-nav .btn {
    min-width: 120px;
}

.section-nav-spacer {
    width: 120px;
}
```

### HTML (interview/index.html)

Added navigation to 12 sections (2-13):

| Section | Back → | Next → |
|---------|--------|--------|
| architecture | welcome | auth |
| auth | architecture | config |
| config | auth | sentiment |
| sentiment | config | external |
| external | sentiment | circuit |
| circuit | external | traffic |
| traffic | circuit | chaos |
| chaos | traffic | caching |
| caching | chaos | observability |
| observability | caching | testing |
| testing | observability | infra |
| infra | testing | (none) |

## Testing

- Visual verification: Navigate through all 13 sections using buttons
- Verify swipe gestures still work alongside buttons
- Verify consistent styling across all sections

## Success Criteria

- [x] All 12 sections (2-13) have navigation buttons
- [x] Welcome section retains "Start the Tour" button only
- [x] Last section has only back button
- [x] Buttons are consistent with existing `.btn` styling
- [x] Border separator provides visual distinction
