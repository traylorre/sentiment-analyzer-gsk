# Data Model: FastAPI Infrastructure Purge

**Feature**: 1217-fastapi-infra-purge
**Date**: 2026-02-11

## Entities

This feature does not introduce new data entities. It modifies existing text content (comments, documentation) and adds a validation script.

### Banned Term

A term that must not appear in non-archived repository files.

| Attribute | Type | Description |
|-----------|------|-------------|
| term | string | The banned text pattern (case-insensitive) |
| scope | enum | `exact_word` or `substring` — all terms use substring matching |

**Instances**:
- `fastapi`
- `mangum`
- `uvicorn`
- `starlette`
- `lambda.web.adapter` (matches `lambda web adapter`, `lambda_web_adapter`, `Lambda Web Adapter`)
- `LambdaAdapterLayer`
- `AWS_LWA`

### Excluded Path

A directory or file pattern excluded from banned-term scanning.

| Attribute | Type | Description |
|-----------|------|-------------|
| path | string | Relative path from repository root |
| reason | string | Why this path is excluded |

**Instances**:
- `.git/` — git internals
- `specs/archive/` — archived historical specifications
- `docs/archive/` — archived historical documentation
- `specs/1217-fastapi-infra-purge/` — this feature's own spec (self-referential)

### Validation Result

Output of the banned-term scanner.

| Attribute | Type | Description |
|-----------|------|-------------|
| status | enum | `PASS` (zero matches) or `FAIL` (matches found) |
| matches | list | List of Match objects (empty on PASS) |

### Match

A single occurrence of a banned term.

| Attribute | Type | Description |
|-----------|------|-------------|
| file | string | Relative file path |
| line | integer | Line number |
| term | string | Which banned term matched |
| content | string | The full line content |
