# Dashboard Specification

Last Updated: 2025-11-22
Status: Planning

## Overview

Interactive dashboard for sentiment analysis monitoring, model evaluation, and operational insights.

## Core Principles

1. **Real-time visibility**: Current system state at a glance
2. **Model accountability**: Track which code version processed each item
3. **A/B testing ready**: Compare model performance quantitatively
4. **On-call friendly**: Quick incident diagnosis and resolution
5. **Interview-ready**: Demonstrate end-to-end system capabilities

---

## Use-Cases

### 1. Interview Demo Scenarios

#### UC-1.1: End-to-End System Demonstration
**Actor**: Interviewer
**Goal**: Verify system works end-to-end with real data

**Flow:**
1. Dashboard shows real-time sentiment metrics updating
2. Recent items list displays articles with sentiment scores
3. Metrics include deployment tracking: "Processed by commit `abc1234` 2 hours ago"

**Data Requirements:**
- Real-time metrics (current)
- Recent items with `model_version` displayed
- Timestamp showing data freshness

**Success Criteria:**
- Interviewer sees live data flow
- Can correlate deployment with data processing

---

#### UC-1.2: Model Improvement Story
**Actor**: Interviewer
**Goal**: See how model improvements are validated

**Flow:**
1. Show A/B comparison view between two model versions
2. Display sentiment distribution differences:
   ```
   Model v1.0.0:  45% positive, 35% neutral, 20% negative
   Model v1.1.0:  48% positive, 33% neutral, 19% negative
   Delta:         +3% positive, -2% neutral, -1% negative
   ```
3. Show confidence score improvements
4. Explain validation methodology

**Data Requirements:**
- Sentiment counts grouped by `model_version`
- Average confidence scores by `model_version`
- Same articles analyzed by both versions (for controlled comparison)

**Dashboard Queries:**
```sql
-- Sentiment distribution by model version
SELECT
  model_version,
  sentiment,
  COUNT(*) as count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY model_version) as percentage
FROM items
WHERE analyzed_at > NOW() - INTERVAL '7 days'
GROUP BY model_version, sentiment

-- Confidence comparison
SELECT
  model_version,
  AVG(score) as avg_confidence,
  STDDEV(score) as std_dev,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY score) as median_confidence
FROM items
WHERE analyzed_at > NOW() - INTERVAL '7 days'
GROUP BY model_version
```

**Success Criteria:**
- Clear quantification of model improvement
- Statistically significant differences highlighted
- Visual comparison (side-by-side charts)

---

#### UC-1.3: Production Incident Walkthrough
**Actor**: Interviewer (on-call scenario)
**Goal**: Demonstrate incident response capabilities

**Narrative:**
"At 2:45 PM, we deployed commit `f8a3c12`. Within 5 minutes, error rates spiked to 5%. Here's how we handled it..."

**Dashboard Features:**
1. **Incident Timeline**: Error rate chart with deployment markers
2. **Affected Items**: Query all items processed by bad version
3. **Rollback Decision**: Compare error rates between versions
4. **Recovery**: Re-analyze failed items with previous good version

**Data Requirements:**
```sql
-- Error rate by model version (time-series)
SELECT
  DATE_TRUNC('minute', analyzed_at) as minute,
  model_version,
  COUNT(*) as total,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
  (errors * 100.0 / NULLIF(total, 0)) as error_rate_pct
FROM items
WHERE analyzed_at > NOW() - INTERVAL '1 hour'
GROUP BY minute, model_version
ORDER BY minute

-- Items affected by bad deployment
SELECT
  source_id,
  title,
  status,
  analyzed_at,
  error_message
FROM items
WHERE model_version = 'vf8a3c12'
  AND status = 'error'
```

**Success Criteria:**
- Can pinpoint exact deployment causing issue
- Quantify blast radius (how many items affected)
- Show rollback effectiveness

---

### 2. A/B Testing & Model Evaluation

#### UC-2.1: Controlled Model Comparison
**Actor**: ML Engineer
**Goal**: Quantify model improvement before full rollout

