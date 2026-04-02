# Feature 1310: Harden INTERNAL_API_KEY Against Empty-String Auth Bypass

## Problem Statement

`INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")` at `src/lambdas/notification/alert_evaluator.py:38` uses a silent empty-string fallback. While the current `verify_internal_auth()` logic (lines 288-301) is **not actively exploitable** -- the `not ""` truthiness check routes to the ENVIRONMENT gate, which correctly denies access in preprod/prod -- the pattern is fragile and violates the fail-fast principle established by Feature 1304.

### Current Behavior Analysis

```python
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")  # line 38

def verify_internal_auth(auth_header: str | None) -> bool:  # line 288
    if not INTERNAL_API_KEY:              # "" is falsy -> True
        return os.environ["ENVIRONMENT"] in ("dev", "test")
    return auth_header == INTERNAL_API_KEY
```

| Scenario | INTERNAL_API_KEY | ENVIRONMENT | Result | Safe? |
|----------|-----------------|-------------|--------|-------|
| Dev, no key configured | `""` | `"dev"` | Allows (bypass) | Yes -- by design |
| Test, no key configured | `""` | `"test"` | Allows (bypass) | Yes -- by design |
| Preprod, no key configured | `""` | `"preprod"` | Denies | Yes -- correct |
| Prod, no key configured | `""` | `"prod"` | Denies | Yes -- correct |
| Prod, key configured | `"abc123"` | `"prod"` | Checks header | Yes -- correct |
| Prod, key set to `""` explicitly | `""` | `"prod"` | Denies | Yes -- but misleading |

### Why This Is Still a Problem

1. **Terraform never sets INTERNAL_API_KEY**: The notification Lambda's environment block (main.tf:564-577) does not include INTERNAL_API_KEY. The variable is dead infrastructure -- it was designed for a feature that never materialized.

2. **Fragile implicit contract**: The security of preprod/prod relies on Python's truthiness of `""` being falsy. A future refactor (e.g., checking `INTERNAL_API_KEY is None` or `len(INTERNAL_API_KEY) == 0`) could break this invariant silently.

