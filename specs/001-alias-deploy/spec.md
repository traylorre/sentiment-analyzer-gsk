# Feature Specification: Alias-Based Lambda Deployment for Function URL Stability

**Feature Branch**: `001-alias-deploy`
**Created**: 2026-03-18
**Status**: Draft
**Input**: Feature 1224.4 — Alias-Based Lambda Deployment for Function URL Stability

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zero-Downtime Deploy (Priority: P1)

The operations team merges code to main and the deploy pipeline runs. After the pipeline completes, the dashboard and SSE endpoints are immediately accessible — no 404 window, no manual retry, no waiting. The smoke test passes on the first attempt.

**Why this priority**: 6 consecutive deploy failures caused by Function URL 404 propagation delay. This is the root cause fix — the current architecture is fundamentally incompatible with reliable CI/CD.

**Independent Test**: Deploy a code change and verify the smoke test passes on attempt 1 with HTTP 200 from the Function URL.

**Acceptance Scenarios**:

1. **Given** a new container image is deployed, **When** the pipeline completes the alias flip, **Then** the Function URL returns HTTP 200 within 30 seconds (not 2-5 minutes).
2. **Given** the deploy is in progress, **When** the old version is still serving via the alias, **Then** users experience zero interruption — the old version serves all requests until the new version is confirmed healthy.
3. **Given** the pre-warm of the new version fails, **When** the alias flip is skipped, **Then** the old version continues serving and the deploy is marked as failed without impacting users.

---

### User Story 2 - Rollback Capability (Priority: P2)

If a newly deployed version has a runtime error that the smoke test doesn't catch, the operations team can roll back to the previous version by flipping the alias to the prior version number. No redeployment or image rebuild needed.

**Why this priority**: Currently there is no fast rollback — rolling back requires re-running the entire deploy pipeline with an older commit. Alias-based deployment gives instant rollback by pointing the alias at the previous version.

**Independent Test**: Deploy a broken version, then flip the alias back to the previous version number and verify the endpoint recovers within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a deployment introduced a runtime error, **When** the operations team updates the alias to the previous version, **Then** the Function URL serves the previous healthy version within 30 seconds.

---

### Edge Cases

- What if the Lambda has never been published (no versions exist)? The first deploy must publish version 1 and create the alias.
- What if `publish-version` fails? The alias stays on the old version. Deploy fails safely.
- What if the pre-warm of the new version returns an error? The alias is NOT flipped. Old version continues serving. Deploy is marked as failed.
- What if SSE Lambda's streaming invoke mode conflicts with alias configuration? Function URL invoke mode is set on the URL resource, not the alias — no conflict expected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The deploy pipeline MUST publish an immutable version of the Lambda function after updating the code, before flipping traffic.
- **FR-002**: The deploy pipeline MUST pre-warm the new version (via direct invoke with the version qualifier) and verify it returns a healthy response before flipping the alias.
- **FR-003**: The deploy pipeline MUST update the alias to point to the new version only after pre-warm succeeds. If pre-warm fails, the alias MUST remain on the old version.
- **FR-004**: The Function URL MUST be attached to the alias, not to the unqualified function ($LATEST).
- **FR-005**: The Function URL's public endpoint (the URL string) MUST NOT change as a result of this migration.
- **FR-006**: Both Dashboard and SSE Lambdas with Function URLs MUST use the alias-based deployment pattern.
- **FR-007**: The CI deploy user MUST have permissions to publish versions and update aliases.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Deploy smoke test passes on the first attempt (HTTP 200 from Function URL within 30 seconds of alias flip).
- **SC-002**: Zero user-visible downtime during deployments — old version serves until alias flips.
- **SC-003**: Rollback to previous version completes within 30 seconds (alias update, no rebuild).
- **SC-004**: The Function URL endpoint string does not change after migration.
- **SC-005**: All existing tests continue to pass.

## Assumptions

- Lambda Function URLs support being attached to aliases (confirmed in AWS documentation).
- The Function URL endpoint string is determined by the URL resource, not the qualifier — attaching to an alias does not change the URL.
- The CI deploy IAM user already has `lambda:UpdateFunctionCode` and `lambda:InvokeFunction`. It needs `lambda:PublishVersion` and `lambda:UpdateAlias` added.
- The initial migration will require a one-time Terraform state operation to move the Function URL from the unqualified function to the alias without destroying and recreating it.
- Provisioned concurrency is not required for this feature (nice-to-have for production, out of scope here).
