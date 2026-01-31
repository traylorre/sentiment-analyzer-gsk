# Diagram 2: Security Flow & Trust Boundaries
**Audience:** Security engineers, developers, architects
**Purpose:** Understand data sanitization, error handling, retry logic
**Focus:** Trust zones, tainted data flow, failure paths, DLQs

---

## Canvas Layout Specifications

**Canvas Size:** 2200 x 1600 px (wide landscape for detailed view)
**Grid:** 100px spacing
**Font:** JetBrains Mono or Courier (monospace for technical audience)

---

## Trust Zone Color Coding

**Zone 1: UNTRUSTED (Red Zone)**
- Background: `#FFEBEE` (very light red - pastel)
- Border: 3px solid `#EF5350` (red)
- Components: External APIs, HTTP requests

**Zone 2: VALIDATION (Orange Zone)**
- Background: `#FFF3E0` (very light orange - pastel)
- Border: 3px solid `#FF9800` (orange)
- Components: Ingestion Lambdas, API Gateway

**Zone 3: PROCESSING (Yellow Zone)**
- Background: `#FFFDE7` (very light yellow - pastel)
- Border: 3px solid `#FDD835` (yellow)
- Components: Analysis Lambda, SNS/SQS

**Zone 4: PROTECTED (Green Zone)**
- Background: `#E8F5E9` (very light green - pastel)
- Border: 3px solid `#66BB6A` (green)
- Components: DynamoDB (parameterized writes only)

**Zone 5: INFRASTRUCTURE (Blue Zone)**
- Background: `#E3F2FD` (very light blue - pastel)
- Border: 3px solid `#42A5F5` (blue)
- Components: Secrets Manager, CloudWatch, S3

---

## Layout (Top to Bottom Flow)

### Header Section (y: 0-150)

**Title**
- Position: (1100, 40)
- Font: Bold, 32px
- Color: `#212121`
- Text: **"Security Flow & Trust Boundaries"**

**Subtitle**
- Position: (1100, 85)
- Font: Regular, 16px
- Color: `#757575`
- Text: "Data sanitization, validation checkpoints, and error handling paths"

**Trust Zone Legend**
- Position: (100, 50)
- Size: 400 x 80 px
- Background: White
- Border: 1px solid `#BDBDBD`
- Content:
  ```
  TRUST ZONES:
  🔴 RED: Untrusted input (internet)
  🟠 ORANGE: Validation layer
  🟡 YELLOW: Processing layer
  🟢 GREEN: Protected data store
  🔵 BLUE: Infrastructure services
  ```

---

### Zone 1: UNTRUSTED INPUT (y: 200-450)

**Zone Container**
- Position: (100, 200)
- Size: 2000 x 250 px
- Background: `#FFEBEE` (light red pastel)
- Border: 3px solid `#EF5350`
- Label: **"ZONE 1: UNTRUSTED (Internet Input)"**

**Component: Tiingo API Response**
- Position: (200, 250)
- Size: 280 x 160 px
- Shape: Rounded rectangle
- Color: `#FFCDD2` (light red)
- Border: 2px solid `#E57373`
- Text:
  ```
  Tiingo API Response

  TAINTED FIELDS:
  • ticker (symbol validation)
  • adjClose (numeric validation)
  • adjVolume (numeric validation)

  THREATS:
  ⚠ Injection: Malformed ticker symbols
  ⚠ Type confusion: String vs numeric
  ⚠ Oversized: Up to 2 MB
  ```

**Component: Finnhub API Response**
- Position: (550, 250)
- Size: 280 x 160 px
- Shape: Rounded rectangle
- Color: `#FFCDD2` (light red)
- Border: 2px solid `#E57373`
- Text:
  ```
  Finnhub API Response

  TAINTED FIELDS:
  • symbol (ticker validation)
  • headline (user content)
  • summary (SSRF risk in URLs)

  THREATS:
  ⚠ XSS: <script>alert()</script>
  ⚠ Malicious URLs in content
  ⚠ Oversized: Up to 5 MB
  ```

**Component: API Key Validation**
- Position: (900, 250)
- Size: 280 x 160 px
- Shape: Rounded rectangle
- Color: `#FFCDD2` (light red)
- Border: 2px solid `#E57373`
- Text:
  ```
  API Key Response

  TAINTED FIELDS:
  • api_key (from Secrets Manager)
  • rate_limit_remaining
  • rate_limit_reset

  THREATS:
  ⚠ Key exposure in logs
  ⚠ Rate limit manipulation
  ⚠ Invalid/expired keys
  ```

