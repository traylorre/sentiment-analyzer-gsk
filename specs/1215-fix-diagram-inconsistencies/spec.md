# Feature Specification: Fix Architecture Diagram Inconsistencies

**Feature Branch**: `1215-fix-diagram-inconsistencies`
**Created**: 2026-01-20
**Status**: Draft
**Input**: User description: "Fix architecture diagram inconsistencies: (1) README.md inline mermaid diagram has undefined CF node at lines 248-252, 314 - must remove CloudFront and show direct Browser→Amplify for static, Browser→APIGW for API, Browser→SSELambda for streaming; (2) docs/diagrams/architecture.mmd line 5 shows NewsAPI but actual data sources are Tiingo+Finnhub - must match README high-level diagram; (3) src/README.md, src/lambdas/README.md, src/lambdas/ingestion/README.md have stale NewsAPI references; (4) mermaid.live link badge must be regenerated from corrected architecture.mmd. CONTEXT: CloudFront removed in Features 1203-1208, NewsAPI replaced by Tiingo/Finnhub in Feature 006."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developers View Accurate Architecture (Priority: P1)

A developer opens the repository README to understand the system architecture. They see diagrams that accurately reflect how the system is built today: Amplify serves the frontend directly, API Gateway handles API requests, and SSE Lambda handles streaming - with no CloudFront intermediary. Data sources show Tiingo (primary) and Finnhub (secondary) for financial news, not the deprecated NewsAPI.

**Why this priority**: Architecture diagrams are the first thing developers see. Inaccurate diagrams cause confusion, wasted investigation time, and incorrect assumptions during development. This directly impacts developer productivity and system understanding.

**Independent Test**: Can be fully tested by opening README.md in GitHub or locally and verifying diagrams render correctly with current architecture components.

**Acceptance Scenarios**:

1. **Given** a developer views README.md, **When** they examine the High-Level System Architecture diagram, **Then** they see Browser connecting directly to Amplify, APIGW, and SSELambda without any CloudFront (CF) intermediary.
2. **Given** a developer views README.md, **When** they examine the External Sources section of the diagram, **Then** they see Tiingo API and Finnhub API as data sources, not NewsAPI.
3. **Given** a developer views the mermaid.live interactive diagram badge, **When** they click it, **Then** they see the same architecture without CF or NewsAPI.

---

### User Story 2 - Onboarding Engineers Understand Data Flow (Priority: P2)

A new engineer joins the team and reads the src/ documentation to understand the Lambda architecture. The documentation accurately describes that the ingestion Lambda fetches financial news from Tiingo and Finnhub APIs, not from a deprecated NewsAPI service.

**Why this priority**: Incorrect documentation in source directories leads new engineers down wrong paths when debugging or extending the system. They may look for NewsAPI adapters that no longer exist or misunderstand rate limits.

**Independent Test**: Can be tested by reading src/README.md and src/lambdas/ingestion/README.md and verifying all data source references match the actual adapters in code.

**Acceptance Scenarios**:

1. **Given** an engineer reads src/README.md, **When** they look at the directory structure explanation, **Then** the ingestion directory is described as "Tiingo + Finnhub financial news ingestion" not "NewsAPI data ingestion".
2. **Given** an engineer reads src/lambdas/ingestion/README.md, **When** they see data flow examples, **Then** all references show Tiingo/Finnhub as sources with their actual rate limits (Tiingo: 500 req/day, Finnhub: 60 req/min).

---

### User Story 3 - Architecture Diagrams Stay Synchronized (Priority: P3)

The architecture.mmd source file and the README inline diagram show identical architecture. The mermaid.live badge URL is regenerated from the corrected source, ensuring all three representations are consistent.

**Why this priority**: Having multiple diagram sources that diverge creates maintenance burden and confusion. A single source of truth prevents future drift.

**Independent Test**: Can be tested by comparing the External Services subgraph in architecture.mmd with the External Sources subgraph in README.md - they should show the same nodes.

**Acceptance Scenarios**:

1. **Given** the architecture.mmd file is corrected, **When** compared to README.md High-Level diagram, **Then** both show identical External data sources (Tiingo, Finnhub) and identical request flow (no CF).
2. **Given** the mermaid.live badge URL, **When** decoded, **Then** it represents the same diagram as shown in README.md inline.

---

### User Story 4 - Maintainers Regenerate Mermaid Links Reliably (Priority: P1)

A maintainer updates architecture diagrams and needs to regenerate the mermaid.live badge URL. They run a single command that reads the source diagram, applies the standard dark theme, and outputs the correctly-encoded URL. No manual encoding, no theme issues, no churn.

**Why this priority**: Mermaid.live link regeneration has been a source of significant churn - theme inconsistencies, encoding errors, and manual copy-paste mistakes. Automating this eliminates an entire class of errors and saves hours of debugging.

**Independent Test**: Can be tested by running `make regenerate-mermaid-url` and verifying the output URL renders correctly in mermaid.live with the dark theme applied.

**Acceptance Scenarios**:

