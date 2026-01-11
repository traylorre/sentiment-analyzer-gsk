# Feature 1189: JWT Audience Environment Suffix

## Problem Statement

The JWT `aud` (audience) claim currently uses the same value `"sentiment-analyzer-api"` across all environments (dev, preprod, prod). This violates security best practice A16 from spec-v2.md which requires environment-specific audience claims to prevent cross-environment token replay attacks.

**Risk**: A token issued in dev could theoretically be replayed in preprod or prod if the JWT secrets were compromised, since the audience claim doesn't distinguish between environments.

## Solution

Set environment-specific `jwt_audience` values in each tfvars file:

| Environment | jwt_audience Value |
|-------------|-------------------|
| dev | `sentiment-api-dev` |
| preprod | `sentiment-api-preprod` |
| prod | `sentiment-api-prod` |

## Scope

### In Scope
- Update `dev.tfvars` with `jwt_audience = "sentiment-api-dev"`
- Update `preprod.tfvars` with `jwt_audience = "sentiment-api-preprod"`
- Update `prod.tfvars` with `jwt_audience = "sentiment-api-prod"`

### Out of Scope
- Code changes (JWT validation already supports configurable audience via Feature 1147)
- Token generation changes (Cognito configuration handles token issuance)
- Migration strategy (existing tokens will fail validation and users re-authenticate)

## Technical Details

### Current State

**variables.tf (lines 202-208)**:
```hcl
variable "jwt_audience" {
  description = "Expected audience claim for JWT validation (Feature 1147)"
  type        = string
  default     = "sentiment-analyzer-api"
}
```

**JWT Validation (auth_middleware.py line 160)**:
```python
payload = jwt.decode(
    token,
    config.secret,
    algorithms=[config.algorithm],
    audience=config.audience,  # Validates aud claim
    ...
)
```

### Changes Required

1. `infrastructure/terraform/dev.tfvars` - Add `jwt_audience = "sentiment-api-dev"`
2. `infrastructure/terraform/preprod.tfvars` - Add `jwt_audience = "sentiment-api-preprod"`
3. `infrastructure/terraform/prod.tfvars` - Add `jwt_audience = "sentiment-api-prod"`

### Migration Impact

**Breaking Change**: Existing tokens without the environment-specific audience claim will be rejected. Users must re-authenticate to obtain new tokens with the correct audience claim.

This is acceptable because:
1. Tokens have 15-minute lifetime (access) and 7-day lifetime (refresh)
2. Re-authentication is the correct security behavior when audience changes
3. Frontend already handles token refresh failures gracefully

## Security Considerations

- **CVSS 7.8 (Feature 1147)**: This feature strengthens the existing audience validation by making it environment-specific
- **Defense in depth**: Combined with environment-specific JWT secrets (Feature 1054), this prevents cross-environment attacks
- **Audit trail**: JWT middleware logs audience mismatch warnings (auth_middleware.py lines 199-201)

## Testing Strategy

1. **Unit tests**: Not required - no code changes
2. **Integration tests**: Verify JWT validation rejects tokens with wrong environment audience
3. **E2E tests**: Verify authentication flow works end-to-end after deployment

## References

- spec-v2.md A16: Environment-specific JWT aud claim
- Feature 1147: JWT audience and nbf validation (CVSS 7.8)
- Feature 1054: JWT Secret Terraform management
