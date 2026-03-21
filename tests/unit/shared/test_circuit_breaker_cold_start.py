"""Tests for circuit breaker cold start persistence and fail-open behavior.

Feature 1231: Circuit breaker state persistence across Lambda cold starts.
Feature 1234: Cold start observability with structured logging fields.

Verifies:
- Fail-open defaults to CLOSED when DynamoDB is unreachable (US1)
- Structured logging includes cold_start and state_source fields (US2)
- ColdStart dimension in SilentFailure/Count metric (FR-006)
- save_state resilience under total DynamoDB outage (FR-004)
- Cold start flag transitions from True to False after first invocation (1234)
"""

import logging
import threading
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from src.lambdas.shared.circuit_breaker import (
    CircuitBreakerManager,
    CircuitBreakerState,
    clear_cache,
    reset_cold_start,
)


@pytest.fixture(autouse=True)
def clear_cache_and_cold_start():
    """Clear circuit breaker cache and reset cold start flag before each test."""
    clear_cache()
    reset_cold_start()
    yield
    clear_cache()
    reset_cold_start()


@pytest.fixture
def mock_table():
    """Create mock DynamoDB table."""
    table = MagicMock()
    table.get_item.return_value = {}  # No existing item
    table.put_item.return_value = None
    return table


@pytest.fixture
def dynamo_client_error():
    """Create a realistic DynamoDB ClientError."""
    return ClientError(
        error_response={
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Requested resource not found",
            }
        },
        operation_name="GetItem",
    )


@pytest.fixture
def dynamo_connection_error():
    """Create a realistic DynamoDB EndpointConnectionError."""
    return EndpointConnectionError(
        endpoint_url="https://dynamodb.us-east-1.amazonaws.com"
    )


@pytest.fixture
def dynamo_timeout_error():
    """Create a realistic DynamoDB read timeout."""
    return ClientError(
        error_response={
            "Error": {
                "Code": "RequestTimeout",
                "Message": "Request timed out",
            }
        },
        operation_name="GetItem",
    )


