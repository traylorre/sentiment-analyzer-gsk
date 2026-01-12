# Feature Specification: Add Stripe Dependency to Dashboard Lambda

**Feature Branch**: `1201-stripe-lambda-dependency`
**Created**: 2026-01-12
**Status**: Draft
**Input**: User description: "Add stripe dependency to dashboard Lambda requirements.txt - deploy is failing with ModuleNotFoundError: No module named stripe"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Dashboard Lambda Deploys Successfully (Priority: P1)

When changes are merged to main, the deployment pipeline should complete successfully. Currently, the Dashboard Lambda image build fails at the smoke test step because the `stripe` module is not available.

**Why this priority**: This is blocking all production deployments. No code changes can reach production until this is resolved.

**Independent Test**: Push any change to main → deployment pipeline completes with all jobs green → Dashboard Lambda is updated in production.

**Acceptance Scenarios**:

1. **Given** code is merged to main, **When** the deployment pipeline runs, **Then** the Dashboard Lambda image smoke test passes with no import errors
2. **Given** the Dashboard Lambda is deployed, **When** auth endpoints are called that use Stripe functionality, **Then** Stripe-related code executes without ModuleNotFoundError

---

### Edge Cases

- What happens if stripe version conflicts with other dependencies?
  - Use version constraint compatible with existing dependencies in root requirements.txt
- What happens if stripe SDK breaks in a future version?
  - Pin to major version with upper bound (e.g., `>=11.4.1,<12.0.0`)

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The Dashboard Lambda Docker image MUST include the `stripe` Python package
- **FR-002**: The stripe version MUST be compatible with the version in root requirements.txt (11.4.1)
- **FR-003**: The Dashboard Lambda MUST pass import smoke tests during CI/CD build

### Key Entities

- **Dashboard Lambda requirements.txt**: Located at `src/lambdas/dashboard/requirements.txt` - lists Python dependencies that are installed in the Lambda Docker image during build
- **stripe_utils.py**: Shared auth module at `src/lambdas/shared/auth/stripe_utils.py` that imports stripe SDK for webhook verification and subscription handling

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Deployment pipeline completes successfully after this change is merged
- **SC-002**: Dashboard Lambda smoke test step passes with exit code 0
- **SC-003**: No ModuleNotFoundError for 'stripe' in Lambda execution logs

## Assumptions

- The stripe version 11.4.1 (from root requirements.txt) is compatible with the Lambda runtime (Python 3.13)
- No other dependencies in the Dashboard Lambda conflict with stripe SDK
- The stripe import is only used in the auth path, not during initial Lambda cold start

## Scope Boundaries

**In Scope:**
- Adding stripe to `src/lambdas/dashboard/requirements.txt`

**Out of Scope:**
- Changes to stripe_utils.py functionality
- Version upgrades to stripe beyond what's in root requirements.txt
- Adding stripe to other Lambda requirements files (only Dashboard uses it)
