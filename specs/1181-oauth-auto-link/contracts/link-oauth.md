# OAuth Account Linking API Contract

## POST /api/v2/auth/link-oauth

### Description
Links an OAuth identity to an existing email-verified user account.
Called after OAuth callback when user confirms manual linking.

### Request Headers
- Authorization: Bearer {access_token}
- Content-Type: application/json

### Request Body
```json
{
  "provider": "google" | "github",
  "oauth_state": "string (state token from OAuth callback)",
  "link_type": "manual" | "auto"
}
```

### Success Response (200 OK)
```json
{
  "success": true,
  "user": {
    "user_id": "uuid",
    "email": "user@example.com",
    "linked_providers": ["email", "google"],
    "last_provider_used": "google"
  },
  "link_type": "auto" | "manual"
}
```

### Error Responses

#### 400 Bad Request - Email Not Verified by Provider
```json
{
  "error": "AUTH_022",
  "message": "Email not verified by provider"
}
```

#### 409 Conflict - OAuth Already Linked to Different User
```json
{
  "error": "AUTH_023",
  "message": "This OAuth account is already linked to another user"
}
```

#### 401 Unauthorized - No Valid Session
```json
{
  "error": "AUTH_001",
  "message": "Authentication required"
}
```

---

## GET /api/v2/auth/link-prompt

### Description
Returns information needed to display the manual linking prompt.
Called when domain-based auto-link is not applicable.

### Request Headers
- Authorization: Bearer {access_token}

### Query Parameters
- state: OAuth state token

### Success Response (200 OK)
```json
{
  "show_prompt": true,
  "existing_email": "c**@hotmail.com",
  "oauth_provider": "google",
  "oauth_email": "c**@gmail.com",
  "options": [
    {
      "action": "link",
      "label": "Link Accounts",
      "description": "Connect both identities to this account"
    },
    {
      "action": "separate",
      "label": "Use Google Only",
      "description": "Sign in with Google as a separate identity"
    }
  ]
}
```

### Auto-Link Response (200 OK)
```json
{
  "show_prompt": false,
  "auto_linked": true,
  "message": "Accounts automatically linked"
}
```