class TestColdStartFailOpen:
    """US1: Circuit breaker defaults to CLOSED on cold start with unreachable state.

    SC-001: All three services default to state="closed" when DynamoDB is unreachable.
    """

    @pytest.mark.parametrize("service", ["tiingo", "finnhub", "sendgrid"])
    def test_all_services_default_closed_on_dynamo_client_error(
        self, mock_table, service, dynamo_client_error
    ):
        """All services fail-open to closed state on DynamoDB ClientError.

        Given: Lambda cold start with empty in-memory cache
        When: DynamoDB get_item raises ClientError
        Then: get_state() returns state="closed", can_execute()=True
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state(service)

        assert state.state == "closed"
        assert state.can_execute() is True
        assert state.service == service
        assert state.failure_count == 0

    @pytest.mark.parametrize("service", ["tiingo", "finnhub", "sendgrid"])
    def test_all_services_default_closed_on_connection_error(
        self, mock_table, service, dynamo_connection_error
    ):
        """All services fail-open to closed state on network partition.

        Given: Lambda cold start with empty in-memory cache
        When: DynamoDB get_item raises EndpointConnectionError
        Then: get_state() returns state="closed", can_execute()=True
        """
        mock_table.get_item.side_effect = dynamo_connection_error
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state(service)

        assert state.state == "closed"
        assert state.can_execute() is True

    def test_fail_open_on_timeout(self, mock_table, dynamo_timeout_error):
        """Fail-open on DynamoDB read timeout.

        Given: Lambda cold start with empty in-memory cache
        When: DynamoDB get_item raises RequestTimeout
        Then: get_state() returns state="closed"
        """
        mock_table.get_item.side_effect = dynamo_timeout_error
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("tiingo")

        assert state.state == "closed"
        assert state.can_execute() is True

    def test_fail_open_on_generic_exception(self, mock_table):
        """Fail-open on unexpected exceptions (e.g., serialization error).

        Given: Lambda cold start with empty in-memory cache
        When: DynamoDB get_item raises an unexpected exception
        Then: get_state() returns state="closed"
        """
        mock_table.get_item.side_effect = RuntimeError("Unexpected error")
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("finnhub")

        assert state.state == "closed"
        assert state.can_execute() is True

    def test_default_state_has_zero_counters(self, mock_table, dynamo_client_error):
        """Fail-open default state has clean counters.

        Ensures the default state is truly fresh — no residual failure counts
        that could cause immediate tripping after DynamoDB recovers.
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("tiingo")

        assert state.failure_count == 0
        assert state.total_failures == 0
        assert state.total_opens == 0
        assert state.total_recoveries == 0
        assert state.last_failure_at is None
        assert state.opened_at is None

    def test_fail_open_state_is_cached(self, mock_table, dynamo_client_error):
        """Fail-open default is cached, preventing repeated DynamoDB errors.

        Given: Cold start, DynamoDB unreachable
        When: get_state() called twice
        Then: Second call returns cached state (DynamoDB not called again)
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state1 = manager.get_state("tiingo")
        state2 = manager.get_state("tiingo")

        assert state1.state == "closed"
        assert state2.state == "closed"
        # DynamoDB should only be called once (second call hits cache)
        assert mock_table.get_item.call_count == 1

    def test_record_failure_works_after_fail_open_cold_start(
        self, mock_table, dynamo_client_error
    ):
        """System continues functioning after fail-open cold start.

        Given: Cold start with DynamoDB unreachable
        When: record_failure() is called (and save also fails)
        Then: In-memory state is preserved and correct
        """
        mock_table.get_item.side_effect = dynamo_client_error
        mock_table.put_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        # get_state will fail-open
        state = manager.record_failure("tiingo")

        # State should reflect the failure even though DynamoDB is down
        assert state.failure_count == 1
        assert state.total_failures == 1
        assert state.state == "closed"  # Not enough failures to trip

    def test_can_execute_returns_true_after_fail_open(
        self, mock_table, dynamo_client_error
    ):
        """can_execute() returns True after fail-open cold start.

        Given: Cold start with DynamoDB unreachable
        When: can_execute() is called
        Then: Returns True (allow traffic)
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        result = manager.can_execute("tiingo")

        assert result is True

    def test_concurrent_cold_start_all_default_closed(
        self, mock_table, dynamo_client_error
    ):
        """SC-005: Concurrent cold start requests all get closed state.

        Given: Cold start with DynamoDB unreachable
        When: Multiple threads call get_state() simultaneously
        Then: All threads receive state="closed"
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)
        results = []
        results_lock = threading.Lock()

        def worker(svc):
            state = manager.get_state(svc)
            with results_lock:
                results.append((svc, state.state, state.can_execute()))

        threads = []
        for service in ["tiingo", "finnhub", "sendgrid"]:
            for _ in range(5):
                t = threading.Thread(target=worker, args=(service,))
                threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results must be closed and executable
        assert len(results) == 15
        for svc, state, can_exec in results:
            assert state == "closed", f"{svc} got state={state}, expected closed"
            assert can_exec is True, f"{svc} got can_execute={can_exec}, expected True"


class TestColdStartLogging:
    """US2: State transitions are logged with cold start context.

    SC-002: Structured log entries include state_source and cold_start fields.
    """

    def test_cache_hit_logs_state_source_cache(self, mock_table, caplog):
        """Cache hit logs state_source="cache" and cold_start=False.

        Given: Warm invocation with populated cache
        When: get_state() hits cache
        Then: Log includes state_source="cache", cold_start=False
        """
        mock_table.get_item.return_value = {}
        manager = CircuitBreakerManager(mock_table)

        # First call populates cache
        manager.get_state("tiingo")

        # Second call hits cache
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            manager.get_state("tiingo")

        # Find the cache hit log record
        cache_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(cache_records) >= 1
        record = cache_records[-1]
        assert record.__dict__.get("state_source") == "cache"
        assert record.__dict__.get("cold_start") is False

    def test_dynamodb_load_logs_state_source_dynamodb(self, mock_table, caplog):
        """DynamoDB load logs state_source="dynamodb" and cold_start=True.

        Given: Cold start with empty cache
        When: get_state() loads from DynamoDB
        Then: Log includes state_source="dynamodb", cold_start=True
        """
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "CIRCUIT#tiingo",
                "SK": "STATE",
                "service": "tiingo",
                "state": "open",
                "failure_count": 3,
            }
        }
        manager = CircuitBreakerManager(mock_table)

        with caplog.at_level(logging.INFO):
            manager.get_state("tiingo")

        state_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(state_records) >= 1
        record = state_records[0]
        assert record.__dict__.get("state_source") == "dynamodb"
        assert record.__dict__.get("cold_start") is True

    def test_dynamodb_empty_logs_state_source_dynamodb(self, mock_table, caplog):
        """DynamoDB with no persisted item logs state_source="dynamodb".

        Given: Cold start, DynamoDB reachable but no item exists
        When: get_state() creates default
        Then: Log includes state_source="dynamodb", cold_start=True
        """
        mock_table.get_item.return_value = {}
        manager = CircuitBreakerManager(mock_table)

        with caplog.at_level(logging.INFO):
            manager.get_state("finnhub")

        state_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(state_records) >= 1
        record = state_records[0]
        assert record.__dict__.get("state_source") == "dynamodb"
        assert record.__dict__.get("cold_start") is True

    def test_fail_open_logs_state_source_default_fail_open(
        self, mock_table, dynamo_client_error, caplog
    ):
        """DynamoDB failure logs state_source="default_fail_open".

        Given: Cold start, DynamoDB unreachable
        When: get_state() falls back to default
        Then: Log includes state_source="default_fail_open", cold_start=True
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        with caplog.at_level(logging.WARNING):
            manager.get_state("tiingo")

        fail_records = [r for r in caplog.records if "fail-open" in r.message.lower()]
        assert len(fail_records) >= 1
        record = fail_records[0]
        assert record.__dict__.get("state_source") == "default_fail_open"
        assert record.__dict__.get("cold_start") is True
        assert record.__dict__.get("state") == "closed"

    def test_warm_invocation_fail_open_logs_cold_start_false(
        self, mock_table, dynamo_client_error, caplog
    ):
        """Warm invocation DynamoDB failure logs cold_start=False.

        Given: Warm invocation (first get_state consumed the cold start flag)
        When: DynamoDB fails on re-load after cache expiry
        Then: Log includes cold_start=False (module-level flag was already consumed)

        Feature 1234: The _is_cold_start flag is module-level and set to False
        after the first get_state() call. Subsequent calls see False regardless
        of cache state.
        """
        # First: successful load to warm the Lambda (consumes cold start flag)
        mock_table.get_item.return_value = {}
        manager = CircuitBreakerManager(mock_table)
        manager.get_state("tiingo")

        # Clear cache to simulate TTL expiry (but cold start flag stays False)
        clear_cache()

        # Now DynamoDB fails
        mock_table.get_item.side_effect = dynamo_client_error

        with caplog.at_level(logging.WARNING):
            caplog.clear()
            manager.get_state("tiingo")

        fail_records = [r for r in caplog.records if "fail-open" in r.message.lower()]
        assert len(fail_records) >= 1
        record = fail_records[0]
        assert record.__dict__.get("state_source") == "default_fail_open"
        # cold_start is False — the module-level flag was consumed by the first call
        assert record.__dict__.get("cold_start") is False

    def test_log_includes_service_name(self, mock_table, dynamo_client_error, caplog):
        """All cold start logs include the service name.

        Ensures operators can filter logs by service during incident triage.
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        with caplog.at_level(logging.WARNING):
            manager.get_state("sendgrid")

        fail_records = [r for r in caplog.records if "fail-open" in r.message.lower()]
        assert len(fail_records) >= 1
        assert fail_records[0].__dict__.get("service") == "sendgrid"


class TestColdStartMetrics:
    """FR-006: SilentFailure/Count metric includes ColdStart dimension.

    SC-003: Metric includes ColdStart dimension.
    """

    @patch("src.lambdas.shared.circuit_breaker.emit_metric")
    def test_silent_failure_metric_includes_cold_start_dimension(
        self, mock_emit_metric, mock_table, dynamo_client_error
    ):
        """SilentFailure metric includes ColdStart=true on cold start.

        Given: Cold start with DynamoDB unreachable
        When: get_state() falls back to default
        Then: emit_metric called with ColdStart="true" dimension
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        manager.get_state("tiingo")

        mock_emit_metric.assert_called_once()
        call_kwargs = mock_emit_metric.call_args
        dimensions = call_kwargs.kwargs.get("dimensions") or call_kwargs[1].get(
            "dimensions"
        )
        assert dimensions is not None
        assert dimensions["ColdStart"] == "true"
        assert dimensions["FailurePath"] == "circuit_breaker_load"

    @patch("src.lambdas.shared.circuit_breaker.emit_metric")
    def test_metric_not_emitted_on_successful_load(self, mock_emit_metric, mock_table):
        """No SilentFailure metric on successful DynamoDB load.

        Given: Cold start with DynamoDB reachable
        When: get_state() loads successfully
        Then: emit_metric is NOT called
        """
        mock_table.get_item.return_value = {}
        manager = CircuitBreakerManager(mock_table)

        manager.get_state("tiingo")

        mock_emit_metric.assert_not_called()


