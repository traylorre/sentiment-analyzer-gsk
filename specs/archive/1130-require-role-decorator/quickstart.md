# Quickstart: @require_role Decorator

**Feature**: 1130-require-role-decorator
**Date**: 2026-01-05

## Installation

The decorator is available after implementing this feature. No additional packages required.

## Basic Usage

```python
from src.lambdas.shared.middleware import require_role

@router.post("/admin/sessions/revoke")
@require_role("operator")
async def revoke_all_sessions(request: Request):
    """Revoke all active sessions. Requires operator role."""
    # Only operators can execute this code
    ...
```

## Available Roles

| Role | Description | Use Case |
|------|-------------|----------|
| `anonymous` | Unauthenticated user | Public content with session tracking |
| `free` | Authenticated, no subscription | Basic features |
| `paid` | Active subscription | Premium features |
| `operator` | Administrative access | Admin endpoints |

## Common Patterns

### Protecting Admin Endpoints

```python
from src.lambdas.shared.middleware import require_role
from fastapi import APIRouter, Request, Depends

admin_router = APIRouter(prefix="/admin")

@admin_router.post("/sessions/revoke")
@require_role("operator")
async def revoke_sessions(request: Request):
    """Requires operator role."""
    ...

@admin_router.get("/users/lookup")
@require_role("operator")
async def lookup_user(request: Request, email: str):
    """Requires operator role."""
    ...
```

### Protecting Paid Features

```python
@router.get("/premium/analytics")
@require_role("paid")
async def get_premium_analytics(request: Request):
    """Requires paid subscription."""
    ...

@router.get("/premium/export")
@require_role("paid")
async def export_data(request: Request):
    """Requires paid subscription."""
    ...
```

### Combining with Dependencies

```python
from fastapi import Depends

@router.post("/admin/config")
@require_role("operator")
async def update_config(
    request: Request,
    table=Depends(get_users_table),
    body: ConfigUpdate = Body(...),
):
    """Decorator works with other dependencies."""
    # table is injected, role is verified
    ...
```

## Error Responses

### 401 Unauthorized (No Authentication)

```json
{
  "detail": "Authentication required"
}
```

### 401 Unauthorized (Invalid Token)

```json
{
  "detail": "Invalid token structure"
}
```

### 403 Forbidden (Insufficient Role)

```json
{
  "detail": "Access denied"
}
```

**Note**: The 403 response is intentionally generic to prevent role enumeration attacks.

## Decorator Order

The decorator should be applied **after** the route decorator:

```python
# CORRECT
@router.post("/admin/endpoint")
@require_role("operator")
async def admin_endpoint(request: Request):
    ...

# INCORRECT (will not work)
@require_role("operator")
@router.post("/admin/endpoint")
async def admin_endpoint(request: Request):
    ...
```

## Testing Protected Endpoints

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

def test_operator_can_access_admin_endpoint(client: TestClient):
    """Test that operators can access protected endpoints."""
    # Mock auth context to return operator role
    mock_context = AuthContext(
        user_id="test-user",
        auth_type=AuthType.AUTHENTICATED,
        auth_method="bearer",
        roles=["free", "operator"],
    )

    with patch("src.lambdas.shared.middleware.auth_middleware.extract_auth_context_typed", return_value=mock_context):
        response = client.post("/admin/sessions/revoke")
        assert response.status_code == 200

def test_non_operator_gets_403(client: TestClient):
    """Test that non-operators get 403."""
    mock_context = AuthContext(
        user_id="test-user",
        auth_type=AuthType.AUTHENTICATED,
        auth_method="bearer",
        roles=["free"],  # No operator role
    )

    with patch("src.lambdas.shared.middleware.auth_middleware.extract_auth_context_typed", return_value=mock_context):
        response = client.post("/admin/sessions/revoke")
        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"
```

## Invalid Role Detection

Using an invalid role will raise an error at **startup**, not runtime:

```python
@router.get("/endpoint")
@require_role("admn")  # Typo!
async def endpoint(request: Request):
    ...

# On app startup:
# ValueError: Invalid role 'admn'. Valid roles: ['anonymous', 'free', 'operator', 'paid']
```

## FAQ

**Q: What happens if I use a role that doesn't exist?**
A: The application will fail to start with a clear error message.

**Q: Can I require multiple roles?**
A: This feature supports single role checks. For multiple roles, chain decorators or use a custom dependency.

**Q: Why is the error message generic?**
A: To prevent role enumeration attacks. An attacker cannot determine which roles exist by probing endpoints.

**Q: How do roles get into the JWT?**
A: That's handled by Phase 1.5 (jwt-roles-claim). This decorator only reads the `roles` claim.