**Flow:**
1. Deploy new model to 10% of traffic (canary)
2. Same article gets analyzed by both models (duplicate processing)
3. Dashboard compares:
   - **Sentiment Agreement Rate**: % of times models agree
   - **Confidence Distribution**: Which model is more confident?
   - **Processing Latency**: Performance impact
   - **Error Rates**: Reliability comparison

**Example Metrics:**
```
Canary Comparison (1000 articles, 6 hours):
┌─────────────────────────┬──────────┬──────────┬────────┐
│ Metric                  │ v1.0.0   │ v2.0.0   │ Delta  │
├─────────────────────────┼──────────┼──────────┼────────┤
│ Sentiment Agreement     │    -     │    -     │  92%   │
│ Avg Confidence Score    │   0.85   │   0.87   │  +2%   │
│ Error Rate              │   0.02%  │   0.01%  │  -50%  │
│ Avg Processing Time (ms)│    245   │    238   │  -3%   │
└─────────────────────────┴──────────┴──────────┴────────┘

Disagreement Analysis (80 cases):
- Model v2.0.0 more positive: 45 cases
- Model v2.0.0 more negative: 35 cases
- Manual validation: v2.0.0 correct in 62/80 cases (78%)
```

**Dashboard Queries:**
```sql
-- Sentiment agreement between models (same article)
WITH dual_analysis AS (
  SELECT
    v1.source_id,
    v1.sentiment as v1_sentiment,
    v1.score as v1_score,
    v2.sentiment as v2_sentiment,
    v2.score as v2_score
  FROM items v1
  JOIN items v2 ON v1.source_id = v2.source_id
  WHERE v1.model_version = 'v1.0.0'
    AND v2.model_version = 'v2.0.0'
    AND v1.analyzed_at > NOW() - INTERVAL '6 hours'
)
SELECT
  COUNT(*) as total_comparisons,
  SUM(CASE WHEN v1_sentiment = v2_sentiment THEN 1 ELSE 0 END) as agreed,
  ROUND(100.0 * agreed / total_comparisons, 2) as agreement_pct,
  AVG(v1_score) as v1_avg_confidence,
  AVG(v2_score) as v2_avg_confidence
FROM dual_analysis

-- Disagreement details for manual review
SELECT
  source_id,
  title,
  v1_sentiment,
  v1_score,
  v2_sentiment,
  v2_score,
  url  -- for manual validation
FROM dual_analysis
WHERE v1_sentiment != v2_sentiment
ORDER BY ABS(v1_score - v2_score) DESC
LIMIT 100
```

**DynamoDB Implementation:**
- **Strategy**: Process each article twice with different model versions
- **Deduplication**: source_id remains same, model_version differs
- **Storage**: Same item stored twice with different model_version values
- **Query**: Filter by model_version, join on source_id

**Success Criteria:**
- Can prove new model is better quantitatively
- Identify edge cases where models disagree
- Make data-driven deployment decision

---

### 3. On-Call / Operations Dashboard

#### UC-3.1: Production Health Monitoring
**Actor**: On-Call Engineer (3 AM alert)
**Goal**: Quickly diagnose and resolve production issues

**Dashboard View:**
```
🚨 PRODUCTION HEALTH DASHBOARD

Current Model Deployments:
┌─────────────┬──────────┬─────────┬───────────┬──────────────┐
│ Version     │ % Traffic│ Errors  │ Avg Score │ Deployed     │
├─────────────┼──────────┼─────────┼───────────┼──────────────┤
│ v2.1.0      │   90%    │  0.02%  │   0.87    │ 4 hrs ago    │
│ v2.0.0      │   10%    │  0.01%  │   0.85    │ 2 days ago   │
└─────────────┴──────────┴─────────┴───────────┴──────────────┘

⚠️  ALERT: v2.1.0 error rate 2x higher than v2.0.0
📊 Recommendation: Rollback to v2.0.0 or reduce traffic to 10%

Recent Errors (Last 15 min):
- 14:32 - vf8a3c12 - NewsAPI rate limit (429)
- 14:28 - vf8a3c12 - DynamoDB ConditionalCheckFailed
- 14:25 - vf8a3c12 - Timeout fetching sentiment model

Metrics by Tag:
AI: 234 items, 0.01% errors
climate: 189 items, 0.05% errors ⚠️
economy: 156 items, 0.00% errors
```

