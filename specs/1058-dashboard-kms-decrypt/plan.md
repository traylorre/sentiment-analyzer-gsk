# Implementation Plan: Dashboard Lambda KMS Decrypt Permission

**Branch**: `1058-dashboard-kms-decrypt` | **Date**: 2025-12-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1058-dashboard-kms-decrypt/spec.md`

## Summary

The dashboard Lambda is missing KMS decrypt permission required to read secrets encrypted with customer-managed KMS keys. The ingestion Lambda has this permission (via conditional block in IAM policy), but the dashboard Lambda's secrets policy only has `secretsmanager:GetSecretValue` without the corresponding `kms:Decrypt`. This blocks the OHLC endpoint from fetching Tiingo/Finnhub API keys, causing the dashboard to display only the sentiment donut chart with no ticker data.

## Technical Context

**Language/Version**: HCL (Terraform) 1.5+
**Primary Dependencies**: AWS Provider ~> 5.0
**Storage**: N/A (IAM policy modification)
**Testing**: terraform validate, terraform plan, IAM validator
**Target Platform**: AWS Lambda IAM Role
**Project Type**: Infrastructure as Code (Terraform modules)
**Performance Goals**: N/A (IAM policy change)
**Constraints**: Must follow least-privilege (single KMS key resource, not wildcard)
**Scale/Scope**: Single IAM policy modification in modules/iam/main.tf

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| Security & Access Control - Least Privilege | PASS | kms:Decrypt scoped to specific KMS key ARN, not wildcard |
| Security & Access Control - Secrets in managed service | PASS | Using AWS Secrets Manager + KMS |
| Infrastructure as Code | PASS | Terraform module modification |
| Testing & Validation | PASS | terraform validate + plan + unit test |
| No Pipeline Bypass | PASS | Standard PR workflow with CI checks |

## Project Structure

### Documentation (this feature)

```text
specs/1058-dashboard-kms-decrypt/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── checklists/
│   └── requirements.md  # Spec validation checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
infrastructure/terraform/modules/iam/
├── main.tf              # Dashboard secrets policy modification (target)
└── variables.tf         # Already has secrets_kms_key_arn variable
```

**Structure Decision**: This is an infrastructure-only change to the IAM module. No application code changes required.

## Complexity Tracking

> No constitution violations. Single, focused IAM policy modification.

## Phase 0: Research

No NEEDS CLARIFICATION markers. The pattern to follow is already established in the ingestion Lambda policy (lines 79-87 in modules/iam/main.tf).

### Research Findings

**Decision**: Add conditional KMS decrypt block to dashboard_secrets policy
**Rationale**: Exact pattern already exists for ingestion Lambda; proven to work
**Alternatives Considered**:
- Shared secrets policy resource: Rejected (violates least-privilege per-role isolation)
- KMS key policy modification: Rejected (less precise, affects all principals)
