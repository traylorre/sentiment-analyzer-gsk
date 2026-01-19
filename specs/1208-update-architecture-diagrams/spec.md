# Feature Specification: Update Architecture Diagrams

**Feature Branch**: `1208-update-architecture-diagrams`
**Created**: 2026-01-18
**Status**: Complete
**Input**: Part of CloudFront removal workplan (Feature 7 of 8)

## Summary

Update architecture diagrams and documentation to remove CloudFront references and reflect Amplify as the primary frontend hosting solution.

## Changes

### Deleted Files
- `docs/diagrams/cloudfront-multi-origin.mmd` - CloudFront-specific routing diagram (obsolete)

### docs/diagrams/high-level-overview.mmd
- Remove CloudFront from entry points
- Update user request flows: Browser -> Amplify (frontend), Browser -> API Gateway (API)
- Update Amplify label from "Optional" to "Primary Frontend"
- Remove CloudFront from class definitions
- Add Feature 1208 comment noting CloudFront removal

### docs/IAM_JUSTIFICATIONS.md
- Mark IAM-002 (CloudFront Cache Policy) as SUPERSEDED
- Note that CloudFront IAM permissions have been removed

### docs/diagrams/README.md
- Update Section 5: Mark "CloudFront Multi-Origin Routing" as REMOVED
- Update heartbeat reference to remove CloudFront mention

## Remaining Documentation

The following docs still reference CloudFront but are retained for:
- Historical context (archived specs)
- Future planning reference (security analysis Phase 3)
- Gap analysis documentation

These can be updated in a follow-up cleanup task if needed:
- `docs/DASHBOARD_SECURITY_ANALYSIS.md`
- `docs/API_GATEWAY_GAP_ANALYSIS.md`
- `docs/architecture.mmd` (already deprecated)
- Various sequence diagrams in `docs/diagrams/`

## Acceptance Criteria

- [x] cloudfront-multi-origin.mmd deleted
- [x] high-level-overview.mmd updated to show Amplify as primary entry point
- [x] IAM justifications updated to note CloudFront removal
- [x] diagrams README updated with supersession note

## Out of Scope

- Provisioner validation (Feature 8)
- Full documentation audit of historical/archived files
