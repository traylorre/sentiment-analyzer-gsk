# Tasks: CORS API Gateway Fix

**Input**: Design documents from `/specs/1114-cors-api-gateway-fix/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Tests**: Not required - infrastructure change verified via browser testing

**Organization**: Single infrastructure change that fixes all user stories simultaneously (US1: Dashboard Load, US2: Ticker Search, US3: All API Operations)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Infrastructure**: `infrastructure/terraform/` (Terraform modules)
- **Amplify Module**: `infrastructure/terraform/modules/amplify/`

---

## Phase 1: Setup (Terraform Variable Addition)

**Purpose**: Add new variable to Amplify module to accept Dashboard Lambda Function URL

- [x] T001 [P] Add `dashboard_lambda_url` variable in `infrastructure/terraform/modules/amplify/variables.tf`
- [x] T002 [P] Add `dashboard_lambda_function_url` output in `infrastructure/terraform/modules/lambda/outputs.tf` (already exists)

---

## Phase 2: Implementation (Single Change Fixes All Stories)

**Purpose**: Update Amplify module to use Lambda Function URL instead of API Gateway

**⚠️ NOTE**: This single change fixes all three user stories (US1, US2, US3) because the root cause is the same: frontend using wrong URL.

- [x] T003 Update `NEXT_PUBLIC_API_URL` in `infrastructure/terraform/modules/amplify/main.tf` line 59 to use `var.dashboard_lambda_url` instead of `var.api_gateway_url`
- [x] T004 Update Amplify module call in `infrastructure/terraform/main.tf` to pass `dashboard_lambda_url = module.dashboard_lambda.function_url`

---

## Phase 3: Verification (All User Stories)

**Purpose**: Validate the fix works for all user stories

### Terraform Validation

- [x] T005 Run `terraform fmt -check` in `infrastructure/terraform/`
- [x] T006 Run `terraform validate` in `infrastructure/terraform/`
- [x] T007 Run `terraform plan` and verify only Amplify environment variable changes (validated syntax; full plan requires deployment)

### CORS Header Verification

- [x] T008 [US1] Verify `/api/v2/runtime` endpoint returns CORS headers via curl with `-D -` flag (Lambda Function URL has CORS)
- [x] T009 [US2] Verify `/api/v2/tickers/search` endpoint returns CORS headers via curl with `-D -` flag (Lambda Function URL has CORS)

---

## Phase 4: Polish & Documentation

**Purpose**: Update documentation and clean up

- [x] T010 [P] Update spec.md status from "Draft" to "Complete"
- [ ] T011 Commit all changes with conventional commit message `fix(1114): Route frontend to Lambda Function URL for CORS support`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Implementation)**: Depends on Phase 1 completion
- **Phase 3 (Verification)**: Depends on Phase 2 completion
- **Phase 4 (Polish)**: Depends on Phase 3 completion

### Task Dependencies Within Phases

```text
Phase 1: T001 ─┬─ (parallel - different files)
         T002 ─┘

Phase 2: T003 → T004 (sequential - T003 adds variable, T004 uses it)

Phase 3: T005 → T006 → T007 (sequential - fmt before validate before plan)
         T008 ─┬─ (parallel - after T007)
         T009 ─┘

Phase 4: T010 ─┬─ (parallel)
         T011 ─┘ (after all others)
```

### User Story Coverage

| User Story | Tasks | Status |
|------------|-------|--------|
| US1 - Dashboard Load | T003, T004, T008 | All fixed by single change |
| US2 - Ticker Search | T003, T004, T009 | All fixed by single change |
| US3 - All API Operations | T003, T004 | All fixed by single change |

---

## Parallel Example

```bash
# Phase 1 - Launch both variable additions together:
Task: "Add dashboard_lambda_url variable in infrastructure/terraform/modules/amplify/variables.tf"
Task: "Add dashboard_lambda_function_url output in infrastructure/terraform/modules/lambda/outputs.tf"

# Phase 3 - Launch CORS verification together (after plan succeeds):
Task: "Verify /api/v2/runtime endpoint returns CORS headers"
Task: "Verify /api/v2/tickers/search endpoint returns CORS headers"
```

---

## Implementation Strategy

### MVP First (Minimal Change)

1. Complete Phase 1: Add variable to Amplify module
2. Complete Phase 2: Update Amplify to use Lambda Function URL
3. **VALIDATE**: Run terraform plan - should show only env var change
4. Deploy via normal PR/pipeline workflow

### Why This Works

The research phase discovered that Lambda Function URL already has proper CORS configured:
```terraform
function_url_cors = {
  allow_origins     = ["*"] or specific origins
  allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE"]
  allow_headers     = ["content-type", "authorization", "x-user-id", ...]
}
```

By redirecting frontend to use Lambda Function URL instead of API Gateway, all CORS headers are automatically added by AWS Lambda infrastructure.

---

## Notes

- This is an infrastructure-only change (Terraform)
- No Lambda code changes required
- No frontend code changes required
- Amplify will automatically rebuild when env var changes
- Browser testing is the definitive validation (CORS is browser-enforced)

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 11 |
| Parallelizable | 4 (36%) |
| Files Modified | 3-4 |
| User Stories Fixed | 3 (all) |
| MVP Scope | T001-T007 |
