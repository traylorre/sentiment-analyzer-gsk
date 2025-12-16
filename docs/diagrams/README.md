# Sentiment Analyzer - System Diagrams

This directory contains comprehensive system architecture diagrams for the Sentiment Analyzer project.

---

## Available Diagrams

### 0. Use Case Sequence Diagrams (NEW)
**File:** `../USE-CASE-DIAGRAMS.md`
**Audience:** All roles (developers, operators, product managers, stakeholders)
**Purpose:** UML sequence diagrams for the top 5 system use cases
**Focus:** End-to-end flows with actor interactions

**What It Shows:**
- UC1: User Configures Sentiment Alerts
- UC2: System Processes News and Triggers Alerts
- UC3: Anonymous User Authentication Flow
- UC4: CI/CD Deployment Pipeline
- UC5: Notification Delivery Flow

**Features:**
- Unified color palette with WCAG 2.1 AA accessibility
- Mermaid sequence diagrams (render in GitHub/VSCode)
- Autonumbered steps for easy reference

---

### 1. High-Level System Overview
**File:** `diagram-1-high-level-overview.md`
**Audience:** Non-technical stakeholders, product managers, executives
**Purpose:** Understand data flow from external sources (Twitter, RSS) to storage
**Focus:** External integrations, happy path only, minimal technical detail

**Canvas Specifications:**
- Size: 1920 x 1400 px (landscape)
- Color Scheme: Pastel (low saturation)
- Layout: Left-to-right flow (external → Lambda → data)
- Line Thickness: Indicates traffic volume (1px to 5px)

**What It Shows:**
- ✅ External sources (Twitter API, RSS feeds, Admin users)
- ✅ Entry points (EventBridge, API Gateway)
- ✅ Lambda functions (scheduler, ingestion, inference, admin API, metrics)
- ✅ Messaging (SNS topics, SQS queues)
- ✅ Data storage (DynamoDB tables)
- ✅ Support services (Secrets Manager, CloudWatch, S3)
- ✅ Operational monitoring (Metrics Lambda, StuckItems detection)
- ❌ Error paths (hidden for clarity)
- ❌ Security zones (not emphasized)

**Variants Available:**
- Simplified version (main flow only)
- Twitter flow only (highlighted)
- RSS flow only (highlighted)
- Admin API focus

---

### 2. Security Flow & Trust Boundaries
**File:** `diagram-2-security-flow.md`
**Audience:** Security engineers, developers, architects
**Purpose:** Understand data sanitization, validation checkpoints, error handling
**Focus:** Trust zones, tainted data flow, retry logic, DLQs, failure scenarios

**Canvas Specifications:**
- Size: 2200 x 1600 px (wide landscape)
- Color Scheme: Trust zone colors (red → orange → yellow → green → blue)
- Layout: Top-to-bottom flow (untrusted → protected)
- Emphasis: Security boundaries, error paths (dashed lines)

**What It Shows:**
- ✅ Trust zones (5 zones with color coding)
- ✅ Tainted data pathways (internet → database)
- ✅ Validation checkpoints (size limits, schema validation, SSRF prevention)
- ✅ Error handling (DLQs, retry logic, circuit breakers)
- ✅ Sanitization procedures (parameterized writes, hash computation)
- ✅ Cascading failure prevention
- ✅ Data loss prevention mechanisms
- ✅ All retry logic with backoff strategies

**Trust Zones:**
1. 🔴 **RED (Untrusted):** Internet-facing input (Twitter API, RSS feeds, Admin API)
2. 🟠 **ORANGE (Validation):** Ingestion Lambdas, API Gateway
3. 🟡 **YELLOW (Processing):** Inference Lambda, SNS/SQS
4. 🟢 **GREEN (Protected):** DynamoDB (parameterized writes only)
5. 🔵 **BLUE (Infrastructure):** Secrets Manager, CloudWatch, S3

---

## Creating Diagrams in Canva

### Prerequisites
1. Canva Pro account (for custom dimensions and export)
2. Access to color picker (for exact hex codes)
3. Grid enabled (100px spacing)

### Step-by-Step Process

#### For Diagram 1 (High-Level Overview):

