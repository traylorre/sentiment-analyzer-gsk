# Research: Financial News Sentiment & Asset Volatility Dashboard

**Feature**: 006-user-config-dashboard | **Date**: 2025-11-26
**Purpose**: Document technology decisions and best practices for implementation

## Financial News APIs

### Decision: Tiingo as Primary, Finnhub as Secondary

**Chosen**: Dual-source architecture with Tiingo (primary) and Finnhub (secondary)

**Rationale**:
- Tiingo provides curated financial news with topic tags and ticker associations
- Finnhub provides built-in sentiment scores for comparison
- Dual-source enables redundancy and cross-validation of sentiment
- Both APIs allow production use on free tier

**Alternatives Considered**:
- Alpha Vantage: Limited news coverage, better for pure price data
- Polygon.io: More expensive, overkill for MVP
- Bloomberg/Reuters: Enterprise pricing, not suitable for <$100/mo budget

### Tiingo API Integration

**Endpoint**: `https://api.tiingo.com/tiingo/news`

**Best Practices**:
```python
# Rate limiting: 500 symbol lookups/month (free tier)
# Strategy: Aggressive deduplication + 1hr cache TTL

class TiingoAdapter:
    BASE_URL = "https://api.tiingo.com"

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Token {api_key}"

    def get_news(self, tickers: list[str], start_date: str) -> list[dict]:
        # Batch tickers to minimize API calls
        # Use aggressive caching (1hr TTL)
        # Implement exponential backoff on 429
        pass
```

**Response Schema**:
```json
{
  "id": 123456,
  "title": "Apple Reports Q4 Earnings",
  "description": "...",
  "publishedDate": "2025-11-25T14:30:00Z",
  "tickers": ["AAPL"],
  "tags": ["earnings", "technology"],
  "source": "bloomberg"
}
```

### Finnhub API Integration

**Endpoint**: `https://finnhub.io/api/v1/news-sentiment`

**Best Practices**:
```python
# Rate limiting: 60 calls/minute (free tier)
# Strategy: Per-ticker sentiment with caching

class FinnhubAdapter:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.params["token"] = api_key

    def get_sentiment(self, ticker: str) -> dict:
        # Returns built-in sentiment score
        # Cache for 1hr to stay within rate limits
        # Implement circuit breaker (5 failures/5 min)
        pass
```

**Response Schema**:
```json
{
  "symbol": "AAPL",
  "buzz": {"articlesInLastWeek": 150, "buzz": 0.95},
  "companyNewsScore": 0.7123,
  "sectorAverageNewsScore": 0.52,
  "sentiment": {"bearishPercent": 0.15, "bullishPercent": 0.85}
}
```

## Volatility Calculation (ATR)

### Decision: Average True Range (ATR) from OHLC Data

**Chosen**: 14-period ATR using OHLC data from both Tiingo and Finnhub

**Rationale**:
- ATR is standard volatility measure in technical analysis
- Both APIs provide OHLC data for ATR calculation
- 14-period is industry standard, adjustable per user preference
- Can be calculated for regular hours only or including extended hours

**Implementation**:
```python
def calculate_atr(ohlc_data: list[dict], period: int = 14) -> float:
    """
    Calculate Average True Range.

    True Range = max(
        high - low,
        abs(high - previous_close),
        abs(low - previous_close)
    )

    ATR = SMA(True Range, period)
    """
    true_ranges = []
    for i, candle in enumerate(ohlc_data):
        if i == 0:
            tr = candle["high"] - candle["low"]
        else:
            prev_close = ohlc_data[i - 1]["close"]
            tr = max(
                candle["high"] - candle["low"],
                abs(candle["high"] - prev_close),
                abs(candle["low"] - prev_close)
            )
        true_ranges.append(tr)

    # Simple Moving Average of True Range
    return sum(true_ranges[-period:]) / period
```

**Data Sources**:
- Tiingo: `https://api.tiingo.com/tiingo/daily/{ticker}/prices`
- Finnhub: `https://finnhub.io/api/v1/stock/candle` (redundancy)

## Authentication & User Management

### Decision: AWS Cognito + Custom Magic Links

**Chosen**: AWS Cognito for OAuth (Google/GitHub), custom Lambda for magic links via SendGrid

**Rationale**:
- Cognito handles OAuth complexity (Google/GitHub providers)
- Custom magic link implementation gives more control over UX
- SendGrid free tier (100 emails/day) sufficient for MVP
- 30-day session refresh aligns with Cognito defaults

**Alternatives Considered**:
- Auth0: More features but adds cost and vendor complexity
- Firebase Auth: Would require Firebase ecosystem
- Cognito built-in magic links: Less control over email templates

