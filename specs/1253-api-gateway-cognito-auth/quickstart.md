# Quickstart: Feature 1253 — API Gateway Cognito Auth

## Implementation Phases

### Phase 1: API Gateway Module (modules/api_gateway/)
1. Add `public_routes` variable to `variables.tf`
2. Create intermediate resources via `for_each` (including FR-012 endpoints)
3. Create leaf/proxy resources with `ANY` + `OPTIONS` methods
4. Add CORS to 401/403 Gateway Responses
5. Add ACCESS_DENIED gateway response (doesn't exist yet)
6. `terraform plan` — expect ~85 new resources, 2 modified

### Phase 2: Wire in main.tf
7. Set `enable_cognito_auth = true`
8. Set `cognito_user_pool_arn = module.cognito.user_pool_arn`
9. Pass `public_routes` list with all 11+2 route configs
10. `terraform plan` — verify same count

### Phase 3: Amplify URL Switch (modules/amplify/)
11. Add `api_gateway_url` variable
12. Change `NEXT_PUBLIC_API_URL` from Lambda URL to API Gateway URL
13. Wire `module.api_gateway.api_endpoint` in main.tf
14. Add `module.api_gateway` to Amplify's `depends_on`

### Phase 4: Deploy Pipeline
15. Add API Gateway health check to deploy.yml smoke tests
16. Keep Lambda direct-invoke as secondary

### Phase 5: Tests
17. Unit tests: Terraform plan validation, mock auth responses
18. E2E tests: Protected endpoint 401, public endpoint 200, CORS on 401, OPTIONS 200

## Verification

```bash
# Protected endpoint → 401
curl -s -o /dev/null -w "%{http_code}" https://{gw}/v1/api/v2/configurations
# Expected: 401

# Public endpoint → 200
curl -s -o /dev/null -w "%{http_code}" https://{gw}/v1/health
# Expected: 200

# 401 has CORS headers
curl -sD- https://{gw}/v1/api/v2/configurations 2>&1 | grep -i access-control
# Expected: Allow-Origin, Allow-Credentials

# FR-012: /notifications still works with JWT
curl -s -H "Authorization: Bearer {jwt}" https://{gw}/v1/api/v2/notifications
# Expected: 200

# FR-012: /auth/magic-link still works without JWT
curl -s -X POST https://{gw}/v1/api/v2/auth/magic-link -d '{"email":"test@test.com"}'
# Expected: 200
```

## Rollback

Set `enable_cognito_auth = false` + revert Amplify URL. Single `terraform apply`. Public overrides become harmless (NONE auth like everything else).
