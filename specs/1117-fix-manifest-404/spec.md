# Feature Specification: Fix Manifest.json 404 Error

**Feature Branch**: `1117-fix-manifest-404`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "The dashboard throws a GET /manifest.json -> 404 error. Root cause: The Next.js frontend declares manifest.json in metadata but file doesn't exist. Create PWA manifest and public directory."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Loads Without Errors (Priority: P1)

As a user accessing the sentiment analyzer dashboard, I want the page to load without console errors so that I have confidence the application is working correctly and can use it for demo purposes.

**Why this priority**: Console errors during page load undermine user confidence and make the application appear broken. For a demo-able dashboard, zero 404 errors on core assets is essential.

**Independent Test**: Can be fully tested by opening browser DevTools, navigating to the dashboard URL, and verifying no 404 errors appear in the Network tab. Delivers immediate value by eliminating visible errors.

**Acceptance Scenarios**:

1. **Given** a user navigates to the dashboard URL, **When** the page loads completely, **Then** no 404 errors appear for manifest.json in the browser console or network tab
2. **Given** a user views the network requests during page load, **When** manifest.json is requested, **Then** the server responds with HTTP 200 and valid JSON content
3. **Given** a user opens the dashboard on any modern browser (Chrome, Firefox, Safari, Edge), **When** the page loads, **Then** manifest.json loads successfully regardless of browser

---

### User Story 2 - PWA Metadata Display (Priority: P2)

As a user adding the dashboard to their home screen or bookmarks, I want the application to have proper PWA metadata so that it displays with a correct name, icon, and theme colors.

**Why this priority**: PWA metadata enhances the professional appearance of the application but is secondary to eliminating visible errors. Users who add to home screen get a better experience.

**Independent Test**: Can be tested by adding the dashboard to home screen on a mobile device or using Chrome's "Install App" feature, verifying the app name and icon display correctly.

**Acceptance Scenarios**:

1. **Given** a user installs the dashboard as a PWA, **When** viewing it on their home screen, **Then** the app displays with the configured name and icon
2. **Given** a user views the browser tab, **When** the page loads, **Then** the browser shows the correct theme color defined in the manifest

---

### Edge Cases

- What happens when manifest.json is requested before the application JavaScript loads? The manifest.json should return immediately as a static file since it doesn't depend on JavaScript execution.
- How does the system handle if the manifest.json file contains invalid JSON? The browser will gracefully ignore it and continue loading the page without PWA features.
- What happens if CDN/CloudFront caches an old 404 response? After deployment, cache invalidation may be needed to serve the new file.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST serve a valid manifest.json file at the `/manifest.json` URL path
- **FR-002**: The manifest.json file MUST conform to the W3C Web App Manifest specification
- **FR-003**: System MUST include all required manifest fields: `name`, `short_name`, `start_url`, `display`, `background_color`, `theme_color`
- **FR-004**: System MUST serve manifest.json with appropriate Content-Type header
- **FR-005**: The Next.js frontend public directory MUST exist and contain the manifest.json file
- **FR-006**: The manifest metadata declaration in layout.tsx MUST correctly reference the manifest.json path
- **FR-007**: System MUST include at least one icon reference in the manifest for PWA compliance

### Key Entities

- **Manifest File**: JSON file conforming to W3C Web App Manifest spec, contains app name, icons, theme colors, and display mode
- **Public Directory**: Static asset directory in Next.js that serves files at root URL path without transformation
- **Layout Metadata**: Next.js metadata export that declares manifest path for browser discovery

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard page loads with zero 404 errors visible in browser DevTools Network tab
- **SC-002**: GET request to /manifest.json returns HTTP 200 status code
- **SC-003**: Lighthouse PWA audit passes the "Web app manifest meets the installability requirements" check
- **SC-004**: manifest.json response time is under 100ms for cached requests
- **SC-005**: Dashboard can be installed as PWA on Chrome/Edge (Add to Home Screen option available)

## Assumptions

- The Next.js frontend is the deployed dashboard (not a legacy static dashboard)
- Static files in the public directory are served directly by the hosting platform (Amplify)
- No server-side processing is required for manifest.json (pure static file)
- The application branding (name, colors) aligns with "Sentiment Analyzer" theme
- Icon assets will be created or sourced as part of this feature (standard PWA icon sizes: 192x192, 512x512)
