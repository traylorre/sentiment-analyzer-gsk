# CI/CD Gotchas

Common pitfalls and their fixes discovered during development. Each entry follows the pattern: Problem, Symptom, Fix, Prevention.

---

## CORS Wildcard + Credentials (Feature 1267)

**Problem**: `Access-Control-Allow-Origin: *` silently fails when `credentials: 'include'` is used on `fetch()`.

**Why**: Per CORS spec, the wildcard `*` is treated as the literal string `"*"` (not a wildcard) when credentials mode is enabled. The browser rejects the preflight response and the fetch silently fails.

**Symptom**: API calls return no data. Frontend shows empty state. No error in the browser console (CORS failures are opaque by design).

**Root Cause**: Three locations in `infrastructure/terraform/modules/api_gateway/main.tf` had `"'*'"` for `Access-Control-Allow-Origin`:
1. `local.cors_headers` (used by public route OPTIONS responses)
2. `proxy_options` integration response (catch-all `{proxy+}` OPTIONS)
3. `root_options` integration response (root `/` OPTIONS)

**Fix**: Replace `"'*'"` with `"method.request.header.Origin"` (origin echoing). This is the standard AWS API Gateway pattern that echoes the requesting Origin header verbatim.

```hcl
# BEFORE (broken with credentials: 'include')
"method.response.header.Access-Control-Allow-Origin" = "'*'"

# AFTER (works with credentials: 'include')
"method.response.header.Access-Control-Allow-Origin" = "method.request.header.Origin"
```

Additionally:
- Added `Access-Control-Allow-Credentials: 'true'` to proxy and root OPTIONS responses (was missing)
- Added `Vary: Origin` header to prevent CDN/proxy cache poisoning

**Prevention**:
- Unit tests in `tests/unit/test_api_gateway_cognito.py` parse the HCL and assert no wildcard `'*'` appears in any `Access-Control-Allow-Origin` value
- Never use `Access-Control-Allow-Origin: *` when `Access-Control-Allow-Credentials: true` is set
- Always include `Vary: Origin` when origin echoing is used
