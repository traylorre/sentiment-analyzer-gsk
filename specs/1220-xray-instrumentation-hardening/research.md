# Research: X-Ray Instrumentation Hardening

**Feature**: 1220-xray-instrumentation-hardening | **Date**: 2026-03-14

## R1: ADOT Lambda Extension for Container Images

**Decision**: Use only the ADOT Collector Layer (sidecar binary), not the Python SDK Layer.

**Rationale**: SSE Lambda manages its own OTel SDK (pinned 1.39.1). The Python SDK Layer bundles its own version causing conflicts. The Collector Layer is protocol-level (OTLP) and version-agnostic.

**Alternatives considered**:
- Full ADOT Python SDK Layer: Rejected (version conflict with OTel SDK 1.39.x)
- aws-xray-sdk directly: Rejected (SSE streaming phase uses OTel spans, not xray segments)

**Details**:
- Layer ARN: arn:aws:lambda:REGION:901920570463:layer:aws-otel-collector-amd64-ver-0-102-1:1
- Download: aws lambda get-layer-version-by-arn --arn ARN --query Content.Location --output text
- Contents: /opt/extensions/collector binary + /opt/collector-config/config.yaml
- Default config exports to X-Ray (no custom collector.yaml needed)
- OTel SDK sends to collector via http://localhost:4318 (already in tracing.py line 75)

## R2: IAM Permissions for Layer Download

**Decision**: IAM policy update REQUIRED.

**Rationale**: lambda:GetLayerVersion is granted but scoped to arn:aws:lambda:*:*:layer:*-sentiment-* which does NOT match the ADOT public layer ARN (account 901920570463). Real-world test confirmed AccessDeniedException. Must add a statement allowing lambda:GetLayerVersion on arn:aws:lambda:*:901920570463:layer:aws-otel-collector-* or use a broader approach.

**File to modify**: infrastructure/terraform/ci-user-policy.tf — add ADOT layer ARN to allowed resources.

## R3: Frontend Trace ID Generation

**Decision**: Lightweight ~20-line utility using crypto.getRandomValues() for X-Ray format.

**Rationale**: X-Ray trace ID format is simple. Full AWS RUM SDK (~200KB+) is overweight for header injection only. OTel JS SDK uses W3C traceparent format, not X-Ray format.

**Details**:
- Root: 1-{hex_timestamp}-{96bit_random_hex}
- Parent: {64bit_random_hex}
- Sampled: Always 1 (backend sampling rules make final decision)

## R4: CORS Terraform Change Scope

**Decision**: Add x-amzn-trace-id to allow_headers and expose_headers on SSE and Dashboard Lambda Function URLs.

**Files**: infrastructure/terraform/main.tf lines 764, 769 (SSE) and 439, ~445 (Dashboard)

## R5: Fanout Metric Pattern

**Decision**: Copy established pattern from circuit_breaker.py (lines 343-357). Add new ConditionalCheck/Count metric for optimistic locking contention.

**Pattern**: Best-effort X-Ray subsegment annotation + emit_metric("SilentFailure/Count", 1, "Count", dimensions={"FailurePath": "..."}, namespace="SentimentAnalyzer/Reliability")
