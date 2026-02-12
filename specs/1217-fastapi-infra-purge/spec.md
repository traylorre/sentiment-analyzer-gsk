# Feature Specification: FastAPI Infrastructure Purge

**Feature Branch**: `1217-fastapi-infra-purge`
**Created**: 2026-02-11
**Status**: Draft
**Input**: User description: "Complete the FastAPI + Mangum permanent removal from deployment infrastructure. Remove every remaining trace from Terraform, Dockerfiles, CI/CD, documentation, comments, and configuration. Zero tolerance — no reference to FastAPI, Mangum, uvicorn, starlette, or Lambda Web Adapter may survive in the codebase."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Without Legacy Framework Artifacts (Priority: P1)

A platform engineer deploys the application and the deployment pipeline contains zero references to FastAPI, Mangum, uvicorn, starlette, or Lambda Web Adapter. Every Lambda function runs on its native handler (AWS Lambda Powertools or custom runtime bootstrap) without any adapter layer, proxy process, or framework shim in the execution path.

**Why this priority**: The deployment infrastructure is the runtime boundary. If legacy references persist in Terraform, Dockerfiles, or CI/CD, they create confusion about the actual architecture, risk re-introducing dead dependencies during maintenance, and inflate container images with unnecessary packages.

**Independent Test**: Can be verified by running `terraform plan` and confirming no Lambda layer ARNs, PORT environment variables, or web adapter references exist. Can be verified by building all Docker images and confirming no FastAPI/uvicorn/mangum packages are installed. Can be verified by running CI/CD in dry-run and confirming no legacy package installation steps.

**Acceptance Scenarios**:

1. **Given** the Terraform configuration for all Lambda functions, **When** a platform engineer reviews the resource definitions, **Then** no `layers` attribute references a Lambda Web Adapter ARN, no environment variable sets `PORT` or `AWS_LWA_*`, and all handlers point to native entry points.
2. **Given** any Dockerfile in the repository, **When** the image is built, **Then** the installed packages contain zero instances of `fastapi`, `mangum`, `uvicorn`, or `starlette`, and no `CMD` or `ENTRYPOINT` invokes uvicorn.
3. **Given** the CI/CD workflow files, **When** a pipeline runs, **Then** no step installs, references, or tests against FastAPI, Mangum, uvicorn, or starlette packages.

---

### User Story 2 - Codebase Contains Zero Legacy References (Priority: P2)

A developer searches the entire repository for any trace of FastAPI, Mangum, uvicorn, starlette, or Lambda Web Adapter. The search returns zero results across all files: source code comments, docstrings, documentation, configuration, README files, spec archives, and inline annotations. The codebase reads as if the legacy framework never existed.

**Why this priority**: Residual comments like "replaces FastAPI" or "migrated from Mangum" create cognitive noise, mislead new contributors into thinking the old framework is still relevant, and serve as semantic anchors that invite re-introduction. A clean codebase communicates the canonical architecture without historical baggage.

**Independent Test**: Can be verified by running a case-insensitive recursive grep for `fastapi`, `mangum`, `uvicorn`, `starlette`, `lambda.web.adapter`, and `LWA` across the entire repository. Zero matches means pass. Any match means fail.

**Acceptance Scenarios**:

1. **Given** the complete repository including all source files, tests, docs, and configs, **When** a case-insensitive search for `fastapi` is performed, **Then** zero results are returned.
2. **Given** the complete repository, **When** a case-insensitive search for `mangum` is performed, **Then** zero results are returned.
3. **Given** the complete repository, **When** a case-insensitive search for `uvicorn` is performed, **Then** zero results are returned.
4. **Given** the complete repository, **When** a case-insensitive search for `starlette` is performed, **Then** zero results are returned.
5. **Given** the complete repository, **When** a case-insensitive search for `lambda.web.adapter` or `LambdaAdapterLayer` is performed, **Then** zero results are returned.
6. **Given** comments in active source code that reference the old framework (e.g., "replaces FastAPI", "migrated from Mangum"), **When** these comments are reviewed, **Then** they have been rewritten to describe the current architecture without mentioning the removed framework.

---

### User Story 3 - Deployment Verification Confirms Native Operation (Priority: P3)

