# Implementation Plan -- Feature 1309: E2E URL Guards

## Change Set

### Change 1: test_cognito_auth.py -- Add pytest.skip guards to 4 api_url fixtures

**File**: `tests/e2e/test_cognito_auth.py`

Each of the 4 `api_url` fixtures (lines 33, 78, 126, 187) currently returns:
```python
return os.environ.get("PREPROD_API_URL", "").rstrip("/")
```

**Change**: Replace single return with URL extraction + guard + return:
```python
url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
if not url:
    pytest.skip("PREPROD_API_URL not set")
return url
```

**Locations** (4 fixtures, identical change):
- Line 33-34 (TestProtectedEndpoints)
- Line 78-79 (TestPublicEndpoints)
- Line 126-127 (TestCORSOnErrorResponses)
- Line 187-188 (TestAnonymousSessions)

### Change 2: test_waf_protection.py -- Add pytest.skip guards to 4 api_url fixtures

**File**: `tests/e2e/test_waf_protection.py`

Same pattern as Change 1. Four fixtures at lines 31, 76, 107, 130.

**Locations** (4 fixtures, identical change):
- Line 31-32 (TestSQLInjectionBlocked)
- Line 76-77 (TestXSSBlocked)
- Line 107-108 (TestOptionsExempt)
- Line 130-131 (TestNormalTrafficPasses)

### Change 3: test_cors_404_e2e.py -- No changes needed

**File**: `tests/e2e/test_cors_404_e2e.py`

Already has `skip_if_no_url` autouse fixture (line 39-42) that correctly
calls `pytest.skip()` when `PREPROD_API_URL` is empty. The `PREPROD_CORS_ORIGIN`
hardcoded fallback (line 22-24) is intentional -- it must match Terraform config.

**Decision**: No changes. Already correct.

### Change 4: api_client.py -- Add ValueError for empty base_url in HTTP mode

**File**: `tests/e2e/helpers/api_client.py`

**Location**: `__init__` method, after line 71 (`self.base_url = raw_base_url.rstrip("/")`),
before line 74 (`raw_sse_url = ...`).

**Insert** (after line 71):
```python
if self._transport_mode == "http" and not self.base_url:
    raise ValueError(
        "base_url is required for HTTP transport mode. "
        "Set PREPROD_API_URL environment variable or pass base_url explicitly."
    )
```

**Why after line 71**: The transport mode is already set on line 66. The base_url
is normalized on line 71. The validation must happen before SSE URL fallback
logic (line 77) which uses `self.base_url`.

## Files Modified

| File | Type | Lines Changed |
|------|------|--------------|
| `tests/e2e/test_cognito_auth.py` | Test | 4 fixtures, +8 lines |
| `tests/e2e/test_waf_protection.py` | Test | 4 fixtures, +8 lines |
| `tests/e2e/helpers/api_client.py` | Helper | 1 insertion, +4 lines |

## Files NOT Modified

| File | Reason |
|------|--------|
| `tests/e2e/test_cors_404_e2e.py` | Already has correct guards |

## Risk Assessment

**Risk**: LOW. Changes are additive guards that only trigger when env vars are missing.
No existing test logic, assertions, or execution paths are modified.

**Rollback**: Revert the 3 files. No database, infrastructure, or configuration changes.
