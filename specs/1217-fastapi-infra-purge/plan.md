# Implementation Plan: FastAPI Infrastructure Purge

**Branch**: `1217-fastapi-infra-purge` | **Date**: 2026-02-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1217-fastapi-infra-purge/spec.md`

## Summary

Permanently remove every remaining trace of FastAPI, Mangum, uvicorn, starlette, and Lambda Web Adapter from the sentiment-analyzer-gsk repository. The code migration is complete (72/78 tasks, 2983 unit tests passing). This plan covers the 6 deferred infrastructure tasks plus a full-sweep purge of comments, documentation, and configuration. A banned-term CI validation gate prevents re-introduction.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard), HCL/Terraform 1.5+, YAML (GitHub Actions), Bash (validation scripts)
**Primary Dependencies**: AWS Lambda Powertools (routing), boto3 (AWS SDK), pydantic (validation) — all already in place
**Storage**: N/A (no data storage changes)
**Testing**: pytest 8.0+ (existing), grep-based validation gate (new)
**Target Platform**: AWS Lambda (Function URL, BUFFERED + RESPONSE_STREAM modes)
**Project Type**: Serverless multi-Lambda application
**Performance Goals**: Zero regression — all existing tests must continue to pass
**Constraints**: No fallbacks. Fail fast on any banned term. Breaking changes acceptable.
**Scale/Scope**: ~170 line edits across ~30 active files, archive ~50 documentation files, 1 new validation gate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Secrets not in source control (§3) | PASS | No secrets involved in this change |
| TLS enforced (§3) | PASS | No network changes |
| IAM least-privilege (§3) | PASS | No IAM changes |
| Unit tests accompany code (§7) | PASS | Banned-term validator will have unit tests |
| GPG-signed commits (§8) | PASS | Will use `git commit -S` |
| No pipeline bypass (§8) | PASS | All changes go through PR |
| Pre-push validation (§10) | PASS | `make validate` will include new gate |
| No fallbacks (user constraint) | PASS | Validator fails hard on any match |

**Post-Design Re-Check**: All gates still pass. No new dependencies, no new infrastructure, no secrets involved.

## Project Structure

### Documentation (this feature)

```text
specs/1217-fastapi-infra-purge/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (validation finding schema)
├── quickstart.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
# Files MODIFIED (comment rewrites, ~30 files)
src/lambdas/shared/dependencies.py                    # Comment rewrite
src/lambdas/shared/utils/response_builder.py           # Comment rewrite (3 lines)
src/lambdas/shared/utils/cookie_helpers.py             # Comment rewrite
src/lambdas/dashboard/handler.py                       # Comment rewrite
src/lambdas/dashboard/router_v2.py                     # Comment rewrite (2 lines)
src/lambdas/dashboard/requirements.txt                 # Comment rewrite (2 lines)
src/lambdas/sse_streaming/handler.py                   # Comment rewrite
src/lambdas/sse_streaming/requirements.txt             # Comment rewrite
src/lambdas/sse_streaming/Dockerfile                   # Comment rewrite
src/README.md                                          # Description rewrite
infrastructure/terraform/main.tf                       # Comment rewrite (lines 730-732)
infrastructure/terraform/modules/api_gateway/main.tf   # Comment rewrite (lines 24, 26)
.github/workflows/deploy.yml                           # Comment rewrite (line 1169)
tests/conftest.py                                      # Comment rewrite
tests/unit/sse_streaming/test_config_stream.py         # Docstring rewrite
tests/unit/sse_streaming/test_global_stream.py         # Docstring rewrite
tests/unit/sse_streaming/test_path_normalization.py    # Docstring rewrite
tests/unit/sse_streaming/test_connection_limit.py      # Docstring rewrite
tests/integration/test_e2e_lambda_invocation_preprod.py # Comment rewrite (4 lines)
tests/e2e/test_anonymous_restrictions.py               # Comment rewrite
tests/e2e/test_dashboard_buffered.py                   # Comment rewrite

# Files ARCHIVED (moved to archive directories)
docs/fastapi-purge/ → docs/archive/fastapi-purge/     # 12 files
specs/001-fastapi-purge/ → specs/archive/001-fastapi-purge/ # 8 files

# Files CREATED (new)
scripts/check-banned-terms.sh                          # Banned-term scanner
Makefile                                               # New target added

