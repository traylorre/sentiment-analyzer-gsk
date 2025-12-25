# Feature 1049: Standardize Auth Extraction in ohlc.py

## Problem Statement

`ohlc.py` uses raw `request.headers.get("X-User-ID")` instead of the standard `get_user_id_from_request()` middleware helper used by all other endpoints.

**Issues:**
1. No UUID validation - accepts any string as user_id
2. Doesn't support Bearer token auth
3. Inconsistent with rest of codebase
4. No session validation

## Files Affected

| File | Line | Current | Should Be |
|------|------|---------|-----------|
| `ohlc.py` | 94 | `request.headers.get("X-User-ID")` | `get_user_id_from_request(request)` |
| `ohlc.py` | 299 | `request.headers.get("X-User-ID")` | `get_user_id_from_request(request)` |

## Solution

Import and use `get_user_id_from_request` from `router_v2.py` (or extract to shared location if circular import).

## Acceptance Criteria

- [ ] AC1: Both OHLC endpoints use `get_user_id_from_request()`
- [ ] AC2: Bearer token auth works for OHLC endpoints
- [ ] AC3: Invalid UUID format returns 401
- [ ] AC4: All existing tests pass

## Risk

Low - simple refactor to use existing helper.
