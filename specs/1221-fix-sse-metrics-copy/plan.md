# Implementation Plan: Fix SSE Lambda Dockerfile Missing Metrics Module

**Branch**: `1221-fix-sse-metrics-copy` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1221-fix-sse-metrics-copy/spec.md`

## Summary

The SSE Lambda Docker image is missing `src/lib/metrics.py`, causing a
`ModuleNotFoundError` during the deploy pipeline smoke test. The `fanout.py` module
(in `lib/timeseries/`) was updated in PR #720 to import `src.lib.metrics.emit_metric`,
but the SSE Dockerfile only copies `lib/timeseries/`, not `lib/metrics.py`. The fix
adds a single COPY instruction to include the metrics module in the container image.

## Technical Context

**Language/Version**: Dockerfile (Docker multi-stage build), Python 3.13 (runtime)
**Primary Dependencies**: Docker, aws-lambda-powertools, boto3
**Storage**: N/A (no data storage changes)
**Testing**: Existing CI smoke test (Python import verification inside container)
**Target Platform**: AWS Lambda (container image deployment via ECR)
**Project Type**: Single project (serverless backend)
**Performance Goals**: N/A (no runtime performance change)
**Constraints**: Minimal image size increase (ADOT sidecar already adds weight)
**Scale/Scope**: Single file change in one Dockerfile

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
| ---- | ------ | ----- |
| Deployment Requirements (Section 5) | PASS | Docker container image, IaC managed |
| Testing (Section 7) | PASS | Existing smoke test validates imports; no new logic to unit test |
| Implementation Accompaniment Rule | PASS | No new code logic; Dockerfile COPY is configuration, not testable code |
| Git Workflow (Section 8) | PASS | Feature branch, GPG-signed commits, PR workflow |
| Security (Section 3) | PASS | No new endpoints, no secrets, no user input |
| Local SAST (Section 10) | PASS | No Python code changes; Dockerfile is not scanned by Bandit/Semgrep |

No constitution violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/1221-fix-sse-metrics-copy/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   └── sse_streaming/
│       └── Dockerfile     # MODIFIED: Add COPY lib/metrics.py
└── lib/
    ├── metrics.py         # Existing file (source for COPY)
    └── timeseries/        # Already copied by Dockerfile
```

**Structure Decision**: Only the SSE Lambda Dockerfile is modified. The metrics module
already exists at `src/lib/metrics.py`. The analysis and dashboard Dockerfiles already
copy the entire `lib/` directory and are unaffected.
