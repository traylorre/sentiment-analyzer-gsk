# Research: OAuth State Validation

**Feature**: 1185-oauth-state-validation
**Date**: 2026-01-10

## Summary

OAuth state parameter implementation for CSRF protection and redirect/provider validation.

## Decisions

### D1: State Storage
- **Decision**: DynamoDB Users table with PK=`OAUTH_STATE#{state_id}`
- **Rationale**: Reuse existing table and TTL configuration
- **Alternatives**: Redis (rejected - adds infrastructure), separate table (rejected - more Terraform)

### D2: State Generation
- **Decision**: `secrets.token_urlsafe(32)` producing 43-character URL-safe string
- **Rationale**: 256 bits entropy, URL-safe encoding
- **Alternatives**: UUID4 (rejected - only 128 bits)

### D3: Expiry Duration
- **Decision**: 5 minutes (300 seconds)
- **Rationale**: Sufficient for OAuth flow, limits attack window
- **Alternatives**: 10 minutes (rejected - too long), 2 minutes (rejected - too short for slow connections)

### D4: One-Time Use Enforcement
- **Decision**: Mark state as `used=True` after successful validation via conditional update
- **Rationale**: Prevents replay attacks
- **Pattern**: `ConditionExpression="used = :false"`

## Security Considerations

1. **Generic Error Messages**: All validation failures return same "Invalid OAuth state" message
2. **Timing Safety**: Use constant-time comparison for state_id if needed (secrets.compare_digest)
3. **No Logging of State Values**: Don't log state_id in plaintext (only hash if needed)

## Existing Code Analysis

Current state of OAuth in codebase:
- `get_authorize_url()` in cognito.py accepts optional state but never receives it
- `handle_oauth_callback()` doesn't validate state
- OAuth callback is exempt from CSRF double-submit validation
- Tests expect state validation but it's not implemented
