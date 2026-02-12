# Implementation Gaps: spec-v2.md vs Current Implementation

**Generated**: 2026-01-07
**Spec Version**: v3.0
**Status**: ALL GAPS CLOSED

---

## Summary

All implementation gaps from the spec-v2.md audit have been addressed:

| Feature | Spec | Status | PR |
|---------|------|--------|-----|
| 1157 | Cache-Control Headers | ✅ Complete | Implemented |
| 1158 | CSRF Double-Submit | ✅ Complete (32 tests) | Implemented |
| 1159 | SameSite=None + CORS | ✅ Complete (7 tests) | Implemented |
| 1160 | Refresh Endpoint Cookie | ✅ Complete (9 tests) | Implemented |
| 1161 | CSRF Bearer Exemption | ✅ Complete | Implemented |
| 1162 | User Model Federation | ✅ Complete | Implemented |
| 1163 | Role-Verification Invariant | ✅ Complete (17 tests) | Implemented |
| 1164 | Remove Magic Link Secret | ✅ Complete | #615 |
| 1165 | Remove Auth Store Persist | ✅ Complete | #616 |
| 1166 | Complete HMAC Removal | ✅ Complete | #617 |
| 1167 | Remove X-User-ID Header | ✅ Complete | #618 |
| 1168 | Refresh Cookie-Only (Frontend) | ✅ Complete | #619 |

---

## Verified Implementations

### Security (Critical)

1. **SameSite=None** - router_v2.py lines 511, 577 (paired with secure=True)
2. **CSRF Double-Submit** - csrf.py + csrf_middleware.py (hmac.compare_digest for timing-safe validation)
3. **CloudFront CORS** - cloudfront/main.tf:152 (access_control_allow_credentials = true)
4. **HttpOnly Cookies** - All auth cookies set with httponly=True

### Data Model

5. **User Model Fields** - All 9 federation fields added with backward-compatible aliases
6. **Role-Verification Invariant** - Pydantic model_validator with auto-upgrade logic
7. **ProviderMetadata Class** - Nested model for linked provider data

### Auth Flow

8. **Refresh Token Cookie** - Cookie-first extraction with body fallback
9. **Cache-Control Headers** - no-store, no-cache, must-revalidate on all auth endpoints

---

## Archive

Previous gap analysis archived to: `archive/implementation-gaps-closed-2026-01-07.md`
