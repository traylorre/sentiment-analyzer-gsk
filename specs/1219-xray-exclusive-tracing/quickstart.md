# Quickstart: X-Ray Exclusive Tracing

**Feature**: 1219-xray-exclusive-tracing | **Branch**: `1219-xray-exclusive-tracing`

## Prerequisites

- Python 3.13
- Docker (for SSE Lambda container builds)
- AWS CLI configured (for preprod verification)
- `gh` CLI authenticated

## Getting Started

```bash
# Switch to feature branch
cd /home/zeebo/projects/sentiment-analyzer-gsk
git checkout 1219-xray-exclusive-tracing
git pull origin 1219-xray-exclusive-tracing

# Install dependencies
pip install -e ".[dev]"

# Verify existing tests pass
pytest tests/unit/ -m unit --timeout=60
```

## Task Execution Order

Follow the 6-phase deployment ordering (FR-107):

### Phase 1: IAM Foundation (Task 1)

```bash
# Edit infrastructure/terraform/modules/iam/main.tf
# Add X-Ray permissions to Ingestion, Analysis, Dashboard, Metrics roles
# See: docs/x-ray/fix-iam-permissions.md

# Validate
cd infrastructure/terraform && terraform plan
```

### Phase 2: Instrumentation (Tasks 14, 2, 3, 4, 5, 13)

```bash
# Task 14: Standardize on Powertools Tracer
# See: docs/x-ray/fix-tracer-standardization.md
# Migrate 57 @xray_recorder.capture decorators

# Task 5: SSE Lambda ADOT Extension
# See: docs/x-ray/fix-sse-subsegments.md
# Build SSE container with ADOT Extension

# Run unit tests after each task
pytest tests/unit/ -m unit --timeout=60
```

### Phase 3: Frontend (Tasks 10, 15)

```bash
# Task 15: Migrate EventSource to fetch()+ReadableStream
# See: docs/x-ray/fix-sse-client-fetch-migration.md

# Frontend tests
cd frontend && npm test
```

### Phase 4: Logging Removal (Tasks 6, 7, 9)

**WAIT**: Minimum 2-week dual-emit period required (FR-109).

```bash
# Only after Phase 2 verified in production for 2+ weeks
# See: docs/x-ray/fix-sse-latency-xray.md (Task 6)
# See: docs/x-ray/fix-sse-cache-xray.md (Task 7)
# See: docs/x-ray/fix-correlation-id-consolidation.md (Task 9)
```

### Phase 5: Monitoring (Tasks 8, 16, 17)

```bash
# Task 17: Deploy CloudWatch alarms (~35 alarms)
# See: docs/x-ray/fix-alarm-coverage.md

# Task 16: Configure X-Ray sampling rules
# See: docs/x-ray/fix-sampling-and-cost.md
```

### Phase 6: Validation (Tasks 11, 12)

```bash
# Task 11: Deploy X-Ray canary Lambda
# See: docs/x-ray/fix-xray-canary.md

# Task 12: Downstream consumer audit
# See: docs/x-ray/fix-downstream-consumer-audit.md
```

## Key Environment Variables (SSE Lambda)

```bash
# OTel SDK (SSE Lambda only)
OTEL_SERVICE_NAME=sentiment-analyzer-sse
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SDK_DISABLED=false
OTEL_EXPORTER_OTLP_TRACES_TIMEOUT=2
OPENTELEMETRY_COLLECTOR_CONFIG_FILE=/opt/collector-config/config.yaml
```

## Testing Strategy

| Test Type | Command | When |
|-----------|---------|------|
| Unit | `pytest tests/unit/ -m unit` | After every code change |
| Integration | `pytest tests/integration/ -m integration` | After Lambda handler changes |
| E2E | `pytest tests/e2e/ -m preprod` | After deployment to preprod |
| Frontend | `npx playwright test` | After frontend SSE changes |

## Verification Gates

| Gate | When | Criteria |
|------|------|----------|
| Phase 2 | After instrumentation deploy | SC-110: ≥95% streaming span retention |
| Phase 3 | After frontend deploy | SC-085: X-Amzn-Trace-Id on all fetch() |
| Phase 4 | After 2-week dual-emit | FR-109: 4 verification checks pass |
| Phase 6 | After canary deploy | SC-063: completeness_ratio ≥ 95% |

## Rollback Procedure (FR-122)

```bash
# SSE Lambda (ADOT rollback): Switch to pre-adot-baseline image (~2min)
aws ecr describe-images --repository-name sse-lambda --image-ids imageTag=pre-adot-baseline

# Standard Lambda rollback: Revert Terraform and apply
git revert HEAD && terraform apply

# Kill switch (zero rebuild): Set OTEL_SDK_DISABLED=true in Lambda config
aws lambda update-function-configuration \
  --function-name sse-streaming \
  --environment "Variables={OTEL_SDK_DISABLED=true,...}"
```

## Common Gotchas

1. **begin_segment() is a no-op in Lambda** — don't try to create independent X-Ray segments
2. **EventSource has no custom headers** — must use fetch()+ReadableStream for trace propagation
3. **Warm invocations use stale _X_AMZN_TRACE_ID** — custom bootstrap must update per-invocation
4. **force_flush() timeout is not enforced** — use thread wrapper with hard timeout
5. **ADOT Extension has ZERO span processors** — all processing in Python SDK
6. **set_attribute() bypasses SpanProcessor.on_start()** — CI gate is the only PII defense
