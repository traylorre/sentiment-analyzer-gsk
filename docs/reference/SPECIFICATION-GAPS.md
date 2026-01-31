# Specification Gaps & Resolutions
**Date:** 2025-11-16
**Status:** ✅ ALL CRITICAL GAPS RESOLVED (2 of 2 complete)
**Source:** Comprehensive interface analysis

**Progress:**
- ✅ Gap 1: Standardized Error Response Schema - **RESOLVED** (SPEC.md lines 148-188)
- ✅ Gap 2: Metric Dimension Access Control - **RESOLVED** (SPEC.md lines 753-820)

---

## CRITICAL Gaps (MUST FIX - P0)

### Gap 1: Standardized Error Response Schema ✅ RESOLVED

**Current State:** ~~SPEC.md mentions "Return 400 Bad Request with specific validation error messages" (line 740) but NO schema defined~~

**Resolution Status:** ✅ **COMPLETE** - Full error schema added to SPEC.md lines 148-188

**Risk:** ~~Inconsistent API behavior, difficult client integration, poor debugging~~ MITIGATED

**Resolution Implemented:**

```yaml
# Add to SPEC.md - Section: Admin API

Error Response Schema (ALL endpoints):

HTTP Status Codes:
  200 OK - Success
  201 Created - Resource created
  204 No Content - Deletion successful
  400 Bad Request - Validation error
  401 Unauthorized - Invalid/missing API key
  404 Not Found - Resource doesn't exist
  409 Conflict - Duplicate resource
  429 Too Many Requests - Rate limit exceeded (includes Retry-After header)
  500 Internal Server Error - Unexpected error
  503 Service Unavailable - Temporary outage

Error Response Body (JSON):
{
  "error": {
    "code": "ERROR_CODE",              # Machine-readable error code (enum)
    "message": "Human-readable error",  # English description
    "field": "field_name",              # Optional: Field that caused error
    "request_id": "uuid",               # Trace ID for logs
    "timestamp": "2025-11-16T12:00:00Z", # ISO 8601
    "docs_url": "https://docs.example.com/errors/ERROR_CODE"  # Link to docs
  }
}

Error Code Enumeration:
  VALIDATION_ERROR        - Input validation failed (field specified)
  DUPLICATE_RESOURCE      - Resource with same ID already exists
  RESOURCE_NOT_FOUND      - Requested resource doesn't exist
  RATE_LIMIT_EXCEEDED     - Too many requests (check Retry-After header)
  QUOTA_EXHAUSTED         - Monthly Twitter quota exceeded
  UNAUTHORIZED            - Invalid or missing API key
  FORBIDDEN               - Valid credentials but insufficient permissions
  INVALID_ENDPOINT        - Endpoint contains private IP or invalid URL
  INTERNAL_ERROR          - Unexpected server error (check request_id in logs)
  SERVICE_UNAVAILABLE     - Temporary outage (retry with exponential backoff)

Example Responses:

1. Validation Error:
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "source_id must be lowercase alphanumeric with hyphens only",
    "field": "source_id",
    "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "timestamp": "2025-11-16T12:34:56.789Z",
    "docs_url": "https://docs.example.com/errors/VALIDATION_ERROR"
  }
}

2. Rate Limit:
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 3600

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "API key exceeded 10 source creations per hour limit",
    "request_id": "...",
    "timestamp": "...",
    "docs_url": "..."
  }
}

3. SSRF Prevention:
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": {
    "code": "INVALID_ENDPOINT",
    "message": "Endpoint cannot be a private IP address (169.254.0.0/16 blocked)",
    "field": "endpoint",
    "request_id": "...",
    "timestamp": "...",
    "docs_url": "..."
  }
}

Implementation Notes:
  - ALL Lambda functions must use this schema for errors
  - Log request_id to CloudWatch Logs for tracing
  - Include stack trace in CloudWatch Logs (NOT in response)
  - For 5xx errors, include generic message only (no sensitive details)
```

---

### Gap 2: Metric Dimension Access Control ✅ RESOLVED

**Current State:** ~~SPEC.md mentions "contributor dashboard shows filtered metrics" but WHICH filters not specified~~

**Resolution Status:** ✅ **COMPLETE** - Full metric access control added to SPEC.md lines 753-820

