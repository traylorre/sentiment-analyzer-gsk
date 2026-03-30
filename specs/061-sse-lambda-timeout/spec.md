# Feature Specification: SSE Lambda Timeout Resolution

**Feature ID**: 061
**Status**: Draft
**Created**: 2025-12-08
**Target Repo**: sentiment-analyzer-gsk

## Problem Statement

The SSE (Server-Sent Events) streaming Lambda function (`preprod-sentiment-sse-streaming`) is timing out during integration tests, causing 7 test failures in the CI/CD pipeline. This is blocking full pipeline success even though infrastructure deployment is complete.

### Error Evidence

From pipeline run 20016262749 (2025-12-08):

```
FAILED tests/e2e/test_dashboard_buffered.py::test_configs_list_returns_json - AssertionError: assert False
FAILED tests/e2e/test_dashboard_buffered.py::test_alerts_list_returns_json - AssertionError: assert False
FAILED tests/e2e/test_sse.py::test_global_stream_available - httpx.ReadTimeout
FAILED tests/e2e/test_sse.py::test_sse_connection_established - httpx.ReadTimeout
FAILED tests/e2e/test_sse.py::test_sse_receives_sentiment_update - httpx.ReadTimeout
FAILED tests/e2e/test_sse.py::test_sse_receives_refresh_event - httpx.ReadTimeout
FAILED tests/e2e/test_sse.py::test_sse_reconnection_with_last_event_id - httpx.ReadTimeout

= 7 failed, 145 passed, 85 skipped, 2218 deselected, 4 warnings in 171.81s =
```

### Root Cause Hypotheses

1. **Cold Start**: Container-based Lambda with large ML dependencies (torch, transformers) may have extended cold start time
2. **Function URL Configuration**: SSE requires `RESPONSE_STREAM` invoke mode, may be misconfigured
3. **Reserved Concurrency**: Lambda may be set to 0 reserved concurrency blocking invocations
4. **Application Code**: SSE endpoint handler may have bugs preventing response
5. **Network/CORS**: Function URL may have misconfigured CORS or network settings

## User Stories

### US1: Diagnose SSE Lambda Timeout (Priority: P1)

**As a** developer,
**I want** to understand why the SSE Lambda is timing out,
**So that** I can implement the correct fix.

**Acceptance Criteria**:

- AC1.1: CloudWatch logs reviewed for error messages
- AC1.2: Lambda configuration verified (invoke mode, timeout, memory)
- AC1.3: Function URL configuration verified
- AC1.4: Root cause identified and documented

### US2: Fix SSE Lambda Connectivity (Priority: P1)

**As a** developer,
**I want** the SSE Lambda to respond to requests within timeout,
**So that** integration tests pass.

**Acceptance Criteria**:

- AC2.1: SSE Lambda responds to health check within 10 seconds
- AC2.2: SSE streaming connection established within 30 seconds
- AC2.3: All 7 failing tests pass

### US3: Optimize Cold Start (Priority: P2)

**As a** developer,
**I want** to minimize SSE Lambda cold start time,
**So that** tests are reliable and user experience is good.

**Acceptance Criteria**:

- AC3.1: Cold start < 15 seconds
- AC3.2: Warm invocation < 1 second
- AC3.3: Provisioned concurrency evaluated (cost vs performance)

## Functional Requirements

### FR-001: Lambda Configuration Audit

- Verify invoke mode is `RESPONSE_STREAM` for SSE support
- Verify timeout >= 60 seconds for streaming connections
- Verify memory >= 512MB for ML dependencies

### FR-002: Function URL Verification

- Verify Function URL is enabled
- Verify auth type matches test expectations (NONE or IAM)
- Verify CORS configuration allows test origins

### FR-003: Application Health Check

- SSE Lambda must have `/health` endpoint
- Health endpoint must return 200 within 5 seconds
- Health endpoint must not require streaming

### FR-004: Cold Start Optimization

- Consider Lambda Layers for common dependencies
- Consider smaller base image
- Consider provisioned concurrency for preprod/prod

## Non-Functional Requirements

### NFR-001: Performance

- Cold start: < 15 seconds
- Warm invocation: < 1 second
- SSE connection establishment: < 5 seconds

### NFR-002: Reliability

- Tests must pass consistently (no flaky timeouts)
- Lambda must handle concurrent connections

### NFR-003: Cost

- Provisioned concurrency only if cold start > 10 seconds
- Memory optimization to minimize cost

## Technical Context

### Current Configuration (from Terraform)

```hcl
# modules/lambda/main.tf
resource "aws_lambda_function" "this" {
  function_name = "${var.environment}-sentiment-sse-streaming"
  package_type  = "Image"
  image_uri     = "${var.ecr_repository_url}:latest"

  memory_size = var.memory_size  # Need to verify actual value
  timeout     = var.timeout      # Need to verify actual value

  reserved_concurrent_executions = var.reserved_concurrency  # May be 0!
}
```

### Investigation Commands

```bash
# Check Lambda configuration
aws lambda get-function-configuration --function-name preprod-sentiment-sse-streaming

# Check Function URL configuration
aws lambda get-function-url-config --function-name preprod-sentiment-sse-streaming

# Check recent invocations
aws logs tail /aws/lambda/preprod-sentiment-sse-streaming --since 30m

# Test health endpoint
curl -v "$(aws lambda get-function-url-config --function-name preprod-sentiment-sse-streaming --query 'FunctionUrl' --output text)health"
```

## Dependencies

### Blocked By

- Feature 060 (Pipeline Unblock) - COMPLETED

### Blocks

- Full pipeline success
- Production deployment

## Success Criteria

- SC-001: All 7 failing SSE tests pass
- SC-002: Pipeline completes successfully through production
- SC-003: SSE streaming works in preprod environment
- SC-004: No increase in Lambda costs > $5/month

## Out of Scope

- Dashboard API fixes (test_configs_list, test_alerts_list may be separate issue)
- Production provisioned concurrency (evaluate first)
- SSE feature enhancements

## Risks

| Risk                                 | Likelihood | Impact | Mitigation                                 |
| ------------------------------------ | ---------- | ------ | ------------------------------------------ |
| Large cold start inherent to ML deps | High       | High   | Evaluate provisioned concurrency           |
| Test timeout too short               | Medium     | Medium | Increase test timeout if Lambda is working |
| Application bug                      | Medium     | High   | Review SSE handler code                    |

## References

- [AWS Lambda Response Streaming](https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html)
- [Lambda Function URLs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html)
- [Lambda Cold Start Optimization](https://docs.aws.amazon.com/lambda/latest/operatorguide/cold-start.html)
- Pipeline run: https://github.com/traylorre/sentiment-analyzer-gsk/actions/runs/20016262749