# Documentation FILES UPDATED
README.md                                              # Remove framework references
CLAUDE.md                                              # Remove framework references
SPEC.md                                                # Remove framework references
docs/architecture/DATA_FLOW_AUDIT.md                   # Remove framework references
docs/architecture/LAMBDA_DEPENDENCY_ANALYSIS.md        # Archive or update
```

**Structure Decision**: No new source directories. This feature modifies existing files in-place and archives historical documentation. One new shell script for the validation gate.

## Complexity Tracking

No constitution violations. All changes are comment/documentation edits, file moves (archive), and one new validation script. No new abstractions, no new infrastructure, no new dependencies.

---

## Phase 0: Research

### Decision 1: Banned-Term Validation Approach

**Decision**: Shell script (`scripts/check-banned-terms.sh`) invoked by Makefile target, not a Python validator class.

**Rationale**: The sentiment-analyzer-gsk repo has migrated its validator infrastructure to the template repo. Its local `Makefile` uses simple shell-based validation targets (`validate: fmt lint security sast`). Adding a Python validator class would require importing from the template repo or duplicating the base class. A shell script using `grep -rni` is simpler, faster (~1 second), has zero dependencies, and follows the existing pattern of `check-iam-patterns` in this repo.

**Alternatives considered**:
- Python validator class in `src/validators/`: Rejected — validator infrastructure lives in template repo, not target repo
- Pre-commit hook only: Rejected — doesn't cover `make validate` and CI workflows
- Ruff custom rule: Rejected — ruff scans Python only, we need to scan all file types

### Decision 2: Documentation Archive Strategy

**Decision**: Move to `docs/archive/` and `specs/archive/` directories, not delete.

**Rationale**: Historical records have value for understanding architectural decisions. Archiving preserves git history while removing from active search paths. The validation gate excludes archive directories (FR-021).

**Alternatives considered**:
- Delete entirely: Rejected — destroys institutional knowledge
- Leave in place with disclaimer header: Rejected — grep would still match banned terms
- Move to separate git branch: Rejected — overcomplicates retrieval

### Decision 3: Comment Rewrite Strategy

**Decision**: Rewrite comments to describe current architecture without any reference to the removed framework. Preserve functional intent.

**Rationale**: Comments like "replaces FastAPI" serve no purpose when FastAPI never existed in the reader's frame of reference. "422 validation error format" is more useful than "FastAPI-parity format" because it describes what the code does, not what it replaced.

**Alternatives considered**:
- Delete comments entirely: Rejected — loses functional context
- Replace with "legacy" or "previous framework": Rejected — still references the old stack conceptually

### Decision 4: PYTHONPATH Terraform Comment

**Decision**: Rewrite the Terraform comment on `main.tf:730-732` to explain PYTHONPATH necessity without mentioning Lambda Web Adapter.

**Rationale**: The PYTHONPATH environment variable IS still needed because the custom runtime bootstrap runs Python in a subprocess context. The comment should explain the actual current reason (custom runtime bootstrap subprocess), not the historical reason (Lambda Web Adapter subprocess).

**Current** (lines 730-732):
```
# Note: PYTHONPATH must be set here, not just in Docker ENV, because
# Lambda Web Adapter runs Python in a subprocess that doesn't reliably
# inherit container environment variables.
```

**Proposed**:
```
# Note: PYTHONPATH must be set here, not just in Docker ENV, because
# the custom runtime bootstrap runs Python in a subprocess that doesn't
# reliably inherit container environment variables.
```

---

## Phase 1: Design

### Banned-Term Validation Script Design

**Script**: `scripts/check-banned-terms.sh`

**Behavior**:
1. Define banned terms array: `fastapi`, `mangum`, `uvicorn`, `starlette`, `lambda.web.adapter`, `LambdaAdapterLayer`, `AWS_LWA`
2. Define excluded paths: `.git/`, `specs/archive/`, `docs/archive/`, `specs/1217-fastapi-infra-purge/` (self-referential spec)
3. For each term, run case-insensitive grep across all files excluding the above paths
4. If any match found: print file, line number, matching line, and exit with code 1
5. If no matches: print success message and exit with code 0

**Exit codes**: 0 = clean, 1 = banned terms found

**Integration**:
- `make check-banned-terms` target
- Added to `make validate` dependency chain
- CI runs via `make validate` in `pr-checks.yml`

### Comment Rewrite Mapping (Exact Changes)

| File | Line(s) | Current Text | Replacement Text |
|------|---------|-------------|-----------------|
| `src/lambdas/shared/dependencies.py` | 3 | `Replaces FastAPI's Depends() injection with module-level singletons.` | `Module-level singleton dependency providers.` |
| `src/lambdas/shared/utils/response_builder.py` | 9 | `FR-009: 422 validation errors in FastAPI-parity format` | `FR-009: 422 validation errors in standard format` |
| `src/lambdas/shared/utils/response_builder.py` | 55 | `Build a 422 validation error response in FastAPI-parity format.` | `Build a 422 validation error response in standard format.` |
| `src/lambdas/shared/utils/response_builder.py` | 58 | `This format is byte-identical to FastAPI's automatic 422 responses,` | `This format follows the standard Pydantic ValidationError structure,` |
| `src/lambdas/shared/utils/cookie_helpers.py` | 3 | `Replaces FastAPI's Request.cookies and Response.set_cookie with` | `Cookie parsing and set-cookie header construction using` |
| `src/lambdas/dashboard/handler.py` | 89 | `# Module-level init logging (FR-028: replaces FastAPI lifespan no-op)` | `# Module-level init logging (FR-028)` |
| `src/lambdas/dashboard/router_v2.py` | 137 | `# Helper functions (migrated from FastAPI Request/Response to raw event dicts)` | `# Helper functions for raw API Gateway event dicts` |
| `src/lambdas/dashboard/router_v2.py` | 229 | `to avoid exception-based flow control with FastAPI HTTPException.` | `to avoid exception-based flow control with HTTP exceptions.` |
| `src/lambdas/dashboard/requirements.txt` | 32 | `# JSON serialization - Fast native datetime/dataclass handling (001-fastapi-purge, R3)` | `# JSON serialization - Fast native datetime/dataclass handling` |
| `src/lambdas/dashboard/requirements.txt` | 35 | `# AWS Lambda Powertools - Routing and middleware (001-fastapi-purge, R1)` | `# AWS Lambda Powertools - Routing and middleware` |
| `src/lambdas/sse_streaming/requirements.txt` | 7 | `# JSON serialization - Fast native datetime/dataclass handling (001-fastapi-purge, R3)` | `# JSON serialization - Fast native datetime/dataclass handling` |
| `src/lambdas/sse_streaming/handler.py` | 516 | `# Normalize double slashes (legacy Lambda Web Adapter artifact)` | `# Normalize double slashes in request paths` |
| `src/lambdas/sse_streaming/Dockerfile` | 3 | `# Replaces Lambda Web Adapter + Uvicorn with native Runtime API bootstrap` | `# Native Runtime API bootstrap for streaming responses` |
| `infrastructure/terraform/main.tf` | 730-732 | `# ... Lambda Web Adapter runs Python in a subprocess ...` | `# ... the custom runtime bootstrap runs Python in a subprocess ...` |
| `infrastructure/terraform/modules/api_gateway/main.tf` | 24 | `#     - Mangum adapter in Lambda handles both Function URL and API Gateway` | `#     - Lambda handler manages both Function URL and API Gateway requests` |
| `infrastructure/terraform/modules/api_gateway/main.tf` | 26 | `#     - CORS configured at both API Gateway and FastAPI levels` | `#     - CORS configured at both API Gateway and application levels` |
| `.github/workflows/deploy.yml` | 1169 | `# SSE Lambda uses Docker image with Lambda Web Adapter, needs warmup` | `# SSE Lambda uses Docker image with custom runtime, needs warmup` |
| `tests/conftest.py` | 115 | `# Mock Lambda Event & Context Fixtures (001-fastapi-purge, FR-058)` | `# Mock Lambda Event & Context Fixtures (FR-058)` |
| `tests/unit/sse_streaming/test_config_stream.py` | 7 | `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` | `Uses direct handler invocation for testing.` |
| `tests/unit/sse_streaming/test_global_stream.py` | 5 | `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` | `Uses direct handler invocation for testing.` |
| `tests/unit/sse_streaming/test_connection_limit.py` | 6 | `Migrated from FastAPI TestClient to direct handler invocation (001-fastapi-purge).` | `Uses direct handler invocation for testing.` |
| `tests/e2e/test_anonymous_restrictions.py` | 497 | `# FastAPI uses "detail" for error messages, other APIs may use "error" or "message"` | `# Error responses use "detail" field for error messages` |
| `tests/e2e/test_dashboard_buffered.py` | 5 | `# uses BUFFERED invoke mode (via Mangum), ensuring REST API responses` | `# uses BUFFERED invoke mode, ensuring REST API responses` |
| `src/README.md` | 10 | `│   ├── dashboard/     # FastAPI dashboard (Function URL)` | `│   ├── dashboard/     # Dashboard API (Function URL)` |