**Component: Dashboard Request**
- Position: (1250, 250)
- Size: 280 x 160 px
- Shape: Rounded rectangle
- Color: `#FFCDD2` (light red)
- Border: 2px solid `#E57373`
- Text:
  ```
  Dashboard API Request

  TAINTED FIELDS:
  • ticker (query param)
  • date_range (validation)
  • sort_order (enum)

  THREATS:
  ⚠ NoSQL Injection: {"$ne": null}
  ⚠ Parameter tampering
  ⚠ Unauthorized access
  ```

---

### Zone 2: VALIDATION LAYER (y: 500-850)

**Zone Container**
- Position: (100, 500)
- Size: 2000 x 350 px
- Border: 3px solid `#FF9800`
- Background: `#FFF3E0` (light orange pastel)
- Label: **"ZONE 2: VALIDATION & SANITIZATION"**

**Validation Checkpoint 1: Ingestion Lambda (Tiingo)**
- Position: (200, 560)
- Size: 320 x 260 px
- Color: `#FFE0B2` (light orange)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  ingestion-lambda-tiingo

  ✓ VALIDATIONS:
  1. Size check: response <2 MB
  2. JSON parsing (strict mode)
  3. Schema validation
  4. API key header validation
  5. Rate limit header check

  ✗ NO SANITIZATION YET
  → Raw data preserved

  ERRORS → DLQ:
  • ValidationError
  • SizeExceededError
  • RateLimitError (429)

  RETRY LOGIC:
  • Max retries: 2
  • Backoff: 1s, 2s, 4s
  • DLQ after 3 failures
  ```

**Validation Checkpoint 2: Ingestion Lambda (Finnhub)**
- Position: (580, 560)
- Size: 320 x 260 px
- Color: `#FFE0B2` (light orange)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  ingestion-lambda-finnhub

  ✓ VALIDATIONS:
  1. Size check: response <5 MB
  2. JSON parsing (strict mode)
  3. Schema validation
  4. API key header validation
  5. URL sanitization

  ✗ NO SANITIZATION YET
  → Raw content preserved

  ERRORS → DLQ:
  • JSONDecodeError
  • SizeExceededError
  • HTTPError (401, 429, 5xx)

  RETRY LOGIC:
  • Max retries: 2
  • Backoff: exponential
  • DLQ after 3 failures
  ```

**Validation Checkpoint 3: Dashboard Lambda**
- Position: (960, 560)
- Size: 320 x 260 px
- Color: `#FFE0B2` (light orange)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  dashboard-lambda

  ✓ VALIDATIONS:
  1. API Gateway request validation
  2. Pydantic schema validation
  3. Regex: ticker ^[A-Z]{1,5}$
  4. Date range bounds check
  5. Pagination limits

  ✓ SANITIZATION:
  → Parameterized DynamoDB queries
  → HTML entity encoding

  ERRORS → HTTP:
  • 400 Bad Request (validation)
  • 401 Unauthorized
  • 429 Too Many Requests
  ```

**Validation Checkpoint 4: API Key Validation**
- Position: (1340, 560)
- Size: 320 x 260 px
- Color: `#FFE0B2` (light orange)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  API Key Validation

  ✓ VALIDATIONS:
  1. Key presence check
  2. Key format validation
  3. Length validation
  4. Response schema check

  CACHE STRATEGY:
  • /tmp cache (5-min TTL)
  • Refresh jitter: 0-300s

  CIRCUIT BREAKER:
  • Threshold: 3 failures
  • Timeout: 30s
  • Fallback: Cache only

  ERRORS:
  • InvalidApiKey → Disable source
  • ThrottlingException → Circuit open
  ```

**Arrow: Zone 1 → Zone 2 (Data Flow)**
- From: Bottom of Tiingo API (340, 410) → Top of Ingestion Tiingo (340, 560)
- Style: Solid, 4px, `#EF5350` → `#FF9800` gradient
- Label: "HTTP Response\n(TAINTED)"
- Annotation: "⚠ Untrusted data enters system"

---

### Zone 3: PROCESSING LAYER (y: 900-1250)

**Zone Container**
- Position: (100, 900)
- Size: 2000 x 350 px
- Border: 3px solid `#FDD835`
- Background: `#FFFDE7` (light yellow pastel)
- Label: **"ZONE 3: PROCESSING (Still Tainted)"**

