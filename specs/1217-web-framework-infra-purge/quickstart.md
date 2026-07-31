# Quickstart: FastAPI Infrastructure Purge

**Feature**: 1217-fastapi-infra-purge
**Date**: 2026-02-11

## What This Feature Does

Removes every remaining trace of FastAPI, Mangum, uvicorn, starlette, and Lambda Web Adapter from the repository. After completion, a case-insensitive search for any of these terms returns zero results in non-archived files.

## Prerequisites

- Branch `001-fastapi-purge` code migration is complete and merged (72/78 tasks)
- All 2983 unit tests and 191 integration tests pass
- Working `git` and `make` on the development machine

## Quick Verification

After implementation, verify the purge succeeded:

```bash
# Run the banned-term scanner
make check-banned-terms

# Run full validation suite (includes banned-term check)
make validate

# Run all tests to confirm no regressions
make test-local

# Manual spot-check (should return zero results)
grep -rni "fastapi\|mangum\|uvicorn\|starlette" --exclude-dir=.git --exclude-dir=specs/archive --exclude-dir=docs/archive .
```

## What Changed

### Comments Rewritten (~24 lines across 15 files)
All source code comments referencing the old framework now describe the current architecture:
- "FastAPI-parity format" → "standard format"
- "Replaces FastAPI Depends()" → "Module-level singleton providers"
- "Lambda Web Adapter artifact" → "request path normalization"

### Documentation Archived
- `docs/fastapi-purge/` → `docs/archive/fastapi-purge/`
- `specs/001-fastapi-purge/` → `specs/archive/001-fastapi-purge/`

### New Validation Gate
- `scripts/check-banned-terms.sh` — scans repo for banned terms
- `make check-banned-terms` — invokes the scanner
- Integrated into `make validate` — runs on every pre-push validation

### Infrastructure Comments Updated
- Terraform `main.tf` — PYTHONPATH comment updated
- Terraform `api_gateway/main.tf` — handler description updated
- SSE Dockerfile — bootstrap description updated
- CI/CD `deploy.yml` — warmup comment updated

## Rollback

If deployment fails after these changes:
1. ECR images: revert to previous SHA-tagged image
2. ZIP packages: revert to previous S3 object version
3. Terraform: `terraform apply -target=module.<lambda>` with prior values
4. Full procedure: `docs/runbooks/rollback-deployment.md`
