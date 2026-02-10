# Implementation Plan: FastAPI/Mangum Permanent Removal

**Branch**: `001-fastapi-purge` | **Date**: 2026-02-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-fastapi-purge/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Permanently remove FastAPI, Mangum, Uvicorn, Starlette, sse-starlette, and AWS Lambda Web Adapter from the sentiment-analyzer-gsk codebase. The dashboard Lambda (BUFFERED, 102 endpoints across 11 routers) transitions to AWS Lambda Powertools `APIGatewayRestResolver` for routing with "validation at the gate" via Pydantic request context objects. The SSE streaming Lambda (RESPONSE_STREAM, 5 endpoints) transitions to raw `awslambdaric` streaming using `HttpResponseStream`. All 62 functional requirements preserve 100% behavioral compatibility while eliminating ~15MB of framework dependencies.

## Technical Context

**Language/Version**: Python 3.13 (pyproject.toml `requires-python = ">=3.13"`, Lambda base image `public.ecr.aws/lambda/python:3.13`)
**Primary Dependencies**: aws-lambda-powertools 3.23.0 (routing, middleware), orjson (JSON serialization — new), pydantic 2.12.5 (validation), boto3 1.42.26 (AWS SDK), aws-xray-sdk 2.15.0 (tracing), awslambdaric (streaming — bundled in base image)
**Storage**: DynamoDB (existing tables unchanged), S3 (model artifacts unchanged)
**Testing**: pytest 7.4.3+ with pytest-asyncio, moto (AWS mocks), Hypothesis (property testing), Playwright (E2E)
**Target Platform**: AWS Lambda (container-based, ECR) with Lambda Function URLs
**Project Type**: single (Python monorepo with 6 Lambda functions sharing `src/lambdas/shared/`)
**Performance Goals**: Dashboard cold start reduced ≥10ms (SC-002), peak memory reduced ≥10MB (SC-003), SSE latency within 50ms baseline (SC-004), JSON serialization faster per invocation (SC-013)
**Constraints**: API Gateway 6MB response limit (FR-046), Lambda 15-min timeout for SSE streams, zero behavioral regression across 102 endpoints
**Scale/Scope**: 102 endpoints, 11 routers, 62 FRs, ~230 test files (22 TestClient migrations, 16 contract test migrations with 462 tests, 6 dependency_overrides migrations)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Evidence |
|------|--------|----------|
| All admin endpoints require authentication | PASS | FR-019, FR-031 preserve auth extraction from event headers/requestContext. No auth removal. |
| Secrets not in source control | PASS | No secrets changes. Existing AWS Secrets Manager integration unchanged. |
| TLS/HTTPS enforced | PASS | Lambda Function URLs enforce HTTPS. No transport changes. |
| No raw user text in logs | PASS | Logging patterns unchanged. FR-024 preserves traceback logging for errors only. |
| Unit tests accompany all implementation | PASS | FR-020, FR-038, FR-058-062 mandate test migration. SC-015 requires test count ≥ pre-migration. |
| 80% minimum coverage for new code | PASS | pyproject.toml `fail_under = 80`. No coverage reduction. |
| Deterministic time handling | PASS | No new time-dependent code introduced. Existing freezegun patterns preserved. |
| GPG-signed commits | PASS | Project standard enforced by pre-commit hooks. |
| Pipeline bypass never allowed | PASS | FR-055 updates CI/CD smoke tests before dependency removal to prevent breakage. |
| Local SAST required (Bandit + Semgrep) | PASS | No security patterns changed. Validation-at-gate improves input handling. |
| Environment testing matrix | PASS | LOCAL=unit+mocks, PREPROD=E2E+real AWS preserved. FR-058 adds mock event factory fixtures. |
| Integration tests use real AWS (no mocking own resources) | PASS | LocalStack integration tests preserved. Only TestClient transport layer changes. |
| No fallback/bypass patterns | PASS | FR-057 removes try/except ImportError fallbacks. Fail-fast principle enforced throughout. |

**Result: ALL GATES PASS. No violations. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-fastapi-purge/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions and rationale
├── data-model.md        # Phase 1: Request/response contract models
├── quickstart.md        # Phase 1: Developer migration guide
├── contracts/           # Phase 1: API contracts (OpenAPI fragments)
│   ├── dashboard-proxy-response.yaml
│   ├── sse-stream-response.yaml
│   ├── validation-error-422.yaml
│   └── mock-event-factory.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── lambdas/
│   ├── dashboard/
│   │   ├── Dockerfile           # CMD changes to Powertools handler
│   │   ├── handler.py           # FastAPI app → APIGatewayRestResolver
│   │   ├── router_v2.py         # FastAPI APIRouter → Powertools Router (9 routers)
│   │   ├── ohlc.py              # FastAPI router → Powertools Router
│   │   ├── alerts.py            # FastAPI router → Powertools Router
│   │   ├── sentiment.py         # Unchanged (business logic)
│   │   └── requirements.txt     # Remove fastapi, mangum, uvicorn
│   ├── sse_streaming/
│   │   ├── Dockerfile           # python:3.13-slim → public.ecr.aws/lambda/python:3.13
│   │   ├── handler.py           # FastAPI+LWA → raw awslambdaric RESPONSE_STREAM
│   │   ├── config.py            # Unchanged (business logic)
│   │   └── requirements.txt     # Remove fastapi, uvicorn, sse-starlette
│   └── shared/
│       ├── middleware/
│       │   ├── csrf_middleware.py    # FastAPI Request/Depends → raw event dict
│       │   └── require_role.py      # FastAPI Depends → raw event dict
│       ├── auth/                    # Extract from event["headers"] not FastAPI
│       └── models/                  # Pydantic models unchanged (validation-at-gate)
└── lib/                             # Unchanged (pure business logic)

tests/
├── conftest.py                      # Remove ohlc_test_client fixture, add mock event factory
├── contract/                        # 16 files: response.json() → json.loads(response["body"])
├── unit/
│   ├── dashboard/                   # TestClient → direct handler invocation
│   ├── lambdas/                     # dependency_overrides → unittest.mock.patch
│   ├── middleware/                   # FastAPI test patterns → event dict patterns
│   └── sse_streaming/               # Starlette TestClient → mock streaming
├── integration/
│   ├── ohlc/                        # dependency_overrides → unittest.mock.patch
│   └── sentiment_history/           # TestClient → direct handler invocation
├── property/
│   └── conftest.py                  # lambda_response strategy (already exists, extend)
└── e2e/                             # Unchanged (hits real infrastructure)

infrastructure/
└── terraform/
    └── modules/lambda/
        └── main.tf                  # Remove AWS_LWA_INVOKE_MODE, AWS_LWA_READINESS_CHECK_PATH env vars
```

**Structure Decision**: Single-project layout preserved. This is a refactoring migration, not a new feature. All changes are in-place modifications to existing files. No new directories or modules created beyond test fixtures (mock event factory in conftest.py).

## Complexity Tracking

> No constitution violations detected. This section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | —          | —                                   |
