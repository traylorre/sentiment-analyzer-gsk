"""Circuit breaker pattern for external API resilience.

Prevents cascading failures when external APIs (Tiingo, Finnhub, SendGrid) are down.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CircuitBreakerState(BaseModel):
    """Per-API circuit breaker state.

    State machine:
    - closed: Normal operation, requests allowed
    - open: Circuit tripped after failures, requests blocked
    - half_open: Testing if service has recovered

    Configuration:
    - failure_threshold: Number of failures to trip circuit (default: 5)
    - failure_window_seconds: Time window for failure counting (default: 300s)
    - recovery_timeout_seconds: How long to wait before testing (default: 60s)
    """

    service: Literal["tiingo", "finnhub", "sendgrid"]
    state: Literal["closed", "open", "half_open"] = "closed"

    # Configuration
    failure_threshold: int = 5
    failure_window_seconds: int = 300  # 5 minutes
    recovery_timeout_seconds: int = 60

    # State tracking
    failure_count: int = 0
    last_failure_at: datetime | None = None
    opened_at: datetime | None = None
    last_success_at: datetime | None = None

    # Metrics
    total_failures: int = 0
    total_opens: int = 0
    total_recoveries: int = 0

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"CIRCUIT#{self.service}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return "STATE"

    def record_success(self) -> None:
        """Record successful API call."""
        self.last_success_at = datetime.utcnow()
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0
            self.total_recoveries += 1

    def record_failure(self) -> None:
        """Record failed API call."""
        now = datetime.utcnow()
        self.last_failure_at = now
        self.total_failures += 1

        # Reset count if outside failure window
        if (
            self.opened_at
            and (now - self.opened_at).total_seconds() > self.failure_window_seconds
        ):
            self.failure_count = 1
        else:
            self.failure_count += 1

        # Trip circuit breaker
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.opened_at = now
            self.total_opens += 1

    def can_execute(self) -> bool:
        """Check if request should be allowed.

        Returns:
            True if request can proceed, False if circuit is open
        """
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout has passed
            if self.opened_at:
                elapsed = (datetime.utcnow() - self.opened_at).total_seconds()
                if elapsed >= self.recovery_timeout_seconds:
                    self.state = "half_open"
                    return True
            return False

        # half_open - allow one request to test
        return True

    def get_fallback_message(self) -> str:
        """Message to show when circuit is open."""
        return (
            f"{self.service.title()} is temporarily unavailable. Showing cached data."
        )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        item = {
            "PK": self.pk,
            "SK": self.sk,
            "service": self.service,
            "state": self.state,
            "failure_threshold": self.failure_threshold,
            "failure_window_seconds": self.failure_window_seconds,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "failure_count": self.failure_count,
            "total_failures": self.total_failures,
            "total_opens": self.total_opens,
            "total_recoveries": self.total_recoveries,
            "entity_type": "CIRCUIT_BREAKER",
        }
        if self.last_failure_at:
            item["last_failure_at"] = self.last_failure_at.isoformat()
        if self.opened_at:
            item["opened_at"] = self.opened_at.isoformat()
        if self.last_success_at:
            item["last_success_at"] = self.last_success_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "CircuitBreakerState":
        """Create CircuitBreakerState from DynamoDB item."""
        last_failure_at = None
        opened_at = None
        last_success_at = None

        if item.get("last_failure_at"):
            last_failure_at = datetime.fromisoformat(item["last_failure_at"])
        if item.get("opened_at"):
            opened_at = datetime.fromisoformat(item["opened_at"])
        if item.get("last_success_at"):
            last_success_at = datetime.fromisoformat(item["last_success_at"])

        return cls(
            service=item["service"],
            state=item.get("state", "closed"),
            failure_threshold=item.get("failure_threshold", 5),
            failure_window_seconds=item.get("failure_window_seconds", 300),
            recovery_timeout_seconds=item.get("recovery_timeout_seconds", 60),
            failure_count=item.get("failure_count", 0),
            last_failure_at=last_failure_at,
            opened_at=opened_at,
            last_success_at=last_success_at,
            total_failures=item.get("total_failures", 0),
            total_opens=item.get("total_opens", 0),
            total_recoveries=item.get("total_recoveries", 0),
        )

    @classmethod
    def create_default(
        cls, service: Literal["tiingo", "finnhub", "sendgrid"]
    ) -> "CircuitBreakerState":
        """Create a default circuit breaker for a service."""
        return cls(service=service)
