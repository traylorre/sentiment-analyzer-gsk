# Research: Validation Finding Remediation

**Feature**: 049-validate-remediation
**Date**: 2025-12-05

## Research Topics

### 1. pytest conftest.py Import Pattern

**Question**: Why does `from conftest import ...` fail in property tests?

**Finding**: pytest's conftest.py is a special file that is automatically discovered and loaded by pytest - it is NOT a regular Python module that can be imported. The conftest.py file provides fixtures, hooks, and plugins to tests without explicit imports.

**Decision**: Change test files to use direct fixture injection instead of explicit imports

**Rationale**:

- pytest automatically makes conftest.py fixtures available to all tests in the same directory
- Direct module imports (`from conftest import`) bypass pytest's discovery mechanism
- Strategies defined with `@st.composite` can be used as fixtures via pytest-hypothesis integration

**Alternative Considered**:

- Move strategies to a regular Python module (e.g., `tests/property/strategies.py`) and import from there
- Rejected because it breaks the pytest conftest convention and requires more changes

**Canonical Source**: https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files

### 2. SQS-009 Allowlist Environment Detection

**Question**: Why isn't SQS-009 for ci-user-policy.tf being suppressed?

**Finding**: The `derive_environment()` function in `iam_allowlist.py` checks file paths for patterns like `dev-deployer`, `preprod-deployer`, etc. The file `infrastructure/terraform/ci-user-policy.tf` doesn't match any of these patterns, so it returns `None` and the context condition fails.

**Decision**: Extend the allowlist entry to support CI policies that deploy to multiple environments by adding a new context pattern

**Rationale**:

- CI deployment policies legitimately span dev/preprod environments
- The current pattern `ci-user-policy.tf` indicates a CI/CD context, not a specific environment
- The sqs:DeleteQueue permission is scoped to `*-sentiment-*` pattern, covering dev and preprod

**Alternatives Considered**:

1. Modify `derive_environment()` to parse Terraform content for resource patterns
   - Rejected: Complex and fragile - resource patterns vary widely
2. Remove environment context from allowlist entry
   - Rejected: Loses environment-based safety checks for other files

**Decision Implementation**: Add a new context condition `ci_policy: true` that matches CI policy file patterns, which implicitly covers dev/preprod

**Canonical Source**: https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html

### 3. IAM-006 Deny Statement False Positive

**Question**: Why does IAM validator flag sqs:\* in Deny statements?

**Finding**: The `SERVICE_WILDCARD_PATTERN` regex and check in `iam.py` line 154-172 only looks for the Action pattern but doesn't check the statement's Effect. Deny statements with wildcards are security-enhancing because they block all matching actions.

**Decision**: Add Effect detection before flagging service wildcards in IAM validator

**Rationale**:

- Deny statements with wildcards (`sqs:*`) are intentional security controls
- DenyInsecureTransport pattern uses `Effect: Deny` + `Action: sqs:*` to block ALL insecure SQS access
- Only Allow statements with wildcards indicate over-permissiveness

**Implementation Approach**:

- Parse JSON content to detect Effect field
- Only flag IAM-006 when Effect is "Allow" (or missing, which defaults to "Deny" but is invalid)
- For Terraform files, use regex to detect effect = "Allow" context

**Canonical Source**: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_effect.html

## Summary of Resolutions

| Issue                  | Root Cause             | Resolution                      |
| ---------------------- | ---------------------- | ------------------------------- |
| PROP-001               | Direct conftest import | Use pytest fixture injection    |
| SQS-009 not suppressed | No CI policy detection | Add ci_policy context condition |
| IAM-006 false positive | No Effect detection    | Skip Deny statements            |
