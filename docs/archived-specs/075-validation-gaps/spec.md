# Feature Specification: Close Validation Gaps - Resource Naming Validators & JWT Auth

**Feature Branch**: `075-validation-gaps`
**Created**: 2025-12-09
**Status**: Partial (Resource Naming Complete, JWT Pending)
**Input**: User description: "Close 7 easily-closeable validation gaps identified in RESULT1-validation-gaps.md: 6 skipped resource naming validator tests and 1 JWT authentication TODO"

## Clarifications

### Session 2025-12-09

- Q: What JWT token expiration policy should be used? → A: Short sessions (15 min) with refresh token

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resource Naming Consistency Validation (Priority: P1)

As a DevOps engineer, I want automated validation that all infrastructure resources follow the `{env}-sentiment-{service}` naming pattern so that IAM policies correctly match resources and prevent permission errors.

**Why this priority**: This is the foundation for IAM security. Without consistent naming, IAM policies may fail to match resources, causing either permission denials (blocking deployments) or overly permissive access (security risk).

**Independent Test**: Can be fully tested by running the validation suite against Terraform files and verifying all resources pass the naming pattern check.

**Acceptance Scenarios**:

1. **Given** a Terraform module with Lambda functions, **When** validation runs, **Then** all Lambda names matching `preprod-sentiment-*` or `prod-sentiment-*` pass validation
2. **Given** a Terraform module with DynamoDB tables, **When** validation runs, **Then** all table names matching `{env}-sentiment-*` pass validation
3. **Given** a resource with legacy naming `sentiment-analyzer-*`, **When** validation runs, **Then** the resource is flagged as non-compliant
4. **Given** a resource missing the `sentiment` segment, **When** validation runs, **Then** the resource is flagged as non-compliant

---

### User Story 2 - IAM Pattern Coverage Validation (Priority: P1)

As a security engineer, I want automated validation that every Terraform resource has a corresponding IAM ARN pattern so that no resources are accidentally left without proper access controls.

**Why this priority**: Orphaned resources (resources without IAM coverage) represent security gaps. This validation ensures defense-in-depth.

**Independent Test**: Can be fully tested by extracting resource names from Terraform and verifying each has a matching IAM ARN pattern.

**Acceptance Scenarios**:

1. **Given** all Lambda, DynamoDB, SQS, and SNS resources in Terraform, **When** IAM coverage validation runs, **Then** each resource has at least one IAM policy pattern that covers it
2. **Given** an IAM policy with ARN patterns, **When** orphan detection runs, **Then** any patterns that reference non-existent resources are flagged
3. **Given** a new resource added to Terraform without IAM coverage, **When** validation runs, **Then** the gap is detected and reported

---

### User Story 3 - JWT Authentication for Authenticated Sessions (Priority: P2)

As a user with an authenticated session, I want the system to validate my JWT token so that my session remains secure and I can access personalized features.

**Why this priority**: While the system currently works with API keys, JWT validation enables stateless authentication and supports future features like OAuth and session management.

**Independent Test**: Can be tested by sending requests with valid/invalid JWT tokens and verifying correct acceptance or rejection.

**Acceptance Scenarios**:

1. **Given** a valid JWT token in the Authorization header, **When** a user makes an API request, **Then** the request is authenticated and processed
2. **Given** an expired JWT token, **When** a user makes an API request, **Then** the request is rejected with appropriate error
3. **Given** a malformed JWT token, **When** a user makes an API request, **Then** the request is rejected without exposing system details
4. **Given** a JWT with invalid signature, **When** validation occurs, **Then** the token is rejected

---

### Edge Cases

- What happens when a Terraform resource uses dynamic naming (variables)?
  - The validator should resolve variable references to actual patterns
- How does the system handle IAM policies with wildcard-only patterns like `*`?
  - Wildcard patterns are flagged for review but not counted as coverage
- What happens when JWT secret is not configured?
  - System should fail securely with clear error message, not fall back to insecure behavior

## Requirements *(mandatory)*

### Functional Requirements

**Part A: Resource Naming Validators**

- **FR-001**: System MUST extract resource names from all Terraform modules (Lambda, DynamoDB, SQS, SNS)
- **FR-002**: System MUST validate resource names against the `{env}-sentiment-{service}` pattern where env is `preprod` or `prod`
- **FR-003**: System MUST reject legacy `sentiment-analyzer-*` naming patterns as non-compliant
- **FR-004**: System MUST cross-reference all Terraform resources against IAM ARN patterns
- **FR-005**: System MUST detect orphaned IAM patterns that reference non-existent resources
- **FR-006**: System MUST unskip and enable the 6 previously skipped validation tests

**Part B: JWT Authentication**

- **FR-007**: System MUST validate JWT tokens in the Authorization header for authenticated sessions
- **FR-008**: System MUST reject expired JWT tokens with appropriate HTTP status (401)
- **FR-009**: System MUST reject malformed JWT tokens without exposing internal details
- **FR-010**: System MUST validate JWT signature against configured secret
- **FR-011**: System MUST remove the TODO comment after implementation is complete
- **FR-012**: JWT access tokens MUST expire after 15 minutes; refresh tokens MUST be supported for session continuity

### Key Entities

- **TerraformResource**: Represents an infrastructure resource extracted from Terraform files (name, type, module path)
- **IAMPattern**: Represents an ARN pattern from IAM policies (pattern string, policy source, resource type)
- **JWTClaim**: Represents validated claims from a JWT token (subject, expiration, issued-at, custom claims)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 6 resource naming tests execute successfully (not skipped) and pass
- **SC-002**: JWT validation is implemented with 100% test coverage for the authentication path
- **SC-003**: Zero new suppressions (nosec, noqa, type:ignore) are added to the codebase
- **SC-004**: `make validate` passes on the target repo with zero failures
- **SC-005**: Resource naming validator detects 100% of intentionally misnamed test fixtures
- **SC-006**: JWT validation handles at least 1000 token validations per second without degradation

## Implementation

### Completed

- `src/validators/resource_naming.py` - Resource naming validation (FR-001, FR-002, FR-003)
  - `extract_resources()` - Extract resources from Terraform
  - `validate_naming_pattern()` - Validate against `{env}-sentiment-{service}`
  - `TerraformResource` dataclass
  - `ValidationResult` dataclass
- `src/validators/iam_coverage.py` - IAM coverage validation (FR-004, FR-005)
  - `extract_iam_patterns()` - Extract ARN patterns from policies
  - `check_coverage()` - Cross-reference resources against patterns
  - `IAMPattern` dataclass
  - `CoverageReport` dataclass

### Pending

- JWT Authentication (FR-007 through FR-012) - Not yet implemented

## Assumptions

- The `{env}-sentiment-{service}` pattern is the canonical naming standard for all resources
- JWT secret will be provided via environment variable or secrets manager
- Terraform files follow standard HCL syntax and can be parsed with existing tools
- The 6 skipped tests have correct assertions and only need implementation to pass
