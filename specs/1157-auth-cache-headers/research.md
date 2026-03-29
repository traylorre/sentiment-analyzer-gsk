# Research: Auth Cache-Control Headers

**Feature**: 1157-auth-cache-headers
**Date**: 2026-01-06

## Research Tasks Completed

### 1. FastAPI Response Header Patterns

**Question**: What is the best practice for setting response headers in FastAPI?

**Finding**: FastAPI provides multiple approaches:

1. **Dependency Injection** (Recommended for this use case)

   ```python
   from fastapi import Depends, Response

   async def add_no_cache_headers(response: Response):
       response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

   @router.get("/endpoint", dependencies=[Depends(add_no_cache_headers)])
   ```

2. **Custom Response Class**

   ```python
   class NoCacheJSONResponse(JSONResponse):
       def __init__(self, *args, **kwargs):
           super().__init__(*args, **kwargs)
           self.headers["Cache-Control"] = "..."
   ```

3. **Middleware** (For application-wide headers)
   ```python
   @app.middleware("http")
   async def add_cache_headers(request, call_next):
       response = await call_next(request)
       if request.url.path.startswith("/auth"):
           response.headers["Cache-Control"] = "..."
       return response
   ```

**Decision**: Use Dependency Injection at the APIRouter level for auth endpoints. This provides:

- Centralized configuration
- Easy testing
- Clear scope (auth endpoints only)

### 2. HTTP Cache Header Standards

**Question**: What combination of headers ensures no caching?

**Canonical Source**: RFC 7234 (HTTP/1.1 Caching)

**Finding**:

| Header        | Value           | Purpose                          | RFC Reference     |
| ------------- | --------------- | -------------------------------- | ----------------- |
| Cache-Control | no-store        | Prevents storage entirely        | RFC 7234 §5.2.2.3 |
| Cache-Control | no-cache        | Requires revalidation before use | RFC 7234 §5.2.2.1 |
| Cache-Control | must-revalidate | Stale responses must not be used | RFC 7234 §5.2.2.2 |
| Pragma        | no-cache        | HTTP/1.0 compatibility           | RFC 7234 §5.4     |
| Expires       | 0               | Legacy proxy compatibility       | RFC 7234 §5.3     |

**Rationale for Combined Headers**:

- `no-store` alone should suffice per spec, but...
- Some older proxies don't honor `Cache-Control`
- `Pragma: no-cache` provides HTTP/1.0 fallback
- `Expires: 0` provides additional legacy support
- Combined approach is defensive and widely used for sensitive data

**Industry Pattern**: OWASP recommends this exact combination for authentication responses.

## Alternatives Considered

### Alternative 1: Only `Cache-Control: no-store`

- **Pros**: Simplest, should be sufficient per spec
- **Cons**: Legacy proxy compatibility concerns
- **Rejected**: Defense in depth preferred for auth data

### Alternative 2: Per-endpoint manual headers

- **Pros**: Most explicit control
- **Cons**: Repetitive, easy to miss an endpoint
- **Rejected**: DRY principle violation

### Alternative 3: Application-wide middleware

- **Pros**: Guaranteed coverage
- **Cons**: Affects non-auth endpoints unnecessarily
- **Rejected**: Too broad scope

## Conclusion

Use FastAPI dependency injection at the auth router level with the full header set:

```
Cache-Control: no-store, no-cache, must-revalidate
Pragma: no-cache
Expires: 0
```

This approach is:

- Standards-compliant (RFC 7234)
- OWASP-recommended
- Scoped to auth endpoints only
- Easy to test and maintain
