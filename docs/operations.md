# Operations

> **CANON**: verified against code.

Two procedures: diagnosing ingestion failures and rolling back a deployment. CI deploys
preprod only; every production job in `.github/workflows/deploy.yml` carries `if: false`.
Commands below use `preprod-` names. Environment names come from
`infrastructure/terraform/main.tf:242-245` (`<env>-sentiment-<lambda>`).

## Ingestion failures

The ingestion Lambda is `preprod-sentiment-ingestion`. EventBridge rule
`preprod-sentiment-ingestion-schedule` fires it every 5 minutes, around the clock; there is
no market-hours gate anywhere in the schedule or the handler
(`infrastructure/terraform/modules/eventbridge/main.tf:3-6`). It fetches Tiingo and Finnhub
in parallel (`src/lambdas/ingestion/parallel_fetcher.py`): `PARALLEL_INGESTION_ENABLED`
defaults to true and Terraform does not override it (`src/lambdas/ingestion/handler.py:152-153`).
Sequential Tiingo-then-Finnhub failover is only the fallback when that flag is off.

### What actually alerts

The live signal is the CloudWatch alarm `preprod-sentiment-ingestion-errors`: more than 5
Lambda errors per 5-minute period, two consecutive periods, notifying SNS topic
`preprod-sentiment-alarms` (`infrastructure/terraform/modules/lambda/main.tf:177-199`,
`modules/monitoring/main.tf:5-6`, threshold set at `main.tf:352`).

The application-level consecutive-failure alert (3 failures in 15 minutes,
`src/lambdas/ingestion/alerting.py`) publishes to `ALERT_TOPIC_ARN`. Terraform does not set
that variable on the Lambda (`main.tf:330-342`), and the handler skips alerting when it is
empty (`src/lambdas/ingestion/handler.py:630`). Watch the CloudWatch alarm, not application
SNS alerts.

### Diagnosis order

Work from the Lambda outward: its own logs, then its upstreams, then its downstreams.

1. Logs first.

   ```bash
   aws logs tail /aws/lambda/preprod-sentiment-ingestion --since 30m --filter-pattern "ERROR"
   ```

2. Source APIs second. Check the Tiingo and Finnhub status pages. Parallel fetch tolerates
   one source failing: the failing source logs an error and emits `SilentFailure/Count`
   (dimension `FailurePath: parallel_fetcher_aggregate`) in `SentimentAnalyzer/Reliability`
   (`src/lambdas/ingestion/parallel_fetcher.py:163-169`) while collection continues on the
   other source.

3. Circuit breaker third. State lives in the items table under `CIRCUIT#<service>`
   (`src/lambdas/ingestion/handler.py:801-806`); it opens after 5 failures and resets after
   300 seconds (`handler.py:139-140`).

   ```bash
   aws dynamodb get-item \
     --table-name preprod-sentiment-items \
     --key '{"PK": {"S": "CIRCUIT#tiingo"}, "SK": {"S": "STATE"}}'
   ```

4. Credentials fourth. Secrets are `preprod/sentiment-analyzer/tiingo` and
   `preprod/sentiment-analyzer/finnhub` (`infrastructure/terraform/modules/secrets/main.tf:41,72`).

   ```bash
   aws secretsmanager get-secret-value \
     --secret-id preprod/sentiment-analyzer/tiingo \
     --query SecretString --output text | head -c 10
   ```

5. Storage last. Despite its name, the alarm `preprod-sentiment-dynamodb-write-throttles`
   (`infrastructure/terraform/modules/dynamodb/main.tf:222`) measures consumed write
   capacity (`ConsumedWriteCapacityUnits` over 1000 per minute), not throttle events. A
   quiet alarm means writes are not spiking; for actual throttles query the
   `WriteThrottleEvents` metric in `AWS/DynamoDB` directly.

### Metrics

Namespace `SentimentAnalyzer/Ingestion` (`src/lambdas/ingestion/metrics.py:26-42`). Watch:

- `CollectionSuccess` / `CollectionFailure` ratio
- `CollectionLatencyMs` (alert threshold 30000 ms, `metrics.py:45`)
- `ItemsCollected` and `ItemsDuplicate` per run
- `NotificationLatencyMs` (30 second SLA to downstream SNS)

`FailoverCount` is declared (`metrics.py:29`) but nothing on the live path emits it;
`record_failover` has no callers outside its own docstring. Do not wait on it.

```bash
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer/Ingestion \
  --metric-name CollectionLatencyMs \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 --statistics Average Maximum
```

Retry and storage reliability events land in `SentimentAnalyzer/Reliability`
(`src/lambdas/ingestion/storage.py:153`).

### Common causes

