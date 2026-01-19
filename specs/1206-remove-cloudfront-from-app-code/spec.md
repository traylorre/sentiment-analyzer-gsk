# Feature Specification: Remove CloudFront from Application Code

**Feature Branch**: `1206-remove-cloudfront-from-app-code`
**Created**: 2026-01-18
**Status**: Complete
**Input**: Part of CloudFront removal workplan (Feature 5 of 8)

## Summary

Remove CloudFront references from Python application code comments.

## Changes

### src/lambdas/shared/middleware/rate_limit.py
- Update docstring: "API Gateway/CloudFront" -> "API Gateway/ALB"
- Update comment: "from CloudFront/ALB" -> "from ALB/API Gateway"

### src/lambdas/dashboard/router_v2.py
- Update cookie comments (2 occurrences): "CloudFront -> Lambda" -> "Amplify -> Lambda"

## Acceptance Criteria

- [x] No CloudFront references remain in src/ directory
- [x] Comments reference appropriate alternatives (Amplify, ALB, API Gateway)

## Out of Scope

- Test file changes (Feature 6)
- Documentation/diagrams (Feature 7)