**Component: SNS/SQS Queue**
- Position: (200, 960)
- Size: 380 x 260 px
- Color: `#FFF9C4` (light yellow)
- Border: 2px solid `#FFF176`
- Text:
  ```
  SNS → SQS Pipeline

  TAINTED DATA:
  • Raw text still present
  • No transformation
  • No sanitization

  BUFFERING:
  • Batch size: 10 messages
  • Visibility timeout: 60s
  • maxReceiveCount: 3

  RETRY BEHAVIOR:
  • Failed message → Back to queue
  • 3 failures → DLQ
  • ReportBatchItemFailures: ON

  DLQ: ingestion-lambda-dlq
  • Retention: 14 days
  • Archive trigger: >10 days old
  ```

**Component: Analysis Lambda**
- Position: (640, 960)
- Size: 420 x 260 px
- Color: `#FFF59D` (light yellow)
- Border: 2px solid `#FFEB3B`
- Text:
  ```
  analysis-lambda

  PROCESSING:
  1. Extract text (STILL TAINTED)
  2. DistilBERT sentiment analysis
     → Text-only, NO code execution
  3. Compute SHA-256 hash
     → Hash = item_id (safe)
  4. Normalize score (-1 to +1 → 0 to 1)

  ✓ PARTIAL SANITIZATION:
  • item_id: SHA-256 hash (safe)
  • sentiment: Enum (positive|neutral|negative)
  • score: Float 0.0-1.0

  ✗ STILL TAINTED:
  • text field: Raw content preserved

  IDEMPOTENCY:
  • DynamoDB conditional write
  • attribute_not_exists(source_key, item_id)
  • Duplicate → Treated as success

  ERRORS → DLQ:
  • ValidationError (invalid score)
  • DynamoDBError (throttling)
  • Max retries: 3
  ```

**Component: Notification Lambda**
- Position: (1120, 960)
- Size: 380 x 130 px
- Color: `#FFF59D` (light yellow)
- Border: 2px solid `#FFEB3B`
- Text:
  ```
  notification-lambda

  SECURITY:
  • SendGrid API key from Secrets Manager
  • Email template validation
  • Recipient allowlist

  THREATS:
  • Email injection prevention
  • Rate limiting per recipient
  ```

**Component: SSE-Streaming Lambda**
- Position: (1120, 1100)
- Size: 380 x 130 px
- Color: `#FFF59D` (light yellow)
- Border: 2px solid `#FFEB3B`
- Text:
  ```
  sse-streaming-lambda

  SECURITY:
  • WebSocket connection validation
  • Connection timeout: 5 min
  • Message size limit: 32 KB

  THREATS:
  • Connection exhaustion prevention
  • Reserved concurrency limit
  ```

**Component: DLQ Processing**
- Position: (1560, 960)
- Size: 380 x 260 px
- Color: `#FFCCBC` (light red-orange)
- Border: 2px solid `#FF8A65`
- Text:
  ```
  Dead Letter Queue (DLQ)

  2 DLQs:
  • ingestion-lambda-dlq
  • analysis-lambda-dlq

  FAILURE SCENARIOS:
  1. Validation errors
  2. Timeout (>60s)
  3. DynamoDB throttling
  4. Malformed events

  DLQ ARCHIVAL:
  • Trigger: Message age >10 days
  • Destination: S3 bucket
  • Retention: 90 days
  • Format: JSON with metadata

  ⚠ CRITICAL ALARM:
  • DLQ depth >10 messages
  • Oldest message >7 days
  ```

**Arrow: SQS → Analysis**
- From: (580, 1090) → To: (640, 1090)
- Style: Solid, 5px (very thick), `#FFEB3B`
- Label: "Poll (batch: 10)\nHigh traffic"

**Arrow: Analysis → DLQ (Error Path)**
- From: (850, 1220) → To: (1560, 1150)
- Style: Dashed, 3px, `#FF5722` (red-orange)
- Label: "FAILURE\n(after 3 retries)"
- Annotation: "⚠ Error path"

---

### Zone 4: PROTECTED DATA STORE (y: 1300-1550)

**Zone Container**
- Position: (100, 1300)
- Size: 2000 x 250 px
- Border: 3px solid `#66BB6A`
- Background: `#E8F5E9` (light green pastel)
- Label: **"ZONE 4: PROTECTED (Parameterized Writes Only)"**

