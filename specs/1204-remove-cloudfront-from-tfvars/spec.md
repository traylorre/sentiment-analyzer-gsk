# Feature Specification: Remove CloudFront from tfvars

**Feature Branch**: `1204-remove-cloudfront-from-tfvars`
**Created**: 2026-01-18
**Status**: Complete
**Input**: Part of CloudFront removal workplan (Feature 3 of 8)

## Summary

Remove CloudFront URLs from terraform.tfvars files and update CORS comments to reference Amplify instead of CloudFront.

## Changes

### preprod.tfvars
- Remove `https://d2z9uvoj5xlbd2.cloudfront.net` from cors_allowed_origins
- Update CORS comment to reference Amplify instead of CloudFront

### prod.tfvars
- Update CORS documentation comments to reference Amplify domain
- Update example URLs to show Amplify format

## Acceptance Criteria

- [ ] No CloudFront URLs remain in cors_allowed_origins
- [ ] Comments reference Amplify instead of CloudFront
- [ ] Feature 1204 audit trail comments added

## Out of Scope

- Terraform module changes (Feature 1203)
- Workflow changes (Feature 4)
- Application code changes (Feature 5)
