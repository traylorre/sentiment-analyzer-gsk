# Tasks: Fix README Mermaid Diagram

## Completed Tasks

- [x] T-001: Analyze failing Mermaid diagrams - Found 3 diagrams with `%%{init:...}%%` directives
- [x] T-002: Research GitHub Mermaid limitations - Confirmed themeVariables support is limited
- [x] T-003: Review deploy.yml to understand actual pipeline structure - No Dev environment
- [x] T-004: Create spec.md with problem analysis and solution design
- [x] T-005: Fix CI/CD Pipeline Status diagram (lines 18-60)
  - Removed `%%{init:...}%%` directive
  - Updated to reflect actual pipeline (Build → Test → Images → Preprod → Prod)
  - Removed non-existent "Dev Stage"
  - Fixed badge URLs (pr-check-*.yml → pr-checks.yml)
- [x] T-006: Fix High-Level System Architecture diagram (line 187)
  - Removed `%%{init:...}%%` directive
  - Kept classDef styling (GitHub supports this)
- [x] T-007: Fix Environment Promotion Pipeline diagram (lines 287-333)
  - Removed `%%{init:...}%%` directive
  - Updated to reflect 2-environment flow (preprod + prod only)
  - Added Canary Test stage
  - Simplified styling

## Verification

- [ ] T-008: Push to branch and verify diagrams render on GitHub
- [ ] T-009: Create PR with before/after screenshots
