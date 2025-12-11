# Feature Specification: Validation Findings Remediation

**Status**: Draft
**Feature ID**: 084
**Branch**: `084-validation-findings-remediation`
**Created**: 2025-12-10

## Overview

Address validation findings from template repo validators run against target repo. Includes IAM wildcard suppression (false positive), spec status tags for roadmap features, orphan code coverage, and missing Makefile targets.

## User Scenarios

### US1: Validator Suppression for AWS-Required Wildcards

**As a** DevOps engineer
**I want** IAM wildcard findings suppressed when AWS requires them
**So that** validators don't flag false positives for AWS service limitations

**Acceptance Criteria**:
- CloudFront cache policy wildcard is suppressed with canonical source citation
- Suppression includes AWS documentation reference

### US2: Spec Status Tags for Roadmap Features

**As a** developer reviewing bidirectional validation
**I want** roadmap specs marked with `Status: Planned` or `Status: In Progress`
**So that** validators distinguish between incomplete work and missing implementations

**Acceptance Criteria**:
- Specs 079, 080, 082 have status tags
- Bidirectional validator respects status tags (future work)

### US3: Orphan Code Coverage

**As a** methodology maintainer
**I want** orphan validators (`resource_naming.py`, `iam_coverage.py`) covered by specs
**So that** bidirectional validation passes

**Acceptance Criteria**:
- Orphan code added to existing methodology spec OR removed if unused
- Only minimal additions for uncovered functionality

### US4: Missing Makefile Targets

**As a** developer running validation
**I want** `make test-spec` and `make test-mutation` available in target repo
**So that** spec-coherence and mutation validators don't skip

**Acceptance Criteria**:
- Makefile has `test-spec` target
- Makefile has `test-mutation` target
- Validators no longer skip

## Functional Requirements

### IAM Allowlist Updates

- **FR-001**: System MUST suppress CloudFront cache policy wildcard (IAM-002) with canonical source
- **FR-002**: Suppression entry MUST cite AWS Service Authorization Reference

### Spec Status Tags

- **FR-003**: Spec 079-e2e-endpoint-roadmap MUST have `Status: Planned` tag
- **FR-004**: Spec 080-fix-integ-test-failures MUST have `Status: Planned` tag
- **FR-005**: Spec 082-fix-sse-e2e-timeouts MUST have `Status: In Progress` tag

### Orphan Code Coverage

- **FR-006**: `src/validators/resource_naming.py` MUST be covered by existing spec OR removed
- **FR-007**: `src/validators/iam_coverage.py` MUST be covered by existing spec OR removed

### Makefile Targets

- **FR-008**: Makefile MUST have `test-spec` target that runs spec coherence tests
- **FR-009**: Makefile MUST have `test-mutation` target that runs mutation tests

## Success Criteria

| ID | Criteria | Measurement |
|----|----------|-------------|
| SC-001 | IAM wildcard false positive suppressed | `/iam-validate` passes |
| SC-002 | Roadmap specs have status tags | Grep for `Status:` in spec files |
| SC-003 | Orphan code covered or removed | `/bidirectional-validate` MEDIUM findings = 0 |
| SC-004 | Makefile targets exist | `make test-spec` and `make test-mutation` don't error |
| SC-005 | Validators don't skip | spec-coherence and mutation validators run |

## Edge Cases

### EC-001: AWS Service Limitations
- **Scenario**: AWS action requires wildcard Resource
- **Resolution**: Add to allowlist with canonical AWS documentation link
- **Example**: CloudFront `GetCachePolicy` doesn't support resource-level permissions

### EC-002: Orphan Code Already Covered
- **Scenario**: Code appears orphan but is actually covered by umbrella spec
- **Resolution**: Verify coverage before removing

## Key Entities

### IAMAllowlistEntry
- `id`: Unique suppression identifier
- `rule`: Rule being suppressed (e.g., `IAM-002`)
- `pattern`: File/resource pattern to match
- `reason`: Human-readable justification
- `canonical_source`: AWS documentation URL

### SpecStatusTag
- `status`: One of `Draft`, `Planned`, `In Progress`, `Complete`, `Deprecated`
- `location`: Top of spec.md after title

## Future Work

- **FW-001**: Teach bidirectional validator to respect `Status:` tags
- **FW-002**: Separate IAM permissions for teardown activities (carve out delete permissions)
- **FW-003**: Update generic IAM validator to read iam-allowlist.yaml (currently only specialized validators like sqs-iam-validate read allowlist)
- **FW-004**: Auto-detect AWS actions requiring wildcards based on AWS Service Authorization Reference

## Dependencies

- IAM allowlist file: `infrastructure/iam-allowlist.yaml`
- Makefile: `Makefile`
- Methodology index: `.specify/methodologies/index.yaml`

## Clarifications

### Session 2025-12-10
- Q: How to handle IAM wildcard at preprod-deployer-policy.json:301?
  - A: This is a FALSE POSITIVE. CloudFront GetCachePolicy/ListCachePolicies don't support resource-level permissions per AWS docs. Suppress with canonical source.
- Q: What about orphan validators?
  - A: Add minimally to existing methodology spec, prune if truly unused.
- Q: Roadmap specs showing as missing implementations?
  - A: Add `Status: Planned` tag to specs. Future work to make validator respect this.
