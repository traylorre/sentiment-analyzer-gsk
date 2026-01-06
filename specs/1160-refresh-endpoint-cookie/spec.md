# Feature 1160: Refresh Endpoint Cookie Extraction

## Problem Statement

The `/api/v2/auth/refresh` endpoint currently requires the refresh token in the request body. This is insecure because:
1. JavaScript must store the refresh token (exposed to XSS)
2. Client code must explicitly send the token (additional attack surface)

## Solution

Extract refresh token from httpOnly cookie instead of request body. Browser sends cookie automatically - no JavaScript access needed.

## Current Behavior

```
POST /api/v2/auth/refresh
Content-Type: application/json

{"refresh_token": "xyz"}  <-- Token in body (JS must handle)
```

## Desired Behavior

```
POST /api/v2/auth/refresh
Cookie: refresh_token=xyz  <-- Browser sends automatically
(NO BODY REQUIRED)

Response:
Set-Cookie: refresh_token=new_xyz; HttpOnly; Secure; SameSite=None
{"access_token": "abc", "user": {...}}
```

## Requirements

### R1: Cookie Extraction
- Add helper function to extract `refresh_token` from Cookie header
- Use Python's `http.cookies` or simple string parsing

### R2: Endpoint Modification
- Remove `RefreshTokenRequest` body requirement (make it optional for backwards compat)
- Try cookie first, fall back to body if present
- Set new refresh token cookie on successful refresh (rotation)

### R3: Response Cookie
- Set new rotated `refresh_token` as httpOnly cookie
- Use same attributes: `HttpOnly; Secure; SameSite=None; Path=/api/v2/auth`

## Security Considerations

1. **XSS Protection**: HttpOnly cookie cannot be read by JavaScript
2. **CSRF Protection**: CSRF double-submit pattern (Feature 1158) protects state-changing requests
3. **Token Rotation**: Issue new refresh token with each use to limit replay window

## Dependencies

- Feature 1158 (CSRF protection) - already implemented
- Feature 1159 (SameSite=None) - pending merge

## Acceptance Criteria

- [ ] Refresh endpoint extracts token from cookie
- [ ] Falls back to body for backwards compatibility
- [ ] Sets new refresh_token cookie on response
- [ ] Unit tests verify cookie extraction
