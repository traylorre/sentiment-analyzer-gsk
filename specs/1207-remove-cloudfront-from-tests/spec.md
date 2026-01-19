# Feature Specification: Remove CloudFront from Tests

**Feature Branch**: `1207-remove-cloudfront-from-tests`
**Created**: 2026-01-18
**Status**: Complete
**Input**: Part of CloudFront removal workplan (Feature 6 of 8)

## Summary

Remove CloudFront references from test files and update interview HTML to use Amplify URLs.

## Changes

### tests/e2e/test_sse_connection_preprod.py
- Update comment about Content-Type to remove CloudFront reference

### tests/fixtures/validators/preprod_env_validator.py
- Replace CloudFront URL pattern with Amplify pattern
- Update comment to reference Amplify
- Update error message to mention Amplify instead of CloudFront

### tests/unit/fixtures/test_preprod_env_validator.py
- Rename test_valid_cloudfront_url to test_valid_amplify_url
- Update test to use Amplify URL pattern

### tests/unit/interview/test_interview_html.py
- Update test_preprod_url_defined to check for Amplify URL

### tests/unit/dashboard/test_samesite_none.py
- Update docstring to reference Amplify instead of CloudFront

### interview/index.html
- Update ENVIRONMENTS config to use Amplify URL
- Update directory tree: cloudfront/ -> amplify/
- Update Environment Parity table: CloudFront CDN -> Amplify Hosting

### interview/FUTURE_IMPROVEMENTS.md
- Mark CloudFront ONE URL feature as superseded by Feature 1207

## Acceptance Criteria

- [x] No functional CloudFront references in tests directory
- [x] Interview HTML uses Amplify URL
- [x] URL validator accepts Amplify URLs
- [x] Test assertions check for Amplify patterns

## Out of Scope

- Architecture diagrams (Feature 7)
