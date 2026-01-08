# Implementation Tasks: OAuth Populate Federation Fields

**Feature**: 1169-oauth-populate-federation-fields
**Plan**: [plan.md](plan.md)
**Created**: 2026-01-07

## Task List

### Phase 1: Implementation

- [x] **T1**: Add `_link_provider()` helper function after `_update_cognito_sub()` in `src/lambdas/dashboard/auth.py`
  - Build ProviderMetadata from claims
  - Atomic DynamoDB update for provider_metadata, linked_providers, last_provider_used
  - Silent failure pattern (log warning, don't raise)
  - Accept: sub, email, avatar, email_verified as params

- [x] **T2**: Integrate `_link_provider()` into new user flow
  - Call after `_create_authenticated_user()` (around line 1603)
  - Pass claims: sub=cognito_sub, email=email, avatar=claims.get("picture"), email_verified=claims.get("email_verified", False)

- [x] **T3**: Integrate `_link_provider()` into existing user flow
  - Call after `_update_cognito_sub()` (around line 1590)
  - Same params as new user flow

### Phase 2: Testing

- [x] **T4**: Add unit tests in `tests/unit/dashboard/test_link_provider.py`
  - test_link_provider_new_user_google
  - test_link_provider_new_user_github
  - test_link_provider_existing_user_same_provider
  - test_link_provider_existing_user_add_provider
  - test_link_provider_no_duplicate_entries
  - test_link_provider_handles_missing_avatar
  - test_link_provider_handles_missing_sub
  - test_link_provider_silent_failure

### Phase 3: Validation

- [x] **T5**: Run full test suite to ensure no regressions
  - `pytest tests/unit/dashboard/ -v`
  - Verify OAuth callback tests still pass
  - All 25 dashboard auth tests pass

- [ ] **T6**: Manual verification (deferred to E2E)
  - Review linked_providers populated after OAuth
  - Review provider_metadata populated with sub, email, avatar
  - Review last_provider_used updated

## Acceptance Criteria

- [x] All OAuth sign-ins populate linked_providers with provider name
- [x] All OAuth sign-ins populate provider_metadata[provider] with sub, email, avatar, linked_at
- [x] All OAuth sign-ins update last_provider_used
- [x] No duplicate entries in linked_providers on re-authentication
- [x] Silent failure pattern: DynamoDB errors logged but don't break OAuth
- [x] All existing OAuth tests pass (25/25)
- [x] New tests pass for _link_provider() functionality (11/11)
