"""
Unit tests for SSE (Server-Sent Events) module.

Tests cover:
- ConnectionManager (FR-015, FR-016, FR-017)
- Event generation (FR-004, FR-009, FR-010, FR-011)
- Endpoint handlers (FR-001, FR-002, FR-003)
- Authentication (FR-006, FR-007)
- Error handling (FR-008)
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from src.lambdas.dashboard.sse import (
    ConnectionManager,
    HeartbeatEventData,
    MetricsEventData,
    NewItemEventData,
    _build_sse_snapshot,
    _generate_event_id,
    connection_manager,
)
from tests.conftest import make_event

# =============================================================================
# ConnectionManager Tests (FR-015, FR-016, FR-017)
# =============================================================================


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_init_default_max_connections(self):
        """ConnectionManager initializes with default max_connections."""
        manager = ConnectionManager()
        assert manager.max_connections == 100
        assert manager.count == 0

    def test_init_custom_max_connections(self):
        """ConnectionManager accepts custom max_connections."""
        manager = ConnectionManager(max_connections=50)
        assert manager.max_connections == 50

    def test_acquire_success(self):
        """acquire() returns True and increments count."""
        manager = ConnectionManager(max_connections=10)
        assert manager.acquire() is True
        assert manager.count == 1

    def test_acquire_multiple(self):
        """acquire() can be called multiple times."""
        manager = ConnectionManager(max_connections=10)
        for _ in range(5):
            assert manager.acquire() is True
        assert manager.count == 5

    def test_acquire_at_limit(self):
        """acquire() returns False when limit reached (FR-015)."""
        manager = ConnectionManager(max_connections=3)
        # Fill to limit
        assert manager.acquire() is True
        assert manager.acquire() is True
        assert manager.acquire() is True
        # At limit - should fail
        assert manager.acquire() is False
        assert manager.count == 3

    def test_release_decrements_count(self):
        """release() decrements count."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager.acquire()
        assert manager.count == 2
        manager.release()
        assert manager.count == 1

    def test_release_does_not_go_negative(self):
        """release() does not decrement below zero."""
        manager = ConnectionManager(max_connections=10)
        manager.release()
        assert manager.count == 0

    def test_count_property(self):
        """count property returns current connection count (FR-017)."""
        manager = ConnectionManager(max_connections=10)
        assert manager.count == 0
        manager.acquire()
        assert manager.count == 1
        manager.acquire()
        assert manager.count == 2

    def test_thread_safety(self):
        """ConnectionManager is thread-safe."""
        import threading

        manager = ConnectionManager(max_connections=100)
        errors = []

        def acquire_release():
            try:
                for _ in range(10):
                    if manager.acquire():
                        manager.release()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_release) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert manager.count == 0


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestPydanticModels:
    """Tests for SSE event data models."""

    def test_metrics_event_data_defaults(self):
        """MetricsEventData has sensible defaults."""
        data = MetricsEventData()
        assert data.total == 0
        assert data.positive == 0
        assert data.neutral == 0
        assert data.negative == 0
        assert data.by_tag == {}
        assert data.rate_last_hour == 0
        assert data.rate_last_24h == 0
        assert isinstance(data.origin_timestamp, datetime)

    def test_metrics_event_data_custom_values(self):
        """MetricsEventData accepts custom values."""
        data = MetricsEventData(
            total=100,
            positive=50,
            neutral=30,
            negative=20,
            by_tag={"AAPL": 40, "MSFT": 30},
            rate_last_hour=10,
            rate_last_24h=100,
        )
        assert data.total == 100
        assert data.by_tag["AAPL"] == 40

    def test_heartbeat_event_data(self):
        """HeartbeatEventData has origin_timestamp and connections."""
        data = HeartbeatEventData(connections=5)
        assert data.connections == 5
        assert isinstance(data.origin_timestamp, datetime)

    def test_new_item_event_data(self):
        """NewItemEventData validates sentiment and score."""
        data = NewItemEventData(
            item_id="item_123",
            ticker="AAPL",
            sentiment="positive",
            score=0.85,
        )
        assert data.item_id == "item_123"
        assert data.ticker == "AAPL"
        assert data.sentiment == "positive"
        assert data.score == 0.85

    def test_new_item_event_data_score_bounds(self):
        """NewItemEventData score must be between 0 and 1."""
        # Valid bounds
        data = NewItemEventData(
            item_id="item_1",
            ticker="MSFT",
            sentiment="neutral",
            score=0.0,
        )
        assert data.score == 0.0

        data = NewItemEventData(
            item_id="item_2",
            ticker="GOOGL",
            sentiment="negative",
            score=1.0,
        )
        assert data.score == 1.0


# =============================================================================
# Event Generation Tests (FR-004, FR-011)
# =============================================================================


