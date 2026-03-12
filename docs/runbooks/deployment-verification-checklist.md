# Deployment Verification Checklist

Verify native Lambda operation after deployment. All Lambdas must respond without any legacy framework dependencies.

## Dashboard Lambda (Container, BUFFERED mode)
- [ ] Health check: `curl <FUNCTION_URL>/api/v2/health` returns HTTP 200
- [ ] Response body contains `{"status": "healthy"}` or similar JSON
- [ ] CloudWatch logs show no import errors for removed packages

## SSE Streaming Lambda (Container, RESPONSE_STREAM mode)
- [ ] Health check: `curl <FUNCTION_URL>/health` returns HTTP 200
- [ ] Response includes streaming headers (`Transfer-Encoding: chunked` or `Content-Type: text/event-stream`)
- [ ] CloudWatch logs show custom runtime bootstrap initialized successfully

## ZIP Lambdas (ingestion, metrics, notification, analysis)
- [ ] CloudWatch logs confirm successful cold start invocations
- [ ] No `ModuleNotFoundError` for any removed packages in logs
- [ ] Event processing completes without framework-related errors

## CI/CD Pipeline
- [ ] `make validate` passes (includes banned-term scanner)
- [ ] All unit tests pass
- [ ] Docker image builds succeed without legacy dependencies
- [ ] Smoke tests in deploy.yml pass
