# Feature Specification: Remove CloudFront References from Documentation

**Feature Branch**: `1209-remove-cloudfront-docs`
**Created**: 2026-01-19
**Status**: Draft
**Input**: User description: "Remove CloudFront references from remaining documentation files. CloudFront was removed in Features 1203-1207 and Amplify now serves frontend directly."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Reads Accurate Architecture (Priority: P1)

A developer new to the project reads the README and documentation to understand how the system works. They need accurate information about the current architecture to make informed decisions about code changes and troubleshooting.

**Why this priority**: Inaccurate documentation leads to wasted time, incorrect assumptions, and potential production issues. README.md is the first thing developers see.

**Independent Test**: Can be fully tested by reading README.md and verifying all architecture descriptions match the deployed infrastructure (Amplify frontend, Lambda Function URLs).

**Acceptance Scenarios**:

1. **Given** a developer opens README.md, **When** they read the Architecture section, **Then** they see Amplify described as the frontend hosting solution with no CloudFront references as active components.
2. **Given** a developer views the architecture diagram in README.md, **When** they trace the request flow, **Then** the diagram shows requests going to Amplify and Lambda Function URLs (not through CloudFront).

---

### User Story 2 - Operations Engineer Uses Runbooks (Priority: P2)

An operations engineer uses scaling runbooks and preflight checklists during incident response or deployment preparation. They need documentation that reflects actual infrastructure components.

**Why this priority**: Inaccurate operational docs during an incident causes confusion and delays resolution. Incorrect component lists lead to troubleshooting non-existent services.

**Independent Test**: Can be tested by following scaling runbook procedures and verifying all referenced components exist in the deployed infrastructure.

**Acceptance Scenarios**:

1. **Given** an ops engineer opens docs/runbooks/scaling.md, **When** they review the architecture table, **Then** they see Amplify listed for frontend hosting (not CloudFront as CDN).
2. **Given** an ops engineer opens docs/PRODUCTION_PREFLIGHT_CHECKLIST.md, **When** they review CORS configuration items, **Then** instructions reference Amplify domain restrictions (not CloudFront domain).

---

### User Story 3 - Architect Reviews Security Diagrams (Priority: P2)

An architect reviews security flow and dataflow diagrams to understand the current security boundaries and request routing. They need diagrams that accurately represent the deployed architecture.

**Why this priority**: Security diagrams inform threat modeling and compliance audits. Incorrect boundaries lead to missed vulnerabilities or unnecessary controls.

**Independent Test**: Can be tested by comparing diagram flows against actual AWS resource configurations.

**Acceptance Scenarios**:

1. **Given** an architect opens docs/diagrams/security-flow.mmd, **When** they review the Edge Layer, **Then** the diagram shows Lambda Function URLs and Amplify as entry points (not CloudFront as ZONE 0).
2. **Given** an architect opens docs/diagrams/dataflow-all-flows.mmd, **When** they trace API request paths, **Then** flows show direct connections to Lambda Function URLs (not routing through CloudFront).

---

### User Story 4 - Security Analyst Reviews Gap Analysis (Priority: P3)

A security analyst reviews gap analysis documents to understand current security posture and recommended improvements. They need clarity on what is currently deployed versus what is proposed for future enhancement.

**Why this priority**: Confusion between current state and recommendations leads to incorrect risk assessments and misallocated security investment.

**Independent Test**: Can be tested by verifying gap analysis documents clearly distinguish "current state" from "proposed enhancements."

**Acceptance Scenarios**:

1. **Given** an analyst reads docs/DASHBOARD_SECURITY_ANALYSIS.md, **When** they review CloudFront recommendations, **Then** the document clearly states CloudFront is a proposed future enhancement (not currently deployed).
2. **Given** an analyst reads docs/API_GATEWAY_GAP_ANALYSIS.md, **When** they review cost comparisons including CloudFront, **Then** the document indicates these are options for consideration (not current architecture).

---

### Edge Cases

- What happens when Mermaid diagram syntax is invalidated by removing nodes? Diagrams must render correctly after changes.
- How does the system handle internal documentation links that reference removed CloudFront diagrams? All links must remain valid or be updated.
- What happens to SSE streaming timeout documentation that references CloudFront-specific behavior? Must be updated to reflect Lambda Function URL timeout behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: README.md MUST describe Amplify as the frontend hosting solution in the Architecture section.
- **FR-002**: README.md architecture diagram MUST show Amplify in the Edge Layer without CloudFront as an active component.
- **FR-003**: README.md Key Features section MUST remove references to CloudFront-delivered UI and CloudFront multi-origin routing.
- **FR-004**: README.md auth flow diagram MUST remove CloudFront participant and show direct Amplify-to-Lambda flow.
- **FR-005**: DEMO_URLS.local.md MUST replace CloudFront URL with Amplify URL in the Architecture Highlights section.
- **FR-006**: docs/diagrams/sse-lambda-streaming.mmd MUST remove CloudFront participant and show browser connecting directly to Lambda Function URL.
- **FR-007**: docs/diagrams/security-flow.mmd MUST remove ZONE 0 CloudFront boundary and show Lambda Function URL security controls as the edge layer.
- **FR-008**: docs/diagrams/dataflow-all-flows.mmd MUST remove CloudFront from Edge Layer and show Amplify as the frontend delivery component.
- **FR-009**: docs/architecture.mmd MUST remove CloudFront CDN subgraph and update request flows to show direct Lambda Function URL connections.
- **FR-010**: docs/DASHBOARD_SECURITY_ANALYSIS.md MUST add clarification that CloudFront recommendations are proposed future enhancements, not current state.
- **FR-011**: docs/API_GATEWAY_GAP_ANALYSIS.md MUST add clarification that CloudFront cost options are for consideration, not currently deployed.
- **FR-012**: docs/runbooks/scaling.md MUST update architecture table to show Amplify for frontend delivery instead of CloudFront.
- **FR-013**: docs/PRODUCTION_PREFLIGHT_CHECKLIST.md MUST update CORS configuration guidance to reference Amplify domain.
- **FR-014**: docs/USE-CASE-DIAGRAMS.md MUST remove CloudFront participant from auth sequence diagram and show Amplify serving the SPA bundle.
- **FR-015**: All Mermaid diagrams MUST render valid syntax after modifications.
- **FR-016**: All internal documentation links MUST remain valid after changes.

### Key Entities

- **Documentation File**: A markdown or Mermaid file that describes system architecture or operational procedures.
- **Architecture Diagram**: A Mermaid flowchart or sequence diagram representing system components and their interactions.
- **Security Boundary**: A conceptual zone in security documentation representing a layer of defense.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero documentation files contain CloudFront as a currently-deployed active component (currently 11 files have such references).
- **SC-002**: 100% of Mermaid diagrams render without syntax errors after modifications.
- **SC-003**: Developer reading README.md can accurately describe the frontend hosting architecture within 2 minutes of reading.
- **SC-004**: Zero broken internal documentation links after changes (validated by link checker).
- **SC-005**: Security gap analysis documents clearly distinguish between "current state" and "proposed enhancements" for any CloudFront mentions.

## Assumptions

- Amplify URL format follows pattern: `main.d*.amplifyapp.com`
- Lambda Function URLs are the primary API entry points (no API Gateway in front)
- SSE streaming uses custom runtime with response streaming (no CloudFront timeout workarounds needed)
- The removal is documentation-only; no infrastructure code changes required
- Existing audit trail comments ("Feature 1203: CloudFront removed") in code should be preserved
