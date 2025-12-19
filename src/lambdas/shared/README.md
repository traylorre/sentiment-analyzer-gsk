# Shared Lambda Utilities

## Purpose

Common code used by multiple Lambda functions. Each module is independently tested.

## Modules

### dynamodb.py
DynamoDB table operations with retry configuration.

**On-Call Note**: If you see `ProvisionedThroughputExceededException`, check CloudWatch
alarm `${environment}-dynamodb-write-throttles`. Table uses on-demand billing, so this
indicates extreme traffic spike.

### secrets.py
Secrets Manager integration with in-memory caching (5-minute TTL).

**On-Call Note**: If secrets fail to load, check:
1. Secret exists: `aws secretsmanager describe-secret --secret-id dev/sentiment-analyzer/tiingo`
2. Lambda IAM role has `secretsmanager:GetSecretValue` permission
3. Cache may be stale - Lambda cold start will refresh

### schemas.py
Pydantic models for data validation.

**On-Call Note**: Validation errors appear as `VALIDATION_ERROR` in logs. Check the
`details` field for specific field failures.

### errors.py
Standardized error response format.

**Error Codes** (for log filtering):
- `RATE_LIMIT_EXCEEDED` - External API throttling
- `VALIDATION_ERROR` - Input validation failure
- `NOT_FOUND` - Resource not found
- `SECRET_ERROR` - Secrets Manager failure
- `DATABASE_ERROR` - DynamoDB operation failure

## Security

- Never log secret values (only ARNs)
- Use parameterized DynamoDB expressions (no string interpolation)
- Validate all external input through Pydantic schemas
