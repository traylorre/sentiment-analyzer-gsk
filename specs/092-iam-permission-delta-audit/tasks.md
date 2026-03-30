# Feature 092: Implementation Tasks

**Status**: Ready
**Created**: 2025-12-11
**Plan**: [plan.md](./plan.md)

---

## Task Execution Order

Tasks are ordered by dependency. Execute sequentially unless marked as parallelizable.

---

## Phase 1: Template Repo - Validator Enhancements

### T001: Add CloudFront and FIS service mappings

- **File**: `src/validators/iam_resource_alignment.py`
- **Action**: Add to `SERVICE_TO_TERRAFORM` dict:
  ```python
  "cloudfront": {
      "distribution": ["aws_cloudfront_distribution"],
      "response-headers-policy": ["aws_cloudfront_response_headers_policy"],
  },
  "fis": {
      "experiment-template": ["aws_fis_experiment_template"],
  },
  ```
- **Depends**: None
- **Acceptance**: Dict contains new service mappings

---

### T002: Create backend bucket extraction method

- **File**: `src/validators/iam_resource_alignment.py`
- **Action**: Add method `_extract_backend_buckets(self, repo_path: Path) -> list[tuple[str, str]]`
  - Glob for `**/backend*.hcl` and `**/backend.tf`
  - Regex extract `bucket = "..."` values
  - Return list of `(file_path, bucket_name)` tuples
- **Depends**: None
- **Acceptance**: Method returns bucket names from test fixtures

---

### T003: Create tag condition extraction method

- **File**: `src/validators/iam_resource_alignment.py`
- **Action**: Add method `_extract_tag_conditions(self, content: str) -> dict[str, dict[str, str]]`
  - Parse `Condition { StringLike { "aws:ResourceTag/Name" = ["pattern"] }}`
  - Return `{service: {tag_key: pattern}}`
- **Depends**: None
- **Acceptance**: Method extracts tag conditions from IAM policy content

---

### T004: Extend validate() to check backend buckets

- **File**: `src/validators/iam_resource_alignment.py`
- **Action**: In `validate()`:
  1. Call `_extract_backend_buckets()`
  2. For each bucket, check against S3 ARN patterns
  3. Add `ALIGN-003` finding if no pattern matches
- **Depends**: T002
- **Acceptance**: Validator reports ALIGN-003 for mismatched backend buckets

---

### T005: Extend validate() to check resource tags

- **File**: `src/validators/iam_resource_alignment.py`
- **Action**: In `validate()`:
  1. Call `_extract_tag_conditions()` on IAM policies
  2. For each Terraform resource, check `tags` block
  3. Add `ALIGN-004` if required tag missing
  4. Add `ALIGN-005` if tag value doesn't match pattern
- **Depends**: T001, T003
- **Acceptance**: Validator reports ALIGN-004/005 for tag mismatches

---

### T006: Create test fixtures for backend mismatch

- **File**: `tests/fixtures/validators/backend-mismatch/`
- **Action**: Create:
  - `backend-preprod.hcl` with bucket `legacy-bucket-name`
  - `ci-policy.tf` with S3 pattern `*-new-pattern-*`
- **Depends**: None (parallelizable with T001-T003)
- **Acceptance**: Fixtures exist with mismatched patterns

---

### T007: Create test fixtures for tag condition mismatch

- **File**: `tests/fixtures/validators/tag-condition-mismatch/`
- **Action**: Create:
  - `cloudfront.tf` with distribution missing `Name` tag
  - `ci-policy.tf` with `aws:ResourceTag/Name` condition
- **Depends**: None (parallelizable with T001-T003)
- **Acceptance**: Fixtures exist with missing tags

---

### T008: Add unit tests for backend validation

- **File**: `tests/unit/test_iam_resource_alignment.py`
- **Action**: Add tests:
  - `test_extract_backend_buckets_from_hcl()`
  - `test_backend_bucket_mismatch_detected()`
  - `test_backend_bucket_match_passes()`
- **Depends**: T004, T006
- **Acceptance**: All tests pass

---

### T009: Add unit tests for tag validation

- **File**: `tests/unit/test_iam_resource_alignment.py`
- **Action**: Add tests:
  - `test_extract_tag_conditions()`
  - `test_missing_name_tag_detected()`
  - `test_tag_pattern_mismatch_detected()`
  - `test_tag_match_passes()`
- **Depends**: T005, T007
- **Acceptance**: All tests pass

---

## Phase 2: Target Repo - Operational Fixes

### T010: Fix S3 state bucket policy pattern

- **File**: `infrastructure/terraform/ci-user-policy.tf` (target repo)
- **Action**: Update lines 831-834:
  ```hcl
  resources = [
    "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
    "arn:aws:s3:::sentiment-analyzer-terraform-state-*/*"
  ]
  ```
- **Depends**: None (parallelizable with Phase 1)
- **Acceptance**: S3 TFState statement allows actual bucket name

---

### T011: Add Name tag to CloudFront distribution

- **File**: `modules/cloudfront/main.tf` (target repo)
- **Action**: Find `aws_cloudfront_distribution`, add to tags:
  ```hcl
  Name = "${var.environment}-sentiment-dashboard"
  ```
- **Depends**: None
- **Acceptance**: CloudFront distribution has Name tag

---

### T012: Add Name tags to FIS resources

- **File**: `modules/chaos/main.tf` (target repo)
- **Action**: Add Name tags to:
  - FIS execution IAM role: `${var.environment}-sentiment-fis-execution`
  - FIS CloudWatch log group: `${var.environment}-sentiment-fis-logs`
- **Depends**: None
- **Acceptance**: FIS resources have Name tags

---

## Phase 3: Documentation

### T013: Create IAM migration guide

- **File**: `docs/iam-migration.md` (template repo)
- **Action**: Document:
  1. Overview of naming convention migration
  2. CI user rename procedure (manual bootstrap)
  3. Pre-flight checklist
  4. Rollback procedure
  5. Validation commands
- **Depends**: T010-T012 (informed by operational fixes)
- **Acceptance**: Guide covers all bootstrap steps

---

## Phase 4: Integration

### T014: Run validator on target repo

- **Action**: Execute:
  ```bash
  python scripts/validate-runner.py --repo /path/to/sentiment-analyzer-gsk --validator iam-resource-alignment
  ```
- **Depends**: T008, T009, T010, T011, T012
- **Acceptance**: Zero findings (all mismatches fixed)

---

### T015: Run full validation suite

- **Action**: Execute `make validate` on both repos
- **Depends**: T014
- **Acceptance**: All validators pass

---

## Summary

| Phase   | Tasks     | Parallelizable       |
| ------- | --------- | -------------------- |
| Phase 1 | T001-T009 | T001-T003, T006-T007 |
| Phase 2 | T010-T012 | All                  |
| Phase 3 | T013      | After T010-T012      |
| Phase 4 | T014-T015 | Sequential           |

**Total Tasks**: 15
**Critical Path**: T001 → T005 → T009 → T014 → T015