### OAuth Flow (Cognito)

```
1. User clicks "Sign in with Google/GitHub"
2. Redirect to Cognito Hosted UI
3. Cognito handles OAuth with provider
4. Callback to dashboard with authorization code
5. Exchange code for tokens (ID, Access, Refresh)
6. Store tokens in localStorage
7. Merge anonymous data with authenticated account
```

### Magic Link Flow (Custom)

```
1. User enters email
2. Lambda generates secure token (UUID + HMAC signature)
3. Store token in DynamoDB (1hr TTL, invalidates previous)
4. Send email via SendGrid with magic link
5. User clicks link
6. Lambda validates token, creates Cognito user if needed
7. Return Cognito tokens to client
8. Merge anonymous data with authenticated account
```

**Token Schema**:
```python
@dataclass
class MagicLinkToken:
    token_id: str  # UUID
    email: str
    created_at: datetime
    expires_at: datetime  # +1 hour
    used: bool = False
    signature: str  # HMAC-SHA256(token_id + email + secret)
```

## Email Notifications (SendGrid)

### Decision: SendGrid Free Tier with Rate Limiting

**Chosen**: SendGrid API for transactional emails (magic links, alerts)

**Rationale**:
- Free tier: 100 emails/day sufficient for MVP
- API-based (no SMTP complexity)
- Good deliverability and spam filtering
- Templates for consistent branding

**Implementation**:
```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

class EmailService:
    def __init__(self, api_key: str):
        self.client = SendGridAPIClient(api_key)

    def send_magic_link(self, email: str, link: str) -> bool:
        message = Mail(
            from_email="noreply@sentiment-analyzer.com",
            to_emails=email,
            subject="Your sign-in link",
            html_content=f'<a href="{link}">Click to sign in</a>'
        )
        response = self.client.send(message)
        return response.status_code == 202

    def send_alert(self, email: str, alert: Alert) -> bool:
        # Rate limit: max 10 alerts/day/user
        # Include unsubscribe link
        pass
```

**Rate Limiting**:
- 100 emails/day global (SendGrid limit)
- 10 alerts/day/user (application limit)
- 50% quota alert at 50 emails/day

## Heat Map Visualization

### Decision: D3.js or Recharts for Heat Maps

**Chosen**: Recharts (React-based) for heat map matrix visualization

**Rationale**:
- Recharts is React-native, integrates well with existing stack
- Supports heat map via ComposedChart with custom cells
- Mobile-responsive out of the box
- Lighter weight than D3.js for this use case

**Alternatives Considered**:
- D3.js: More powerful but steeper learning curve
- Chart.js: Less suitable for heat maps
- Plotly: Heavier, more suited for scientific viz

**Heat Map Dimensions**:
1. **Tickers x Sources**: Compare sentiment across Tiingo/Finnhub/Our Model
2. **Tickers x Time Periods**: Compare sentiment across Today/1W/1M/3M

**Color Gradient**:
```javascript
// Sentiment score -1 to +1 mapped to color
const sentimentColor = (score) => {
  if (score < -0.33) return '#ef4444'; // red (negative)
  if (score < 0.33) return '#eab308';  // yellow (neutral)
  return '#22c55e';                     // green (positive)
};
```

## Ticker Validation & Autocomplete

### Decision: Hybrid Local Cache + API Validation

**Chosen**: Static cache of ~8K US symbols (NYSE/NASDAQ/AMEX) + API validation

**Rationale**:
- Local cache enables instant autocomplete
- API validation catches delisted/changed symbols
- ~8K symbols is manageable in memory
- Update cache weekly via scheduled job

**Implementation**:
```python
# Static cache loaded at Lambda cold start
TICKER_CACHE = {}  # {symbol: {name, exchange, sector}}

def load_ticker_cache():
    """Load from S3 or bundled JSON file."""
    # NYSE: ~2,800 symbols
    # NASDAQ: ~3,500 symbols
    # AMEX: ~300 symbols
    # Total: ~6,600 active + ~1,400 recently delisted
    pass

def validate_ticker(symbol: str) -> TickerValidation:
    """
    Returns:
    - VALID: Symbol exists and is active
    - DELISTED: Symbol was delisted (suggest successor)
    - INVALID: Symbol not found
    """
    if symbol in TICKER_CACHE:
        ticker = TICKER_CACHE[symbol]
        if ticker.get("delisted"):
            return TickerValidation(
                status="DELISTED",
                successor=ticker.get("successor"),
                message=f"{symbol} replaced with {ticker['successor']}"
            )
        return TickerValidation(status="VALID", ticker=ticker)
    return TickerValidation(status="INVALID")
```