class TestSaveStateResilience:
    """FR-004: save_state() never raises exceptions.

    Ensures DynamoDB write failures are swallowed and in-memory state preserved.
    """

    def test_save_state_returns_false_on_dynamo_error(
        self, mock_table, dynamo_client_error
    ):
        """save_state() returns False (not raises) on DynamoDB write failure."""
        mock_table.get_item.return_value = {}
        mock_table.put_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state = CircuitBreakerState.create_default("tiingo")
        result = manager.save_state(state)

        assert result is False

    def test_save_state_returns_false_on_connection_error(
        self, mock_table, dynamo_connection_error
    ):
        """save_state() returns False on network partition."""
        mock_table.put_item.side_effect = dynamo_connection_error
        manager = CircuitBreakerManager(mock_table)

        state = CircuitBreakerState.create_default("tiingo")
        result = manager.save_state(state)

        assert result is False

    def test_save_state_preserves_cache_on_dynamo_failure(
        self, mock_table, dynamo_client_error
    ):
        """In-memory state is preserved even when DynamoDB write fails.

        The write-through pattern updates cache BEFORE attempting DynamoDB write.
        If write fails, cached state is still valid for the current invocation.
        """
        mock_table.get_item.return_value = {}
        mock_table.put_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state = CircuitBreakerState.create_default("tiingo")
        state.record_failure()
        state.record_failure()
        manager.save_state(state)

        # Cache should have the updated state despite DynamoDB failure
        cached_state = manager.get_state("tiingo")
        assert cached_state.failure_count == 2

    def test_total_dynamo_outage_system_continues(
        self, mock_table, dynamo_client_error
    ):
        """System operates normally under total DynamoDB outage.

        Given: Both read and write to DynamoDB fail
        When: Full circuit breaker lifecycle is exercised
        Then: System continues via in-memory state, no exceptions raised
        """
        mock_table.get_item.side_effect = dynamo_client_error
        mock_table.put_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        # Full lifecycle with DynamoDB completely unreachable
        assert manager.can_execute("tiingo") is True

        state = manager.record_failure("tiingo")
        assert state.failure_count == 1

        state = manager.record_success("tiingo")
        assert state.failure_count == 0
        assert state.state == "closed"

        # Trip the breaker
        for _ in range(5):
            state = manager.record_failure("tiingo")
        assert state.state == "open"

        # All of this worked without DynamoDB
        assert manager.can_execute("tiingo") is False


