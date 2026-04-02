# AR#2: Plan Review -- Feature 1309

## Review Findings

### FINDING-1: Line numbers will shift after first edit (ATTENTION)
**Observation**: The plan references line numbers (e.g., "Line 33-34", "Line 78-79"). After the first fixture is modified (+2 lines), subsequent line numbers shift. This is a documentation concern, not an implementation risk -- the actual edits use string matching, not line offsets.
**Risk**: None for implementation. The `old_string`/`new_string` edit pattern matches content, not line numbers.
**Severity**: None
**Disposition**: ACCEPTED -- line numbers are for human reference only.

### FINDING-2: test_cors_404_e2e.py correctly excluded (CONFIRMED)
**Observation**: The plan explicitly states "No changes needed" for test_cors_404_e2e.py with clear reasoning: `skip_if_no_url` autouse fixture already guards the API URL, and the CORS origin fallback is intentional.
**Risk**: None.
**Severity**: None
**Disposition**: CONFIRMED

### FINDING-3: ValueError placement in api_client.py is correct (CONFIRMED)
**Observation**: The plan places the ValueError check after `self.base_url` assignment (line 71) and after `self._transport_mode` assignment (line 66), but before SSE URL fallback logic (line 77). This ordering is critical: the transport mode check must happen after the mode is set, and the base_url must be validated before it's used as an SSE fallback.
**Risk**: None -- ordering is correct.
**Severity**: None
**Disposition**: CONFIRMED

### FINDING-4: 8 identical fixture edits -- mechanical correctness (INFORMATIONAL)
**Observation**: All 8 fixture edits follow the same pattern:
```python
# Before
return os.environ.get("PREPROD_API_URL", "").rstrip("/")

# After
url = os.environ.get("PREPROD_API_URL", "").rstrip("/")
if not url:
    pytest.skip("PREPROD_API_URL not set")
return url
```
The `old_string` is identical across all 8 locations within each file (4 per file). Since `Edit` requires unique matches, each edit must include surrounding context (the `@pytest.fixture` decorator and `def api_url(self)` line) to disambiguate.
**Risk**: Medium -- if the Edit tool matches the wrong fixture, the change applies to the wrong location.
**Recommendation**: Include the class name or preceding decorator in the old_string for uniqueness.
**Severity**: Medium
**Disposition**: REQUIRES ACTION -- implementation must use sufficient context in each edit to ensure unique matches.

### FINDING-5: No test for the new api_client.py ValueError (INFORMATIONAL)
**Observation**: The plan does not include a unit test for the new ValueError in `PreprodAPIClient.__init__`. This is a test helper, not production code, so formal test coverage is less critical. However, the verification section in spec.md describes manual validation steps.
**Risk**: Low -- if the ValueError is accidentally removed, there's no automated guard. But this is a test helper that protects other tests, so the protection is self-evident during test runs.
**Severity**: Low
**Disposition**: ACCEPTED -- the value is in preventing confusing failures, not in test coverage of the guard itself.

## Summary

| Finding | Severity | Disposition |
|---------|----------|-------------|
| AR2-FINDING-1 | None | ACCEPTED |
| AR2-FINDING-2 | None | CONFIRMED |
| AR2-FINDING-3 | None | CONFIRMED |
| AR2-FINDING-4 | Medium | REQUIRES ACTION (use unique context in edits) |
| AR2-FINDING-5 | Low | ACCEPTED |

**Verdict**: PASS with one implementation note: each Edit must include enough surrounding context for unique string matching (AR2-FINDING-4).
