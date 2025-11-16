# Sentiment Analyzer — SPEC

Purpose
-------
This file is the actionable specification for the Sentiment Analyzer service. It contains concrete API contracts, data shapes, deployment/CI instructions, Terraform module interfaces, test cases and acceptance criteria derived from the higher-level `constitution.md`.

Location and usage
------------------
- Canonical spec: `SPEC.md` (this file).
- Architecture diagrams: see `diagrams/` and `diagrams/README.md` for Canva links and exports.

High-level architecture (short)
-------------------------------
- Event-driven, serverless pipeline on AWS.
- EventBridge scheduled rules trigger ingestion Lambdas per source based on poll_interval_seconds.
- Ingestion adapters fetch from external publishing endpoints (RSS/Twitter-style APIs) and emit ingestion events.
- SNS topics publish ingestion events; SQS queues buffer and decouple work.
- AWS Lambda consumers perform inference and write a compact record to DynamoDB.
- Terraform + Terraform Cloud (TFC) manage infra; GitHub Actions run checks and publish artifacts.

Ingestion Flow Details:
- Single EventBridge scheduled rule (rate: 1 minute) triggers scheduler Lambda.
- Scheduler Lambda scans source-configs table for all enabled sources, filters by poll_interval_seconds (e.g., only sources with next_poll_time <= now).
- For each eligible source, scheduler Lambda invokes ingestion Lambda asynchronously with source_id as event payload.
- Ingestion Lambda reads source config from DynamoDB, fetches new items from endpoint, deduplicates, publishes to SNS.
- After successful poll, ingestion Lambda updates next_poll_time = now + poll_interval_seconds in source-configs.
- Scaling: This pattern supports unlimited sources (no EventBridge 300-rule limit), with all sources checked every minute.

Technology Stack
----------------
- AWS Region: us-west-2 (Oregon)
- Lambda Runtime: Python 3.11
- Lambda Networking: No VPC (public execution environment)
  - Rationale: All AWS services (DynamoDB, SNS, SQS, Secrets Manager, S3) accessible via public endpoints with IAM authentication
  - Security: TLS 1.2+ encryption in transit, IAM policies enforce least privilege, no network-level access required
  - Performance: Avoids VPC cold start overhead (10-50ms) and NAT Gateway latency
  - Cost: Saves $32/month NAT Gateway + data transfer fees
  - Future: Migrate to VPC only if private resources (RDS, ElastiCache) added
- Sentiment Analysis: VADER (vaderSentiment library) - lightweight rule-based analyzer optimized for social media, sub-100ms inference, <5MB package size
- Ingestion Libraries: feedparser (RSS/Atom), tweepy (Twitter API v2)
- Infrastructure: Terraform >= 1.5.0, AWS provider ~> 5.0
- Testing: pytest, moto (AWS mocking), LocalStack (integration tests)

External API Configuration:
- Twitter API: Free tier initially ($0/month) - 1,500 tweets/month, 50 requests/day, 10,000 characters/month
  - Limits: Suitable for testing/demo only, NOT production-grade
  - Upgrade path: Migrate to Basic tier ($100/month, 10K tweets/month) when approaching limits
  - Rate limit handling: Implement exponential backoff, monitor quota usage via CloudWatch metrics
  - Compliance: Must follow Twitter Developer Agreement (attribution, no redistribution)
  - OAuth 2.0 Token Management:
    - Store access_token and refresh_token in AWS Secrets Manager (per-source secret)
    - Access tokens expire after ~2 hours
    - Ingestion Lambda checks token expiry before each API call (compare expires_at timestamp)
    - If expired or expiring within 5 minutes, use refresh_token to obtain new access_token via OAuth refresh flow
    - Atomically update Secrets Manager with new access_token, refresh_token, and expires_at
    - On refresh failure (invalid refresh_token), disable source and alert operator for manual re-authentication
- RSS/Atom: No tier limits, respect feed-specific rate limits and robots.txt
  - ETag/Last-Modified caching: Store ETag and Last-Modified headers in source-configs, send If-None-Match/If-Modified-Since on subsequent requests
  - Handle 304 Not Modified responses (skip processing, update last_poll_time only)

