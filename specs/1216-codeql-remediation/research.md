# Research: CodeQL Security Vulnerability Remediation

**Feature**: 1216-codeql-remediation
**Date**: 2026-01-20

## Key Findings

### Decision 1: Log Sanitization Strategy

**Decision**: Use inline sanitization patterns that CodeQL recognizes as taint barriers, supplemented by the existing `sanitize_for_log()` utility.

**Rationale**: CodeQL's taint analysis tracks data flow through function calls but may not recognize custom sanitization functions as barriers unless they match specific patterns. Inline sanitization with explicit string replacement is universally recognized.

**Alternatives Considered**:
- CodeQL model file annotations (complex, requires maintaining separate config)
- Suppress all findings with inline comments (violates security best practice)
- Replace logging library (over-engineering for this use case)

### Decision 2: CodeQL-Recognized Sanitization Pattern

**Decision**: Use this inline pattern for user-derived values:

```python
# Pattern that CodeQL recognizes as sanitization barrier
safe_value = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")[:200]
logger.info("Message", extra={"field": safe_value})
```

**Rationale**: CodeQL specifically looks for string replacement of newline/carriage return characters as log injection mitigation. This is documented in CodeQL's security query documentation.

**Alternatives Considered**:
- `%r` formatting (does not fully sanitize control characters)
- JSON encoding (adds unnecessary overhead)
- Base64 encoding (loses readability in logs)

### Decision 3: Sensitive Data Handling

**Decision**: For password/credential logging at oauth_state.py:95, remove the sensitive value entirely rather than masking.

**Rationale**: Even masked passwords (`****`) can leak information about password length. Best practice is complete omission.

**Alternatives Considered**:
- Hash the value (computational overhead, no benefit)
- Fixed-length mask (still reveals password presence)
- Log only boolean has_credential flag (chosen - already implemented)

### Decision 4: Bad Tag Filter Remediation

**Decision**: Remove the unused HTML comment regex from regenerate-mermaid-url.py as it's not needed for mermaid syntax validation.

**Rationale**: The py/bad-tag-filter rule flags regex patterns that attempt to filter HTML but miss edge cases like `--!>`. Since this code validates mermaid syntax (not HTML), the check is unnecessary.

**Alternatives Considered**:
- Fix the regex to handle `--!>` (over-engineering - we're not filtering HTML)
- Add a CodeQL suppression comment (avoids the root cause)

## Findings Summary

### Existing Infrastructure

**Sanitization Utility**: `/src/lambdas/shared/logging_utils.py`
- `sanitize_for_log(value, max_length=200)` - Removes CRLF, control characters
- `get_safe_error_info(exception)` - Returns only exception type
- `redact_sensitive_fields(data)` - Redacts passwords, tokens, secrets

### CodeQL Alert Analysis

| Rule | Count | Files | Remediation Strategy |
|------|-------|-------|---------------------|
| py/log-injection | 26 | auth.py, ohlc.py, oauth_state.py | Add inline sanitization pattern |
| py/clear-text-logging-sensitive-data | 1 | oauth_state.py:95 | Remove sensitive value from log |
| py/bad-tag-filter | 1 | regenerate-mermaid-url.py:81 | Remove unnecessary regex |

### Files Requiring Changes

1. **src/lambdas/dashboard/auth.py** (21 locations)
   - Most use `sanitize_for_log()` but CodeQL doesn't recognize it as barrier
   - Add inline sanitization pattern before logging

2. **src/lambdas/dashboard/ohlc.py** (2 locations)
   - Lines 342, 478: cache_key contains user-derived ticker/resolution
   - Add sanitization to cache_key before logging

3. **src/lambdas/shared/auth/oauth_state.py** (4 locations)
   - Line 95: Clear-text sensitive data issue
   - Lines 193, 201, 220: Log injection from redirect_uri

4. **scripts/regenerate-mermaid-url.py** (1 location)
   - Line 81: Remove HTML comment regex check (not needed for mermaid)

## Implementation Approach

### Phase 1: Create Sanitization Wrapper
Add a CodeQL-recognized sanitization function that wraps the existing utility:

```python
def safe_log_value(value: str, max_length: int = 200) -> str:
    """Sanitize value for safe logging - CodeQL recognized pattern."""
    if value is None:
        return ""
    s = str(value)
    # Inline pattern CodeQL recognizes as log injection barrier
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return s[:max_length]
```

### Phase 2: Apply to Flagged Locations
Update each flagged location to use the sanitization pattern inline or via the wrapper.

### Phase 3: Remove Sensitive Data Logging
For oauth_state.py:95, ensure no credential values are logged.

### Phase 4: Remove Bad Tag Filter
Delete the unused HTML regex from regenerate-mermaid-url.py.

## References

- [CodeQL py/log-injection documentation](https://codeql.github.com/codeql-query-help/python/py-log-injection/)
- [CWE-117: Improper Output Neutralization for Logs](https://cwe.mitre.org/data/definitions/117.html)
- [OWASP Log Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
