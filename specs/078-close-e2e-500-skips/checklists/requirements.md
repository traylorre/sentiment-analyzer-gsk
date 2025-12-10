# Requirements Checklist: Feature 078 - Close Config Creation 500 E2E Test Skips

## Functional Requirements

| ID     | Requirement                                                                              | Status  | Notes |
| ------ | ---------------------------------------------------------------------------------------- | ------- | ----- |
| FR-001 | E2E tests MUST NOT skip with message "Config creation endpoint returning 500 - API issue" | PENDING |       |
| FR-002 | Tests MUST preserve skip conditions unrelated to 500 error                               | PENDING |       |
| FR-003 | Skip pattern `pytest.skip("Config creation endpoint returning 500")` MUST be removed     | PENDING |       |
| FR-004 | All modified tests MUST pass against preprod after skip removal                          | PENDING |       |
| FR-005 | RESULT2-tech-debt.md MUST be updated with closure summary                                | PENDING |       |
| FR-006 | No test coverage regression - tests that were executing MUST continue to execute         | PENDING |       |

## Success Criteria

| ID     | Criterion                                                                   | Status  | Notes |
| ------ | --------------------------------------------------------------------------- | ------- | ----- |
| SC-001 | Zero E2E tests contain skip message "Config creation endpoint returning 500" | PENDING |       |
| SC-002 | 100% of unskipped tests pass against preprod with Feature 077 deployed      | PENDING |       |
| SC-003 | RESULT2-tech-debt.md updated with closure date and PR reference             | PENDING |       |
| SC-004 | No increase in total test skip count (excluding intentional removals)       | PENDING |       |

## Test Files to Modify

| File                           | Expected Skips | Status  | Notes |
| ------------------------------ | -------------- | ------- | ----- |
| test_config_crud.py            | ~8             | PENDING |       |
| test_alerts.py                 | ~2             | PENDING |       |
| test_anonymous_restrictions.py | ~5             | PENDING |       |
| test_auth_anonymous.py         | ~2             | PENDING |       |
| test_failure_injection.py      | ~1             | PENDING |       |
| test_sentiment.py              | ~1 (if any)    | PENDING |       |

## Edge Cases

| Case                                               | Expected Behavior                         | Status  |
| -------------------------------------------------- | ----------------------------------------- | ------- |
| Test with BOTH 500 skip and "not implemented" skip | Remove only 500-related condition         | PENDING |
| Config-dependent test (alerts, failure injection)  | Should proceed to test actual functionality | PENDING |
| Feature 077 not deployed to preprod                | Tests will fail - feature is blocked      | PENDING |

## Dependencies

| Dependency                              | Status   | Notes                  |
| --------------------------------------- | -------- | ---------------------- |
| Feature 077 deployed to preprod         | REQUIRED | PR #332 merged to main |
| Feature 077 deployed to preprod runtime | VERIFY   | Check preprod endpoint |