1. **Given** a maintainer has updated architecture.mmd, **When** they run `make regenerate-mermaid-url`, **Then** the command outputs a valid mermaid.live URL that renders the diagram with the standard dark theme.
2. **Given** the regenerated URL, **When** opened in a browser, **Then** the diagram displays with correct dark theme colors (dark background, white text, styled nodes).
3. **Given** the docs/diagrams/TEMPLATE.md theme configuration, **When** URL is generated, **Then** the theme variables from TEMPLATE.md are embedded in the pako payload.

---

### Edge Cases

- What happens when mermaid syntax is invalid after edits? All edits must preserve valid mermaid syntax that renders without errors.
- How does the system handle the edgeStyle class after CF removal? The edgeStyle class definition remains but only applies to Amplify and APIGW nodes.
- What happens if mermaid.live URL generation fails? The script must validate mermaid syntax before encoding and report errors clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: README.md diagram MUST remove all CF (CloudFront) node references at lines 248, 250-252, and 314.
- **FR-002**: README.md diagram MUST show Browser connecting directly to Amplify for static content delivery.
- **FR-003**: README.md diagram MUST show Browser connecting directly to APIGW for API requests (/api/*).
- **FR-004**: README.md diagram MUST show Browser connecting directly to SSELambda for streaming (/api/v2/stream*).
- **FR-005**: docs/diagrams/architecture.mmd MUST replace NewsAPI node with Tiingo and Finnhub nodes in External Services subgraph.
- **FR-006**: docs/diagrams/architecture.mmd External Services subgraph MUST match README.md External Sources subgraph structure.
- **FR-007**: src/README.md MUST update line 8 from "NewsAPI data ingestion" to "Tiingo + Finnhub financial news ingestion".
- **FR-008**: src/lambdas/ingestion/README.md MUST replace all NewsAPI references (lines 5, 14, 34, 60-63) with Tiingo/Finnhub references.
- **FR-009**: README.md mermaid.live badge URL MUST be regenerated to encode the corrected diagram.
- **FR-010**: All modified mermaid diagrams MUST validate and render correctly in GitHub markdown preview.
- **FR-011**: The edgeStyle class MUST be updated to apply only to Amplify and APIGW after CF removal.
- **FR-012**: A script MUST exist at `scripts/regenerate-mermaid-url.py` that reads a .mmd file and outputs a mermaid.live URL with dark theme embedded.
- **FR-013**: A make target `regenerate-mermaid-url` MUST invoke the script with the high-level architecture diagram as default input.
- **FR-014**: The URL generation script MUST use the theme configuration from docs/diagrams/TEMPLATE.md to ensure consistency.
- **FR-015**: The script MUST validate mermaid syntax before encoding and exit with error if invalid.

### Key Entities

- **README.md High-Level System Architecture Diagram**: The primary inline mermaid diagram showing system components and data flow. Located at lines 191-316.
- **architecture.mmd**: Source diagram file in docs/diagrams/ that should serve as reference for detailed architecture. Currently shows NewsAPI incorrectly.
- **Mermaid.live Badge**: A clickable badge in README.md that links to an interactive pan/zoom version of the architecture diagram using pako-encoded URL.
- **External Sources/Services**: The subgraph showing external data providers - should be Tiingo (Financial News) and Finnhub (Market Data).
- **regenerate-mermaid-url.py**: New script that reads .mmd files and generates mermaid.live URLs with consistent dark theme.
- **docs/diagrams/TEMPLATE.md**: Existing template file containing canonical dark theme configuration and Python snippet for URL generation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All mermaid diagrams render without syntax errors in GitHub markdown preview.
- **SC-002**: Zero references to "CF" or "CloudFront" exist in README.md diagram sections.
- **SC-003**: Zero references to "NewsAPI" exist in any architecture diagrams or src/ documentation.
- **SC-004**: The mermaid.live interactive diagram shows identical architecture to README.md inline diagram.
- **SC-005**: A grep search for "NewsAPI" in src/README.md, src/lambdas/README.md, and src/lambdas/ingestion/README.md returns zero matches.
- **SC-006**: A grep search for "CloudFront\|CF\[" in README.md mermaid blocks returns zero matches.
- **SC-007**: Running `make regenerate-mermaid-url` produces a URL that renders correctly in mermaid.live with dark theme.
- **SC-008**: The regenerated URL when decoded contains the same diagram content as the source .mmd file.

## Assumptions

- The actual architecture uses Amplify for frontend hosting (confirmed by Feature 1203-1208 completion).
- Tiingo and Finnhub are the only external data sources (confirmed by Feature 006 and existing adapters in src/lambdas/shared/adapters/).
- The mermaid.live badge uses pako encoding for the diagram URL.
- Rate limits are: Tiingo 500 requests/day, Finnhub 60 requests/minute (based on adapter implementations).

## Out of Scope

- Changes to actual infrastructure code (Terraform, Lambda code).
- Changes to the architecture itself - this is documentation-only.
- Other CloudFront references in security analysis docs that are clearly marked as "future recommendations".
- Regenerating any diagrams beyond the ones explicitly listed.
