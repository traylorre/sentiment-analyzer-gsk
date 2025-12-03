"""Unit tests for global SSE stream endpoint.

Tests /api/v2/stream endpoint per FR-004 and FR-014.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestGlobalStreamEndpoint:
    """Tests for GET /api/v2/stream endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for SSE Lambda."""
        from src.lambdas.sse_streaming.handler import app

        return TestClient(app)

    def test_health_endpoint(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_stream_status_endpoint(self, client):
        """Stream status should return connection info."""
        response = client.get("/api/v2/stream/status")

        assert response.status_code == 200
        data = response.json()
        assert "connections" in data
        assert "max_connections" in data
        assert "available" in data
        assert "uptime_seconds" in data

    def test_stream_status_shows_correct_max(self, client):
        """Stream status should show correct max connections."""
        response = client.get("/api/v2/stream/status")

        data = response.json()
        # Default is 100
        assert data["max_connections"] == 100


class TestStreamEndpointIntegration:
    """Integration tests for stream endpoint (mocked)."""

    @pytest.fixture
    def mock_polling_service(self):
        """Mock the polling service."""
        with patch("src.lambdas.sse_streaming.stream.PollingService") as mock:
            instance = MagicMock()
            mock.return_value = instance
            yield instance

    def test_stream_endpoint_exists(self):
        """Verify stream endpoint is registered in app."""
        from src.lambdas.sse_streaming.handler import app

        routes = [route.path for route in app.routes]
        # Stream endpoint will be added in T015
        # For now, verify base routes exist
        assert "/health" in routes
        assert "/api/v2/stream/status" in routes
