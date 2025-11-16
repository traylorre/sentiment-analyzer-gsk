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
- Twitter API: Tier-based configuration (externalized via Terraform variable `twitter_api_tier`)
  - Current tier: Free ($0/month) - 1,500 tweets/month, 450 requests/15min
  - Upgrade path: Basic ($100/month, 50K tweets/month) → Pro ($5K/month, 1M tweets/month)
  - Tier Management:
    - Configuration: Terraform variable controls tier (values: free|basic|pro)
    - Monthly quota tracking: DynamoDB source-configs table tracks consumption per source
    - Automatic tier detection: Lambda reads TWITTER_API_TIER environment variable
    - Quota enforcement: Pre-request quota check prevents exceeding monthly cap
    - Upgrade trigger: CloudWatch alarm at 80% quota utilization for 2 consecutive days
  - Rate limit handling: Dual-layer (request rate + monthly consumption cap) with exponential backoff
  - Compliance: Must follow Twitter Developer Agreement (attribution, no redistribution)
  - Tier Upgrade Procedure (seamless migration):
    1. Update Twitter Developer Portal: Upgrade account tier (Free → Basic or Basic → Pro)
    2. Update Terraform variable: Change `var.twitter_api_tier = "basic"` (or "pro") in terraform/live/<env>/terraform.tfvars
    3. Run Terraform apply: `terraform apply` updates Lambda environment variables, ingestion concurrency, CloudWatch alarms
    4. Automatic detection: Ingestion Lambda reads new TWITTER_API_TIER env var, adjusts quota enforcement automatically
    5. Quota reset: DynamoDB source-configs table entries auto-reset monthly_tweets_consumed on next monthly boundary
    6. Zero downtime: No code changes required, no Lambda redeployment, no DynamoDB migration
    7. Rollback: Simply revert Terraform variable and re-apply if needed
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
- Lambda Configuration (tier-aware for ingestion Lambda):
  - Scheduler Lambda: 256 MB memory, 60s timeout, reserved concurrency: 1 (single invocation per minute, scans DynamoDB, invokes ingestion Lambdas)
  - Ingestion Lambda: 256 MB memory, 60s timeout, reserved concurrency tier-based (controlled via Terraform variable `var.twitter_api_tier`):
    - Free tier: reserved concurrency = 10 (conservative limit for 1,500 tweets/month, ~50 tweets/day)
    - Basic tier: reserved concurrency = 20 (supports 50K tweets/month, ~1,666 tweets/day)
    - Pro tier: reserved concurrency = 50 (supports 1M tweets/month, ~33,333 tweets/day)
  - Inference Lambda: 512 MB memory, 30s timeout, reserved concurrency: 20 (processes SQS messages, performs VADER sentiment analysis, writes to DynamoDB)
- Expected Throughput:
  - Average load: 100 items/minute (~1.7 items/second)
  - Peak load: 1,000 items/minute (~16.7 items/second) during viral events or breaking news
  - Supports: 10-50 active sources with moderate activity
  - DynamoDB throughput: ~100-1,000 write requests/minute (well within on-demand capacity)
  - Lambda concurrency: Peak requires ~5-10 concurrent inference executions (well below reserved limit of 20)
