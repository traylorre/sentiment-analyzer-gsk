# Tasks: CloudFront + WAF for SSE Streaming

**Input**: Design documents from `/specs/1255-cloudfront-sse-waf/`
**Tests**: Included — E2E SSE connection tests.

---

## Phase 1: Setup

- [x] T001 Create CloudFront module at `infrastructure/terraform/modules/cloudfront_sse/`
- [x] T002 [P] Create `infrastructure/terraform/modules/cloudfront_sse/variables.tf` — origin_url, waf_web_acl_arn, price_class, origin_read_timeout, environment, tags
- [x] T003 [P] Create `infrastructure/terraform/modules/cloudfront_sse/outputs.tf` — distribution_url, distribution_arn, distribution_id

---

## Phase 2: Foundational — CloudFront Distribution

- [x] T004 Create CloudFront distribution in `infrastructure/terraform/modules/cloudfront_sse/main.tf` — SSE Lambda Function URL as custom HTTPS origin, PriceClass_100, HTTP/2
- [x] T005 [P] Configure origin with 180s read timeout, 60s keepalive, HTTPS-only origin protocol
- [x] T006 [P] Set default cache behavior — CachingDisabled managed policy (FR-002), AllowedMethods GET/HEAD/OPTIONS
- [x] T007 Create custom Origin Request Policy in `infrastructure/terraform/modules/cloudfront_sse/main.tf` — forward Authorization, Origin, Last-Event-ID, X-User-ID, X-Amzn-Trace-Id headers (FR-004)
- [x] T008 Associate WAF WebACL ARN with distribution via `web_acl_id` parameter (FR-005)

**Checkpoint**: `terraform validate` on module.

---

## Phase 3: User Story 1 — SSE Routes Through CloudFront (Priority: P1) MVP

- [x] T009 [US1] Wire CloudFront module in `infrastructure/terraform/main.tf` — pass `module.sse_streaming_lambda.function_url` as origin
- [x] T010 [US1] Wire WAF module (CLOUDFRONT scope) in `infrastructure/terraform/main.tf` — `scope = "CLOUDFRONT"`, pass CloudFront distribution ARN
- [ ] T011 [US1] Run `terraform plan` — verify CloudFront distribution, WAF, and association

---

## Phase 4: User Story 3 — Frontend Uses CloudFront URL (Priority: P1)

- [x] T012 [US3] Update `NEXT_PUBLIC_SSE_URL` in Amplify module to use CloudFront URL — change `var.sse_lambda_url` to `var.sse_cloudfront_url` in `infrastructure/terraform/modules/amplify/main.tf`
- [x] T013 [US3] Add `sse_cloudfront_url` variable to `infrastructure/terraform/modules/amplify/variables.tf`
- [x] T014 [US3] Pass `module.cloudfront_sse.distribution_url` to Amplify module in `infrastructure/terraform/main.tf` (FR-007, FR-011)
- [ ] T015 [US3] Verify `terraform plan` shows Amplify SSE URL change

---

## Phase 5: User Story 2 — WAF Protects SSE (Priority: P1)

- [x] T016 [US2] Verify WAF CLOUDFRONT WebACL has rate-based + managed rules in `terraform plan`
- [x] T017 [P] [US2] Create E2E test `tests/e2e/test_cloudfront_sse.py` — SSE connection via CloudFront, WAF block on SQLi, normal traffic passes

---

## Phase 6: User Story 4 — No Caching (Priority: P1)

- [x] T018 [US4] Verify CachingDisabled policy in CloudFront default behavior in `terraform plan`

---

## Phase 7: Polish

- [ ] T019 [P] Run `terraform plan` full validation
- [ ] T020 [P] Run existing SSE E2E tests to verify zero regression
- [ ] T021 Update checkov baseline if needed
- [ ] T022 Run `terraform apply` and verify SSE via CloudFront URL
- [ ] T023 Verify security zone map accuracy post-implementation

---

## Dependencies

- Phase 1-2: Independent (module creation)
- Phase 3: Depends on Phase 2 (CloudFront must exist)
- Phase 4: Depends on Phase 3 (need CloudFront URL output)
- Phase 5: Depends on Phase 3 (WAF associated with CloudFront)
- Phase 6: Part of Phase 2 (cache behavior set during creation)
- Phase 7: All previous

## Notes

- ~20 new Terraform resources
- Cost: ~$11/month (CloudFront + WAF CLOUDFRONT)
- Two independent WAF WebACLs: REGIONAL (API GW) + CLOUDFRONT (SSE)
- 180s CloudFront timeout < 900s Lambda — frontend reconnect handles this
- Lambda Function URL still directly accessible until Feature 1256
