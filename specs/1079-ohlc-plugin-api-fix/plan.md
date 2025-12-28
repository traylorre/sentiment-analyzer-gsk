# Implementation Plan: OHLC Plugin API Fix

**Branch**: `1079-ohlc-plugin-api-fix` | **Date**: 2025-12-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1079-ohlc-plugin-api-fix/spec.md`

## Summary

Fix OHLC chart initialization error caused by incorrect Chart.js v4.x API usage in Feature 1077. Replace `Chart.registry.plugins.items` array check with `Chart.registry.getPlugin('zoom')` method.

## Technical Context

**Language/Version**: JavaScript (ES6+)
**Primary Dependencies**: Chart.js v4.x, chartjs-plugin-zoom, Hammer.js
**Storage**: N/A (frontend-only fix)
**Testing**: Browser console, manual testing
**Target Platform**: Web browser (Chrome, Firefox, Safari, Edge)
**Project Type**: Web application (frontend fix only)
**Performance Goals**: N/A (bug fix)
**Constraints**: Must maintain backward compatibility with existing chart functionality
**Scale/Scope**: Single file change (ohlc.js)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- No complexity violations (single file, single function fix)
- No new dependencies added
- Bug fix for existing feature

## Project Structure

### Documentation (this feature)

```text
specs/1079-ohlc-plugin-api-fix/
├── plan.md              # This file
├── spec.md              # Feature specification
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
src/dashboard/
└── ohlc.js              # File containing the bug (line 347-348)
```

**Structure Decision**: Frontend-only fix, single file modification in existing dashboard module.

## Implementation Details

### Current Code (Buggy)

```javascript
// ohlc.js:343-355
if (typeof ChartZoom !== 'undefined' && typeof Chart !== 'undefined') {
    const registeredPlugins = Chart.registry?.plugins?.items || [];
    const isRegistered = registeredPlugins.some(p => p.id === 'zoom');
    if (!isRegistered) {
        Chart.register(ChartZoom);
        console.log('chartjs-plugin-zoom registered for pan/zoom functionality');
    }
} else {
    console.warn('chartjs-plugin-zoom not available - pan/zoom disabled');
}
```

### Fixed Code

```javascript
// ohlc.js:343-355
if (typeof ChartZoom !== 'undefined' && typeof Chart !== 'undefined') {
    // Chart.js v4.x uses getPlugin() method, not array access
    const isRegistered = Chart.registry.getPlugin('zoom');
    if (!isRegistered) {
        Chart.register(ChartZoom);
        console.log('chartjs-plugin-zoom registered for pan/zoom functionality');
    }
} else {
    console.warn('chartjs-plugin-zoom not available - pan/zoom disabled');
}
```

### Why This Fix Works

1. `Chart.registry.getPlugin('zoom')` is the correct Chart.js v4.x API
2. Returns the plugin object if registered, `undefined` if not
3. Works as a truthy check for the `if (!isRegistered)` condition
4. No array methods needed on internal Chart.js structures
