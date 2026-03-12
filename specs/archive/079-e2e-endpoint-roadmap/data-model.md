# Data Model: E2E Endpoint Entities

**Feature**: 079-e2e-endpoint-roadmap
**Derived From**: E2E test assertions and API payloads

This document defines the entity models scaffolded from existing E2E test blackbox behavior.

---

## Phase 1 Entities

### Alert

**Source**: `tests/e2e/test_alerts.py`

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    """Request payload for creating an alert."""

    type: Literal["sentiment", "volatility"]
    ticker: str
    threshold: float
    condition: Literal["above", "below"]
    enabled: bool = True


class AlertUpdate(BaseModel):
    """Request payload for updating an alert."""

    enabled: bool | None = None
    threshold: float | None = None


class Alert(BaseModel):
    """Alert entity as returned by API."""

    alert_id: str
    type: Literal["sentiment", "volatility"]
    ticker: str
    threshold: float
    condition: Literal["above", "below"]
    enabled: bool
    config_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
```

**DynamoDB Schema**:
```
PK: CONFIG#{config_id}
SK: ALERT#{alert_id}
GSI1PK: USER#{user_id}
GSI1SK: ALERT#{alert_id}

Attributes:
- alert_id (S)
- type (S): "sentiment" | "volatility"
- ticker (S)
- threshold (N)
- condition (S): "above" | "below"
- enabled (BOOL)
- config_id (S)
- user_id (S)
- created_at (S): ISO8601
- updated_at (S): ISO8601
```

---

### MarketStatus

**Source**: `tests/e2e/test_market_status.py`

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MarketStatus(BaseModel):
    """Current market status."""

    status: Literal["OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS"]
    is_open: bool
    timestamp: datetime
    next_open: datetime | None = None
    next_close: datetime | None = None
    trading_day: bool
    timezone: str = "America/New_York"


class MarketSchedule(BaseModel):
    """Market trading hours."""

    open_time: str  # "09:30"
    close_time: str  # "16:00"
    timezone: str = "America/New_York"
    pre_market_start: str = "04:00"
    pre_market_end: str = "09:30"
    after_hours_start: str = "16:00"
    after_hours_end: str = "20:00"


class Holiday(BaseModel):
    """Market holiday."""

    date: str  # "2025-12-25"
    name: str  # "Christmas Day"
```

**Implementation Note**: MarketStatus is computed, not persisted. Use `exchange_calendars` for NYSE schedule.

---

### TickerInfo

**Source**: `tests/e2e/test_ticker_validation.py`

```python
from pydantic import BaseModel


class TickerInfo(BaseModel):
    """Ticker metadata from validation/search."""

    symbol: str  # Uppercase
    company_name: str | None = None
    exchange: str | None = None
    is_valid: bool
    is_delisted: bool = False
    successor: str | None = None  # For renamed tickers


class TickerSearchResult(BaseModel):
    """Search results wrapper."""

    results: list[TickerInfo]
    query: str
```

**DynamoDB Cache Schema** (optional):
```
PK: TICKER#{symbol}
SK: METADATA

Attributes:
- symbol (S)
- company_name (S)
- exchange (S)
- is_valid (BOOL)
- is_delisted (BOOL)
- successor (S)
- cached_at (S): ISO8601
- ttl (N): epoch seconds (24h expiry)
```

---

## Phase 2 Entities

### Notification

**Source**: `tests/e2e/test_notifications.py`

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Notification(BaseModel):
    """User notification."""

    notification_id: str
    type: str  # "alert_trigger", "system", "digest"
    status: Literal["pending", "sent", "delivered", "failed", "read"]
    message: str
    created_at: datetime
    read: bool = False
    read_at: datetime | None = None

    # Alias for compatibility
    @property
    def id(self) -> str:
        return self.notification_id


class NotificationList(BaseModel):
    """Paginated notification list."""

    notifications: list[Notification]
    total: int
    limit: int
    offset: int
