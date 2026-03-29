# Stage 1: Research & Context Gathering

## Feature: 1278-pydantic-dev-pin

## Findings

### Current State
- `requirements.txt` (production): `pydantic==2.12.5`
- `requirements-ci.txt`: `pydantic==2.12.4` (explicit pin, override, with comment)
- `requirements-dev.txt`: inherits `pydantic==2.12.5` via `-r requirements.txt`, NO override
- Lambda requirements use flexible ranges (`>=2.9.0,<3.0.0`, `>=2.10.0,<3.0.0`, `>=2.12.0,<3.0.0`)

### Dependency Conflict
- `moto[all]==5.1.22` requires `pydantic<=2.12.4`
- `requirements.txt` pins `pydantic==2.12.5`
- When `requirements-dev.txt` includes `-r requirements.txt`, pip installs 2.12.5
- Then `moto[all]==5.1.22` fails because 2.12.5 > 2.12.4

### Existing Fix (requirements-ci.txt)
Line 25: `pydantic==2.12.4  # pinned: moto[all]==5.1.22 requires pydantic<=2.12.4`
This explicit pin AFTER boto3/botocore (standalone, not via -r) overrides effectively.

### Why Production Stays at 2.12.5
Production (`requirements.txt`) does NOT include moto. No conflict exists there.
Lambda runtimes use pydantic 2.12.5 in production. Downgrading would require
redeployment and re-testing of all Lambda functions for no benefit.

### Fix Strategy
Add `pydantic==2.12.4` with explanatory comment in `requirements-dev.txt` AFTER the
`-r requirements.txt` line. pip resolves the last-specified version, so the explicit
pin overrides the transitive 2.12.5 from requirements.txt.

### Files to Modify
- `requirements-dev.txt` — add pydantic override pin

### Files NOT to Modify
- `requirements.txt` — production stays at 2.12.5
- `requirements-ci.txt` — already fixed
- Lambda requirements — use flexible ranges, unaffected
