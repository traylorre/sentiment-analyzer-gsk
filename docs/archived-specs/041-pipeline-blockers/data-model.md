# Data Model: Pipeline Blockers Resolution

**Feature**: 041-pipeline-blockers
**Date**: 2025-12-06

## Overview

This feature is **infrastructure-only** and does not introduce new data models or entities.

## Entities Affected

### Existing: ECR Repository

**Resource**: `aws_ecr_repository.sse_streaming`
**Change**: Import into terraform state (no schema change)

| Attribute | Current | After |
|-----------|---------|-------|
| name | `preprod-sse-streaming-lambda` | No change |
| image_tag_mutability | `MUTABLE` | No change |
| scan_on_push | `true` | No change |
| encryption_type | `AES256` | No change |

### Existing: KMS Key

**Resource**: `aws_kms_key.main`
**Change**: Add CI deployer principals to key policy

| Attribute | Current | After |
|-----------|---------|-------|
| policy.Statement | 4 statements (Root, S3, SecretsManager, SNS) | 5 statements (+CIDeployerKeyAdmin) |

## No New Entities

This feature resolves state reconciliation and permission issues. No new:
- Database tables
- API endpoints
- Data structures
- Application entities

## State Transitions

N/A - Infrastructure resources only.
