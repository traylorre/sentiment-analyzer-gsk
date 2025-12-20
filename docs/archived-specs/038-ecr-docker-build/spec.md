# Feature Specification: ECR Docker Build for SSE Lambda

**Feature Branch**: `038-ecr-docker-build`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "Building and pushing Docker image to ECR for SSE streaming Lambda"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI Pipeline Builds Docker Image (Priority: P1)

When code changes are pushed to the repository, the CI/CD pipeline automatically builds a Docker image for the SSE streaming Lambda and pushes it to the container registry before Terraform deployment runs.

**Why this priority**: This is the core blocker. Without the Docker image in ECR, Terraform cannot create the Lambda function. The pipeline fails at "Terraform Apply" with "Source image does not exist".

**Independent Test**: Can be tested by running the pipeline on a feature branch and verifying the Docker image appears in the container registry with the expected tag.

**Acceptance Scenarios**:

1. **Given** code is pushed to the repository, **When** the CI/CD pipeline runs, **Then** a Docker image is built from the SSE Lambda source code
2. **Given** the Docker image is built successfully, **When** the build job completes, **Then** the image is pushed to the container registry with the `latest` tag
3. **Given** the image is pushed to the registry, **When** Terraform runs, **Then** the Lambda function can be created using the pushed image

---

### User Story 2 - Environment-Specific Image Tags (Priority: P2)

Each environment (preprod, prod) receives its own tagged Docker image, ensuring deployment isolation and allowing rollback to previous versions.

**Why this priority**: Important for production safety and rollback capability, but the core functionality (P1) works with just the `latest` tag.

**Independent Test**: Can be verified by running deployments to different environments and confirming each has its own image tag in the registry.

**Acceptance Scenarios**:

1. **Given** a deployment to preprod, **When** the image is pushed, **Then** it is tagged with a preprod-specific identifier
2. **Given** a deployment to prod, **When** the image is pushed, **Then** it is tagged with a prod-specific identifier
3. **Given** a previous deployment exists, **When** viewing the registry, **Then** previous image versions are retained for rollback

---

### User Story 3 - Image Build Caching (Priority: P3)

The build process uses caching to minimize build time for unchanged dependencies, improving pipeline performance.

**Why this priority**: Optimization that improves developer experience but is not required for basic functionality.

**Independent Test**: Can be measured by comparing build times with and without cache, targeting significant time reduction for no-change builds.

**Acceptance Scenarios**:

1. **Given** dependencies haven't changed, **When** the build runs, **Then** cached layers are reused
2. **Given** only application code changed, **When** the build runs, **Then** dependency layers are cached and only application layers are rebuilt

---

### Edge Cases

- What happens when the container registry is unavailable? Build should fail with clear error message.
- What happens when the Docker build fails? Pipeline should abort before Terraform runs to prevent partial deployments.
- What happens when authentication to the registry fails? Clear error message should indicate credential issues.
- What happens when the image already exists with the same tag? The existing image should be overwritten with the new build.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Pipeline MUST build a Docker image from the SSE streaming Lambda source before Terraform deployment
- **FR-002**: Pipeline MUST authenticate to the container registry before pushing images
- **FR-003**: Pipeline MUST push the built image to the container registry with the `latest` tag
- **FR-004**: Pipeline MUST fail the deployment if the Docker build fails
- **FR-005**: Pipeline MUST fail the deployment if the image push fails
- **FR-006**: Pipeline MUST use the same naming convention for ECR repository as Terraform expects (`{env}-sse-streaming-lambda`)
- **FR-007**: Pipeline MUST run the image build step before the Terraform apply step
- **FR-008**: Pipeline MUST support building images for different environments (preprod, prod)
- **FR-009**: Built images MUST include all runtime dependencies required by the SSE Lambda
- **FR-010**: Pipeline MUST log build progress for debugging purposes

### Key Entities

- **Docker Image**: Container image built from SSE Lambda source code, tagged with version/environment identifiers
- **Container Registry Repository**: Storage location for Docker images, organized by environment
- **Build Artifact**: The resulting image layer cache and metadata from the build process

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Docker image is built and pushed successfully in under 5 minutes for a clean build
- **SC-002**: Subsequent builds with cached layers complete in under 2 minutes
- **SC-003**: Terraform deployment no longer fails with "Source image does not exist" error
- **SC-004**: 100% of pipeline runs that reach Terraform apply have the required image available
- **SC-005**: Build failures produce clear, actionable error messages within 30 seconds of the failure

## Out of Scope

- Image vulnerability scanning (can be added as future enhancement)
- Multi-architecture builds (ARM/x86 - current requirement is x86_64 only)
- Image signing and verification
- Automatic cleanup of old images (lifecycle policies are managed separately)

## Assumptions

- Container registry (ECR) repositories already exist and are managed by Terraform
- CI/CD pipeline has appropriate credentials to authenticate to the container registry
- SSE Lambda Dockerfile already exists in the repository
- Build environment has Docker available for building images
