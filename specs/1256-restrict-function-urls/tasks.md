# Tasks: Restrict Lambda Function URLs

**Input**: Design documents from `/specs/1256-restrict-function-urls/`

---

## Phase 1: Setup

- [ ] T001 Check if Lambda module supports `function_url_auth_type` variable — if not, add it to `infrastructure/terraform/modules/lambda/variables.tf` with default "NONE"
- [ ] T002 Wire `function_url_auth_type` into Lambda Function URL resource in `infrastructure/terraform/modules/lambda/main.tf`

---

## Phase 2: User Story 1+2 — Dashboard Lambda (Priority: P1) MVP

- [ ] T003 [US1] Set `function_url_auth_type = "AWS_IAM"` on Dashboard Lambda module call in `infrastructure/terraform/main.tf`
- [ ] T004 [US2] Verify existing `aws_lambda_permission.api_gateway` is sufficient for API Gateway access (no change needed)
- [ ] T005 [US1] Run `terraform plan` — verify Dashboard Lambda Function URL auth type changes to AWS_IAM

---

## Phase 3: User Story 3 — SSE Lambda + CloudFront OAC (Priority: P1)

- [ ] T006 [US3] Set `function_url_auth_type = "AWS_IAM"` on SSE Streaming Lambda module call in `infrastructure/terraform/main.tf`
- [ ] T007 [US3] Add CloudFront OAC resource (`aws_cloudfront_origin_access_control`) in `infrastructure/terraform/modules/cloudfront_sse/main.tf`
- [ ] T008 [US3] Set `origin_access_control_id` on CloudFront distribution origin in `infrastructure/terraform/modules/cloudfront_sse/main.tf`
- [ ] T009 [US3] Add Lambda permission for CloudFront to invoke SSE Lambda via Function URL — `aws_lambda_permission` with `lambda:InvokeFunctionUrl` in `infrastructure/terraform/main.tf`
- [ ] T010 [US3] Run `terraform plan` — verify OAC, Lambda permission, and auth type change

---

## Phase 4: User Story 4 — Deploy Pipeline (Priority: P1)

- [ ] T011 [US4] Verify deploy.yml smoke test uses `aws lambda invoke` (direct invoke, not Function URL) — no changes needed
- [ ] T012 [US4] Verify deploy.yml API Gateway health check still works (Feature 1253 test)

---

## Phase 5: Tests

- [ ] T013 [P] Create E2E test `tests/e2e/test_function_url_restricted.py` — direct curl to Function URL → 403, API Gateway path → 200
- [ ] T014 Run `terraform plan` full validation
- [ ] T015 Run existing E2E tests — verify zero regression
- [ ] T016 Run `terraform apply` and verify (curl Function URLs → 403, API GW → 200, CloudFront SSE → 200)
- [ ] T017 Verify FINAL security zone map accuracy

---

## Dependencies

- Phase 1: Independent
- Phase 2: Depends on Phase 1 (auth type variable)
- Phase 3: Depends on Phase 1
- Phase 4: Verification only
- Phase 5: Depends on all previous

## Notes

- Smallest feature in the series: ~5 resource changes
- $0 additional cost
- Rollback: Set `function_url_auth_type = "NONE"` and apply
- FINAL feature — closes all security gaps in the hardening series
