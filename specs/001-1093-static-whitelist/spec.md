# Feature 1093: Fix Static File Whitelist for Dashboard JS Files

**Feature Branch**: `001-1093-static-whitelist`
**Created**: 2025-12-28
**Status**: Implementing

## Problem Statement

The dashboard HTML (`index.html`) references JavaScript files with paths like `/config.js`, `/cache.js`, `/ohlc.js`, etc., but the FastAPI handler only serves static files from the `/static/` prefix route. Additionally, the handler's whitelist (`ALLOWED_STATIC_FILES`) only includes 3 files, while 7 static files need to be served.

This causes 404 errors when the browser tries to load the dashboard JavaScript files, rendering the dashboard non-functional.

## Root Cause Analysis

1. **Path mismatch**: `index.html` uses `/app.js` but handler has `@app.get("/static/{filename}")`
2. **Incomplete whitelist**: Only `app.js`, `config.js`, `styles.css` were whitelisted
3. **Missing files**: `cache.js`, `ohlc.js`, `timeseries.js`, `unified-resolution.js` not in whitelist

## User Scenarios & Testing

### User Story 1 - Dashboard Static Files Load (Priority: P1)

User opens the dashboard URL and all JavaScript/CSS files load successfully, enabling the OHLC chart and resolution selector to function.

**Why this priority**: Without static files loading, the dashboard is completely non-functional.

**Independent Test**: Open dashboard URL, check DevTools Network tab shows 200 for all .js and .css files.

**Acceptance Scenarios**:

1. **Given** user navigates to dashboard URL, **When** page loads, **Then** all 7 static files return HTTP 200
2. **Given** static files are loaded, **When** user views dashboard, **Then** OHLC chart renders correctly
3. **Given** OHLC chart is visible, **When** user selects a resolution, **Then** chart updates to show selected time bucket

## Requirements

### Functional Requirements

- **FR-001**: All static files (7 total) MUST be served with correct MIME types via `/static/` prefix
- **FR-002**: index.html MUST reference all static files using `/static/` prefix
- **FR-003**: Static file whitelist MUST include all dashboard JS files (security requirement)

## Solution

### Changes Made

1. **Update index.html** - Change all local static file references to use `/static/` prefix:
   - `/styles.css` → `/static/styles.css`
   - `/config.js` → `/static/config.js`
   - `/cache.js` → `/static/cache.js`
   - `/ohlc.js` → `/static/ohlc.js`
   - `/timeseries.js` → `/static/timeseries.js`
   - `/unified-resolution.js` → `/static/unified-resolution.js`
   - `/app.js` → `/static/app.js`

2. **Update handler.py** - Add all 7 files to ALLOWED_STATIC_FILES whitelist and serve_static() function

### Files Modified

- `src/dashboard/index.html` - Fixed static file path references
- `src/lambdas/dashboard/handler.py` - Added 4 missing files to whitelist

## Success Criteria

- **SC-001**: All 7 static files return HTTP 200 when dashboard loads
- **SC-002**: OHLC chart renders with price data
- **SC-003**: Resolution selector changes chart time bucket correctly

## Security Note

All static files are served via explicit whitelist pattern to prevent path injection attacks (CodeQL py/path-injection). Each file requires:
1. Entry in `ALLOWED_STATIC_FILES` dictionary
2. Explicit `elif` branch in `serve_static()` function with hardcoded path