Data Residency & Compliance
----------------------------
- Primary region: us-west-2 (all data at rest stored in Oregon)
- No cross-region replication initially (single-region deployment)
- Data retention: 90-day TTL on DynamoDB items, 7-year CloudWatch Logs retention for compliance
- Encryption: Server-side encryption (SSE) enabled on DynamoDB, S3 artifacts encrypted with AWS-managed keys (SSE-S3)
- No PII storage by default; text snippets require explicit approval and must be minimal
- GDPR Compliance:
  - Right to be forgotten: DELETE /v1/items endpoint provides immediate deletion capability
  - Data portability: Can be implemented via GET /v1/items/{source}/{id} or DynamoDB export (future enhancement)
  - Consent tracking: Not required (publicly available social media data, no user accounts)
  - Privacy policy: Must document data collection, retention (90 days), deletion procedures, backup retention (30 days)
  - DPA (Data Processing Agreement): Required if processing data on behalf of EU controllers

Disaster Recovery & Business Continuity
----------------------------------------
- RTO (Recovery Time Objective): 4 hours - Maximum acceptable downtime to restore service from backup
- RPO (Recovery Point Objective): 1 hour - Maximum acceptable data loss window
- Backup Strategy:
  - DynamoDB PITR (Point-in-Time Recovery): Enabled on both tables, restore to any second within last 35 days
  - AWS Backup: Daily automated backups with 30-day retention for long-term archival
  - Lambda code: Versioned in Git, artifacts stored in versioned S3 bucket
  - Infrastructure: Terraform state in Terraform Cloud with state history
- Recovery Procedures:
  - DynamoDB restore: Use PITR to restore tables to new table names, update Lambda environment variables, redeploy via Terraform (estimated 2-4 hours)
  - Lambda restore: Redeploy from Git tag or previous S3 artifact version via Terraform (estimated 30 minutes)
  - Full region outage: Manual failover not supported initially; document multi-region migration path for future (would achieve RTO: 1 hour, RPO: 5 minutes with active-active)
- Testing: Quarterly disaster recovery drill (restore to non-prod environment, validate data integrity)

Interfaces & Contracts
----------------------
1) Admin API: configure sources
- Implementation: AWS API Gateway (REST API) + Lambda (Python 3.11)
- Authentication: API Gateway API Keys with usage plans (1000 requests/day per key, 10 requests/second burst)
- Endpoint: POST /v1/sources
- Purpose: create source subscriptions or update polling config
- Headers required: `X-API-Key: <api-key-value>`
- Example request payload:
  {
    "id": "source-1",
    "type": "rss",            // or "twitter"
    "endpoint": "https://example.com/feed.xml",
    "auth": { "secret_ref": "arn:aws:secretsmanager:..." },
    "poll_interval_seconds": 60,
    "enabled": true
  }
- Validation rules: `id` unique and slug-safe; `type` in allowlist {"rss","twitter"}; `poll_interval_seconds` >= 15; `endpoint` must be a valid URL.
- Additional endpoints: GET /v1/sources (list all sources), GET /v1/sources/{id} (get source details), PATCH /v1/sources/{id} (update source), DELETE /v1/sources/{id} (remove source)

5) Data deletion API (GDPR compliance)
- Endpoint: DELETE /v1/items/{source_type}/{source_id}/{item_id}
- Purpose: Delete sentiment records to comply with GDPR "right to be forgotten" and similar regulations
- Headers required: `X-API-Key: <api-key-value>`
- Path parameters:
  - source_type: "rss" or "twitter"
  - source_id: source identifier (e.g., "source-1")
  - item_id: item identifier (content hash or publisher ID)
- Behavior:
  - Constructs DynamoDB composite key: source_key = "source_type#source_id", item_id
  - Deletes item from sentiment-items table via DeleteItem operation
  - Logs deletion event to CloudWatch with: requester (API key ID), timestamp, deleted record keys, deletion reason (if provided)
  - Returns 204 No Content on successful deletion
  - Returns 404 Not Found if record doesn't exist (idempotent - safe to retry)
  - Returns 400 Bad Request if invalid path parameters
- Audit trail: All deletions logged to dedicated CloudWatch log group `/aws/api/deletions` with 7-year retention for compliance
- SLA: Deletion completed within 30 days of request (actual: immediate, well within GDPR requirements)
- Backup handling: Deleted items remain in PITR and AWS Backup snapshots per retention policy (30 days), document this in privacy policy

