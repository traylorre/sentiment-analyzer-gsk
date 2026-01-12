# Feature Specification: Workspace Bootstrap with Local Secrets Cache

**Feature Branch**: `1194-workspace-bootstrap`
**Created**: 2026-01-11
**Status**: Draft
**Input**: User description: "Create secure workflow for migrating development workspace to new machines with one-time AWS Secrets Manager fetch and local encrypted cache"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Developer Workspace Setup (Priority: P1)

A developer setting up a new machine (e.g., migrating from desktop WSL to laptop WSL) needs to bootstrap their development environment with minimal friction. They run a single bootstrap command that verifies prerequisites, fetches secrets once, and creates a ready-to-develop workspace.

**Why this priority**: This is the core value proposition - reducing workspace setup from hours of manual configuration to a single automated command. Without this, all other features are inaccessible.

**Independent Test**: Can be fully tested by cloning the repo on a fresh WSL instance with AWS credentials and running the bootstrap script. Success delivers a fully functional development environment.

**Acceptance Scenarios**:

1. **Given** a fresh WSL Ubuntu instance with AWS CLI configured, **When** developer runs the bootstrap script, **Then** all prerequisites are verified and missing tools are reported with installation instructions
2. **Given** valid AWS credentials, **When** bootstrap script runs, **Then** secrets are fetched from AWS Secrets Manager exactly once and cached locally
3. **Given** successful bootstrap, **When** developer runs tests, **Then** tests execute without requiring AWS Secrets Manager calls

---

### User Story 2 - Offline Development After Bootstrap (Priority: P2)

A developer who has already bootstrapped their workspace wants to work offline (airplane, coffee shop without internet). They should be able to run tests and develop locally using cached secrets without any network dependency on AWS.

**Why this priority**: Enables productivity in common offline scenarios. Depends on P1 (bootstrap must happen first).

**Independent Test**: Can be tested by disconnecting network after bootstrap and verifying tests still pass.

**Acceptance Scenarios**:

1. **Given** a bootstrapped workspace with cached secrets, **When** network is disconnected, **Then** local tests using cached secrets execute successfully
2. **Given** cached secrets exist, **When** developer runs the test suite, **Then** no AWS Secrets Manager API calls are made

---

### User Story 3 - Environment Verification (Priority: P3)

A developer returning to the project after time away wants to verify their environment is still correctly configured. They run a verification script that validates all prerequisites, cached secrets validity, and configuration.

**Why this priority**: Supports ongoing maintenance and troubleshooting. Less critical than initial setup.

**Independent Test**: Can be tested by running verification script and checking each validation item produces correct pass/fail status.

**Acceptance Scenarios**:

1. **Given** a valid development environment, **When** verification script runs, **Then** all checks pass with green status indicators
2. **Given** missing prerequisites, **When** verification script runs, **Then** specific remediation instructions are displayed for each failing check
3. **Given** expired secrets cache, **When** verification script runs, **Then** developer is prompted to refresh the cache

---

### User Story 4 - Cache Refresh on Rotation (Priority: P4)

A developer needs to refresh their local secrets cache after secrets have been rotated in AWS Secrets Manager. They can force-refresh the cache with a simple command.

**Why this priority**: Operational maintenance scenario, needed periodically but not for initial setup.

**Independent Test**: Can be tested by manually invalidating cache and running refresh command.

**Acceptance Scenarios**:

1. **Given** stale cached secrets, **When** developer runs cache refresh command, **Then** new secrets are fetched and cached
2. **Given** cache refresh in progress, **When** refresh completes, **Then** old cache is atomically replaced with new cache

---

### Edge Cases

- What happens when AWS credentials are expired during bootstrap?
  - Bootstrap fails with clear message directing user to run `aws configure` or `aws sso login`
- How does system handle partial bootstrap (interrupted during secrets fetch)?
  - No partial cache is written; bootstrap is atomic (all or nothing)
