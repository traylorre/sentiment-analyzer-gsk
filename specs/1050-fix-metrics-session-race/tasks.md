# Implementation Tasks: Fix Legacy Dashboard 401 on /api/v2/metrics

**Feature**: 1050-fix-metrics-session-race
**Plan**: [plan.md](./plan.md)
**Spec**: [spec.md](./spec.md)

## Tasks

### T001: Update config.js with session constants

**File**: `src/dashboard/config.js`
**Priority**: P1
**Estimate**: 5 min

**Changes**:
1. Add `SESSION_KEY: 'sentiment_dashboard_session'` to CONFIG
2. Add `AUTH_ANONYMOUS: '/api/v2/auth/anonymous'` to ENDPOINTS
3. Remove or comment out deprecated `API_KEY` reference

**Acceptance**:
- [ ] SESSION_KEY constant exists
- [ ] AUTH_ANONYMOUS endpoint exists
- [ ] API_KEY reference removed/deprecated

---

### T002: Add session initialization to app.js

**File**: `src/dashboard/app.js`
**Priority**: P1
**Estimate**: 15 min

**Changes**:
1. Add module-level `let sessionUserId = null;`
2. Add `isValidUUID(str)` helper function (UUID4 regex validation)
3. Add `async function initSession()`:
   - Try to load from `localStorage.getItem(CONFIG.SESSION_KEY)`
   - If valid UUID, use it
   - If not, POST to `/api/v2/auth/anonymous` to get new UUID
   - Store in localStorage and sessionUserId variable
   - Return true on success, false on failure

**Acceptance**:
- [ ] sessionUserId variable exists
- [ ] isValidUUID function validates UUID4 format
- [ ] initSession checks localStorage first
- [ ] initSession calls anonymous auth endpoint if needed
- [ ] initSession stores UUID in localStorage

---

### T003: Update initDashboard to initialize session first

**File**: `src/dashboard/app.js`
**Priority**: P1
**Estimate**: 5 min

**Changes**:
1. Call `await initSession()` at start of `initDashboard()`
2. If initSession returns false, show error and return early
3. Only proceed to `fetchMetrics()` after session is established

**Acceptance**:
- [ ] initSession called before fetchMetrics
- [ ] Error handling for session init failure
- [ ] Dashboard blocked until session ready (FR-006)

---

### T004: Update fetchMetrics to use X-User-ID header

**File**: `src/dashboard/app.js`
**Priority**: P1
**Estimate**: 5 min

**Changes**:
1. Remove `CONFIG.API_KEY` check
2. Add `'X-User-ID': sessionUserId` to headers object
3. Always include the header (session is guaranteed by T003)

**Acceptance**:
- [ ] X-User-ID header added to fetch request
- [ ] API_KEY logic removed
- [ ] No 401 errors on /api/v2/metrics

---

### T005: Update connectSSE for authenticated connections

**File**: `src/dashboard/app.js`
**Priority**: P2
**Estimate**: 5 min

**Changes**:
1. EventSource doesn't support custom headers natively
2. Option A: Append `?user_id={sessionUserId}` to SSE URL
3. Option B: Backend may not require auth for SSE (check)

**Note**: Check if SSE endpoint requires auth. If not, skip this task.

**Acceptance**:
- [ ] SSE connection works with session auth (if required)

---

### T006: Test in browser

**File**: N/A (manual testing)
**Priority**: P1
**Estimate**: 10 min

**Steps**:
1. Clear localStorage
2. Load dashboard URL
3. Verify no 401 errors in console
4. Verify metrics load
5. Reload page, verify session reused (no new POST to /auth/anonymous)
6. Test SSE connection works

**Acceptance**:
- [ ] SC-001: No 401 errors
- [ ] SC-002: Metrics display within 5 seconds
- [ ] SC-003: Session persists across reloads
- [ ] SC-004: SSE and polling work

## Summary

| Task | Priority | File | Status |
|------|----------|------|--------|
| T001 | P1 | config.js | pending |
| T002 | P1 | app.js | pending |
| T003 | P1 | app.js | pending |
| T004 | P1 | app.js | pending |
| T005 | P2 | app.js | pending |
| T006 | P1 | manual | pending |
