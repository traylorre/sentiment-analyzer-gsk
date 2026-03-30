# CORS Deployment Verification Results

**Date**: 2026-03-29
**Verified by**: Claude Code (automated analysis)

## 1. CORS PRs — All Merged to Main

| PR | Feature | Merged | Commit |
|----|---------|--------|--------|
| #832 | 1269: Populate prod CORS origins + terraform guard | 2026-03-29 01:08 | 2bcc69a |
| #833 | 1267: Replace wildcard origin with echoing | 2026-03-29 01:08 | d606175 |
| #834 | 1268: Add CORS headers to env-gated 404s | 2026-03-28 23:19 | b6ce9fa |

## 2. Preprod Verification

**Status**: CORS fixes are on main. Preprod auto-deploys on push to main via `deploy.yml`.

**Credential requirements** (FR-005):
- `PREPROD_FRONTEND_URL` env var (from Amplify deployment output)
- AWS credentials with preprod access
- `gh` CLI authenticated

**Existing automated verification**:
- `test-preprod` job in `deploy.yml` runs `sanity.spec.ts` and `auth.spec.ts` against deployed preprod
- These tests make credentialed API calls (`credentials: 'include'`) which implicitly verify CORS
- If CORS is broken, API calls fail → dashboard shows empty state → tests fail

**Manual verification**: Not performed (requires live preprod access).

## 3. Production Blockers

| Blocker | File | Current State | Required Change |
|---------|------|---------------|----------------|
| Amplify not enabled | `infrastructure/terraform/prod.tfvars` | No `enable_amplify = true` | Add `enable_amplify = true` and `amplify_github_repository` |
| CORS origins incomplete | `infrastructure/terraform/prod.tfvars` | Only `traylorre.github.io` | Add Amplify production URL after enabling |
| Deploy pipeline disabled | `.github/workflows/deploy.yml` | `if: false` on prod jobs | Remove `if: false` from `build-sse-image-prod`, `deploy-prod`, `test-prod`, `canary` |
| Amplify app ID unknown | — | Not created yet | Run `terraform plan -var-file=prod.tfvars` after enabling to get app ID |

**Production deployment sequence**:
1. Enable Amplify in `prod.tfvars`
2. Run terraform plan → get Amplify production URL
3. Add Amplify URL to `cors_allowed_origins` in `prod.tfvars`
4. Re-enable production jobs in `deploy.yml`
5. Merge to main → pipeline deploys prod → `test-prod` verifies CORS

## 4. CORS Test Coverage

| Test File | Tests | What It Verifies |
|-----------|-------|-----------------|
| `cors-headers.spec.ts` | ~8 | Browser credentialed fetch, CORS header values |
| `cors-prod.spec.ts` | ~4 | Production CORS (skips if no PROD_AMPLIFY_URL) |
| `cors-env-gated-404.spec.ts` | ~3 | CORS on env-gated 404 responses |
| `sanity.spec.ts` | ~15 | Implicit CORS via full dashboard flow |

Total: ~30 tests exercise CORS either directly or implicitly.
