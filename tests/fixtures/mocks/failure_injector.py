"""Configurable failure injection for mock adapters.

Used to simulate various failure modes from external APIs including:
- HTTP error codes (4xx, 5xx)
- Connection errors (timeout, refused, DNS)
- Malformed responses (invalid JSON, empty, truncated)
- Field-level errors (missing fields, null values, NaN/Infinity)
"""

from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from src.lambdas.shared.adapters.base import AdapterError, RateLimitError

# Connection error types
ConnectionErrorType = Literal["timeout", "refused", "dns"]

# Malformed response types
MalformedResponseType = Literal[
    "invalid_json", "empty_object", "empty_array", "html", "truncated", "extra_fields"
]


@dataclass
class FailureInjector:
    """Configurable failure injection for mock adapters.

    Attributes:
        http_error: HTTP status code to return (400, 401, 404, 429, 500, 502, 503, 504)
        connection_error: Type of connection error ("timeout", "refused", "dns")
        malformed_response: Type of malformed response ("invalid_json", "empty", etc.)
        missing_fields: List of field names to omit from response
        invalid_values: Dict mapping field names to invalid values (None, NaN, Infinity)
        latency_ms: Simulated response latency in milliseconds
        call_count_threshold: Fail after N successful calls (for fallback testing)
        retry_after_seconds: Value for Retry-After header when http_error=429

    Usage:
        injector = FailureInjector(http_error=500)
        mock_tiingo = MockTiingoAdapter(failure_injector=injector)
    """

    http_error: int | None = None
    connection_error: ConnectionErrorType | None = None
    malformed_response: MalformedResponseType | None = None
    missing_fields: list[str] = field(default_factory=list)
    invalid_values: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    call_count_threshold: int | None = None
    retry_after_seconds: int = 60

    # Internal state
    _call_count: int = field(default=0, init=False)

    def reset(self) -> None:
        """Reset internal state (call count)."""
        self._call_count = 0

    def increment_call_count(self) -> int:
        """Increment and return call count."""
        self._call_count += 1
        return self._call_count

    @property
    def call_count(self) -> int:
        """Get current call count."""
        return self._call_count

    def should_fail(self) -> bool:
        """Check if the injector should trigger a failure.

        Returns:
            True if any failure condition is configured
        """
        # Check call count threshold
        if (
            self.call_count_threshold is not None
            and self._call_count >= self.call_count_threshold
        ):
            return True

        # Check for configured failures
        return any(
            [
                self.http_error is not None,
                self.connection_error is not None,
                self.malformed_response is not None,
            ]
        )

    def should_fail_after_threshold(self) -> bool:
        """Check if failure should occur due to call count threshold.

        Returns:
            True if call count has exceeded threshold
        """
        if self.call_count_threshold is None:
            return False
        return self._call_count >= self.call_count_threshold

    def raise_if_configured(self) -> None:
        """Raise appropriate exception if failure is configured.

        Raises:
            RateLimitError: For HTTP 429
            AdapterError: For other HTTP errors
            httpx.TimeoutException: For timeout errors
            httpx.ConnectError: For connection refused
            httpx.ConnectError: For DNS failures
        """
        # Check HTTP errors
        if self.http_error is not None:
            if self.http_error == 429:
                raise RateLimitError(
                    "Rate limit exceeded (injected)",
                    retry_after=self.retry_after_seconds,
                )
            raise AdapterError(
                f"HTTP {self.http_error} error (injected)",
            )

        # Check connection errors
        if self.connection_error == "timeout":
            raise httpx.TimeoutException("Connection timed out (injected)")
        if self.connection_error == "refused":
            raise httpx.ConnectError("Connection refused (injected)")
        if self.connection_error == "dns":
            raise httpx.ConnectError("DNS resolution failed (injected)")

    def get_malformed_response(self) -> Any:
        """Get a malformed response based on configuration.

        Returns:
            Malformed response data based on malformed_response type

        Raises:
            ValueError: If no malformed_response is configured
        """
        if self.malformed_response is None:
            raise ValueError("No malformed_response configured")

        if self.malformed_response == "invalid_json":
            return "{invalid json"
        if self.malformed_response == "empty_object":
            return {}
        if self.malformed_response == "empty_array":
            return []
        if self.malformed_response == "html":
            return "<html><body>Error 500</body></html>"
        if self.malformed_response == "truncated":
            return '{"date": "2024-01-01", "open": 100.0, "high":'
        if self.malformed_response == "extra_fields":
            return {
                "date": "2024-01-01",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 1000000,
                "unexpected_field": "should_be_ignored",
                "another_extra": 42,
            }

        raise ValueError(f"Unknown malformed_response type: {self.malformed_response}")

    def modify_candle(self, candle: dict) -> dict:
        """Modify a candle by removing fields or injecting invalid values.

        Args:
            candle: Original candle data

        Returns:
            Modified candle with configured field removals and value injections
        """
        modified = candle.copy()

        # Remove configured fields
        for field_name in self.missing_fields:
            modified.pop(field_name, None)

        # Inject invalid values
        for field_name, value in self.invalid_values.items():
            modified[field_name] = value

        return modified


