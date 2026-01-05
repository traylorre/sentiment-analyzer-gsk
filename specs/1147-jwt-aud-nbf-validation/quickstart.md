# Quickstart: JWT Audience and Not-Before Validation

**Feature**: 1147-jwt-aud-nbf-validation
**Date**: 2026-01-05

## Prerequisites

- Python 3.13
- PyJWT (already installed)
- Access to `auth_middleware.py`

## Implementation Overview

This feature adds two JWT claim validations to close CVSS 7.8 security vulnerabilities:

1. **Audience (aud)**: Prevents cross-service token replay
2. **Not-Before (nbf)**: Prevents pre-generated token attacks

## Step-by-Step Implementation

### Step 1: Update JWTConfig Dataclass

Add `audience` field to `JWTConfig`:

```python
@dataclass(frozen=True)
class JWTConfig:
    secret: str
    algorithm: str = "HS256"
    issuer: str | None = "sentiment-analyzer"
    audience: str | None = None  # ADD THIS
    leeway_seconds: int = 60
```

### Step 2: Update from_env() Method

Load audience from environment:

```python
@classmethod
def from_env(cls) -> "JWTConfig":
    return cls(
        secret=os.environ["JWT_SECRET"],
        algorithm=os.environ.get("JWT_ALGORITHM", "HS256"),
        issuer=os.environ.get("JWT_ISSUER", "sentiment-analyzer"),
        audience=os.environ.get("JWT_AUDIENCE"),  # ADD THIS
        leeway_seconds=int(os.environ.get("JWT_LEEWAY_SECONDS", "60")),
    )
```

### Step 3: Update jwt.decode() Call

Add audience parameter and nbf requirement:

```python
payload = jwt.decode(
    token,
    config.secret,
    algorithms=[config.algorithm],
    issuer=config.issuer,
    audience=config.audience,  # ADD THIS
    leeway=config.leeway_seconds,
    options={
        "require": ["sub", "exp", "iat", "nbf"],  # ADD nbf
    },
)
```

### Step 4: Add Error Handlers

Add handlers for new exception types:

```python
except jwt.InvalidAudienceError:
    logger.warning("JWT audience mismatch detected")
    return None

except jwt.ImmatureSignatureError:
    logger.debug("JWT not yet valid (nbf)")
    return None
```

### Step 5: Update Test Fixtures

Update `create_test_jwt()` in `tests/e2e/conftest.py`:

```python
def create_test_jwt(
    user_id: str,
    secret: str,
    expires_in: int = 3600,
    issuer: str = "sentiment-analyzer",
    audience: str = "sentiment-analyzer-api",  # ADD THIS
) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "exp": now + expires_in,
        "iat": now,
        "nbf": now,  # ADD THIS
        "iss": issuer,
        "aud": audience,  # ADD THIS
    }
    return jwt.encode(payload, secret, algorithm="HS256")
```

## Environment Configuration

Set these environment variables:

| Environment | JWT_AUDIENCE |
|-------------|--------------|
| Local/Dev | `sentiment-analyzer-api-dev` |
| Preprod | `sentiment-analyzer-api-preprod` |
| Prod | `sentiment-analyzer-api` |

## Testing

### Unit Test: Audience Validation

```python
def test_rejects_wrong_audience():
    token = create_jwt(aud="other-service")
    result = validate_jwt(token, config_with_expected_audience)
    assert result is None

def test_accepts_correct_audience():
    token = create_jwt(aud="sentiment-analyzer-api")
    result = validate_jwt(token, config_with_expected_audience)
    assert result is not None
```

### Unit Test: NBF Validation

```python
def test_rejects_future_nbf():
    token = create_jwt(nbf=time.time() + 300)  # 5 minutes future
    result = validate_jwt(token, config)
    assert result is None

def test_accepts_past_nbf():
    token = create_jwt(nbf=time.time() - 60)  # 1 minute ago
    result = validate_jwt(token, config)
    assert result is not None
```

## Breaking Change

Tokens issued before this change (without `aud`/`nbf` claims) will be rejected. This is intentional for security. Users must re-authenticate to receive new tokens.
