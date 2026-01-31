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
- Ingestion adapters fetch from external publishing endpoints (RSS feeds, Tiingo/Finnhub APIs) and emit ingestion events.
- SNS topics publish ingestion events; SQS queues buffer and decouple work.
- AWS Lambda consumers perform inference and write a compact record to DynamoDB.
- Terraform + Terraform Cloud (TFC) manage infra; GitHub Actions run checks and publish artifacts.

Ingestion Flow Details:
- EventBridge scheduled rule (rate: 5 minutes) triggers Ingestion Lambda directly.
- Ingestion Lambda fetches active configurations from DynamoDB via GSI query, aggregates unique tickers.
- Ingestion Lambda fetches news from Tiingo and Finnhub APIs in parallel (circuit breaker + quota tracking).
- Items are deduplicated using SHA256 hash of normalized headline + source, stored in DynamoDB.
- Batch publishes to SNS (max 10 per batch) for Analysis Lambda processing.
- Self-healing mechanism auto-republishes items stuck in pending status > 1 hour.

Technology Stack
----------------
- AWS Region: us-west-2 (Oregon)
- Lambda Runtime: Python 3.13
- Lambda Networking: No VPC (public execution environment)
  - Rationale: All AWS services (DynamoDB, SNS, SQS, Secrets Manager, S3) accessible via public endpoints with IAM authentication
  - Security: TLS 1.2+ encryption in transit, IAM policies enforce least privilege, no network-level access required
  - Performance: Avoids VPC cold start overhead (10-50ms) and NAT Gateway latency
  - Cost: Saves $32/month NAT Gateway + data transfer fees
  - Future: Migrate to VPC only if private resources (RDS, ElastiCache) added
- Sentiment Analysis: DistilBERT (HuggingFace transformers) - fine-tuned transformer model (distilbert-base-uncased-finetuned-sst-2-english), 100-150ms inference, ~250MB model size, superior accuracy for nuanced sentiment
- Ingestion Libraries: feedparser (RSS/Atom), requests (Tiingo/Finnhub APIs)
- Infrastructure: Terraform >= 1.5.0, AWS provider ~> 5.0
- Testing: pytest, moto (AWS mocking), LocalStack (integration tests)

External API Configuration:
- Tiingo News API: REST API for financial news
  - Authentication: API key via header (Authorization: Token <key>)
  - Rate limits: 50,000 requests/month (free tier), higher for paid tiers
  - Endpoints: /tiingo/news (headlines with sentiment scores)
- Finnhub News API: REST API for market news
  - Authentication: API key via query parameter (token=<key>)
  - Rate limits: 60 API calls/minute (free tier)
  - Endpoints: /company-news, /general-news
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
- Implementation: AWS API Gateway (REST API) + Lambda (Python 3.13)
- Authentication: API Gateway API Keys with usage plans (1000 requests/day per key, 10 requests/second burst)
- Endpoint: POST /v1/sources
- Purpose: create source subscriptions or update polling config
- Headers required: `X-API-Key: <api-key-value>`
- Example request payload:
  {
    "id": "source-1",
    "type": "rss",            // "rss" or "api" (for Tiingo/Finnhub)
    "endpoint": "https://example.com/feed.xml",
    "auth": { "secret_ref": "arn:aws:secretsmanager:..." },
    "poll_interval_seconds": 60,
    "enabled": true
  }
- Validation rules: `id` unique and slug-safe; `type` in allowlist {"rss","api"}; `poll_interval_seconds` >= 60; `endpoint` must be a valid URL.
- Additional endpoints: GET /v1/sources (list all sources), GET /v1/sources/{id} (get source details), PATCH /v1/sources/{id} (update source), DELETE /v1/sources/{id} (remove source)
- Error Response Schema (standardized across ALL Admin API endpoints):
  - HTTP Status Codes:
    - 200 OK: Success (GET, PATCH)
    - 201 Created: Resource created (POST)
    - 204 No Content: Deletion successful (DELETE)
    - 400 Bad Request: Validation error
    - 401 Unauthorized: Invalid/missing API key
    - 404 Not Found: Resource doesn't exist
    - 409 Conflict: Duplicate resource (source ID already exists)
    - 429 Too Many Requests: Rate limit exceeded (includes Retry-After header in seconds)
    - 500 Internal Server Error: Unexpected error
    - 503 Service Unavailable: Temporary outage
  - Error Response Body (JSON):
    ```json
    {
      "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error description",
        "field": "field_name",
        "request_id": "uuid-v4",
        "timestamp": "2025-11-16T12:00:00Z",
        "docs_url": "https://docs.example.com/errors/ERROR_CODE"
      }
    }
    ```
  - Error Code Enumeration:
    - VALIDATION_ERROR: Input validation failed (field specified, e.g., "source_id must be lowercase alphanumeric")
    - DUPLICATE_RESOURCE: Resource with same ID already exists (409 Conflict)
    - RESOURCE_NOT_FOUND: Requested resource doesn't exist (404 Not Found)
    - RATE_LIMIT_EXCEEDED: Too many requests (429, check Retry-After header)
    - QUOTA_EXHAUSTED: Monthly API quota exceeded (Tiingo/Finnhub)
    - UNAUTHORIZED: Invalid or missing API key (401)
    - FORBIDDEN: Valid credentials but insufficient permissions (403)
    - INVALID_ENDPOINT: Endpoint contains private IP (169.254.0.0/16, 10.0.0.0/8, 127.0.0.0/8) or invalid URL
    - INTERNAL_ERROR: Unexpected server error (check request_id in CloudWatch Logs)
    - SERVICE_UNAVAILABLE: Temporary outage (503, retry with exponential backoff)
  - Example Error Responses:
    - Validation Error (400): `{"error": {"code": "VALIDATION_ERROR", "message": "source_id must be lowercase alphanumeric with hyphens only", "field": "source_id", "request_id": "...", "timestamp": "...", "docs_url": "..."}}`
    - Rate Limit (429): HTTP header `Retry-After: 3600`, body: `{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "API key exceeded 10 source creations per hour limit", "request_id": "...", ...}}`
    - SSRF Prevention (400): `{"error": {"code": "INVALID_ENDPOINT", "message": "Endpoint cannot be a private IP address (169.254.0.0/16 blocked)", "field": "endpoint", ...}}`
  - Lambda Implementation: Use Pydantic models for validation, catch exceptions, return standardized error structure with request_id from Lambda context

