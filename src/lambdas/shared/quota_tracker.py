"""API quota tracking for external services.

Manages API quota across Tiingo, Finnhub, and SendGrid to prevent overages.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class APIQuotaUsage(BaseModel):
    """Track API quota usage per service."""

    service: Literal["tiingo", "finnhub", "sendgrid"]
    period: Literal["minute", "hour", "day", "month"]

    limit: int
    used: int
    remaining: int
    reset_at: datetime

    # Alert thresholds
    warn_threshold: float = 0.5  # 50%
    critical_threshold: float = 0.8  # 80%

    @property
    def percent_used(self) -> float:
        """Calculate percentage of quota used."""
        return (self.used / self.limit) * 100 if self.limit > 0 else 0

    @property
    def is_warning(self) -> bool:
        """Check if usage is at warning level."""
        return self.percent_used >= self.warn_threshold * 100

    @property
    def is_critical(self) -> bool:
        """Check if usage is at critical level."""
        return self.percent_used >= self.critical_threshold * 100


class QuotaTracker(BaseModel):
    """Manages API quota across all external services.

    Stored in DynamoDB with TTL for automatic cleanup.
    Tracks daily usage to prevent budget overruns.

    Service limits:
    - Tiingo: 500 symbols/month (free tier)
    - Finnhub: 60 calls/minute (free tier)
    - SendGrid: 100 emails/day (free tier)
    """

    tracker_id: str = "QUOTA_TRACKER"  # Singleton
    updated_at: datetime

    # Per-service quotas
    tiingo: APIQuotaUsage
    finnhub: APIQuotaUsage
    sendgrid: APIQuotaUsage

    # Aggregated metrics
    total_api_calls_today: int = 0
    estimated_daily_cost: float = 0.0

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return "SYSTEM#QUOTA"

    @property
    def sk(self) -> str:
        """DynamoDB sort key (daily partitioning)."""
        return datetime.utcnow().strftime("%Y-%m-%d")

    def can_call(self, service: Literal["tiingo", "finnhub", "sendgrid"]) -> bool:
        """Check if we can make another API call to service.

        Args:
            service: The service to check

        Returns:
            True if call is allowed, False if quota exhausted or critical
        """
        quota = getattr(self, service)
        return quota.remaining > 0 and not quota.is_critical

    def record_call(
        self, service: Literal["tiingo", "finnhub", "sendgrid"], count: int = 1
    ) -> None:
        """Record API call(s) to service.

        Args:
            service: The service called
            count: Number of API calls made
        """
        quota = getattr(self, service)
        quota.used += count
        quota.remaining = max(0, quota.limit - quota.used)
        self.total_api_calls_today += count
        self.updated_at = datetime.utcnow()

    def get_reserve_allocation(
        self, service: Literal["tiingo", "finnhub", "sendgrid"]
    ) -> int:
        """Get reserve quota allocation for critical operations.

        Reserves 10% of quota for high-priority operations like alerts.

        Args:
            service: The service to check

        Returns:
            Number of calls reserved for priority operations
        """
        quota = getattr(self, service)
        return int(quota.limit * 0.1)

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        # TTL: 7 days after creation
        ttl = int(self.updated_at.timestamp()) + (7 * 86400)

        def serialize_quota(quota: APIQuotaUsage) -> dict:
            """Serialize quota with ISO datetime and convert floats to str."""
            data = quota.model_dump()
            data["reset_at"] = quota.reset_at.isoformat()
            # Convert floats to strings for DynamoDB compatibility
            data["warn_threshold"] = str(quota.warn_threshold)
            data["critical_threshold"] = str(quota.critical_threshold)
            return data

        return {
            "PK": self.pk,
            "SK": self.sk,
            "tracker_id": self.tracker_id,
            "updated_at": self.updated_at.isoformat(),
            "tiingo": serialize_quota(self.tiingo),
            "finnhub": serialize_quota(self.finnhub),
            "sendgrid": serialize_quota(self.sendgrid),
            "total_api_calls_today": self.total_api_calls_today,
            "estimated_daily_cost": str(self.estimated_daily_cost),
            "ttl": ttl,
            "entity_type": "QUOTA_TRACKER",
        }

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "QuotaTracker":
        """Create QuotaTracker from DynamoDB item."""
        tiingo_data = item.get("tiingo", {})
        finnhub_data = item.get("finnhub", {})
        sendgrid_data = item.get("sendgrid", {})

        def parse_quota(data: dict, service: str, defaults: dict) -> APIQuotaUsage:
            """Parse quota data from DynamoDB item."""
            return APIQuotaUsage(
                service=service,
                period=data.get("period", defaults["period"]),
                limit=data.get("limit", defaults["limit"]),
                used=data.get("used", 0),
                remaining=data.get("remaining", defaults["limit"]),
                reset_at=datetime.fromisoformat(data["reset_at"])
                if data.get("reset_at")
                else datetime.utcnow(),
                warn_threshold=float(data.get("warn_threshold", 0.5)),
                critical_threshold=float(data.get("critical_threshold", 0.8)),
            )

        return cls(
            tracker_id=item.get("tracker_id", "QUOTA_TRACKER"),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            tiingo=parse_quota(
                tiingo_data, "tiingo", {"period": "month", "limit": 500}
            ),
            finnhub=parse_quota(
                finnhub_data, "finnhub", {"period": "minute", "limit": 60}
            ),
            sendgrid=parse_quota(
                sendgrid_data, "sendgrid", {"period": "day", "limit": 100}
            ),
            total_api_calls_today=item.get("total_api_calls_today", 0),
            estimated_daily_cost=float(item.get("estimated_daily_cost", 0)),
        )

    @classmethod
    def create_default(cls) -> "QuotaTracker":
        """Create a default quota tracker with standard limits."""
        now = datetime.utcnow()
        return cls(
            updated_at=now,
            tiingo=APIQuotaUsage(
                service="tiingo",
                period="month",
                limit=500,
                used=0,
                remaining=500,
                reset_at=now,
            ),
            finnhub=APIQuotaUsage(
                service="finnhub",
                period="minute",
                limit=60,
                used=0,
                remaining=60,
                reset_at=now,
            ),
            sendgrid=APIQuotaUsage(
                service="sendgrid",
                period="day",
                limit=100,
                used=0,
                remaining=100,
                reset_at=now,
            ),
        )
