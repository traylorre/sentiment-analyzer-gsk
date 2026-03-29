# Implementation Plan: CORS Wildcard Origin Fix

**Branch**: `1268-cors-wildcard-fix` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1268-cors-wildcard-fix/spec.md`

## Summary

Replace the hardcoded `Access-Control-Allow-Origin: '*'` in all API Gateway OPTIONS integration responses with `method.request.header.Origin` (origin echoing). This is the standard AWS pattern used by the existing gateway error responses (401/403). The API Gateway module needs a new `cors_allowed_origins` variable for documentation/validation purposes, but the actual origin validation for data responses happens at the Lambda middleware layer (which already validates against `CORS_ORIGINS` env var). Three separate locations in `main.tf` contain the wildcard and must all be updated.

## Technical Context

**Language/Version**: Terraform (HCL) >= 1.5.0 with AWS Provider ~> 5.0
**Primary Dependencies**: AWS API Gateway (REST API), Lambda proxy integration, existing security_headers.py middleware
**Storage**: N/A (infrastructure-only change)
**Testing**: pytest (unit: HCL validation), curl/httpie (integration: header verification), Playwright (implicit CORS via dashboard functionality)
**Target Platform**: AWS API Gateway (REST API, not HTTP API)
**Project Type**: Web application (infrastructure layer)
**Performance Goals**: Zero latency impact (static header configuration change)
**Constraints**: Must not cause API Gateway redeployment failures; must maintain backward compatibility with existing frontend
**Scale/Scope**: 3 locations in 1 file + 1 new variable + root module wiring + test updates

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: All external endpoints authenticated | PASS | CORS is transport-level; auth unchanged |
| Security: No wildcards in sensitive configs | PASS after fix | This feature removes the wildcard |
| Security: Secrets in managed service | N/A | No secrets involved |
| IaC: Terraform for all infra | PASS | Change is in Terraform modules |
| Testing: Unit tests with mocks, E2E with real AWS | PASS | Plan includes both layers |
| Cost: No new billable resources | PASS | Configuration change only |

## Project Structure

### Documentation (this feature)

```text
specs/1268-cors-wildcard-fix/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Technical research
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── modules/api_gateway/
│   ├── main.tf          # PRIMARY: 3 wildcard locations to fix
│   └── variables.tf     # NEW: cors_allowed_origins variable
├── main.tf              # Wire cors_allowed_origins to module
├── variables.tf         # EXISTING: cors_allowed_origins (already exists)
└── preprod.tfvars       # EXISTING: origin list (already configured)

tests/
├── unit/
│   └── test_api_gateway_cognito.py  # UPDATE: Add wildcard-absence assertions
├── integration/
│   └── test_cors_headers.py         # NEW: curl-based header verification
└── e2e/
    └── test_cors_e2e.py             # NEW: deployed API header verification
```

**Structure Decision**: Existing infrastructure layout. No new directories needed except test files.

## Technical Approach

### Change 1: Update `local.cors_headers` (line 212)

Replace the wildcard with origin echoing:

```hcl
# BEFORE
"method.response.header.Access-Control-Allow-Origin" = "'*'"

# AFTER
"method.response.header.Access-Control-Allow-Origin" = "method.request.header.Origin"
```

This is used by 4 integration responses: `fr012_options`, `fr012_proxy_options`, `public_leaf_options`, `public_proxy_options`.

### Change 2: Update `proxy_options` integration response (line 619)

The catch-all `{proxy+}` OPTIONS handler has its own inline response_parameters (not using `local.cors_headers`). It also is missing `Access-Control-Allow-Credentials`. Fix both:

```hcl
# BEFORE
"method.response.header.Access-Control-Allow-Origin" = "'*'"
# (no credentials header)

# AFTER
"method.response.header.Access-Control-Allow-Origin"      = "method.request.header.Origin"
"method.response.header.Access-Control-Allow-Credentials"  = "'true'"
```

The method_response must also declare the new `Access-Control-Allow-Credentials` parameter.

### Change 3: Update `root_options` integration response (line 679)

Same pattern as Change 2 -- the root `/` OPTIONS handler has inline parameters with the same wildcard and missing credentials header.

### Change 4: Add `cors_allowed_origins` variable to api_gateway module

Add the variable to `modules/api_gateway/variables.tf` for documentation and potential future validation. Wire it from the root module.

### Change 5: Update method_response declarations

For the proxy and root OPTIONS method_responses, add `Access-Control-Allow-Credentials` to the response_parameters declaration (set to `true`).

### Change 6: Add `Vary: Origin` header

All OPTIONS responses should include `Vary: Origin` to prevent cache poisoning. Add to `local.cors_headers` and to the proxy/root inline headers.

### Why Origin Echoing Without Allowlist Validation Is Safe

API Gateway MOCK integrations cannot perform conditional logic. They can only echo the `Origin` header verbatim. This is acceptable because:

1. **OPTIONS preflight only authorizes the browser to send the request** -- it doesn't expose data.
2. **Actual data responses** go through Lambda proxy integration, where `security_headers.py` middleware validates the origin against `CORS_ORIGINS` env var (which comes from `cors_allowed_origins` tfvars).
3. **Gateway error responses** (401/403) already echo origin and contain no user data.
4. The browser enforces that the actual response must ALSO have matching CORS headers -- so even if OPTIONS succeeds for an evil origin, the Lambda response will reject it.

### Test Strategy

**Unit tests** (pytest, no AWS):
- Parse the Terraform HCL and assert no `'*'` appears in any CORS Allow-Origin value
- Assert `method.request.header.Origin` is used instead
- Assert `Access-Control-Allow-Credentials` is present in all OPTIONS responses
- Assert `Vary` header is declared

**Integration tests** (against deployed preprod API):
- Send OPTIONS with `Origin: https://main.d29tlmksqcx494.amplifyapp.com` -- assert echoed
- Send OPTIONS with `Origin: https://evil.example.com` -- assert echoed (expected: MOCK echoes all, Lambda validates)
- Send GET with `Origin: https://evil.example.com` and credentials -- assert Lambda rejects origin
- Send GET with valid origin and credentials -- assert Lambda echoes origin