5) Data deletion API (GDPR compliance)
- Endpoint: DELETE /v1/items/{source_type}/{source_id}/{item_id}
- Purpose: Delete sentiment records to comply with GDPR "right to be forgotten" and similar regulations
- Headers required: `X-API-Key: <api-key-value>`
- Path parameters:
  - source_type: "rss" or "api"
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
  - Ingestion Lambda: 512 MB memory, 60s timeout, EventBridge trigger (every 5 minutes), parallel fetching from Tiingo/Finnhub, reserved concurrency: 10
  - Analysis Lambda: 2048 MB memory, 60s timeout, reserved concurrency: 20 (processes SNS messages via container deployment, performs DistilBERT sentiment analysis, writes to DynamoDB)
  - Dashboard Lambda: 1024 MB memory, 60s timeout, container deployment (FastAPI + Mangum), Lambda Function URL with IAM auth
  - Metrics Lambda: 128 MB memory, 30s timeout, EventBridge trigger (every 1 minute), monitors stuck items in pending status, emits CloudWatch metrics
  - Notification Lambda: 256 MB memory, 30s timeout, SNS + EventBridge triggers, sends email alerts, magic links, and digests via SendGrid
  - SSE Streaming Lambda: 512 MB memory, 900s timeout (15 min), container deployment (FastAPI + sse-starlette), Lambda Function URL with RESPONSE_STREAM invoke mode for real-time sentiment updates
- Expected Throughput:
  - Average load: 100 items/minute (~1.7 items/second)
  - Peak load: 1,000 items/minute (~16.7 items/second) during viral events or breaking news
  - Supports: 10-50 active sources with moderate activity
  - DynamoDB throughput: ~100-1,000 write requests/minute (well within on-demand capacity)
  - Lambda concurrency: Peak requires ~5-10 concurrent inference executions (well below reserved limit of 20)