2) Output record (persisted / forwarded shape)
- Documented JSON schema (minimal):
  {
    "id": "string",                       // internal id
    "source": { "type": "string", "source_id": "string", "url": "string?" },
    "received_at": "ISO8601",
    "sentiment": "positive|neutral|negative",
    "score": 0.0,
    "model_version": "string"
  }
- Notes: by default do NOT persist full text; `text_snippet` may be included if approved and documented.

3) Downstream push/forward
- Optional webhook: POST <configured webhook URL> with the same output record.
- Headers: `X-Request-Id`, `X-Idempotency-Key` (when forwarding batch items), HMAC signature header if configured.
- Retry semantics: exponential backoff; honor 429/503 with backoff; DLQ on repeated failures.

4) Optional label submission API (for external labeling workflows)
- Endpoint: POST /v1/labels
- Payload example:
  { "item_id": "...", "labeler_id": "annotator-1", "label": "negative", "confidence": 0.9, "notes":"contains sarcasm", "timestamp":"...", "source_model_version":"v1.2.0" }
- Labels are stored with provenance and not used for training until validated and a retraining pipeline is triggered.

Operational Behaviors (must implement)
--------------------------------------
- Deduplication: prefer stable `source_id` from publishers; fallback to content hash (SHA-256) where `source_id` not available. Use DynamoDB conditional write (ConditionExpression attribute_not_exists(pk)) to dedupe atomically.
- Idempotency: every ingestion event includes an idempotency key; consumers must be idempotent and avoid double-processing.
- Watch filters: admin can set up to 5 watch keywords/hashtags per scope. Matching is token/hashtag exact match (case-insensitive). UI must reflect changes within ≤5s.
- Backpressure: use SQS retention and DLQs; tune visibility timeout > expected processing time (60 seconds based on 30s Lambda timeout + buffer); reserved concurrency for Lambdas to protect downstream.
- Lambda Configuration:
  - Scheduler Lambda: 256 MB memory, 60s timeout, reserved concurrency: 1 (single invocation per minute, scans DynamoDB, invokes ingestion Lambdas)
  - Ingestion Lambda: 256 MB memory, 60s timeout, reserved concurrency: 10 (max 10 sources polled concurrently, fetches from external APIs, publishes to SNS)
  - Inference Lambda: 512 MB memory, 30s timeout, reserved concurrency: 20 (processes SQS messages, performs VADER sentiment analysis, writes to DynamoDB)
- Expected Throughput:
  - Average load: 100 items/minute (~1.7 items/second)
  - Peak load: 1,000 items/minute (~16.7 items/second) during viral events or breaking news
  - Supports: 10-50 active sources with moderate activity
  - DynamoDB throughput: ~100-1,000 write requests/minute (well within on-demand capacity)
  - Lambda concurrency: Peak requires ~5-10 concurrent inference executions (well below reserved limit of 20)
  - Estimated monthly cost: $50-200 (DynamoDB $20-80, Lambda $10-50, other services $20-70)
- Lambda Error Handling (Dead Letter Queues):
  - Each Lambda function configured with dedicated SQS DLQ
  - Async invocations (EventBridge → Scheduler, Scheduler → Ingestion): MaximumRetryAttempts=2, MaximumEventAge=3600s (1 hour)
  - SQS event source (SQS → Inference): ReportBatchItemFailures enabled, maxReceiveCount=3 before DLQ
  - DLQ Configuration:
    - scheduler-lambda-dlq: Stores failed scheduler invocations
    - ingestion-lambda-dlq: Stores failed ingestion invocations (Twitter/RSS fetch failures)
    - inference-lambda-dlq: Stores failed sentiment analysis invocations
  - Message retention: 14 days (maximum) in all DLQs
  - CloudWatch alarms: Alert when DLQ depth >10 messages (indicates persistent failures)
  - DLQ Reprocessing: Provide manual inspection and replay script in `tools/dlq-reprocessor.py`

Terraform module contracts (core)
--------------------------------
Provide reusable modules and document inputs/outputs. Minimal examples:

module "sns_topic" {
  source = "./modules/sns_topic"
  name   = "ingest-topic"
}

