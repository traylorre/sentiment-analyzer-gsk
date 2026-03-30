# Spec: 1278-pydantic-dev-pin

## Problem Statement

`requirements-dev.txt` includes production dependencies via `-r requirements.txt`, which pins
`pydantic==2.12.5`. However, `requirements-dev.txt` also declares `moto[all]==5.1.22`, which
requires `pydantic<=2.12.4`. This version conflict causes pip install failures in the Deploy
Pipeline and local development environments.

The identical fix was already applied to `requirements-ci.txt` but was missed in
`requirements-dev.txt`.

## Requirements

### Functional
1. `pip install -r requirements-dev.txt` MUST succeed without version conflicts
2. `pydantic==2.12.4` MUST be explicitly pinned in `requirements-dev.txt`
3. The pin MUST appear AFTER the `-r requirements.txt` include to override the transitive 2.12.5
4. An explanatory comment MUST accompany the pin (matching CI pattern)

### Non-Functional
1. Production `requirements.txt` MUST NOT be modified (stays at 2.12.5)
2. `requirements-ci.txt` MUST NOT be modified (already correct)
3. Lambda requirements MUST NOT be modified (use flexible ranges)

## Acceptance Criteria
- [ ] `pip install -r requirements-dev.txt` resolves without conflict
- [ ] `pip install -r requirements-ci.txt` continues to resolve without conflict
- [ ] `pip install -r requirements.txt` continues to install pydantic 2.12.5
- [ ] Comment explains WHY the override exists

## Scope
- 1 file modified: `requirements-dev.txt`
- 2 lines added (comment + pin)
- Zero code changes
- Zero infrastructure changes

## Risk Assessment
- **Risk**: LOW. Adding an explicit version pin to override a transitive dependency.
- **Rollback**: Remove the 2 added lines.
- **Blast radius**: Dev/test environments only. Production unaffected.
