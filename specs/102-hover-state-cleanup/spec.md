# Feature Specification: 102-hover-state-cleanup

**Branch**: `102-hover-state-cleanup` | **Date**: 2025-12-12

## Problem Statement

All `.card` elements in the Interview Dashboard have hover effects (border glow, lift animation),
making non-interactive informational cards appear clickable when they are not.

## Root Cause Analysis

The original CSS applied hover effects to all cards:
```css
.card:hover {
    border-color: var(--accent-green);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 211, 149, 0.1);
}
```

However, cards are purely informational containers. Interactive elements (buttons) are in
separate `.api-demo` sections, not inside cards.

## Solution

Replace `.card:hover` with `.card-interactive:hover` to only apply hover effects when
explicitly marked. Since no cards are currently interactive, this effectively removes
all misleading hover effects.

### Before
```css
.card:hover {
    border-color: var(--accent-green);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 211, 149, 0.1);
}
```

### After
```css
/* Only interactive cards (with buttons/actions) should have hover effects */
.card-interactive:hover {
    border-color: var(--accent-green);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 211, 149, 0.1);
    cursor: pointer;
}
```

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| Remove hover from `.card` | Adding hover to other elements |
| Create `.card-interactive` class | Actually making any cards interactive |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | Cards no longer have hover effects | Manual test |
| SC-002 | API demo sections still work | Manual test |
| SC-003 | No visual regressions | Manual test |

## Technical Details

**File**: `interview/index.html`
**Lines changed**: 244-250 (CSS section)
**Cards audited**: 39 cards, 0 need interactive hover