1. **Create new design:**
   - Custom dimensions: 1920 x 1400 px
   - Enable grid: View → Show rulers and guides → Grid (100px)

2. **Set up layers:**
   - Layer 1: Background (white)
   - Layer 2: Component containers (rounded rectangles)
   - Layer 3: Arrows and connections
   - Layer 4: Text labels
   - Layer 5: Legend and title

3. **Use color palette:**
   - Copy hex codes from `diagram-1-high-level-overview.md`
   - Create color palette in Canva for reuse
   - Apply to components as specified

4. **Add components:**
   - Follow exact positions from specification
   - Use "Duplicate" for similar components
   - Group related items (component + label)

5. **Connect with arrows:**
   - Line thickness indicates traffic volume
   - Solid = write operations
   - Dashed = read operations
   - Add labels for data flow descriptions

6. **Export:**
   - Format: PNG
   - Resolution: 300 DPI
   - Filename: `sentiment-analyzer-high-level-overview.png`

#### For Diagram 2 (Security Flow):

1. **Create new design:**
   - Custom dimensions: 2200 x 1600 px
   - Enable grid: 100px spacing

2. **Create trust zone containers FIRST:**
   - Draw large rectangles for each zone
   - Apply background colors (very light pastels)
   - Add 3px borders with zone colors
   - Lock containers to prevent movement

3. **Add components inside zones:**
   - Follow top-to-bottom layout
   - 40px padding inside zone containers
   - Use monospace font (JetBrains Mono or Courier)

4. **Add error paths:**
   - Use dashed lines (distinct from solid happy paths)
   - Red/orange colors for error arrows
   - Add ⚠ warning icons

5. **Export:**
   - Format: PNG
   - Resolution: 300 DPI
   - Filename: `sentiment-analyzer-security-flow.png`

---

## Color Palettes

### Unified Mermaid Color Palette (for all flowcharts/sequence diagrams)

All Mermaid diagrams use this consistent palette optimized for WCAG 2.1 AA accessibility:

**Theme Configuration:**
```
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
```

**Node Class Definitions:**

| Class | Purpose | Fill | Border | Text | Contrast |
|-------|---------|------|--------|------|----------|
| `userNode` | User/Actor | `#dbeafe` | `#2563eb` | `#1e3a5f` | 7.2:1 |
| `systemNode` | System Component | `#e0e7ff` | `#4f46e5` | `#1e1b4b` | 8.1:1 |
| `apiNode` | API Gateway | `#fef3c7` | `#d97706` | `#78350f` | 6.8:1 |
| `lambdaNode` | Lambda Function | `#ddd6fe` | `#7c3aed` | `#2e1065` | 7.5:1 |
| `storageNode` | Database/S3 | `#d1fae5` | `#059669` | `#064e3b` | 6.2:1 |
| `queueNode` | SNS/SQS | `#fce7f3` | `#db2777` | `#831843` | 5.8:1 |
| `successNode` | Success State | `#bbf7d0` | `#16a34a` | `#14532d` | 5.4:1 |
| `errorNode` | Error State | `#fecaca` | `#dc2626` | `#7f1d1d` | 5.1:1 |
| `decisionNode` | Decision Point | `#fed7aa` | `#ea580c` | `#7c2d12` | 5.6:1 |
| `externalNode` | External Service | `#e5e7eb` | `#6b7280` | `#1f2937` | 9.4:1 |

**Copy-paste class definitions:**
```
classDef userNode fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
classDef systemNode fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b
classDef apiNode fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
classDef lambdaNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
classDef storageNode fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b
classDef queueNode fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
classDef successNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d
classDef errorNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
classDef externalNode fill:#e5e7eb,stroke:#6b7280,stroke-width:2px,color:#1f2937
```

---

### Diagram 1 (High-Level Overview) - Pastel Colors (Canva)