- Cost Estimates (tier-dependent + source count scaling, based on 100 items/min average load per source):

  **Phase 1: 10-50 Sources (MVP)**
  - Twitter Free tier: ~$15-30/month total
    - Twitter API: $0/month (1,500 tweets/month cap, ~30 tweets/source/month at 50 sources)
    - Lambda: $5-10/month (10 reserved concurrency, ~200K invocations/month)
    - DynamoDB: $5-10/month (on-demand, ~400K writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $5-10/month
  - Bottleneck: Twitter quota exhaustion at ~50 active Twitter sources (30 tweets/source/month = 1,500 total)

  **Phase 2: 50-100 Sources (Growth)**
  - Twitter Basic tier required: ~$130-180/month total
    - Twitter API: $100/month (50K tweets/month, ~500 tweets/source/month at 100 sources)
    - Lambda: $15-30/month (20 reserved concurrency, ~500K invocations/month)
    - DynamoDB: $10-20/month (on-demand, ~1M writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $15-30/month
  - Architectural change: Migrate to Query pattern (GSI) around 50 sources (+$2/month GSI cost)
  - Bottleneck: Scheduler Lambda scan/query time approaching 15-20s

  **Phase 3: 100-500 Sources (Scale-up)**
  - Twitter Basic → Pro tier: ~$200-2,000/month total (highly variable based on per-source activity)
  - Low activity (10 tweets/source/month, 5,000 tweets total): ~$200-300/month
    - Twitter API: $100/month (Basic tier sufficient)
    - Lambda: $30-60/month (20 reserved concurrency, ~1M invocations/month)
    - DynamoDB: $30-60/month (on-demand, ~2.5M writes/month)
    - API Gateway + CloudWatch + Secrets Manager: $40-80/month
  - High activity (100 tweets/source/month, 50,000 tweets total): ~$1,000-1,500/month
    - Twitter API: $100/month (Basic tier at cap)
    - Lambda: $100-200/month (50 reserved concurrency, ~5M invocations/month)
    - DynamoDB: $150-300/month (on-demand, ~10M writes/month - consider provisioned migration)
    - API Gateway + CloudWatch + Secrets Manager: $50-100/month
  - Architectural change: Sharded schedulers or Step Functions required around 100-150 sources
  - Bottleneck: Scheduler timeout (60s), ingestion Lambda concurrency

  **Phase 4: 500-5,000 Sources (Enterprise)**
  - Twitter Pro tier required: ~$5,200-10,000/month total
    - Twitter API: $5,000/month (1M tweets/month, ~200 tweets/source/month at 5,000 sources)
    - Lambda: $200-500/month (50-100 reserved concurrency, ~10-20M invocations/month)
    - DynamoDB (provisioned): $300-800/month (replaces on-demand for 85% cost savings)
    - API Gateway + CloudWatch + Secrets Manager: $100-200/month
    - Step Functions (if using Option C): $20-50/month (state transitions)
  - Cost optimization: Migrate DynamoDB to provisioned capacity when costs exceed $500/month
  - Bottleneck: Twitter Pro tier quota (1M tweets/month), operational complexity

  **Phase 5: >5,000 Sources (Re-architecture)**
  - Twitter Enterprise + custom infrastructure: ~$20,000-50,000/month
    - Twitter API: $10,000-30,000/month (Enterprise tier, custom contract)
    - Lambda/Compute: $2,000-5,000/month (ECS Fargate or larger Lambda allocations)
    - DynamoDB (provisioned): $1,000-3,000/month
    - Additional services (Kinesis, Redis, multi-region): $2,000-5,000/month
    - Operational costs: Dedicated SRE team, monitoring tools, incident response

  **Cost Scaling Summary by Source Count:**
  | Sources | Monthly Cost | Primary Expense | Tier Required | Architecture |
  |---------|-------------|-----------------|---------------|--------------|
  | 10 | $15-30 | Lambda + DynamoDB | Free | Scan pattern |
  | 50 | $130-180 | Twitter Basic tier | Basic | Query pattern (GSI) |
  | 100 | $200-500 | Lambda + DynamoDB | Basic/Pro | Query + shards |
  | 500 | $1,000-2,000 | Twitter + DynamoDB | Pro | Shards or Step Functions |
  | 1,000 | $2,000-5,000 | Twitter Pro tier | Pro | Step Functions |
  | 5,000 | $10,000-20,000 | Twitter Enterprise | Enterprise | Distributed scheduler |

  **Key Cost Inflection Points:**
  - 50 sources: +$100/month (Twitter Free → Basic tier upgrade)
  - 100 sources: +$100-300/month (increased Lambda/DynamoDB usage)
  - 500 sources: +$4,000-5,000/month (Twitter Basic → Pro tier upgrade)
  - 1,000 sources: DynamoDB provisioned migration saves $400-1,000/month
  - 5,000 sources: +$10,000-20,000/month (Twitter Pro → Enterprise + infrastructure scaling)
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

Scaling Thresholds & Migration Triggers
----------------------------------------

This service has architectural scaling limits that require proactive monitoring and migration planning. The specification is designed for 10-50 sources (MVP phase) but includes clear migration paths to scale to 5,000+ sources.

### Scaling Phases & Bottlenecks

**Phase 1: 0-50 Sources (Current Architecture - SAFE)**
- Expected cost: $15-30/month (Twitter Free tier)
- No architectural changes required
- All components operate well within limits
- Primary risk: Twitter API Free tier monthly quota (1,500 tweets/month)
- Action: Monitor Twitter quota utilization via CloudWatch alarm (80% threshold)

**Phase 2: 50-100 Sources (Performance Degradation Begins)**
- Expected cost: $130-160/month (Twitter Basic tier required)
- Bottleneck #1: Scheduler Lambda DynamoDB Scan performance (15-20s scan time)
  - Symptom: CloudWatch metric `scheduler.scan_duration_ms` exceeds 15,000ms
  - Impact: Reduced polling accuracy, sources miss scheduled windows
  - Migration trigger: When scan duration >15s for 2 consecutive days
  - Fix: Migrate scheduler Lambda from Scan to Query using GSI polling-schedule-index
  - Effort: 2-3 days engineering (update Lambda code, deploy)
  - Cost impact: Minimal (GSI adds ~$1-2/month)
- Bottleneck #2: Twitter API Free tier rate limit (30 req/min)
  - Symptom: HTTP 429 errors in ingestion Lambda logs, exponential backoff delays
  - Migration trigger: When 80% of 450 requests/15min quota sustained for 1 day
  - Fix: Upgrade to Twitter Basic tier ($100/month, higher rate limits)
  - Effort: 15 minutes (update Terraform variable, apply)
- Bottleneck #3: Ingestion Lambda reserved concurrency (10 concurrent, 85 invocations/min capacity)
  - Symptom: TooManyRequestsException in CloudWatch Logs, messages sent to ingestion-lambda-dlq
  - Migration trigger: When ingestion Lambda throttled invocations >5% for 1 hour
  - Fix: Increase reserved concurrency to 20 (coordinated with Twitter tier upgrade)
  - Effort: 10 minutes (update Terraform, apply)

**Phase 3: 100-500 Sources (Architectural Change Required)**
- Expected cost: $200-2,000/month (depends on Twitter usage per source)
- Bottleneck #4: Scheduler Lambda timeout (60s hard AWS limit)
  - Symptom: Scheduler Lambda timeout errors in CloudWatch Logs, incomplete source polling
  - Impact: CATASTROPHIC - some sources never polled, silent data gaps
  - Migration trigger: When scheduler execution time >45s for 3 consecutive cycles
  - Fix: Implement ONE of three architectural options (see "Scheduler Scaling Options" below)
  - Effort: 1-2 weeks engineering (Option A), 2-4 weeks (Option B/C)
  - Cost impact: Minimal for Option A/B, +$10-20/month for Option C (Step Functions)
- Bottleneck #5: API Gateway API Key daily quota (1,000 req/day)
  - Symptom: HTTP 429 errors for Admin API operations
  - Migration trigger: When approaching 800 requests/day from single API key
  - Fix: Issue multiple API keys (1 per admin user/system) or increase usage plan quota
  - Effort: 30 minutes (Terraform change)

**Phase 4: 500-5,000 Sources (Enterprise Scale)**
- Expected cost: $5,000-10,000/month (Twitter Pro tier + DynamoDB provisioned capacity)
- Bottleneck #6: Twitter API Pro tier monthly quota (1M tweets/month)
  - Migration trigger: When approaching 800K tweets/month (80% of Pro tier)
  - Fix: Negotiate Twitter Enterprise API contract (custom pricing)
  - Effort: 1-2 months (legal, procurement, integration)
- Bottleneck #7: DynamoDB on-demand cost inefficiency
  - Symptom: DynamoDB costs exceed $500/month
  - Migration trigger: After establishing 2-3 months of baseline traffic patterns
  - Fix: Migrate to provisioned capacity with auto-scaling (85% cost savings at scale)
  - Effort: 1 week (capacity planning, Terraform changes, gradual migration)
- Bottleneck #8: Lambda account-level concurrency (1,000 concurrent executions)
  - Symptom: Account-wide throttling across all Lambdas
  - Migration trigger: When total reserved concurrency allocations exceed 800
  - Fix: Request AWS support to increase account limit to 10,000
  - Effort: 1-2 weeks (support ticket, justification, approval)

**Phase 5: >5,000 Sources (Re-architecture Required)**
- Expected cost: $20,000-50,000/month
- Primary bottleneck: Scheduler fan-out pattern (even with Step Functions, coordination overhead grows)
- Fix options:
  - Event-driven architecture (replace polling with Kinesis Data Streams + webhooks)
  - Distributed scheduler (ECS Fargate or Kubernetes with sharded responsibility)
  - Multi-region deployment (reduce latency, increase availability)
- Effort: 3-6 months engineering + dedicated SRE team

### Scheduler Scaling Options (Phase 3 Migration)

When scheduler Lambda execution time exceeds 45s (typically around 100 sources), implement ONE of the following architectural patterns:

**Option A: Query Pattern with GSI (RECOMMENDED for 100-500 sources)**
- Prerequisites: GSI polling-schedule-index already exists (defined in DynamoDB schema above)
- Change: Replace DynamoDB Scan with Query in scheduler Lambda
- Before (O(n) Scan):
  ```python
  response = dynamodb.scan(
      TableName='source-configs',
      FilterExpression='enabled = :true AND next_poll_time <= :now'
  )
  # Scans entire table, returns filtered results
  # 100 sources: ~7-10s, 500 sources: ~40-60s (timeout risk)
  ```
- After (O(log n) Query):
  ```python
  response = dynamodb.query(
      TableName='source-configs',
      IndexName='polling-schedule-index',
      KeyConditionExpression='enabled = :true AND next_poll_time <= :now'
  )
  # Queries only eligible sources using index
  # 100 sources: <1s, 500 sources: <2s, 1,000 sources: <3s
  ```
- Performance improvement: 10-20x faster query time
- Scales to: ~500 sources before hitting other limits (ingestion concurrency, cost)
- Cost: +$1-2/month (GSI storage and read capacity)
- Effort: 2-3 days (update Lambda code, test, deploy)
- Rollback: Easy (revert Lambda code to Scan, GSI remains unused)

**Option B: Sharded Schedulers (for 500-5,000 sources)**
- Architecture: Split sources across multiple scheduler Lambdas
  - EventBridge rule 1 (every 1 min) → Scheduler-Shard-0 (handles sources 0-99)
  - EventBridge rule 2 (every 1 min) → Scheduler-Shard-1 (handles sources 100-199)
  - EventBridge rule 3 (every 1 min) → Scheduler-Shard-2 (handles sources 200-299)
  - etc. (dynamically scale shards as sources grow)
- Implementation:
  - Add `shard_id` field to source-configs table (0-49 for 50 shards)
  - Assign shard_id during source creation (round-robin or hash-based)
  - Each shard queries: `shard_id = X AND enabled = true AND next_poll_time <= now`
  - Requires GSI: PK=shard_id, SK=next_poll_time (or composite GSI)
- Scales to: ~5,000 sources (50 shards × 100 sources/shard)
- Cost: Same as Option A (no additional costs beyond GSI)
- Effort: 1-2 weeks (design sharding strategy, update source creation logic, deploy multiple schedulers)
- Operational complexity: Managing 10-50 EventBridge rules, monitoring multiple schedulers
- Rollback: Moderate difficulty (requires data migration to remove shard_id)

**Option C: Step Functions State Machine (for unlimited sources)**
- Architecture: Replace scheduler Lambda with Step Functions workflow
  - EventBridge rule (every 1 min) → Step Functions execution
  - Step Functions queries DynamoDB (paginated, handles 1M+ sources)
  - Map state (parallel mode) fans out to ingestion Lambdas (up to 10,000 parallel branches)
  - No timeout constraint (Step Functions max execution: 1 year)
- Workflow:
  ```
  1. Query DynamoDB (parallel, paginated if >1MB results)
  2. Map state: For each eligible source → Invoke ingestion Lambda
  3. Aggregate results, update CloudWatch metrics
  4. Handle errors (DLQ integration)
  ```
- Scales to: Unlimited sources (tested to 100,000+ by AWS customers)
- Cost: $0.025 per 1,000 state transitions (~$1-5/month for 100-1,000 sources)
- Effort: 2-4 weeks (learn Step Functions, design workflow, migrate logic, test at scale)
- Benefits: Built-in retry logic, visual workflow, better observability
- Drawbacks: New orchestration paradigm, team learning curve
- Rollback: Difficult (significant architectural change)

### CloudWatch Alarms for Proactive Scaling

Implement these alarms to trigger migrations BEFORE failures occur:

**Scheduler Performance (Critical - Bottleneck #2 & #4)**
- Metric: `scheduler.scan_duration_ms` (custom metric, emit from scheduler Lambda)
- Alarm 1: WARN when scan_duration >10,000ms for 2 consecutive minutes
  - Action: Investigate source count growth, prepare for GSI migration
- Alarm 2: CRITICAL when scan_duration >15,000ms for 2 consecutive minutes
  - Action: Immediately migrate to Query pattern (Option A)
- Alarm 3: EMERGENCY when execution_duration >45,000ms for 1 minute
  - Action: Risk of timeout, urgently deploy Option A or B

**Twitter API Quota (Critical - Bottleneck #1 & #4)**
- Metric: `twitter.quota_utilization_pct` (custom metric: monthly_tweets_consumed ÷ tier_limit × 100)
- Alarm 1: WARN when quota_utilization >60% for 2 consecutive days
  - Action: Review source activity, forecast when 80% threshold will be reached
- Alarm 2: CRITICAL when quota_utilization >80% for 2 consecutive days (per spec line 53)
  - Action: Prepare tier upgrade (Basic → Pro)
- Alarm 3: EMERGENCY when quota_utilization >95%
  - Action: Immediately upgrade tier or disable low-priority sources

**Ingestion Lambda Throttling (Moderate - Bottleneck #5)**
- Metric: `AWS/Lambda/Throttles` (built-in CloudWatch metric)
- Alarm: WARN when throttled invocations >5% for 1 hour
  - Action: Increase reserved concurrency proportional to Twitter tier

**DLQ Depth (Operational - Indicates failures)**
- Metric: `AWS/SQS/ApproximateNumberOfMessagesVisible` for each DLQ
- Alarm: CRITICAL when DLQ depth >10 messages (per spec line 211)
  - Action: Investigate root cause (API failures, throttling, bugs)

**Cost Overrun (Budget Protection)**
- Metric: AWS Cost Explorer / Budgets
- Alarm 1: WARN when monthly forecast exceeds budget by 20%
- Alarm 2: CRITICAL when actual spending exceeds budget
  - Action: Review DynamoDB on-demand costs, consider provisioned capacity migration

### Migration Decision Matrix

| Current State | Symptom | Bottleneck | Recommended Fix | Effort | Cost Impact |
|---------------|---------|------------|-----------------|--------|-------------|
| 30 sources | Twitter quota 80% | Twitter Free tier | Upgrade to Basic ($100/mo) | 15 min | +$100/mo |
| 50 sources | Scan time >10s | Scheduler Scan | Deploy Query pattern (Option A) | 2-3 days | +$2/mo |
| 100 sources | Execution time >45s | Scheduler timeout | Already using Query? Deploy shards (Option B) | 1-2 weeks | +$0/mo |
| 500 sources | Quota 80% (Basic) | Twitter Basic tier | Upgrade to Pro ($5K/mo) | 15 min | +$4,900/mo |
| 1,000 sources | DynamoDB cost >$500/mo | On-demand pricing | Migrate to provisioned capacity | 1 week | -$400/mo (savings) |
| 5,000 sources | Shard management burden | Operational complexity | Migrate to Step Functions (Option C) | 2-4 weeks | +$20/mo |

### Testing Scaling Transitions

Before each migration, validate with load testing:

**Pre-Migration Validation (Query Pattern - Option A)**
1. Populate source-configs table with 100 test sources
2. Run scheduler Lambda with current Scan implementation, measure duration (baseline)
3. Deploy Query pattern implementation to staging environment
4. Run scheduler Lambda with Query, measure duration (should be <1s vs 10-15s baseline)
5. Verify all 100 sources are correctly identified and invoked
6. Monitor for 24 hours to confirm no regressions

**Pre-Migration Validation (Sharded Schedulers - Option B)**
1. Create test sources distributed across 5 shards (20 sources each)
2. Deploy 5 scheduler Lambda instances (1 per shard)
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
- Attributes: type (STRING: "rss"|"twitter"), endpoint (STRING), auth_secret_ref (STRING: ARN), poll_interval_seconds (NUMBER), enabled (BOOLEAN), next_poll_time (NUMBER: Unix timestamp), last_poll_time (NUMBER: Unix timestamp), etag (STRING, optional for RSS), last_modified (STRING, optional for RSS), twitter_api_tier (STRING: "free"|"basic"|"pro", for Twitter sources only), monthly_tweets_consumed (NUMBER: for Twitter sources, resets monthly), last_quota_reset (NUMBER: Unix timestamp, for Twitter sources), quota_exhausted (BOOLEAN: for Twitter sources, auto-disable when monthly cap reached), created_at (ISO8601), updated_at (ISO8601)
- GSI-1 (polling-schedule-index): PK=enabled (BOOLEAN), SK=next_poll_time (NUMBER) - Enables efficient Query instead of Scan for scheduler Lambda
  - Projection: ALL (project all attributes to avoid base table lookups)
  - Purpose: Critical scaling optimization - replaces O(n) Scan with O(log n) Query
  - Query pattern: `enabled = true AND next_poll_time <= now` (returns only sources ready to poll)
  - Scaling impact: Reduces scheduler query time from 15-20s (100 sources) to <1s, enables scaling to 500+ sources
- Purpose: Stores source subscription configurations accessed by Admin API and polling scheduler
- Access pattern:
  - Admin API: GetItem by source_id (single source lookup)
  - Scheduler Lambda: Query on GSI polling-schedule-index (find sources ready to poll)
  - Migration note: Initial implementation may use Scan (simpler), migrate to Query when approaching 50 sources
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
- Scaling & Performance Metrics (critical for proactive bottleneck detection):
  - `scheduler.scan_duration_ms` - Time to scan/query source-configs table (emit from scheduler Lambda)
    - WARN alarm: >10,000ms for 2 consecutive minutes
    - CRITICAL alarm: >15,000ms for 2 consecutive minutes (triggers GSI migration)
  - `scheduler.execution_duration_ms` - Total scheduler Lambda execution time including invocations
    - WARN alarm: >30,000ms for 2 consecutive minutes
    - EMERGENCY alarm: >45,000ms for 1 minute (risk of 60s timeout)
  - `scheduler.sources_polled` - Count of sources processed per scheduler invocation
    - Used to correlate with scan_duration_ms for performance analysis
  - `scheduler.invocations_triggered` - Count of ingestion Lambda invocations triggered per cycle
  - `twitter.quota_utilization_pct{source_id}` - Monthly tweet consumption percentage per source
    - Calculated: (monthly_tweets_consumed ÷ tier_limit) × 100
    - WARN alarm: >60% for 2 consecutive days
    - CRITICAL alarm: >80% for 2 consecutive days (per tier upgrade trigger)
    - EMERGENCY alarm: >95% (immediate action required)
  - `twitter.quota_remaining{tier}` - Aggregate remaining tweets across all Twitter sources for current tier
  - `ingestion.throttled_invocations` - Count of throttled ingestion Lambda invocations (indicates concurrency bottleneck)
    - WARN alarm: >5% of total invocations for 1 hour
  - `dynamodb.consumed_read_capacity{table}` - Track DynamoDB read consumption for cost optimization analysis
  - `dynamodb.consumed_write_capacity{table}` - Track DynamoDB write consumption for provisioned capacity migration planning
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
- Q: Should the Twitter API tier configuration be hardcoded or externalized to support future upgrades (Free → Basic → Pro)? → A: Externalized via Terraform variable `twitter_api_tier` - Enables seamless tier upgrades with zero code changes, tier-aware Lambda concurrency scaling (10→20→50), DynamoDB quota tracking fields, automatic tier detection via environment variables - Upgrade procedure: change Terraform variable + apply (zero downtime)
- Q: What are the architectural scaling bottlenecks and when should migrations be triggered? → A: 32 identified bottlenecks across 9 categories - Top 3: (1) Twitter Free tier quota at 1,500 tweets/month, (2) Scheduler Lambda DynamoDB Scan at ~50-100 sources (15-20s scan time), (3) Scheduler timeout (60s) at ~100-150 sources - Mitigation: GSI (polling-schedule-index) enables Query pattern for 10-20x performance improvement, supports scaling to 500 sources before requiring sharded schedulers or Step Functions - Proactive monitoring via CloudWatch alarms (scheduler.scan_duration_ms >15s triggers migration)