- What happens when secrets don't exist in AWS Secrets Manager?
  - Bootstrap reports which specific secrets are missing and continues with available secrets
- How does system handle cache file corruption?
  - Verification script detects corruption and prompts for cache refresh

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST verify all system prerequisites (Python 3.12+, AWS CLI v2, Terraform 1.5+, Node.js 20+, Git 2.30+) before proceeding with bootstrap
- **FR-002**: System MUST report missing prerequisites with specific installation instructions for Ubuntu/WSL
- **FR-003**: System MUST fetch secrets from AWS Secrets Manager only once during bootstrap (not on every test run)
- **FR-004**: System MUST encrypt cached secrets at rest using age encryption
- **FR-005**: System MUST set cache file permissions to 600 (owner read/write only)
- **FR-006**: System MUST store cached secrets in user's home directory (`~/.config/sentiment-analyzer/`)
- **FR-007**: System MUST create a `.env.local` file with development environment variables from cached secrets
- **FR-008**: System MUST add `.env.local` to `.gitignore` to prevent accidental commits
- **FR-009**: System MUST provide a verification script that validates environment completeness
- **FR-010**: System MUST support cache TTL configuration (default: 30 days) with manual override
- **FR-011**: System MUST provide force-refresh capability to update cached secrets on demand
- **FR-012**: System MUST never log or display secret values in any output
- **FR-013**: System MUST validate AWS credentials before attempting secrets fetch

### Secrets to Cache

The following secrets are fetched from AWS Secrets Manager and cached locally:

- **Dashboard API Key**: `dev/sentiment-analyzer/dashboard-api-key` - Dashboard authentication
- **Tiingo API Key**: `dev/sentiment-analyzer/tiingo` - Financial news API
- **Finnhub API Key**: `dev/sentiment-analyzer/finnhub` - Financial news API
- **SendGrid API Key**: `dev/sentiment-analyzer/sendgrid` - Email notifications
- **hCaptcha Secret**: `dev/sentiment-analyzer/hcaptcha` - Bot protection

### Secrets NOT Cached (Standard Locations)

- AWS credentials (`~/.aws/credentials`) - Standard AWS tooling
- GitHub PAT (`gh auth`) - Standard GitHub CLI authentication
- GPG keys (`~/.gnupg/`) - Standard GPG keyring

### Key Entities

- **Secrets Cache**: Encrypted file containing all cached secrets with metadata (fetch timestamp, TTL, version)
- **Environment Configuration**: `.env.local` file containing environment variables derived from cached secrets
- **Verification Report**: Output of verification script showing pass/fail status for each check

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developer can set up complete workspace in under 10 minutes using bootstrap script (excluding prerequisite installation)
- **SC-002**: Zero AWS Secrets Manager API calls during local test execution after bootstrap
- **SC-003**: Verification script completes in under 30 seconds with clear pass/fail indicators
- **SC-004**: 100% of secrets are encrypted at rest in the cache file
- **SC-005**: Bootstrap script provides remediation instructions for all failure modes (no cryptic errors)
- **SC-006**: Developer can work offline for at least 30 days after initial bootstrap (default TTL)
- **SC-007**: Bootstrap process is idempotent (running multiple times produces same result)

## Assumptions

1. **AWS Credentials Pre-configured**: User has already configured AWS credentials via `aws configure` or AWS SSO before running bootstrap
2. **age Encryption Tool**: Bootstrap script will install `age` if not present (standard package manager installation)
3. **Development Environment**: Target is `dev` environment secrets; production secrets are never cached locally
4. **Single User**: Cache is per-user, not shared across users on the same machine
5. **Ubuntu/WSL Primary Target**: Instructions and scripts optimized for Ubuntu on WSL2; other environments may work but are not primary targets

## Out of Scope

- Production secret caching (security risk)
- Cross-machine cache synchronization
- Secret rotation automation (handled by AWS Secrets Manager)
- CI/CD pipeline changes (uses GitHub environment secrets, not local cache)
- IDE-specific configuration (VS Code, etc.)