| Component Type | Fill Color | Border Color | Hex Code (Fill) |
|----------------|------------|--------------|-----------------|
| External Sources (Twitter) | Light Blue | Blue | `#E3F2FD` / `#90CAF9` |
| External Sources (RSS) | Light Orange | Orange | `#FFF3E0` / `#FFB74D` |
| External Sources (Admin) | Light Purple | Purple | `#F3E5F5` / `#CE93D8` |
| Lambda Functions | Light Purple | Purple | `#E1BEE7` / `#9C27B0` |
| SNS Topics | Light Pink | Pink | `#FCE4EC` / `#F48FB1` |
| SQS Queues | Light Yellow | Yellow | `#FFF9C4` / `#FFF176` |
| DynamoDB | Light Green | Green | `#C8E6C9` / `#66BB6A` |
| Secrets Manager | Light Teal | Teal | `#B2DFDB` / `#4DB6AC` |
| CloudWatch | Light Orange | Orange | `#FFCCBC` / `#FF8A65` |
| S3 | Light Purple | Purple | `#D1C4E9` / `#9575CD` |

### Diagram 2 (Security Flow) - Trust Zone Colors

| Trust Zone | Background | Border | Hex Code (BG) |
|------------|------------|--------|---------------|
| RED (Untrusted) | Very Light Red | Red | `#FFEBEE` / `#EF5350` |
| ORANGE (Validation) | Very Light Orange | Orange | `#FFF3E0` / `#FF9800` |
| YELLOW (Processing) | Very Light Yellow | Yellow | `#FFFDE7` / `#FDD835` |
| GREEN (Protected) | Very Light Green | Green | `#E8F5E9` / `#66BB6A` |
| BLUE (Infrastructure) | Very Light Blue | Blue | `#E3F2FD` / `#42A5F5` |

---

## Line Thickness Legend

**Diagram 1 (Traffic Volume):**
- Very thick (5px): High traffic (100-1,000 items/min) - SNS → SQS → Inference
- Thick (4px): Medium traffic (1-10 invocations/min) - Scheduler → Ingestion
- Medium (3px): Regular traffic - Admin API operations
- Thin (2px): Low traffic - Configuration reads
- Very thin (1px): Support/monitoring - CloudWatch, Secrets Manager

**Diagram 2 (Error Paths):**
- Solid (3-5px): Happy path (normal flow)
- Dashed (3px): Error path (retry/failure)
- Very thin (1px): Infrastructure connections

---

---

### 3. SSE Lambda Streaming Architecture (NEW - Dec 2025)
**File:** `sse-lambda-streaming.mmd`
**Audience:** Backend developers, SREs, streaming specialists
**Purpose:** Understand how SSE Lambda works from connection to event delivery
**Focus:** Connection lifecycle, heartbeat mechanism, polling strategy

**What It Shows:**
- ✅ Connection establishment through CloudFront → Lambda Web Adapter
- ✅ Connection pool management (100 max connections)
- ✅ DynamoDB polling (every 5 seconds)
- ✅ Heartbeat mechanism (30s intervals to keep CloudFront alive)
- ✅ Event streaming format (SSE protocol)
- ✅ Disconnect and cleanup flow
- ✅ Config-specific filtered streams with authentication
- ✅ Error handling (503 when pool full)

**Key Insights:**
- Lambda Web Adapter enables HTTP/1.1 streaming (not possible with Mangum)
- RESPONSE_STREAM invoke mode required for SSE
- Heartbeats prevent CloudFront's 60s origin timeout from disconnecting
- Last-Event-ID enables client reconnection resumption

---

### 4. CloudFront Multi-Origin Routing (NEW - Dec 2025)
**File:** `cloudfront-multi-origin.mmd`
**Audience:** DevOps, architects, frontend developers
**Purpose:** Understand how CloudFront routes requests to different backends
**Focus:** Cache behaviors, origin configuration, path-based routing

**What It Shows:**
- ✅ CloudFront edge entry point
- ✅ Three cache behaviors (priority order):
  1. `/api/v2/stream*` → SSE Lambda (TTL=0, no compression)
  2. `/api/*` → API Gateway (TTL=0, forward Authorization)
  3. `/*` → S3 Dashboard (TTL=1 day, compression enabled)
- ✅ Origin configurations (timeouts, keepalive)
- ✅ Lambda Web Adapter integration
- ✅ S3 Origin Access Control (OAC)
- ✅ Data flow to DynamoDB

**Key Insights:**
- SSE requires separate origin due to RESPONSE_STREAM requirement
- Path patterns evaluated in precedence order (most specific first)
- Static assets cached at edge, APIs never cached
- OAC replaces deprecated OAI for S3 access

