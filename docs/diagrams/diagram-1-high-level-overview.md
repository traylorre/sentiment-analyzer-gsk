# Diagram 1: High-Level System Overview
**Audience:** Non-technical stakeholders, product managers, executives
**Purpose:** Understand data flow from external sources to storage
**Focus:** External integrations, multiple source types, happy path only

---

## Canvas Layout Specifications

**Canvas Size:** 1920 x 1400 px (landscape)
**Grid:** 100px spacing
**Font:** Inter or Arial (clean, professional)

---

## Component Layout (Left to Right Flow)

### Layer 1: External Sources (Left Side - x: 100-300)

**Component: Twitter API**
- Position: (150, 200)
- Size: 180 x 120 px
- Shape: Rounded rectangle
- Color: `#E3F2FD` (light blue - pastel)
- Icon: Twitter bird (optional)
- Border: 2px solid `#90CAF9`
- Text:
  ```
  Twitter API
  Rate: 450 req/15min
  Quota: Tier-based
  ```

**Component: RSS Feeds (Multiple)**
- Position: (150, 400)
- Size: 180 x 120 px
- Shape: Rounded rectangle
- Color: `#FFF3E0` (light orange - pastel)
- Icon: RSS icon (optional)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  RSS/Atom Feeds
  Size: ≤10 MB
  Format: XML
  ```

**Component: Admin User**
- Position: (150, 600)
- Size: 180 x 120 px
- Shape: Rounded rectangle
- Color: `#F3E5F5` (light purple - pastel)
- Icon: User icon
- Border: 2px solid `#CE93D8`
- Text:
  ```
  Admin User
  API Gateway
  REST API
  ```

**Label (Above all sources):**
- Position: (150, 100)
- Text: **"EXTERNAL SOURCES"**
- Font: Bold, 18px
- Color: `#37474F` (dark gray)

---

### Layer 2: Entry Points (x: 400-600)

**Component: EventBridge Scheduler**
- Position: (450, 200)
- Size: 160 x 100 px
- Shape: Hexagon (or rounded rect)
- Color: `#E8F5E9` (light green - pastel)
- Border: 2px solid `#81C784`
- Text:
  ```
  EventBridge
  Every 60 seconds
  ```

**Arrow: EventBridge → Scheduler Lambda**
- From: (610, 250) → To: (700, 250)
- Style: Solid, 3px, `#81C784`
- Label: "Trigger (1/min)"

**Component: API Gateway**
- Position: (450, 600)
- Size: 160 x 100 px
- Shape: Rounded rectangle
- Color: `#F3E5F5` (light purple)
- Border: 2px solid `#CE93D8`
- Text:
  ```
  API Gateway
  REST API
  API Key Auth
  ```

**Arrow: Admin User → API Gateway**
- From: (330, 660) → To: (450, 660)
- Style: Solid, 2px, `#CE93D8`
- Label: "POST/GET/PATCH/DELETE"

---

### Layer 3: Lambda Functions (x: 700-900)

**Component: Scheduler Lambda**
- Position: (700, 150)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple - pastel)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  scheduler-lambda
  256 MB | 60s timeout
  Concurrency: 1

  • Query source-configs
  • Filter: enabled=true
  • Invoke ingestion
  ```

**Component: Ingestion Lambda (Twitter)**
- Position: (700, 350)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  ingestion-twitter
  256 MB | 60s timeout
  Tier concurrency

  • OAuth refresh
  • Fetch tweets
  • Publish to SNS
  ```

**Component: Ingestion Lambda (RSS)**
- Position: (700, 530)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  ingestion-rss
  256 MB | 60s timeout
  Tier concurrency

  • HTTP GET feed
  • Parse XML
  • Publish to SNS
  ```

**Component: Admin API Lambda**
- Position: (700, 710)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  admin-api-lambda
  256 MB | 30s timeout
  Concurrency: 10

  • CRUD sources
  • Validation
  ```

**Arrow: Scheduler → Ingestion (Twitter)**
- From: (800, 290) → To: (800, 350)
- Style: Solid, 4px (thick), `#9C27B0`
- Label: "Invoke N times\n(N = source count)"

**Arrow: Scheduler → Ingestion (RSS)**
- From: (800, 290) → To: (800, 530)
- Style: Solid, 4px (thick), `#9C27B0`
- Label: "Async invocation"

