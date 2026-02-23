# Implementation Plan: SSE Endpoint Implementation

**Branch**: `015-sse-endpoint-fix` | **Date**: 2025-12-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/015-sse-endpoint-fix/spec.md`

## Summary

Implement Server-Sent Events (SSE) endpoints for the dashboard to enable real-time updates. The dashboard currently shows "Disconnected" because the SSE endpoint (`/api/v2/stream`) returns 404. This feature adds both a global metrics stream and configuration-specific streams, with comprehensive unit and E2E tests.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, sse-starlette 3.0.3 (already installed), boto3, pydantic
**Storage**: DynamoDB (existing single-table design)
**Testing**: pytest, pytest-asyncio, httpx (unit), moto (mocking)
**Target Platform**: AWS Lambda with Function URLs
**Project Type**: Web application (serverless backend + static frontend dashboard)
**Performance Goals**: 100 concurrent SSE connections, heartbeat every 15-30 seconds
**Constraints**: Lambda Function URL streaming response, graceful degradation to polling
**Scale/Scope**: Small team/department scale (100 users max)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status | Notes |
|------|-------------|--------|-------|
| Security | All endpoints require authentication | ✅ Pass | FR-006: Config-specific SSE requires auth; Global stream is read-only metrics |
| Observability | Structured logging, metrics | ✅ Pass | FR-016, FR-017: Log open/close, emit connection count metrics |
| Testing | Unit + Integration tests | ✅ Pass | FR-012-014: Unit tests without network, E2E validates headers |
| Deployment | IaC, Lambda/DynamoDB | ✅ Pass | Uses existing Lambda deployment, no new infrastructure |
| Data Privacy | No raw text in responses | ✅ Pass | SSE events contain aggregated metrics, not raw content |

## Project Structure

### Documentation (this feature)

```text
specs/015-sse-endpoint-fix/
├── plan.md              # This file
├── research.md          # Phase 0: sse-starlette patterns, Lambda streaming
├── data-model.md        # Phase 1: SSE event schema
├── quickstart.md        # Phase 1: How to test SSE locally
├── contracts/           # Phase 1: SSE endpoint contracts
│   └── sse-endpoints.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   └── dashboard/
│       ├── handler.py         # Add SSE endpoints here
│       ├── router_v2.py       # Wire SSE router
│       └── sse.py             # NEW: SSE streaming logic
└── dashboard/
    ├── app.js                 # Already expects SSE (no changes needed)
    └── config.js              # Already has ENDPOINTS.STREAM configured

tests/
├── unit/
│   └── dashboard/
│       └── test_sse.py        # NEW: Unit tests for SSE module
├── e2e/
│   └── test_sse.py            # UPDATE: Make tests pass (not skip)
└── conftest.py                # May need SSE test fixtures
```

**Structure Decision**: Extend existing web application structure. Add `src/lambdas/dashboard/sse.py` for SSE-specific logic, keeping `handler.py` as the main entry point.

## Complexity Tracking

No constitution violations - this is a straightforward feature addition using an existing dependency.

---

## Post-Design Constitution Re-Check

| Gate | Requirement | Status | Verification |
|------|-------------|--------|--------------|
| Security | Auth required for protected endpoints | ✅ Pass | Config-specific stream requires Authorization header (contracts/sse-endpoints.md) |
| Observability | Logging + metrics | ✅ Pass | ConnectionManager tracks count; FR-016/FR-017 specify logging |
| Testing | Unit + E2E coverage | ✅ Pass | Unit tests mock generators; E2E tests validate HTTP (research.md) |
| Deployment | Uses existing IaC | ✅ Pass | No new Terraform resources needed |
| Data Privacy | No raw text exposure | ✅ Pass | Events contain aggregated metrics only (data-model.md) |

**Gate Status**: All gates pass. Ready for Phase 2 task generation.

---

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Research | [research.md](./research.md) | sse-starlette patterns, Lambda streaming, testing strategy |
| Data Model | [data-model.md](./data-model.md) | SSE event schemas, connection manager |
| Contracts | [contracts/sse-endpoints.md](./contracts/sse-endpoints.md) | API endpoint specifications |
| Quickstart | [quickstart.md](./quickstart.md) | Local development and testing guide |

---

## Next Steps

Run `/speckit.tasks` to generate implementation tasks from this plan.