**Dashboard Queries:**
```sql
-- Error rate by model version (last 1 hour)
SELECT
  model_version,
  COUNT(*) as total_items,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
  ROUND(100.0 * errors / NULLIF(total_items, 0), 4) as error_rate_pct,
  MAX(analyzed_at) as last_seen
FROM items
WHERE analyzed_at > NOW() - INTERVAL '1 hour'
GROUP BY model_version
ORDER BY error_rate_pct DESC

-- Traffic distribution (canary vs baseline)
SELECT
  model_version,
  COUNT(*) as items,
  ROUND(100.0 * COUNT(*) / (
    SELECT COUNT(*) FROM items
    WHERE analyzed_at > NOW() - INTERVAL '1 hour'
  ), 2) as traffic_pct
FROM items
WHERE analyzed_at > NOW() - INTERVAL '1 hour'
GROUP BY model_version

-- Recent errors for debugging
SELECT
  analyzed_at,
  model_version,
  source_id,
  title,
  error_message,
  tag
FROM items
WHERE status = 'error'
  AND analyzed_at > NOW() - INTERVAL '15 minutes'
ORDER BY analyzed_at DESC
LIMIT 50
```

**Success Criteria:**
- On-call engineer can diagnose issue in <5 minutes
- Clear recommendation (rollback, reduce traffic, investigate)
- Error details for debugging

---

### 4. Data Quality & Drift Detection

#### UC-4.1: Sentiment Drift Alerts
**Actor**: ML Ops
**Goal**: Detect when model behavior changes unexpectedly

**Scenario:**
```
📊 DRIFT ALERT

Model v1.5.0 Sentiment Distribution:
Days 1-30: 45% positive, 35% neutral, 20% negative (stable)
Day 31:     32% positive, 28% neutral, 40% negative (⚠️ drift detected)

Possible Causes:
1. Model degradation (needs investigation)
2. News cycle shift (legitimate - verify manually)
3. Data pipeline issue (check ingestion logs)

Recommended Action:
- Manual review of 50 recent articles
- Compare with baseline articles from Day 1-30
- Check if world events explain shift
```

**Dashboard Queries:**
```sql
-- Daily sentiment trend by model version
SELECT
  DATE(analyzed_at) as day,
  model_version,
  sentiment,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (
    PARTITION BY DATE(analyzed_at), model_version
  ), 2) as pct
FROM items
WHERE analyzed_at > NOW() - INTERVAL '90 days'
GROUP BY day, model_version, sentiment
ORDER BY day DESC, model_version

-- Anomaly detection: Days with >10% sentiment shift
WITH daily_positive AS (
  SELECT
    DATE(analyzed_at) as day,
    model_version,
    ROUND(100.0 * SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) / COUNT(*), 2) as positive_pct
  FROM items
  WHERE analyzed_at > NOW() - INTERVAL '90 days'
  GROUP BY day, model_version
)
SELECT
  day,
  model_version,
  positive_pct,
  LAG(positive_pct, 1) OVER (PARTITION BY model_version ORDER BY day) as prev_day_pct,
  positive_pct - prev_day_pct as delta
FROM daily_positive
WHERE ABS(positive_pct - prev_day_pct) > 10
ORDER BY day DESC
```

**Success Criteria:**
- Detect drift within 24 hours
- Distinguish legitimate changes from model issues
- Provide actionable recommendations

---

### 5. Regulatory / Audit Requirements

#### UC-5.1: Audit Trail & Reproducibility
**Actor**: Compliance Officer / Legal
**Goal**: Track which model version processed specific content

**Scenario:**
Customer complaint: "Your system labeled my article as 'negative' sentiment, hurting our brand"

