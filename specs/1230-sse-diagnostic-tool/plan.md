# Implementation Plan: SSE Diagnostic Tool

**Branch**: `1230-sse-diagnostic-tool` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1230-sse-diagnostic-tool/spec.md`

## Summary

A CLI tool that connects to the SSE streaming endpoint and displays events in human-readable format. Supports filtering by event type and ticker, automatic reconnection with Last-Event-ID, and prints a session health summary on disconnect. Single Python script with no external dependencies beyond the standard library and existing project packages.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: Standard library only (`urllib.request`, `json`, `argparse`, `signal`). No new packages.
**Storage**: None (stateless CLI tool, in-memory event counters only)
**Testing**: pytest with mock HTTP responses
**Target Platform**: Developer workstation (Linux/macOS)
**Project Type**: Single script CLI utility
**Performance Goals**: Connect and display first event within 35 seconds
**Constraints**: No configuration files; single command with URL argument
**Scale/Scope**: 1 Python script + 1 test file

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (unit tests) | PASS | Tests for event parsing, filtering, summary |
| Deterministic time handling in tests | PASS | Mock SSE responses, no time-dependent logic |
| External dependency mocking | PASS | Mock HTTP connection in tests |
| GPG-signed commits | PASS | Standard workflow |
| Feature branch workflow | PASS | Branch `1230-sse-diagnostic-tool` |
| SAST/lint pre-push | PASS | `make validate` |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1230-sse-diagnostic-tool/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
└── tasks.md
```

### Source Code

```text
scripts/
└── sse_diagnostic.py          # NEW: The diagnostic tool

tests/
└── unit/
    └── test_sse_diagnostic.py  # NEW: Unit tests
```

**Structure Decision**: Single script in `scripts/` directory (same as `run-local-api.py`). Not a package — it's a developer utility invoked directly.
