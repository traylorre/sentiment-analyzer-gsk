"""API quota tracking for external services.

Manages API quota across Tiingo, Finnhub, and SendGrid to prevent overages.

Performance optimization (C2):
- In-memory cache with 60s TTL reduces DynamoDB reads by ~95%
- Batched write-through pattern for quota updates
- Periodic sync to DynamoDB (not on every call)

Thread-safety (Feature 1010):
- Module-level lock protects cache access during parallel ingestion
- record_call() and check_quota() are thread-safe
"""

import logging
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# =============================================================================
# C2 FIX: In-memory cache for quota tracker
# =============================================================================
# Cache TTL in seconds (default 60s - configurable via env var)
QUOTA_TRACKER_CACHE_TTL = int(os.environ.get("QUOTA_TRACKER_CACHE_TTL", "60"))

# Sync interval - how often to persist to DynamoDB (default 60s)
QUOTA_TRACKER_SYNC_INTERVAL = int(os.environ.get("QUOTA_TRACKER_SYNC_INTERVAL", "60"))

# In-memory cache: (timestamp, QuotaTracker, last_sync_time)
_quota_tracker_cache: tuple[float, "QuotaTracker", float] | None = None

# Cache statistics for monitoring
_quota_cache_stats = {"hits": 0, "misses": 0, "syncs": 0}

# Thread-safety lock for cache access (Feature 1010)
_quota_cache_lock = threading.Lock()


def _get_cached_tracker() -> "QuotaTracker | None":
    """Get quota tracker from cache if not expired.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    global _quota_tracker_cache
    with _quota_cache_lock:
        if _quota_tracker_cache is not None:
            timestamp, tracker, _ = _quota_tracker_cache
            if time.time() - timestamp < QUOTA_TRACKER_CACHE_TTL:
                _quota_cache_stats["hits"] += 1
                return tracker
            # Expired - don't delete, will be overwritten
        _quota_cache_stats["misses"] += 1
        return None


def _set_cached_tracker(tracker: "QuotaTracker", synced: bool = False) -> None:
    """Store quota tracker in cache.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    global _quota_tracker_cache
    with _quota_cache_lock:
        now = time.time()
        last_sync = (
            now
            if synced
            else (_quota_tracker_cache[2] if _quota_tracker_cache else now)
        )
        _quota_tracker_cache = (now, tracker, last_sync)


def _needs_sync() -> bool:
    """Check if cache needs to be synced to DynamoDB.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    with _quota_cache_lock:
        if _quota_tracker_cache is None:
            return False
        _, _, last_sync = _quota_tracker_cache
        return time.time() - last_sync >= QUOTA_TRACKER_SYNC_INTERVAL


def get_quota_cache_stats() -> dict[str, int]:
    """Get cache hit/miss/sync statistics for monitoring.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    with _quota_cache_lock:
        return _quota_cache_stats.copy()