**Dashboard Query:**
```sql
-- Audit trail for specific item
SELECT
  source_id,
  title,
  snippet,
  url,
  sentiment,
  score,
  model_version,
  analyzed_at,
  analyzed_by_commit,
  tag
FROM items
WHERE source_id = 'complaint-12345'
```

**Response:**
```
Audit Report: Article #complaint-12345

Title: "Tech Company Q3 Earnings Miss Expectations"
Analyzed: 2025-10-15 14:32:11 UTC
Model Version: vf8a3c12 (Git commit: f8a3c12a4b5c6d7e8f9)
Sentiment: negative (confidence: 0.91)
Tag: economy

Reproduction Steps:
1. git checkout f8a3c12a4b5c6d7e8f9
2. pytest tests/test_sentiment_model.py::test_article_complaint_12345
3. Verify sentiment matches production result

Manual Review:
- Article discusses missed earnings, layoffs, stock drop
- Negative sentiment classification: CONFIRMED ACCURATE
- Customer complaint: REJECTED
```

**Success Criteria:**
- Complete audit trail for every analyzed item
- Reproducible results via Git commit
- Defensible decision with evidence

---

### 6. Model Performance Benchmarking

#### UC-6.1: Model Leaderboard
**Actor**: ML Team
**Goal**: Track model performance over time

**Dashboard View:**
```
MODEL LEADERBOARD (Last 30 Days)

┌─────────────┬───────────────┬──────────────┬──────────────┬─────────────┐
│ Version     │ Avg Confidence│ Error Rate   │ Throughput   │ Rank        │
├─────────────┼───────────────┼──────────────┼──────────────┼─────────────┤
│ v2.1.0      │    0.87      │    0.02%     │  150 items/s │  ⭐ #1     │
│ v2.0.0      │    0.85      │    0.01%     │  140 items/s │  #2         │
│ v1.9.0      │    0.82      │    0.05%     │  130 items/s │  #3         │
│ v1.8.0      │    0.79      │    0.08%     │  120 items/s │  deprecated │
└─────────────┴───────────────┴──────────────┴──────────────┴─────────────┘

Best Overall: v2.1.0
- Highest confidence
- Low error rate (acceptable tradeoff vs v2.0.0)
- Best throughput

Recommendation: Increase v2.1.0 traffic to 100%
```

**Dashboard Queries:**
```sql
-- Model performance metrics (30-day rolling)
SELECT
  model_version,
  COUNT(*) as total_items,
  ROUND(AVG(score), 3) as avg_confidence,
  ROUND(STDDEV(score), 3) as confidence_std_dev,
  ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(*), 4) as error_rate_pct,
  ROUND(COUNT(*) / (30.0 * 24 * 3600), 2) as items_per_second
FROM items
WHERE analyzed_at > NOW() - INTERVAL '30 days'
GROUP BY model_version
ORDER BY avg_confidence DESC, error_rate_pct ASC
```

**Success Criteria:**
- Objective ranking of model versions
- Clear winner identification
- Data-driven deployment decisions

---

### 7. Canary Deployment Validation

#### UC-7.1: Real-Time Canary Health Check
**Actor**: DevOps / ML Ops
**Goal**: Validate new model before full rollout

**Workflow:**
1. Deploy new model to preprod → validate → tag commit
2. Deploy tagged commit to prod at 5% traffic
3. Dashboard shows real-time comparison for 10 minutes
4. Auto-promote to 25% if healthy, rollback if issues

**Dashboard View:**
```
🚀 CANARY DEPLOYMENT: v2.2.0 (5% traffic)

Health Check (5 minutes elapsed):
┌──────────────────┬──────────────┬──────────────┬──────────┐
│ Metric           │ Canary       │ Baseline     │ Status   │
├──────────────────┼──────────────┼──────────────┼──────────┤
│ Error Rate       │   0.01%      │   0.02%      │ ✅ Better│
│ Avg Confidence   │   0.88       │   0.87       │ ✅ Better│
│ P95 Latency      │   245ms      │   248ms      │ ✅ Better│
│ Items Processed  │   125        │   2,375      │ ℹ️  5%   │
└──────────────────┴──────────────┴──────────────┴──────────┘

✅ All metrics healthy
📊 Recommendation: PROMOTE to 25% traffic

Auto-promote in: 5 minutes (unless manual override)
```

