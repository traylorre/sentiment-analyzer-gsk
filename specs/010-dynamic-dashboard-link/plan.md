# Implementation Plan: Dynamic Dashboard Link

**Branch**: `feat/010-dynamic-dashboard-link` | **Date**: 2025-11-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-dynamic-dashboard-link/spec.md`

## Summary

Add a dynamic "View Live Dashboard" link to the interview dashboard (`interview/index.html`) that updates when the preprod/prod toggle is triggered. The link should display the last deployment date for the selected environment. Deployment metadata will be generated during CI/CD and fetched client-side.

## Technical Context

**Language/Version**: JavaScript (ES6+) embedded in HTML, GitHub Actions YAML
**Primary Dependencies**: Static HTML/CSS/JS, GitHub Pages, GitHub Actions
**Storage**: N/A (metadata JSON file fetched from S3 or repo)
**Testing**: Existing `tests/unit/interview/test_interview_html.py` unit tests
**Target Platform**: Web browser (GitHub Pages static hosting)
**Project Type**: Static single-page application
**Performance Goals**: Instant toggle response, <1s metadata fetch
**Constraints**: No server-side processing (static hosting), GitHub API rate limits
**Scale/Scope**: Single HTML file modification + CI/CD workflow update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: No secrets in source | PASS | URLs are public, no auth needed for dashboard link |
| Testing: Unit tests for new code | PASS | Will add tests for new JS functions |
| CI/CD: No pipeline bypass | PASS | Follows standard merge workflow |
| Observability: Structured logging | N/A | Client-side static HTML |
| Documentation: No raw text exposure | PASS | No sensitive data involved |

## Project Structure

### Documentation (this feature)

```text
specs/010-dynamic-dashboard-link/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Research on implementation approach
└── quickstart.md        # Implementation quickstart
```

### Source Code (repository root)

```text
interview/
├── index.html           # Modified: Add dashboard link and last-deployed display

.github/workflows/
└── deploy.yml           # Modified: Generate deployment metadata JSON

infrastructure/terraform/
└── (no changes needed)
```

**Structure Decision**: Single file modification to interview dashboard HTML + CI/CD metadata generation. No new directories or complex structure needed.

## Complexity Tracking

No constitution violations - simple feature addition.

## Phase 0: Research

See [research.md](./research.md) for implementation approach decisions.

## Phase 1: Design

### Approach Selected: CI/CD Generated Metadata

During the deploy workflow, generate a JSON metadata file with deployment info. Store in S3 bucket accessible via HTTPS. The interview dashboard fetches this on load and toggle.

### Implementation Steps

1. **Modify deploy.yml workflow**
   - Add step after successful deploy to generate `deployment-metadata.json`
   - Upload to S3 bucket with public read access
   - Include: environment, timestamp, git SHA, dashboard URL

2. **Modify interview/index.html**
   - Add "View Live Dashboard" link element in header
   - Add "Last deployed: ..." text element
   - Modify `initEnvToggle()` to fetch metadata on toggle
   - Add `fetchDeploymentMetadata(env)` function
   - Add `updateDashboardLink(metadata)` function

3. **Update tests**
   - Add tests for new HTML elements
   - Add tests for new JS function definitions
