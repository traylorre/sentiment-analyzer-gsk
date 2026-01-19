# Feature Specification: Remove CloudFront from GitHub Workflows

**Feature Branch**: `1205-remove-cloudfront-from-workflows`
**Created**: 2026-01-18
**Status**: Complete
**Input**: Part of CloudFront removal workplan (Feature 4 of 8)

## Summary

Remove all CloudFront-related steps and references from GitHub Actions workflows.

## Changes

### .github/workflows/deploy.yml

**Preprod deploy job:**
- Remove "Fix CloudFront Invalid Timeout (AWS CLI)" step
- Remove "Reset CloudFront Terraform State" step
- Remove cloudfront_distribution_id from Get Preprod Outputs
- Remove CloudFront cache invalidation from Deploy Dashboard to S3

**Prod deploy job:**
- Remove "Fix CloudFront Invalid Timeout (AWS CLI)" step
- Remove "Reset CloudFront Terraform State" step

**Updated comments:**
- Smoke Test: Updated comment to reference Amplify
- Canary: Updated comment to reference Amplify

## Acceptance Criteria

- [x] No CloudFront operational steps remain in workflows
- [x] No cloudfront_distribution_id outputs or variables
- [x] Comments reference Amplify instead of CloudFront
- [x] Feature 1205 audit trail comments added

## Out of Scope

- Terraform module changes (Feature 1203)
- tfvars changes (Feature 1204)
- Application code changes (Feature 5)
