# Feature 1159: SameSite=None and CORS Credentials Update

## Problem Statement

Cross-origin cookie transmission fails between CloudFront frontend and Lambda Function URL backend. Cookies set with `SameSite=Strict` are not sent on cross-origin requests, breaking authentication flow.

## Context

- Frontend: CloudFront/Amplify domain (e.g., `main.d29tlmksqcx494.amplifyapp.com`)
- Backend: Lambda Function URL (e.g., `*.lambda-url.us-east-1.on.aws`)
- Different origins require `SameSite=None` for cookies to be transmitted
- CSRF protection (Feature 1158) is prerequisite - provides security when SameSite protection is removed

## Requirements

### R1: Backend Cookie Changes
- Change `SameSite` from `Strict` to `None` for all auth cookies
- Ensure `Secure=true` is set (mandatory with SameSite=None)
- Affected cookies: `__Host-access-token`, `__Host-refresh-token`, `__Host-csrf-token`

### R2: Backend CORS Headers
- Set `Access-Control-Allow-Credentials: true` on Lambda responses
- Set `Access-Control-Allow-Origin` to exact origin (NOT wildcard `*`)
- Include `X-CSRF-Token` in `Access-Control-Allow-Headers`
- Handle preflight OPTIONS requests correctly

### R3: CloudFront CORS Configuration
- Update Terraform `aws_cloudfront_distribution` response headers policy
- Set `access_control_allow_credentials = true`
- Ensure origin allowlist includes Amplify domain

### R4: Frontend fetch() Updates
- Add `credentials: 'include'` to all API fetch calls
- Ensure X-CSRF-Token header is sent with state-changing requests

## Security Considerations

1. **CSRF Protection Required**: SameSite=None removes browser CSRF protection; Feature 1158 double-submit pattern provides mitigation
2. **Origin Validation**: Backend must validate Origin header against allowlist
3. **Secure Flag Mandatory**: Browsers reject SameSite=None without Secure flag

## Dependencies

- Feature 1158 (CSRF double-submit cookie pattern) - MUST be merged first

## Acceptance Criteria

- [ ] Auth cookies sent cross-origin from CloudFront to Lambda Function URL
- [ ] CSRF validation still passes on state-changing requests
- [ ] No CORS errors in browser console
- [ ] Preflight OPTIONS requests return correct headers

## References

- RFC 6265bis (SameSite cookie attribute)
- spec-v2.md lines 6090-6107 (SameSite decision rationale)
- Feature 1158 (CSRF implementation)