class TestEventGeneration:
    """Tests for event generation functions."""

    def test_generate_event_id_format(self):
        """Event IDs have correct format (FR-011)."""
        event_id = _generate_event_id()
        assert event_id.startswith("evt_")
        assert len(event_id) == 16  # "evt_" + 12 hex chars

    def test_generate_event_id_unique(self):
        """Event IDs are unique."""
        ids = [_generate_event_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_build_sse_snapshot_contains_metrics_and_heartbeat(self):
        """SSE snapshot contains metrics and heartbeat events (FR-004)."""
        with patch(
            "src.lambdas.dashboard.sse._get_metrics_data",
            return_value=MetricsEventData(),
        ):
            snapshot = _build_sse_snapshot()

            # Should contain both event types
            assert "event: metrics" in snapshot
            assert "event: heartbeat" in snapshot

            # Should contain event IDs
            assert "id: evt_" in snapshot

            # Parse the metrics data line
            for line in snapshot.split("\n"):
                if line.startswith("data: ") and "origin_timestamp" in line:
                    data = json.loads(line[6:])
                    assert "origin_timestamp" in data
                    break
            else:
                pytest.fail("No data line with origin_timestamp found")

    def test_build_sse_snapshot_with_last_event_id(self):
        """SSE snapshot accepts Last-Event-ID for reconnection (FR-005)."""
        with patch(
            "src.lambdas.dashboard.sse._get_metrics_data",
            return_value=MetricsEventData(),
        ):
            # Should not raise - just accept the ID
            snapshot = _build_sse_snapshot(last_event_id="evt_abc123")
            assert snapshot is not None
            assert "event: metrics" in snapshot


# =============================================================================
# Global Stream Endpoint Tests (FR-001, FR-003)
# =============================================================================


class TestGlobalStreamEndpoint:
    """Tests for GET /api/v2/stream endpoint."""

    def test_stream_endpoint_registered(self):
        """Global stream endpoint is registered (FR-003).

        Note: Full SSE streaming tested in E2E tests (test_global_stream_available).
        Unit test validates endpoint registration by calling lambda_handler.
        The SSE streaming endpoint will return 503 if connections are at limit,
        or attempt to stream. We verify the route resolves (not 404).
        """
        from src.lambdas.dashboard.sse import router

        # Verify the router has the stream route by checking its routes dict
        route_paths = [key[0] for key in router._routes]

        assert "/api/v2/stream" in route_paths, "Stream endpoint should be registered"

    def test_stream_503_when_limit_reached(self, mock_lambda_context):
        """Global stream returns 503 when connection limit reached (FR-015)."""
        # Set connection manager to limit
        original_count = connection_manager._count
        connection_manager._count = connection_manager.max_connections

        try:
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/stream",
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 503
            assert "Maximum connections" in json.loads(response["body"])["detail"]
        finally:
            # Reset for other tests
            connection_manager._count = original_count


# =============================================================================
# Config Stream Endpoint Tests (FR-002, FR-006, FR-007, FR-008)
# =============================================================================


class TestConfigStreamEndpoint:
    """Tests for GET /api/v2/configurations/{config_id}/stream endpoint."""

    def test_config_stream_requires_auth(self, mock_lambda_context):
        """Config stream returns 401 without authentication (FR-007)."""
        # Reset connection manager
        original_count = connection_manager._count
        connection_manager._count = 0

        try:
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/configurations/test-config-id/stream",
                    path_params={"config_id": "test-config-id"},
                ),
                mock_lambda_context,
            )
            assert response["statusCode"] == 401
        finally:
            connection_manager._count = original_count

    def test_config_stream_404_invalid_config(self, mock_lambda_context):
        """Config stream returns 404 for invalid config ID (FR-008)."""
        # Reset connection manager
        original_count = connection_manager._count
        connection_manager._count = 0

        with patch(
            "src.lambdas.dashboard.sse.extract_auth_context",
            return_value={"user_id": "user-123"},
        ):
            with patch(
                "src.lambdas.dashboard.sse.SENTIMENTS_TABLE",
                "test-table",
            ):
                with patch(
                    "src.lambdas.dashboard.sse.get_table",
                    return_value=MagicMock(),
                ):
                    with patch(
                        "src.lambdas.dashboard.configurations.get_configuration",
                        return_value=None,
                    ):
                        try:
                            response = lambda_handler(
                                make_event(
                                    method="GET",
                                    path="/api/v2/configurations/invalid-config/stream",
                                    path_params={"config_id": "invalid-config"},
                                    headers={"Authorization": "Bearer user-123"},
                                ),
                                mock_lambda_context,
                            )
                            assert response["statusCode"] == 404
                        finally:
                            connection_manager._count = original_count


# =============================================================================
# Stream Status Endpoint Tests
# =============================================================================


class TestStreamStatusEndpoint:
    """Tests for GET /api/v2/stream/status endpoint."""

    def test_stream_status_returns_counts(self, mock_lambda_context):
        """Stream status returns connection counts."""
        # Set specific count
        original_count = connection_manager._count
        connection_manager._count = 5

        try:
            response = lambda_handler(
                make_event(
                    method="GET",
                    path="/api/v2/stream/status",
                ),
                mock_lambda_context,
            )

            assert response["statusCode"] == 200
            data = json.loads(response["body"])
            assert data["connections"] == 5
            assert data["max_connections"] == connection_manager.max_connections
            assert data["available"] == connection_manager.max_connections - 5
        finally:
            # Reset
            connection_manager._count = original_count