### Archive Operations

```bash
# Create archive directories
mkdir -p docs/archive
mkdir -p specs/archive

# Move documentation
git mv docs/fastapi-purge docs/archive/fastapi-purge

# Move specs
git mv specs/001-fastapi-purge specs/archive/001-fastapi-purge
```

### Documentation Updates (README.md, CLAUDE.md, SPEC.md)

These files must be scanned for legacy framework references and updated. The exact changes depend on the current content at execution time, but the principle is:
- Replace "FastAPI" with "Lambda Powertools" or "REST API" as context requires
- Replace "Mangum" with "native Lambda handler"
- Replace "uvicorn" with "custom runtime bootstrap" (SSE) or remove entirely
- Remove any "starlette" references

### Makefile Integration

Add to the existing `validate` target:

```makefile
check-banned-terms: ## Verify no legacy framework references remain
	@bash scripts/check-banned-terms.sh

validate: fmt lint security sast check-banned-terms ## Run all validation
	@echo "$(GREEN)✓ All validation passed$(NC)"
```

### Rollback Procedure

Document in `docs/runbooks/rollback-deployment.md`:
1. Identify the last successful ECR image SHA tags per Lambda
2. `aws lambda update-function-code --function-name <name> --image-uri <ecr-repo>@sha256:<hash>`
3. For ZIP Lambdas: `aws lambda update-function-code --function-name <name> --s3-bucket <bucket> --s3-key <previous-version-key>`
4. If Terraform state diverged: `terraform apply -target=module.<lambda>` with prior variable values
5. Verify each Lambda health endpoint returns 200