---

## Future Diagram Plans

Keep Canva project active for future diagrams:

### Focused Component Diagrams (2-3 components each):

1. **OAuth Flow Deep Dive**
   - Components: Ingestion Lambda (Twitter), Secrets Manager, Circuit Breaker
   - Focus: Token refresh, caching, error handling
   - Audience: Developers implementing OAuth

2. **DLQ Processing Flow**
   - Components: SQS queues, DLQs, S3 archival, Reprocessing Lambda
   - Focus: Data loss prevention, message archival
   - Audience: Operations team

3. **Retry Logic Diagram**
   - Components: All retry patterns in one view
   - Focus: Backoff strategies, circuit breakers, DLQ triggers
   - Audience: Reliability engineers

4. **Cascading Failure Scenarios**
   - Components: 4 failure scenarios side-by-side
   - Focus: Twitter outage, Secrets throttling, DynamoDB hotspot, Lambda timeout
   - Audience: Incident responders

5. **Admin API Flow**
   - Components: API Gateway, Admin Lambda, DynamoDB, Validation
   - Focus: CRUD operations, SSRF prevention, rate limiting
   - Audience: API integrators

6. **Scheduler Scaling (Scan vs Query)**
   - Components: Scheduler Lambda, DynamoDB, GSI
   - Focus: Performance comparison, migration path
   - Audience: Performance engineers

---

## Exporting Diagrams

### For Documentation (Web):
- Format: PNG
- Resolution: 72 DPI
- Size: Original (1920x1400 or 2200x1600)
- Use: Embed in README.md, SPEC.md

### For Presentations:
- Format: PDF or SVG
- Resolution: 300 DPI
- Size: Original (scales well)
- Use: Stakeholder presentations, architecture reviews

### For Printing (Posters):
- Format: PNG or PDF
- Resolution: 300 DPI
- Size: Original or 2x (3840x2800 for Diagram 1)
- Use: Office wall posters, conference displays

---

## Diagram Versioning

**Version Control:**
- Keep all diagram versions in Canva project
- Export with version suffix: `diagram-1-v1.0.png`, `diagram-1-v1.1.png`
- Update README.md with latest version info

**Version History:**
- v1.0 (2025-11-16): Initial high-level overview and security flow diagrams
- v1.1 (2025-11-24): Added Metrics Lambda for operational monitoring (StuckItems detection)
- v1.2 (TBD): Add monthly quota reset Lambda (after specification gap fix)
- v2.0 (TBD): Add focused component diagrams (OAuth, DLQ, Retry)

---

## Usage Guidelines

**When to Update Diagrams:**
- ✅ New Lambda function added
- ✅ New AWS service integrated
- ✅ Error handling logic changed
- ✅ Security boundary modified
- ✅ Scaling architecture updated
- ❌ Minor configuration changes (no diagram update needed)
- ❌ Bug fixes (no diagram update needed)

**Review Schedule:**
- Quarterly review: Check if diagrams match current architecture
- After major releases: Update diagrams with new components
- Before architecture review meetings: Ensure diagrams are current

---

## Contributing

**To add a new diagram:**

1. Create specification file: `diagram-N-{name}.md`
2. Follow template from existing diagrams
3. Include:
   - Canvas size and layout
   - Component positions and colors
   - Arrow styles and labels
   - Color palette
   - Export settings
4. Update this README with new diagram info
5. Create Canva design
6. Export and commit PNG to repo

**Diagram Naming Convention:**
- `diagram-{number}-{short-name}.md` (specification)
- `sentiment-analyzer-{short-name}.png` (exported image)

---

## Resources

**Tools:**
- Canva: https://www.canva.com
- Color Palette Generator: https://coolors.co

**References:**
- SPEC.md: Complete technical specification
- SPECIFICATION-GAPS.md: Missing specifications and resolutions
- Interface analysis report: Comprehensive component inventory

**Contacts:**
- Diagram Owner: @traylorre
- Questions: Create GitHub issue with "diagram" label

---

**Last Updated:** 2025-12-16
**Diagram Count:** 5 specs + 5 use-case sequences (+ 6 planned component diagrams)
**Status:** SSE and CloudFront diagrams added; architecture diagrams updated with CloudFront CDN
