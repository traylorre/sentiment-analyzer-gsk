# Tasks: Next.js Frontend Migration via AWS Amplify SSR (Feature 1105)

## Overview

Deploy the existing Next.js frontend (`/frontend/`) via AWS Amplify SSR, replacing the broken vanilla JS dashboard.

**Revised**: Original plan (static export) was impossible due to middleware/auth dependencies. Now using Amplify SSR.

---

## Phase 1: Create Amplify Terraform Module

- [x] **1.1** Create module directory structure
  ```bash
  mkdir -p infrastructure/terraform/modules/amplify
  ```

- [x] **1.2** Create `modules/amplify/variables.tf`
  ```hcl
  variable "environment" { type = string }
  variable "github_repository" { type = string }
  variable "github_access_token" { type = string, sensitive = true }
  variable "api_gateway_url" { type = string }
  variable "sse_lambda_url" { type = string }
  variable "cognito_user_pool_id" { type = string }
  variable "cognito_client_id" { type = string }
  variable "cognito_domain" { type = string }
  ```

- [x] **1.3** Create `modules/amplify/iam.tf`
  - IAM role for Amplify service
  - Policy attachment: `AdministratorAccess-Amplify`

- [x] **1.4** Create `modules/amplify/main.tf`
  - `aws_amplify_app` resource with:
    - `platform = "WEB_COMPUTE"` (SSR mode)
    - Build spec for monorepo (`appRoot: frontend`)
    - Environment variables from inputs
  - `aws_amplify_branch` for main branch

- [x] **1.5** Create `modules/amplify/outputs.tf`
  ```hcl
  output "app_id" { value = aws_amplify_app.frontend.id }
  output "default_domain" { value = aws_amplify_app.frontend.default_domain }
  output "branch_domain" { value = aws_amplify_branch.main.branch_name }
  ```

- [x] **1.6** Validate module locally
  ```bash
  cd infrastructure/terraform/modules/amplify
  terraform fmt
  terraform validate
  ```

---

## Phase 2: GitHub Token Setup

- [ ] **2.1** Create GitHub Personal Access Token
  - Go to GitHub → Settings → Developer settings → Personal access tokens
  - Create token with `repo` scope
  - Note: Fine-grained tokens also work if repository is specified

- [ ] **2.2** Add token to GitHub Secrets
  - Repository → Settings → Secrets and variables → Actions
  - Add `AMPLIFY_GITHUB_TOKEN` secret

- [x] **2.3** Add token to Terraform variables
  - Add to `infrastructure/terraform/variables.tf`:
    ```hcl
    variable "github_token" {
      description = "GitHub PAT for Amplify"
      type        = string
      sensitive   = true
    }
    ```
  - Add to `preprod.tfvars`:
    ```hcl
    # Passed via environment: TF_VAR_github_token
    ```

---

## Phase 3: Integrate Amplify Module

- [x] **3.1** Add module to `infrastructure/terraform/main.tf`
  ```hcl
  module "amplify_frontend" {
    source = "./modules/amplify"
    # ... variables ...
  }
  ```

- [x] **3.2** Add Amplify outputs to `main.tf`
  - `amplify_app_id`
  - `amplify_default_domain`
  - `amplify_production_url`

- [ ] **3.3** Run Terraform plan
  ```bash
  cd infrastructure/terraform
  terraform init
  terraform plan -var-file=preprod.tfvars
  ```

- [ ] **3.4** Apply Terraform
  ```bash
  terraform apply -var-file=preprod.tfvars
  ```

- [ ] **3.5** Verify Amplify app created in AWS Console
  - Navigate to AWS Amplify → Apps
  - Confirm app exists and is connected to GitHub

---

## Phase 4: Trigger Initial Build

- [ ] **4.1** Verify Amplify detected Next.js
  - Check Amplify Console → App settings → Build settings
  - Confirm framework: "Next.js - SSR"

- [ ] **4.2** Trigger manual build (if auto-build not triggered)
  ```bash
  aws amplify start-job \
    --app-id $(terraform output -raw amplify_app_id) \
    --branch-name main \
    --job-type RELEASE
  ```

- [ ] **4.3** Monitor build logs
  - Amplify Console → App → main branch → Build logs
  - Verify all phases complete successfully