module "sqs_queue" {
  source = "./modules/sqs_queue"
  name   = "ingest-queue"
  fifo   = false
}

module "lambda_function" {
  source         = "./modules/lambda"
  name           = "inference-consumer"
  runtime        = "python3.11"
  handler        = "handler.lambda_handler"
  memory_size    = 512                    # MB - balanced for VADER + Python runtime
  timeout        = 30                     # seconds - ample for P90 ≤ 500ms target
  s3_key         = "artifacts/model-v1.2.0.zip"
  environment    = { MODEL_VERSION = "v1.2.0" }
  iam_role_arn   = var.lambda_role_arn
}

module "dynamodb_table" {
  source = "./modules/dynamodb_table"
  name   = "items"
  pk     = "source_key"     # Format: "source_type#source_id" (e.g., "rss#source-1")
  sk     = "item_id"        # Content hash (SHA-256) or publisher's stable ID
  gsi    = [
    {
      name = "model-version-index"
      pk   = "model_version"
      sk   = "received_at"
    }
  ]
  ttl_attribute = "ttl_timestamp"
}

DynamoDB Schema Details:

Table: sentiment-items
- Partition Key (PK): `source_key` (STRING) - composite format "source_type#source_id" distributes writes across sources
- Sort Key (SK): `item_id` (STRING) - content hash (SHA-256) or publisher's stable ID for deduplication
- Attributes: received_at (ISO8601), sentiment (STRING), score (NUMBER), model_version (STRING), text_snippet (STRING, optional), ttl_timestamp (NUMBER)
- GSI-1 (model-version-index): PK=model_version, SK=received_at - enables model performance queries and A/B testing
- TTL: ttl_timestamp field (90 days from received_at, configurable)
- Capacity Mode: On-demand (pay per request, no throttling, instant scaling)
- Billing: $1.25 per million write requests, $0.25 per million read requests
- Encryption: Server-side encryption (SSE) with AWS-managed keys
- Backup: Point-in-time recovery (PITR) enabled, daily AWS Backup with 30-day retention

Table: source-configs
- Partition Key (PK): `source_id` (STRING) - unique identifier for each source
- Attributes: type (STRING: "rss"|"twitter"), endpoint (STRING), auth_secret_ref (STRING: ARN), poll_interval_seconds (NUMBER), enabled (BOOLEAN), next_poll_time (NUMBER: Unix timestamp), last_poll_time (NUMBER: Unix timestamp), etag (STRING, optional for RSS), last_modified (STRING, optional for RSS), created_at (ISO8601), updated_at (ISO8601)
- Purpose: Stores source subscription configurations accessed by Admin API and polling scheduler
- Access pattern: GetItem by source_id (Admin API), Scan with filter enabled=true AND next_poll_time <= now (scheduler Lambda)
- Capacity Mode: On-demand (low-volume table, predictable costs)
- Encryption: Server-side encryption (SSE) with AWS-managed keys
- Backup: Point-in-time recovery (PITR) enabled

Note: Both tables use on-demand capacity for MVP to avoid throttling during unpredictable traffic patterns. After establishing baseline traffic (2-3 months), evaluate migration to provisioned capacity with autoscaling for cost optimization.

- Each module must document required inputs, optional inputs and outputs (e.g., topic_arn, queue_url, table_name).
- Conditional writes example for dedup (DynamoDB): PutItem with ConditionExpression: "attribute_not_exists(source_key) AND attribute_not_exists(item_id)".

CI / CD
-------
- GitHub Actions responsibilities (PR):
  - Run `terraform fmt`, `terraform validate`, `tflint`.
  - Run security checks: `tfsec` (Terraform), `semgrep` or other SAST for code, dependency checks.
  - Run unit tests and build model artifact; upload artifact to S3 artifact bucket (versioned path) and publish artifact path as output for the TFC plan.
- Terraform Cloud integration:
  - Use VCS-connected TFC workspaces (one per environment). Merge to protected branches triggers TFC run.
  - TFC stores remote state and run logs. Require manual approvals or policy gates for production applies.
  - Store sensitive workspace variables in TFC as sensitive variables.

