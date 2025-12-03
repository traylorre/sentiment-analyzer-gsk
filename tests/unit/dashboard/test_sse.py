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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lambdas.dashboard.sse import (
    ConnectionManager,
    HeartbeatEventData,
    MetricsEventData,
    NewItemEventData,
    _generate_event_id,
    connection_manager,
    create_event_generator,
)

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
        assert isinstance(data.timestamp, datetime)

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
        """HeartbeatEventData has timestamp and connections."""
        data = HeartbeatEventData(connections=5)
        assert data.connections == 5
        assert isinstance(data.timestamp, datetime)

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

    @pytest.mark.asyncio
    async def test_create_event_generator_yields_heartbeat(self):
        """Event generator yields heartbeat events (FR-004)."""
        with patch(
            "src.lambdas.dashboard.sse._get_metrics_data",
            new_callable=AsyncMock,
            return_value=MetricsEventData(),
        ):
            gen = create_event_generator(heartbeat_interval=0.1, metrics_interval=0.1)

            # Get first event
            event = await gen.__anext__()

            # Should be either metrics or heartbeat
            assert event["event"] in ("metrics", "heartbeat")
            assert "id" in event
            assert event["id"].startswith("evt_")
            assert "data" in event

            # Parse data as JSON
            data = json.loads(event["data"])
            assert "timestamp" in data

            # Cancel generator
            await gen.aclose()

    @pytest.mark.asyncio
    async def test_create_event_generator_with_last_event_id(self):
        """Event generator accepts Last-Event-ID for reconnection (FR-005)."""
        with patch(
            "src.lambdas.dashboard.sse._get_metrics_data",
            new_callable=AsyncMock,
            return_value=MetricsEventData(),
        ):
            gen = create_event_generator(
                heartbeat_interval=0.1,
                metrics_interval=0.1,
                last_event_id="evt_abc123",
            )

            # Should not raise - just accept the ID
            event = await gen.__anext__()
            assert event is not None

            await gen.aclose()


# =============================================================================
# Global Stream Endpoint Tests (FR-001, FR-003)
# =============================================================================


class TestGlobalStreamEndpoint:
    """Tests for GET /api/v2/stream endpoint."""

    def test_stream_endpoint_registered(self):
        """Global stream endpoint is registered and returns EventSourceResponse (FR-003).

        Note: Full SSE streaming tested in E2E tests (test_global_stream_available).
        Unit test validates endpoint registration and route availability.
        """
        from fastapi import FastAPI
        from starlette.routing import Route

        from src.lambdas.dashboard.sse import router

        app = FastAPI()
        app.include_router(router)

        # Verify route is registered
        stream_route = None
        for route in app.routes:
            if isinstance(route, Route) and route.path == "/api/v2/stream":
                stream_route = route
                break

        assert stream_route is not None, "Stream endpoint should be registered"
        assert "GET" in stream_route.methods, "Stream endpoint should accept GET"

    @pytest.mark.asyncio
    async def test_stream_503_when_limit_reached(self):
        """Global stream returns 503 when connection limit reached (FR-015)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.lambdas.dashboard.sse import router

        app = FastAPI()
        app.include_router(router)

        # Set connection manager to limit

        connection_manager._count = connection_manager.max_connections

        client = TestClient(app)
        response = client.get("/api/v2/stream")
        assert response.status_code == 503
        assert "Maximum connections" in response.json()["detail"]

        # Reset for other tests
        connection_manager._count = 0


# =============================================================================
# Config Stream Endpoint Tests (FR-002, FR-006, FR-007, FR-008)
# =============================================================================


class TestConfigStreamEndpoint:
    """Tests for GET /api/v2/configurations/{config_id}/stream endpoint."""

    @pytest.mark.asyncio
    async def test_config_stream_requires_auth(self):
        """Config stream returns 401 without authentication (FR-007)."""
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient

        from src.lambdas.dashboard.sse import router

        app = FastAPI()
        app.include_router(router)

        # Reset connection manager
        connection_manager._count = 0

        with patch(
            "src.lambdas.dashboard.router_v2.get_user_id_from_request",
            side_effect=HTTPException(status_code=401, detail="No auth"),
        ):
            client = TestClient(app)
            response = client.get("/api/v2/configurations/test-config-id/stream")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_config_stream_404_invalid_config(self):
        """Config stream returns 404 for invalid config ID (FR-008)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.lambdas.dashboard.sse import router

        app = FastAPI()
        app.include_router(router)

        # Reset connection manager
        connection_manager._count = 0

        with patch(
            "src.lambdas.dashboard.router_v2.get_user_id_from_request",
            return_value="user-123",
        ):
            with patch(
                "src.lambdas.dashboard.sse.DYNAMODB_TABLE",
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
                        client = TestClient(app)
                        response = client.get(
                            "/api/v2/configurations/invalid-config/stream",
                            headers={"X-User-ID": "user-123"},
                        )
                        assert response.status_code == 404


# =============================================================================
# Stream Status Endpoint Tests
# =============================================================================


class TestStreamStatusEndpoint:
    """Tests for GET /api/v2/stream/status endpoint."""

    def test_stream_status_returns_counts(self):
        """Stream status returns connection counts."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.lambdas.dashboard.sse import router

        app = FastAPI()
        app.include_router(router)

        # Set specific count

        connection_manager._count = 5

        client = TestClient(app)
        response = client.get("/api/v2/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connections"] == 5
        assert data["max_connections"] == connection_manager.max_connections
        assert data["available"] == connection_manager.max_connections - 5

        # Reset
        connection_manager._count = 0
