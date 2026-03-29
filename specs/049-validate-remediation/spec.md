# Feature Specification: Validation Finding Remediation

**Feature Branch**: `049-validate-remediation`
**Created**: 2025-12-05
**Status**: Draft
**Input**: Remediate validation findings from /validate run on sentiment-analyzer-gsk

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Fix Property Test Import Errors (Priority: P1)

A developer runs property tests in the target repo and all tests should pass without import errors.

**Why this priority**: Property tests are currently failing with `ModuleNotFoundError: No module named 'conftest'`. This is a P1 blocker because the tests cannot even be collected, making the entire property testing methodology unusable.

**Independent Test**: Run `pytest tests/property/ -v` and verify all tests pass

**Acceptance Scenarios**:

1. **Given** the property test files import from conftest, **When** pytest runs, **Then** all 33 property tests should be collected and execute successfully
2. **Given** the conftest.py provides Hypothesis strategies, **When** tests use these strategies, **Then** property-based testing generates valid test cases

---

### User Story 2 - Suppress SQS-009 for CI User Policy (Priority: P2)

A security validator scans the ci-user-policy.tf and correctly suppresses sqs:DeleteQueue findings that are already in the allowlist.

**Why this priority**: The SQS-009 finding for ci-user-policy.tf:177 is not being suppressed despite the allowlist entry `dev-preprod-sqs-delete` existing. This causes false positive HIGH severity findings in validation runs.

**Independent Test**: Run `/sqs-iam-validate` and verify SQS-009 findings for ci-user-policy.tf are suppressed

**Acceptance Scenarios**:

1. **Given** ci-user-policy.tf contains sqs:DeleteQueue, **When** the SQS IAM validator runs, **Then** the finding is marked as SUPPRESSED with reference to allowlist entry
2. **Given** the allowlist entry has context_required for dev/preprod environments, **When** the validator processes Terraform files, **Then** it correctly determines the environment context from resource patterns

---

### User Story 3 - Eliminate False Positive for Deny Statement Wildcards (Priority: P2)

A security validator correctly identifies that wildcard actions in Deny statements are security-enhancing and should not be flagged.

**Why this priority**: IAM-006 flags `sqs:*` in DenyInsecureTransport statements as "Service Wildcard Action detected" but Deny statements with wildcards are actually security best practice - they block ALL actions matching a condition, which is the intended behavior.

**Independent Test**: Run `/iam-validate` on deployer policies with DenyInsecureTransport statements and verify no IAM-006 findings

**Acceptance Scenarios**:

1. **Given** a policy contains `"Effect": "Deny"` with `"Action": "sqs:*"`, **When** the IAM validator runs, **Then** no wildcard warning is generated
2. **Given** a policy contains `"Effect": "Allow"` with `"Action": "sqs:*"`, **When** the IAM validator runs, **Then** IAM-006 wildcard warning is generated

---

### Edge Cases

- What happens when a Deny statement has a mix of wildcards and specific actions?
- How does the validator handle conditional Deny statements (with Condition blocks)?
- What if the allowlist entry exists but the file path doesn't match?

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Property test files MUST use proper pytest conftest discovery instead of direct module imports
- **FR-002**: All 33 property tests MUST pass when running `pytest tests/property/`
- **FR-003**: SQS IAM validator MUST check allowlist before reporting HIGH severity findings
- **FR-004**: SQS IAM validator MUST support environment detection from Terraform resource patterns for context-aware suppression
- **FR-005**: IAM validator MUST distinguish between Allow and Deny statement effects when flagging wildcards
- **FR-006**: IAM validator MUST NOT flag wildcard actions in Deny statements as IAM-006 violations
- **FR-007**: Validation run on sentiment-analyzer-gsk MUST produce 0 HIGH severity unsuppressed findings after remediation

### Key Entities

- **Property Test Strategies**: Hypothesis composite strategies for generating test data (lambda_response, sentiment_response, etc.)
- **IAM Allowlist Entry**: YAML configuration that suppresses known-acceptable findings with justification and canonical source
- **IAM Policy Statement**: JSON structure with Effect, Action, Resource, and optional Condition fields

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Property tests achieve 100% pass rate (33/33 tests passing)
- **SC-002**: Validation run produces 0 HIGH severity unsuppressed findings
- **SC-003**: All IAM-006 findings for Deny statements are eliminated (currently 3 false positives)
- **SC-004**: SQS-009 finding for ci-user-policy.tf is suppressed (reduce unsuppressed SQS-009 from 1 to 0)
