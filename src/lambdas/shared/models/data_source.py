"""DataSourceConfig model for source availability tracking.

Configuration and runtime state for data sources (Tiingo, Finnhub).
Schema defined in specs/072-market-data-ingestion/contracts/data-source-config.schema.json
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApiConfig(BaseModel):
    """API-specific configuration for a data source."""

    base_url: str = Field(..., description="API base URL")
    timeout_seconds: int = Field(default=10, ge=1, le=60, description="Request timeout")
    rate_limit_per_minute: int = Field(
        default=60, ge=1, description="Max requests per minute"
    )


class DataSourceConfig(BaseModel):
    """Configuration and availability status for a data source.

    Used by FailoverOrchestrator to manage primary/secondary source selection.
    """

    source_id: Literal["tiingo", "finnhub"] = Field(
        ..., description="Unique source identifier"
    )
    display_name: str = Field(..., max_length=50, description="Human-readable name")
    priority: int = Field(..., ge=1, le=10, description="Priority order (1=primary)")
    is_available: bool = Field(
        default=True, description="Whether source is currently available"
    )
    last_success_at: datetime | None = Field(
        default=None, description="Last successful collection timestamp"
    )
    last_failure_at: datetime | None = Field(
        default=None, description="Last failed collection timestamp"
    )
    consecutive_failures: int = Field(
        default=0, ge=0, description="Current consecutive failure count"
    )
    failure_window_start: datetime | None = Field(
        default=None, description="Start of 15-minute failure tracking window"
    )
    api_config: ApiConfig | None = Field(
        default=None, description="API-specific configuration"
    )

    def record_success(self, at: datetime) -> "DataSourceConfig":
        """Record a successful collection, resetting failure tracking.

        Args:
            at: Timestamp of successful collection

        Returns:
            Updated DataSourceConfig with success recorded
        """
        return DataSourceConfig(
            source_id=self.source_id,
            display_name=self.display_name,
            priority=self.priority,
            is_available=True,
            last_success_at=at,
            last_failure_at=self.last_failure_at,
            consecutive_failures=0,
            failure_window_start=None,
            api_config=self.api_config,
        )

    def record_failure(
        self, at: datetime, window_minutes: int = 15, threshold: int = 3
    ) -> "DataSourceConfig":
        """Record a failed collection, updating failure tracking.

        If failures exceed threshold within window, source becomes unavailable.

        Args:
            at: Timestamp of failed collection
            window_minutes: Duration of failure tracking window
            threshold: Consecutive failures before marking unavailable

        Returns:
            Updated DataSourceConfig with failure recorded
        """
        # Start new window if none exists or previous window expired
        if self.failure_window_start is None:
            window_start = at
            failures = 1
        else:
            window_age = (at - self.failure_window_start).total_seconds() / 60
            if window_age > window_minutes:
                # Window expired, start fresh
                window_start = at
                failures = 1
            else:
                # Within window, increment
                window_start = self.failure_window_start
                failures = self.consecutive_failures + 1

        is_available = failures < threshold

        return DataSourceConfig(
            source_id=self.source_id,
            display_name=self.display_name,
            priority=self.priority,
            is_available=is_available,
            last_success_at=self.last_success_at,
            last_failure_at=at,
            consecutive_failures=failures,
            failure_window_start=window_start,
            api_config=self.api_config,
        )

    @classmethod
    def tiingo_default(cls) -> "DataSourceConfig":
        """Create default Tiingo configuration (primary source)."""
        return cls(
            source_id="tiingo",
            display_name="Tiingo",
            priority=1,
            api_config=ApiConfig(
                base_url="https://api.tiingo.com",
                timeout_seconds=10,
                rate_limit_per_minute=500,
            ),
        )

    @classmethod
    def finnhub_default(cls) -> "DataSourceConfig":
        """Create default Finnhub configuration (secondary source)."""
        return cls(
            source_id="finnhub",
            display_name="Finnhub",
            priority=2,
            api_config=ApiConfig(
                base_url="https://finnhub.io/api/v1",
                timeout_seconds=10,
                rate_limit_per_minute=60,
            ),
        )