After deployment to preprod, a platform engineer runs smoke tests that confirm every Lambda function responds correctly using its native handler. The SSE streaming Lambda streams events via custom runtime bootstrap. The dashboard Lambda routes requests via AWS Lambda Powertools. No adapter layer is in the execution path.

**Why this priority**: Verification closes the loop. Without deployment confirmation, infrastructure changes are theoretical. Smoke tests prove the system functions correctly after the purge.

**Independent Test**: Can be verified by invoking each Lambda's health endpoint (or trigger) after deployment and confirming HTTP 200 responses with correct content types and expected response bodies.

**Acceptance Scenarios**:

1. **Given** the dashboard Lambda deployed to preprod, **When** a health check request is sent to its Function URL, **Then** it returns HTTP 200 with the expected response body generated by AWS Lambda Powertools.
2. **Given** the SSE streaming Lambda deployed to preprod, **When** an SSE connection is established to its Function URL, **Then** it streams events via RESPONSE_STREAM mode using the custom runtime bootstrap (not through uvicorn or a web adapter).
3. **Given** all ZIP-packaged Lambdas (ingestion, metrics, notification) deployed to preprod, **When** their triggers fire (S3 event, EventBridge schedule, SNS message), **Then** they execute successfully with native `handler.lambda_handler` entry points.

---

### User Story 4 - Rollback Plan Exists for Failed Deployment (Priority: P3)

If the purged deployment fails in preprod, a platform engineer can revert to the last known working state within 15 minutes using documented rollback procedures. The rollback does not require re-introducing FastAPI or any removed dependency.

**Why this priority**: Breaking changes to deployment infrastructure carry deployment risk. A rollback plan is essential but lower priority because the code migration (72/78 tasks) is already proven with 2983 passing tests.

**Independent Test**: Can be verified by reviewing the rollback procedure document and confirming it references only currently-available artifacts (prior container image tags, prior Terraform state, prior ZIP packages).

**Acceptance Scenarios**:

1. **Given** a failed deployment to preprod, **When** the rollback procedure is executed, **Then** the previous container images are restored from ECR image tags and the previous ZIP packages are restored from S3 versioned objects.
2. **Given** the rollback procedure, **When** reviewed by a platform engineer, **Then** it contains step-by-step commands and estimated time-to-recovery under 15 minutes.

---

### Edge Cases

- What happens when a developer adds a new Python dependency that transitively pulls in `starlette` (e.g., `httpx[cli]`)? The CI pipeline MUST fail with an explicit error, not silently allow it.
- What happens when a Terraform module is updated and re-introduces a `layers` attribute with a web adapter ARN? The validation gate MUST detect and reject it.
- What happens when documentation references are searched and the `specs/001-fastapi-purge/` directory itself contains the term "fastapi"? This directory is part of the purge scope — its contents describe the completed migration and must be updated to remove framework names or archived outside the main tree.
- What happens when `pyproject.toml` has exclusion rules (e.g., ruff ignore patterns) that reference `fastapi`? These must be removed.

## Requirements *(mandatory)*

### Functional Requirements

#### Terraform Cleanup

- **FR-001**: All Lambda function Terraform resources MUST NOT contain any `layers` attribute referencing Lambda Web Adapter extension ARNs
- **FR-002**: All Lambda function environment variables MUST NOT include `PORT`, `AWS_LWA_INVOKE_MODE`, `AWS_LWA_READINESS_CHECK_PATH`, or any `AWS_LWA_*` prefixed variable
- **FR-003**: All Terraform variable definitions MUST NOT contain variables for web adapter layer ARN, adapter configuration, or uvicorn settings
- **FR-004**: The SSE streaming Lambda Terraform environment variable `PYTHONPATH` comment (if present) MUST NOT reference Lambda Web Adapter

#### Dockerfile Cleanup

- **FR-005**: All Dockerfiles MUST NOT contain any `pip install` of `fastapi`, `mangum`, `uvicorn`, or `starlette`
- **FR-006**: All Dockerfiles MUST NOT contain `CMD` or `ENTRYPOINT` directives that invoke `uvicorn`
- **FR-007**: All Dockerfile comments MUST NOT reference FastAPI, Mangum, uvicorn, starlette, or Lambda Web Adapter
- **FR-008**: All requirements.txt files MUST NOT list `fastapi`, `mangum`, `uvicorn`, or `starlette` as dependencies

