# Implementation Plan: Fix SRI Hash for Date Adapter

**Feature Branch**: `1086-sri-hash-fix`
**Created**: 2025-12-28

## Technical Context

- **Tech Stack**: HTML, Subresource Integrity (SRI)
- **Affected Files**: `src/dashboard/index.html`
- **Dependencies**: None

## Architecture

No architectural changes. Single attribute value update.

## File Changes

1. **index.html**: Update `integrity` attribute for chartjs-adapter-date-fns from incorrect hash to correct hash

## Implementation Strategy

1. Update integrity hash value
2. Add Feature 1086 comment for traceability
3. Verify no other CDN resources have stale hashes
