# Research: FastAPI Infrastructure Purge

**Feature**: 1217-fastapi-infra-purge
**Date**: 2026-02-11

## Research Tasks & Findings

### R1: Banned-Term Validation Approach

**Question**: What is the best way to prevent re-introduction of removed framework references in a polyglot repository (Python, HCL, YAML, Markdown, Bash, Dockerfile)?

**Finding**: A shell script using `grep -rni` with `--exclude-dir` is the industry-standard approach for cross-language term scanning. Tools like `gitleaks` and `detect-secrets` use similar patterns for secret detection. The key design principles are:

1. **Fail fast**: Exit code 1 on first category of matches (scan all terms, report all, then fail)
2. **Exclude paths**: Support exclusion of archive directories and self-referential spec files
3. **Case-insensitive**: Framework names appear in mixed case across file types
4. **All file types**: Must scan .py, .tf, .yml, .md, .txt, .toml, Dockerfile, Makefile, .sh, .json, .cfg

**Canonical source**: GNU grep is the POSIX standard for pattern matching. The `--include`/`--exclude-dir` flags are POSIX-compliant and available on all CI runners (Ubuntu, macOS).

### R2: Archive Strategy for Historical Documentation

**Question**: What is the industry practice for archiving completed migration documentation while preserving git history?

**Finding**: `git mv` preserves full git history (blame, log) for moved files. The `docs/archive/` and `specs/archive/` pattern is used by large open-source projects (Kubernetes, Terraform) to separate active from historical documentation. The key principle is that archived files remain discoverable via `git log --follow` but don't pollute active searches.

**Canonical source**: Git documentation on `git mv` — "git mv is a convenience command that performs a rename, which git tracks as a delete + add with rename detection."

### R3: Comment Rewrite — Preserving Functional Intent

**Question**: When rewriting comments that reference a removed framework, how do you preserve the functional intent without the historical context?

**Finding**: The principle is "describe what the code does now, not what it replaced." Industry best practice from Google's Style Guide (go/style): comments should explain WHY or WHAT, never reference removed alternatives. The replacement comment should be understandable to a developer who has never heard of the removed framework.

**Examples applied**:
- "FastAPI-parity format" → "standard format" (the format IS the standard now)
- "Replaces FastAPI Depends()" → "Module-level singleton providers" (describes current pattern)
- "Legacy Lambda Web Adapter artifact" → "request path normalization" (describes what the code does)

### R4: PYTHONPATH in Custom Lambda Runtime

**Question**: Is the PYTHONPATH Terraform environment variable still needed after removing Lambda Web Adapter?

**Finding**: YES. The PYTHONPATH is needed because the custom runtime bootstrap (SSE streaming Lambda) starts a Python subprocess that requires explicit path configuration. This is NOT a Lambda Web Adapter requirement — it's a custom runtime requirement. The Lambda execution environment does not automatically propagate Docker `ENV` directives to subprocess contexts started by the bootstrap script.

**Canonical source**: AWS Lambda Custom Runtime documentation — "The bootstrap is responsible for initializing the runtime and handling communication with the Lambda Runtime API. Environment variables set in the function configuration are available to the bootstrap process."

The critical nuance: while env vars are available to the bootstrap process itself, if the bootstrap spawns a subprocess (e.g., `python3 handler.py`), the subprocess inherits the bootstrap's environment — but Docker `ENV` directives in the Dockerfile are only set during image build and may not be present in the Lambda execution context if the runtime overrides the environment. Setting PYTHONPATH explicitly in Terraform guarantees it's available regardless of how the runtime initializes.

## Unknowns Resolved

All unknowns from the Technical Context have been resolved. No NEEDS CLARIFICATION markers remain.

| Unknown | Resolution |
|---------|-----------|
| Validation approach | Shell script (R1) |
| Archive vs delete | Archive with git mv (R2) |
| Comment rewrite style | Describe current, not historical (R3) |
| PYTHONPATH necessity | Still needed for custom runtime (R4) |
