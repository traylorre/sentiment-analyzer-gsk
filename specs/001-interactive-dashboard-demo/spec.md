# Feature Specification: Interactive Dashboard Demo

**Branch**: `001-interactive-dashboard-demo` | **Date**: 2025-11-16

## Purpose

Deliver a demonstrable, interactive sentiment analysis system where stakeholders can participate by selecting 5 custom tags/keywords to watch, then observe real-time data ingestion and sentiment analysis results appearing in a live dashboard.

## Demo Success Criteria

**Primary Demo Flow:**
1. Interviewer/stakeholder provides 5 tags/keywords they want to track
2. System admin enters these tags into the watch configuration
3. Dashboard displays live traffic being ingested across multiple visualizations
4. Results of sentiment analysis populate in near-real-time (visible in DynamoDB via AWS Console or dashboard UI)
5. Charts show ingestion rate, sentiment distribution, per-tag matches

**Why This Matters:**
- Interactive participation (not passive demo)
- Real system behavior (not toy curl examples)
- Visual UX demonstrates production-quality thinking
- Validates end-to-end architecture under live conditions

## Scope (Demo 1 Only)

### In Scope
- **Data Sources**: At least ONE working data source adapter (recommend NewsAPI or Twitter/X API)
- **Tag-based ingestion**: Fetch items matching the 5 user-provided tags
- **Sentiment analysis**: Real inference (OpenAI API or simple local model) producing positive/neutral/negative + confidence score
- **Storage**: DynamoDB table storing analyzed items with source metadata, sentiment, score, timestamp
- **Dashboard**: Live-updating visualization showing:
  - Ingestion rate over time
  - Sentiment distribution (pie/bar chart)
  - Per-tag match counts
  - Recent items (last 10-20) with redacted/snippet text
- **Admin controls**: Simple UI or CLI to input the 5 watch tags and select active feed

### Out of Scope (Deferred)
- Full authentication (use API keys or skip for demo)
- Quota management and rate-limit enforcement (basic backoff only)
- Metric dimensions and complex access control
- Multiple simultaneous data sources (one source is sufficient)
- Chaos testing infrastructure (Demo 2)
- Auto-scaling stress tests (Demo 3)

## Functional Requirements

1. **Tag Watch Configuration**
   - Admin can input exactly 5 keywords/hashtags
   - System validates input (no > 200 char, no control chars)
   - Changes apply immediately to ingestion

2. **Data Ingestion**
   - Fetch items from selected source matching watch tags
   - Poll interval: configurable (default 30-60s for demo responsiveness)
   - Deduplicate by stable ID or content hash
   - Respect source API rate limits with basic backoff

3. **Sentiment Analysis**
   - Process each unique item through sentiment model
   - Return: `{sentiment: positive|neutral|negative, score: 0.0-1.0, model_version}`
   - Store result in DynamoDB

4. **Dashboard Display**
   - Update interval: ≤ 5-10 seconds
   - Charts:
     - Time-series: ingestion rate (items/min)
     - Pie chart: sentiment distribution
     - Bar chart: matches per tag
     - Table: recent items (show snippet, sentiment, score, timestamp)
   - Filters: time range (last 1h/24h), tag selector

5. **Observability**
   - CloudWatch metrics for ingestion_count, analysis_count, error_count
   - Logs showing item processing flow
   - Dashboard reads from DynamoDB or CloudWatch metrics

## Non-Functional Requirements

- **Responsiveness**: Dashboard updates visible within 10 seconds of item ingestion
- **Reliability**: Handle transient API failures gracefully (retry with backoff)
- **Simplicity**: Minimal infrastructure - use serverless where possible (Lambda + DynamoDB + API Gateway or S3-hosted dashboard)
- **Cost**: Optimize for demo cost efficiency (on-demand DynamoDB, pay-per-invocation Lambda)

## Technical Approach

### Architecture (Simplified for Demo)
```
[Data Source API]
    ↓ (polling Lambda scheduled every 60s)
[Ingestion Lambda] → dedup check → [DynamoDB: items table]
    ↓ (trigger or SNS)
[Analysis Lambda] → sentiment inference → update DynamoDB
    ↓
[Dashboard] ← reads DynamoDB + CloudWatch metrics
```

### Technology Stack
- **Compute**: AWS Lambda (Python 3.11)
- **Storage**: DynamoDB (on-demand capacity)
- **Dashboard**: Options:
  - Static S3-hosted HTML + Chart.js + AWS SDK (polls DynamoDB)
  - CloudWatch dashboard + custom widgets
  - Simple Flask/FastAPI app on Lambda URL
- **Sentiment Model**: OpenAI API (gpt-3.5-turbo) or HuggingFace transformers (distilbert-base-uncased-finetuned-sst-2-english)
- **IaC**: Terraform (minimal - defer full TFC integration to later)
- **Data Source**: NewsAPI (easy, no OAuth) or Twitter API v2

### Data Model (DynamoDB)
**Table: `sentiment_items`**
- PK: `source_id` (string, e.g., "newsapi#article-123")
- SK: `ingested_at` (ISO8601 timestamp)
- Attributes:
  - `source_type`: "newsapi" | "twitter"
  - `text_snippet`: first 200 chars
  - `sentiment`: "positive" | "neutral" | "negative"
  - `score`: number (0.0-1.0)
  - `model_version`: string
  - `matched_tags`: list of strings (which watch tags matched)
  - `url`: source URL (optional)

**GSI: `by_timestamp`** (for recent items query)
- PK: `source_type`
- SK: `ingested_at`

### Security (Minimal for Demo)
- API keys stored in AWS Secrets Manager
- Lambda IAM roles: least-privilege (read/write DynamoDB, read Secrets Manager)
- Dashboard: public read-only (or simple API key for access)
- TLS enforced for external API calls

## Acceptance Criteria

**Demo Day Checklist:**
1. ✅ Admin enters 5 tags (e.g., "AI", "climate", "economy", "health", "sports")
2. ✅ Dashboard shows initial state (empty or seeded data)
3. ✅ Ingestion Lambda runs and fetches items matching tags
4. ✅ Within 30 seconds, dashboard shows:
   - Ingestion count increasing
   - At least 3 items in recent items table
   - Sentiment distribution chart updating
5. ✅ Sentiment scores are realistic (not all neutral)
6. ✅ Per-tag match counts are accurate
7. ✅ No errors visible in CloudWatch logs
8. ✅ Stakeholder can ask "show me negative sentiment items" and we can filter/highlight

**Technical Validation:**
- End-to-end test: seed 10 items → verify DynamoDB entries → verify dashboard displays them
- Deduplication test: re-fetch same item → verify no duplicate in DB
- Rate limit test: simulate API 429 → verify backoff and retry

## Open Questions

1. **Data Source Choice**: NewsAPI (easier, no OAuth) vs Twitter API (more engaging but OAuth complexity)?
2. **Dashboard Framework**: S3-hosted static HTML vs Lambda-hosted web app?
3. **Sentiment Model**: OpenAI API (fast, costs $) vs local HuggingFace model (slower, free)?
4. **Seed Data**: Should we pre-populate DynamoDB with sample data for instant demo gratification?

## Future Enhancements (Post-Demo 1)

- **Demo 2**: Chaos testing - randomly disable Lambda, simulate DynamoDB throttling, verify alarms
- **Demo 3**: Load testing - spike traffic, observe auto-scaling, verify throughput alarms resolve
- Multi-source support (all three: News, Twitter, Market data)
- Full Cognito authentication
- Advanced metric dimensions and access control
- Terraform Cloud integration with full CI/CD