**Risk:** ~~Contributors see competitive intelligence (per-source metrics, quota usage)~~ MITIGATED

**Resolution Implemented:**

```yaml
# Add to SPEC.md - Section: CloudWatch Metrics

Metric Dimension Access Control:

CONTRIBUTOR DASHBOARD (sentiment-analyzer-contributor):
  Access: Read-only via CloudWatch Dashboard URL
  Metrics Allowed:
    - AWS/Lambda/Invocations (aggregate ONLY, no dimensions)
    - AWS/Lambda/Duration (aggregate, P50/P90/P99 statistics only)
    - AWS/Lambda/Errors (aggregate count, no error details)
    - AWS/Lambda/Throttles (aggregate count)
    - AWS/Lambda/ConcurrentExecutions (aggregate)
    - AWS/DynamoDB/ConsumedReadCapacityUnits (aggregate)
    - AWS/DynamoDB/ConsumedWriteCapacityUnits (aggregate)
    - AWS/DynamoDB/UserErrors (aggregate count, no details)

  Metrics DENIED:
    - Any metric with source_id dimension (competitive intelligence)
    - Any metric with api_key_id dimension (usage tracking)
    - Custom metric: twitter.quota_utilization_pct (quota attack vector)
    - Custom metric: scheduler.scan_duration_ms (timing attack)
    - Custom metric: dlq.oldest_message_age_days (reveals incident duration)
    - Custom metric: oauth.refresh_failure_rate (reveals auth issues)
    - Custom metric: dynamodb.throttled_requests (hot partition attack)

  Dashboard Configuration:
    - Fixed time ranges: 1h, 24h, 7d, 30d (no custom queries)
    - No CloudWatch Insights access (prevents dimension filtering)
    - No alarm modification permissions
    - Dashboard updates: Refreshes every 60 seconds (auto)

ADMIN DASHBOARD (sentiment-analyzer-admin):
  Access: Full read/write via IAM admin role
  Metrics Allowed: ALL (no restrictions)
  Capabilities:
    - Filter by all dimensions (source_id, model_version, etc.)
    - Create custom CloudWatch Insights queries
    - Modify alarms and dashboards
    - Export metric data to S3

Enforcement Mechanism:
  1. Two separate CloudWatch Dashboards created via Terraform:
     - sentiment-analyzer-contributor-dashboard (safe metrics only)
     - sentiment-analyzer-admin-dashboard (all metrics)

  2. IAM Policy for Contributors:
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "cloudwatch:GetDashboard",
             "cloudwatch:ListDashboards",
             "cloudwatch:GetMetricData"
           ],
           "Resource": "arn:aws:cloudwatch:us-west-2:ACCOUNT:dashboard/sentiment-analyzer-contributor-dashboard"
         },
         {
           "Effect": "Deny",
           "Action": [
             "cloudwatch:GetDashboard",
             "cloudwatch:GetMetricData"
           ],
           "Resource": "arn:aws:cloudwatch:us-west-2:ACCOUNT:dashboard/sentiment-analyzer-admin-dashboard"
         }
       ]
     }

  3. Dashboard widgets use fixed queries (no user input for dimensions)

Example Contributor Dashboard Widget:
  {
    "type": "metric",
    "properties": {
      "metrics": [
        [ "AWS/Lambda", "Invocations", { "stat": "Sum" } ],
        [ "AWS/Lambda", "Errors", { "stat": "Sum" } ]
      ],
      "title": "Lambda Health (Service-Level - All Sources)",
      "region": "us-west-2",
      "period": 300,
      "yAxis": {
        "left": { "label": "Count" }
      }
    }
  }

Rationale:
  - Per-source metrics reveal competitive intelligence
  - Quota metrics enable denial-of-service planning
  - Timing metrics enable optimization attack vectors
  - Admin needs full visibility for troubleshooting
```

---

## HIGH Priority Gaps (Should Fix - P1)

### Gap 3: API Key Lifecycle Management (UNDERSPECIFIED)

**Current:** "API Gateway API Keys with usage plans" (line 133)

**Missing:**
- Key issuance procedure
- Rotation schedule
- Revocation process

**Resolution:**

