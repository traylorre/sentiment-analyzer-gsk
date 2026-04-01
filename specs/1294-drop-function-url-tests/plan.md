# Feature 1294: Plan

## Implementation
1. Delete `tests/integration/test_e2e_lambda_invocation_preprod.py`
2. Add `AWS_ENV: preprod` to deploy workflow test job environment
3. Verify no imports reference the deleted file

## Clarifications
Q1: Does anything import from test_e2e_lambda_invocation_preprod.py?
A1: Grep shows no imports. It's a standalone test file. Self-answered.

## Adversarial Review #2
AR#1 finding resolved: FR-003 (add AWS_ENV) ensures test_function_url_restricted.py runs in CI.
No drift. Gate passes.
