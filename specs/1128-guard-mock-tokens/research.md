# Research: Guard Mock Token Generation

**Feature**: 1128-guard-mock-tokens
**Date**: 2026-01-05

## Summary

Minimal research required - this feature uses a well-established AWS pattern for Lambda environment detection.

## AWS Lambda Environment Detection

### Decision: Use `AWS_LAMBDA_FUNCTION_NAME`

**Rationale**: This is the canonical AWS-recommended way to detect Lambda runtime environment.

**Alternatives Considered**:
1. `AWS_EXECUTION_ENV` - Also set by AWS, but format varies (e.g., `AWS_Lambda_python3.13`)
2. `LAMBDA_TASK_ROOT` - Set to `/var/task`, but less semantically clear
3. `_HANDLER` - Contains handler path, but not as universally reliable

**Why `AWS_LAMBDA_FUNCTION_NAME` is best**:
- Always set in Lambda, never set locally
- Contains clear, readable value (the function name)
- Documented in official AWS Lambda environment variables docs
- LocalStack also sets this variable for realistic testing
- Used by AWS SDK and other AWS tooling for detection

## Implementation Pattern

```python
import os

# Standard Lambda detection pattern
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    # Running in Lambda
    pass
else:
    # Running locally or in non-Lambda environment
    pass
```

## Security Considerations

- **Defense in depth**: This guard is one layer; production should also have real Cognito integration
- **Fail-closed**: If detection fails somehow, better to block mock tokens than allow them
- **Logging**: ERROR-level log enables security monitoring and alerting

## References

- AWS Lambda Environment Variables: https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html
- LocalStack Lambda Support: https://docs.localstack.cloud/user-guide/aws/lambda/
