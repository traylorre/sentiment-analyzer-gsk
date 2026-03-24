# Quickstart: Feature 1253 — API Gateway Cognito Auth

## Prerequisites

- Terraform 1.5+ installed
- AWS credentials configured for the target environment
- Cognito User Pool deployed (`module.cognito` exists)
- API Gateway deployed (`module.api_gateway` exists)

## Implementation Order

### Phase 1: API Gateway Module Changes

1. **Add `public_routes` variable** to `modules/api_gateway/variables.tf`
2. **Create intermediate + leaf resources** using `for_each` in `modules/api_gateway/main.tf`
3. **Add CORS to Gateway Responses** (401 UNAUTHORIZED, MISSING_AUTH_TOKEN, 403 ACCESS_DENIED)
4. **Verify with `terraform plan`** — expect ~77 new resources, 2 modified

### Phase 2: Wire Module in main.tf

5. **Add `enable_cognito_auth = true`** to `module "api_gateway"` block
6. **Add `cognito_user_pool_arn = module.cognito.user_pool_arn`**
7. **Add `public_routes` list** with all 10 route groups
8. **Verify with `terraform plan`** — should show same resource count

### Phase 3: Amplify URL Switch

9. **Add `api_gateway_url` variable** to `modules/amplify/variables.tf`
10. **Change `NEXT_PUBLIC_API_URL`** from `var.dashboard_lambda_url` to `var.api_gateway_url`
11. **Pass `module.api_gateway.api_endpoint`** from main.tf to Amplify module

### Phase 4: Deploy Pipeline

12. **Add API Gateway smoke test** to `deploy.yml`
13. **Keep Lambda Function URL smoke test** as secondary (until Feature 1256)

### Phase 5: Tests

14. **Unit tests**: Terraform plan validation, auth behavior assertions
15. **E2E tests**: Protected endpoint 401, public endpoint 200, CORS on 401

## Verification

```bash
# After terraform apply:

# 1. Protected endpoint without token → 401
curl -s -o /dev/null -w "%{http_code}" https://{api_gw_url}/v1/api/v2/configurations
# Expected: 401

# 2. Public endpoint without token → 200
curl -s -o /dev/null -w "%{http_code}" https://{api_gw_url}/v1/health
# Expected: 200

# 3. 401 response has CORS headers
curl -s -D- https://{api_gw_url}/v1/api/v2/configurations 2>&1 | grep -i 'access-control'
# Expected: Access-Control-Allow-Origin, Access-Control-Allow-Credentials

# 4. Amplify env var points to API Gateway
# Check in Amplify console or via Terraform output
```

## Rollback

Set `enable_cognito_auth = false` in main.tf and run `terraform apply`. This:
- Removes the Cognito authorizer (conditional `count = 0`)
- Reverts `{proxy+}` to `authorization = "NONE"`
- Public route overrides remain harmless (they just have `NONE` auth like everything else)
- Amplify URL change requires separate revert (change back to `dashboard_lambda_url`)

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Partial deployment breaks /health | FR-007: Atomic deployment (single terraform apply) |
| 401 not visible to frontend | FR-008: CORS on Gateway Responses |
| All tokens rejected | FR-009: No scope validation (signature + expiry only) |
| Stage prefix missing | FR-010: Amplify URL includes `/v1` |