#### CI/CD Cleanup

- **FR-009**: All GitHub Actions workflow files MUST NOT contain steps that install, test, or reference FastAPI, Mangum, uvicorn, or starlette
- **FR-010**: All CI/CD smoke test assertions MUST validate against native Lambda handler responses, not web framework responses
- **FR-011**: The CI pipeline MUST include a gate that fails if any of the banned package names (`fastapi`, `mangum`, `uvicorn`, `starlette`) appear in any `requirements*.txt` file

#### Source Code Comment Cleanup

- **FR-012**: All comments and docstrings in active source code that reference FastAPI, Mangum, uvicorn, starlette, or Lambda Web Adapter MUST be rewritten to describe the current architecture without mentioning the removed framework
- **FR-013**: The rewritten comments MUST preserve the functional intent (e.g., "422 validation error format" instead of "FastAPI-parity format")
- **FR-014**: The `src/README.md` MUST NOT reference FastAPI in Lambda descriptions

#### Documentation Cleanup

- **FR-015**: The `docs/fastapi-purge/` directory MUST be archived (moved to `docs/archive/fastapi-purge/` or deleted entirely)
- **FR-016**: The `specs/001-fastapi-purge/` directory MUST be archived (moved to `specs/archive/001-fastapi-purge/` or deleted entirely)
- **FR-017**: The project `README.md` MUST NOT reference FastAPI, Mangum, uvicorn, or starlette as current technology
- **FR-018**: The project `CLAUDE.md` MUST NOT reference FastAPI or Mangum in active technology descriptions
- **FR-019**: The project `SPEC.md` (architecture overview) MUST describe the current stack without legacy framework references

#### Verification Gates

- **FR-020**: A CI validation gate MUST exist that scans all non-archived files for banned terms (`fastapi`, `mangum`, `uvicorn`, `starlette`, `lambda.web.adapter`) and fails the build if any are found
- **FR-021**: The validation gate MUST exclude the `specs/archive/` and `docs/archive/` directories from scanning (archived historical records are acceptable)
- **FR-022**: The `make validate` target MUST include the banned-term scan as part of the standard validation suite

#### Deployment Verification

- **FR-023**: After deployment to preprod, a smoke test MUST confirm each Lambda function responds correctly through its native handler
- **FR-024**: The smoke test MUST verify the SSE streaming Lambda delivers events via RESPONSE_STREAM mode
- **FR-025**: A documented rollback procedure MUST exist that restores the prior deployment state using versioned artifacts (ECR image tags, S3 object versions, Terraform state)

### Assumptions

- The code migration (72/78 tasks from branch `001-fastapi-purge`) is complete and merged, with 2983 unit tests and 191 integration tests passing
- AWS Lambda Powertools `APIGatewayRestResolver` is the canonical replacement for FastAPI routing in the dashboard Lambda
- The SSE streaming Lambda uses a custom Python runtime bootstrap (not any web framework)
- All ZIP-packaged Lambdas (ingestion, metrics, notification) use native `handler.lambda_handler` entry points
- Container images are deployed via ECR with immutable SHA-tagged references
- The `specs/archive/` and `docs/archive/` directories are excluded from CI scanning to preserve historical records

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repository-wide case-insensitive search for `fastapi`, `mangum`, `uvicorn`, `starlette`, and `lambda web adapter` returns exactly zero matches in non-archived files
- **SC-002**: All Docker images build successfully with zero instances of banned packages in the installed package list (verified by `pip list` inside each container)
- **SC-003**: `terraform plan` produces no changes related to Lambda layers, PORT environment variables, or web adapter configuration
- **SC-004**: The CI pipeline passes with the new banned-term validation gate active
- **SC-005**: Each Lambda function responds correctly to its health check or trigger within 5 seconds after preprod deployment
- **SC-006**: Container image sizes decrease by at least 10MB compared to the pre-purge baseline (removal of uvicorn, mangum, starlette, and their transitive dependencies)
- **SC-007**: The rollback procedure can restore the previous deployment state within 15 minutes (measured from decision-to-rollback to service-restored)
