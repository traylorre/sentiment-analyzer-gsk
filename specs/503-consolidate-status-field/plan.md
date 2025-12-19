# Implementation Plan: Consolidate Status Field

**Branch**: `503-consolidate-status-field` | **Date**: 2025-12-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/503-consolidate-status-field/spec.md`

## Summary

Consolidate boolean status attributes (`is_active`, `is_enabled`, `enabled`) into a single string `status` field across CONFIGURATION, ALERT_RULE, and DIGEST_SETTINGS entities. This fixes the GSI query mismatch where `by_entity_status` GSI expects `status` string but existing data only has boolean fields, causing zero results from GSI queries.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: boto3, pydantic (for model validation)
**Storage**: DynamoDB (preprod-sentiment-users table with by_entity_status GSI)
**Testing**: pytest with moto (unit), real AWS (integration/e2e)
**Target Platform**: AWS Lambda (serverless)
**Project Type**: Serverless Lambda functions
**Performance Goals**: O(result) GSI queries instead of O(partition) filtered scans
**Constraints**: Zero downtime migration, backward compatibility during transition
**Scale/Scope**: ~100 existing configurations, ~50 alert rules, ~20 digest settings in preprod

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Parameterized queries | PASS | DynamoDB uses ExpressionAttributeValues |
| TLS enforced | PASS | AWS SDK handles TLS |
| Secrets in Secrets Manager | PASS | No new secrets introduced |
| Unit tests required | PASS | Will add tests for new status field logic |
| No pipeline bypass | PASS | Standard PR workflow |
| GPG-signed commits | PASS | Required by pre-push hooks |
| Least-privilege IAM | PASS | No IAM changes required |

**Constitution Compliance**: All gates pass. This is a data model consolidation with no security implications.

## Project Structure

### Documentation (this feature)

```text
specs/503-consolidate-status-field/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A - no API changes)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/lambdas/
├── shared/
│   └── models/
│       ├── configuration.py    # MODIFY: is_active → status
│       ├── alert_rule.py       # MODIFY: is_enabled → status
│       └── notification.py     # MODIFY: enabled → status (DigestSettings)
├── dashboard/
│   ├── configurations.py       # MODIFY: read/write paths
│   ├── alerts.py               # MODIFY: read/write paths
│   └── notifications.py        # MODIFY: read/write paths
├── ingestion/
│   └── handler.py              # ALREADY USES status (from PR #431)
├── notification/
│   └── alert_evaluator.py      # MODIFY: is_enabled → status check
└── sse_streaming/
    └── config.py               # MODIFY: is_active → status check

tests/
├── unit/
│   └── lambdas/
│       ├── shared/
│       │   └── models/         # MODIFY: update model tests
│       ├── dashboard/          # MODIFY: update handler tests
│       └── notification/       # MODIFY: update evaluator tests
└── e2e/                        # Will verify end-to-end after migration

scripts/
└── migrate_status_field.py     # NEW: data migration script
```

**Structure Decision**: Existing Lambda structure preserved. Changes are model attribute updates and read/write path modifications.

## Complexity Tracking

No constitution violations requiring justification.
