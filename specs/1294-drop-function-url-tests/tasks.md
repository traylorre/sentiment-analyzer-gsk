# Feature 1294: Tasks

## T-001: Delete test_e2e_lambda_invocation_preprod.py
`git rm tests/integration/test_e2e_lambda_invocation_preprod.py`

## T-002: Add AWS_ENV to deploy workflow
File: `.github/workflows/deploy.yml`. Add `AWS_ENV: preprod` to test job env vars.

## T-003: Verify no import references
`grep -r "test_e2e_lambda_invocation" tests/`

## Adversarial Review #3
**Highest risk**: Deleting 29 tests. Mitigated by coverage matrix in spec + enabling test_function_url_restricted.py via AWS_ENV.
**READY FOR IMPLEMENTATION.**
