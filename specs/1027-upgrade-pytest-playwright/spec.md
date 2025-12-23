# Feature Specification: Upgrade pytest-playwright for pytest 9.0+ Compatibility

**Branch**: `1027-upgrade-pytest-playwright`
**Created**: 2025-12-22
**Status**: Implementation
**Priority**: P1 - CI Blocking

## Purpose

Upgrade pytest-playwright from 0.5.2 to >=0.7.2 to resolve version compatibility with pytest 9.0.2. Current version 0.5.2 enforces `pytest<9.0.0` constraint, blocking clean dependency resolution.

## Problem Statement

- `requirements-dev.txt` pins `pytest-playwright==0.5.2`
- Version 0.5.2 requires `pytest<9.0.0` per PyPI metadata
- Project uses `pytest==9.0.2` (line 20 of requirements-dev.txt)
- Result: pip cannot resolve compatible versions

## Solution

Upgrade to pytest-playwright 0.7.2 (released November 2025) which explicitly adds pytest 9.0 support via PR #300.

## User Story 1 - Dependency Resolution (Priority: P1)

As a developer, I want pytest-playwright to install cleanly with pytest 9.0.2 so that E2E tests can run.

**Acceptance Scenarios**:

1. **Given** requirements-dev.txt with updated version, **When** pip install -r requirements-dev.txt, **Then** installation succeeds without version conflicts
2. **Given** updated dependencies, **When** running pytest tests/e2e/, **Then** all 7 E2E test files execute successfully

## User Story 2 - Async Fixture Compatibility (Priority: P1)

As a developer, I want async fixtures to continue working after the upgrade so that API client fixtures remain functional.

**Acceptance Scenarios**:

1. **Given** pytest-playwright 0.7.2, **When** pytest-asyncio fixtures load, **Then** @pytest_asyncio.fixture decorators work correctly
2. **Given** session-scoped event_loop fixture, **When** E2E tests run, **Then** async context managers function correctly

## Files to Modify

1. `requirements-dev.txt` line 48: `pytest-playwright==0.5.2` -> `pytest-playwright>=0.7.2`

## Validation

1. Local: `pip install -r requirements-dev.txt` succeeds
2. Local: `pytest tests/e2e/ -v --collect-only` shows all tests collected
3. CI: pr-checks.yml workflow passes

## Version Changelog Notes (0.5.2 -> 0.7.2)

- 0.7.2: chore: support Pytest v9 (PR #300)
- 0.7.1: feat: add async/sync compatibility check
- 0.7.0: Internal improvements
- 0.6.x: Incremental fixes

## Rollback Plan

Revert requirements-dev.txt to `pytest-playwright==0.5.2`. This would also require downgrading pytest to <9.0.0.
