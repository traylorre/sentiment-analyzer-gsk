# Authentication API Contract

**Feature**: 006-user-config-dashboard | **Version**: 1.0
**Base URL**: `https://{lambda-url}.lambda-url.{region}.on.aws` or `https://api.{domain}/v2`

## Overview

Authentication flow supports three paths:
1. **Anonymous**: localStorage-based session (no auth required)
2. **Magic Link**: Email-based passwordless auth via SendGrid
3. **OAuth**: Google/GitHub via AWS Cognito

---

## Anonymous Session

### Create Anonymous Session

Called automatically on first visit when no existing session found.

```http
POST /api/v2/auth/anonymous
Content-Type: application/json

{
  "timezone": "America/New_York",
  "device_fingerprint": "optional-browser-fingerprint"
}
```

**Response** (201 Created):
```json
{
  "user_id": "uuid",
  "auth_type": "anonymous",
  "created_at": "2025-11-26T10:00:00Z",
  "session_expires_at": "2025-12-26T10:00:00Z",
  "storage_hint": "localStorage"
}
```

**Client Storage**:
```javascript
localStorage.setItem('sentiment_user_id', response.user_id);
localStorage.setItem('sentiment_session_expires', response.session_expires_at);
```

### Validate Anonymous Session

```http
GET /api/v2/auth/validate
X-Anonymous-ID: {user_id}
```

**Response** (200 OK) - Valid:
```json
{
  "valid": true,
  "user_id": "uuid",
  "auth_type": "anonymous",
  "expires_at": "2025-12-26T10:00:00Z"
}
```

**Response** (401 Unauthorized) - Invalid/Expired:
```json
{
  "valid": false,
  "error": "session_expired",
  "message": "Session has expired. Please create a new session."
}
```

---

## Magic Link Authentication

### Request Magic Link

```http
POST /api/v2/auth/magic-link
Content-Type: application/json

{
  "email": "user@example.com",
  "anonymous_user_id": "uuid-to-merge"
}
```

**Response** (202 Accepted):
```json
{
  "status": "email_sent",
  "email": "user@example.com",
  "expires_in_seconds": 3600,
  "message": "Check your email for a sign-in link"
}
```

**Email Content** (via SendGrid):
```
Subject: Your sign-in link for Sentiment Dashboard

Click the link below to sign in:
https://app.domain/auth/verify?token={token_id}&sig={signature}

This link expires in 1 hour.
If you didn't request this, you can ignore this email.
```

**Previous Link Invalidation**:
If user requests a new magic link while one is pending:
1. Previous token is invalidated
2. User receives notification email about invalidation
3. New token is created and sent

### Verify Magic Link

```http
GET /api/v2/auth/magic-link/verify?token={token_id}&sig={signature}
```

**Response** (200 OK) - Success:
```json
{
  "status": "verified",
  "user_id": "uuid",
  "email": "user@example.com",
  "auth_type": "email",
  "tokens": {
    "id_token": "eyJ...",
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_in": 3600
  },
  "merged_anonymous_data": true
}
```

**Response** (400 Bad Request) - Invalid:
```json
{
  "status": "invalid",
  "error": "token_expired",
  "message": "This link has expired. Please request a new one."
}
```

**Response** (400 Bad Request) - Already Used:
```json
{
  "status": "invalid",
  "error": "token_used",
  "message": "This link has already been used."
}
```

---

## OAuth Authentication (Cognito)

### Get OAuth URLs

```http
GET /api/v2/auth/oauth/urls
```

**Response** (200 OK):
```json
{
  "providers": {
    "google": {
      "authorize_url": "https://cognito-domain.auth.region.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=Google",
      "icon": "google"
    },
    "github": {
      "authorize_url": "https://cognito-domain.auth.region.amazoncognito.com/oauth2/authorize?client_id=xxx&response_type=code&scope=openid+email+profile&redirect_uri=https://app.domain/auth/callback&identity_provider=GitHub",
      "icon": "github"
    }
  }
}
```

### OAuth Callback

```http
POST /api/v2/auth/oauth/callback
Content-Type: application/json

{
  "code": "authorization_code_from_cognito",
  "provider": "google",
  "anonymous_user_id": "uuid-to-merge"
}
```

**Response** (200 OK):
```json
{
  "status": "authenticated",
  "user_id": "uuid",
  "email": "user@gmail.com",
  "auth_type": "google",
  "tokens": {
    "id_token": "eyJ...",
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_in": 3600
  },
  "merged_anonymous_data": true,
  "is_new_user": false
}
```

