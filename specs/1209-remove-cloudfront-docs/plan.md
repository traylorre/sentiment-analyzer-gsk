# Implementation Plan: Remove CloudFront References from Documentation

**Branch**: `1209-remove-cloudfront-docs` | **Date**: 2026-01-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1209-remove-cloudfront-docs/spec.md`

## Summary

Remove all references to CloudFront as an actively-deployed component from documentation files. CloudFront was removed in Features 1203-1207 and replaced by AWS Amplify for frontend hosting. Lambda Function URLs are now the direct API entry points. This is a documentation-only update affecting 11 files including README.md, architecture diagrams, operational runbooks, and security analysis documents.

## Technical Context

**Language/Version**: Markdown, Mermaid (documentation syntax)
**Primary Dependencies**: N/A (documentation-only, no code dependencies)
**Storage**: N/A (file-based documentation)
**Testing**: Mermaid syntax validation (npx @mermaid-js/mermaid-cli), markdown link checking
**Target Platform**: Documentation files (GitHub-rendered markdown)
**Project Type**: Documentation update
**Performance Goals**: N/A
**Constraints**: All Mermaid diagrams must render valid syntax after modifications
**Scale/Scope**: 11 documentation files, ~40 CloudFront references total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Section | Applicable? | Status | Notes |
|---------------------|-------------|--------|-------|
| 1) Functional Requirements | No | N/A | Documentation-only change |
| 2) Non-Functional Requirements | No | N/A | No service changes |
| 3) Security & Access Control | No | N/A | No code changes |
| 4) Data & Model Requirements | No | N/A | No data changes |
| 5) Deployment Requirements | No | N/A | No infrastructure changes |
| 6) Observability & Monitoring | No | N/A | No telemetry changes |
| 7) Testing & Validation | Partial | PASS | Mermaid syntax validation required |
| 8) Git Workflow & CI/CD Rules | Yes | PASS | GPG-signed commits, feature branch |
| Design & Diagrams (Canva preferred) | Partial | PASS | Updating existing Mermaid diagrams |

**Gate Status**: PASS - Documentation-only change with minimal constitution overlap.

## Project Structure

### Documentation (this feature)

```text
specs/1209-remove-cloudfront-docs/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (diagram analysis)
├── checklists/          # Validation checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Target Files (repository root)

```text
# Files to Update (11 total)

# Primary Documentation
README.md                                    # 6 CloudFront references
DEMO_URLS.local.md                          # 1 CloudFront URL reference

# Architecture Diagrams (Mermaid)
docs/diagrams/sse-lambda-streaming.mmd      # CloudFront participant
docs/diagrams/security-flow.mmd            # ZONE 0 CloudFront boundary
docs/diagrams/dataflow-all-flows.mmd       # CloudFront in Edge Layer
docs/architecture.mmd                       # CloudFront CDN subgraph

# Security Analysis (Clarifications needed)
docs/DASHBOARD_SECURITY_ANALYSIS.md         # CloudFront recommendations
docs/API_GATEWAY_GAP_ANALYSIS.md           # CloudFront cost options

# Operational Documentation
docs/runbooks/scaling.md                    # CloudFront in architecture table
docs/PRODUCTION_PREFLIGHT_CHECKLIST.md     # CloudFront CORS reference

# Use Case Diagrams
docs/USE-CASE-DIAGRAMS.md                   # CloudFront in auth sequence
```

**Structure Decision**: Documentation-only update. No source code changes required.

## Complexity Tracking

No complexity violations - this is a straightforward documentation update.

## Phase 0: Research Summary

### R-001: Current Amplify Architecture

**Decision**: Document frontend as "AWS Amplify (Next.js SSR)" serving directly to users.
**Rationale**: Terraform confirms `module.amplify_frontend[0]` with `platform = "WEB_COMPUTE"` for SSR.
**Alternatives Considered**: None - Amplify is the deployed solution.

### R-002: Lambda Function URL Direct Access

**Decision**: Document APIs as "Lambda Function URLs" without CDN layer.
**Rationale**: Dashboard and SSE Lambda both expose Function URLs directly. No API Gateway or CloudFront in front.
**Alternatives Considered**: None - this is the current deployed architecture.

### R-003: Security Boundary Redesign

**Decision**: Replace "ZONE 0: CloudFront" with "Edge: Lambda Function URL IAM + Amplify".
**Rationale**: Lambda Function URLs have IAM auth_type, Amplify provides managed HTTPS. Security boundary is at Lambda/Amplify level.
**Alternatives Considered**: Could mark as "No Edge CDN" but this is less descriptive.

### R-004: SSE Streaming Timeout Handling

**Decision**: Remove CloudFront 60s timeout references. Lambda Function URLs have 15-minute timeout by default.
**Rationale**: Custom runtime handles RESPONSE_STREAM mode with longer timeouts than CloudFront supported.
**Alternatives Considered**: None - CloudFront timeout workarounds are no longer needed.

### R-005: Gap Analysis Documents Treatment

**Decision**: Add "Note: CloudFront is not currently deployed" clarification; keep recommendations as future options.
**Rationale**: Gap analysis documents are planning documents. Removing CloudFront options would reduce future flexibility.
**Alternatives Considered**: Could remove CloudFront sections entirely, but this loses valuable cost analysis.

## Phase 1: Design

### Data Model

N/A - Documentation-only change. No data entities affected.

### Contracts

N/A - No API contracts affected. This is documentation update only.

### Diagram Update Strategy

For each Mermaid diagram:

1. **sse-lambda-streaming.mmd**: Remove `participant CF` and update flow to show Browser → Lambda Function URL directly
2. **security-flow.mmd**: Replace ZONE 0 CloudFront subgraph with "Lambda Function URL Security" (IAM, CORS, HTTPS)
3. **dataflow-all-flows.mmd**: Remove CF from Edge Layer, keep Amplify as frontend delivery
4. **architecture.mmd**: Remove CloudFront CDN subgraph, update flows to show direct Lambda connections
5. **USE-CASE-DIAGRAMS.md**: Update auth sequence to show Amplify serving SPA, then direct Lambda calls

### Validation Requirements

1. **Mermaid Syntax**: Run `npx @mermaid-js/mermaid-cli -i <file> -o /tmp/test.svg` for each .mmd file
2. **Link Checking**: Verify no broken internal links after removing CloudFront routing diagram reference
3. **Visual Review**: Render each diagram to confirm flows make logical sense

## Quickstart

### Prerequisites

- Access to sentiment-analyzer-gsk repository
- Mermaid CLI for validation: `npm install -g @mermaid-js/mermaid-cli`

### Steps

1. Update README.md architecture section (6 references)
2. Update DEMO_URLS.local.md (1 reference)
3. Update each Mermaid diagram (4 files)
4. Add clarifications to security analysis docs (2 files)
5. Update operational docs (2 files)
6. Update USE-CASE-DIAGRAMS.md (1 file)
7. Validate all Mermaid diagrams render correctly
8. Verify no broken links

### Validation

```bash
# Validate Mermaid syntax for all diagrams
for f in docs/diagrams/*.mmd docs/architecture.mmd; do
  npx @mermaid-js/mermaid-cli -i "$f" -o /tmp/$(basename "$f" .mmd).svg && echo "✓ $f" || echo "✗ $f"
done

# Check for remaining CloudFront-as-deployed references
grep -rn "CloudFront" README.md docs/ --include="*.md" --include="*.mmd" | grep -v "proposed\|future\|option\|recommend"
```
