# Destroyed Files Analysis - 2025-12-11

## Incident Summary

On 2025-12-11, Claude ran `git stash && git stash drop` in the target repository (sentiment-analyzer-gsk), permanently destroying uncommitted work. This document catalogs what was lost.

## Files Destroyed (from user's `ll` before destruction)

### Deleted Files (completely lost)

| File                                                                   | Purpose                   | Recovery Possible                        |
| ---------------------------------------------------------------------- | ------------------------- | ---------------------------------------- |
| `.claude/commands/sri-validate.md`                                     | SRI validation command    | Yes - copy from template                 |
| `src/validators/__init__.py`                                           | Validator package init    | No - need to recreate                    |
| `src/validators/iam_coverage.py`                                       | IAM coverage checker      | No - was target-specific                 |
| `src/validators/resource_naming.py`                                    | Resource naming validator | Partial - template has different version |
| `src/validators/sri.py`                                                | SRI validator             | Partial - template has different version |
| `tests/fixtures/terraform/invalid_naming.tf`                           | Test fixture              | No                                       |
| `tests/fixtures/terraform/legacy_naming.tf`                            | Test fixture              | No                                       |
| `tests/fixtures/terraform/valid_naming.tf`                             | Test fixture              | No                                       |
| `tests/unit/resource_naming_consistency/test_iam_pattern_coverage.py`  | Unit tests                | No                                       |
| `tests/unit/resource_naming_consistency/test_resource_name_pattern.py` | Unit tests                | No                                       |
| `tests/unit/test_sri_validator.py`                                     | SRI validator tests       | Yes - copy from template                 |
| `tests/unit/validators/__init__.py`                                    | Test package init         | No                                       |
| `tests/unit/validators/test_iam_coverage.py`                           | IAM coverage tests        | No                                       |
| `tests/unit/validators/test_resource_naming.py`                        | Resource naming tests     | Yes - copy from template                 |

### Modified Files (changes lost)

| File                                                      | What Was Lost                       |
| --------------------------------------------------------- | ----------------------------------- |
| `.specify/methodologies/index.yaml`                       | Cleanup of sri_validation entry     |
| `infrastructure/terraform/ci-user-policy.tf`              | IAM policy changes (likely ECR fix) |
| `infrastructure/terraform/modules/cloudfront/main.tf`     | CloudFront changes                  |
| `tests/e2e/test_alerts.py`                                | Unknown modifications               |
| `tests/e2e/test_anonymous_restrictions.py`                | Unknown modifications               |
| `tests/e2e/test_auth_anonymous.py`                        | Unknown modifications               |
| `tests/e2e/test_auth_magic_link.py`                       | Unknown modifications               |
| `tests/e2e/test_auth_oauth.py`                            | Unknown modifications               |
| `tests/e2e/test_circuit_breaker.py`                       | Unknown modifications               |
| `tests/e2e/test_cleanup.py`                               | Unknown modifications               |
| `tests/e2e/test_config_crud.py`                           | Unknown modifications               |
| `tests/e2e/test_dashboard_buffered.py`                    | Unknown modifications               |
| `tests/e2e/test_financial_pipeline.py`                    | Unknown modifications               |
| `tests/e2e/test_market_status.py`                         | Unknown modifications               |
| `tests/e2e/test_notification_preferences.py`              | Unknown modifications               |
| `tests/e2e/test_notifications.py`                         | Unknown modifications               |
| `tests/e2e/test_quota.py`                                 | Unknown modifications               |
| `tests/e2e/test_rate_limiting.py`                         | Unknown modifications               |
| `tests/e2e/test_sentiment.py`                             | Unknown modifications               |
| `tests/e2e/test_sse.py`                                   | Unknown modifications               |
| `tests/e2e/test_ticker_validation.py`                     | Unknown modifications               |
| `tests/integration/ohlc/test_happy_path.py`               | Unknown modifications               |
| `tests/integration/sentiment_history/test_boundary.py`    | Unknown modifications               |
| `tests/integration/sentiment_history/test_happy_path.py`  | Unknown modifications               |
| `tests/integration/test_canary_preprod.py`                | Unknown modifications               |
| `tests/integration/test_e2e_lambda_invocation_preprod.py` | Unknown modifications               |
| `tests/integration/test_observability_preprod.py`         | Unknown modifications               |
| `tests/unit/interview/test_interview_html.py`             | Unknown modifications               |
| `tests/unit/test_dashboard_handler.py`                    | Unknown modifications               |

## Critical Lost Work

1. **IAM Policy Changes** - `ci-user-policy.tf` modifications were likely the ECR permission fixes needed for the failing pipeline
2. **CloudFront Changes** - `cloudfront/main.tf` modifications were likely related to the same IAM alignment work
3. **All E2E/Integration Test Modifications** - Pattern suggests these were bulk updates, possibly for test compatibility

## Recovery Attempts

- Checked `git reflog --all` - no stash references found
- Checked `git fsck --lost-found` - found 11 dangling commits, all from old rebases (pre-2025-12-11)
- Stash drop is permanent - uncommitted changes never become git objects that can be recovered

## Lessons Learned

**Constitution Amendment 1.9** has been added to prohibit:

- `git stash drop`
- `git stash && git stash drop`
- `git stash clear`
- `git checkout -- <file>` without user confirmation
- `git reset --hard` without user confirmation
- `git clean -fd` without user confirmation

## Recommended Next Steps

1. Create spec for "Option A: Commit via Template" workflow to prevent future methodology leakage
2. Remove all methodology artifacts from target repo (they should live only in template)
3. Re-implement the lost IAM/CloudFront changes following Amendment 1.6 (No Quick Fixes)
4. Consider whether lost E2E test modifications are worth reconstructing