---

## Token Management

### Refresh Tokens

```http
POST /api/v2/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

**Response** (200 OK):
```json
{
  "id_token": "eyJ...",
  "access_token": "eyJ...",
  "expires_in": 3600
}
```

**Response** (401 Unauthorized) - Invalid Refresh Token:
```json
{
  "error": "invalid_refresh_token",
  "message": "Please sign in again."
}
```

### Sign Out (Current Device)

```http
POST /api/v2/auth/signout
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "status": "signed_out",
  "message": "Signed out from this device"
}
```

Note: This invalidates tokens for current device only, not all devices.

---

## Account Linking

### Check for Existing Account

When user authenticates with email that exists under different auth method:

```http
POST /api/v2/auth/check-email
Content-Type: application/json

{
  "email": "user@example.com",
  "current_provider": "google"
}
```

**Response** (200 OK) - No Conflict:
```json
{
  "conflict": false
}
```

**Response** (200 OK) - Conflict Detected:
```json
{
  "conflict": true,
  "existing_provider": "email",
  "message": "An account with this email exists via magic link. Would you like to link your Google account?"
}
```

### Link Accounts

Requires explicit user confirmation.

```http
POST /api/v2/auth/link-accounts
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "link_to_user_id": "existing-user-uuid",
  "confirmation": true
}
```

**Response** (200 OK):
```json
{
  "status": "linked",
  "user_id": "existing-user-uuid",
  "linked_providers": ["email", "google"],
  "message": "Accounts successfully linked"
}
```

---

## Session Management

### Get Session Info

```http
GET /api/v2/auth/session
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "auth_type": "google",
  "session_started_at": "2025-11-26T10:00:00Z",
  "session_expires_at": "2025-12-26T10:00:00Z",
  "last_activity_at": "2025-11-26T15:30:00Z",
  "linked_providers": ["google"]
}
```

### Extend Session (Activity)

Session is automatically extended on any authenticated API call.
Explicit extension endpoint:

```http
POST /api/v2/auth/session/extend
Authorization: Bearer {access_token}
```

**Response** (200 OK):
```json
{
  "session_expires_at": "2025-12-26T15:30:00Z",
  "message": "Session extended for 30 days"
}
```

---

## Anonymous Data Merge

When upgrading from anonymous to authenticated, data merge happens automatically.

### Merge Strategy

1. **Configurations**: All anonymous configs transferred to authenticated account
2. **Alert Rules**: All anonymous alerts transferred
3. **Preferences**: Anonymous preferences preserved (can be overwritten)

### Check Merge Status

```http
GET /api/v2/auth/merge-status?anonymous_user_id={uuid}
Authorization: Bearer {access_token}
```

**Response** (200 OK) - Merge Completed:
```json
{
  "status": "completed",
  "merged_at": "2025-11-26T10:00:00Z",
  "items_merged": {
    "configurations": 2,
    "alert_rules": 5,
    "preferences": 1
  }
}
```

**Response** (200 OK) - No Data to Merge:
```json
{
  "status": "no_data",
  "message": "No anonymous data found to merge"
}
```

---

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /auth/anonymous` | 10 | per minute per IP |
| `POST /auth/magic-link` | 5 | per hour per email |
| `POST /auth/oauth/callback` | 20 | per minute per IP |
| `POST /auth/refresh` | 30 | per minute per user |

**Rate Limit Response** (429 Too Many Requests):
```json
{
  "error": "rate_limited",
  "message": "Too many requests. Please try again later.",
  "retry_after_seconds": 60
}
```

---

## Security Headers

All responses include:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

---

## Client-Side Implementation Notes

### localStorage Schema

```javascript
{
  "sentiment_user_id": "uuid",
  "sentiment_auth_type": "anonymous|email|google|github",
  "sentiment_tokens": {
    "id_token": "eyJ...",
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "expires_at": 1732633200
  },
  "sentiment_session_expires": "2025-12-26T10:00:00Z"
}
```

### Token Refresh Logic

```javascript
async function ensureValidToken() {
  const tokens = getStoredTokens();
  if (!tokens) return null;

  const expiresAt = tokens.expires_at * 1000;
  const now = Date.now();
  const buffer = 5 * 60 * 1000; // 5 minutes

  if (now + buffer >= expiresAt) {
    // Token expiring soon, refresh it
    const newTokens = await refreshTokens(tokens.refresh_token);
    storeTokens(newTokens);
    return newTokens.access_token;
  }

  return tokens.access_token;
}
```
