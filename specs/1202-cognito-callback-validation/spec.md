# Feature Specification: Cognito Callback URL Validation

**Feature Branch**: `1202-cognito-callback-validation`
**Created**: 2026-01-18
**Status**: Draft
**Input**: User description: "Verify Cognito OAuth callback URLs are correctly configured for Amplify frontend. Add Terraform outputs to surface callback URLs for future validation. The terraform_data provisioner may have failed silently."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Infrastructure Engineer Verifies OAuth Configuration (Priority: P1)

An infrastructure engineer needs to verify that Cognito OAuth callback URLs are correctly configured for the Amplify frontend after deployment. Currently, there is no visibility into whether the `terraform_data` provisioner successfully patched the Cognito client with the correct callback URLs, which can lead to silent authentication failures.

**Why this priority**: Authentication is foundational - if callbacks are misconfigured, users cannot log in at all. This is a blocking issue for all authenticated functionality.

**Independent Test**: Can be tested by running `terraform output` and verifying the callback URLs match expected Amplify domain patterns.

**Acceptance Scenarios**:

1. **Given** a deployed Cognito user pool with an associated app client, **When** the engineer runs `terraform output cognito_callback_urls`, **Then** the output displays all configured callback URLs including the Amplify production URL.

2. **Given** a deployed Cognito user pool, **When** the engineer runs `terraform output cognito_logout_urls`, **Then** the output displays all configured logout URLs including the Amplify production URL.

3. **Given** the Terraform outputs are available, **When** the engineer compares callback URLs against the Amplify app URL, **Then** they can verify the URLs match without needing AWS console access.

---

### User Story 2 - CI Pipeline Validates Callback Configuration (Priority: P2)

The CI/CD pipeline needs to automatically verify that Cognito callbacks are correctly configured after each deployment, catching silent provisioner failures before they reach production.

**Why this priority**: Automated validation prevents silent failures from reaching production, but requires manual verification capability (P1) to exist first.

**Independent Test**: Can be tested by adding a deployment verification step that queries Terraform outputs and validates against expected patterns.

**Acceptance Scenarios**:

1. **Given** a deployment has completed, **When** the CI pipeline queries Cognito callback configuration, **Then** it can programmatically verify the Amplify URL is present in the callback list.

2. **Given** the provisioner failed silently (callbacks stuck on localhost only), **When** the CI pipeline checks the configuration, **Then** the check fails with a clear error message indicating missing Amplify URL.

---

### User Story 3 - Developer Troubleshoots Auth Failures (Priority: P3)

A developer investigating authentication failures needs quick visibility into Cognito callback configuration without accessing the AWS console or running complex CLI commands.

**Why this priority**: Improves developer experience and reduces troubleshooting time, but is not blocking for core functionality.

**Independent Test**: Can be tested by simulating an auth failure scenario and using Terraform outputs to diagnose the issue.

**Acceptance Scenarios**:

1. **Given** a user reports "redirect_mismatch" OAuth errors, **When** the developer checks `terraform output`, **Then** they can immediately see if the callback URL matches the frontend URL.

---

### Edge Cases

- What happens when the Cognito module is not deployed (e.g., disabled via feature flag)?
  - Outputs should gracefully return empty or null without causing Terraform errors.
- How does the system handle multiple callback URLs (localhost + Amplify)?
  - Outputs should display all configured URLs as a list.
- What happens if the Cognito client doesn't exist yet (first deployment)?
  - Outputs should indicate "not yet configured" rather than failing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose Cognito callback URLs as a Terraform output named `cognito_callback_urls`.
- **FR-002**: System MUST expose Cognito logout URLs as a Terraform output named `cognito_logout_urls`.
- **FR-003**: The Cognito module MUST export callback and logout URL values from the user pool client configuration.
- **FR-004**: Outputs MUST be available immediately after `terraform apply` completes without requiring additional commands.
- **FR-005**: Outputs MUST handle cases where Cognito is conditionally deployed without causing errors.
- **FR-006**: The callback URL list MUST include the Amplify production URL pattern when Amplify is enabled.

### Key Entities

- **Cognito User Pool Client**: The OAuth client that holds callback and logout URL configurations.
- **Terraform Output**: Infrastructure-as-code output values that surface internal resource attributes for external consumption.
- **Callback URL**: The URL that Cognito redirects to after successful authentication.
- **Logout URL**: The URL that Cognito redirects to after logout/session termination.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Engineers can verify callback URL configuration in under 30 seconds using `terraform output`.
- **SC-002**: 100% of Cognito callback configurations are visible without AWS console access.
- **SC-003**: Silent provisioner failures are detectable by comparing output URLs against expected Amplify URL.
- **SC-004**: Zero authentication failures caused by undetected callback URL misconfigurations after this feature is implemented.

## Assumptions

- The Cognito user pool and app client are managed by Terraform (not created externally).
- The `terraform_data` resource that patches callback URLs exists and may have failed silently.
- The Amplify frontend URL follows the pattern `https://main.{app-id}.amplifyapp.com`.
- Localhost URLs (`http://localhost:3000`) are expected in addition to production URLs for local development.

## Out of Scope

- Automatically fixing misconfigured callback URLs (this feature is for visibility/validation only).
- Modifying the `terraform_data` provisioner itself (that is a separate feature - Feature 8 in the workplan).
- Adding callback URLs for environments beyond what's currently configured.