- Cost Estimates (based on 100 items/min average load per source):

  **Phase 1: 10-50 Sources (MVP)**
  - ~$15-30/month total
    - Tiingo/Finnhub API: Free tiers available (Tiingo: 50K/month, Finnhub: 60 calls/min)
    - Lambda: $5-10/month (10 reserved concurrency, ~200K invocations/month)
    - DynamoDB: $5-10/month (on-demand, ~400K writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $5-10/month

  **Phase 2: 50-100 Sources (Growth)**
  - ~$30-80/month total
    - Lambda: $15-30/month (20 reserved concurrency, ~500K invocations/month)
    - DynamoDB: $10-20/month (on-demand, ~1M writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $15-30/month
  - Architectural change: Migrate to Query pattern (GSI) around 50 sources (+$2/month GSI cost)

  **Phase 3: 100-500 Sources (Scale-up)**
  - ~$100-500/month total
    - Lambda: $30-60/month (increased concurrency)
    - DynamoDB: $30-60/month (on-demand, ~2.5M writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $40-80/month
  - Architectural change: Sharded ingestion or Step Functions required around 100-150 sources

  **Cost Scaling Summary by Source Count:**
  | Sources | Monthly Cost | Primary Expense | Architecture |
  |---------|-------------|-----------------|--------------|
  | 10 | $15-30 | Lambda + DynamoDB | Scan pattern |
  | 50 | $30-80 | Lambda + DynamoDB | Query pattern (GSI) |
  | 100 | $100-300 | Lambda + DynamoDB | Query + shards |
  | 500 | $300-800 | Lambda + DynamoDB | Shards or Step Functions |
- Lambda Error Handling (Dead Letter Queues):
  - Each Lambda function configured with dedicated SQS DLQ
  - Async invocations (EventBridge → Scheduler, Scheduler → Ingestion): MaximumRetryAttempts=2, MaximumEventAge=3600s (1 hour)
  - SQS event source (SQS → Inference): ReportBatchItemFailures enabled, maxReceiveCount=3 before DLQ
  - DLQ Configuration (with archival for data loss prevention):
    - ingestion-lambda-dlq: Stores failed ingestion invocations (API/RSS fetch failures)
    - analysis-lambda-dlq: Stores failed sentiment analysis invocations (naming: {env}-sentiment-analysis-dlq in Terraform)
  - Message retention: 14 days (maximum) in all DLQs
  - **DLQ Archival Protection** (prevents 14-day data loss):
    - CloudWatch alarm: "DLQ oldest message age >7 days" → CRITICAL (50% of retention consumed)
    - Automatic S3 archival: Lambda triggered daily to archive DLQ messages older than 10 days
    - Archive location: s3://sentiment-analyzer-dlq-archive/{dlq-name}/{year}/{month}/{day}/{message-id}.json
    - Archive retention: 90 days (matches DynamoDB TTL for consistency)
    - Recovery procedure: Replay from S3 archive using tools/s3-dlq-replayer.py
    - Cost: ~$1-5/month for S3 storage (Glacier Instant Retrieval for archived messages)
  - CloudWatch alarms:
    - Alert when DLQ depth >10 messages (indicates persistent failures)
    - Alert when DLQ oldest message age >7 days (prevents 14-day expiry data loss)
    - Alert when DLQ archival Lambda fails (ensures archival protection active)
  - DLQ Reprocessing:
    - Provide manual inspection and replay script in `tools/dlq-reprocessor.py`
    - Message signature validation: Verify HMAC before replay to prevent injection attacks
    - Replay rate limiting: Max 10 messages/minute to prevent overwhelming downstream systems

Scaling Thresholds & Migration Triggers
----------------------------------------

This service has architectural scaling limits that require proactive monitoring and migration planning. The specification is designed for 10-50 sources (MVP phase) but includes clear migration paths to scale.

### Scaling Phases & Bottlenecks

**Phase 1: 0-50 Sources (Current Architecture - SAFE)**
- Expected cost: $15-30/month
- No architectural changes required
- All components operate well within limits
- Primary risk: API rate limits (Tiingo 50K/month, Finnhub 60 calls/min free tiers)

**Phase 2: 50-100 Sources (Performance Degradation Begins)**
- Expected cost: $30-80/month
- Bottleneck #1: Ingestion Lambda configuration fetch performance (15-20s query time)
  - Symptom: CloudWatch metric `ingestion.config_fetch_duration_ms` exceeds 15,000ms
  - Impact: Reduced polling accuracy, ingestion misses scheduled windows
  - Migration trigger: When config fetch duration >15s for 2 consecutive days
  - Fix: Use GSI query with caching (already implemented via DFA-003 5-minute cache)
  - Effort: 2-3 days engineering (update Lambda code, deploy)
  - Cost impact: Minimal (GSI adds ~$1-2/month)
- Bottleneck #2: Ingestion Lambda reserved concurrency (10 concurrent, 85 invocations/min capacity)
  - Symptom: TooManyRequestsException in CloudWatch Logs, messages sent to ingestion-lambda-dlq
  - Migration trigger: When ingestion Lambda throttled invocations >5% for 1 hour
  - Fix: Increase reserved concurrency to 20
  - Effort: 10 minutes (update Terraform, apply)

**Phase 3: 100-500 Sources (Architectural Change Required)**
- Expected cost: $100-500/month
- Bottleneck #3: Ingestion Lambda timeout (60s hard AWS limit)
  - Symptom: Ingestion Lambda timeout errors in CloudWatch Logs, incomplete source polling
  - Impact: CATASTROPHIC - some sources never polled, silent data gaps
  - Migration trigger: When ingestion execution time >45s for 3 consecutive cycles
  - Fix: Increase parallelism (ThreadPoolExecutor workers) or split into sharded ingestion Lambdas
  - Effort: 1-2 weeks engineering (Option A), 2-4 weeks (Option B/C)
  - Cost impact: Minimal for Option A/B, +$10-20/month for Option C (Step Functions)
- Bottleneck #4: API Gateway API Key daily quota (1,000 req/day)
  - Symptom: HTTP 429 errors for Admin API operations
  - Migration trigger: When approaching 800 requests/day from single API key
  - Fix: Issue multiple API keys (1 per admin user/system) or increase usage plan quota
  - Effort: 30 minutes (Terraform change)

**Phase 4: 500+ Sources (Enterprise Scale)**
- Expected cost: $500-2,000/month
- Bottleneck #5: DynamoDB on-demand cost inefficiency
  - Symptom: DynamoDB costs exceed $500/month
  - Migration trigger: After establishing 2-3 months of baseline traffic patterns
  - Fix: Migrate to provisioned capacity with auto-scaling (85% cost savings at scale)
  - Effort: 1 week (capacity planning, Terraform changes, gradual migration)
- Bottleneck #6: Lambda account-level concurrency (1,000 concurrent executions)
  - Symptom: Account-wide throttling across all Lambdas
  - Migration trigger: When total reserved concurrency allocations exceed 800
  - Fix: Request AWS support to increase account limit to 10,000
  - Effort: 1-2 weeks (support ticket, justification, approval)

### Ingestion Scaling (Current Architecture)

The current implementation uses a simpler architecture than originally planned:

**Actual Implementation:**
- EventBridge rule (every 5 minutes) triggers Ingestion Lambda directly
- Ingestion Lambda fetches active configurations via GSI query (DFA-003 caching)
- Parallel fetching from Tiingo/Finnhub using ThreadPoolExecutor (max 4 workers)
- Circuit breaker and quota tracking per source

**Scaling Options (if needed):**
- Increase ThreadPoolExecutor workers for more parallelism
- Increase Lambda memory (currently 512MB) for more CPU
- Split into sharded ingestion Lambdas if execution time exceeds 45s
- Consider Step Functions for unlimited source scalability

### CloudWatch Alarms for Proactive Scaling

Implement these alarms to trigger migrations BEFORE failures occur:

**Ingestion Performance (Critical)**
- Metric: `ingestion.execution_duration_ms` (custom metric from Ingestion Lambda)
- Alarm 1: WARN when execution_duration >30,000ms for 2 consecutive cycles
  - Action: Investigate parallel fetch bottlenecks, consider increasing workers
- Alarm 2: CRITICAL when execution_duration >45,000ms for 2 consecutive cycles
  - Action: Approaching timeout, increase parallelism or consider sharding
- Alarm 3: EMERGENCY when execution_duration >55,000ms for 1 cycle
  - Action: Risk of timeout, urgent action required

**Ingestion Lambda Throttling (Moderate)**
- Metric: `AWS/Lambda/Throttles` (built-in CloudWatch metric)
- Alarm: WARN when throttled invocations >5% for 1 hour
  - Action: Increase reserved concurrency

**DLQ Depth (Operational - Indicates failures)**
- Metric: `AWS/SQS/ApproximateNumberOfMessagesVisible` for each DLQ
- Alarm: CRITICAL when DLQ depth >10 messages (per spec line 295)
  - Action: Investigate root cause (API failures, throttling, bugs)

**Cost Overrun (Budget Protection)**
- Metric: AWS Cost Explorer / Budgets
- Alarm 1: WARN when monthly forecast exceeds budget by 20%
- Alarm 2: CRITICAL when actual spending exceeds budget
  - Action: Review DynamoDB on-demand costs, consider provisioned capacity migration

### Migration Decision Matrix

| Current State | Symptom | Bottleneck | Recommended Fix | Effort | Cost Impact |
|---------------|---------|------------|-----------------|--------|-------------|
| 50 sources | Scan time >10s | Ingestion fetch | Deploy Query pattern (GSI) | 2-3 days | +$2/mo |
| 100 sources | Execution time >45s | Ingestion timeout | Deploy shards (Option B) | 1-2 weeks | +$0/mo |
| 500 sources | DynamoDB cost >$500/mo | On-demand pricing | Migrate to provisioned capacity | 1 week | -$400/mo (savings) |
| 1,000 sources | Shard management burden | Operational complexity | Migrate to Step Functions | 2-4 weeks | +$20/mo |

### Testing Scaling Transitions

Before each migration, validate with load testing:

**Pre-Migration Validation (Query Pattern - Option A)**
1. Populate source-configs table with 100 test sources
2. Run ingestion Lambda with current Scan implementation, measure duration (baseline)
3. Deploy Query pattern implementation to staging environment
4. Run ingestion Lambda with Query, measure duration (should be <1s vs 10-15s baseline)
5. Verify all 100 sources are correctly identified and invoked
6. Monitor for 24 hours to confirm no regressions

**Pre-Migration Validation (Sharded Schedulers - Option B)**
1. Create test sources distributed across 5 shards (20 sources each)
2. Deploy 5 ingestion Lambda instances (1 per shard)
3. Verify each shard only processes its assigned sources (no overlap)
4. Simulate shard failure (disable 1 scheduler), verify only 1/5 of sources affected
5. Validate shard rebalancing when new sources added

**Pre-Migration Validation (Step Functions - Option C)**
1. Create Step Functions workflow in staging
2. Populate 500+ test sources
3. Execute workflow, verify all sources processed within 60s
4. Simulate failures (DynamoDB throttling, Lambda errors), verify retry logic
5. Validate cost (count state transitions, compare to budget)

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
  name           = "${var.environment}-sentiment-analysis"  # e.g., dev-sentiment-analysis
  runtime        = "python3.13"
  handler        = "handler.lambda_handler"
  memory_size    = 1024                   # MB - required for DistilBERT model + Python runtime
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
- Attributes: type (STRING: "rss"|"api"), endpoint (STRING), auth_secret_ref (STRING: ARN), poll_interval_seconds (NUMBER), enabled (BOOLEAN), next_poll_time (NUMBER: Unix timestamp), last_poll_time (NUMBER: Unix timestamp), etag (STRING, optional for RSS), last_modified (STRING, optional for RSS), created_at (ISO8601), updated_at (ISO8601)
- GSI-1 (polling-schedule-index): PK=enabled (BOOLEAN), SK=next_poll_time (NUMBER) - Enables efficient Query instead of Scan for ingestion Lambda
  - Projection: ALL (project all attributes to avoid base table lookups)
  - Purpose: Critical scaling optimization - replaces O(n) Scan with O(log n) Query
  - Query pattern: `enabled = true AND next_poll_time <= now` (returns only sources ready to poll)
  - Scaling impact: Reduces scheduler query time from 15-20s (100 sources) to <1s, enables scaling to 500+ sources
- Purpose: Stores source subscription configurations accessed by Admin API and polling scheduler
- Access pattern:
  - Admin API: GetItem by source_id (single source lookup)
  - Ingestion Lambda: Query on GSI polling-schedule-index (find sources ready to poll)
  - Migration note: Initial implementation may use Scan (simpler), migrate to Query when approaching 50 sources
- Capacity Mode: On-demand (low-volume table, predictable costs)
- Encryption: Server-side encryption (SSE) with AWS-managed keys
- Backup: Point-in-time recovery (PITR) enabled

Note: Both tables use on-demand capacity for MVP to avoid throttling during unpredictable traffic patterns. After establishing baseline traffic (2-3 months), evaluate migration to provisioned capacity with autoscaling for cost optimization.

- Each module must document required inputs, optional inputs and outputs (e.g., topic_arn, queue_url, table_name).
- Conditional writes example for dedup (DynamoDB): PutItem with ConditionExpression: "attribute_not_exists(source_key) AND attribute_not_exists(item_id)".

CI / CD (with deployment safety and resilience patterns)
-------------------------------------------------------
- GitHub Actions responsibilities (PR):
  - Run `terraform fmt`, `terraform validate`, `tflint`.
  - Run security checks: `tfsec` (Terraform), `semgrep` or other SAST for code, dependency checks.
  - Run unit tests and build model artifact; upload artifact to S3 artifact bucket (versioned path) and publish artifact path as output for the TFC plan.
  - **Pre-deployment validation:**
    - Lambda package size check: Fail if package >200MB (approaching 250MB limit)
    - Memory profiling: Run Lambda locally with production-like workload, fail if memory usage >80% of allocated
    - Dependency vulnerability scan: Block critical CVEs (CVSS >7.0)
    - Cold start benchmark: Fail if cold start >5 seconds (compared to previous version baseline)

- Terraform Cloud integration:
  - Use VCS-connected TFC workspaces (one per environment). Merge to protected branches triggers TFC run.
  - TFC stores remote state and run logs. Require manual approvals or policy gates for production applies.
  - Store sensitive workspace variables in TFC as sensitive variables.
  - **Deployment safety (prevents bad deploys):**
    - Terraform state backup: Automated backup to S3 before each apply
    - State lock timeout: Auto-release locks after 1 hour (prevents indefinite locks)
    - Sentinel policies: Enforce reserved concurrency limits, DLQ configuration, encryption at rest
    - Drift detection: Daily scan for infrastructure drift, alert on >5 resource changes

- **Lambda Deployment Resilience (canary + circuit breakers):**
  - CodeDeploy configuration: Linear10PercentEvery1Minute deployment (10% traffic shift every minute over 10 minutes)
  - Pre-traffic hook: Synthetic test Lambda verifies new version responds correctly
  - CloudWatch alarms for automatic rollback (monitored during canary):
    - Lambda error rate >5% for new version → rollback
    - Lambda duration >2x baseline P99 → rollback
    - DLQ message increase >50% during deployment → rollback
    - Custom metric inference.accuracy <95% → rollback (DistilBERT sentiment validation)
  - Post-deployment validation:
    - Smoke test: Invoke new Lambda with fixture, verify expected sentiment output
    - Integration test: End-to-end test via Admin API → Lambda → DynamoDB
    - Rollback window: 24-hour window to revert if issues discovered post-deployment
  - Version retention: Keep last 10 Lambda versions for quick rollback
  - Alias management: Production traffic points to "live" alias (not $LATEST)

- **Rollback Procedures (fully automated):**
  - Lambda rollback: Update alias to previous version, ~30 seconds
  - Terraform rollback: `terraform apply` with previous state backup, ~5-10 minutes
  - DynamoDB schema rollback: Online schema changes only (no breaking changes), GSI can be deleted safely
  - Secrets rotation rollback: Secrets Manager maintains previous version for 24 hours
  - **Emergency rollback:** Break-glass script `tools/emergency-rollback.sh` (bypasses approval, logs audit trail)

- **Deployment Attack Protection:**
  - Deployment mutex: Only 1 deployment at a time per environment
  - Deployment authentication: TFC API token with MFA, rotated every 90 days
  - Audit logging: All deployments logged to CloudWatch Logs with Git commit SHA, deployer identity, timestamp
  - Deployment rate limiting: Max 5 deployments per day (prevents rapid-fire malicious deploys)
  - Terraform plan review: Require 2 approvals for production applies (4-eyes principle)

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
- Scaling & Performance Metrics (critical for proactive bottleneck detection):
  - `ingestion.fetch_duration_ms` - Time to scan/query source-configs table (emit from ingestion Lambda)
    - WARN alarm: >10,000ms for 2 consecutive minutes
    - CRITICAL alarm: >15,000ms for 2 consecutive minutes (triggers GSI migration)
  - `ingestion.execution_duration_ms` - Total ingestion Lambda execution time including invocations
    - WARN alarm: >30,000ms for 2 consecutive minutes
    - EMERGENCY alarm: >45,000ms for 1 minute (risk of 60s timeout)
  - `scheduler.sources_polled` - Count of sources processed per scheduler invocation
    - Used to correlate with scan_duration_ms for performance analysis
  - `scheduler.invocations_triggered` - Count of ingestion Lambda invocations triggered per cycle
  - `ingestion.throttled_invocations` - Count of throttled ingestion Lambda invocations (indicates concurrency bottleneck)
    - WARN alarm: >5% of total invocations for 1 hour
  - `dynamodb.consumed_read_capacity{table}` - Track DynamoDB read consumption for cost optimization analysis
  - `dynamodb.consumed_write_capacity{table}` - Track DynamoDB write consumption for provisioned capacity migration planning
  - **EventBridge Health Metrics** (prevents scheduler silent failures):
    - `eventbridge.scheduler_rule_invocations` - Count of ingestion Lambda invocations per hour
      - CRITICAL alarm: <50 invocations/hour (rule disabled or EventBridge failure)
      - Expected: 60 invocations/hour (1 per minute)
    - `eventbridge.rule_state{rule_name}` - Boolean metric indicating rule enabled/disabled state
      - CRITICAL alarm: ingestion-rule state = DISABLED for >2 consecutive minutes
      - Emit via Lambda that checks rule state every 5 minutes
    - `eventbridge.missed_invocations` - Count of ingestion invocations that didn't execute
      - Calculated: Expected (60/hour) - Actual invocations
      - WARN alarm: >5 missed invocations in 1 hour
- Dashboard widgets must reference these exact metric names.
- Admin Controls: Feed switching and watch filter management implemented via Admin API endpoints (GET/POST /v1/dashboard/config), UI can be added later as separate lightweight web interface
- Metric Dimension Access Control (security - zero-trust collaboration):
  - Two CloudWatch Dashboards (created via Terraform):
    1. **sentiment-analyzer-contributor-dashboard** (safe metrics only)
    2. **sentiment-analyzer-admin-dashboard** (all metrics, full access)
  - Contributor Dashboard (sentiment-analyzer-contributor IAM role):
    - Access: Read-only via CloudWatch Dashboard URL (no console access, no custom queries)
    - Metrics Allowed (aggregate only, NO dimensions):
      - AWS/Lambda/Invocations (aggregate Sum, no per-function breakdown)
      - AWS/Lambda/Duration (P50/P90/P99 statistics only)
      - AWS/Lambda/Errors (aggregate count, no error details)
      - AWS/Lambda/Throttles (aggregate count)
      - AWS/Lambda/ConcurrentExecutions (aggregate)
      - AWS/DynamoDB/ConsumedReadCapacityUnits (aggregate)
      - AWS/DynamoDB/ConsumedWriteCapacityUnits (aggregate)
      - AWS/DynamoDB/UserErrors (aggregate count, no details)
    - Metrics DENIED (security risk):
      - Any metric with source_id dimension (competitive intelligence - enables source usage tracking)
      - Any metric with api_key_id dimension (usage tracking)
      - ingestion.fetch_duration_ms (timing attack vector)
      - dlq.oldest_message_age_days (reveals incident duration)
      - dynamodb.throttled_requests (hot partition attack data)
    - Dashboard Configuration:
      - Fixed time ranges: 1h, 24h, 7d, 30d (no custom ranges)
      - No CloudWatch Insights access (prevents dimension filtering bypass)
      - No alarm modification permissions
      - Auto-refresh: 60 seconds
    - IAM Policy Enforcement:
      ```json
      {
        "Version": "2012-10-17",
        "Statement": [
          {
            "Effect": "Allow",
            "Action": ["cloudwatch:GetDashboard", "cloudwatch:ListDashboards", "cloudwatch:GetMetricData"],
            "Resource": "arn:aws:cloudwatch:us-west-2:ACCOUNT:dashboard/sentiment-analyzer-contributor-dashboard"
          },
          {
            "Effect": "Deny",
            "Action": ["cloudwatch:GetDashboard", "cloudwatch:GetMetricData"],
            "Resource": "arn:aws:cloudwatch:us-west-2:ACCOUNT:dashboard/sentiment-analyzer-admin-dashboard"
          }
        ]
      }
      ```
    - Example Widget (aggregate Lambda health):
      ```json
      {
        "type": "metric",
        "properties": {
          "metrics": [
            ["AWS/Lambda", "Invocations", {"stat": "Sum"}],
            ["AWS/Lambda", "Errors", {"stat": "Sum"}]
          ],
          "title": "Lambda Health (Service-Level - All Sources)",
          "region": "us-west-2",
          "period": 300
        }
      }
      ```
  - Admin Dashboard (sentiment-analyzer-admin IAM role):
    - Access: Full read/write via IAM admin role (console access, custom queries, exports)
    - Metrics Allowed: ALL (no restrictions)
    - Capabilities: Filter by all dimensions (source_id, model_version, api_key_id), create CloudWatch Insights queries, modify alarms/dashboards, export metric data to S3
  - Terraform Implementation: Create both dashboards in terraform/modules/cloudwatch_dashboard/, reference dashboard ARNs in IAM policies
  - Audit: Log all CloudWatch API calls (GetDashboard, GetMetricData) to CloudTrail with 7-year retention
  - Rationale: Prevents contributors from gaining competitive intelligence (per-source usage), planning DoS attacks (quota utilization), or optimizing attack timing (scan duration)

Security & privacy checklist
---------------------------
- TLS enforced for all external endpoints (TLS 1.2+ minimum).
- Secrets stored in AWS Secrets Manager or TFC sensitive variables; not in repo.
- Default behavior: do not persist full raw text. When required, approvals and encryption-at-rest must be in place.
- DynamoDB conditional writes and ExpressionAttributeNames/Values used for all expressions that incorporate user-provided values.

Input Validation & Sanitization (defense in depth against attacks):
- API Gateway request validation: Enable request validators for all POST/PATCH endpoints with JSON schema models
- Lambda validation: Use pydantic models for request/response validation with strict type enforcement
- Validation Rules:
  - source_id: Regex `^[a-z0-9-]{1,64}$` (lowercase alphanumeric and hyphens only, max 64 chars)
  - type: Enum allowlist {"rss", "api"} (reject any other values)
  - endpoint: Valid HTTPS URL (regex check), max 2048 characters, reject non-HTTPS
  - poll_interval_seconds: Integer range 60-86400 (1 minute to 24 hours)
  - enabled: Boolean only (true/false)
  - Control character rejection: Reject any input containing ASCII control characters (0x00-0x1F except whitespace)
  - SQL keyword blocking: Reject inputs containing SQL keywords (SELECT, DROP, INSERT, etc.) to prevent injection attempts
  - Path traversal prevention: Reject inputs containing ../, ..\, or encoded variants
- **Enhanced Security Validation** (prevents attacks):
  - **Size Limits** (prevents memory bombs and cost attacks):
    - API request body: Max 10KB (prevents JSON bombs)
    - RSS feed response: Max 10MB (prevents memory exhaustion in ingestion Lambda)
    - News API response: Max 2MB (Tiingo/Finnhub limit + buffer)
    - DynamoDB item size: Max 300KB (well below 400KB limit, prevents throttling)
    - SNS message size: Max 200KB (buffer below 256KB limit)
  - **Rate Limiting** (prevents abuse):
    - Source creation: Max 10 sources/hour per API key, max 100 total per account
    - API calls per source: Enforce poll_interval_seconds minimum of 60s
  - **Content Validation** (prevents injection and malformed data):
    - RSS feed XML: Validate against XML schema before parsing (prevents XXE attacks)
    - API JSON responses: Strict JSON parsing (reject malformed responses)
    - URL validation: Check against DNS rebinding (resolve DNS, reject private IPs like 127.0.0.1, 10.0.0.0/8)
    - SSL certificate validation: Enforce valid certificates (no self-signed), pin public keys for critical feeds
  - **Anomaly Detection** (prevents unusual behavior):
    - Detect sources with abnormally high item counts (>1000 items/poll) → flag for review
    - Detect rapid source creation (>20 sources in 10 minutes) → rate limit enforcement
    - Detect repeated validation failures from same API key (>50 in 1 hour) → temporary ban
- Error responses: Return 400 Bad Request with specific validation error messages (e.g., "source_id must be lowercase alphanumeric")
- Logging: Log validation failures to CloudWatch for security monitoring (track repeated failed attempts from same IP/API key)
- **Security Monitoring:**
  - CloudWatch metric: validation.failures{reason, api_key} - Track validation failure reasons
  - Alarm: >100 validation failures from single API key in 1 hour → CRITICAL (potential attack)
  - Automatic response: Temporary API key suspension (1 hour) after 200 failures

Operational Resilience & Known Fragilities
-------------------------------------------

This section documents known operational fragilities, attack vectors, and mitigations to ensure the service can run for extended periods with minimal intervention.

### Critical Operational Fragilities (Top 10)

**1. Ingestion Lambda Timeout at Scale (CRITICAL)**
- **Failure Mode:** Scheduler hits 60s AWS timeout when scanning 100+ sources
- **Impact:** Sources after timeout cutoff NEVER polled → silent permanent data gaps
- **Detection:** CloudWatch alarm ingestion.execution_duration_ms >45s
- **MTTR:** 1-2 weeks (requires GSI migration)
- **Mitigation:** Deploy GSI polling-schedule-index BEFORE reaching 50 sources (preventive)
- **Status:** GSI defined in schema, Query pattern documented in Scaling section

**2. DLQ 14-Day Data Loss (CRITICAL)**
- **Failure Mode:** Extended outage → DLQ messages expire after 14 days → permanent data loss
- **Impact:** Data gone forever, no recovery possible
- **Detection:** CloudWatch alarm when oldest DLQ message >7 days
- **MTTR:** Infinite (data permanently lost)
- **Mitigation:** S3 archival of DLQ messages older than 10 days, 90-day retention
- **Status:** IMPLEMENTED in spec lines 287-301

**4. EventBridge Rule Silent Disable (HIGH)**
- **Failure Mode:** Scheduler rule gets disabled (human error, AWS issue)
- **Impact:** Complete ingestion halt, no new data processed
- **Detection:** CloudWatch alarm when ingestion invocations <50/hour
- **MTTR:** 2-4 hours (investigate, re-enable rule)
- **Mitigation:** EventBridge rule state monitoring every 5 minutes, auto-enable trigger
- **Status:** IMPLEMENTED in spec lines 648-657

**5. Regional AWS Service Outage (HIGH)**
- **Failure Mode:** DynamoDB/EventBridge/Secrets Manager outage in us-west-2
- **Impact:** Complete service outage for 4-12 hours (historical AWS outage duration)
- **Detection:** Immediate (Lambda errors, API failures)
- **MTTR:** Hours (wait for AWS recovery)
- **Mitigation:** Multi-region deployment (future enhancement), manual failover procedures
- **Status:** UNMITIGATED - single region deployment accepted for MVP

**6. Lambda Package Size Explosion (MEDIUM)**
- **Failure Mode:** New dependencies push package over 250MB Lambda limit
- **Impact:** Deployment fails, stuck on old version
- **Detection:** Pre-deployment package size check in CI/CD
- **MTTR:** 30-60 minutes (remove dependencies, rebuild)
- **Mitigation:** Container images for Lambda, pre-deployment size validation (<200MB threshold)
- **Status:** IMPLEMENTED in spec line 606

**7. DynamoDB On-Demand Cost Explosion (MEDIUM)**
- **Failure Mode:** Unexpected traffic spike causes $1,000+ monthly bill
- **Impact:** Budget exhaustion, service may be shut down
- **Detection:** AWS cost anomaly detection, daily budget alerts
- **MTTR:** 1 week (migrate to provisioned capacity)
- **Mitigation:** Cost alarms at 20% over budget, automatic traffic throttling, provisioned capacity migration plan
- **Status:** Cost monitoring mentioned (line 452), provisioned migration documented (line 273)

### Attack Resilience Summary

**Most Damaging Attack:** Ingestion timeout DoS
- **Attacker cost:** $0 (create 100+ sources via Admin API)
- **Defender cost:** 1-2 weeks engineering time for GSI migration
- **Detection time:** 45 seconds (execution time alarm)
- **Mitigation:** Mandatory GSI deployment before 50 sources, source quotas

### Can This Service Run for 1 Year Unattended?

**NO** - Multiple guaranteed failures without intervention:
1. Scheduler will timeout at ~100 sources without GSI migration (requires engineering work)
2. DLQ may fill during extended outages causing data loss (requires S3 archival implementation)
3. AWS service outages require manual failover (no multi-region redundancy)

**YES** - If the following protections are implemented:
1. ⚠️ DLQ S3 archival (DEFERRED - post-production enhancement, see TD-012)
2. ✅ EventBridge rule monitoring (IMPLEMENTED)
3. ✅ Deployment circuit breakers (IMPLEMENTED)
4. ⚠️ GSI deployment before 50 sources (NEEDS PROACTIVE DEPLOYMENT)
5. ❌ Multi-region failover (NOT IMPLEMENTED - accepted risk for MVP)

### Single Points of Failure (External Dependencies)

All AWS services in us-west-2 are SPOFs:
1. **DynamoDB** - Core data store (RTO: hours, RPO: 1 hour via PITR)
2. **Secrets Manager** - OAuth token storage (mitigation: caching reduces impact)
3. **EventBridge** - Scheduler trigger (mitigation: manual Lambda invocation possible)
4. **CloudWatch Logs** - Observability (mitigation: Lambdas continue running, just blind)
5. **API Gateway** - Admin API (mitigation: direct DynamoDB access possible)

**Graceful Degradation:**
- CloudWatch Logs down → Lambdas continue executing (verified by AWS design)
- CloudWatch Metrics down → Alarms fail OPEN (no false alarms), monitoring blind
- EventBridge down → Manual scheduler invocation via script maintains critical sources

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

- Q: Which sentiment analysis approach should the Lambda inference function use? → A: DistilBERT (distilbert-base-uncased-finetuned-sst-2-english via HuggingFace) - Fine-tuned transformer model, superior accuracy, 100-150ms inference, ~250MB model packaged in Lambda layer, better handles nuanced sentiment than rule-based approaches
- Q: What should be the DynamoDB table partition key (PK) and sort key (SK) design for the items table? → A: PK: `source_type#source_id` (e.g., "rss#source-1"), SK: `item_id` (content hash or publisher ID) - Distributes writes across sources, supports per-source queries
- Q: How should the Admin API (POST /v1/sources, etc.) authenticate requests? → A: API Gateway API Keys with usage plans - Simplest implementation, built-in rate limiting, easy rotation via Terraform, suitable for service-to-service or small admin team
- Q: Which AWS region should host the infrastructure? → A: us-west-2 (Oregon) - Good alternative to us-east-1, slightly higher availability due to fewer outages historically, minimal cost difference
- Q: What technology should implement the externally-facing dashboard with metrics and admin controls? → A: CloudWatch Dashboard (native AWS) - Zero infrastructure overhead, direct metric integration, built-in auth via IAM/SSO, limited customization for admin controls
- Q: Where should source configuration data (from POST /v1/sources) be persisted? → A: DynamoDB table (source-configs) with source_id as PK - Native serverless integration, fast Lambda access, supports atomic updates, consistent with existing data layer
- Q: What should trigger the periodic polling of news APIs for each configured source? → A: EventBridge rule (every 5 minutes) triggers Ingestion Lambda directly. Ingestion Lambda fetches active configs via GSI query, aggregates tickers, fetches from Tiingo/Finnhub in parallel with circuit breaker protection.
- Q: How does the architecture handle scaling? → A: Ingestion Lambda processes all active configurations in a single invocation using parallel ThreadPoolExecutor fetching. Scales via increased memory/timeout if needed.
- Q: What memory allocation should the sentiment inference Lambda function use? → A: 1024 MB - Required for DistilBERT model + Python runtime + logging, comfortable headroom for model loading, faster inference with more allocated CPU
- Q: Which DynamoDB capacity mode should the tables use? → A: On-demand capacity - Pay per request ($1.25/M writes, $0.25/M reads), no throttling, instant scaling, unpredictable costs - Best for MVP with unknown traffic patterns
- Q: Which news APIs should the service use? → A: Tiingo (financial news with sentiment) and Finnhub (market news). Both have free tiers suitable for MVP, with paid upgrade paths.
- Q: How should Lambda function failures be handled? → A: Dedicated SQS DLQ per Lambda function - Each Lambda has its own DLQ, maxReceiveCount=3 retries, CloudWatch alarm when DLQ depth >10, DLQ processor Lambda for replay - Complete failure visibility and recovery
- Q: What are the acceptable recovery targets for disaster recovery? → A: RTO: 4 hours, RPO: 1 hour - Balanced targets, achievable with DynamoDB PITR, daily AWS Backup snapshots, acceptable for non-mission-critical service - Future upgrade path to multi-region for RTO: 1 hour, RPO: 5 minutes
- Q: What is the expected throughput for ingested items? → A: 100 items/min average, 1,000 items/min peak - Moderate load for MVP with 10-50 sources, validates serverless scaling, reasonable costs $50-200/month
- Q: Should Lambda functions run in a VPC? → A: No VPC (public Lambda execution) - Lambdas access AWS services via public endpoints with IAM auth, lowest latency, no NAT costs, simpler networking - Recommended for serverless-only stack
- Q: What input validation rules should the Admin API enforce? → A: Comprehensive validation with pydantic models - source_id: regex `^[a-z0-9-]{1,64}$`, endpoint: HTTPS URL max 2048 chars, poll_interval: integer 60-86400, reject control characters - Use API Gateway request validation + Lambda pydantic models
- Q: How should the service handle data deletion requests (GDPR "right to be forgotten")? → A: DELETE endpoint + cascading deletion - DELETE /v1/items/{source}/{item_id} removes record from sentiment-items table, audit logs deletion with timestamp and requester, returns 204 No Content - Full GDPR compliance
- Q: What are the architectural scaling bottlenecks and when should migrations be triggered? → A: Key bottlenecks: (1) Ingestion Lambda DynamoDB Scan at ~50-100 sources (15-20s scan time), (2) Ingestion timeout (60s) at ~100-150 sources - Mitigation: GSI (polling-schedule-index) enables Query pattern for 10-20x performance improvement, supports scaling to 500 sources before requiring sharded schedulers or Step Functions - Proactive monitoring via CloudWatch alarms (ingestion.fetch_duration_ms >15s triggers migration)
- Q: What are the operational fragilities and can this service run unattended for 1 year? → A: Key issues: (1) Ingestion timeout at 100 sources (guaranteed failure), (2) DLQ 14-day expiry (permanent data loss), (3) Regional AWS outage (4-12 hour RTO) - Service CAN run 1 year unattended IF: DLQ S3 archival enabled, EventBridge rule monitoring active, GSI deployed before 50 sources - Service CANNOT run 1 year unattended WITHOUT these protections due to guaranteed failures at scale
