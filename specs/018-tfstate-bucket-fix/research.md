# Research: Fix Terraform State Bucket Permission Mismatch

**Feature**: 018-tfstate-bucket-fix
**Date**: 2025-12-06

## Investigation Summary

### Decision: Migrate All Patterns to Standardized `terraform-state` Convention

**Rationale**: The codebase has two different bucket naming conventions:
- Dev environment uses: `sentiment-analyzer-tfstate-{account}`
- Preprod/Prod environments use: `sentiment-analyzer-terraform-state-{account}`

Per user clarification, we will standardize on the `terraform-state` pattern across all files to eliminate technical debt and prevent future confusion.

**Implementation Approach**: Clean replacement - dev compatibility not required since pipeline only verifies integration tests pass and Terraform can deploy.

**Alternatives Considered**:

| Alternative | Status |
|-------------|--------|
| Add both patterns for backward compatibility | Rejected - unnecessary complexity, dev compat not required |
| Wildcard `sentiment-analyzer-*state-*` | Rejected - too permissive, violates least privilege |
| Keep old pattern everywhere | Rejected - perpetuates naming inconsistency |

### Findings

1. **Backend Configuration Analysis**:
   - `backend-dev.hcl`: `bucket = "sentiment-analyzer-tfstate-218795110243"`
   - `backend-preprod.hcl`: `bucket = "sentiment-analyzer-terraform-state-218795110243"`
   - `backend-prod.hcl`: `bucket = "sentiment-analyzer-terraform-state-218795110243"`

2. **Bootstrap Resource**:
   - `bootstrap/main.tf` creates bucket with pattern `sentiment-analyzer-tfstate-{account}`
   - This only affects initial bucket creation, not usage

3. **IAM Policy Current State**:
   - All deployer policies use `sentiment-analyzer-tfstate-*`
   - CI user policy uses `*-sentiment-tfstate-*`
   - Neither matches `sentiment-analyzer-terraform-state-*`

## Best Practices Applied

- **Least Privilege**: Each environment policy only grants access to its specific path prefix (`/dev/*`, `/preprod/*`, `/prod/*`)
- **Backward Compatibility**: Retaining old patterns prevents breaking existing configurations
- **Explicit Patterns**: Using specific bucket name prefixes rather than broad wildcards

## No Additional Research Needed

This is a straightforward configuration fix with clear root cause and solution. No external research required.
