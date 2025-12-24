# Feature Specification: Rename Confusing Table Environment Variables

**Feature Branch**: `1043-fix-metrics-table-env`
**Created**: 2024-12-24
**Status**: Draft
**Input**: Fix /api/v2/metrics 500 error by comprehensively renaming DATABASE_TABLE and DYNAMODB_TABLE to descriptive names (USERS_TABLE, SENTIMENTS_TABLE)

## Problem Statement

The dashboard Lambda has two confusingly named environment variables:
- `DATABASE_TABLE` → points to **users table** (feature_006_users_table)
- `DYNAMODB_TABLE` → points to **sentiment items table** (sentiment-items)

This caused a bug: `/api/v2/metrics` returns 500 because `handler.py:81` reads `DATABASE_TABLE` (users table) but the metrics functions expect the sentiment items table.

The similar names tell nothing about which table they represent, leading to bugs and confusion.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pipeline Passes Integration Tests (Priority: P1)

As a developer, I need the preprod integration tests to pass so that deployments can proceed to production.

**Why this priority**: Blocking all deployments - pipeline fails at warmup step with HTTP 500

**Independent Test**: Run preprod integration tests, `/api/v2/metrics` returns 200

**Acceptance Scenarios**:

1. **Given** dashboard Lambda deployed with renamed env vars, **When** GET /api/v2/metrics called, **Then** returns 200 with valid metrics JSON
2. **Given** warmup step runs in deploy pipeline, **When** /api/v2/metrics invoked, **Then** returns 200 (not 500)

---

### User Story 2 - Clear Variable Naming Convention (Priority: P1)

As a developer, I need environment variable names that clearly indicate which table they reference so I don't accidentally use the wrong table.

**Why this priority**: Prevents future bugs from confusing naming - root cause of current issue

**Independent Test**: Code review confirms variable names match their purpose

**Acceptance Scenarios**:

1. **Given** Terraform config, **When** reading env var definitions, **Then** variable name clearly indicates table purpose (`USERS_TABLE`, `SENTIMENTS_TABLE`)
2. **Given** Python handler code, **When** reading table access code, **Then** variable name matches actual table being accessed
3. **Given** codebase search for old names, **When** grep for `DATABASE_TABLE` or `DYNAMODB_TABLE`, **Then** returns zero matches (fully migrated)

---

### Edge Cases

- Lambda invocations during deployment handled by AWS Lambda versioning
- No backward compatibility needed - internal env var naming only
- Tests must also use new naming convention

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Terraform MUST rename `DATABASE_TABLE` to `USERS_TABLE` (points to users table)
- **FR-002**: Terraform MUST rename `DYNAMODB_TABLE` to `SENTIMENTS_TABLE` (points to sentiment items table)
- **FR-003**: Python code MUST read `SENTIMENTS_TABLE` env var for metrics/sentiment operations
- **FR-004**: Python code MUST read `USERS_TABLE` env var for user/session/config operations
- **FR-005**: `/api/v2/metrics` endpoint MUST query the sentiments table (has GSIs for sentiment distribution)
- **FR-006**: All unit tests MUST use the new env var names in fixtures

### Files to Update

**Terraform** (infrastructure/terraform/main.tf):
- Line 405: `DATABASE_TABLE` → `USERS_TABLE`
- Line 407: `DYNAMODB_TABLE` → `SENTIMENTS_TABLE`

**Python Lambda Code** (src/lambdas/dashboard/):
- `handler.py:81` - Change `os.environ["DATABASE_TABLE"]` to appropriate table
- `handler.py` - Rename Python variable from `DYNAMODB_TABLE` to match env var name
- All usages of the renamed variables

**Tests**:
- Update test fixtures/conftest to use new env var names

### Key Entities

- **USERS_TABLE**: DynamoDB table for user data (sessions, configs, alerts) - single-table design with PK/SK
- **SENTIMENTS_TABLE**: DynamoDB table for sentiment items (news, analysis results) - has GSIs for sentiment/status/tag queries

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Preprod integration tests pass (0 failures in SSE/metrics/latency tests)
- **SC-002**: `/api/v2/metrics` returns HTTP 200 with valid JSON containing sentiment distribution
- **SC-003**: `grep -r "DATABASE_TABLE\|DYNAMODB_TABLE" src/ infrastructure/` returns 0 matches
- **SC-004**: Deploy pipeline completes successfully through preprod integration tests
- **SC-005**: Variable names in code are self-documenting (no comments needed to explain which table)