class TestColdStartStateRestoration:
    """Tests for state restoration from DynamoDB after cold start."""

    def test_cold_start_restores_open_state_from_dynamodb(self, mock_table):
        """Cold start restores OPEN state from DynamoDB (not overridden to closed).

        When DynamoDB IS reachable and has an open circuit, we must respect that.
        Fail-open only applies when DynamoDB is UNREACHABLE.
        """
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "CIRCUIT#tiingo",
                "SK": "STATE",
                "service": "tiingo",
                "state": "open",
                "failure_count": 5,
                "failure_threshold": 5,
                "opened_at": "2026-03-21T12:00:00+00:00",
            }
        }
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("tiingo")

        assert state.state == "open"
        assert state.failure_count == 5

    def test_cold_start_restores_half_open_from_dynamodb(self, mock_table):
        """Cold start restores HALF_OPEN state from DynamoDB."""
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "CIRCUIT#finnhub",
                "SK": "STATE",
                "service": "finnhub",
                "state": "half_open",
                "failure_count": 3,
            }
        }
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("finnhub")

        assert state.state == "half_open"
        assert state.can_execute() is True  # half_open allows one test request


class TestColdStartObservability:
    """Feature 1234: Circuit breaker cold start observability.

    Verifies structured logging fields (state_source, cold_start, service)
    are emitted on all get_state() paths for chaos testing visibility.
    """

    def test_cold_start_defaults_to_closed(self, mock_table, dynamo_client_error):
        """Cold start with DynamoDB failure defaults to CLOSED state.

        Given: Lambda cold start with empty cache
        When: DynamoDB get_item raises an error
        Then: get_state() returns state="closed" (fail-open)
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        state = manager.get_state("tiingo")

        assert state.state == "closed"
        assert state.can_execute() is True
        assert state.failure_count == 0

    def test_cold_start_logs_state_source(
        self, mock_table, dynamo_client_error, caplog
    ):
        """Cold start failure path logs state_source="default_fail_open".

        Given: Lambda cold start with empty cache
        When: DynamoDB is unreachable
        Then: Warning log includes state_source="default_fail_open"
              and error_type from get_safe_error_info
        """
        mock_table.get_item.side_effect = dynamo_client_error
        manager = CircuitBreakerManager(mock_table)

        with caplog.at_level(logging.WARNING):
            manager.get_state("tiingo")

        fail_records = [r for r in caplog.records if "fail-open" in r.message.lower()]
        assert len(fail_records) >= 1
        record = fail_records[0]
        assert record.__dict__.get("state_source") == "default_fail_open"
        assert record.__dict__.get("cold_start") is True
        assert record.__dict__.get("service") == "tiingo"
        assert record.__dict__.get("state") == "closed"
        # Feature 1234: get_safe_error_info provides error_type
        assert record.__dict__.get("error_type") == "ClientError"

    def test_warm_start_logs_cache_source(self, mock_table, caplog):
        """Warm start cache hit logs state_source="cache".

        Given: Warm invocation with populated cache (first call loaded state)
        When: get_state() hits the in-memory cache
        Then: Debug log includes state_source="cache", cold_start=False
        """
        mock_table.get_item.return_value = {}
        manager = CircuitBreakerManager(mock_table)

        # First call: populates cache, consumes cold start flag
        manager.get_state("tiingo")

        # Second call: hits cache, is a warm invocation
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            manager.get_state("tiingo")

        cache_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(cache_records) >= 1
        record = cache_records[-1]
        assert record.__dict__.get("state_source") == "cache"
        assert record.__dict__.get("cold_start") is False
        assert record.__dict__.get("service") == "tiingo"

    def test_cold_start_flag_set_on_first_call(self, mock_table, caplog):
        """First get_state() call is cold, second is warm.

        Given: Fresh module state (reset_cold_start called by fixture)
        When: get_state() called twice
        Then: First call logs cold_start=True, second logs cold_start=False

        Feature 1234: The module-level _is_cold_start flag is True on the
        first invocation after a Lambda cold start and False thereafter.
        """
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "CIRCUIT#tiingo",
                "SK": "STATE",
                "service": "tiingo",
                "state": "closed",
                "failure_count": 0,
            }
        }
        manager = CircuitBreakerManager(mock_table)

        # First call — should be cold start
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            manager.get_state("tiingo")

        first_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(first_records) >= 1
        assert first_records[0].__dict__.get("cold_start") is True
        assert first_records[0].__dict__.get("state_source") == "dynamodb"

        # Clear cache to force DynamoDB path again (not cache path)
        clear_cache()

        # Second call — should be warm start
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            manager.get_state("tiingo")

        second_records = [
            r for r in caplog.records if "state loaded" in r.message.lower()
        ]
        assert len(second_records) >= 1
        assert second_records[0].__dict__.get("cold_start") is False
        assert second_records[0].__dict__.get("state_source") == "dynamodb"