**Component: DynamoDB Write Operation**
- Position: (300, 1360)
- Size: 500 x 160 px
- Color: `#C8E6C9` (light green)
- Border: 2px solid `#81C784`
- Text:
  ```
  DynamoDB.PutItem (sentiment-items)

  ✓ PARAMETERIZED (NoSQL Injection Protected):
  {
    'source_key': {'S': 'tiingo#AAPL'},           ← Safe (controlled)
    'item_id': {'S': 'e3b0c44...'},               ← Safe (SHA-256 hash)
    'text': {'S': '<script>alert()</script>'},   ← TAINTED but safe
    'sentiment': {'S': 'neutral'},                ← Safe (enum)
    'score': {'N': '0.5'}                         ← Safe (float)
  }

  ConditionExpression:
  'attribute_not_exists(source_key) AND attribute_not_exists(item_id)'

  ✓ NO CODE EXECUTION POSSIBLE
  ✓ XSS only risk if text displayed in web UI
  ✓ All expressions use ExpressionAttributeValues
  ```

**Component: Security Guarantees**
- Position: (860, 1360)
- Size: 500 x 160 px
- Color: `#A5D6A7` (green)
- Border: 2px solid `#66BB6A`
- Text:
  ```
  SECURITY GUARANTEES:

  ✅ No SQL injection (DynamoDB NoSQL)
  ✅ No NoSQL injection (parameterized expressions)
  ✅ No code execution (strings stored as-is)
  ✅ No SSRF (URL validation + allowlist)
  ✅ API keys secured in Secrets Manager

  ⚠ RESIDUAL RISKS:
  • XSS if text displayed in web UI without escaping
  • Log injection (text written to CloudWatch Logs)

  MITIGATION:
  • Frontend must escape HTML entities
  • CloudWatch filters control characters
  ```

**Arrow: Analysis → DynamoDB**
- From: (850, 1220) → To: (550, 1360)
- Style: Solid, 5px (very thick), `#66BB6A`
- Label: "PutItem\n(conditional)\n100-1000 writes/min"

---

### Zone 5: INFRASTRUCTURE (Right Side - x: 1400-2100, y: 1300-1550)

**Zone Container (Vertical)**
- Position: (1400, 200)
- Size: 680 x 1350 px
- Border: 3px solid `#42A5F5`
- Background: `#E3F2FD` (light blue pastel)
- Label: **"ZONE 5: INFRASTRUCTURE"**

**Component: Secrets Manager**
- Position: (1450, 280)
- Size: 280 x 160 px
- Color: `#BBDEFB` (light blue)
- Border: 2px solid `#64B5F6`
- Text:
  ```
  Secrets Manager

  STORED SECRETS:
  • Tiingo API key
  • Finnhub API key
  • SendGrid API key
  • Database credentials

  CACHING STRATEGY:
  • /tmp cache (5-min TTL)
  • Reduces API calls

  CIRCUIT BREAKER:
  • ThrottlingException → Open
  • Fallback: Cache only
  • Timeout: 30s

  THROTTLE LIMITS:
  • 5,000 reads/day
  • 1,000 updates/day
  ```

**Component: CloudWatch**
- Position: (1780, 280)
- Size: 280 x 160 px
- Color: `#BBDEFB` (light blue)
- Border: 2px solid `#64B5F6`
- Text:
  ```
  CloudWatch

  LOGS:
  • Retention: 7 years
  • Secret filtering: Automatic
  • Structure: JSON

  METRICS:
  • Custom metrics (per-source)
  • StuckItems (from Metrics Lambda)
  • Access control (contributor vs admin)

  ALARMS:
  • DLQ depth >10
  • StuckItems >0 for 10 min
  • API key failures >5%
  • Scheduler timeout
  • Quota >80%
  ```

**Component: Metrics Lambda (Operational Monitor)**
- Position: (1780, 480)
- Size: 280 x 160 px
- Color: `#BBDEFB` (light blue)
- Border: 2px solid `#64B5F6`
- Text:
  ```
  metrics-lambda

  SECURITY NOTES:
  • No external input (internal only)
  • Read-only DynamoDB access
  • Query by_status GSI only
  • No secrets required

  OPERATIONS:
  • Trigger: EventBridge (1/min)
  • Query: pending items >5 min old
  • Output: CloudWatch StuckItems metric

  MINIMAL PERMISSIONS:
  • dynamodb:Query (GSI only)
  • cloudwatch:PutMetricData
  ```