```yaml
API Key Lifecycle:

Issuance (Admin Only):
  1. Generate via AWS Console or CLI:
     aws apigateway create-api-key \
       --name "admin-{username}-key" \
       --description "API key for admin user {username}" \
       --enabled

  2. Associate with usage plan:
     aws apigateway create-usage-plan-key \
       --usage-plan-id {plan_id} \
       --key-id {api_key_id} \
       --key-type API_KEY

  3. Securely transmit to admin:
     - Method: Encrypted email or 1Password share
     - Never via Slack/GitHub issues

  4. Admin stores in secure location (password manager)

Rotation Schedule:
  - Frequency: Every 180 days (6 months)
  - Notification: 14 days before expiration
  - Overlap period: 7 days (old + new both valid)
  - Procedure:
    1. Generate new API key
    2. Send to admin user
    3. Admin updates clients to use new key
    4. After 7 days, delete old key

Revocation:
  - On compromise: Immediate deletion
  - On admin offboarding: Delete within 1 hour
  - Command:
    aws apigateway delete-api-key --api-key {key_id}

Usage Plan Limits:
  - Requests: 1,000 per day (burst: 10 per second)
  - Source creation: 10 per hour (enforced in Lambda)
  - Throttling: 429 response with Retry-After header

Monitoring:
  - CloudWatch metric: API key usage per day
  - Alarm: Usage >800 requests/day (approaching limit)
```

---

### Gap 4: Canary Deployment Rollback Thresholds (QUANTIFY)

**Current:** "Rollback if error rate >5%" (line 625) but measurement period not specified

**Resolution:**

```yaml
Canary Deployment Configuration:

Strategy: Linear10PercentEvery1Minute
  - Traffic shift: 10% increments every 1 minute
  - Total duration: 10 minutes (100% traffic)
  - Rollback time: <30 seconds (update alias to previous version)

Rollback Thresholds:

1. Error Rate Threshold:
   Metric: AWS/Lambda/Errors / AWS/Lambda/Invocations
   Threshold: >5%
   Evaluation Period: 5 minutes (rolling window)
   Data Points: 2 consecutive periods above threshold
   Action: Immediate rollback
   Example:
     - Baseline (previous version): 1% error rate
     - Canary (new version): 7% error rate for 10 minutes
     - Result: Rollback triggered after 10 minutes

2. Duration Increase Threshold:
   Metric: AWS/Lambda/Duration (P99 statistic)
   Threshold: >2x baseline P99
   Baseline Calculation: P99 from previous version over last 24 hours
   Evaluation Period: 10 minutes (rolling window)
   Data Points: 2 consecutive periods above threshold
   Action: Immediate rollback
   Example:
     - Baseline P99: 200ms
     - Canary P99: 450ms (2.25x baseline)
     - Result: Rollback triggered

3. DLQ Increase Threshold:
   Metric: AWS/SQS/ApproximateNumberOfMessagesVisible (DLQ)
   Threshold: >50% increase from baseline
   Baseline Calculation: Average DLQ depth over previous 30 minutes
   Evaluation Period: 5 minutes
   Action: Immediate rollback
   Example:
     - Baseline DLQ depth: 2 messages
     - Canary DLQ depth: 4 messages (+100%)
     - Result: Rollback triggered

4. Inference Accuracy Threshold (Custom Metric):
   Metric: sentiment.validation_accuracy
   Threshold: <95%
   Sample: First 100 inferences from canary traffic
   Test Fixtures: Known-good labeled dataset (100 items)
   Evaluation: Compare canary output to expected labels
   Action: Rollback if accuracy <95%
   Example:
     - Test: 100 labeled tweets (40 positive, 40 negative, 20 neutral)
     - Canary results: 92 correct predictions (92%)
     - Result: Rollback triggered (below 95% threshold)

Pre-Traffic Hook (Synthetic Test):
  Lambda: canary-pre-traffic-test
  Purpose: Validate new version before sending traffic
  Tests:
    1. Invoke Lambda with 10 test events
    2. Verify all return HTTP 200
    3. Verify response schema matches expected
    4. Check cold start duration <3 seconds
  Timeout: 60 seconds
  On Failure: Abort deployment (no traffic sent to new version)

Post-Traffic Hook:
  Lambda: canary-post-traffic-test
  Purpose: Final validation after 100% traffic shift
  Tests:
    1. Check CloudWatch alarms (all OK state)
    2. Verify DLQ depth <10 messages
    3. Check error rate over last 15 minutes <2%
  On Failure: Automatic rollback

Monitoring During Deployment:
  - Real-time dashboard showing canary vs baseline metrics
  - Slack notifications on rollback
  - CloudWatch Logs Insights query for canary errors
```