### Test Strategy

**Existing tests**: All 2983 unit tests and 191 integration tests must continue to pass with zero modifications to assertions. Comment-only changes do not affect test behavior.

**New test**: The banned-term validation script itself is tested by:
1. Running it against the cleaned repository — expect exit code 0
2. Creating a temporary file with a banned term — expect exit code 1
3. Creating a file in an excluded path — expect exit code 0 (excluded)

---

## Execution Phases (for /speckit.tasks)

### Phase 1: Source Code Comment Rewrites (FR-012, FR-013, FR-014)
- Rewrite all 24 comment/docstring lines in active source code
- Zero functional changes — comments only
- Verify all existing tests still pass

### Phase 2: Infrastructure Comment Rewrites (FR-001 through FR-010)
- Rewrite Terraform comments (main.tf, api_gateway/main.tf)
- Rewrite Dockerfile comment (sse_streaming/Dockerfile)
- Rewrite CI/CD workflow comment (deploy.yml)

### Phase 3: Documentation Archive (FR-015, FR-016, FR-017, FR-018, FR-019)
- Archive docs/fastapi-purge/ → docs/archive/fastapi-purge/
- Archive specs/001-fastapi-purge/ → specs/archive/001-fastapi-purge/
- Update README.md, CLAUDE.md, SPEC.md
- Update docs/architecture/ files

### Phase 4: Banned-Term Validation Gate (FR-020, FR-021, FR-022)
- Create scripts/check-banned-terms.sh
- Add make target check-banned-terms
- Integrate into make validate
- Run to verify clean state

### Phase 5: Deployment Verification Artifacts (FR-023, FR-024, FR-025)
- Create rollback procedure document
- Verify existing smoke tests in deploy.yml are framework-agnostic
- Document deployment verification checklist

### Phase 6: Full Sweep Verification
- Run banned-term scanner across entire repo
- Run all unit tests
- Run all integration tests
- Verify grep returns zero matches for all banned terms in non-archived files