# Pre-configured failure injectors for common test scenarios
def create_http_500_injector() -> FailureInjector:
    """Create injector that returns HTTP 500."""
    return FailureInjector(http_error=500)


def create_http_502_injector() -> FailureInjector:
    """Create injector that returns HTTP 502 Bad Gateway."""
    return FailureInjector(http_error=502)


def create_http_503_injector() -> FailureInjector:
    """Create injector that returns HTTP 503 Service Unavailable."""
    return FailureInjector(http_error=503)


def create_http_504_injector() -> FailureInjector:
    """Create injector that returns HTTP 504 Gateway Timeout."""
    return FailureInjector(http_error=504)


def create_http_429_injector(retry_after: int = 60) -> FailureInjector:
    """Create injector that returns HTTP 429 Rate Limited."""
    return FailureInjector(http_error=429, retry_after_seconds=retry_after)


def create_timeout_injector() -> FailureInjector:
    """Create injector that simulates connection timeout."""
    return FailureInjector(connection_error="timeout")


def create_connection_refused_injector() -> FailureInjector:
    """Create injector that simulates connection refused."""
    return FailureInjector(connection_error="refused")


def create_dns_failure_injector() -> FailureInjector:
    """Create injector that simulates DNS resolution failure."""
    return FailureInjector(connection_error="dns")


def create_invalid_json_injector() -> FailureInjector:
    """Create injector that returns invalid JSON."""
    return FailureInjector(malformed_response="invalid_json")


def create_empty_response_injector() -> FailureInjector:
    """Create injector that returns empty object."""
    return FailureInjector(malformed_response="empty_object")


def create_empty_array_injector() -> FailureInjector:
    """Create injector that returns empty array."""
    return FailureInjector(malformed_response="empty_array")


def create_html_error_injector() -> FailureInjector:
    """Create injector that returns HTML error page."""
    return FailureInjector(malformed_response="html")


def create_truncated_json_injector() -> FailureInjector:
    """Create injector that returns truncated JSON."""
    return FailureInjector(malformed_response="truncated")


def create_missing_fields_injector(fields: list[str]) -> FailureInjector:
    """Create injector that removes specified fields from responses."""
    return FailureInjector(missing_fields=fields)


def create_null_values_injector(fields: list[str]) -> FailureInjector:
    """Create injector that sets specified fields to None."""
    return FailureInjector(invalid_values={f: None for f in fields})


def create_nan_values_injector(fields: list[str]) -> FailureInjector:
    """Create injector that sets specified fields to NaN."""
    return FailureInjector(invalid_values={f: float("nan") for f in fields})


def create_infinity_values_injector(fields: list[str]) -> FailureInjector:
    """Create injector that sets specified fields to Infinity."""
    return FailureInjector(invalid_values={f: float("inf") for f in fields})


def create_negative_prices_injector() -> FailureInjector:
    """Create injector that sets price fields to negative values."""
    return FailureInjector(
        invalid_values={"open": -100.0, "high": -95.0, "low": -110.0, "close": -98.0}
    )


def create_threshold_injector(threshold: int) -> FailureInjector:
    """Create injector that fails after N successful calls.

    Useful for testing fallback behavior where primary source
    works initially but fails after a threshold.
    """
    return FailureInjector(call_count_threshold=threshold)
