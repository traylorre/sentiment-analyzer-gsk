# Implementation Plan: Validate $60/Month Infrastructure Budget

**Branch**: `1020-validate-budget-60-month` | **Date**: 2025-12-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1020-validate-budget-60-month/spec.md`

## Summary

Validate that the real-time multi-resolution feature (1009) infrastructure cost remains under $60/month using infracost analysis. Document the cost breakdown by resource type (DynamoDB, Lambda, CloudWatch) and provide optimization recommendations if the budget is exceeded.

## Technical Context

**Language/Version**: Python 3.13 (for any helper scripts), Terraform HCL (infrastructure)
**Primary Dependencies**: infracost CLI, make, jq (for parsing)
**Storage**: N/A (documentation output only)
**Testing**: Manual validation of infracost output
**Target Platform**: AWS (us-east-1)
**Project Type**: Infrastructure cost analysis (no new code)
**Performance Goals**: Cost analysis completes in <2 minutes
**Constraints**: $60/month budget (SC-010), 100 concurrent users, 13 tickers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
| ---- | ------ | ----- |
| Section 5: Deployment Requirements | PASS | Uses Terraform IaC, AWS serverless |
| Section 6: Observability & Cost | PASS | This feature validates cost budgets and alerts |
| Section 7: Testing | N/A | Documentation-only feature |
| Section 8: Git Workflow | PASS | Will use signed commits, feature branch |

**All gates PASS** - proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/1020-validate-budget-60-month/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: infracost research
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# No new source code - this is a documentation/validation feature

docs/
└── cost-breakdown.md    # OUTPUT: Detailed cost analysis document

infrastructure/terraform/
├── main.tf              # Existing infrastructure (analysis target)
├── modules/
│   ├── dynamodb/        # DynamoDB tables
│   ├── lambda/          # Lambda functions
│   └── cloudwatch/      # CloudWatch resources (if any)
└── *.tfvars             # Environment variables
```

**Structure Decision**: This is a documentation-only feature. No new source code directories needed. Output is a cost breakdown document in `docs/`.

## Complexity Tracking

> No violations - feature is documentation/validation only.

## Phase 0: Research

### Research Questions

1. **RQ-1**: How does infracost calculate DynamoDB on-demand costs?
2. **RQ-2**: What Lambda invocation assumptions should we use for SSE streaming?
3. **RQ-3**: How to model CloudWatch Logs ingestion for streaming events?

### Key Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Cost tool | infracost | Already integrated via `make cost`, AWS-specific |
| Usage model | Assumptions-based | On-demand pricing requires usage estimates |
| Output format | Markdown | Consistent with project documentation |

## Phase 1: Design

### Cost Model Assumptions

Based on spec usage assumptions:
- **Users**: 100 concurrent users
- **Tickers**: 13 tracked tickers
- **Ingestion**: ~500 news items/day
- **SSE Connections**: Average 50 active SSE connections
- **Dashboard Views**: ~1000 resolution switches/day

### DynamoDB Cost Factors

- **Timeseries table**: On-demand mode
- **Write operations**: 500 items/day × 8 resolutions = 4000 writes/day
- **Read operations**: 50 connections × 8 resolutions × 24 hours = ~9600 reads/day
- **Storage**: ~13 tickers × 8 resolutions × 30 days retention × 1KB = ~3MB

### Lambda Cost Factors

- **SSE Streaming Lambda**: ~50 concurrent connections × 30s heartbeat = function URL invocations
- **Ingestion Lambda**: 500 items/day invocations
- **Analysis Lambda**: 500 items/day invocations

### CloudWatch Cost Factors

- **Logs ingestion**: Lambda logs + structured latency metrics
- **Logs storage**: 30-day retention
- **Metrics**: Custom metrics if any

## Artifacts

- **research.md**: Cost calculation methodology
- **docs/cost-breakdown.md**: Detailed cost breakdown with optimization recommendations
- **tasks.md**: Implementation tasks (Phase 2)
