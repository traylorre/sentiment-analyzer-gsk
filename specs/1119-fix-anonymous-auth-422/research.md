# Research: Fix Anonymous Auth 422 Error

**Feature**: 1119-fix-anonymous-auth-422
**Date**: 2026-01-02

## Research Questions

### Q1: How to make FastAPI body parameter optional (accept no body)?

**Decision**: Use `Body(default=None)` with union type

**Rationale**:
- In FastAPI, a function parameter typed as a Pydantic model requires a request body to be present
- Even if all model fields have defaults, the body parsing step itself fails without a body
- The `Body(default=None)` pattern allows the entire body to be omitted
- When body is None, instantiate the model with defaults in the handler

**Research Source**: FastAPI documentation on request body, Pydantic v2 documentation

**Pattern**:
```python
from fastapi import Body
from pydantic import BaseModel

class MyModel(BaseModel):
    field1: str = "default"
    field2: int | None = None

@router.post("/endpoint")
async def endpoint(
    body: MyModel | None = Body(default=None),  # Allows no body
):
    if body is None:
        body = MyModel()  # Use all defaults
    # body.field1 == "default", body.field2 == None
```

### Q2: Does existing AnonymousSessionRequest need changes?

**Decision**: No changes needed

**Rationale**: The model already has proper defaults defined:
```python
class AnonymousSessionRequest(BaseModel):
    timezone: str = Field(default="America/New_York")
    device_fingerprint: str | None = Field(default=None)
```

### Q3: What about empty body `{}` vs no body?

**Decision**: Both should work

**Rationale**:
- Empty body `{}` already works - Pydantic instantiates model with defaults
- No body (undefined/null) currently fails - this is what we're fixing
- After the fix, both will return 201 with default values

### Q4: Impact on existing frontend code?

**Decision**: No impact - backward compatible

**Rationale**:
- Frontend currently sends `undefined` (no body) - will now work
- If frontend ever sends `{}` or populated body, it will continue to work
- This is a permissive change, not a breaking change

## Alternatives Rejected

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Modify frontend to send `{}` | Requires frontend changes, violates "backend-only fix" requirement |
| Catch 422 and return defaults | Workaround, not proper API design |
| Use middleware to inject body | Over-engineering for simple fix |
| Default value in Body() directly | `Body(default=MyModel())` doesn't work - needs JSON-serializable default |

## Conclusion

Single-line signature change plus 2-line null check is the minimal, correct solution.