| Root cause | Resolution |
|------------|------------|
| Source API down | Failover to Finnhub is automatic; confirm via `FailoverCount`, then wait out the primary |
| Rate limited | Daily budgets are 500 Tiingo and 1000 Finnhub calls (`handler.py:147-148`); reduce ticker count or wait for the window to reset |
| Credential invalid | Put a new value in the secret; automatic rotation only exists when a rotation Lambda ARN is configured (`modules/secrets/main.tf:59-68`) |
| Bad deploy | Roll back, next section |

## Rolling back a deployment

Deploys run from `.github/workflows/deploy.yml` on every push to `main`. The concurrency
group `deploy-pipeline` serializes runs. Three Lambdas deploy as container images
(dashboard, SSE, analysis); four deploy as ZIPs from S3 (ingestion, metrics, notification,
canary).

To find the last good commit, read the deployment record CI maintains:

```bash
aws s3 cp s3://preprod-sentiment-lambda-deployments/deployment-metadata.json -
```

It holds the deployed short SHA and timestamp per environment.

### First choice: revert and redeploy

`git revert` the offending commit and push to `main`. The pipeline rebuilds and redeploys
everything, including Terraform, and its smoke tests gate the result. Use the manual paths
below when the pipeline itself is broken or too slow for the outage.

### Dashboard and SSE (container, live alias)

`preprod-sentiment-dashboard` and `preprod-sentiment-sse-streaming` serve through the
`live` alias. Each deploy publishes an immutable version and flips the alias, so rollback
is flipping it back. No image pull, effective immediately.

```bash
aws lambda list-versions-by-function \
  --function-name preprod-sentiment-dashboard \
  --query 'Versions[*].[Version,Description]' --output table

aws lambda update-alias \
  --function-name preprod-sentiment-dashboard \
  --name live \
  --function-version <previous-version>
```

The version description carries the git SHA it was built from (deploy.yml, "Deploy
Dashboard Lambda (alias-based)" step). Same procedure for the SSE function.

### Analysis (container, no alias)

`preprod-sentiment-analysis` is updated in place on `$LATEST`. Roll back by repointing it
at an older image. ECR keeps one immutable tag per commit SHA in `preprod-analysis-lambda`
(repos for the other two: `preprod-dashboard-lambda`, `preprod-sse-streaming-lambda`).

```bash
aws ecr describe-images --repository-name preprod-analysis-lambda \
  --query 'imageDetails[*].[imageTags,imagePushedAt]' --output table

aws lambda update-function-code \
  --function-name preprod-sentiment-analysis \
  --image-uri <account>.dkr.ecr.<region>.amazonaws.com/preprod-analysis-lambda:<good-git-sha>

aws lambda wait function-updated --function-name preprod-sentiment-analysis
```

### ZIP Lambdas (ingestion, metrics, notification, canary)

Each deploy overwrites one fixed key per function:
`s3://preprod-sentiment-lambda-deployments/<name>/lambda.zip` (deploy.yml, "Upload Lambda
Packages to S3"). The bucket is bootstrapped outside Terraform with versioning enabled
(`infrastructure/terraform/main.tf:211-213`), so earlier packages exist as object versions.

```bash
aws s3api list-object-versions \
  --bucket preprod-sentiment-lambda-deployments \
  --prefix ingestion/lambda.zip \
  --query 'Versions[*].[VersionId,LastModified]' --output table

aws lambda update-function-code \
  --function-name preprod-sentiment-ingestion \
  --s3-bucket preprod-sentiment-lambda-deployments \
  --s3-key ingestion/lambda.zip \
  --s3-object-version <version-id>
```

Confirm versioning before relying on this (`aws s3api get-bucket-versioning --bucket
preprod-sentiment-lambda-deployments`); if it is off, revert and redeploy.

### Terraform is not a rollback tool here

The pipeline's only per-deploy variables are `model_version` and
`lambda_package_version`; there is no image-tag variable, and the container image pointers
are moved by the AWS CLI after apply precisely because Terraform cannot detect `:latest`
content changes (deploy.yml, "Force Analysis Lambda Image Update"). Running Terraform
locally during a CI deploy is an unprotected concurrent state write; see
`docs/runbooks/terraform-state.md`.

### Verify recovery

1. The API health endpoint returns 200 unauthenticated: `curl <api-url>/health`.
2. Logs on the rolled-back function show clean invocations:
   `aws logs tail /aws/lambda/<function> --since 10m`.
3. For ingestion, a successful cycle appears within 5 minutes (the schedule interval):
   `CollectionSuccess` ticks in `SentimentAnalyzer/Ingestion`.
4. Alarms return to OK:
   `aws cloudwatch describe-alarms --alarm-names preprod-sentiment-ingestion-errors`.
