# AR#1: Spec Review -- Feature 1309

## Review Findings

### FINDING-1: Duplicate api_url fixtures -- consolidation opportunity (INFORMATIONAL)
**Observation**: `test_cognito_auth.py` defines `api_url` in 4 separate classes. `test_waf_protection.py` defines it in 4 classes. Each needs the same guard added.
**Risk**: Copy-paste 8 times increases chance of inconsistency.
**Recommendation**: The spec correctly scopes this as "add guard to each fixture" rather than refactoring into a shared fixture. Refactoring class-scoped fixtures into module-level would change test isolation semantics and is out of scope. Accepted as-is.
**Severity**: Low
**Disposition**: ACCEPTED -- the spec explicitly lists "out of scope" items that prevent scope creep.

### FINDING-2: CORS origin fallback is intentional, not a bug (CONFIRMED)
**Observation**: `test_cors_404_e2e.py` line 22-24 hardcodes `PREPROD_CORS_ORIGIN` fallback to an Amplify URL. The spec correctly identifies this as intentional (must match Terraform config).
**Risk**: None -- the spec correctly excludes this from changes (FR-002).
**Severity**: None
**Disposition**: CONFIRMED -- correct analysis.

### FINDING-3: ValueError vs pytest.skip for api_client.py (ATTENTION)
**Observation**: FR-003 specifies `ValueError` for empty base_url in HTTP mode. Test files use `pytest.skip()`. The distinction is correct: `api_client.py` is a library, not a test -- it should raise a proper exception, not call pytest.skip.
**Risk**: A caller might catch ValueError generically. Consider a more specific exception.
**Recommendation**: `ValueError` is the standard Python exception for "argument has right type but wrong value." This is appropriate. A custom exception would be over-engineering for a test helper.
**Severity**: Low
**Disposition**: ACCEPTED -- ValueError is correct for a library-level validation.

### FINDING-4: SkipInfo condition vs fixture guard -- double skip? (ATTENTION)
**Observation**: Both `test_cognito_auth.py` and `test_waf_protection.py` already have module-level `SkipInfo(condition=os.getenv("AWS_ENV") != "preprod")`. If `AWS_ENV != "preprod"`, the class is skipped via `@pytest.mark.skipif` before the fixture ever runs. The fixture guard only fires when `AWS_ENV=preprod` but `PREPROD_API_URL` is unset.
**Risk**: The two guards cover different failure modes. The module-level skip handles "wrong environment." The fixture-level skip handles "right environment, missing URL." Both are needed.
**Severity**: None
**Disposition**: CONFIRMED -- complementary guards, not redundant.

### FINDING-5: api_client.py -- SSE URL fallback to base_url (INFORMATIONAL)
**Observation**: Line 77: `self.sse_url = raw_sse_url.rstrip("/") if raw_sse_url else self.base_url`. If base_url is empty AND sse_url is empty, sse_url becomes empty too. The FR-003 ValueError on empty base_url will catch this transitively.
**Risk**: None -- the base_url guard catches the root cause.
**Severity**: None
**Disposition**: CONFIRMED -- transitive protection via FR-003.

## Summary

| Finding | Severity | Disposition |
|---------|----------|-------------|
| AR1-FINDING-1 | Low | ACCEPTED |
| AR1-FINDING-2 | None | CONFIRMED |
| AR1-FINDING-3 | Low | ACCEPTED |
| AR1-FINDING-4 | None | CONFIRMED |
| AR1-FINDING-5 | None | CONFIRMED |

**Verdict**: PASS -- spec is well-scoped, correctly identifies the problem, and the fix pattern matches existing codebase conventions. No blocking findings.
