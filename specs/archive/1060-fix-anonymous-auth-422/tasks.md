# Tasks: Feature 1060 - Fix Anonymous Auth 422 Error

## Implementation Tasks

### T001: Add body to fetch request [P1]
- Edit `src/dashboard/app.js` line 106-114
- Add `body: JSON.stringify({})` to the fetch options
- Ensure proper comma placement

**Files**: `src/dashboard/app.js`
**Verification**: No syntax errors, dashboard loads

### T002: Manual browser test [P1]
- Load dashboard in browser
- Check console for 422 errors (should be none)
- Verify session is created (console log "Created new anonymous session: xxx...")

**Verification**: Visual confirmation

## Verification Checklist

- [ ] T001: body added to fetch call
- [ ] T002: Dashboard loads without 422 errors
