# Data Model: Financial News Sentiment & Asset Volatility Dashboard

**Feature**: 006-user-config-dashboard | **Date**: 2025-11-26

## Entity Overview

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│      User       │────<│   Configuration     │────<│   AlertRule     │
└─────────────────┘     └─────────────────────┘     └─────────────────┘
        │                        │
        │                        │
        ▼                        ▼
┌─────────────────┐     ┌─────────────────────┐
│  Notification   │     │  SentimentResult    │
└─────────────────┘     └─────────────────────┘
                                 │
                                 │
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────────┐ ┌─────────────────┐
               │ VolatilityMetric│ │   NewsArticle   │
               └─────────────────┘ └─────────────────┘
```

## DynamoDB Table Design

### Table: `{env}-sentiment-users`

**Primary Key**: `PK` (user_id) | **Sort Key**: `SK` (entity type)

| Access Pattern | PK | SK | GSI |
|---------------|----|----|-----|
| Get user by ID | `USER#{user_id}` | `PROFILE` | - |
| Get user configs | `USER#{user_id}` | `CONFIG#{config_id}` | - |
| Get user alerts | `USER#{user_id}` | `ALERT#{alert_id}` | - |
| Get user by email | - | - | GSI1: `email` |
| Get user by Cognito ID | - | - | GSI2: `cognito_sub` |

### Table: `{env}-sentiment-items` (existing, extended)