```

**DynamoDB Schema**:
```
PK: USER#{user_id}
SK: NOTIFICATION#{notification_id}

Attributes:
- notification_id (S)
- type (S)
- status (S)
- message (S)
- created_at (S): ISO8601
- read (BOOL)
- read_at (S): ISO8601 | null
```

---

### NotificationPreference

**Source**: `tests/e2e/test_notification_preferences.py`

```python
from pydantic import BaseModel


class NotificationPreference(BaseModel):
    """User notification preferences."""

    email_enabled: bool = True
    digest_enabled: bool = False
    digest_time: str = "09:00"  # HH:MM format
    timezone: str = "America/New_York"


class DigestSettings(BaseModel):
    """Digest email settings."""

    enabled: bool
    time: str  # HH:MM format
    timezone: str = "America/New_York"
```

**DynamoDB Schema**:
```
PK: USER#{user_id}
SK: PREFERENCES

Attributes:
- email_enabled (BOOL)
- digest_enabled (BOOL)
- digest_time (S)
- timezone (S)
```

---

### AlertQuota

**Source**: `tests/e2e/test_quota.py`

```python
from pydantic import BaseModel


class AlertQuota(BaseModel):
    """User alert email quota status."""

    used: int
    limit: int
    remaining: int  # Computed: max(0, limit - used)
    resets_at: str  # ISO8601 datetime
    is_exceeded: bool  # Computed: used >= limit

    @classmethod
    def compute(cls, used: int, limit: int, resets_at: str) -> "AlertQuota":
        return cls(
            used=used,
            limit=limit,
            remaining=max(0, limit - used),
            resets_at=resets_at,
            is_exceeded=used >= limit,
        )
```

**DynamoDB Schema**:
```
PK: USER#{user_id}
SK: QUOTA#alerts

Attributes:
- used (N)
- limit (N)
- resets_at (S): ISO8601
- period_start (S): ISO8601
```

---

## Phase 3 Entities

### MagicLinkToken

**Source**: `tests/e2e/test_auth_magic_link.py`

```python
from datetime import datetime

from pydantic import BaseModel


class MagicLinkRequest(BaseModel):
    """Request to send magic link."""

    email: str


class MagicLinkToken(BaseModel):
    """Magic link token (internal)."""

    token: str
    email: str
    expires_at: datetime
    used: bool = False
    anonymous_session_id: str | None = None


class MagicLinkVerifyRequest(BaseModel):
    """Request to verify magic link."""

    token: str
    anonymous_session_id: str | None = None


class MagicLinkVerifyResponse(BaseModel):
    """Successful verification response."""

    access_token: str
    refresh_token: str
    user_id: str
```

**DynamoDB Schema**:
```
PK: MAGICLINK#{token}
SK: TOKEN

Attributes:
- token (S)
- email (S)
- expires_at (S): ISO8601
- used (BOOL)
- anonymous_session_id (S): nullable
- ttl (N): epoch seconds (auto-delete after expiry)
```

---

## Entity Relationships

```
User (existing)
├── Configuration (existing)
│   └── Alert (new - Phase 1)
├── Notification (new - Phase 2)
├── NotificationPreference (new - Phase 2)
├── AlertQuota (new - Phase 2)
└── MagicLinkToken (new - Phase 3, temporary)

MarketStatus (computed, no persistence)
TickerInfo (cached, optional persistence)
```

---

## Validation Rules (from E2E tests)

### Alert
- `type` must be "sentiment" or "volatility"
- `threshold` for sentiment: typically -1.0 to 1.0
- `threshold` for volatility: ATR-based, positive float
- `condition` must be "above" or "below"

### Quota
- `remaining = max(0, limit - used)`
- `is_exceeded = (used >= limit)`
- `resets_at` must be valid ISO datetime in future
- `limit` typically 10-1000

### NotificationPreference
- `digest_time` must be HH:MM format
- `timezone` must be valid IANA timezone

### MagicLinkToken
- Token expires in 15 minutes
- Token can only be used once
- Rate limit: 1 per email per minute
