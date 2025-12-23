"""Shared models for Feature 006: Financial News Sentiment Dashboard.

This module exports all entity models used across Lambda functions:
- User: Dashboard user (anonymous or authenticated)
- Configuration: User's saved ticker configurations
- AlertRule: User-defined alert rules for tickers
- Notification: Sent notification records
- SentimentResult: Sentiment analysis results
- VolatilityMetric: ATR volatility calculations
- MagicLinkToken: Magic link authentication tokens
"""

from src.lambdas.shared.models.alert_rule import (
    ALERT_LIMITS,
    AlertEvaluation,
    AlertRule,
    AlertRuleCreate,
)
from src.lambdas.shared.models.collection_event import CollectionEvent
from src.lambdas.shared.models.configuration import (
    CONFIG_LIMITS,
    Configuration,
    ConfigurationCreate,
    ConfigurationUpdate,
    Ticker,
)
from src.lambdas.shared.models.data_source import (
    ApiConfig,
    DataSourceConfig,
)
from src.lambdas.shared.models.magic_link_token import (
    SESSION_LIMITS,
    MagicLinkToken,
)
from src.lambdas.shared.models.news_item import (
    NewsItem,
    SentimentScore,
)
from src.lambdas.shared.models.notification import (
    DigestSettings,
    Notification,
)
from src.lambdas.shared.models.ohlc import (
    RESOLUTION_MAX_DAYS,
    TIME_RANGE_DAYS,
    OHLCResolution,
    OHLCResponse,
    PriceCandle,
    TimeRange,
)
from src.lambdas.shared.models.sentiment_history import (
    SentimentHistoryResponse,
    SentimentPoint,
    SentimentSourceType,
)
from src.lambdas.shared.models.sentiment_result import (
    SentimentResult,
    SentimentSource,
    sentiment_label_from_score,
)
from src.lambdas.shared.models.user import (
    User,
    UserCreate,
    UserUpgrade,
)
from src.lambdas.shared.models.volatility_metric import (
    OHLCCandle,
    VolatilityMetric,
)

__all__ = [
    # User models
    "User",
    "UserCreate",
    "UserUpgrade",
    # Configuration models
    "Configuration",
    "ConfigurationCreate",
    "ConfigurationUpdate",
    "Ticker",
    "CONFIG_LIMITS",
    # Alert models
    "AlertRule",
    "AlertRuleCreate",
    "AlertEvaluation",
    "ALERT_LIMITS",
    # Notification models
    "Notification",
    "DigestSettings",
    # Sentiment models
    "SentimentResult",
    "SentimentSource",
    "sentiment_label_from_score",
    # Volatility models
    "VolatilityMetric",
    "OHLCCandle",
    # Auth models
    "MagicLinkToken",
    "SESSION_LIMITS",
    # OHLC models
    "OHLCResolution",
    "OHLCResponse",
    "PriceCandle",
    "TimeRange",
    "TIME_RANGE_DAYS",
    "RESOLUTION_MAX_DAYS",
    # Sentiment history models
    "SentimentHistoryResponse",
    "SentimentPoint",
    "SentimentSourceType",
    # Ingestion models (Feature 072)
    "NewsItem",
    "SentimentScore",
    "CollectionEvent",
    "DataSourceConfig",
    "ApiConfig",
]
