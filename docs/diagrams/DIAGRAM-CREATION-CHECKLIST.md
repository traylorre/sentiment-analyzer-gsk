# Canva Diagram Creation Checklist

**Project:** sentiment-analyzer-gsk
**Date:** 2025-11-16
**Status:** Ready to create in Canva

---

## Pre-Creation Setup

### Canva Account
- [ ] Canva Pro account active (required for custom dimensions)
- [ ] Create new project: "Sentiment Analyzer - Architecture Diagrams"
- [ ] Enable grid: View → Show rulers and guides → Grid (100px spacing)

### Color Palettes (Save in Canva)

**Palette 1: High-Level Overview (Pastels)**
```
External Sources:
- Light Blue: #E3F2FD (Tiingo)
- Light Orange: #FFF3E0 (Finnhub)
- Light Purple: #F3E5F5 (Admin)

Lambdas: #E1BEE7 (Light Purple)
Messaging: #FCE4EC (Pink), #FFF9C4 (Yellow)
Databases: #C8E6C9 (Green)
Support: #B2DFDB (Teal), #FFCCBC (Orange), #D1C4E9 (Purple)
```

**Palette 2: Security Flow (Trust Zones)**
```
Zone 1 (Untrusted): #FFEBEE (Very Light Red)
Zone 2 (Validation): #FFF3E0 (Very Light Orange)
Zone 3 (Processing): #FFFDE7 (Very Light Yellow)
Zone 4 (Protected): #E8F5E9 (Very Light Green)
Zone 5 (Infrastructure): #E3F2FD (Very Light Blue)
```

---

## Diagram 1: High-Level Overview

