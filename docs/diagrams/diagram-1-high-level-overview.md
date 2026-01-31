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

**Component: Tiingo API**
- Position: (150, 200)
- Size: 180 x 120 px
- Shape: Rounded rectangle
- Color: `#E3F2FD` (light blue - pastel)
- Icon: Chart/stock icon (optional)
- Border: 2px solid `#90CAF9`
- Text:
  ```
  Tiingo API
  Financial market data
  REST API | API Key Auth
  ```

**Component: Finnhub API**
- Position: (150, 400)
- Size: 180 x 120 px
- Shape: Rounded rectangle
- Color: `#FFF3E0` (light orange - pastel)
- Icon: News/finance icon (optional)
- Border: 2px solid `#FFB74D`
- Text:
  ```
  Finnhub API
  Stock quotes & news
  REST API | API Key Auth
  ```

**Label (Above all sources):**
- Position: (150, 100)
- Text: **"EXTERNAL SOURCES"**
- Font: Bold, 18px
- Color: `#37474F` (dark gray)

---

### Layer 2: Entry Points (x: 400-600)

**Component: EventBridge Scheduler (Ingestion)**
- Position: (450, 200)
- Size: 160 x 100 px
- Shape: Hexagon (or rounded rect)
- Color: `#E8F5E9` (light green - pastel)
- Border: 2px solid `#81C784`
- Text:
  ```
  EventBridge
  Every 5 minutes
  ```

**Arrow: EventBridge → Ingestion Lambda**
- From: (610, 250) → To: (700, 350)
- Style: Solid, 3px, `#81C784`
- Label: "Trigger (5min)"

**Component: API Gateway (Dashboard)**
- Position: (450, 500)
- Size: 160 x 100 px
- Shape: Rounded rectangle
- Color: `#F3E5F5` (light purple)
- Border: 2px solid `#CE93D8`
- Text:
  ```
  API Gateway
  REST API
  Dashboard endpoints
  ```

**Arrow: API Gateway → Dashboard Lambda**
- From: (610, 550) → To: (700, 550)
- Style: Solid, 2px, `#CE93D8`
- Label: "HTTP requests"

---

### Layer 3: Lambda Functions (x: 700-900)

**Component: Ingestion Lambda**
- Position: (700, 200)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  ingestion-lambda
  256 MB | 60s timeout

  • Fetch Tiingo/Finnhub
  • Write to DynamoDB
  • Publish to SNS
  ```

**Component: Analysis Lambda**
- Position: (700, 380)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  analysis-lambda
  512 MB | 30s timeout
  Concurrency: 20

  • SNS trigger
  • DistilBERT analysis
  • Write to DynamoDB
  ```

**Component: Dashboard Lambda**
- Position: (700, 560)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  dashboard-lambda
  256 MB | 30s timeout

  • FastAPI/Mangum
  • API Gateway trigger
  • Query DynamoDB
  ```

**Component: SSE-Streaming Lambda**
- Position: (700, 740)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  sse-streaming-lambda
  256 MB | 900s timeout

  • Function URL
  • Server-Sent Events
  • Real-time updates
  ```

**Component: Notification Lambda**
- Position: (950, 740)
- Size: 180 x 140 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  notification-lambda
  128 MB | 30s timeout

  • SNS/EventBridge trigger
  • SendGrid integration
  • Alert delivery
  ```

**Arrow: Tiingo API → Ingestion Lambda**
- From: (330, 260) → To: (700, 270)
- Style: Dashed, 2px, `#90CAF9`
- Label: "HTTP GET\n/tiingo/daily"

**Arrow: Finnhub API → Ingestion Lambda**
- From: (330, 460) → To: (700, 270)
- Style: Dashed, 2px, `#FFB74D`
- Label: "HTTP GET\n/quote, /news"

**Arrow: API Gateway → Dashboard Lambda**
- From: (610, 550) → To: (700, 630)
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

  sentiment-ingestion-topic
  sentiment-alerts-topic

  Fan-out to Analysis Lambda
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

  sentiment-analysis-queue
  sentiment-dlq

  Batch: 10 messages
  ```

**Arrow: Ingestion Lambda → SNS**
- From: (880, 270) → To: (1050, 450)
- Style: Solid, 5px (very thick), `#F48FB1`
- Label: "Publish\n10-100 items/poll"

**Arrow: SNS → Analysis Lambda**
- From: (1050, 400) → To: (880, 450)
- Style: Solid, 4px, `#F48FB1`
- Label: "Trigger"

**Arrow: SNS → SQS**
- From: (1140, 600) → To: (1140, 650)
- Style: Solid, 4px, `#FFF176`
- Label: "Subscription"

---

### Layer 5: Processing (x: 1300-1500)

**Component: Metrics Lambda**
- Position: (1350, 500)
- Size: 180 x 160 px
- Shape: Rounded rectangle
- Color: `#E1BEE7` (light purple)
- Border: 2px solid `#9C27B0`
- Text:
  ```
  metrics-lambda
  128 MB | 30s timeout
  Concurrency: 1

  • EventBridge 1min trigger
  • Query DynamoDB
  • Emit CloudWatch metrics
  ```

**Arrow: EventBridge → Metrics Lambda**
- From: (1210, 550) → To: (1350, 550)
- Style: Solid, 3px, `#81C784`
- Label: "Trigger (1/min)"

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

**Arrow: Dashboard Lambda → source-configs (Read)**
- From: (880, 630) → To: (1650, 340)
- Style: Dashed, 2px, `#66BB6A`
- Label: "Query operations"
- Curve: Arc downward

**Arrow: Analysis Lambda → sentiment-items (Write)**
- From: (880, 450) → To: (1650, 580)
- Style: Solid, 5px (very thick), `#66BB6A`
- Label: "PutItem\n(conditional)"

---

### Layer 6b: Operational Monitoring (x: 1300-1500, y: 800-1000)

**Component: EventBridge Metrics Scheduler**
- Position: (1050, 850)
- Size: 160 x 100 px
- Shape: Hexagon (or rounded rect)
- Color: `#E8F5E9` (light green - pastel)
- Border: 2px solid `#81C784`
- Text:
  ```
  EventBridge
  Every 1 minute
  ```

**Arrow: Metrics Lambda → DynamoDB**
- From: (1530, 580) → To: (1650, 580)
- Style: Dashed, 2px, `#66BB6A`
- Label: "Query\n(by_status GSI)"
- Curve: Arc

**Arrow: Metrics Lambda → CloudWatch**
- From: (1440, 660) → To: (790, 1050)
- Style: Solid, 3px, `#FF8A65`
- Label: "PutMetricData\n(StuckItems)"

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
  Tiingo API key
  Finnhub API key
  SendGrid API key
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

**Arrow: Ingestion Lambda → Secrets Manager**
- From: (790, 340) → To: (540, 1050)
- Style: Dashed, 1px (thin), `#4DB6AC`
- Label: "GetSecret\n(API keys)"

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
- Text: "Event-driven serverless architecture for Tiingo & Finnhub financial sentiment analysis"

---

## Color Palette Summary

**Pastel Colors (Low Saturation):**
- External Sources: `#E3F2FD` (light blue - Tiingo), `#FFF3E0` (light orange - Finnhub)
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
2. **Tiingo Flow Only** - Highlight Tiingo market data path, gray out Finnhub
3. **Finnhub Flow Only** - Highlight Finnhub news/quotes path, gray out Tiingo
4. **Dashboard/SSE Focus** - Highlight real-time dashboard and SSE streaming paths

Keep all in same Canva project for easy switching.
