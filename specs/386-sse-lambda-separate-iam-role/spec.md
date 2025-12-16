# Spec 386: Separate IAM Role for SSE Lambda

## Problem Statement

The SSE Lambda currently reuses the Dashboard Lambda's IAM role (`preprod-dashboard-lambda-role`). This causes two issues:

1. **Missing permissions**: The Dashboard role lacks `dynamodb:Scan` which the SSE Lambda needs for metrics polling, causing `AccessDeniedException` errors.

2. **Architectural smell**: Sharing roles between Lambdas with different purposes violates least-privilege principle and increases blast radius.

## Root Cause Analysis

From CloudWatch logs:
```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the Scan operation:
User: arn:aws:sts::218795110243:assumed-role/preprod-dashboard-lambda-role/preprod-sentiment-sse-streaming
is not authorized to perform: dynamodb:Scan
```

The SSE Lambda needs to scan the `sentiment-items` table for metrics aggregation, but the Dashboard role only grants `Query`, `GetItem`, and `DescribeTable`.

## Solution

Create a dedicated IAM role for the SSE Lambda with exactly the permissions it needs:

### Required Permissions

| Service | Actions | Resource | Reason |
|---------|---------|----------|--------|
| DynamoDB | `Scan` | sentiment-items table | Metrics polling every 5s |
| DynamoDB | `Query`, `GetItem` | sentiment-items table | Config validation |
| CloudWatch Logs | Basic execution | Log group | Standard Lambda logging |
| CloudWatch | `PutMetricData` | SentimentAnalyzer/SSE namespace | Custom metrics |
| X-Ray | Write access | Traces | Distributed tracing |

### Permissions NOT Needed (vs Dashboard Role)

- DynamoDB access to Feature 006 users table
- Secrets Manager access
- S3 ticker cache access
- FIS chaos testing permissions
- DynamoDB access to chaos_experiments table

## Implementation

### Files to Modify

1. `infrastructure/terraform/modules/iam/main.tf` - Add SSE role definition
2. `infrastructure/terraform/modules/iam/outputs.tf` - Export SSE role ARN
3. `infrastructure/terraform/main.tf` - Use SSE role for SSE Lambda

### Terraform Pattern

Follow the established pattern from ingestion Lambda:
1. Create role with trust policy for Lambda service
2. Create inline policies per AWS service
3. Attach managed policies for common permissions
4. Output role ARN

### Role Definition

```hcl
resource "aws_iam_role" "sse_streaming_lambda" {
  name = "${var.environment}-sse-streaming-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Environment = var.environment
    Feature     = "016-sse-streaming-lambda"
    Lambda      = "sse-streaming"
  }
}
```

### DynamoDB Policy

```hcl
resource "aws_iam_role_policy" "sse_streaming_dynamodb" {
  name = "${var.environment}-sse-streaming-dynamodb-policy"
  role = aws_iam_role.sse_streaming_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:GetItem"
      ]
      Resource = var.dynamodb_table_arn
    }]
  })
}
```

## Acceptance Criteria

- [ ] SSE Lambda has its own IAM role separate from Dashboard
- [ ] SSE Lambda can successfully scan DynamoDB for metrics
- [ ] SSE Lambda CloudWatch logs show no AccessDeniedException
- [ ] Role follows least-privilege principle
- [ ] Existing Dashboard Lambda functionality is unchanged

## Test Plan

1. Deploy to preprod
2. Invoke SSE Lambda `/api/v2/stream` endpoint
3. Check CloudWatch logs for successful DynamoDB scans
4. Verify metrics appear in CloudWatch under SentimentAnalyzer/SSE namespace
5. Run preprod integration tests

## Rollback

If issues occur, revert to using Dashboard role by changing:
```hcl
iam_role_arn = module.iam.dashboard_lambda_role_arn
```