**Dashboard Queries:**
```sql
-- Canary vs baseline comparison (last 10 minutes)
WITH recent_metrics AS (
  SELECT
    model_version,
    COUNT(*) as items,
    ROUND(AVG(score), 3) as avg_confidence,
    ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(*), 4) as error_rate,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_time_ms), 0) as p95_latency_ms
  FROM items
  WHERE analyzed_at > NOW() - INTERVAL '10 minutes'
  GROUP BY model_version
)
SELECT
  canary.model_version as canary_version,
  baseline.model_version as baseline_version,
  canary.items as canary_items,
  baseline.items as baseline_items,
  canary.avg_confidence - baseline.avg_confidence as confidence_delta,
  canary.error_rate - baseline.error_rate as error_rate_delta,
  canary.p95_latency_ms - baseline.p95_latency_ms as latency_delta_ms
FROM recent_metrics canary
CROSS JOIN recent_metrics baseline
WHERE canary.model_version = 'v2.2.0'  -- canary
  AND baseline.model_version = 'v2.1.0'  -- current baseline
```

**Success Criteria:**
- Real-time health validation
- Automatic rollback on regression
- Gradual traffic ramp (5% → 25% → 50% → 100%)

---

## Data Model Requirements

### DynamoDB Schema Extensions

**Current Schema:**
```
Primary Key: source_id (hash)
Sort Key: timestamp
Attributes: title, snippet, url, tag, sentiment, score, status, analyzed_at
```

**Required Additions:**
```
NEW: model_version (String)
  - Format: "v" + 7-char Git SHA (e.g., "vf8a3c12")
  - Required field
  - Indexed via GSI

NEW: processing_time_ms (Number)
  - Lambda execution time for this item
  - Used for latency analysis

NEW: error_message (String)
  - Populated when status = 'error'
  - Used for debugging
```

### Global Secondary Index (GSI)

**GSI Name:** `model-version-analyzed-index`
```
Hash Key: model_version
Sort Key: analyzed_at
Projection: ALL
```

**Enables queries:**
- Get all items for specific model version
- Time-range filtering per version
- Model comparison queries

---

## Dashboard API Endpoints

### Existing Endpoints (Current)
```
GET /health
GET /api/metrics?hours={1-168}
GET /api/items?status={pending|analyzed}&limit={1-100}
```

### New Endpoints (Required)

#### Model Comparison
```
GET /api/models/compare
Query Params:
  - baseline_version: string (e.g., "v1.0.0")
  - canary_version: string (e.g., "v2.0.0")
  - hours: number (default: 24)

Response:
{
  "baseline": {
    "model_version": "v1.0.0",
    "total_items": 5000,
    "avg_confidence": 0.85,
    "error_rate_pct": 0.02,
    "sentiment_distribution": {
      "positive": 45,
      "neutral": 35,
      "negative": 20
    }
  },
  "canary": { ... },
  "agreement": {
    "total_comparisons": 500,
    "agreed": 460,
    "agreement_pct": 92.0
  }
}
```

#### Model Performance
```
GET /api/models/performance?days={1-90}

Response:
{
  "models": [
    {
      "model_version": "v2.1.0",
      "total_items": 100000,
      "avg_confidence": 0.87,
      "confidence_std_dev": 0.12,
      "error_rate_pct": 0.02,
      "throughput_items_per_sec": 150.5,
      "first_seen": "2025-11-20T14:32:00Z",
      "last_seen": "2025-11-22T10:15:00Z"
    }
  ]
}
```

