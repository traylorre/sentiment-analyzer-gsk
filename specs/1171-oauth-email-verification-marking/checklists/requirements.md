# Requirements Checklist: Feature 1171

## Functional Requirements

- [ ] FR-1: OAuth login with `email_verified=true` sets `verification="verified"`
- [ ] FR-2: OAuth login with `email_verified=false` leaves `verification` unchanged
- [ ] FR-3: Already-verified users are not re-marked (idempotent)
- [ ] FR-4: `primary_email` set to OAuth email when marking verified
- [ ] FR-5: Audit fields (`verification_marked_at`, `verification_marked_by`) populated

## Non-Functional Requirements

- [ ] NFR-1: Silent failure pattern - OAuth flow succeeds even if marking fails
- [ ] NFR-2: Called BEFORE role advancement to maintain state machine invariant
- [ ] NFR-3: Unit test coverage 100% for new function
- [ ] NFR-4: No changes to existing behavior when `email_verified=false`

## Security Requirements

- [ ] SR-1: User ID prefix sanitized in logs
- [ ] SR-2: Email not logged in full
- [ ] SR-3: No exceptions leak to client

## Testing Evidence

- [ ] TE-1: Unit test `test_mark_verified_when_provider_verified` passes
- [ ] TE-2: Unit test `test_skip_when_provider_not_verified` passes
- [ ] TE-3: Unit test `test_skip_when_already_verified` passes
- [ ] TE-4: Unit test `test_sets_primary_email` passes
- [ ] TE-5: Unit test `test_sets_audit_fields` passes
- [ ] TE-6: Unit test `test_silent_failure_on_dynamodb_error` passes
- [ ] TE-7: All existing auth tests still pass
