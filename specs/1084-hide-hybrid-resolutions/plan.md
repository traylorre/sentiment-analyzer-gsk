# Implementation Plan: Hide Hybrid Resolution Buckets

**Feature Branch**: `1084-hide-hybrid-resolutions`
**Created**: 2025-12-28

## Technical Context

- **Tech Stack**: Vanilla JavaScript (browser), Chart.js
- **Affected Files**: `src/dashboard/unified-resolution.js`, `src/dashboard/config.js`
- **Dependencies**: None (uses existing `exact` property)

## Architecture

No architectural changes required. This is a simple filter on the existing UNIFIED_RESOLUTIONS array.

## File Changes

1. **unified-resolution.js**: Filter buttons to only show `exact: true` resolutions
2. **config.js**: Ensure DEFAULT_UNIFIED_RESOLUTION is an exact resolution (currently '1h' which is exact)

## Implementation Strategy

1. Modify `renderSelector()` to filter UNIFIED_RESOLUTIONS by `exact === true`
2. Modify `loadSavedResolution()` to validate saved preference is still visible
3. Add static analysis test to verify only exact resolutions render