**Component: S3 (DLQ Archive)**
- Position: (1450, 480)
- Size: 280 x 160 px
- Color: `#BBDEFB` (light blue)
- Border: 2px solid `#64B5F6`
- Text:
  ```
  S3: DLQ Archive

  ARCHIVAL TRIGGER:
  • DLQ message age >10 days
  • Prevents 14-day data loss

  LOCATION:
  s3://dlq-archive/
    {dlq-name}/
    {year}/{month}/{day}/
    {message-id}.json

  RETENTION: 90 days

  STORAGE CLASS:
  • Glacier Instant Retrieval
  ```

**Component: Retry Logic Summary**
- Position: (1780, 480)
- Size: 280 x 320 px
- Color: `#C5CAE9` (light indigo)
- Border: 2px solid `#7986CB`
- Text:
  ```
  RETRY LOGIC SUMMARY

  LAMBDA ASYNC:
  • Max retries: 2
  • Max age: 3600s (1 hour)
  • DLQ after retries exhausted

  SQS EVENT SOURCE:
  • maxReceiveCount: 3
  • Visibility timeout: 60s
  • ReportBatchItemFailures: ON

  TIINGO/FINNHUB API:
  • 429 Rate Limit:
    - Wait for X-RateLimit-Reset
    - Max wait: 15 minutes
  • 5xx Server Error:
    - Exponential backoff: 1s, 2s, 4s
    - Max retries: 3

  API KEY REFRESH:
  • Retries: 3
  • Backoff: 1s, 2s, 4s
  • 401 Invalid Key → Disable source

  SECRETS MANAGER:
  • Circuit breaker: 3 failures
  • Fallback: Cache only
  • Timeout: 30s
  ```

**Component: Error Response Schema**
- Position: (1450, 680)
- Size: 580 x 200 px
- Color: `#FFCCBC` (light orange)
- Border: 2px solid `#FF8A65`
- Text:
  ```
  STANDARDIZED ERROR RESPONSE

  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "ticker must be uppercase alphanumeric",
      "field": "ticker",
      "request_id": "uuid",
      "timestamp": "2025-11-16T12:00:00Z",
      "docs_url": "https://docs.example.com/errors/VALIDATION_ERROR"
    }
  }

  ERROR CODES:
  • VALIDATION_ERROR - Input validation failed
  • DUPLICATE_RESOURCE - Resource already exists
  • RATE_LIMIT_EXCEEDED - Too many requests
  • QUOTA_EXHAUSTED - Monthly quota exceeded
  • UNAUTHORIZED - Invalid API key
  • INTERNAL_ERROR - Unexpected server error
  ```

**Component: Cascading Failure Prevention**
- Position: (1450, 920)
- Size: 580 x 280 px
- Color: `#FFCCBC` (light red-orange)
- Border: 2px solid `#FF7043`
- Text:
  ```
  CASCADING FAILURE PREVENTION

  SCENARIO 1: Tiingo/Finnhub API Outage
  ✓ MITIGATION:
  • Rate smoothing (prevent burst after recovery)
  • Circuit breaker (stop requests during outage)
  • Quota tracking (cap retry attempts)

  SCENARIO 2: Secrets Manager Throttling
  ✓ MITIGATION:
  • API key caching (/tmp, 5-min TTL)
  • Refresh jitter (0-300s random delay)
  • Circuit breaker (fallback to cache)

  SCENARIO 3: DynamoDB Hot Partition
  ✓ MITIGATION:
  • Time-based sort key suffix
  • On-demand capacity (auto-scaling)
  • Conditional writes (idempotency)

  SCENARIO 4: Lambda Timeout Cascade
  ✓ MITIGATION:
  • Reserved concurrency limits
  • DLQ for failed events
  • Scheduler GSI migration (reduce scan time)
  ```