**Primary Key**: `PK` (ticker) | **Sort Key**: `SK` (timestamp#source)

| Access Pattern | PK | SK | GSI |
|---------------|----|----|-----|
| Get sentiment by ticker/time | `TICKER#{symbol}` | `{timestamp}#{source}` | - |
| Get by sentiment score | - | - | GSI1: `sentiment_label` |
| Get by source | - | - | GSI2: `source_type` |
| Get recent by ticker | `TICKER#{symbol}` | begins_with `2025-` | - |

### Table: `{env}-sentiment-notifications`

**Primary Key**: `PK` (user_id) | **Sort Key**: `SK` (timestamp)

| Access Pattern | PK | SK |
|---------------|----|----|
| Get user notifications | `USER#{user_id}` | `{timestamp}` |
| Get by status | - | GSI1: `status` |

---

## Entity Schemas

### User

```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import datetime

class User(BaseModel):
    """Dashboard user - anonymous or authenticated."""

    # Primary identifiers
    user_id: str = Field(..., description="UUID, generated on first visit")
    email: Optional[EmailStr] = Field(None, description="Set after auth")
    cognito_sub: Optional[str] = Field(None, description="Cognito user pool sub")

    # Authentication state
    auth_type: Literal["anonymous", "email", "google", "github"] = "anonymous"
    created_at: datetime
    last_active_at: datetime
    session_expires_at: datetime  # 30 days, refreshed on activity

    # Preferences
    timezone: str = "America/New_York"
    email_notifications_enabled: bool = True
    daily_email_count: int = 0  # Reset daily, max 10

    # DynamoDB keys
    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return "PROFILE"

class UserCreate(BaseModel):
    """Anonymous user creation."""
    timezone: Optional[str] = "America/New_York"

class UserUpgrade(BaseModel):
    """Upgrade anonymous to authenticated."""
    email: Optional[EmailStr] = None
    cognito_sub: Optional[str] = None
    auth_type: Literal["email", "google", "github"]
```

### Configuration

```python
class Ticker(BaseModel):
    """Stock ticker with validation metadata."""
    symbol: str = Field(..., max_length=10, pattern=r"^[A-Z]{1,5}$")
    name: Optional[str] = None
    exchange: Literal["NYSE", "NASDAQ", "AMEX"]
    added_at: datetime

class Configuration(BaseModel):
    """User's saved configuration (max 2 per user)."""

    config_id: str = Field(..., description="UUID")
    user_id: str
    name: str = Field(..., max_length=50, description="e.g., 'Tech Giants'")

    # Ticker settings (max 5)
    tickers: list[Ticker] = Field(..., max_length=5)

    # Timeframe (1-365 days, limited by Finnhub 1-year free tier)
    timeframe_days: int = Field(7, ge=1, le=365)

    # ATR settings
    include_extended_hours: bool = False
    atr_period: int = Field(14, ge=5, le=50)

    # Metadata
    created_at: datetime
    updated_at: datetime
    is_active: bool = True  # For soft delete

    # DynamoDB keys
    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return f"CONFIG#{self.config_id}"

class ConfigurationCreate(BaseModel):
    """Create new configuration."""
    name: str = Field(..., max_length=50)
    tickers: list[str] = Field(..., max_length=5)
    timeframe_days: int = Field(7, ge=1, le=365)
    include_extended_hours: bool = False

class ConfigurationUpdate(BaseModel):
    """Update existing configuration."""
    name: Optional[str] = Field(None, max_length=50)
    tickers: Optional[list[str]] = Field(None, max_length=5)
    timeframe_days: Optional[int] = Field(None, ge=1, le=365)
    include_extended_hours: Optional[bool] = None
```

### SentimentResult

```python
class SentimentSource(BaseModel):
    """Source metadata for sentiment."""
    source_type: Literal["tiingo", "finnhub", "our_model"]
    model_version: Optional[str] = None
    fetched_at: datetime

class SentimentResult(BaseModel):
    """Sentiment analysis result for a ticker at a point in time."""

    result_id: str = Field(..., description="UUID")
    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    timestamp: datetime

    # Sentiment scores (-1 to +1)
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    sentiment_label: Literal["positive", "neutral", "negative"]
    confidence: float = Field(..., ge=0.0, le=1.0)

    # Source information
    source: SentimentSource

    # Associated news (optional, for our_model source)
    news_article_ids: list[str] = Field(default_factory=list)

    # DynamoDB keys
    @property
    def pk(self) -> str:
        return f"TICKER#{self.ticker}"

    @property
    def sk(self) -> str:
        return f"{self.timestamp.isoformat()}#{self.source.source_type}"

def sentiment_label_from_score(score: float) -> str:
    """Map numeric score to label."""
    if score < -0.33:
        return "negative"
    elif score > 0.33:
        return "positive"
    return "neutral"
```

### VolatilityMetric

```python
class OHLCCandle(BaseModel):
    """Single OHLC candle."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class VolatilityMetric(BaseModel):
    """ATR volatility calculation for a ticker."""

    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")
    timestamp: datetime
    period: int = Field(14, description="ATR period in days")

    # ATR values
    atr_value: float
    atr_percent: float  # ATR as % of current price
    previous_atr: Optional[float] = None

    # Trend indicator
    trend: Literal["increasing", "decreasing", "stable"]

    # Source candles used
    candle_count: int
    includes_extended_hours: bool

    @property
    def trend_arrow(self) -> str:
        """Visual trend indicator."""
        return {"increasing": "↑", "decreasing": "↓", "stable": "→"}[self.trend]
```

### AlertRule

```python
class AlertRule(BaseModel):
    """User-defined alert rule for a ticker."""

    alert_id: str = Field(..., description="UUID")
    user_id: str
    config_id: str  # Associated configuration
    ticker: str = Field(..., pattern=r"^[A-Z]{1,5}$")

    # Alert type
    alert_type: Literal["sentiment_threshold", "volatility_threshold"]

    # Threshold settings
    threshold_value: float
    threshold_direction: Literal["above", "below"]

    # State
    is_enabled: bool = True
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0

    # Metadata
    created_at: datetime

    # DynamoDB keys
    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return f"ALERT#{self.alert_id}"

class AlertRuleCreate(BaseModel):
    """Create new alert rule."""
    config_id: str
    ticker: str
    alert_type: Literal["sentiment_threshold", "volatility_threshold"]
    threshold_value: float
    threshold_direction: Literal["above", "below"]

class AlertEvaluation(BaseModel):
    """Result of evaluating an alert rule."""
    alert_id: str
    triggered: bool
    current_value: float
    threshold_value: float
    message: str
```

### Notification

```python
class Notification(BaseModel):
    """Sent notification record."""

    notification_id: str = Field(..., description="UUID")
    user_id: str
    alert_id: str

    # Delivery
    email: EmailStr
    subject: str
    sent_at: datetime
    status: Literal["pending", "sent", "failed", "bounced"]

    # Tracking
    sendgrid_message_id: Optional[str] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None

    # Content
    ticker: str
    alert_type: str
    triggered_value: float
    deep_link: str  # Link back to dashboard config

    # DynamoDB keys
    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return self.sent_at.isoformat()
```

### MagicLinkToken

```python
class MagicLinkToken(BaseModel):
    """Magic link authentication token."""

    token_id: str = Field(..., description="UUID")
    email: EmailStr
    signature: str  # HMAC-SHA256

    created_at: datetime
    expires_at: datetime  # +1 hour
    used: bool = False

    # Link to anonymous user to merge
    anonymous_user_id: Optional[str] = None

    # DynamoDB keys (separate table or TTL-managed)
    @property
    def pk(self) -> str:
        return f"TOKEN#{self.token_id}"

    def is_valid(self) -> bool:
        return not self.used and datetime.utcnow() < self.expires_at
```

---

## State Transitions

### User Authentication States

```
┌──────────────┐  upgrade   ┌─────────────┐
│  anonymous   │───────────>│ authenticated│
└──────────────┘            └─────────────┘
       │                           │
       │ session_expires           │ session_expires
       ▼                           ▼
┌──────────────┐            ┌─────────────┐
│   expired    │            │  logged_out │
│ (localStorage│            │  (re-auth)  │
│   cleared)   │            └─────────────┘
└──────────────┘
```

### Alert Rule States

```
┌──────────┐  enable   ┌─────────┐  trigger  ┌───────────┐
│ disabled │──────────>│ enabled │──────────>│ triggered │
└──────────┘           └─────────┘           └───────────┘
     ▲                      │                      │
     │       disable        │                      │
     └──────────────────────┘                      │
                            ▲                      │
                            │    reset (auto)      │
                            └──────────────────────┘
```

---

## Validation Rules

### Ticker Validation

```python
TICKER_RULES = {
    "format": r"^[A-Z]{1,5}$",
    "exchanges": ["NYSE", "NASDAQ", "AMEX"],
    "max_per_config": 5,
    "cache_size": 8000,  # Approximate US market symbols
}
```

### Configuration Limits

```python
CONFIG_LIMITS = {
    "max_configs_per_user": 2,
    "max_tickers_per_config": 5,
    "min_timeframe_days": 1,
    "max_timeframe_days": 365,
    "name_max_length": 50,
}
```

### Alert Limits

```python
ALERT_LIMITS = {
    "max_alerts_per_config": 10,
    "max_emails_per_day": 10,
    "sentiment_threshold_range": (-1.0, 1.0),
    "volatility_threshold_range": (0.0, 100.0),  # Percent
}
```

### Session Limits

```python
SESSION_LIMITS = {
    "anonymous_retention_days": 30,  # localStorage only
    "authenticated_retention_days": 90,
    "session_duration_days": 30,
    "magic_link_expiry_hours": 1,
}
```
