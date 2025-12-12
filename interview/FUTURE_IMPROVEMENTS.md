# Interview Dashboard Future Improvements

This document tracks planned enhancements for the Interview Dashboard (`interview/index.html`).

## Priority 1: UX Polish

### Navigation Buttons (Feature 101)
**Status**: Planned
**Effort**: Medium

Add visible back/forward navigation buttons to all pages:
- "← Back" button on pages 2-13 (architecture through infra)
- "Next →" button on pages 1-12 (welcome through testing)
- Consistent positioning at bottom of each section
- Complement existing swipe gesture navigation

### Hover State Cleanup (Feature 102)
**Status**: Planned
**Effort**: Low

Remove misleading hover effects from non-interactive cards:
- Currently all `.card` elements have hover effects (border glow, lift animation)
- Only ~11 cards contain interactive buttons; ~26 are informational
- Create `.card-interactive` class with hover effects
- Apply only to cards with actual click functionality

### Auto-Highlight Animations (Feature 103)
**Status**: Planned
**Effort**: High

Guide users to interactive elements on page load:
- Add `data-interactive` attribute to clickable elements
- CSS pulse/glow animation highlighting interactive widgets
- Optional: SVG path animations between sequential actions (pixie/star trails)
- Must not interfere with existing swipe gestures

## Priority 2: Functionality

### Web-Based Traffic Generator
**Status**: Future
**Effort**: High

Move traffic generation from Python CLI to Interview Dashboard:
- Currently requires: `python3 traffic_generator.py --env preprod --scenario all`
- Web interface would allow one-click load generation
- Real-time visualization of traffic patterns
- No local Python environment required for interviewers

### GitHub Pages Root Redirect
**Status**: Planned
**Effort**: Low

Fix 404 at `https://traylorre.github.io/sentiment-analyzer-gsk/`:
- GitHub Pages serves from root but content is in `/interview/`
- Add `index.html` at root that redirects to `/interview/`
- Or configure GitHub Pages to serve from `/interview/` directory

## Priority 3: Polish

### Interview Timer Enhancements
- Audible notification at 15-minute intervals
- Visual warning at 10 minutes remaining
- Section time tracking (time spent per section)

### Mobile Responsiveness Audit
- Verify all sections render correctly on mobile
- Test swipe gestures on various devices
- Ensure API demo buttons are touch-friendly

### Accessibility Improvements
- Add ARIA labels to interactive elements
- Keyboard navigation support
- Screen reader compatibility

## Temporary Operational Changes

### Production Deployment Disabled
**Status**: Active
**Commit**: `71b37cd02b4d68057b33e81b6cdb4bcb209012d3`
**Date**: 2025-12-12

Production deployment jobs in `.github/workflows/deploy.yml` are temporarily disabled
with `if: false`. Pipeline completes after Preprod Integration Tests pass.

**To Re-enable**:
1. Remove `if: false` from jobs 5-7 (build-sse-image-prod, deploy-prod, canary)
2. Restore summary job's `needs` array to include production jobs
3. See commit message for exact line numbers

## Completed

### CloudFront ONE URL (Feature 104)
**Status**: Complete (PR #347)
**Date**: 2025-12-12

Updated "View Live Dashboard" link from Lambda Function URL to CloudFront ONE URL for proper routing to both Dashboard and SSE Lambdas.

---

*Last updated: 2025-12-12*