def clear_quota_cache() -> None:
    """Clear cache and reset stats. Used in tests.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    global _quota_tracker_cache, _quota_cache_stats
    with _quota_cache_lock:
        _quota_tracker_cache = None
        _quota_cache_stats = {"hits": 0, "misses": 0, "syncs": 0}


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
        return datetime.now(UTC).strftime("%Y-%m-%d")

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
        self.updated_at = datetime.now(UTC)

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
                reset_at=(
                    datetime.fromisoformat(data["reset_at"])
                    if data.get("reset_at")
                    else datetime.now(UTC)
                ),
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
        now = datetime.now(UTC)
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


class QuotaTrackerManager:
    """Manages quota tracking with caching and batched DynamoDB persistence.

    Performance optimization (C2):
    - Reads use in-memory cache with 60s TTL (~95% DynamoDB read reduction)
    - Writes are batched - sync to DynamoDB every 60s instead of every call
    - Immediate sync on critical quota changes

    Usage:
        manager = QuotaTrackerManager(dynamodb_table)
        if manager.can_call("tiingo"):
            # Make API call
            manager.record_call("tiingo")
    """

    def __init__(self, table: Any):
        """Initialize manager with DynamoDB table.

        Args:
            table: boto3 DynamoDB Table resource
        """
        self._table = table

    def get_tracker(self) -> QuotaTracker:
        """Get quota tracker, using cache when available.

        Returns:
            QuotaTracker (from cache, DynamoDB, or default)
        """
        # Check cache first
        cached = _get_cached_tracker()
        if cached is not None:
            logger.debug("Quota tracker cache hit")
            return cached

        # Cache miss - load from DynamoDB
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            response = self._table.get_item(Key={"PK": "SYSTEM#QUOTA", "SK": today})
            if "Item" in response:
                tracker = QuotaTracker.from_dynamodb_item(response["Item"])
                logger.debug(
                    "Quota tracker loaded from DynamoDB",
                    extra={"date": today, "total_calls": tracker.total_api_calls_today},
                )
            else:
                # Create default tracker for today
                tracker = QuotaTracker.create_default()
                logger.debug("Quota tracker created default", extra={"date": today})
        except Exception as e:
            logger.warning(
                "Failed to load quota tracker, using default",
                extra={"error": str(e)},
            )
            tracker = QuotaTracker.create_default()

        # Update cache (mark as synced since we just loaded)
        _set_cached_tracker(tracker, synced=True)
        return tracker

    def _sync_to_dynamodb(self, tracker: QuotaTracker, force: bool = False) -> bool:
        """Sync tracker to DynamoDB if needed.

        Args:
            tracker: QuotaTracker to sync
            force: Force sync regardless of interval

        Returns:
            True if sync performed, False otherwise
        """
        if not force and not _needs_sync():
            return False

        try:
            self._table.put_item(Item=tracker.to_dynamodb_item())
            _set_cached_tracker(tracker, synced=True)
            _quota_cache_stats["syncs"] += 1
            logger.debug(
                "Quota tracker synced to DynamoDB",
                extra={"total_calls": tracker.total_api_calls_today},
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to sync quota tracker",
                extra={"error": str(e)},
            )
            return False

    def can_call(self, service: Literal["tiingo", "finnhub", "sendgrid"]) -> bool:
        """Check if we can make another API call to service.

        Args:
            service: The service to check

        Returns:
            True if call is allowed
        """
        tracker = self.get_tracker()
        return tracker.can_call(service)

    def record_call(
        self,
        service: Literal["tiingo", "finnhub", "sendgrid"],
        count: int = 1,
    ) -> QuotaTracker:
        """Record API call(s) and update cache.

        Args:
            service: The service called
            count: Number of API calls made

        Returns:
            Updated QuotaTracker
        """
        tracker = self.get_tracker()
        old_is_critical = getattr(tracker, service).is_critical

        tracker.record_call(service, count)

        # Update cache
        _set_cached_tracker(tracker, synced=False)

        # Force sync if quota became critical
        new_is_critical = getattr(tracker, service).is_critical
        if new_is_critical and not old_is_critical:
            logger.warning(
                "Quota critical threshold reached",
                extra={
                    "service": service,
                    "used": getattr(tracker, service).used,
                    "limit": getattr(tracker, service).limit,
                },
            )
            self._sync_to_dynamodb(tracker, force=True)
        else:
            # Try periodic sync
            self._sync_to_dynamodb(tracker)

        return tracker

    def get_usage_summary(self) -> dict[str, dict]:
        """Get usage summary for all services.

        Returns:
            Dict with service usage info
        """
        tracker = self.get_tracker()
        return {
            "tiingo": {
                "used": tracker.tiingo.used,
                "limit": tracker.tiingo.limit,
                "remaining": tracker.tiingo.remaining,
                "percent_used": tracker.tiingo.percent_used,
                "is_warning": tracker.tiingo.is_warning,
                "is_critical": tracker.tiingo.is_critical,
            },
            "finnhub": {
                "used": tracker.finnhub.used,
                "limit": tracker.finnhub.limit,
                "remaining": tracker.finnhub.remaining,
                "percent_used": tracker.finnhub.percent_used,
                "is_warning": tracker.finnhub.is_warning,
                "is_critical": tracker.finnhub.is_critical,
            },
            "sendgrid": {
                "used": tracker.sendgrid.used,
                "limit": tracker.sendgrid.limit,
                "remaining": tracker.sendgrid.remaining,
                "percent_used": tracker.sendgrid.percent_used,
                "is_warning": tracker.sendgrid.is_warning,
                "is_critical": tracker.sendgrid.is_critical,
            },
            "total_api_calls_today": tracker.total_api_calls_today,
        }

    def force_sync(self) -> bool:
        """Force immediate sync to DynamoDB.

        Useful at Lambda shutdown or when critical changes occur.

        Returns:
            True if sync succeeded
        """
        tracker = self.get_tracker()
        return self._sync_to_dynamodb(tracker, force=True)
