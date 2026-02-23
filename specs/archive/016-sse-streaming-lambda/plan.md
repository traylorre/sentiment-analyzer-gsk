# Implementation Plan: SSE Streaming Lambda

**Branch**: `016-sse-streaming-lambda` | **Date**: 2025-12-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-sse-streaming-lambda/spec.md`

## Summary

Deploy a dedicated SSE Lambda function using AWS Lambda Web Adapter with RESPONSE_STREAM invoke mode, separate from the existing Mangum-based dashboard Lambda (BUFFERED mode). This two-Lambda architecture resolves the fundamental incompatibility between Mangum's buffered response handling and Lambda's streaming response mode required for real-time SSE.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI, sse-starlette, boto3, aws-xray-sdk, AWS Lambda Web Adapter
**Storage**: DynamoDB (existing tables - read-only access for SSE Lambda)
**Testing**: pytest, pytest-asyncio, httpx, moto (unit), real AWS (E2E)
**Target Platform**: AWS Lambda with Function URL (RESPONSE_STREAM mode)
**Project Type**: Serverless Lambda (Docker-based for Web Adapter)
**Performance Goals**: <5s end-to-end latency, 100 concurrent connections/instance, <2s cold start
**Constraints**: 15-minute Lambda timeout (clients handle reconnection), 100 connection limit per instance
**Scale/Scope**: Production-ready SSE streaming for sentiment dashboard

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|-------------|--------|-------|
| **1) Functional** - Ingest/sentiment analysis | N/A | SSE Lambda is read-only, no ingestion |
| **2) Non-Functional** - 99.5% SLA, P90 ≤500ms | PASS | SSE is streaming, latency measured differently |
| **3) Security** - Auth for admin endpoints | PASS | Config-specific streams require X-User-ID auth |
| **4) Data** - Output schema, no raw text | PASS | SSE events contain only aggregated metrics |
| **5) Deployment** - IaC, serverless preferred | PASS | Terraform + Docker Lambda |
| **6) Observability** - X-Ray, CloudWatch | PASS | FR-016, FR-017, FR-018 specify observability |
| **7) Testing** - Unit + E2E, mocked externals | PASS | Unit with moto, E2E with real AWS |
| **8) Git Workflow** - GPG signed, no bypass | PASS | Standard workflow applies |
| **9) Tech Debt** - Registry tracking | PASS | Any shortcuts documented in registry |

**Gate Status**: PASS - No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/016-sse-streaming-lambda/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── sse-events.md    # SSE event contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   ├── dashboard/           # Existing - BUFFERED mode (no changes)
│   │   ├── handler.py       # Mangum-based handler
│   │   └── sse.py           # Existing SSE module (to be extracted)
│   └── sse_streaming/       # NEW - RESPONSE_STREAM mode
│       ├── Dockerfile       # Docker image with Lambda Web Adapter
│       ├── handler.py       # Main Lambda handler
│       ├── stream.py        # SSE streaming logic
│       ├── connection.py    # Connection pool management
│       └── metrics.py       # CloudWatch custom metrics

infrastructure/terraform/
├── main.tf                  # Add SSE Lambda module instance
└── modules/
    └── lambda/              # Existing module (supports Docker)

tests/
├── unit/
│   └── sse_streaming/       # Unit tests for new Lambda
└── e2e/
    └── test_sse.py          # Update existing E2E tests
```

**Structure Decision**: Single Lambda project added to existing monorepo. SSE streaming code is isolated in `src/lambdas/sse_streaming/` to maintain separation from dashboard Lambda while sharing common utilities from `src/lambdas/shared/`.

## Complexity Tracking

> No violations requiring justification. Two-Lambda architecture is the simplest solution to the Mangum/RESPONSE_STREAM incompatibility.
