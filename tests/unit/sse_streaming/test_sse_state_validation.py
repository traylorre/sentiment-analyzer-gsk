"""Unit tests for SSE state validation (Feature 1232).

Tests ConnectionManager.validate_state() for detecting and self-healing
state drift in the module-level singleton across warm Lambda invocations.
"""

import json
from unittest.mock import MagicMock, patch

from src.lambdas.sse_streaming.connection import ConnectionManager
from src.lambdas.sse_streaming.handler import handler
from tests.conftest import make_function_url_event, parse_streaming_response


class TestValidateStateClean:
    """Tests for validate_state on a fresh ConnectionManager."""

    def test_validate_state_clean(self):
        """Fresh ConnectionManager should report valid=True with no issues."""
        manager = ConnectionManager(max_connections=10)
        result = manager.validate_state()

        assert result["valid"] is True
        assert result["issues"] == []
        assert result["connection_count"] == 0
        assert result["active_count_matches"] is True

    def test_validate_state_clean_with_connections(self):
        """ConnectionManager with properly acquired connections should be valid."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager.acquire()

        result = manager.validate_state()

        assert result["valid"] is True
        assert result["issues"] == []
        assert result["connection_count"] == 2
        assert result["active_count_matches"] is True

    def test_validate_state_clean_after_release(self):
        """ConnectionManager after acquire+release should remain valid."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        manager.release(conn.connection_id)

        result = manager.validate_state()

        assert result["valid"] is True
        assert result["issues"] == []
        assert result["connection_count"] == 0
        assert result["active_count_matches"] is True


class TestValidateStateCountMismatch:
    """Tests for validate_state detecting and self-healing _active_count drift."""

    def test_validate_state_count_mismatch_high(self):
        """Detect when _active_count is higher than actual connections."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        # Simulate drift: _active_count is too high (e.g., release path missed)
        manager._active_count = 5

        result = manager.validate_state()

        assert result["valid"] is False
        assert len(result["issues"]) == 1
        assert "_active_count=5" in result["issues"][0]
        assert "actual=1" in result["issues"][0]
        assert result["connection_count"] == 1

    def test_validate_state_count_mismatch_low(self):
        """Detect when _active_count is lower than actual connections."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager.acquire()
        # Simulate drift: _active_count is too low
        manager._active_count = 0

        result = manager.validate_state()

        assert result["valid"] is False
        assert len(result["issues"]) == 1
        assert "_active_count=0" in result["issues"][0]
        assert "actual=2" in result["issues"][0]

    def test_validate_state_self_heals(self):
        """After detecting mismatch, _active_count should be corrected."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager._active_count = 99  # Wrong value

        # First call detects and heals
        result1 = manager.validate_state()
        assert result1["valid"] is False

        # Second call should be clean
        result2 = manager.validate_state()
        assert result2["valid"] is True
        assert result2["issues"] == []
        assert result2["active_count_matches"] is True

    def test_validate_state_self_heals_to_correct_value(self):
        """Self-heal should set _active_count to the actual dict length."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()
        manager.acquire()
        manager.acquire()
        manager._active_count = 0

        manager.validate_state()

        # _active_count should now equal 3 (the actual count)
        assert manager._active_count == 3


class TestValidateCalledOnStreamConnect:
    """Tests for validate_state being called when handler processes a stream request."""

    def test_validate_called_on_global_stream(self):
        """validate_state should be called when processing /api/v2/stream."""
        mock_mgr = MagicMock()
        mock_mgr.validate_state.return_value = {
            "valid": True,
            "issues": [],
            "connection_count": 0,
            "active_count_matches": True,
        }
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        with (
            patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr),
            patch("src.lambdas.sse_streaming.handler.metrics_emitter"),
        ):
            event = make_function_url_event(path="/api/v2/stream")
            gen = handler(event, None)
            list(gen)  # Consume generator

            mock_mgr.validate_state.assert_called()

    def test_validate_called_on_config_stream(self):
        """validate_state should be called when processing config stream."""
        mock_mgr = MagicMock()
        mock_mgr.validate_state.return_value = {
            "valid": True,
            "issues": [],
            "connection_count": 0,
            "active_count_matches": True,
        }
        mock_mgr.acquire.return_value = None
        mock_mgr.max_connections = 100

        mock_lookup = MagicMock()
        mock_lookup.validate_user_access.return_value = (True, ["AAPL"])

        with (
            patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr),
            patch(
                "src.lambdas.sse_streaming.handler.config_lookup_service", mock_lookup
            ),
            patch("src.lambdas.sse_streaming.handler.metrics_emitter"),
        ):
            event = make_function_url_event(
                path="/api/v2/configurations/test-config/stream",
                headers={"X-User-ID": "user-123"},
            )
            gen = handler(event, None)
            list(gen)  # Consume generator

            mock_mgr.validate_state.assert_called()

    def test_validate_called_on_stream_status(self):
        """validate_state should be called when processing /api/v2/stream/status."""
        mock_mgr = MagicMock()
        mock_mgr.validate_state.return_value = {
            "valid": True,
            "issues": [],
            "connection_count": 0,
            "active_count_matches": True,
        }
        mock_mgr.get_status.return_value = {
            "connections": 0,
            "max_connections": 100,
            "available": 100,
            "uptime_seconds": 42,
        }

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            event = make_function_url_event(path="/api/v2/stream/status")
            gen = handler(event, None)
            list(gen)  # Consume generator

            mock_mgr.validate_state.assert_called()

    def test_stream_status_includes_state_valid(self):
        """The /api/v2/stream/status response should include state_valid field."""
        event = make_function_url_event(path="/api/v2/stream/status")
        gen = handler(event, None)
        metadata, body = parse_streaming_response(gen)

        assert metadata["statusCode"] == 200
        data = json.loads(body)
        assert "state_valid" in data
        assert data["state_valid"] is True

    def test_stream_status_shows_invalid_state(self):
        """The status response should show state_valid=False when drift exists."""
        mock_mgr = MagicMock()
        mock_mgr.validate_state.return_value = {
            "valid": False,
            "issues": ["Count mismatch: _active_count=5, actual=1"],
            "connection_count": 1,
            "active_count_matches": True,
        }
        mock_mgr.get_status.return_value = {
            "connections": 1,
            "max_connections": 100,
            "available": 99,
            "uptime_seconds": 42,
        }

        with patch("src.lambdas.sse_streaming.handler.connection_manager", mock_mgr):
            event = make_function_url_event(path="/api/v2/stream/status")
            gen = handler(event, None)
            metadata, body = parse_streaming_response(gen)

            data = json.loads(body)
            assert data["state_valid"] is False
