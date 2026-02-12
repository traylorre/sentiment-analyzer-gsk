# Feature Specification: Dashboard Lambda Container Deployment

**Feature Branch**: `1036-dashboard-container-deploy`
**Created**: 2025-12-23
**Status**: Draft
**Input**: User description: "Fix preprod 502 errors caused by binary incompatibility in ZIP packaging. Migrate Dashboard Lambda from ZIP to container image deployment."

## Problem Statement

The Dashboard Lambda is currently deployed as a ZIP package with platform-specific pip install flags. This causes **HTTP 502 errors** in preprod due to binary incompatibility between `manylinux2014_x86_64` wheels and the Lambda Amazon Linux 2023 runtime.

**Root Cause**: The `pydantic_core._pydantic_core` shared library compiled for generic manylinux2014 is incompatible with Lambda's AL2023 + Python 3.13 runtime.

**Impact**: Preprod health endpoint returns HTTP 502, all E2E tests fail, OHLC resolution selector feature cannot be demonstrated.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Smoke Test Health Check (Priority: P1)

As a CI/CD pipeline, I need the preprod health endpoint to return HTTP 200 so that smoke tests pass and deployments complete successfully.

**Why this priority**: Without a healthy preprod environment, no features can be demonstrated or tested end-to-end. This blocks all other work.

**Independent Test**: Can be fully tested by curling the preprod health endpoint and expecting HTTP 200.

**Acceptance Scenarios**:

1. **Given** Dashboard Lambda is deployed as a container image, **When** I curl `https://{api_url}/health`, **Then** I receive HTTP 200 with valid JSON response
2. **Given** Dashboard Lambda container starts cold, **When** the first request arrives, **Then** the response is returned within 10 seconds (cold start acceptable)

---

### User Story 2 - E2E Test Compatibility (Priority: P1)

As a developer, I need preprod E2E tests to pass so that code changes can be validated before production deployment.

**Why this priority**: E2E tests are the last line of defense before production. They validate actual AWS infrastructure integration.

**Independent Test**: Run `pytest tests/e2e/test_e2e_lambda_invocation_preprod.py` and all tests pass.

**Acceptance Scenarios**:

1. **Given** Dashboard Lambda is deployed as container, **When** E2E tests run, **Then** no HTTP 502 errors occur
2. **Given** all Lambda dependencies are included in container, **When** any endpoint is called, **Then** no `ImportModuleError` appears in CloudWatch logs

---

### User Story 3 - Deploy Pipeline Completion (Priority: P1)

As a DevOps engineer, I need the deploy pipeline to complete successfully so that features can be deployed to preprod and production.

**Why this priority**: A blocked deploy pipeline prevents all feature releases.

**Independent Test**: Merge any change to main and observe the Deploy Pipeline workflow completes with green status.

**Acceptance Scenarios**:

1. **Given** a PR is merged to main, **When** Deploy Pipeline runs, **Then** all jobs complete successfully including smoke test
2. **Given** container image is built in CI, **When** Terraform applies, **Then** Lambda is updated to use the new container image

---

### Edge Cases

- What happens when ECR image build fails? Pipeline should fail fast with clear error before Terraform apply.
- What happens when container image exceeds Lambda size limit (10GB)? Build should error with clear message.
- What happens during ECR rate limiting? Build should retry with exponential backoff.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: CI MUST build Dashboard Lambda as a Docker container image using `public.ecr.aws/lambda/python:3.13` base
- **FR-002**: CI MUST push container image to ECR repository in preprod/prod AWS accounts
- **FR-003**: Terraform MUST deploy Lambda using ECR container image instead of ZIP package
- **FR-004**: Container MUST include all runtime dependencies (pydantic, fastapi, boto3, etc.)
- **FR-005**: Container MUST use the same handler path as current ZIP deployment
- **FR-006**: Deploy workflow MUST NOT remove ZIP packaging for Analysis Lambda (only Dashboard)
- **FR-007**: Smoke test MUST continue to validate health endpoint after deployment

### Key Entities

- **Dashboard Lambda**: The sentiment-dashboard Lambda function that serves the FastAPI dashboard
- **ECR Repository**: Container registry for storing Dashboard Lambda images
- **Container Image**: Docker image containing Dashboard Lambda code and dependencies

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Preprod health endpoint returns HTTP 200 (currently returns HTTP 502)
- **SC-002**: CloudWatch logs contain no `ImportModuleError` or `No module named` errors
- **SC-003**: All E2E tests in `test_e2e_lambda_invocation_preprod.py` pass (currently 24/25 fail)
- **SC-004**: Deploy Pipeline workflow completes with green status on main branch
- **SC-005**: Lambda cold start completes within 15 seconds

## Assumptions

- ECR repository can be created in the same Terraform module as the Lambda
- The public Lambda base image `public.ecr.aws/lambda/python:3.13` is suitable and doesn't require AWS authentication to pull
- Container image size will be under 1GB (manageable cold start)
- GitHub Actions has permissions to push to ECR via OIDC

## Out of Scope

- Analysis Lambda migration (already using container deployment)
- Ingestion Lambda migration (ZIP packaging works for this Lambda)
- Production deployment (will follow preprod validation)
- Performance optimization beyond ensuring cold start < 15s