**Arrow: Twitter API → Ingestion Twitter**
- From: (330, 260) → To: (700, 420)
- Style: Dashed, 2px, `#90CAF9`
- Label: "HTTP GET\n/tweets/search/recent"

**Arrow: RSS Feeds → Ingestion RSS**
- From: (330, 460) → To: (700, 600)
- Style: Dashed, 2px, `#FFB74D`
- Label: "HTTP GET\nfeed.xml"

**Arrow: API Gateway → Admin API Lambda**
- From: (610, 660) → To: (700, 780)
- Style: Solid, 2px, `#CE93D8`
- Label: "Invoke"

---

### Layer 4: Messaging (x: 1000-1200)

**Component: SNS Topics (Group)**
- Position: (1050, 400)
- Size: 180 x 200 px
- Shape: Rounded rectangle
- Color: `#FCE4EC` (light pink - pastel)
- Border: 2px solid `#F48FB1`
- Text:
  ```
  SNS Topics

  ingest-topic-twitter
  ingest-topic-rss

  Fan-out to SQS
  ```

**Component: SQS Queues (Group)**
- Position: (1050, 650)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#FFF9C4` (light yellow - pastel)
- Border: 2px solid `#FFF176`
- Text:
  ```
  SQS Queues

  ingest-queue-twitter
  ingest-queue-rss

  Batch: 10 messages
  ```

**Arrow: Ingestion Twitter → SNS**
- From: (880, 420) → To: (1050, 450)
- Style: Solid, 5px (very thick), `#F48FB1`
- Label: "Publish\n10-100 items/poll"

**Arrow: Ingestion RSS → SNS**
- From: (880, 600) → To: (1050, 550)
- Style: Solid, 5px (very thick), `#F48FB1`
- Label: "Publish\n10-100 items/poll"

**Arrow: SNS → SQS**
- From: (1140, 600) → To: (1140, 650)
- Style: Solid, 4px, `#FFF176`
- Label: "Subscription"

---

### Layer 5: Processing (x: 1300-1500)

**Component: Inference Lambda**
- Position: (1350, 500)
- Size: 180 x 160 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  inference-lambda
  512 MB | 30s timeout
  Concurrency: 20

  • VADER analysis
  • Compute sentiment
  • Write to DynamoDB
  ```

**Arrow: SQS → Inference**
- From: (1230, 720) → To: (1350, 580)
- Style: Solid, 5px (very thick), `#9C27B0`
- Label: "Poll (batch: 10)"

---

### Layer 6: Data Storage (Right Side - x: 1600-1800)

**Component: DynamoDB (source-configs)**
- Position: (1650, 220)
- Size: 200 x 120 px
- Shape: Rounded rectangle with database icon
- Color: `#C8E6C9` (light green - pastel)
- Border: 2px solid `#66BB6A`
- Text:
  ```
  DynamoDB
  source-configs

  PK: source_id
  GSI: polling-schedule-index
  ```

**Component: DynamoDB (sentiment-items)**
- Position: (1650, 520)
- Size: 200 x 120 px
- Shape: Rounded rectangle with database icon
- Color: `#C8E6C9` (light green)
- Border: 2px solid `#66BB6A`
- Text:
  ```
  DynamoDB
  sentiment-items

  PK: source_key
  SK: item_id
  TTL: 90 days
  ```

**Arrow: Scheduler → source-configs (Read)**
- From: (880, 220) → To: (1650, 280)
- Style: Dashed, 2px, `#66BB6A`
- Label: "Query\n(enabled, next_poll_time)"
- Curve: Arc upward

**Arrow: Ingestion → source-configs (Update)**
- From: (880, 420) → To: (1650, 280)
- Style: Dashed, 2px, `#66BB6A`
- Label: "Update\n(next_poll_time, etag)"
- Curve: Arc

**Arrow: Admin API → source-configs (CRUD)**
- From: (880, 780) → To: (1650, 340)
- Style: Solid, 3px, `#66BB6A`
- Label: "CRUD operations"
- Curve: Arc downward

**Arrow: Inference → sentiment-items (Write)**
- From: (1530, 580) → To: (1650, 580)
- Style: Solid, 5px (very thick), `#66BB6A`
- Label: "PutItem\n(conditional)"

