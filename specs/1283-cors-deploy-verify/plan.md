# Implementation Plan: Verify CORS Fixes Deployed

**Branch**: `1283-cors-deploy-verify` | **Date**: 2026-03-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1283-cors-deploy-verify/spec.md`

## Summary

Operational verification that CORS fix PRs #832-#834 are deployed and functional. Run existing Playwright tests against preprod to confirm credentialed API calls succeed, document production deployment blockers, and update the Gameday Readiness Assessment. No code changes -- this is a verification and documentation feature.

## Technical Context

**Language/Version**: N/A (operational verification, no new code)
**Primary Dependencies**: Playwright (existing tests), `gh` CLI (GitHub API), AWS credentials (preprod access)
**Storage**: N/A
**Testing**: Existing `sanity.spec.ts`, `cors-headers.spec.ts` run against preprod
**Target Platform**: Preprod environment (Amplify + Lambda Function URLs)
**Project Type**: Operational verification
**Performance Goals**: N/A
**Constraints**: Requires preprod AWS credentials and `PREPROD_FRONTEND_URL` env var (FR-005). If unavailable, feature is BLOCKED.
**Scale/Scope**: Run existing tests, inspect 2 config files, update 1 assessment document

## Constitution Check

- No new production code
- No infrastructure changes
- No cost impact
- Documentation deliverables only

## Project Structure

### Documentation (this feature)

```text
specs/1283-cors-deploy-verify/
├── spec.md              # Feature specification
├── plan.md              # This file
└── tasks.md             # Task list
```

### Files to Inspect (READ ONLY)

```text
# Target repo (sentiment-analyzer-gsk)
frontend/tests/e2e/
├── sanity.spec.ts              # Existing sanity tests (run against preprod)
└── cors-headers.spec.ts        # CORS-specific header tests (run against preprod)

infra/
├── prod.tfvars                 # Check enable_amplify, cors_allowed_origins
└── ...

.github/workflows/
└── deploy.yml                  # Check production job `if: false` flags

# Security repo (sentiment-analyzer-gsk-security)
GAMEDAY_READINESS_ASSESSMENT_2026-03-26.md   # Update with verification results
```

**Structure Decision**: No new files created in the codebase. Deliverables are: test execution results, production blocker documentation (in tasks.md findings), and updated Gameday Readiness Assessment in the security repo.

## Key Design Decisions

1. **No new tests**: The existing `sanity.spec.ts` and `cors-headers.spec.ts` already verify CORS behavior via credentialed API calls. Running them against preprod is sufficient.

2. **CORS-specific pass criteria**: SC-001 scopes to "zero CORS-related network failures" not "all tests pass." A non-CORS failure (e.g., data loading) does not block this feature.

3. **Credential gate**: FR-005 requires documenting credential requirements upfront. If preprod access is unavailable, the feature is explicitly BLOCKED -- not silently skipped.

4. **Production blockers as documentation**: US2 is deliberately a documentation task. The deliverable is a concrete checklist of what must change in `prod.tfvars` and `deploy.yml` before production deployment can proceed.
