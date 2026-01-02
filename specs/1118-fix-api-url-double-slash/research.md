# Research: Fix Double-Slash URL in API Requests

**Feature**: 1118-fix-api-url-double-slash
**Date**: 2026-01-02

## Research Tasks

### 1. URL Normalization Best Practices

**Decision**: Use a simple `joinUrl` utility function that:
1. Removes trailing slash from base URL
2. Ensures path starts with a single slash
3. Concatenates with single slash between

**Rationale**: This is the standard pattern used across the industry. It's deterministic, has no edge cases with proper implementation, and produces consistent results regardless of input format.

**Implementation Pattern**:
```typescript
function joinUrl(baseUrl: string, path: string): string {
  const normalizedBase = baseUrl.replace(/\/+$/, '');  // Remove trailing slashes
  const normalizedPath = path.replace(/^\/+/, '');     // Remove leading slashes
  return `${normalizedBase}/${normalizedPath}`;
}
```

**Alternatives Considered**:
- **URL constructor**: `new URL(path, baseUrl)` - Rejected: Behavior varies with path format and can produce unexpected results with leading slashes
- **Template literals only**: `${baseUrl}${path}` - Rejected: Current approach, causes the double-slash bug
- **Trailing slash on base URL**: Requires changing infrastructure config - Rejected: Moving the problem elsewhere, not solving it

### 2. Where URL Construction Happens

**Decision**: Modify `frontend/src/lib/api/client.ts` where the API client constructs request URLs

**Rationale**: This is the single point where all API requests are constructed. Fixing it here ensures all endpoints benefit from the fix.

**Key Finding**: The current code likely does:
```typescript
const url = `${API_URL}${endpoint}`;  // If API_URL has no trailing slash and endpoint has leading slash, produces //
```

**Fix Location**: Apply `joinUrl` at the point where URL is constructed from base + endpoint

### 3. Testing Strategy

**Decision**: Unit test the `joinUrl` function with all edge case combinations

**Test Cases**:
| Base URL | Path | Expected Result |
|----------|------|-----------------|
| `https://api.example.com` | `/api/v2/auth` | `https://api.example.com/api/v2/auth` |
| `https://api.example.com/` | `/api/v2/auth` | `https://api.example.com/api/v2/auth` |
| `https://api.example.com` | `api/v2/auth` | `https://api.example.com/api/v2/auth` |
| `https://api.example.com/` | `api/v2/auth` | `https://api.example.com/api/v2/auth` |
| `https://api.example.com//` | `//api/v2/auth` | `https://api.example.com/api/v2/auth` |

**Rationale**: Comprehensive edge case testing ensures the function handles any input variation correctly.

## Unknowns Resolved

| Unknown | Resolution |
|---------|------------|
| Best normalization approach | Simple string manipulation with trim + join |
| Where to implement | frontend/src/lib/api/client.ts |
| Handling multiple slashes | Regex replacement removes all leading/trailing slashes |

## No Further Research Needed

The URL normalization pattern is well-established and straightforward. Implementation can proceed.