**Component: Data Loss Prevention**
- Position: (1450, 1240)
- Size: 580 x 280 px
- Color: `#C8E6C9` (light green)
- Border: 2px solid `#66BB6A`
- Text:
  ```
  DATA LOSS PREVENTION

  PROTECTION 1: DLQ Archival
  • Messages >10 days → S3
  • Prevents 14-day SQS expiry
  • Retention: 90 days

  PROTECTION 2: DynamoDB Backups
  • PITR: Restore to any point (35 days)
  • AWS Backup: Daily snapshots (30 days)
  • Cross-region replication: Optional

  PROTECTION 3: Idempotent Operations
  • Conditional DynamoDB writes
  • Duplicate detection (SHA-256 hash)
  • Safe to retry all operations

  PROTECTION 4: CloudWatch Logs
  • 7-year retention (compliance)
  • Archive to S3 Glacier (optional)
  • Deletion logs: Separate 7-year retention

  ⚠ UNMITIGATED RISKS:
  • EventBridge rule disabled >1 day → Missed polls
  • Regional AWS outage → 4-12 hour data gap
  ```

---

## Error Path Annotations

**Annotation 1: Lambda Timeout Path**
- Position: (850, 820)
- Arrow: From Ingestion Lambda → DLQ
- Style: Dashed, 3px, `#FF5722` (red)
- Label: "TIMEOUT\n(>60s)"
- Icon: ⚠ warning triangle

**Annotation 2: Validation Failure Path**
- Position: (550, 820)
- Arrow: From Ingestion Lambda → DLQ
- Style: Dashed, 3px, `#FF5722` (red)
- Label: "VALIDATION FAILED\n(malformed JSON)"

**Annotation 3: DynamoDB Throttling Path**
- Position: (1060, 1220)
- Arrow: From Analysis Lambda → DLQ
- Style: Dashed, 3px, `#FF5722` (red)
- Label: "THROTTLING\n(ProvisionedThroughputExceeded)"

**Annotation 4: Circuit Breaker Open**
- Position: (1340, 820)
- Arrow: From API Key component → CloudWatch alarm
- Style: Dashed, 2px, `#FF9800` (orange)
- Label: "CIRCUIT OPEN\n(3 failures)"

---

## Legend & Annotations (Bottom Right)

**Retry Logic Legend**
- Position: (100, 1600)
- Size: 600 x 100 px
- Background: `#FAFAFA`
- Border: 1px solid `#BDBDBD`
- Content:
  ```
  RETRY BEHAVIOR LEGEND:
  ━━━━━ Solid line: Happy path (normal flow)
  ┅┅┅┅┅ Dashed line: Error path (retry/failure)
  ━━━━━ Very thick (5px): High traffic (100-1000/min)
  ━━━  Medium (3px): Error paths
  ━━   Thin (2px): Support operations
  ```

**Trust Zone Summary**
- Position: (750, 1600)
- Size: 700 x 100 px
- Background: `#FAFAFA`
- Border: 1px solid `#BDBDBD`
- Content:
  ```
  TRUST ZONE TRANSITIONS:
  RED (untrusted) → ORANGE (validation) → YELLOW (processing) → GREEN (protected)

  SANITIZATION CHECKPOINTS:
  1. Size limits (2 MB / 5 MB)
  2. Schema validation (JSON parsing)
  3. API key validation + rate limit tracking
  4. Parameterized DynamoDB writes (NoSQL injection prevention)
  ```

**Watermark**
- Position: (1500, 1600)
- Size: 500 x 80 px
- Font: Regular, 12px, `#BDBDBD`
- Text:
  ```
  Generated: 2025-11-16
  Project: sentiment-analyzer-gsk
  Focus: Security flow & trust boundaries
  Audience: Security engineers, developers
  ```

---

## Export Settings

**Format:** PNG (high resolution)
**Resolution:** 300 DPI
**File Name:** `sentiment-analyzer-security-flow.png`

---

## Notes for Canva Creation

1. **Create trust zones first** - Draw background rectangles with pastel colors
2. **Add components layer by layer** - Follow top-to-bottom flow
3. **Use consistent spacing** - 40px padding inside zone containers
4. **Error paths use dashed lines** - Make them visually distinct
5. **Add warning icons** - Use ⚠ symbol for error annotations
6. **Test color contrast** - Ensure text readable on pastel backgrounds
7. **Group related items** - Lock zone containers to prevent movement

---

## Future Diagram Variations

Keep in same Canva project for reuse:

1. **API Key Flow Deep Dive** - Just API key refresh + Secrets Manager + circuit breaker
2. **DLQ Processing Flow** - SQS → DLQ → S3 archival → Reprocessing
3. **Retry Logic Diagram** - All retry patterns in one view
4. **Cascading Failure Scenarios** - Show 4 failure scenarios side-by-side
