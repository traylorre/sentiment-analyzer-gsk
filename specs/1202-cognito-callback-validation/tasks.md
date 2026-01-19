# Tasks: Cognito Callback URL Validation

**Feature**: 1202-cognito-callback-validation
**Branch**: `1202-cognito-callback-validation`
**Generated**: 2026-01-18
**Total Tasks**: 5

## Overview

This feature adds Terraform outputs to expose Cognito OAuth callback and logout URLs. The implementation is minimal (2 files, ~20 lines) and satisfies all three user stories with a single change set.

## User Story Mapping

| Story | Priority | Implementation Scope |
|-------|----------|---------------------|
| US1 - Engineer Verification | P1 | T002-T004 (all outputs) |
| US2 - CI Pipeline Validation | P2 | Enabled by US1 (no additional tasks) |
| US3 - Developer Troubleshooting | P3 | Enabled by US1 (no additional tasks) |

**Note**: All user stories are satisfied by the same implementation. US2 and US3 are use cases of the outputs created in US1.

---

## Phase 1: Setup

- [x] T001 Verify current Cognito module outputs structure in `infrastructure/terraform/modules/cognito/outputs.tf`

---

## Phase 2: Implementation (US1 - Engineer Verification)

**Goal**: Add Terraform outputs to expose Cognito callback and logout URLs

**Independent Test**: Run `terraform output cognito_callback_urls` and verify list is returned

### Module Outputs

- [x] T002 [US1] Add `callback_urls` output to `infrastructure/terraform/modules/cognito/outputs.tf`
- [x] T003 [P] [US1] Add `logout_urls` output to `infrastructure/terraform/modules/cognito/outputs.tf`

### Root Outputs

- [x] T004 [US1] Add `cognito_callback_urls` and `cognito_logout_urls` outputs to `infrastructure/terraform/main.tf`

---

## Phase 3: Verification

- [x] T005 Run `terraform plan` to verify no unexpected changes and outputs are defined correctly

---

## Dependencies

```
T001 (Setup)
  └── T002 (callback_urls output)
        └── T003 [P] (logout_urls output - can parallel with T002)
              └── T004 (root outputs - depends on module outputs)
                    └── T005 (verification)
```

## Parallel Execution

Tasks T002 and T003 can be executed in parallel as they modify the same file but are independent output definitions.

## Implementation Details

### T002: Add callback_urls output

**File**: `infrastructure/terraform/modules/cognito/outputs.tf`

```hcl
output "callback_urls" {
  description = "Configured callback URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.callback_urls
}
```

### T003: Add logout_urls output

**File**: `infrastructure/terraform/modules/cognito/outputs.tf`

```hcl
output "logout_urls" {
  description = "Configured logout URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.logout_urls
}
```

### T004: Add root outputs

**File**: `infrastructure/terraform/main.tf` (after existing Cognito outputs section)

```hcl
output "cognito_callback_urls" {
  description = "Cognito OAuth callback URLs (Terraform-configured values)"
  value       = module.cognito.callback_urls
}

output "cognito_logout_urls" {
  description = "Cognito OAuth logout URLs (Terraform-configured values)"
  value       = module.cognito.logout_urls
}
```

## MVP Scope

**Suggested MVP**: All tasks (T001-T005) - this is already minimal scope.

## Acceptance Criteria Verification

After implementation:

```bash
# Verify outputs exist
terraform output cognito_callback_urls
terraform output cognito_logout_urls

# Expected: List of URLs including Amplify domain
```
