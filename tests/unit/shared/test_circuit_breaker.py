"""Unit tests for CircuitBreakerState."""

from datetime import UTC, datetime, timedelta

from src.lambdas.shared.circuit_breaker import CircuitBreakerState


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState class."""

    def test_create_default(self):
        """Test creating default circuit breaker."""
        cb = CircuitBreakerState.create_default("tiingo")

        assert cb.service == "tiingo"
        assert cb.state == "closed"
        assert cb.failure_threshold == 5
        assert cb.failure_count == 0
        assert cb.can_execute() is True

    def test_initial_state_is_closed(self):
        """Test that initial state allows requests."""
        cb = CircuitBreakerState(service="finnhub")

        assert cb.state == "closed"
        assert cb.can_execute() is True

    def test_record_success_updates_timestamp(self):
        """Test recording success updates last_success_at."""
        cb = CircuitBreakerState(service="tiingo")

        cb.record_success()

        assert cb.last_success_at is not None
        assert cb.state == "closed"

    def test_record_failure_increments_count(self):
        """Test recording failure increments failure count."""
        cb = CircuitBreakerState(service="tiingo")

        cb.record_failure()

        assert cb.failure_count == 1
        assert cb.total_failures == 1
        assert cb.last_failure_at is not None

    def test_circuit_trips_after_threshold(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreakerState(service="tiingo", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == "open"
        assert cb.total_opens == 1
        assert cb.can_execute() is False

    def test_open_circuit_blocks_requests(self):
        """Test that open circuit blocks requests."""
        cb = CircuitBreakerState(service="sendgrid", failure_threshold=2)

        cb.record_failure()
        cb.record_failure()

        assert cb.state == "open"
        assert cb.can_execute() is False

    def test_circuit_transitions_to_half_open(self):
        """Test circuit transitions to half_open after recovery timeout."""
        cb = CircuitBreakerState(
            service="tiingo",
            failure_threshold=2,
            recovery_timeout_seconds=0,  # Immediate recovery for testing
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.state == "open"

        # With 0 second timeout, should transition immediately
        cb.opened_at = datetime.now(UTC) - timedelta(seconds=1)
        assert cb.can_execute() is True
        assert cb.state == "half_open"

    def test_success_in_half_open_closes_circuit(self):
        """Test successful request in half_open closes circuit."""
        cb = CircuitBreakerState(service="finnhub")
        cb.state = "half_open"
        cb.failure_count = 3

        cb.record_success()

        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.total_recoveries == 1

    def test_failure_in_half_open_reopens_circuit(self):
        """Test failure in half_open reopens circuit."""
        cb = CircuitBreakerState(service="finnhub", failure_threshold=1)
        cb.state = "half_open"

        cb.record_failure()

        assert cb.state == "open"
        assert cb.total_opens == 1

    def test_failure_window_resets_count(self):
        """Test failure count resets after window expires."""
        cb = CircuitBreakerState(
            service="tiingo",
            failure_threshold=5,
            failure_window_seconds=10,
        )

        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        # Simulate time passing outside window
        cb.opened_at = datetime.now(UTC) - timedelta(seconds=20)
        cb.record_failure()

        # Count should reset to 1
        assert cb.failure_count == 1

    def test_fallback_message(self):
        """Test fallback message is service-specific."""
        cb = CircuitBreakerState(service="tiingo")

        assert "Tiingo" in cb.get_fallback_message()
        assert "unavailable" in cb.get_fallback_message()

    def test_pk_sk_properties(self):
        """Test DynamoDB key properties."""
        cb = CircuitBreakerState(service="sendgrid")

        assert cb.pk == "CIRCUIT#sendgrid"
        assert cb.sk == "STATE"

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item."""
        cb = CircuitBreakerState(service="tiingo")
        cb.record_failure()

        item = cb.to_dynamodb_item()

        assert item["PK"] == "CIRCUIT#tiingo"
        assert item["SK"] == "STATE"
        assert item["service"] == "tiingo"
        assert item["state"] == "closed"
        assert item["failure_count"] == 1
        assert item["entity_type"] == "CIRCUIT_BREAKER"
        assert "last_failure_at" in item

    def test_from_dynamodb_item(self):
        """Test creating from DynamoDB item."""
        now = datetime.now(UTC)
        item = {
            "PK": "CIRCUIT#finnhub",
            "SK": "STATE",
            "service": "finnhub",
            "state": "open",
            "failure_threshold": 10,
            "failure_window_seconds": 600,
            "recovery_timeout_seconds": 120,
            "failure_count": 5,
            "last_failure_at": now.isoformat(),
            "opened_at": now.isoformat(),
            "total_failures": 15,
            "total_opens": 3,
            "total_recoveries": 2,
        }

        cb = CircuitBreakerState.from_dynamodb_item(item)

        assert cb.service == "finnhub"
        assert cb.state == "open"
        assert cb.failure_threshold == 10
        assert cb.failure_count == 5
        assert cb.total_failures == 15
        assert cb.total_opens == 3
        assert cb.total_recoveries == 2

    def test_roundtrip_serialization(self):
        """Test serialization roundtrip."""
        cb = CircuitBreakerState(service="sendgrid")
        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        item = cb.to_dynamodb_item()
        restored = CircuitBreakerState.from_dynamodb_item(item)

        assert restored.service == cb.service
        assert restored.state == cb.state
        assert restored.failure_count == cb.failure_count
        assert restored.total_failures == cb.total_failures