### Setup
- [ ] Create new design: Custom size 1920 x 1400 px
- [ ] Set background: White (#FFFFFF)
- [ ] Enable grid: 100px spacing
- [ ] Add title: "Sentiment Analyzer: High-Level System Overview" (28px bold)

### Component Creation (Follow Left-to-Right)

**Layer 1: External Sources (x: 100-300)**
- [ ] Tiingo API component (150, 200) - Size: 180x120
  - Fill: #E3F2FD, Border: #90CAF9 2px
  - Text: "Tiingo API\nRate: 450 req/15min\nQuota: Tier-based"
- [ ] Finnhub API component (150, 400) - Size: 180x120
  - Fill: #FFF3E0, Border: #FFB74D 2px
  - Text: "Finnhub API\nStock Market Data\nFormat: JSON"
- [ ] Admin User component (150, 600) - Size: 180x120
  - Fill: #F3E5F5, Border: #CE93D8 2px
  - Text: "Admin User\nAPI Gateway\nREST API"

**Layer 2: Entry Points (x: 400-600)**
- [ ] EventBridge component (450, 200) - Size: 160x100
  - Fill: #E8F5E9, Border: #81C784 2px
  - Text: "EventBridge\nEvery 60 seconds"
- [ ] API Gateway component (450, 600) - Size: 160x100
  - Fill: #F3E5F5, Border: #CE93D8 2px

**Layer 3: Lambda Functions (x: 700-900)**
- [ ] Ingestion Lambda Tiingo (700, 350) - Size: 180x140
- [ ] Ingestion Lambda Finnhub (700, 530) - Size: 180x140
- [ ] Dashboard Lambda (700, 710) - Size: 180x140

**Layer 4: Messaging (x: 1000-1200)**
- [ ] SNS Topics group (1050, 400) - Size: 180x200
  - Fill: #FCE4EC, Border: #F48FB1 2px
- [ ] SQS Queues group (1050, 650) - Size: 180x140
  - Fill: #FFF9C4, Border: #FFF176 2px

**Layer 5: Processing (x: 1300-1500)**
- [ ] Analysis Lambda (1350, 500) - Size: 180x160
  - Fill: #E1BEE7, Border: #9C27B0 2px

**Layer 6: Data Storage (x: 1600-1800)**
- [ ] DynamoDB source-configs (1650, 220) - Size: 200x120
  - Fill: #C8E6C9, Border: #66BB6A 2px
- [ ] DynamoDB sentiment-items (1650, 520) - Size: 200x120

**Layer 7: Support Services (y: 1000-1200)**
- [ ] Secrets Manager (450, 1050) - Size: 180x100
  - Fill: #B2DFDB, Border: #4DB6AC 2px
- [ ] CloudWatch (700, 1050) - Size: 180x100
  - Fill: #FFCCBC, Border: #FF8A65 2px
- [ ] S3 DLQ Archive (950, 1050) - Size: 180x100
  - Fill: #D1C4E9, Border: #9575CD 2px

### Arrows (Connect components)

**Traffic Volume Indicators:**
- [ ] EventBridge → Ingestion: 3px solid #81C784 - Label: "Trigger (5min)"
- [ ] Ingestion → SNS: 5px solid #F48FB1 (very thick) - Label: "10-100 items/poll"
- [ ] SNS → SQS: 4px solid #FFF176
- [ ] SQS → Analysis: 5px solid #9C27B0 (very thick) - Label: "Poll (batch: 10)"
- [ ] Analysis → DynamoDB: 5px solid #66BB6A (very thick) - Label: "100-1000 writes/min"

**Support Connections (thin):**
- [ ] Ingestion → Secrets Manager: 1px dashed #4DB6AC
- [ ] All Lambdas → CloudWatch: 1px dashed #FF8A65

### Legend
- [ ] Legend box (100, 1050) - Size: 250x100
  - Background: #FAFAFA, Border: #BDBDBD 1px
  - Content: Line thickness meanings

### Final Touches
- [ ] Align all components horizontally by layer
- [ ] Ensure text is readable at 50% zoom
- [ ] Group related items (component + arrows)
- [ ] Lock background elements

### Export
- [ ] Format: PNG
- [ ] Resolution: 300 DPI
- [ ] Filename: `sentiment-analyzer-high-level-overview.png`
- [ ] Save Canva project as "Diagram 1 - High-Level Overview"

---

## Diagram 2: Security Flow & Trust Boundaries

### Setup
- [ ] Create new design: Custom size 2200 x 1600 px
- [ ] Set background: White (#FFFFFF)
- [ ] Enable grid: 100px spacing
- [ ] Add title: "Security Flow & Trust Boundaries" (32px bold)

### Trust Zone Containers (Create FIRST, then lock)

- [ ] Zone 1: UNTRUSTED (100, 200) - Size: 2000x250
  - Background: #FFEBEE, Border: #EF5350 3px
  - Label: "ZONE 1: UNTRUSTED (Internet Input)"
- [ ] Zone 2: VALIDATION (100, 500) - Size: 2000x350
  - Background: #FFF3E0, Border: #FF9800 3px
  - Label: "ZONE 2: VALIDATION & SANITIZATION"
- [ ] Zone 3: PROCESSING (100, 900) - Size: 2000x350
  - Background: #FFFDE7, Border: #FDD835 3px
  - Label: "ZONE 3: PROCESSING (Still Tainted)"
- [ ] Zone 4: PROTECTED (100, 1300) - Size: 2000x250
  - Background: #E8F5E9, Border: #66BB6A 3px
  - Label: "ZONE 4: PROTECTED (Parameterized Writes Only)"
- [ ] Zone 5: INFRASTRUCTURE (1400, 200) - Size: 680x1350
  - Background: #E3F2FD, Border: #42A5F5 3px
  - Label: "ZONE 5: INFRASTRUCTURE"

### Components Inside Zones

**Zone 1 (Untrusted Input):**
- [ ] Tiingo API Response (200, 250) - Size: 280x160
  - Fill: #FFCDD2, Border: #E57373 2px
  - Text includes: "TAINTED FIELDS", "THREATS: ⚠ XSS, SQL Injection"
- [ ] Finnhub API Response (550, 250) - Size: 280x160
- [ ] Dashboard API Request (900, 250) - Size: 280x160
- [ ] OAuth Tokens (1250, 250) - Size: 280x160

**Zone 2 (Validation):**
- [ ] Ingestion Lambda Tiingo (200, 560) - Size: 320x260
  - Fill: #FFE0B2, Border: #FFB74D 2px
  - Text includes: "✓ VALIDATIONS", "✗ NO SANITIZATION YET", "ERRORS → DLQ"
- [ ] Ingestion Lambda Finnhub (580, 560) - Size: 320x260
- [ ] Dashboard Lambda (960, 560) - Size: 320x260
- [ ] OAuth Refresh (1340, 560) - Size: 320x260

**Zone 3 (Processing):**
- [ ] SNS/SQS Queue (200, 960) - Size: 380x260
  - Fill: #FFF9C4, Border: #FFF176 2px
- [ ] Analysis Lambda (640, 960) - Size: 420x260
  - Fill: #FFF59D, Border: #FFEB3B 2px
  - Text includes: "PARTIAL SANITIZATION", "IDEMPOTENCY"
- [ ] DLQ Processing (1120, 960) - Size: 380x260
  - Fill: #FFCCBC, Border: #FF8A65 2px

**Zone 4 (Protected):**
- [ ] DynamoDB Write Operation (300, 1360) - Size: 500x160
  - Fill: #C8E6C9, Border: #81C784 2px
  - Text: "✓ PARAMETERIZED (NoSQL Injection Protected)"
- [ ] Security Guarantees (860, 1360) - Size: 500x160
  - Fill: #A5D6A7, Border: #66BB6A 2px
  - Text: "✅ No SQL injection, ⚠ RESIDUAL RISKS"

**Zone 5 (Infrastructure):**
- [ ] Secrets Manager (1450, 280) - Size: 280x160
  - Fill: #BBDEFB, Border: #64B5F6 2px
- [ ] CloudWatch (1780, 280) - Size: 280x160
- [ ] S3 DLQ Archive (1450, 480) - Size: 280x160
- [ ] Retry Logic Summary (1780, 480) - Size: 280x320
  - Fill: #C5CAE9, Border: #7986CB 2px
- [ ] Error Response Schema (1450, 680) - Size: 580x200
  - Fill: #FFCCBC, Border: #FF8A65 2px
- [ ] Cascading Failure Prevention (1450, 920) - Size: 580x280
- [ ] Data Loss Prevention (1450, 1240) - Size: 580x280

### Arrows (Data Flow + Error Paths)

**Happy Paths (Solid):**
- [ ] Zone 1 → Zone 2: 4px solid, gradient #EF5350 → #FF9800
  - Label: "HTTP Response (TAINTED)"
- [ ] SQS → Analysis: 5px solid #FFEB3B
- [ ] Analysis → DynamoDB: 5px solid #66BB6A

**Error Paths (Dashed):**
- [ ] Ingestion → DLQ: 3px dashed #FF5722
  - Label: "FAILURE (after 3 retries)"
  - Add ⚠ warning icon
- [ ] Analysis → DLQ: 3px dashed #FF5722
- [ ] OAuth → Circuit Breaker: 2px dashed #FF9800

### Annotations
- [ ] Add ⚠ warning triangles on error paths
- [ ] Trust zone transition note: "RED → ORANGE → YELLOW → GREEN"
- [ ] "SANITIZATION CHECKPOINTS: Size limits, Schema validation, DNS + IP blocklist"

### Legend
- [ ] Trust Zone Legend (100, 50) - Size: 400x80
  - "🔴 RED: Untrusted, 🟠 ORANGE: Validation, etc."
- [ ] Retry Behavior Legend (100, 1600) - Size: 600x100
- [ ] Trust Zone Summary (750, 1600) - Size: 700x100

### Final Touches
- [ ] Use monospace font (JetBrains Mono or Courier)
- [ ] Ensure 40px padding inside zone containers
- [ ] Test text readability on pastel backgrounds
- [ ] Group components within each zone
- [ ] Lock zone containers

### Export
- [ ] Format: PNG
- [ ] Resolution: 300 DPI
- [ ] Filename: `sentiment-analyzer-security-flow.png`
- [ ] Save Canva project as "Diagram 2 - Security Flow"

---

## Post-Creation Tasks

### Documentation
- [ ] Export both diagrams as PNG (300 DPI)
- [ ] Save to: `docs/diagrams/exports/`
- [ ] Embed in README.md: `![High-Level Overview](docs/diagrams/exports/sentiment-analyzer-high-level-overview.png)`
- [ ] Embed in SPEC.md (optional)

### Version Control
- [ ] Commit diagram exports to Git
- [ ] Update `docs/diagrams/README.md` with version info
- [ ] Tag commit: `diagrams-v1.0`

### Canva Project Management
- [ ] Save Canva project link in README
- [ ] Create "Variations" pages in same project:
  - Simplified version (main flow only)
  - Tiingo flow only
  - Finnhub flow only
  - Dashboard API focus
- [ ] Keep project active for future updates

### Validation
- [ ] Review diagrams with team (if applicable)
- [ ] Check against SPEC.md for accuracy
- [ ] Verify all 27 interfaces are represented
- [ ] Confirm color contrast for accessibility

---

## Time Estimates

**Diagram 1 (High-Level Overview):**
- Setup & color palettes: 15 minutes
- Component creation: 45 minutes
- Arrows & connections: 30 minutes
- Legend & final touches: 15 minutes
- **Total: ~2 hours**

**Diagram 2 (Security Flow):**
- Setup & trust zones: 20 minutes
- Zone 1-3 components: 60 minutes
- Zone 4-5 components: 45 minutes
- Arrows & error paths: 45 minutes
- Annotations & legend: 20 minutes
- **Total: ~3 hours**

**Total Time: ~5 hours** (both diagrams)

---

## Troubleshooting

**Issue: Text not readable on pastel background**
- Solution: Increase font weight to Semi-Bold or Bold
- Solution: Add 80% opacity white rectangle behind text

**Issue: Arrows overlapping**
- Solution: Use curved arrows instead of straight
- Solution: Adjust arrow anchor points

**Issue: Components not aligning**
- Solution: Use Canva's alignment tools (Arrange → Align)
- Solution: Enable smart guides

**Issue: Color picker doesn't match hex codes**
- Solution: Use "Custom color" → Enter hex code manually
- Solution: Save custom colors to palette for reuse

**Issue: Export file size too large**
- Solution: Reduce resolution to 150 DPI (still good quality)
- Solution: Export as PDF instead of PNG

---

## Success Criteria

- [ ] Both diagrams created in Canva
- [ ] All components positioned correctly
- [ ] Colors match specifications (pastel, low saturation)
- [ ] Line thickness indicates traffic volume
- [ ] Text readable at 50% zoom
- [ ] Exported at 300 DPI PNG
- [ ] Files committed to Git
- [ ] Team reviewed (if applicable)

---

**Checklist Owner:** @traylorre
**Last Updated:** 2025-11-16
**Status:** Ready for Canva creation

---

## Notes

- Keep Canva project active - you'll create 6 more focused diagrams later
- Save color palettes in Canva for reuse
- Use "Duplicate page" in Canva to create variations
- Export each version with version suffix (v1.0, v1.1, etc.)

**Good luck creating the diagrams!** 🎨
