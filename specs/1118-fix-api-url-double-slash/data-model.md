# Data Model: Fix Double-Slash URL in API Requests

**Feature**: 1118-fix-api-url-double-slash
**Date**: 2026-01-02

## URL Construction Model

This feature involves string manipulation, not data persistence. The "data model" describes the URL construction logic.

### Input Types

#### API Base URL
- **Source**: Environment variable `NEXT_PUBLIC_API_URL`
- **Format**: HTTPS URL, may or may not have trailing slash
- **Examples**:
  - `https://abc123.lambda-url.us-east-1.on.aws` (no trailing slash - Lambda default)
  - `https://abc123.lambda-url.us-east-1.on.aws/` (with trailing slash)

#### Endpoint Path
- **Source**: Defined in API client code (auth.ts, etc.)
- **Format**: API route path, may or may not have leading slash
- **Examples**:
  - `/api/v2/auth/anonymous` (with leading slash - common pattern)
  - `api/v2/auth/anonymous` (without leading slash)

### Output Type

#### Constructed URL
- **Format**: Valid HTTPS URL with exactly one slash between base and path
- **Invariant**: Must NEVER contain `//` in the path portion (after protocol)
- **Example**: `https://abc123.lambda-url.us-east-1.on.aws/api/v2/auth/anonymous`

## Normalization Function Signature

```typescript
/**
 * Joins a base URL and path, ensuring no double slashes.
 *
 * @param baseUrl - The API base URL (e.g., from NEXT_PUBLIC_API_URL)
 * @param path - The endpoint path (e.g., '/api/v2/auth/anonymous')
 * @returns Properly formatted URL with single slash between base and path
 *
 * @example
 * joinUrl('https://api.example.com', '/api/v2/auth')
 * // => 'https://api.example.com/api/v2/auth'
 *
 * joinUrl('https://api.example.com/', '/api/v2/auth')
 * // => 'https://api.example.com/api/v2/auth'
 */
function joinUrl(baseUrl: string, path: string): string
```

## Validation Rules

1. **Base URL Required**: If base URL is empty/undefined, throw clear error
2. **Path Required**: If path is empty/undefined, return base URL as-is
3. **No Double Slashes**: Output must never contain `//` after the protocol `://`
4. **Preserve Protocol**: The `https://` must remain intact

## Edge Case Matrix

| # | Base URL | Path | Expected Output | Notes |
|---|----------|------|-----------------|-------|
| 1 | `https://a.com` | `/path` | `https://a.com/path` | Standard case |
| 2 | `https://a.com/` | `/path` | `https://a.com/path` | Both have slash |
| 3 | `https://a.com` | `path` | `https://a.com/path` | Neither has slash |
| 4 | `https://a.com/` | `path` | `https://a.com/path` | Only base has slash |
| 5 | `https://a.com//` | `//path` | `https://a.com/path` | Multiple slashes |
| 6 | `https://a.com` | `` | `https://a.com` | Empty path |
| 7 | `` | `/path` | ERROR | Empty base |