---

### Layer 7: Support Services (Bottom - y: 1000-1200)

**Component: Secrets Manager**
- Position: (450, 1050)
- Size: 180 x 100 px
- Shape: Rounded rectangle with lock icon
- Color: `#B2DFDB` (light teal - pastel)
- Border: 2px solid `#4DB6AC`
- Text:
  ```
  Secrets Manager
  OAuth tokens
  API keys
  ```

**Component: CloudWatch**
- Position: (700, 1050)
- Size: 180 x 100 px
- Shape: Rounded rectangle
- Color: `#FFCCBC` (light orange - pastel)
- Border: 2px solid `#FF8A65`
- Text:
  ```
  CloudWatch
  Logs | Metrics | Alarms
  ```

**Component: S3 (DLQ Archive)**
- Position: (950, 1050)
- Size: 180 x 100 px
- Shape: Rounded rectangle
- Color: `#D1C4E9` (light purple - pastel)
- Border: 2px solid `#9575CD`
- Text:
  ```
  S3 Bucket
  DLQ Archives
  90-day retention
  ```

**Arrow: Ingestion Twitter → Secrets Manager**
- From: (790, 490) → To: (540, 1050)
- Style: Dashed, 1px (thin), `#4DB6AC`
- Label: "GetSecret\n(OAuth token)"

**Arrow: All Lambdas → CloudWatch**
- From multiple Lambda boxes → (790, 1050)
- Style: Dashed, 1px (thin), `#FF8A65`
- Label: "Logs & Metrics"

---

## Annotations & Legend

**Legend Box**
- Position: (100, 1050)
- Size: 250 x 100 px
- Background: `#FAFAFA` (light gray)
- Border: 1px solid `#BDBDBD`
- Content:
  ```
  LINE THICKNESS LEGEND:
  ━━━━━ Very thick (5px): High traffic (100-1000 items/min)
  ━━━━  Thick (4px): Medium traffic (1-10 invocations/min)
  ━━━  Medium (3px): Regular traffic
  ━━   Thin (2px): Low traffic
  ━    Very thin (1px): Support/monitoring
  ┅┅┅  Dashed: Read operations
  ━━━  Solid: Write operations
  ```

**Title Box**
- Position: (650, 30)
- Font: Bold, 28px
- Color: `#212121` (dark gray)
- Text: **"Sentiment Analyzer: High-Level System Overview"**

**Subtitle**
- Position: (650, 70)
- Font: Regular, 14px
- Color: `#757575` (medium gray)
- Text: "Event-driven serverless architecture for Twitter & RSS sentiment analysis"

---

## Color Palette Summary

**Pastel Colors (Low Saturation):**
- External Sources: `#E3F2FD` (light blue), `#FFF3E0` (light orange), `#F3E5F5` (light purple)
- Lambdas: `#E1BEE7` (light purple)
- Messaging: `#FCE4EC` (light pink), `#FFF9C4` (light yellow)
- Databases: `#C8E6C9` (light green)
- Support: `#B2DFDB` (light teal), `#FFCCBC` (light orange), `#D1C4E9` (light purple)

**Border Colors (Slightly darker than fills):**
- Maintain visual hierarchy without over-saturation
- All borders 2px except very thin annotation lines (1px)

---

## Export Settings

**Format:** PNG (high resolution)
**Resolution:** 300 DPI (for printing)
**File Name:** `sentiment-analyzer-high-level-overview.png`

---

## Notes for Canva Creation

1. **Start with grid layout** - Use Canva's grid feature (100px spacing)
2. **Create component templates** - Make one rounded rectangle, duplicate for all components
3. **Group related items** - Group each Lambda with its connecting arrows
4. **Use smart guides** - Align components horizontally by layer
5. **Lock background elements** - Prevent accidental movement
6. **Test readability** - Zoom to 50% to ensure text is readable at poster size

---

## Variations to Create

After main diagram, create these variants (save as separate Canva pages):

1. **Simplified Version** - Remove support services, show only main flow
2. **Twitter Flow Only** - Highlight Twitter path, gray out RSS
3. **RSS Flow Only** - Highlight RSS path, gray out Twitter
4. **Admin API Focus** - Highlight admin operations, gray out ingestion

Keep all in same Canva project for easy switching.