---

## MEDIUM Priority Gaps (Nice to Have - P2)

### Gap 5: FinBERT/DistilBERT Score Normalization Formula (AMBIGUOUS)

**Current:** "score: 0.0-1.0" (line 177)

**Missing:** How is DistilBERT sentiment score normalized?

**Resolution:**

```python
# Add to SPEC.md - Section: Inference Lambda

DistilBERT (FinBERT) Score Normalization:

HuggingFace Transformers Output (distilbert-base-uncased-finetuned-sst-2-english):
  - label: str ("POSITIVE", "NEGATIVE", or "NEUTRAL")
  - score: float (0.0 to 1.0) - confidence probability

  Model returns softmax probabilities for each class:
    - POSITIVE: probability of positive sentiment
    - NEGATIVE: probability of negative sentiment
    - NEUTRAL: probability of neutral sentiment (if 3-class model)

Normalization (Already 0.0-1.0):
  normalized_score = model_output['score']  # No transformation needed

  Examples:
    - DistilBERT output: {"label": "NEGATIVE", "score": 0.95} → Normalized: 0.05 (inverted for negative)
    - DistilBERT output: {"label": "POSITIVE", "score": 0.85} → Normalized: 0.85
    - DistilBERT output: {"label": "NEUTRAL", "score": 0.60} → Normalized: 0.50 (neutral midpoint)

Sentiment Label Determination:
  label = model_output['label'].lower()
  confidence = model_output['score']

  if label == "positive":
      sentiment = "positive"
      score = confidence
  elif label == "negative":
      sentiment = "negative"
      score = 1.0 - confidence  # Invert for consistency
  else:
      sentiment = "neutral"
      score = 0.5  # Neutral midpoint

DynamoDB Storage:
  {
    "sentiment": "positive",  # String enum
    "score": 0.85,            # Normalized float (0.0-1.0)
    "confidence": 0.85,       # Original model confidence (optional, for debugging)
    "model_version": "distilbert-base-uncased-finetuned-sst-2-english-v1.0.0"
  }

Validation:
  - Assert 0.0 <= normalized_score <= 1.0
  - If out of range → Log error, send to DLQ
  - If NaN/Inf → Log error, send to DLQ
```

---

### Gap 6: CloudWatch Log Retention (PER LOG GROUP)

**Current:** "7-year CloudWatch Logs retention for compliance" (line 104)

**Missing:** Does this apply to ALL log groups? (Cost implications)

**Resolution:**

```yaml
CloudWatch Log Retention Policy:

GDPR/Compliance (7 years):
  Log Groups:
    - /aws/api/deletions
      - Reason: GDPR "right to be forgotten" audit trail
      - Retention: 7 years (2,557 days)
      - Cost: ~$5-10/month (low volume)
      - Archive: S3 Glacier after 1 year (optional)

Operational (1 year):
  Log Groups:
    - /aws/lambda/{env}-sentiment-dashboard
      - Reason: API access audit
      - Retention: 1 year (365 days)
      - Cost: ~$20-30/month

Operational (90 days):
  Log Groups:
    - /aws/lambda/{env}-sentiment-ingestion  # Ingestion Lambda (EventBridge-triggered scheduler)
    - /aws/lambda/{env}-sentiment-analysis
    - /aws/lambda/dlq-archival-lambda
      - Reason: Troubleshooting recent issues
      - Retention: 90 days
      - Cost: ~$50-100/month (combined, high volume)
      - Archive: Optional S3 export for long-term storage

Development/Testing (30 days):
  Log Groups:
    - /aws/lambda/canary-pre-traffic-test
    - /aws/lambda/canary-post-traffic-test
      - Reason: Deployment validation only
      - Retention: 30 days
      - Cost: <$5/month

Terraform Configuration:
  resource "aws_cloudwatch_log_group" "deletion_logs" {
    name              = "/aws/api/deletions"
    retention_in_days = 2557  # 7 years
  }

  resource "aws_cloudwatch_log_group" "dashboard_logs" {
    name              = "/aws/lambda/${var.env}-sentiment-dashboard"
    retention_in_days = 365   # 1 year
  }

  resource "aws_cloudwatch_log_group" "analysis_logs" {
    name              = "/aws/lambda/${var.env}-sentiment-analysis"
    retention_in_days = 90    # 90 days
  }

Cost Optimization:
  - Export to S3 after retention period (optional)
  - Use S3 Intelligent-Tiering for long-term archives
  - Estimated total cost: $75-150/month (all log groups)
```

