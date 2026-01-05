# Research: JWT Audience and Not-Before Validation

**Feature**: 1147-jwt-aud-nbf-validation
**Date**: 2026-01-05
**Status**: Complete

## Research Questions

### Q1: How does PyJWT validate `aud` (audience) claims?

**Decision**: Use PyJWT's built-in `audience` parameter in `jwt.decode()`

**Rationale**: PyJWT natively supports audience validation via the `audience` parameter. When provided, PyJWT:
1. Requires the `aud` claim to be present (or raises `MissingRequiredClaimError`)
2. Validates that the token's `aud` matches the expected audience (or raises `InvalidAudienceError`)
3. Supports array audiences - if token has `aud: ["service-a", "service-b"]`, it accepts if expected audience is in the array

**Implementation**:
```python
payload = jwt.decode(
    token,
    secret,
    algorithms=["HS256"],
    audience="sentiment-analyzer-api",  # Add this parameter
    ...
)
```

**Alternatives Considered**:
- Manual validation after decode: Rejected - duplicates PyJWT's built-in logic, error-prone
- Custom validator decorator: Rejected - over-engineering for simple claim check

**Source**: [PyJWT Documentation - Usage Examples](https://pyjwt.readthedocs.io/en/stable/usage.html#audience-claim-aud)

---

### Q2: How does PyJWT validate `nbf` (not-before) claims?

**Decision**: Add `"nbf"` to the `require` options list; PyJWT validates automatically

**Rationale**: PyJWT validates `nbf` automatically when the claim is present. To make it required:
1. Add `"nbf"` to `options={"require": ["sub", "exp", "iat", "nbf"]}`
2. PyJWT checks if current time >= nbf (accounting for leeway)
3. Raises `ImmatureSignatureError` if token is not yet valid

**Implementation**:
```python
payload = jwt.decode(
    token,
    secret,
    algorithms=["HS256"],
    options={
        "require": ["sub", "exp", "iat", "nbf"],  # Add nbf
    },
    leeway=60,  # Already configured - applies to nbf too
)
```

**Alternatives Considered**:
- Manual timestamp comparison: Rejected - PyJWT handles edge cases and leeway
- Optional nbf with manual check: Rejected - spec requires nbf to be mandatory

**Source**: [PyJWT Documentation - Registered Claims](https://pyjwt.readthedocs.io/en/stable/usage.html#not-before-claim-nbf)

---

### Q3: What environment configuration pattern for audience?

**Decision**: Add `JWT_AUDIENCE` environment variable with environment-specific defaults

**Rationale**: 
1. Follow existing pattern (JWT_ISSUER, JWT_SECRET)
2. Environment-specific to prevent cross-environment replay
3. Support both single string and multiple audiences (comma-separated)

**Implementation**:
```python
@dataclass(frozen=True)
class JWTConfig:
    secret: str
    algorithm: str = "HS256"
    issuer: str | None = "sentiment-analyzer"
    audience: str | None = None  # NEW: Required for validation
    leeway_seconds: int = 60
```

**Environment values**:
- `dev`: `"sentiment-analyzer-api-dev"`
- `preprod`: `"sentiment-analyzer-api-preprod"`
- `prod`: `"sentiment-analyzer-api"`

**Alternatives Considered**:
- Hardcoded audience: Rejected - prevents environment isolation testing
- Audience from issuer: Rejected - conflates two distinct claims

---

### Q4: How to handle tokens without aud/nbf (migration)?

**Decision**: Reject tokens missing aud/nbf claims immediately (breaking change by design)

**Rationale**: Per spec edge cases:
- "System MUST reject the token" when aud claim is missing
- "System MUST reject the token (required claim)" when nbf claim is missing  
- "System MUST reject them (breaking change by design for security)"

This is a security feature - allowing legacy tokens defeats the purpose.

**Implementation**:
- Add `"aud"` requirement via `audience` parameter presence
- Add `"nbf"` to `require` options
- PyJWT raises `MissingRequiredClaimError` for missing claims

**Migration Strategy**:
1. Deploy with audience/nbf validation enabled
2. All new tokens from Cognito will include claims
3. Legacy tokens (if any) will fail - this is intentional
4. Users re-authenticate to get new tokens

**Alternatives Considered**:
- Grace period for legacy tokens: Rejected - spec explicitly requires breaking change
- Optional validation flag: Rejected - security bypass risk

---

### Q5: Error handling and logging pattern?

**Decision**: Add `InvalidAudienceError` and `ImmatureSignatureError` handlers with security logging

**Rationale**: 
1. Follow existing error handling pattern in validate_jwt()
2. Audience mismatch is a potential attack - log as WARNING (FR-005)
3. Immature signature is less concerning - log as DEBUG
4. Return 401 for both (FR-007: no information leakage)

**Implementation**:
```python
except jwt.InvalidAudienceError:
    logger.warning("JWT audience mismatch detected")  # Security event
    return None

except jwt.ImmatureSignatureError:
    logger.debug("JWT not yet valid (nbf)")
    return None
```

**Source**: Existing error handling pattern at lines 157-174 of auth_middleware.py

---

## Summary of Changes

| Component | Change |
|-----------|--------|
| `JWTConfig` dataclass | Add `audience: str \| None = None` field |
| `validate_jwt()` | Add `audience` parameter to `jwt.decode()` |
| `validate_jwt()` | Add `"nbf"` to `require` options |
| `validate_jwt()` | Add error handlers for `InvalidAudienceError`, `ImmatureSignatureError` |
| Environment | Add `JWT_AUDIENCE` env var with environment-specific values |
| Test fixtures | Update `create_test_jwt()` to include `aud` and `nbf` claims |

## Dependencies

- PyJWT (existing) - no version change needed
- No new dependencies required

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing tokens | Intentional per spec; users re-authenticate |
| Clock skew issues | 60-second leeway already configured |
| Cognito token compatibility | Verify Cognito includes aud/nbf claims (standard behavior) |
