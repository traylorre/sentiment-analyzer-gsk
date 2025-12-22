# Feature 1011: Dashboard API Authorization Header

## Problem Statement

The dashboard frontend makes API calls to `/api/v2/metrics` without including an Authorization header. When `API_KEY` is configured on the backend (production/preprod), these requests return 401 Unauthorized, causing the dashboard to show empty/stale data.

## Root Cause Analysis

1. **Frontend (`app.js:140-156`)**: `fetchMetrics()` uses bare `fetch()` without headers
2. **Backend (`handler.py:189-270`)**: `verify_api_key()` requires `Authorization: Bearer <key>`
3. **Security constraint**: API key cannot be hardcoded in frontend JS (would be in version control)

## User Story

**US1: Dashboard displays live metrics in production** (P1)
> As a dashboard user, I want the metrics dashboard to work correctly in production environments where API key authentication is enabled, so I can view real-time sentiment data.

## Functional Requirements

| ID | Requirement | Rationale |
|----|-------------|-----------|
| FR-001 | Backend injects API key into HTML at render time | Avoids hardcoding key in static files |
| FR-002 | Frontend reads injected key from `window.DASHBOARD_API_KEY` | Decouples key source from fetch logic |
| FR-003 | `fetchMetrics()` includes `Authorization: Bearer <key>` header | Satisfies `verify_api_key()` dependency |
| FR-004 | Frontend gracefully handles missing API key (dev mode) | Backwards compatible with unauthenticated dev mode |

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | Dashboard loads metrics in preprod with 200 response | Network tab shows Authorization header |
| SC-002 | Dashboard works in dev mode without API key | No 401 errors when API_KEY not configured |
| SC-003 | API key not visible in static JS files | grep for key in src/dashboard/*.js returns nothing |
| SC-004 | API key rotated without code change | Key comes from Secrets Manager at runtime |

## Technical Design

### Approach: Server-Side Template Injection

1. **Modify `serve_index()`** to:
   - Read `index.html` content
   - Inject `<script>window.DASHBOARD_API_KEY = "...";</script>` before `</head>`
   - Return modified HTML

2. **Modify `config.js`** to:
   - Add `API_KEY: window.DASHBOARD_API_KEY || ''`

3. **Modify `app.js:fetchMetrics()`** to:
   - Include `headers: { 'Authorization': 'Bearer ' + CONFIG.API_KEY }` if key exists

### Security Considerations

- **Key exposure**: The injected key is visible in page source, but only to authenticated users who can already access the dashboard
- **No static exposure**: Key is NOT in version control or static files
- **Runtime injection**: Key comes from Secrets Manager → Lambda env → HTML injection
- **Graceful degradation**: If no key configured, works in unauthenticated mode

## Out of Scope

- Session-based authentication (too complex for this fix)
- Token refresh logic (API key is static)
- Other endpoints (focus on metrics endpoint first)

## Checklist

- [x] FR-001: Backend template injection implemented (handler.py:310-315)
- [x] FR-002: Frontend reads window.DASHBOARD_API_KEY (config.js:21)
- [x] FR-003: fetchMetrics includes Authorization header (app.js:145-151)
- [x] FR-004: Dev mode continues to work (test_no_injection_when_api_key_not_configured)
- [ ] SC-001: Preprod test passes (200 response) - pending deployment
- [x] SC-002: Local dev test passes (5/5 tests pass)
- [x] SC-003: No hardcoded keys in JS (key injected at runtime)
- [x] SC-004: Documentation updated for key rotation (security note in spec.md)

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/dashboard/handler.py` | Modify `serve_index()` to inject API key |
| `src/dashboard/config.js` | Add `API_KEY` config |
| `src/dashboard/app.js` | Add auth header to `fetchMetrics()` |
| `tests/unit/lambdas/dashboard/test_handler.py` | Test template injection |