#### Canary Health
```
GET /api/canary/health?canary_version={version}&baseline_version={version}&minutes={5-60}

Response:
{
  "canary": {
    "model_version": "v2.2.0",
    "items": 125,
    "error_rate_pct": 0.01,
    "avg_confidence": 0.88,
    "p95_latency_ms": 245
  },
  "baseline": { ... },
  "comparison": {
    "confidence_delta": 0.01,
    "error_rate_delta": -0.01,
    "latency_delta_ms": -3
  },
  "recommendation": "PROMOTE",  // PROMOTE | HOLD | ROLLBACK
  "health_status": "HEALTHY"     // HEALTHY | DEGRADED | UNHEALTHY
}
```

#### Drift Detection
```
GET /api/drift/check?model_version={version}&baseline_days={30}

Response:
{
  "model_version": "v1.5.0",
  "current_day": {
    "date": "2025-11-22",
    "sentiment_distribution": {
      "positive": 32,
      "neutral": 28,
      "negative": 40
    }
  },
  "baseline_avg": {
    "days": 30,
    "sentiment_distribution": {
      "positive": 45,
      "neutral": 35,
      "negative": 20
    }
  },
  "drift_detected": true,
  "drift_magnitude": 13.0,  // max percentage point change
  "recommendation": "INVESTIGATE"
}
```

---

## UI/UX Requirements

### Page 1: Real-Time Monitoring
- **Top**: Current model deployments (traffic %, error rates, confidence)
- **Middle**: Live sentiment metrics (refreshes every 5 seconds)
- **Bottom**: Recent items feed

### Page 2: Model Comparison (A/B Testing)
- **Left**: Model A metrics
- **Right**: Model B metrics
- **Center**: Side-by-side charts (sentiment distribution, confidence histograms)
- **Bottom**: Disagreement cases for manual review

### Page 3: Operations Dashboard (On-Call)
- **Alerts panel**: Current issues requiring attention
- **Health panel**: Error rates, latency, throughput by model
- **Recent errors**: Last 50 errors with details
- **Quick actions**: Rollback button, traffic adjustment sliders

### Page 4: Model Leaderboard
- **Table**: All models ranked by performance
- **Charts**: Trend lines for confidence, error rate, throughput over time
- **Filters**: Date range, metric to optimize for

### Page 5: Drift Detection
- **Time-series chart**: Sentiment distribution over 90 days
- **Anomaly markers**: Days with significant shifts
- **Investigation panel**: Drill into specific days

---

## Implementation Phases

### Phase 1: Foundation (Current Sprint)
- ✅ Store `model_version` in DynamoDB
- ✅ Pass Git SHA as `vABC1234` format
- ✅ Include `model_version` in API responses
- ⏳ Add GSI for model_version queries

### Phase 2: Basic Model Comparison (Next Sprint)
- `/api/models/compare` endpoint
- Simple A/B comparison UI
- Sentiment agreement calculation

### Phase 3: Operations Dashboard (Sprint 3)
- `/api/models/performance` endpoint
- Real-time health monitoring
- Error rate tracking by model

### Phase 4: Advanced Features (Sprint 4+)
- Canary deployment automation
- Drift detection alerts
- Model leaderboard
- Auto-rollback on regression

---

## Success Metrics

### Interview Demo
- ✅ Interviewer can see end-to-end data flow in <2 minutes
- ✅ Can explain model versioning strategy
- ✅ Can demonstrate A/B testing capability

### Production Operations
- ✅ On-call engineer can diagnose issues in <5 minutes
- ✅ Mean time to recovery (MTTR) <15 minutes
- ✅ Zero undetected model regressions

### Model Development
- ✅ Can quantify model improvements before full rollout
- ✅ 95%+ confidence in deployment decisions
- ✅ Complete audit trail for all items

---

## Related Documentation

- [DynamoDB Schema](../../infrastructure/terraform/main.tf)
- [FAILURE_RECOVERY_RUNBOOK](../operations/FAILURE_RECOVERY_RUNBOOK.md) - Incident response
- [TROUBLESHOOTING](../operations/TROUBLESHOOTING.md) - Common issues
