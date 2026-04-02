# Tasks -- Feature 1309: E2E URL Guards

## Dependencies

```
T1 (no deps) ─┐
T2 (no deps) ─┤── T4 (verify)
T3 (no deps) ─┘
```

T1, T2, T3 are independent and can be implemented in any order.
T4 depends on all three.

---

## T1: Add pytest.skip guards to test_cognito_auth.py api_url fixtures

**File**: `tests/e2e/test_cognito_auth.py`
**Depends on**: None

Replace the single-line return in all 4 `api_url` fixtures with:
```python
url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
if not url:
    pytest.skip("PREPROD_API_URL not set")
return url
```

**Fixtures to modify** (4 total):
1. `TestProtectedEndpoints.api_url` (line ~33)
2. `TestPublicEndpoints.api_url` (line ~78)
3. `TestCORSOnErrorResponses.api_url` (line ~126)
4. `TestAnonymousSessions.api_url` (line ~187)

**Implementation note** (AR2-FINDING-4): Each edit must include the class context or preceding method to ensure unique string matching, since the fixture body is identical across all 4 classes.

**Acceptance**: `unset PREPROD_API_URL && pytest tests/e2e/test_cognito_auth.py --collect-only` shows all tests as collected (they skip at fixture time, not collection time -- the SkipInfo/skipif handles collection-time skip for wrong AWS_ENV).

- [ ] Done

---

## T2: Add pytest.skip guards to test_waf_protection.py api_url fixtures

**File**: `tests/e2e/test_waf_protection.py`
**Depends on**: None

Same pattern as T1. Replace the single-line return in all 4 `api_url` fixtures.

**Fixtures to modify** (4 total):
1. `TestSQLInjectionBlocked.api_url` (line ~31)
2. `TestXSSBlocked.api_url` (line ~76)
3. `TestOptionsExempt.api_url` (line ~107)
4. `TestNormalTrafficPasses.api_url` (line ~130)

**Acceptance**: Same as T1 but for `test_waf_protection.py`.

- [ ] Done

---

## T3: Add ValueError guard to PreprodAPIClient for empty base_url in HTTP mode

**File**: `tests/e2e/helpers/api_client.py`
**Depends on**: None

After `self.base_url = raw_base_url.rstrip("/")` (line ~71), insert:
```python
if self._transport_mode == "http" and not self.base_url:
    raise ValueError(
        "base_url is required for HTTP transport mode. "
        "Set PREPROD_API_URL environment variable or pass base_url explicitly."
    )
```

**Acceptance**:
- `PreprodAPIClient()` with no env vars raises `ValueError`
- `PreprodAPIClient(transport="invoke")` with no env vars does NOT raise
- `PreprodAPIClient(base_url="https://example.com")` does NOT raise

- [ ] Done

---

## T4: Verify all changes

**Depends on**: T1, T2, T3

Run validation:
1. `python -c "from tests.e2e.helpers.api_client import PreprodAPIClient; PreprodAPIClient()"` -- should raise ValueError
2. `python -c "from tests.e2e.helpers.api_client import PreprodAPIClient; PreprodAPIClient(transport='invoke')"` -- should succeed
3. Verify test files parse correctly: `python -m py_compile tests/e2e/test_cognito_auth.py && python -m py_compile tests/e2e/test_waf_protection.py`
4. Check no ruff/lint violations in modified files

- [ ] Done