- [ ] **4.4** Note the Amplify URL
  - Format: `https://main.{app-id}.amplifyapp.com`
  - Save for testing

---

## Phase 5: Verification Testing

- [ ] **5.1** Test basic page load
  ```bash
  curl -s https://main.{app-id}.amplifyapp.com/ | grep -q "Sentiment" && echo "PASS"
  ```

- [ ] **5.2** Test OHLC chart pan
  - Navigate to dashboard
  - Select AAPL ticker
  - Select daily (D) resolution
  - Pan left/right → verify chart scrolls

- [ ] **5.3** Test gap visualization
  - View daily chart spanning a weekend
  - Verify red shading appears for Saturday/Sunday

- [ ] **5.4** Test auth middleware
  - Navigate to protected route (e.g., /settings)
  - Verify redirect to /auth/signin

- [ ] **5.5** Test magic link flow
  - Request magic link
  - Click link → verify token extracted and verified

- [ ] **5.6** Test SSE streaming
  - Open dashboard
  - Verify real-time updates (heartbeat, new items)

- [ ] **5.7** Test all API endpoints
  - `/api/v2/sentiment`
  - `/api/v2/tickers/AAPL/ohlc`
  - `/api/v2/configurations`
  - `/health`

---

## Phase 6: Update CI/CD (Optional)

- [ ] **6.1** Add frontend build validation to deploy.yml
  ```yaml
  validate-frontend:
    name: Validate Next.js Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd frontend && npm ci && npm run build
  ```

- [ ] **6.2** Remove S3 sync step (after Amplify verified)
  - Comment out or delete the `aws s3 sync ../../src/dashboard/` step

---

## Phase 7: Clean Up Legacy Code (After Stable)

- [ ] **7.1** Delete `/src/dashboard/` directory
  ```bash
  rm -rf src/dashboard/
  git add -A
  git commit -m "chore: Remove legacy vanilla JS dashboard (Feature 1105)"
  ```

- [ ] **7.2** Remove static file routes from `handler.py` (optional)
  - Delete routes: `GET /`, `GET /favicon.ico`, `GET /static/*`, `GET /chaos`
  - Delete `ALLOWED_STATIC_FILES` dict
  - Delete `serve_static_file()` function

- [ ] **7.3** Update CloudFront to remove S3 origin
  - Remove `s3-dashboard` origin from CloudFront module
  - Keep `api-gateway` and `sse-lambda` origins

- [ ] **7.4** Update documentation
  - README.md: Update frontend URL
  - CLAUDE.md: Remove /src/dashboard/ references

---

## Verification Checklist

### Amplify Deployment
- [ ] Amplify app created via Terraform
- [ ] GitHub integration working
- [ ] Auto-build on push to main
- [ ] Build completes successfully

### Frontend Features
- [ ] OHLC chart renders
- [ ] Pan/scroll works on all resolutions
- [ ] Gap visualization (red shading) works
- [ ] Resolution selector works
- [ ] Sentiment overlay works

### Authentication
- [ ] Middleware redirects work
- [ ] Anonymous session creation works
- [ ] Magic link verification works
- [ ] Protected routes enforce auth

### Real-time Updates
- [ ] SSE connection established
- [ ] Heartbeat events received
- [ ] New sentiment items appear

### API Integration
- [ ] All /api/v2/* endpoints accessible
- [ ] CORS headers correct
- [ ] Rate limiting works

---

## Rollback Procedure

If critical issues occur:

1. **Disable auto-build**:
   ```bash
   aws amplify update-branch \
     --app-id $(terraform output -raw amplify_app_id) \
     --branch-name main \
     --enable-auto-build false
   ```

2. **Users fall back to CloudFront + S3** (vanilla JS still deployed)

3. **Investigate** Amplify build logs

4. **Fix forward** - do not permanently revert to vanilla JS

---

## Definition of Done

- [ ] Amplify serves Next.js frontend
- [ ] OHLC chart pan works on all resolutions
- [ ] Gap visualization appears
- [ ] Auth flows work (middleware, magic links)
- [ ] SSE streaming works
- [ ] Amplify auto-builds on push
- [ ] `/src/dashboard/` deleted (Phase 7)
- [ ] Documentation updated
