# Implementation Plan: Fix Legacy Dashboard 401 on /api/v2/metrics

**Branch**: `1050-fix-metrics-session-race` | **Date**: 2024-12-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1050-fix-metrics-session-race/spec.md`

## Summary

Add anonymous session authentication to the legacy vanilla JS dashboard. The dashboard currently fails with 401 on `/api/v2/metrics` because Feature 1039 removed API key auth. The fix adds session initialization that calls `/api/v2/auth/anonymous` on load and includes `X-User-ID` header in all API requests.

## Technical Context

**Language/Version**: JavaScript ES6+ (vanilla, no framework)
**Primary Dependencies**: None (browser-native fetch, localStorage, EventSource)
**Storage**: localStorage (session UUID persistence)
**Testing**: Manual browser testing, E2E smoke test via deploy pipeline
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Static web dashboard served by Lambda
**Performance Goals**: Dashboard loads in <5 seconds
**Constraints**: No build step, no npm dependencies (vanilla JS only)
**Scale/Scope**: Single dashboard page, 2 files to modify

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (speckit.specify required) | PASS | Running full speckit workflow |
| Amendment 1.9 (no workspace destruction) | N/A | No git operations |
| Complexity limits | PASS | Minimal change, 2 files |

## Project Structure

### Documentation (this feature)

```text
specs/1050-fix-metrics-session-race/
├── spec.md              # Feature specification
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Implementation tasks (next step)
```

### Source Code (files to modify)

```text
src/dashboard/
├── config.js            # Add SESSION_KEY constant, remove deprecated API_KEY
└── app.js               # Add session initialization, update fetchMetrics()
```

**Structure Decision**: Modifying existing legacy dashboard files. No new files needed.

## Implementation Approach

### Phase 1: Session State Management (config.js)

1. Add `SESSION_KEY` constant for localStorage key
2. Remove deprecated `API_KEY` reference (no longer injected)
3. Add `AUTH_ENDPOINTS` config for anonymous auth

### Phase 2: Session Initialization (app.js)

1. Add `initSession()` function:
   - Check localStorage for existing UUID
   - Validate UUID format (regex for UUID4)
   - If missing/invalid, call `POST /api/v2/auth/anonymous`
   - Store returned UUID in localStorage
   - Store in module-level `sessionUserId` variable

2. Update `initDashboard()`:
   - Call `await initSession()` BEFORE `fetchMetrics()`
   - Handle session init failure with error display

3. Update `fetchMetrics()`:
   - Remove `CONFIG.API_KEY` check
   - Add `X-User-ID: {sessionUserId}` header to all requests

4. Update `connectSSE()`:
   - SSE connections also need the user ID (query param or header)

## Complexity Tracking

No violations - this is a minimal, targeted fix with clear scope.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality | E2E smoke test in deploy pipeline |
| localStorage not available | Check availability, fallback to memory-only session |
| Session endpoint failure | Show error message, allow retry |
