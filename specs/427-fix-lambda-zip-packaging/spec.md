# Feature Specification: Fix Lambda ZIP Packaging Structure

**Feature Branch**: `427-fix-lambda-zip-packaging`
**Created**: 2025-12-18
**Status**: Draft
**Input**: User description: "Fix Lambda ZIP packaging to preserve directory structure. The ingestion Lambda uses absolute imports (from src.lambdas.ingestion.module) but deploy.yml copies files flat (cp -r src/lambdas/ingestion/* dest/), causing Runtime.ImportModuleError. Apply the correct dashboard Lambda pattern (mkdir -p dest/src/lambdas/ingestion && cp -r src/lambdas/ingestion/* dest/src/lambdas/ingestion/) to all affected Lambdas."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Ingestion Lambda Successfully (Priority: P1)

As a CI/CD pipeline operator, I want the ingestion Lambda to deploy and execute without import errors, so that data ingestion flows work reliably in production.

**Why this priority**: The ingestion Lambda is currently broken in preprod with `Runtime.ImportModuleError`. This is the primary blocker preventing the feature from functioning.

**Independent Test**: Can be fully tested by triggering the ingestion Lambda via AWS CLI or API Gateway and verifying it returns a successful response without import errors.

**Acceptance Scenarios**:

1. **Given** the deploy workflow has completed, **When** the ingestion Lambda is invoked, **Then** it executes without `ImportModuleError` or `ModuleNotFoundError`.
2. **Given** the ingestion Lambda handler imports `from src.lambdas.ingestion.alerting`, **When** the Lambda cold starts, **Then** the `alerting` module is found at the expected path.
3. **Given** the Lambda ZIP package is built, **When** the package contents are inspected, **Then** the directory structure matches `src/lambdas/ingestion/handler.py` not a flat `handler.py` at root.

---

### User Story 2 - Consistent Packaging Across All Lambdas (Priority: P2)

As a platform engineer, I want all ZIP-based Lambda packaging to follow the same directory structure pattern, so that import behavior is consistent and predictable.

**Why this priority**: Preventing future regressions by establishing a consistent pattern. The dashboard Lambda already uses the correct pattern, but others (ingestion, analysis, metrics, notification) may have the same flat-copy issue.

**Independent Test**: Can be tested by running a static analysis validator against the workflow file to detect flat-copy patterns.

**Acceptance Scenarios**:

1. **Given** any Lambda that uses absolute imports (from src.lambdas.X.module), **When** its ZIP package is built, **Then** the package preserves the `src/lambdas/X/` directory structure.
2. **Given** the docker-import validator is run against the repository, **When** LPK-003 (flat copy) findings are checked, **Then** zero findings are reported.

---

### User Story 3 - Local and Lambda Import Parity (Priority: P3)

As a developer, I want the same Python imports to work identically in local development and in deployed Lambda, so that I can test locally with confidence that it will work in production.

**Why this priority**: Reduces debugging time and prevents "works on my machine" issues. Lower priority because the immediate fix unblocks deployment; parity is a maintainability concern.

**Independent Test**: Can be tested by running `python -c "from src.lambdas.ingestion.handler import lambda_handler"` locally and verifying the Lambda accepts the same import structure.

**Acceptance Scenarios**:

1. **Given** a Lambda handler with absolute imports, **When** the handler is invoked locally via pytest, **Then** imports resolve identically to the deployed Lambda environment.

---

### Edge Cases

- What happens when a Lambda has no intra-module imports (only external packages)? The packaging change should have no negative impact - files can still be at root if no src.* imports exist.
- How does the system handle Lambda shared modules (src/lambdas/shared)? Shared modules must also be copied to the correct path `dest/src/lambdas/shared/`.
- What happens if src/lib is imported? The `src/lib` directory must also be copied to `dest/src/lib/` to maintain import paths.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Deploy workflow MUST create the directory structure `packages/<lambda>-build/src/lambdas/<lambda>/` before copying Lambda handler files.
- **FR-002**: Deploy workflow MUST copy Lambda handler files to `dest/src/lambdas/<lambda>/` not to `dest/` root.
- **FR-003**: Deploy workflow MUST copy `src/lambdas/shared` to `dest/src/lambdas/shared/` to maintain shared module imports.
- **FR-004**: Deploy workflow MUST copy `src/lib` to `dest/src/lib/` to maintain library imports.
- **FR-005**: All ZIP-based Lambdas (ingestion, analysis, metrics, notification) MUST use the same packaging pattern as the dashboard Lambda.
- **FR-006**: Terraform handler configuration MUST match the preserved directory structure (e.g., `handler = "src.lambdas.ingestion.handler.lambda_handler"`).
- **FR-007**: Lambda functions MUST start successfully without `ImportModuleError` or `ModuleNotFoundError` after deployment.

### Key Entities

- **Lambda Package**: A ZIP file containing Python modules, structured to match import paths used in handler code.
- **Handler**: The Lambda entry point file (e.g., `src/lambdas/ingestion/handler.py`) containing `lambda_handler` function.
- **Shared Modules**: Common code in `src/lambdas/shared/` imported by multiple Lambda handlers.
- **Library Modules**: Utility code in `src/lib/` imported by Lambda handlers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All ZIP-based Lambda functions (ingestion, analysis, metrics, notification) successfully execute without import errors when invoked.
- **SC-002**: The docker-import validator reports zero LPK-003 (flat copy) findings when run against the repository.
- **SC-003**: CI/CD pipeline completes deployment without Lambda invocation failures for all environments (dev, preprod, prod).
- **SC-004**: Cold start latency does not increase by more than 100ms due to the directory structure change (validates no performance regression).

## Assumptions

- The dashboard Lambda's packaging pattern (lines 219-228 in deploy.yml) is the correct reference implementation.
- The ingestion Lambda is the primary broken Lambda, but all ZIP-based Lambdas should be audited for consistency.
- Terraform handler configuration already uses the correct path format (`src.lambdas.X.handler.lambda_handler`).
- Docker-based Lambdas (like SSE) use a different packaging mechanism and are not affected by this fix.