## Circuit Breaker Pattern

### Decision: 5 Failures in 5 Minutes = Open, 60s Recovery

**Chosen**: Per-API circuit breaker with configurable thresholds

**Rationale**:
- Prevents cascading failures when APIs are down
- 5 failures/5 min is aggressive enough to detect issues quickly
- 60s recovery allows quick restoration when issues resolve
- Show cached data during open circuit

**Implementation**:
```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    failure_window: timedelta = timedelta(minutes=5)
    recovery_timeout: timedelta = timedelta(seconds=60)

    failures: list[datetime] = field(default_factory=list)
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    opened_at: datetime = None

    def record_failure(self):
        now = datetime.utcnow()
        self.failures = [f for f in self.failures if now - f < self.failure_window]
        self.failures.append(now)

        if len(self.failures) >= self.failure_threshold:
            self.state = "OPEN"
            self.opened_at = now

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if datetime.utcnow() - self.opened_at > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN allows one request
```

## X-Ray Distributed Tracing

### Decision: Day 1 Mandatory with SNS Message Attribute Propagation

**Chosen**: AWS X-Ray on all 4 Lambdas using AWSXRayDaemonWriteAccess managed policy

**Rationale**:
- Full observability from day 1 (not deferred to Phase 2)
- SNS message attributes propagate trace context across Lambda invocations
- Managed policy simplifies IAM setup
- Essential for debugging async workflows

**Implementation**:
```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch boto3, requests, etc.
patch_all()

@xray_recorder.capture("ingestion_handler")
def handler(event, context):
    # Automatic tracing of all AWS calls
    pass
```

**Terraform Configuration**:
```hcl
resource "aws_iam_role_policy_attachment" "xray" {
  for_each   = toset(["ingestion", "analysis", "dashboard", "notification"])
  role       = aws_iam_role.lambda[each.key].name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

resource "aws_lambda_function" "all" {
  # ... other config
  tracing_config {
    mode = "Active"
  }
}
```

## CloudWatch RUM (Real User Monitoring)

### Decision: CloudWatch RUM for Client-Side Analytics

**Chosen**: AWS CloudWatch RUM integrated with React dashboard

**Rationale**:
- Native AWS integration with existing CloudWatch
- ~$0.10 per 1K sessions (within budget)
- Captures page load times, errors, user journeys
- No additional vendor (Mixpanel, Amplitude, etc.)

**Implementation**:
```javascript
// Install CloudWatch RUM web client
import { AwsRum } from 'aws-rum-web';

const config = {
  sessionSampleRate: 1,
  guestRoleArn: 'arn:aws:iam::ACCOUNT:role/RUM-Guest',
  identityPoolId: 'us-east-1:xxx',
  endpoint: 'https://dataplane.rum.us-east-1.amazonaws.com',
  telemetries: ['performance', 'errors', 'http'],
  allowCookies: true,
  enableXRay: true
};

const awsRum = new AwsRum('APP_NAME', '1.0.0', 'us-east-1', config);
```

## Cost Optimization Strategy

### Decision: Aggressive Caching + Smart Allocation

**Strategy**:
1. **1-hour cache TTL** on all API responses
2. **Deduplication** across users tracking same tickers
3. **Volatility-aware priority**: High-volatility tickers refresh more often
4. **Daily burn rate alerts** at $3.33 (1/30th of $100 budget)

**Quota Management**:
```python
class QuotaManager:
    def __init__(self, daily_limit: int):
        self.daily_limit = daily_limit
        self.used_today = 0

    def can_fetch(self, ticker: str, volatility: float) -> bool:
        # High volatility (>3% ATR) gets priority
        if volatility > 0.03:
            return self.used_today < self.daily_limit * 0.8
        # Low volatility uses remaining quota
        return self.used_today < self.daily_limit * 0.5
```

## Summary of Decisions

| Area | Decision | Key Rationale |
|------|----------|---------------|
| News APIs | Tiingo + Finnhub | Dual-source redundancy, free tier production use |
| Volatility | ATR (14-period) | Industry standard, both APIs provide OHLC |
| Auth | Cognito + Custom Magic Links | OAuth handled, custom UX for magic links |
| Email | SendGrid | 100/day free, good deliverability |
| Visualization | Recharts | React-native, mobile-responsive |
| Ticker Cache | ~8K local + API validation | Instant autocomplete, catches delisted |
| Circuit Breaker | 5 failures/5 min | Prevents cascading failures |
| Tracing | X-Ray Day 1 | Full observability from launch |
| Analytics | CloudWatch RUM | Native AWS, ~$5/mo at scale |
| Cost Control | Aggressive caching + alerts | Stay under $100/mo |
