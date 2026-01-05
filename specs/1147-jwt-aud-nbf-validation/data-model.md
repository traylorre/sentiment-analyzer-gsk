# Data Model: JWT Audience and Not-Before Validation

**Feature**: 1147-jwt-aud-nbf-validation
**Date**: 2026-01-05

## Entity Changes

### JWTConfig (Modified)

**Location**: `src/lambdas/shared/middleware/auth_middleware.py`

```python
@dataclass(frozen=True)
class JWTConfig:
    """JWT validation configuration."""
    
    secret: str                              # Existing: HMAC signing key
    algorithm: str = "HS256"                 # Existing: Signature algorithm
    issuer: str | None = "sentiment-analyzer" # Existing: Expected issuer
    audience: str | None = None              # NEW: Expected audience claim
    leeway_seconds: int = 60                 # Existing: Clock skew tolerance
    access_token_lifetime_seconds: int = 900 # Existing: Token TTL

    @classmethod
    def from_env(cls) -> "JWTConfig":
        """Load configuration from environment variables."""
        return cls(
            secret=os.environ["JWT_SECRET"],
            algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
            issuer=os.environ.get("JWT_ISSUER", "sentiment-analyzer"),
            audience=os.environ.get("JWT_AUDIENCE"),  # NEW
            leeway_seconds=int(os.environ.get("JWT_LEEWAY_SECONDS", "60")),
        )
```

**Field Details**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audience` | `str \| None` | Yes (runtime) | None | Expected audience claim value |

**Environment Variable**:

| Env Var | Example | Required |
|---------|---------|----------|
| `JWT_AUDIENCE` | `sentiment-analyzer-api` | Yes (prod) |

## Validation Rules

### Audience Claim (aud)

1. **Presence**: Token MUST contain `aud` claim
2. **Value Match**: Token `aud` MUST equal configured `JWT_AUDIENCE`
3. **Array Support**: If token has `aud: ["a", "b"]`, accept if expected audience is in array
4. **Case Sensitivity**: Comparison is case-sensitive

### Not-Before Claim (nbf)

1. **Presence**: Token MUST contain `nbf` claim
2. **Timestamp**: `nbf` is Unix timestamp (seconds since epoch)
3. **Validation**: Current time MUST be >= nbf (minus leeway)
4. **Leeway**: 60-second tolerance for clock skew

## State Transitions

N/A - Stateless validation, no state machine.

## Error Mapping

| PyJWT Exception | HTTP Status | Log Level | Log Message |
|-----------------|-------------|-----------|-------------|
| `InvalidAudienceError` | 401 | WARNING | "JWT audience mismatch detected" |
| `ImmatureSignatureError` | 401 | DEBUG | "JWT not yet valid (nbf)" |
| `MissingRequiredClaimError` | 401 | DEBUG | "JWT missing required claim: {claim}" |

## Test Token Structure

Tokens generated for testing must include:

```python
{
    "sub": "user-id",           # Required: User identifier
    "exp": <future_timestamp>,  # Required: Expiration
    "iat": <past_timestamp>,    # Required: Issued at
    "iss": "sentiment-analyzer", # Required: Issuer
    "nbf": <past_timestamp>,    # NEW Required: Not before
    "aud": "sentiment-analyzer-api", # NEW Required: Audience
    "roles": ["user"]           # Optional: User roles
}
```
