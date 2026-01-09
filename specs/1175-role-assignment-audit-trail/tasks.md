# Tasks: Feature 1175

## Implementation Tasks

- [ ] 1. Create audit.py module
  - Add create_role_audit_entry() function
  - Support oauth, stripe, admin sources
  - Return dict with role_assigned_at and role_assigned_by

- [ ] 2. Create unit tests
  - Test oauth source format
  - Test stripe source format
  - Test admin source format
  - Test timestamp format

- [ ] 3. (Optional) Refactor _advance_role()
  - Import audit helper
  - Use helper instead of inline logic

- [ ] 4. Validate
  - Run existing tests
  - Run new tests
  - Lint check

## Completion Criteria

- All tests pass
- Ruff passes
- PR created with auto-merge