Acceptance tests & fixtures
--------------------------
- Provide a deterministic test fixture (JSONL) with a small set of feed items and expected output records.
- Integration test: push fixture into ingestion adapter mock (or simulate SNS event) → assert DynamoDB entry created with expected sentiment and model_version.
- Performance check: small synthetic load (e.g., 100 concurrent small events) to assert P90 <= 500ms for a single inference under nominal test environment.

Metrics & dashboard mapping
---------------------------
- Dashboard Implementation: AWS CloudWatch Dashboard
- Access Control: IAM-based authentication (read-only role for operators/auditors, admin role for full access)
- Update Frequency: Near real-time (CloudWatch standard 1-minute metric resolution, 5-second resolution for custom metrics via high-resolution)
- Metric names (minimal):
  - `sentiment.request_count{source,model_version}`
  - `sentiment.error_count{source}`
  - `sentiment.latency_ms` (histogram for p50/p90/p99)
  - `sentiment.model_version_inferences{model_version}`
  - `sentiment.watch_match_count{filter}`
  - `sentiment.dedup_rate`
- Dashboard widgets must reference these exact metric names.
- Admin Controls: Feed switching and watch filter management implemented via Admin API endpoints (GET/POST /v1/dashboard/config), UI can be added later as separate lightweight web interface

Security & privacy checklist
---------------------------
- TLS enforced for all external endpoints (TLS 1.2+ minimum).
- Secrets stored in AWS Secrets Manager or TFC sensitive variables; not in repo.
- Default behavior: do not persist full raw text. When required, approvals and encryption-at-rest must be in place.
- DynamoDB conditional writes and ExpressionAttributeNames/Values used for all expressions that incorporate user-provided values.

Input Validation & Sanitization:
- API Gateway request validation: Enable request validators for all POST/PATCH endpoints with JSON schema models
- Lambda validation: Use pydantic models for request/response validation with strict type enforcement
- Validation Rules:
  - source_id: Regex `^[a-z0-9-]{1,64}$` (lowercase alphanumeric and hyphens only, max 64 chars)
  - type: Enum allowlist {"rss", "twitter"} (reject any other values)
  - endpoint: Valid HTTPS URL (regex check), max 2048 characters, reject non-HTTPS
  - poll_interval_seconds: Integer range 60-86400 (1 minute to 24 hours)
  - enabled: Boolean only (true/false)
  - Control character rejection: Reject any input containing ASCII control characters (0x00-0x1F except whitespace)
  - SQL keyword blocking: Reject inputs containing SQL keywords (SELECT, DROP, INSERT, etc.) to prevent injection attempts
  - Path traversal prevention: Reject inputs containing ../, ..\, or encoded variants
- Error responses: Return 400 Bad Request with specific validation error messages (e.g., "source_id must be lowercase alphanumeric")
- Logging: Log validation failures to CloudWatch for security monitoring (track repeated failed attempts from same IP/API key)

Runbooks (short)
-----------------
- How to rollback model: change Lambda environment MODEL_VERSION to previous value and redeploy via Terraform; use Lambda alias/traffic shifting / CodeDeploy for canary.
- How to reprocess DLQ: inspect message, fix data if required, and requeue to the original queue; provide a reprocess script in `tools/`.

Files to add (recommended)
--------------------------
- `SPEC.md` (this file)
- `diagrams/` with exported SVG/PNG architecture diagram (see existing docs)
- `terraform/` modules and `terraform/live/<env>/` root modules
- `tests/fixtures/` with synthetic feed JSONL
- `ci/` or `.github/workflows/` GitHub Actions workflows for checks

Acceptance criteria (short)
---------------------------
- PR checks run and pass (format/validate/SAST/unit-tests).
- TFC workspaces configured and run on protected-branch merges.
- Integration test shows ingestion → inference → DynamoDB record for fixture.
- Dashboard shows the mapped metrics and watch filter metrics.

Contact / ownership
-------------------
- Core service owner: `scotthazlett@gmail.com`
- Infra owner (Terraform/TFC): `scotthazlett@gmail.com`

## Clarifications

### Session 2025-11-15

