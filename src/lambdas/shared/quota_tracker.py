"""API quota tracking for external services.

Manages API quota across Tiingo, Finnhub, and SendGrid to prevent overages.

Performance optimization (C2):
- In-memory read cache with 10s TTL reduces DynamoDB reads
- Atomic DynamoDB counters for cross-instance write accuracy (Feature 1224)
- Full tracker sync to DynamoDB every 60s for metadata/thresholds

Feature 1224 (Cache Architecture Audit):
- Replaced batched put_item() sync with per-call atomic update_item(ADD)
- Cross-instance accuracy within 10% at 20 concurrent instances
- 25% rate reduction + alert on DynamoDB disconnection
- Flat atomic counter fields (tiingo_used, finnhub_used, sendgrid_used)

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
# Cache and sync configuration
# =============================================================================
# Read cache TTL (default 10s — Feature 1224: reduced from 60s for fresher reads)
QUOTA_TRACKER_CACHE_TTL = int(os.environ.get("QUOTA_TRACKER_CACHE_TTL", "10"))

# Full sync interval - persist complete tracker to DynamoDB (default 60s)
QUOTA_TRACKER_SYNC_INTERVAL = int(os.environ.get("QUOTA_TRACKER_SYNC_INTERVAL", "60"))

# In-memory cache: (timestamp, QuotaTracker, last_sync_time)
_quota_tracker_cache: tuple[float, "QuotaTracker", float] | None = None

# Cache statistics for monitoring
_quota_cache_stats = {"hits": 0, "misses": 0, "syncs": 0, "atomic_writes": 0}

# Thread-safety lock for cache access (Feature 1010, 1179)
# RLock allows same thread to acquire lock multiple times (reentrant)
# This is needed because record_call() wraps the full read-modify-write
# cycle, but the helper functions also acquire the lock internally.
_quota_cache_lock = threading.RLock()

# Feature 1224: Reduced-rate mode when DynamoDB is unreachable
_reduced_rate_mode = False
_reduced_rate_since: float | None = None
_last_disconnected_alert: float = 0.0
REDUCED_RATE_FRACTION = 0.25  # 25% of normal rate
DISCONNECTED_ALERT_INTERVAL = 300  # Max one alert per 5 minutes


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


def _enter_reduced_rate_mode() -> None:
    """Enter 25% reduced-rate mode when DynamoDB is unreachable (Feature 1224).

    Emits QuotaTracker/Disconnected metric (max once per 5 minutes).
    """
    global _reduced_rate_mode, _reduced_rate_since, _last_disconnected_alert
    with _quota_cache_lock:
        if not _reduced_rate_mode:
            _reduced_rate_mode = True
            _reduced_rate_since = time.time()
            logger.warning("Entering reduced-rate mode (25%) — DynamoDB unreachable")

        # Emit alert metric (spam-protected)
        now = time.time()
        if now - _last_disconnected_alert >= DISCONNECTED_ALERT_INTERVAL:
            _last_disconnected_alert = now
            try:
                from src.lib.metrics import emit_metric

                emit_metric("QuotaTracker/Disconnected", 1.0)
            except Exception:
                logger.debug("Failed to emit disconnected alert", exc_info=True)


def _exit_reduced_rate_mode() -> None:
    """Exit reduced-rate mode when DynamoDB becomes reachable again."""
    global _reduced_rate_mode, _reduced_rate_since
    with _quota_cache_lock:
        if _reduced_rate_mode:
            duration = time.time() - (_reduced_rate_since or 0)
            logger.info(
                "Exiting reduced-rate mode — DynamoDB reachable",
                extra={"duration_seconds": round(duration, 1)},
            )
            _reduced_rate_mode = False
            _reduced_rate_since = None


def clear_quota_cache() -> None:
    """Clear cache and reset stats. Used in tests.

    Thread-safe: Uses _quota_cache_lock for synchronized access.
    """
    global _quota_tracker_cache, _quota_cache_stats
    global _reduced_rate_mode, _reduced_rate_since, _last_disconnected_alert
    with _quota_cache_lock:
        _quota_tracker_cache = None
        _quota_cache_stats = {"hits": 0, "misses": 0, "syncs": 0, "atomic_writes": 0}
        _reduced_rate_mode = False
        _reduced_rate_since = None
        _last_disconnected_alert = 0.0


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
        """Create QuotaTracker from DynamoDB item.

        Feature 1224: Prefers flat atomic counter fields (tiingo_used, etc.)
        over nested map values. Falls back to nested values for backward
        compatibility with items written before atomic counters were added.
        """
        tiingo_data = item.get("tiingo", {})
        finnhub_data = item.get("finnhub", {})
        sendgrid_data = item.get("sendgrid", {})

        # Feature 1224: Override nested 'used' with flat atomic counter if present
        for service, data in [
            ("tiingo", tiingo_data),
            ("finnhub", finnhub_data),
            ("sendgrid", sendgrid_data),
        ]:
            atomic_used = item.get(f"{service}_used")
            if atomic_used is not None:
                data["used"] = int(atomic_used)
                # Recalculate remaining from the accurate atomic counter
                limit = data.get("limit", 0)
                data["remaining"] = max(0, limit - int(atomic_used))

        # Override total_api_calls_today with atomic value if present
        atomic_total = item.get("total_api_calls_today")
        if atomic_total is not None:
            item["total_api_calls_today"] = int(atomic_total)

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

        Feature 1224: Uses ConsistentRead for accurate atomic counter values.

        Returns:
            QuotaTracker (from cache, DynamoDB, or default)
        """
        # Check cache first
        cached = _get_cached_tracker()
        if cached is not None:
            logger.debug("Quota tracker cache hit")
            return cached

        # Cache miss - load from DynamoDB with ConsistentRead
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            response = self._table.get_item(
                Key={"PK": "SYSTEM#QUOTA", "SK": today},
                ConsistentRead=True,
            )
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

            # DynamoDB is reachable — exit reduced-rate mode if active
            _exit_reduced_rate_mode()

        except Exception as e:
            logger.warning(
                "Failed to load quota tracker, using default",
                extra={"error": str(e)},
            )
            tracker = QuotaTracker.create_default()

        # Update cache (mark as synced since we just loaded)
        _set_cached_tracker(tracker, synced=True)
        return tracker

    def _atomic_increment_usage(
        self,
        service: Literal["tiingo", "finnhub", "sendgrid"],
        count: int = 1,
    ) -> None:
        """Atomically increment usage counter in DynamoDB.

        Feature 1224: Uses DynamoDB ADD operation for immediate cross-instance
        visibility. This is the write path — every API call increments the
        shared counter atomically.

        The flat fields (tiingo_used, finnhub_used, sendgrid_used) are the
        source of truth for cross-instance quota tracking. The nested
        structures are updated by the periodic full sync.

        Args:
            service: API service name
            count: Number of calls to record
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        self._table.update_item(
            Key={"PK": "SYSTEM#QUOTA", "SK": today},
            UpdateExpression=(
                "ADD #used :count, #total :count "
                "SET #updated = :now, #ttl = if_not_exists(#ttl, :ttl_val), "
                "#entity = if_not_exists(#entity, :entity_val)"
            ),
            ExpressionAttributeNames={
                "#used": f"{service}_used",
                "#total": "total_api_calls_today",
                "#updated": "updated_at",
                "#ttl": "ttl",
                "#entity": "entity_type",
            },
            ExpressionAttributeValues={
                ":count": count,
                ":now": datetime.now(UTC).isoformat(),
                ":ttl_val": int(time.time()) + 7 * 86400,
                ":entity_val": "QUOTA_TRACKER",
            },
        )
        _quota_cache_stats["atomic_writes"] += 1

    def _sync_to_dynamodb(self, tracker: QuotaTracker, force: bool = False) -> bool:
        """Sync full tracker to DynamoDB if needed.

        This writes the complete tracker (with metadata, thresholds, etc.)
        for dashboards and monitoring. The atomic counters handle accuracy;
        this sync handles metadata richness.

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

        Feature 1224: In reduced-rate mode, allows only 25% of quota.

        Args:
            service: The service to check

        Returns:
            True if call is allowed
        """
        tracker = self.get_tracker()

        if _reduced_rate_mode:
            # In reduced-rate mode, enforce 25% of limit
            quota = getattr(tracker, service)
            reduced_limit = int(quota.limit * REDUCED_RATE_FRACTION)
            return quota.used < reduced_limit

        return tracker.can_call(service)

    def record_call(
        self,
        service: Literal["tiingo", "finnhub", "sendgrid"],
        count: int = 1,
    ) -> QuotaTracker:
        """Record API call(s) with atomic DynamoDB increment.

        Feature 1224: Every call atomically increments the shared DynamoDB
        counter for immediate cross-instance visibility. Falls back to 25%
        rate reduction if DynamoDB is unreachable.

        Thread-safe: Uses _quota_cache_lock to protect the local cache
        read-modify-write cycle (Feature 1179).

        Args:
            service: The service called
            count: Number of API calls made

        Returns:
            Updated QuotaTracker
        """
        # Step 1: Atomic DynamoDB increment (immediate cross-instance visibility)
        try:
            self._atomic_increment_usage(service, count)
            _exit_reduced_rate_mode()
        except Exception as e:
            logger.error(
                "Atomic quota increment failed — entering reduced-rate mode",
                extra={"service": service, "error": str(e)},
            )
            _enter_reduced_rate_mode()

        # Step 2: Update local cache
        with _quota_cache_lock:
            tracker = self.get_tracker()
            old_is_critical = getattr(tracker, service).is_critical

            tracker.record_call(service, count)
            _set_cached_tracker(tracker, synced=False)

            new_is_critical = getattr(tracker, service).is_critical

        # Step 3: Emit threshold warning if quota became critical
        if new_is_critical and not old_is_critical:
            logger.warning(
                "Quota critical threshold reached (80%)",
                extra={
                    "service": service,
                    "used": getattr(tracker, service).used,
                    "limit": getattr(tracker, service).limit,
                },
            )
            self._emit_threshold_warning(service)
            self._sync_to_dynamodb(tracker, force=True)
        else:
            self._sync_to_dynamodb(tracker)

        return tracker

    def is_reduced_rate(self) -> bool:
        """Check if this instance is in reduced-rate mode (Feature 1224).

        When DynamoDB is unreachable, instances reduce API call rate to 25%
        to prevent quota overages.

        Returns:
            True if in reduced-rate mode
        """
        return _reduced_rate_mode

    def _emit_threshold_warning(
        self, service: Literal["tiingo", "finnhub", "sendgrid"]
    ) -> None:
        """Emit QuotaTracker/ThresholdWarning metric (Feature 1224)."""
        try:
            from src.lib.metrics import emit_metric

            emit_metric(
                "QuotaTracker/ThresholdWarning",
                1.0,
                dimensions={"Service": service},
            )
        except Exception:
            logger.debug("Failed to emit threshold warning metric", exc_info=True)

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
