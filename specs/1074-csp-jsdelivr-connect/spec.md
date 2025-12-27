# Feature Specification: CSP jsdelivr.net connect-src

**Feature Branch**: `1074-csp-jsdelivr-connect`
**Created**: 2025-12-27
**Status**: Implementation Complete
**Input**: Fix CSP blocking Hammer.js source maps from cdn.jsdelivr.net

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Price Chart Pan Gestures Work (Priority: P1)

As a user viewing the Price Chart, I want left-click-drag pan functionality to work without browser console errors, so I can navigate through historical price data.

**Why this priority**: Pan gestures (Feature 1071) require Hammer.js which loads from cdn.jsdelivr.net. The browser's CSP currently blocks source map requests to this CDN, causing console errors and potentially impacting gesture recognition.

**Independent Test**: Can be fully tested by opening the dashboard in a browser, checking the console for CSP violations, and verifying pan gestures work on the Price Chart.

**Acceptance Scenarios**:

1. **Given** a user loads the dashboard, **When** Hammer.js attempts to load source maps, **Then** no CSP violation errors appear in the console
2. **Given** a user views the Price Chart, **When** they left-click and drag, **Then** the chart pans horizontally through the data

---

### Edge Cases

- If cdn.jsdelivr.net is unreachable, the page still loads (scripts have crossorigin="anonymous")
- Source maps are optional for functionality; this fix improves debugging experience

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CloudFront CSP `connect-src` directive MUST include `https://cdn.jsdelivr.net`
- **FR-002**: Existing CSP directives (script-src, style-src, etc.) MUST remain unchanged
- **FR-003**: Browser console MUST NOT show CSP violation errors for cdn.jsdelivr.net

### Key Entities

- **CloudFront Distribution**: Response headers include CSP policy
- **CSP Header**: `content_security_policy` Terraform variable in cloudfront module

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero CSP violation errors in browser console when loading dashboard
- **SC-002**: Hammer.js source maps load without blocking (visible in Network tab)
- **SC-003**: Pan gestures functional on Price Chart (left-click-drag moves chart)

## Implementation Notes

The fix adds `https://cdn.jsdelivr.net` to the `connect-src` directive in:
- `infrastructure/terraform/modules/cloudfront/variables.tf` line 34

This allows browsers to make source map requests to the CDN without CSP violations.
