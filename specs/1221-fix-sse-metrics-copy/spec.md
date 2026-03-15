# Feature Specification: Fix SSE Lambda Dockerfile Missing Metrics Module

**Feature Branch**: `1221-fix-sse-metrics-copy`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Fix SSE Lambda Dockerfile missing src/lib/metrics.py COPY"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deploy Pipeline Completes Successfully (Priority: P1)

When a developer merges code to main, the deploy pipeline builds the SSE Lambda Docker
image, runs a smoke test to verify all Python imports resolve, and proceeds to deploy
the image to the target environment. Currently this fails because the metrics module is
missing from the container image.

**Why this priority**: The deploy pipeline is completely blocked. No code changes can
reach preprod or production until this is resolved.

**Independent Test**: Can be tested by building the SSE Lambda Docker image locally and
running the existing smoke test import check inside the container.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda Dockerfile is built with the standard build context, **When**
   the smoke test runs Python import verification inside the container, **Then** all
   imports succeed including src.lib.metrics
2. **Given** the deploy pipeline triggers on a push to main, **When** the Build SSE
   Lambda Image job executes, **Then** both the Docker build and smoke test pass

---

### User Story 2 - SSE Lambda Runtime Imports Succeed (Priority: P1)

When the SSE Lambda starts in AWS, it must be able to import all modules it depends on.
The fanout module imports the metrics module to emit CloudWatch custom metrics for error
tracking. If this import fails at runtime, the Lambda crashes with an unrecoverable error.

**Why this priority**: Even if the smoke test were bypassed, the Lambda would crash at
runtime. This is equally critical to Story 1.

**Independent Test**: Can be tested by running the Docker container locally with a Python
import of the fanout module to verify the transitive import chain resolves.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda container starts in AWS, **When** the handler imports fanout
   functionality, **Then** the transitive dependency on src.lib.metrics resolves without
   ModuleNotFoundError
2. **Given** the SSE Lambda container starts in AWS, **When** the circuit breaker module
   from shared is loaded, **Then** its dependency on src.lib.metrics also resolves

---

### User Story 3 - Graceful ADOT Layer Absence (Priority: P2)

When the ADOT Collector layer is not available, the Docker build must still succeed. The
existing wildcard COPY pattern handles this, and the metrics module fix must not break
this graceful degradation.

**Why this priority**: Important for developer experience and bootstrap scenarios, but
not blocking the immediate deploy.

**Independent Test**: Can be tested by building the Docker image without the adot-layer
directory present and verifying the build succeeds.

**Acceptance Scenarios**:

1. **Given** no adot-layer directory exists in the build context, **When** the Docker
   image is built, **Then** the build completes successfully and the metrics module is
   still available

---

### Edge Cases

- What happens when metrics.py is deleted or renamed? The Docker build fails with a
  clear COPY error, which is correct behavior (fail fast).
- What happens if metrics.py gains new dependencies on other internal library modules?
  The same pattern applies: any new transitive dependency must be explicitly copied.
- What happens if the SSE Dockerfile is refactored to copy all of lib like the
  analysis and dashboard Dockerfiles? This is a valid alternative that eliminates the
  selective copy maintenance burden.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The SSE Lambda Docker image MUST include the metrics module at the
  expected internal path within the container
- **FR-002**: The SSE Lambda Docker image MUST pass the existing smoke test that
  verifies Python import chains
- **FR-003**: The Docker build MUST succeed both with and without the ADOT layer
  directory present (existing behavior preserved)
- **FR-004**: The metrics module MUST be importable via the standard internal import
  path inside the running container

### Assumptions

- The metrics module has no transitive imports from other internal library modules
  (verified: it only imports standard library and installed packages)
- The selective COPY approach is preferred over copying the entire lib directory to
  keep the SSE image size minimal since it includes the ADOT sidecar
- No changes to the analysis or dashboard Dockerfiles are needed (they already copy
  all of lib)
- The existing init file at the lib directory path is already created by the
  mkdir/touch step in the Dockerfile

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The SSE Lambda Docker image builds and passes the smoke test on every
  deploy pipeline run
- **SC-002**: The deploy pipeline progresses past the Build SSE Lambda Image job
  without failures related to missing modules
- **SC-003**: The SSE Lambda starts successfully in AWS without ModuleNotFoundError
  for any module in its import chain
- **SC-004**: No meaningful increase in Docker image size beyond the metrics module
  itself (approximately 12KB)
