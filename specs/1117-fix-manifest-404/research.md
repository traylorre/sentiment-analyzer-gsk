# Research: Fix Manifest.json 404 Error

**Feature**: 1117-fix-manifest-404
**Date**: 2026-01-01

## Research Tasks

### 1. W3C Web App Manifest Specification

**Decision**: Use W3C Web App Manifest standard format

**Rationale**: The W3C specification defines the required and optional fields for PWA manifests. Following this standard ensures compatibility across all modern browsers.

**Required Fields** (per spec):
- `name` - Full application name
- `short_name` - Short name for home screen
- `start_url` - URL to open when app launches
- `display` - Display mode (standalone, fullscreen, minimal-ui, browser)
- `background_color` - Background color during app launch
- `theme_color` - Theme color for browser UI
- `icons` - Array of icon objects with src, sizes, type

**Alternatives Considered**:
- Minimal manifest (name only) - Rejected: Would not enable PWA install prompt
- Extended manifest with screenshots/shortcuts - Rejected: Overkill for fixing 404

### 2. Next.js Static File Serving

**Decision**: Place manifest.json in `frontend/public/` directory

**Rationale**: Next.js automatically serves files from the `public` directory at the root path. A file at `public/manifest.json` will be served at `/manifest.json`.

**Alternatives Considered**:
- API route returning JSON - Rejected: Adds complexity, unnecessary for static content
- Build-time generation - Rejected: Manifest content is static, no need for dynamic generation

### 3. Icon Requirements

**Decision**: Include 192x192 and 512x512 PNG icons

**Rationale**: These are the standard sizes required for PWA installability:
- 192x192: Required for "Add to Home Screen" on Android
- 512x512: Required for splash screen on Android, PWA install prompt

**Alternatives Considered**:
- SVG icons only - Rejected: Not universally supported for PWA icons
- Multiple sizes (48, 72, 96, 128, 144, 152, 192, 384, 512) - Rejected: Overkill; 192 and 512 cover required use cases

### 4. Color Scheme

**Decision**: Use Sentiment Analyzer brand colors
- `theme_color`: "#3b82f6" (blue-500, matches existing UI)
- `background_color`: "#ffffff" (white, standard)

**Rationale**: Maintains visual consistency with existing dashboard styling.

## Unknowns Resolved

| Unknown | Resolution |
|---------|------------|
| Icon assets | Will create simple placeholder icons; can be replaced with branded icons later |
| Exact manifest fields | Using W3C standard required fields |
| Display mode | "standalone" - provides app-like experience without browser UI |

## No Further Research Needed

This feature is straightforward - creating a static JSON file following a well-defined standard. No additional research required.
