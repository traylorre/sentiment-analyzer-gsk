# Audit Verdicts

> **CANON**: verified against code.

This file is the bucket for review and audit verdicts, amended in place; resolved findings are removed, not marked resolved.

## IAM and access posture

Every claim below is verified against `infrastructure/terraform/`.

### Dashboard API Gateway endpoint is intentionally unauthenticated

Accepted posture. `enable_cognito_auth = false` in `infrastructure/terraform/main.tf:879`, so
method authorization resolves to `NONE` throughout
`infrastructure/terraform/modules/api_gateway/main.tf` (lines 302, 583, 652). The Cognito
authorizer resources take `count = 0` under the same flag.

### SNS analysis-requests topic is publisher-restricted

The topic policy names the ingestion Lambda role ARN as the only allowed publisher
(`modules/sns/main.tf:45`). The earlier any-Lambda-in-account principal is gone.

### Metrics Lambda has the narrowest data access

Single `dynamodb:Query` on the `by_status` GSI, no base-table access, no writes
(`modules/iam/main.tf:740`).

### Dashboard is read-only on the sentiment-items table

`dashboard_dynamodb` grants only `Query`, `GetItem`, `DescribeTable` on the table and its three
GSIs (`modules/iam/main.tf:392`). The role as a whole is not write-free: it holds full CRUD on
the feature-006 users table, write access to the OHLC cache table, and a non-prod chaos policy
that includes `DeleteItem` and `lambda:UpdateFunctionConfiguration`. Scope any "read-only"
claim to the sentiment-items table.

### Secrets Manager access is ARN-scoped

Ingestion reads the Tiingo and Finnhub secrets; dashboard reads those plus the dashboard API
key secret. No wildcard secret ARNs. KMS `Decrypt` is granted only when a customer-managed key
is configured (`modules/iam/main.tf:61`, `modules/iam/main.tf:418`).

### CloudWatch metric writes are namespace-conditioned

`cloudwatch:PutMetricData` on `*` carries a `cloudwatch:namespace = "SentimentAnalyzer"`
condition (verified on the ingestion policy, `modules/iam/main.tf:150`).

### DynamoDB backups are prod-only

`enable_backup = var.environment == "preprod" ? false : true` (`main.tf:198`); the backup
vault, plan, and role all take `count` from it (`modules/dynamodb/main.tf`).

## Open hardening items

Recommended for production, verified as not yet implemented:

- No `dynamodb:LeadingKeys` condition on dashboard queries (`modules/iam/main.tf:392` has no
  `Condition` block).
- No VPC endpoint condition on Secrets Manager access; Lambdas reach it over the public path.
- No S3 model version pinning: analysis reads `${bucket}/*` in every environment
  (`modules/iam/main.tf:321`).
