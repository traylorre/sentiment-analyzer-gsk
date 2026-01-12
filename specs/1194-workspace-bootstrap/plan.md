# Implementation Plan: Workspace Bootstrap with Local Secrets Cache

**Branch**: `1194-workspace-bootstrap` | **Date**: 2026-01-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1194-workspace-bootstrap/spec.md`

## Summary

Create a workspace bootstrap system that enables developers to set up a new development machine with minimal friction. The system fetches secrets from AWS Secrets Manager once during initial setup, caches them locally using age encryption, and generates a `.env.local` file for test execution. This eliminates repeated KMS/Secrets Manager calls during development and enables offline work.

## Technical Context

**Language/Version**: Bash (bootstrap scripts), Python 3.13 (helper utilities)
**Primary Dependencies**: age (encryption), AWS CLI v2, jq
**Storage**: `~/.config/sentiment-analyzer/secrets.cache.age` (encrypted file)
**Testing**: Manual verification, bash script unit tests (bats-core optional)
**Target Platform**: WSL2 Ubuntu 24.04, Linux (Ubuntu/Debian)
**Project Type**: Single project with CLI scripts
**Performance Goals**: Bootstrap completes in <10 minutes (excluding prerequisite installation)
**Constraints**: Offline-capable after bootstrap, no secret values in logs
**Scale/Scope**: Single developer workstation, 5 cached secrets

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Secrets stored in managed service | PASS | Secrets remain in AWS Secrets Manager; local cache is encrypted |
| No secrets in source control | PASS | `.env.local` is gitignored; cache is outside repo |
| TLS in transit | PASS | AWS CLI uses HTTPS for Secrets Manager API |
| Auth required for management | PASS | Requires valid AWS credentials |
| Implementation accompaniment (tests) | PASS | Verification script serves as test |
| Pre-push requirements | N/A | No code changes to push (scripts only) |
| No pipeline bypass | PASS | Normal PR workflow |

**Post-Design Re-check**: All gates pass. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1194-workspace-bootstrap/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output (developer quick start)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
scripts/
├── bootstrap-workspace.sh     # NEW: Main bootstrap script
├── verify-dev-environment.sh  # NEW: Environment verification
├── refresh-secrets-cache.sh   # NEW: Force-refresh secrets
└── setup-github-secrets.sh    # EXISTING: GitHub secrets setup

docs/
└── WORKSPACE_SETUP.md         # NEW: Comprehensive setup guide

.env.example                   # NEW: Template for .env.local
.gitignore                     # EXISTING: Already ignores .env.local
```

**Structure Decision**: Scripts-only feature. No src/ changes. All new files are bash scripts in `scripts/` directory and documentation in `docs/`.

## Complexity Tracking

No violations to justify. This feature is a simple bash scripting addition with no architectural complexity.

## Implementation Phases

### Phase 1: Core Bootstrap Script (P1 - New Developer Setup)

1. Create `scripts/bootstrap-workspace.sh`:
   - Prerequisites check function (version validation)
   - age installation check/install
   - AWS credentials validation
   - Secrets fetch from AWS Secrets Manager
   - age encryption of secrets to cache file
   - `.env.local` generation from cached secrets
   - Success/failure reporting

2. Create `.env.example` template

### Phase 2: Verification Script (P3 - Environment Verification)

1. Create `scripts/verify-dev-environment.sh`:
   - Prerequisites status (pass/fail with versions)
   - Cache validity check (exists, not expired)
   - AWS credentials status
   - Git hooks status
   - Python venv status
   - Remediation instructions for failures

### Phase 3: Cache Refresh (P4 - Cache Refresh)

1. Create `scripts/refresh-secrets-cache.sh`:
   - Force-refresh of secrets cache
   - Atomic replacement of cache file

### Phase 4: Documentation

1. Create `docs/WORKSPACE_SETUP.md`:
   - Complete WSL2 setup section
   - pyenv installation for Python 3.13
   - AWS credentials configuration
   - Bootstrap execution
   - Troubleshooting section

2. Update `README.md`:
   - Add "New Developer Setup" section pointing to WORKSPACE_SETUP.md
   - Add quick start commands

## Dependencies

- **age**: Modern encryption tool. Install via `apt install age` or from GitHub releases.
- **jq**: JSON processing. Already common in the project.
- **AWS CLI v2**: Required for Secrets Manager access.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| age not available in older Ubuntu | Script checks and provides install instructions |
| AWS credentials expired | Clear error message with remediation |
| Cache file corruption | Verification script detects, prompts refresh |
| User runs bootstrap without AWS creds | Pre-flight check aborts with helpful message |

## Deliverables

1. `scripts/bootstrap-workspace.sh` - Main bootstrap script
2. `scripts/verify-dev-environment.sh` - Verification script
3. `scripts/refresh-secrets-cache.sh` - Cache refresh utility
4. `.env.example` - Environment template
5. `docs/WORKSPACE_SETUP.md` - Comprehensive setup guide
6. Updated `README.md` - Quick start addition