- Q: Which sentiment analysis approach should the Lambda inference function use? → A: VADER (Valence Aware Dictionary and sEntiment Reasoner) - Lightweight rule-based analyzer, <5MB, no cold starts, sub-100ms inference, good for social media text
- Q: What should be the DynamoDB table partition key (PK) and sort key (SK) design for the items table? → A: PK: `source_type#source_id` (e.g., "rss#source-1"), SK: `item_id` (content hash or publisher ID) - Distributes writes across sources, supports per-source queries
- Q: How should the Admin API (POST /v1/sources, etc.) authenticate requests? → A: API Gateway API Keys with usage plans - Simplest implementation, built-in rate limiting, easy rotation via Terraform, suitable for service-to-service or small admin team
- Q: Which AWS region should host the infrastructure? → A: us-west-2 (Oregon) - Good alternative to us-east-1, slightly higher availability due to fewer outages historically, minimal cost difference
- Q: What technology should implement the externally-facing dashboard with metrics and admin controls? → A: CloudWatch Dashboard (native AWS) - Zero infrastructure overhead, direct metric integration, built-in auth via IAM/SSO, limited customization for admin controls
- Q: Where should source configuration data (from POST /v1/sources) be persisted? → A: DynamoDB table (source-configs) with source_id as PK - Native serverless integration, fast Lambda access, supports atomic updates, consistent with existing data layer
- Q: What should trigger the periodic polling of RSS/Twitter feeds for each configured source? → A: Single EventBridge rule (1-minute) → Scheduler Lambda scans source-configs → Invokes ingestion Lambda per eligible source - Avoids 300-rule limit, scales indefinitely
- Q: How to handle more than 300 sources (EventBridge rule limit)? → A: Single EventBridge rule (1-minute interval) → Scheduler Lambda scans source-configs table → Invokes ingestion Lambda per enabled source - Scales indefinitely, simpler operations, all sources checked every minute
- Q: What memory allocation should the sentiment inference Lambda function use? → A: 512 MB - Good balance for Python + VADER + logging, comfortable headroom, minimal cost increase, faster cold starts due to more allocated CPU
- Q: Which DynamoDB capacity mode should the tables use? → A: On-demand capacity - Pay per request ($1.25/M writes, $0.25/M reads), no throttling, instant scaling, unpredictable costs - Best for MVP with unknown traffic patterns
- Q: Which Twitter API v2 tier should the service use? → A: Free tier - $0/month, 1,500 tweets/month, 50 requests/day, 10,000 characters/month - Only suitable for demo/testing, not production
- Q: How should the service handle Twitter OAuth token expiration and refresh? → A: Automatic refresh in ingestion Lambda - Lambda checks token expiry, uses refresh_token from Secrets Manager to get new access_token, updates Secrets Manager atomically - Zero downtime, fully automated
- Q: How should Lambda function failures be handled? → A: Dedicated SQS DLQ per Lambda function - Each Lambda has its own DLQ, maxReceiveCount=3 retries, CloudWatch alarm when DLQ depth >10, DLQ processor Lambda for replay - Complete failure visibility and recovery
- Q: What are the acceptable recovery targets for disaster recovery? → A: RTO: 4 hours, RPO: 1 hour - Balanced targets, achievable with DynamoDB PITR, daily AWS Backup snapshots, acceptable for non-mission-critical service - Future upgrade path to multi-region for RTO: 1 hour, RPO: 5 minutes
- Q: What is the expected throughput for ingested items? → A: 100 items/min average, 1,000 items/min peak - Moderate load for MVP with 10-50 sources, validates serverless scaling, reasonable costs $50-200/month
- Q: Should Lambda functions run in a VPC? → A: No VPC (public Lambda execution) - Lambdas access AWS services via public endpoints with IAM auth, lowest latency, no NAT costs, simpler networking - Recommended for serverless-only stack
- Q: What input validation rules should the Admin API enforce? → A: Comprehensive validation with pydantic models - source_id: regex `^[a-z0-9-]{1,64}$`, endpoint: HTTPS URL max 2048 chars, poll_interval: integer 60-86400, reject control characters - Use API Gateway request validation + Lambda pydantic models
- Q: How should the service handle data deletion requests (GDPR "right to be forgotten")? → A: DELETE endpoint + cascading deletion - DELETE /v1/items/{source}/{item_id} removes record from sentiment-items table, audit logs deletion with timestamp and requester, returns 204 No Content - Full GDPR compliance