3. **Pattern inconsistency**: Feature 1304 (PR #857) converted all ENVIRONMENT fallbacks to fail-fast `os.environ["ENVIRONMENT"]`. INTERNAL_API_KEY is the last remaining silent-fallback env var in alert_evaluator.py.

4. **Security audit noise**: Any automated scanner or manual reviewer seeing `os.environ.get(..., "")` for an authentication credential will flag it as a finding. Eliminating it reduces audit friction.

5. **Dead code path**: The `return auth_header == INTERNAL_API_KEY` branch (line 301) can never execute because the key is never configured. Dead auth code is a liability.

### Relationship to Prior Work

- **Feature 1304** (PR #857): Fixed `os.environ.get("ENVIRONMENT", "dev")` at line 299 to `os.environ["ENVIRONMENT"]`. Did NOT address line 38.
- **Feature 1048**: Explicitly listed "Removing deprecated INTERNAL_API_KEY references" as out of scope.
- **Feature 1310** (this): Closes the remaining gap from both.

## Requirements

### FR-001: Remove INTERNAL_API_KEY Module-Level Variable

Remove line 38 (`INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")`) entirely. This variable is never set by Terraform and serves no purpose.

### FR-002: Simplify verify_internal_auth to Environment Gate Only

Replace the current two-branch logic with a single ENVIRONMENT check:

```python
def verify_internal_auth(auth_header: str | None) -> bool:
    """Verify internal API authentication.

    Internal endpoints are only accessible in dev/test environments.
    Production internal calls use IAM-authenticated Lambda invocations,
    not HTTP API keys.

    Args:
        auth_header: X-Internal-Auth header value (unused, kept for interface stability)

    Returns:
        True if environment allows internal access, False otherwise
    """
    return os.environ["ENVIRONMENT"] in ("dev", "test")
```

**Rationale**: Since INTERNAL_API_KEY is never provisioned in any environment, the `auth_header == INTERNAL_API_KEY` path is dead code. Removing it makes the security model explicit: internal endpoints are dev/test only. Production inter-Lambda communication uses IAM-authenticated direct invocations, not HTTP API keys.

### FR-003: Update Tests to Match New Logic

Update `TestVerifyInternalAuth` to reflect the simplified function:
- Remove tests that patch `INTERNAL_API_KEY` (no longer exists)
- Keep/update environment-gated tests
- Add test for auth_header being ignored (interface stability)

### NFR-001: No Terraform Changes Required

Since INTERNAL_API_KEY was never in the Terraform config, no infrastructure changes are needed.

### NFR-002: Interface Stability

The function signature `verify_internal_auth(auth_header: str | None) -> bool` must not change. Callers pass the header value; the function now simply ignores it. This prevents breaking any call sites.

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Dev environment, no auth header | Returns True (dev bypass) |
| Dev environment, any auth header value | Returns True (dev bypass, header ignored) |
| Test environment, no auth header | Returns True (test bypass) |
| Preprod environment, any auth header | Returns False (denied) |
| Prod environment, any auth header | Returns False (denied) |
| ENVIRONMENT var missing | Raises KeyError (fail-fast, per 1304) |

## Acceptance Criteria

- [ ] AC1: `INTERNAL_API_KEY` module-level variable removed from alert_evaluator.py
- [ ] AC2: `verify_internal_auth()` returns True only for dev/test environments
- [ ] AC3: `verify_internal_auth()` ignores `auth_header` parameter
- [ ] AC4: Function signature unchanged (`auth_header: str | None -> bool`)
- [ ] AC5: All existing callers continue to work without modification
- [ ] AC6: Tests updated -- no references to INTERNAL_API_KEY in test file
- [ ] AC7: No Terraform changes required or made

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Caller relies on auth_header check | Low | Very Low | Interface unchanged; no caller ever passes a real key since Terraform never sets one |
| Future need for API key auth | Low | Low | Can be re-added with proper Terraform provisioning; pattern documented in this spec |
| Breaking test isolation | Low | Low | Tests already mock ENVIRONMENT; removing INTERNAL_API_KEY mock simplifies them |

## Files to Modify

| File | Change |
|------|--------|
| `src/lambdas/notification/alert_evaluator.py` | Remove line 38, simplify lines 288-301 |
| `tests/unit/notification/test_alert_evaluator.py` | Update TestVerifyInternalAuth class |

## Out of Scope

- Other `os.environ.get(..., "")` patterns in other files (separate feature per file)
- Adding API key auth infrastructure to Terraform (not needed; inter-Lambda uses IAM)
- Modifying callers of `verify_internal_auth()` (interface stable)

---

## Adversarial Review #1

### AR1-FINDING-01: verify_internal_auth Is Entirely Dead Code (SEVERITY: UPGRADE)

**Attack**: The spec claims we need to keep the function signature for "interface stability" (NFR-002, AC4, AC5). But `verify_internal_auth()` is never called anywhere in production code. Grep confirms:
- It is defined at `alert_evaluator.py:288` but never called within the file
- No other file in `src/` imports `alert_evaluator` or `verify_internal_auth`
- Only `tests/unit/notification/test_alert_evaluator.py` imports it (line 26)

**Impact**: The entire function is dead code, not just the INTERNAL_API_KEY branch. The module docstring at line 14 says "Internal endpoints require X-Internal-Auth header" but there is no code path that enforces this.

**Recommendation**: The spec should be updated to consider whether `verify_internal_auth()` itself should be removed entirely, not just simplified. However, removing it is a larger scope change (changes the module's public API surface). For this feature, simplifying it is still correct -- it eliminates the dangerous pattern and any future caller would get the safe version.

**Decision**: ACCEPT spec as-is. Simplifying is safer than removing. A future feature can remove the dead function if desired. Update the spec to document this finding.

### AR1-FINDING-02: Module Docstring Is Inaccurate

**Attack**: Line 14 says "Internal endpoints require X-Internal-Auth header" but after this change, internal endpoints will be gated by ENVIRONMENT only, ignoring the header entirely.

**Recommendation**: Update the module docstring as part of this feature. Add to plan.

**Decision**: ACCEPT. Add docstring update to requirements.

### AR1-FINDING-03: Test Import Still References INTERNAL_API_KEY

**Attack**: The test file at line 9-26 imports symbols from alert_evaluator. After removing INTERNAL_API_KEY, the import line itself won't break (it's not imported), but the @patch decorators on lines 411, 416, 421, 427 will fail because the patch target no longer exists.

**Recommendation**: Already covered by FR-003, but explicitly call out that patch targets must be removed, not just test methods.

**Decision**: ACCEPT. Already in scope.

### AR1-FINDING-04: Spec Correctly Identifies No Terraform Changes Needed

**Validation**: Confirmed -- grep of `infrastructure/terraform/` for `INTERNAL_API_KEY` or `internal_api_key` returns zero results. The variable was never provisioned. NFR-001 is correct.

### AR1-FINDING-05: auth_header Parameter Becomes Misleading

**Attack**: After FR-002, the function accepts `auth_header` but ignores it. This is a code smell that could confuse future developers.

**Recommendation**: Acceptable for interface stability. The docstring should clearly state the parameter is unused. Future cleanup can remove the parameter if all callers are audited.

**Decision**: ACCEPT. Docstring already specified in FR-002 says "(unused, kept for interface stability)".

### Summary

| Finding | Severity | Action |
|---------|----------|--------|
| AR1-01: Function is entirely dead code | INFO | Document in spec, keep simplification approach |
| AR1-02: Module docstring inaccurate | LOW | Add docstring update to plan |
| AR1-03: Test @patch targets will break | COVERED | Already in FR-003 scope |
| AR1-04: No Terraform changes confirmed | VALIDATED | NFR-001 correct |
| AR1-05: Unused parameter smell | ACCEPTED | Documented in docstring |

**Net assessment**: Spec is sound. One addition needed: update module docstring (line 14). No structural changes to requirements.

---

## Clarification Questions (Stage 4)

### Q1: Should we remove verify_internal_auth entirely since it's dead code?

**Answer**: No. The function exists in the module's public API surface. Removing it would be a larger scope change (requires auditing all test imports, checking if any downstream repos import it, etc.). Simplifying it is safer and eliminates the dangerous pattern. A separate feature can remove dead code if needed.

### Q2: Is there any environment where INTERNAL_API_KEY could be set via a mechanism outside Terraform (e.g., SSM, Secrets Manager, container env)?

**Answer**: No. Confirmed by grepping the entire `infrastructure/` directory. No SSM parameters, no Secrets Manager references, no env var injection for INTERNAL_API_KEY. The Lambda's environment is fully defined in `main.tf:564-577` and the post-creation wiring resources. INTERNAL_API_KEY is absent from all of them.

### Q3: Could there be a runtime mechanism that sets INTERNAL_API_KEY after cold start?

**Answer**: No. `INTERNAL_API_KEY` is read at module load time (line 38, module-level). Lambda cold start runs this once. There is no code that modifies `os.environ["INTERNAL_API_KEY"]` at runtime. Even if there were, the module-level variable captures the value once and wouldn't see runtime changes.

### Q4: After this change, what actually gates access to internal endpoints in preprod/prod?

**Answer**: `verify_internal_auth()` will return False for preprod/prod, blocking all internal endpoint calls. However, as noted in AR1-FINDING-01, this function is never actually called in production code paths. The real access control for inter-Lambda communication is AWS IAM -- the analysis Lambda invokes the notification Lambda directly (not via HTTP), and IAM policies control which Lambdas can invoke which. The X-Internal-Auth header mechanism was designed but never wired into the request routing.

### Q5: Should we also update the archive spec references that mention INTERNAL_API_KEY?

**Answer**: No. Archive specs (e.g., `specs/archive/006-user-config-dashboard/contracts/notification-api.md`) are historical records. They document what was planned, not current behavior. Updating them would misrepresent history.
