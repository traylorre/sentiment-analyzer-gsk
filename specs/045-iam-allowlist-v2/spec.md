# Feature Specification: IAM Allowlist V2 - VALIDATE2 Remediation

**Feature Branch**: `045-iam-allowlist-v2`
**Created**: 2025-12-05
**Status**: Draft
**Input**: Fix VALIDATE2 findings (5 CRITICAL, 5 HIGH) in target repo ../sentiment-analyzer-gsk

## Clarifications

### Session 2025-12-05

- Q: If multiple allowlist entries match the same finding, how should the validator behave? → A: Most specific match - select entry with most restrictive context_required conditions

## Context

VALIDATE2 baseline shows 5 CRITICAL, 5 HIGH, 6 MEDIUM findings after PR #294 merged. The IAM allowlist exists in target repo but validators are not consuming it, causing false positives for documented acceptable risks.

### Current State

- `iam-allowlist.yaml` exists with entries for LAMBDA-007, LAMBDA-011, SQS-009 (preprod)
- Validators flag these patterns regardless of allowlist documentation
- Pipeline may be blocked on IAM permission errors

### Findings Summary

| ID         | Severity | Count | Current Status                           |
| ---------- | -------- | ----- | ---------------------------------------- |
| LAMBDA-007 | CRITICAL | 4     | Documented in allowlist, not consumed    |
| LAMBDA-011 | CRITICAL | 1     | Documented in allowlist, not consumed    |
| SQS-009    | HIGH     | 3     | Partial (preprod only, missing dev)      |
| CAN-002    | HIGH     | 1     | PR description missing canonical sources |
| PROP-001   | HIGH     | 1     | Property tests failing                   |

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Validator Respects Allowlist (Priority: P1)

A security engineer runs `/validate ../sentiment-analyzer-gsk` and findings that match documented allowlist entries with valid justifications are suppressed from the CRITICAL/HIGH count.

**Why this priority**: Core functionality - validators must consume allowlist to avoid false positives on documented acceptable risks.

**Independent Test**: Run `python3 scripts/validate-runner.py --repo ../sentiment-analyzer-gsk` and verify LAMBDA-007/LAMBDA-011 findings are suppressed when allowlist entries exist with valid canonical sources.

**Acceptance Scenarios**:

1. **Given** iam-allowlist.yaml contains entry for LAMBDA-007 with canonical_source, **When** lambda-iam validator runs, **Then** matching findings are marked SUPPRESSED not FAIL
2. **Given** allowlist entry has context_required.passrole_scoped=true, **When** policy PassRole is scoped to specific roles, **Then** finding is suppressed
3. **Given** allowlist entry lacks canonical_source, **When** validator runs, **Then** finding is NOT suppressed (canonical source required per Amendment 1.5)

---

### User Story 2 - Environment-Aware SQS Suppression (Priority: P2)

SQS-009 (sqs:DeleteQueue) is flagged for dev-deployer-policy.json but should be suppressed for non-production environments where terraform destroy is legitimate.

**Why this priority**: Reduces false positive noise for expected dev/preprod permissions.

**Independent Test**: Run validator against dev-deployer-policy.json and verify SQS-009 is suppressed when environment context matches allowlist.

**Acceptance Scenarios**:

1. **Given** allowlist entry for SQS-009 with context_required.environment=[dev,preprod], **When** validator scans dev-deployer-policy.json, **Then** finding is suppressed
2. **Given** allowlist entry for SQS-009, **When** validator scans prod-deployer-policy.json, **Then** finding is NOT suppressed (prod should not have DeleteQueue)

---

### User Story 3 - Canonical Source Validation (Priority: P3)

PRs that modify IAM files must include a '## Canonical Sources Cited' section referencing AWS documentation to satisfy Amendment 1.5.

**Why this priority**: Ensures traceability and auditability of IAM decisions.

**Independent Test**: Create PR modifying IAM policy, verify CAN-002 is only raised when canonical sources section is missing.

**Acceptance Scenarios**:

1. **Given** PR modifies infrastructure/iam-policies/\*.json, **When** PR description lacks '## Canonical Sources Cited', **Then** CAN-002 finding raised
2. **Given** PR modifies IAM files, **When** PR description includes '## Canonical Sources Cited' with AWS doc links, **Then** CAN-002 not raised

---

### Edge Cases

- What happens when allowlist entry exists but canonical_source is invalid URL? Validator warns but still requires valid source
- How does system handle policy files outside infrastructure/iam-policies/? Must check ci-user-policy.tf and docs/iam-policies/ paths
- What if allowlist entry matches pattern but context_required conditions fail? Finding should NOT be suppressed
- What if multiple allowlist entries match the same finding? Use most specific match (entry with most restrictive context_required conditions)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: lambda-iam validator MUST check iam-allowlist.yaml before marking findings as FAIL
- **FR-002**: Allowlist entries MUST have canonical_source field to enable suppression (Amendment 1.5 compliance)
- **FR-003**: Context-aware suppression MUST evaluate context_required conditions (environment, passrole_scoped)
- **FR-004**: SQS-009 allowlist entry MUST cover both dev and preprod environments, NOT prod
- **FR-005**: Suppressed findings MUST appear in output with status=SUPPRESSED, not removed entirely
- **FR-006**: canonical-validate MUST check for '## Canonical Sources Cited' section in PRs modifying IAM files
- **FR-007**: Validators MUST report which allowlist entry caused suppression for auditability
- **FR-008**: When multiple allowlist entries match the same finding, validator MUST select the most specific match (entry with most restrictive context_required conditions)

### Key Entities

- **AllowlistEntry**: id, pattern, classification, finding_ids, justification, canonical_source, context_required
- **Finding**: validator, id, severity, status (FAIL|PASS|SUPPRESSED), file, line, message
- **ContextCondition**: key-value pairs evaluated against policy context (environment, passrole_scoped)

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: VALIDATE3 shows 0 CRITICAL findings (down from 5) after allowlist integration
- **SC-002**: VALIDATE3 shows at most 2 HIGH findings (down from 5) - SQS-009 suppressed, CAN-002/PROP-001 addressed
- **SC-003**: All suppressed findings include traceability to allowlist entry ID
- **SC-004**: Target repo passes template validation with exit code 0
- **SC-005**: Pipeline unblocked: Deploy to Preprod succeeds after changes merged

## Dependencies & Assumptions

### Dependencies

- lambda-iam validator exists at src/validators/lambda_iam.py
- sqs-iam-validate exists and can be extended
- iam-allowlist.yaml schema is stable (034-allowlist-architecture)

### Assumptions

- Validators are Python-based and can import allowlist parsing logic
- Target repo tests do not need modification (test failures are separate from IAM findings)
- Property test failures (PROP-001) are tracked separately from IAM remediation

## Out of Scope

- PROP-001 (property tests) - tracked in separate feature
- MEDIUM severity findings - not blocking, address in future iteration
- Mutation testing gaps (MUT-001) - methodology improvement, not this feature