**E2E tests** (against deployed preprod):
- Full authenticated flow: login, make API call, verify response received (implicit CORS)

**Playwright tests** (deferred per AR1-05):
- Dashboard loads and displays data (implicitly validates CORS works)
- No explicit CORS header assertions in Playwright (test infra limitation)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| API Gateway redeployment fails | Low | High | Terraform plan review before apply |
| Origin echoing breaks non-browser clients | None | N/A | Non-browser clients ignore CORS |
| Cache serves wrong origin | Medium | Medium | Vary: Origin header prevents this |
| Missing credentials header on proxy/root | Already broken | High | Fixed as part of this change |

## Deployment Plan

1. Apply Terraform change (API Gateway config update)
2. API Gateway creates new deployment automatically (trigger: resource config changes)
3. Verify via curl that OPTIONS responses echo origin
4. Verify frontend dashboard loads correctly
5. Rollback: revert Terraform and apply (immediate, no data migration)

## Adversarial Review #2

**Reviewer perspective**: Spec-plan alignment auditor. Checking for drift between specification and implementation plan.

### Drift Check: FR Traceability

| Spec FR | Plan Coverage | Status |
|---------|---------------|--------|
| FR-001 (echo origin for allowed) | Change 1, 2, 3 | COVERED |
| FR-002 (no wildcard with credentials) | Change 1, 2, 3 | COVERED |
| FR-003 (amended: echo-only, Lambda validates) | "Why Origin Echoing Is Safe" section | COVERED |
| FR-004 (module accepts allowlist) | Change 4 | COVERED |
| FR-005 (consistent with gateway responses) | Change 1 uses same pattern | COVERED |
| FR-006 (other CORS headers unchanged) | Plan explicitly preserves them | COVERED |
| FR-007 (Vary: Origin MUST) | Change 6 | COVERED |
| FR-008 (no wildcard in allowlist config) | Already exists in root variables.tf | COVERED |
| FR-009 (same config source) | Plan notes existing CORS_ORIGINS env var | COVERED |

### Drift Check: Success Criteria Testability

| Spec SC | Plan Test Coverage | Status |
|---------|-------------------|--------|
| SC-001 (100% allowed origin success) | Integration: valid origin test | COVERED |
| SC-002 (no wildcard in responses) | Unit: HCL parse for wildcard | COVERED |
| SC-003 (0% unauthorized origin data) | Integration: evil origin GET test | COVERED |
| SC-004 (four test layers) | Unit + Integration + E2E + Playwright (implicit) | COVERED |
| SC-005 (zero downtime) | Deployment plan: atomic redeployment | COVERED |

### Finding AR2-01: LOW - Spec FR-003 Inconsistency with User Story 3

**Issue**: The original FR-003 says "response MUST omit Access-Control-Allow-Origin" for unauthorized origins, but the amended FR-003 says "system echoes the requesting origin header verbatim." These are contradictory. User Story 3 acceptance scenario 1 expects the response does NOT include the evil origin, but the plan correctly notes that MOCK integrations echo ALL origins.

**Resolution**: The amended FR-003 supersedes the original. User Story 3 acceptance scenarios need updating to reflect reality: OPTIONS will echo ANY origin, but the actual data response (from Lambda) will block unauthorized origins. The browser blocks the data, not the preflight.

**Self-resolved**: Updated understanding. No spec change needed because the Amended Requirements section in AR1 already overrides the original FR-003. User Story 3 should be read in context of the amendment. However, for clarity, a note should be added to the spec.

### Finding AR2-02: LOW - Plan Discovers Secondary Bug Not in Spec

**Issue**: The plan identifies that `proxy_options` and `root_options` are MISSING `Access-Control-Allow-Credentials: true`. This is a bug not mentioned in the original spec (which only discussed the wildcard). The plan correctly includes the fix (Changes 2, 3, 5), but this should be documented in the spec as an additional finding.

**Resolution**: This is a bonus fix discovered during planning. It's already in the plan and doesn't change scope significantly. No spec update needed -- the plan supersedes.

### Finding AR2-03: LOW - Test Strategy Missing Vary Header Verification

**Issue**: FR-007 (amended to MUST) requires `Vary: Origin`. The unit test strategy mentions asserting `Vary` header is declared, but the integration test strategy doesn't include a Vary header assertion.

**Resolution**: Add Vary header check to integration test strategy. Minor addition.

### Summary

| Finding  | Severity | Status   |
|----------|----------|----------|
| AR2-01   | LOW      | RESOLVED - amended FR-003 already supersedes; consistent when read with AR1 |
| AR2-02   | LOW      | RESOLVED - bonus fix already in plan; no scope change |
| AR2-03   | LOW      | RESOLVED - will add Vary check to integration tests in tasks |

**Verdict**: No drift between spec and plan. All FRs traceable. All SCs testable. Minor inconsistency in User Story 3 vs amended FR-003 is adequately addressed by the AR1 amendments section. Plan is ready for task generation.
