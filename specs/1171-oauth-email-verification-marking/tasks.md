# Tasks: Feature 1171

## Implementation Tasks

- [ ] 1. Add `_mark_email_verified()` function in `auth.py`
  - Location: After `_advance_role()` (~line 1829)
  - Follow same pattern as `_advance_role()`
  - Include docstring with Feature 1171 reference

- [ ] 2. Implement function logic
  - Early return if `email_verified=False`
  - Early return if already verified
  - DynamoDB update expression
  - Try/except with warning log

- [ ] 3. Integrate in existing user OAuth path
  - Call after `_link_provider()` (~line 1604)
  - Call before `_advance_role()`
  - Pass email_verified from claims

- [ ] 4. Integrate in new user OAuth path
  - Call after `_link_provider()` (~line 1629)
  - Call before `_advance_role()`
  - Pass email_verified from claims

- [ ] 5. Create unit test file
  - File: `tests/unit/dashboard/test_mark_email_verified.py`
  - Follow `test_role_advancement.py` structure

- [ ] 6. Implement unit tests
  - Test happy path (provider verified)
  - Test skip when not verified
  - Test skip when already verified
  - Test audit fields set
  - Test primary_email set
  - Test silent failure
  - Test integration with callback

- [ ] 7. Validate
  - Run existing tests
  - Run new tests
  - Lint check
  - Type check

## Completion Criteria

- All tests pass
- Ruff passes
- Pre-commit hooks pass
- Feature committed and PR created
