# Validation Baseline: sentiment-analyzer-gsk

**Date**: 2025-12-08
**Target Repo**: `/home/traylorre/projects/sentiment-analyzer-gsk`
**Constitution Version**: 1.7
**Validator Version**: 0.1.0

## Summary

| Metric              | Value |
| ------------------- | ----- |
| Validators Run      | 13    |
| PASS                | 11    |
| FAIL                | 0     |
| SKIP                | 2     |
| SUPPRESSED Findings | 8     |

## Success Criteria Verification

| Criterion             | Status | Notes                                               |
| --------------------- | ------ | --------------------------------------------------- |
| SC-001 (Zero FAIL)    | PASS   | validators_failed: 0                                |
| SC-002 (Zero WARN)    | PASS   | 2 SKIPs are documented exemptions per Amendment 1.7 |
| SC-003 (PRs Merged)   | PASS   | Template PR #42, Target PR #303 both merged         |
| SC-004 (Clean output) | PASS   | All findings either PASS or SUPPRESSED              |

## Validator Results

### Passing Validators (11)

| Validator          | Duration | Findings           |
| ------------------ | -------- | ------------------ |
| security-validate  | 69.1s    | 0                  |
| iam-validate       | 0.6s     | 0                  |
| s3-iam-validate    | 0.6s     | 0                  |
| sns-iam-validate   | 0.6s     | 0                  |
| sqs-iam-validate   | 0.6s     | 3 (all SUPPRESSED) |
| lambda-iam         | 0.3s     | 5 (all SUPPRESSED) |
| cost-validate      | <0.1s    | 0                  |
| canonical-validate | 1.4s     | 0                  |
| format-validate    | <0.1s    | 0                  |
| bidirectional      | 0.2s     | 0                  |
| property           | 3.5s     | 0                  |

### Skipped Validators (2) - Amendment 1.7 Exemptions

| Validator      | Reason                                            |
| -------------- | ------------------------------------------------- |
| spec-coherence | `make test-spec` not available in target repo     |
| mutation       | `make test-mutation` not available in target repo |

These validators are skipped per Constitutional Amendment 1.7 (Target Repo Independence), which states that template methodology infrastructure MUST NOT be required in target repos.

## Suppressed Findings (8)

### SQS Validator (3 findings)

| ID      | File                                                         | Suppressed By          |
| ------- | ------------------------------------------------------------ | ---------------------- |
| SQS-009 | docs/iam-policies/dev-deployer-policy.json:115               | dev-preprod-sqs-delete |
| SQS-009 | infrastructure/terraform/ci-user-policy.tf:177               | ci-user-sqs-delete     |
| SQS-009 | infrastructure/iam-policies/preprod-deployer-policy.json:115 | dev-preprod-sqs-delete |

**Justification**: CI/CD pipelines require `sqs:DeleteQueue` permission to manage SQS resources during deployment lifecycle.

### Lambda Validator (5 findings)

| ID         | File                                                        | Suppressed By               |
| ---------- | ----------------------------------------------------------- | --------------------------- |
| LAMBDA-007 | infrastructure/terraform/ci-user-policy.tf:48               | lambda-cicd-deployment      |
| LAMBDA-011 | infrastructure/terraform/ci-user-policy.tf:71               | lambda-event-source-mapping |
| LAMBDA-007 | docs/iam-policies/dev-deployer-policy.json:37               | lambda-cicd-deployment      |
| LAMBDA-007 | infrastructure/iam-policies/prod-deployer-policy.json:35    | lambda-cicd-deployment      |
| LAMBDA-007 | infrastructure/iam-policies/preprod-deployer-policy.json:37 | lambda-cicd-deployment      |

**Justification**: CI/CD deployments require `lambda:CreateFunction + iam:PassRole` combinations for deploying Lambda functions with execution roles.

## Bidirectional Allowlist Summary

The target repo includes `bidirectional-allowlist.yaml` with:

- **18 spec-level suppressions** (BIDIR-001):

  - 5 vaporware specs (frontend/mobile UI for backend-only project)
  - 3 test-infrastructure specs (E2E testing methodology)
  - 10 infrastructure specs (JSON/Terraform where semantic matching fails per SC-005)

- **16 path-level suppressions** (BIDIR-002):
  - Pre-existing Lambda/lib code (predates spec-driven development)
  - Test fixtures and helpers
  - Terraform module files
  - Build/CI scripts

## Baseline Established

This baseline represents a clean validation state for the target repo. Future validation runs should maintain:

- 0 FAIL validators
- All findings either PASS or documented in allowlists
- SKIP status only for Amendment 1.7 exemptions

Any regression from this baseline indicates either:

1. New code introducing validation findings (must be fixed or allowlisted with justification)
2. Template validator changes (must be backward compatible)
