# Feature 1166: Tasks

## Implementation Tasks

- [ ] T001: Make signature field optional in MagicLinkToken model
- [ ] T002: Delete _get_magic_link_secret() function from auth.py
- [ ] T003: Delete _generate_magic_link_signature() function from auth.py
- [ ] T004: Remove signature generation from request_magic_link()
- [ ] T005: Remove signature from MagicLinkToken instantiation
- [ ] T006: Remove MAGIC_LINK_SECRET from test fixtures
- [ ] T007: Update/remove signature-related unit tests
- [ ] T008: Run unit tests and fix any failures
- [ ] T009: Create PR and verify preprod tests pass

## Verification

- [ ] Unit tests pass locally
- [ ] No references to MAGIC_LINK_SECRET in auth.py
- [ ] Magic link E2E tests pass in preprod