---

## Specification Conflicts to Resolve

### Conflict 1: Ingestion Lambda Concurrency

**Location 1:** Line 199 - "tier-based (10/20/50)"
**Location 2:** Line 332 - "fixed 10"

**Resolution:** Update line 332 to reflect tier-based values

```diff
- {env}-sentiment-ingestion: 256 MB, 60s timeout, concurrency: 10
+ {env}-sentiment-ingestion: 256 MB, 60s timeout, concurrency: tier-based (10/20/50)

Tier Mapping:
  - Free tier: 10 concurrent executions
  - Basic tier: 20 concurrent executions
  - Pro tier: 50 concurrent executions
```

---

### Conflict 2: DynamoDB Migration Trigger

**Location 1:** Line 594 - "After 2-3 months"
**Location 2:** Line 273 - "$500/month threshold"

**Resolution:** Use cost-based trigger (more practical)

```diff
- "After establishing baseline traffic (2-3 months), evaluate migration to provisioned capacity"
+ "When DynamoDB costs exceed $500/month, evaluate migration to provisioned capacity"

Migration Decision Tree:
  If monthly cost > $500:
    1. Analyze CloudWatch metrics:
       - Average RCU/WCU usage
       - Peak RCU/WCU usage (P99)
       - Traffic patterns (hourly, daily)
    2. Calculate provisioned capacity cost:
       - Provisioned cost = (avg_RCU * $0.00013/hour + avg_WCU * $0.00065/hour) * 720 hours
    3. Compare costs:
       - If provisioned < on-demand: Migrate
       - If on-demand < provisioned: Stay on-demand
```

---

### Conflict 3: Ingestion Lambda Scan vs Query

**Location 1:** Line 23 - "Uses Scan"
**Location 2:** Line 387 - "Use Query with GSI"

**Resolution:** Both correct - clarify as phased migration

```diff
- "Scheduler Lambda scans source-configs table"
+ "Scheduler Lambda uses phased approach:
   Phase 1 (0-50 sources): Scan source-configs table
   Phase 2 (50+ sources): Query polling-schedule-index GSI"

Migration Procedure:
  1. Deploy GSI (polling-schedule-index) via Terraform
  2. Monitor CloudWatch metric: scheduler.scan_duration_ms
  3. When scan_duration_ms >10,000ms for 2 consecutive minutes:
     - Deploy Lambda code update (switch Scan → Query)
     - Verify query_duration_ms <1,000ms
     - Remove Scan code path after 1 week validation
```

---

## Summary & Next Steps

**Total Gaps Identified:** 6 (2 CRITICAL, 2 HIGH, 2 MEDIUM)
**Conflicts Resolved:** 3

**Immediate Actions (Before Implementation):**

1. **Define Error Response Schema** (2 hours)
   - Document in SPEC.md
   - Create Pydantic models
   - Update all Lambda functions

2. **Specify Metric Access Control** (4 hours)
   - Create contributor dashboard definition
   - Update IAM policies
   - Document in SPEC.md

**Timeline:** 6 hours (1 day) to resolve all CRITICAL gaps

**Validation:** After fixes, run specification completeness check:
- [ ] All Lambda functions specified
- [ ] All EventBridge rules defined
- [ ] All error scenarios documented
- [ ] All metrics access controlled
- [ ] All retry logic quantified
- [ ] All security boundaries explicit

---

**Document Owner:** @traylorre
**Last Updated:** 2025-11-16
**Status:** Draft (awaiting implementation)
