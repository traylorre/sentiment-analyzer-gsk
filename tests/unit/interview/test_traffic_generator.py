"""Unit tests for interview traffic generator.

Tests cover:
- TrafficStats dataclass
- TrafficGenerator class methods
- Edge cases: auth tokens, timing, network failures
- Chicken-and-egg hazards (session required before config)
"""

import asyncio

# Import module under test - need to add interview to path
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# Add interview directory to path for imports
interview_path = Path(__file__).parent.parent.parent.parent / "interview"
sys.path.insert(0, str(interview_path))

from traffic_generator import (  # noqa: E402
    ENVIRONMENTS,
    SAMPLE_CONFIG_NAMES,
    SAMPLE_TICKERS,
    TrafficGenerator,
    TrafficStats,
)


class TestTrafficStats:
    """Tests for TrafficStats dataclass."""

    def test_default_values(self):
        """Stats should have sensible defaults."""
        stats = TrafficStats()
        assert stats.requests_sent == 0
        assert stats.success_count == 0
        assert stats.error_count == 0
        assert stats.rate_limited == 0
        assert stats.circuit_breaker_trips == 0
        assert stats.total_latency_ms == 0

    def test_avg_latency_zero_requests(self):
        """Avg latency should be 0 when no requests sent (avoid division by zero)."""
        stats = TrafficStats()
        assert stats.avg_latency_ms == 0

    def test_avg_latency_calculation(self):
        """Avg latency should be calculated correctly."""
        stats = TrafficStats(requests_sent=10, total_latency_ms=500)
        assert stats.avg_latency_ms == 50.0

    def test_success_rate_zero_requests(self):
        """Success rate should be 0 when no requests sent (avoid division by zero)."""
        stats = TrafficStats()
        assert stats.success_rate == 0

    def test_success_rate_calculation(self):
        """Success rate should be calculated correctly."""
        stats = TrafficStats(requests_sent=10, success_count=8)
        assert stats.success_rate == 80.0

    def test_success_rate_100_percent(self):
        """Success rate should handle 100% success."""
        stats = TrafficStats(requests_sent=5, success_count=5)
        assert stats.success_rate == 100.0

    def test_success_rate_0_percent(self):
        """Success rate should handle 0% success."""
        stats = TrafficStats(requests_sent=5, success_count=0)
        assert stats.success_rate == 0.0

    def test_print_summary_no_errors(self, capsys):
        """Print summary should not raise errors."""
        stats = TrafficStats(
            requests_sent=100,
            success_count=95,
            error_count=5,
            rate_limited=2,
            circuit_breaker_trips=1,
            total_latency_ms=5000,
        )
        stats.print_summary()
        captured = capsys.readouterr()
        assert "TRAFFIC GENERATION SUMMARY" in captured.out
        assert "Total Requests:      100" in captured.out
        assert "95.0%" in captured.out


class TestTrafficGenerator:
    """Tests for TrafficGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.fixture
    def mock_client(self):
        """Create a mock httpx client."""
        return AsyncMock(spec=httpx.AsyncClient)

    def test_init(self, generator):
        """Generator should initialize with correct values."""
        assert generator.base_url == "https://test-api.example.com"
        assert generator.verbose is False
        assert isinstance(generator.stats, TrafficStats)
        assert generator.sessions == []

    def test_log_when_verbose(self, capsys):
        """Log should print when verbose is True."""
        gen = TrafficGenerator("https://test.com", verbose=True)
        gen.log("Test message", "  ")
        captured = capsys.readouterr()
        assert "Test message" in captured.out

    def test_log_when_not_verbose(self, capsys):
        """Log should not print when verbose is False."""
        gen = TrafficGenerator("https://test.com", verbose=False)
        gen.log("Test message", "  ")
        captured = capsys.readouterr()
        assert captured.out == ""


class TestMakeRequest:
    """Tests for make_request method."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_success_200(self, generator):
        """200 response should be counted as success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 200
        assert data == {"status": "ok"}
        assert generator.stats.success_count == 1
        assert generator.stats.requests_sent == 1
        assert generator.stats.error_count == 0

    @pytest.mark.asyncio
    async def test_success_201(self, generator):
        """201 response should be counted as success."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": "123"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(
            mock_client, "POST", "/api/v2/auth/anonymous", json_data={}
        )

        assert status == 201
        assert generator.stats.success_count == 1

    @pytest.mark.asyncio
    async def test_rate_limited_429(self, generator):
        """429 response should be counted as rate limited."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "rate_limited"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(
            mock_client, "GET", "/api/v2/configurations"
        )

        assert status == 429
        assert generator.stats.rate_limited == 1
        assert generator.stats.error_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_503(self, generator):
        """503 response should be counted as circuit breaker trip."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.json.return_value = {"error": "service_unavailable"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 503
        assert generator.stats.circuit_breaker_trips == 1
        assert generator.stats.error_count == 1

    @pytest.mark.asyncio
    async def test_other_error(self, generator):
        """Other error codes should be counted as errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "internal"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 500
        assert generator.stats.error_count == 1
        assert generator.stats.rate_limited == 0
        assert generator.stats.circuit_breaker_trips == 0

    @pytest.mark.asyncio
    async def test_network_error(self, generator):
        """Network errors should be counted as errors and return status 0."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("Connection failed")

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 0
        assert data is None
        assert generator.stats.error_count == 1

    @pytest.mark.asyncio
    async def test_timeout_error(self, generator):
        """Timeout errors should be counted as errors."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.TimeoutException("Request timeout")

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 0
        assert data is None
        assert generator.stats.error_count == 1

    @pytest.mark.asyncio
    async def test_json_decode_error(self, generator):
        """JSON decode errors should return None data but not crash."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 200
        assert data is None
        assert generator.stats.success_count == 1

    @pytest.mark.asyncio
    async def test_latency_tracking(self, generator):
        """Latency should be tracked for requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        await generator.make_request(mock_client, "GET", "/health")

        assert generator.stats.total_latency_ms > 0


class TestCheckHealth:
    """Tests for check_health method."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_healthy_service(self, generator):
        """Should return True when service is healthy."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        result = await generator.check_health(mock_client)

        assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy_service(self, generator):
        """Should return False when service is unhealthy."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"status": "error"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        result = await generator.check_health(mock_client)

        assert result is False

    @pytest.mark.asyncio
    async def test_unreachable_service(self, generator):
        """Should return False when service is unreachable."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("Connection failed")

        result = await generator.check_health(mock_client)

        assert result is False


class TestCreateSession:
    """Tests for create_session method - critical for auth flow."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_session_created_200(self, generator):
        """Should create session on 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token": "abc123",
            "user_id": "user-12345678",
            "session_id": "sess-001",
        }

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        session = await generator.create_session(mock_client)

        assert session is not None
        assert session["token"] == "abc123"
        assert session["user_id"] == "user-12345678"
        assert session["session_id"] == "sess-001"
        assert len(generator.sessions) == 1

    @pytest.mark.asyncio
    async def test_session_created_201(self, generator):
        """Should create session on 201 response."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "token": "xyz789",
            "user_id": "user-87654321",
            "session_id": "sess-002",
        }

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        session = await generator.create_session(mock_client)

        assert session is not None
        assert session["token"] == "xyz789"
        assert len(generator.sessions) == 1

    @pytest.mark.asyncio
    async def test_session_failed(self, generator):
        """Should return None on failed session creation."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "bad_request"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        session = await generator.create_session(mock_client)

        assert session is None
        assert len(generator.sessions) == 0

    @pytest.mark.asyncio
    async def test_session_network_error(self, generator):
        """Should return None on network error."""
        mock_client = AsyncMock()
        mock_client.request.side_effect = httpx.ConnectError("Network error")

        session = await generator.create_session(mock_client)

        assert session is None
        assert len(generator.sessions) == 0


class TestCreateConfiguration:
    """Tests for create_configuration - requires valid session token."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_config_created(self, generator):
        """Should create configuration with valid token."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "config_id": "config-12345678",
            "name": "Tech Stocks",
        }

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        config = await generator.create_configuration(
            mock_client, "valid-user-id", "Tech Stocks", ["AAPL", "MSFT"]
        )

        assert config is not None
        assert config["config_id"] == "config-12345678"

        # Verify correct headers were sent
        call_args = mock_client.request.call_args
        assert call_args.kwargs["headers"]["X-User-ID"] == "valid-user-id"

    @pytest.mark.asyncio
    async def test_config_unauthorized(self, generator):
        """Should fail with invalid/expired token."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "unauthorized"}

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        config = await generator.create_configuration(
            mock_client, "invalid-token", "My Stocks", ["AAPL"]
        )

        assert config is None

    @pytest.mark.asyncio
    async def test_config_validation_error(self, generator):
        """Should fail with validation errors (422)."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "error": "validation_error",
            "details": [{"field": "tickers", "message": "Invalid ticker symbol"}],
        }

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        config = await generator.create_configuration(
            mock_client, "valid-token", "Stocks", ["INVALID"]
        )

        assert config is None


class TestChickenAndEggHazards:
    """Tests for chicken-and-egg scenarios (order of operations)."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_basic_flow_requires_session_first(self, generator):
        """Basic flow should fail gracefully if session creation fails."""
        mock_response_health = MagicMock()
        mock_response_health.status_code = 200
        mock_response_health.json.return_value = {"status": "healthy"}

        mock_response_session = MagicMock()
        mock_response_session.status_code = 500
        mock_response_session.json.return_value = {"error": "server_error"}

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            mock_response_health,  # health check
            mock_response_session,  # session creation fails
        ]

        # Should not crash, just return early
        await generator.run_scenario_basic_flow(mock_client)

        # Should have made exactly 2 requests (health + session attempt)
        assert generator.stats.requests_sent == 2

    @pytest.mark.asyncio
    async def test_config_requires_session_token(self, generator):
        """Config creation needs a valid session token from prior step."""
        # First request: health check succeeds
        mock_health = MagicMock()
        mock_health.status_code = 200
        mock_health.json.return_value = {"status": "healthy"}

        # Second request: session created
        mock_session = MagicMock()
        mock_session.status_code = 201
        mock_session.json.return_value = {
            "token": "test-token-123",
            "user_id": "user-abc12345",
            "session_id": "sess-123",
        }

        # Third request: config created using session token
        mock_config = MagicMock()
        mock_config.status_code = 201
        mock_config.json.return_value = {
            "config_id": "config-xyz",
            "name": "Test",
        }

        # Fourth request: list configs
        mock_list = MagicMock()
        mock_list.status_code = 200
        mock_list.json.return_value = {"configurations": []}

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            mock_health,
            mock_session,
            mock_config,
            mock_list,
        ]

        await generator.run_scenario_basic_flow(mock_client)

        # Verify config request used session user_id
        calls = mock_client.request.call_args_list
        config_call = calls[2]  # Third call is config creation
        assert "user-abc12345" in str(config_call)  # X-User-ID header


class TestTimingHazards:
    """Tests for timing-related edge cases."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_rate_limit_burst_handling(self, generator):
        """Rate limit scenario should handle burst of requests."""
        # Session creation succeeds
        mock_session = MagicMock()
        mock_session.status_code = 201
        mock_session.json.return_value = {
            "token": "test-token",
            "user_id": "user-test123",
            "session_id": "sess-test",
        }

        # First few requests succeed, then rate limited
        def create_response(success: bool):
            mock = MagicMock()
            if success:
                mock.status_code = 200
                mock.json.return_value = {"configurations": []}
            else:
                mock.status_code = 429
                mock.json.return_value = {"error": "rate_limited"}
            return mock

        responses = [mock_session]
        # 5 successful, then all rate limited
        responses.extend([create_response(i < 5) for i in range(10)])

        mock_client = AsyncMock()
        mock_client.request.side_effect = responses

        await generator.run_scenario_rate_limit(mock_client, burst_size=10)

        assert generator.stats.rate_limited == 5
        assert generator.stats.success_count >= 6  # session + 5 successful

    @pytest.mark.asyncio
    async def test_cache_warmup_latency_tracking(self, generator):
        """Cache warmup should track latency changes."""
        # Session and config creation
        mock_session = MagicMock()
        mock_session.status_code = 201
        mock_session.json.return_value = {
            "token": "test-token",
            "user_id": "user-test123",
            "session_id": "sess-test",
        }

        mock_config = MagicMock()
        mock_config.status_code = 201
        mock_config.json.return_value = {"config_id": "config-test12"}

        mock_sentiment = MagicMock()
        mock_sentiment.status_code = 200
        mock_sentiment.json.return_value = {"sentiment": 0.5}

        responses = [mock_session, mock_config]
        # Add sentiment responses for warmup iterations
        responses.extend([mock_sentiment] * 5)

        mock_client = AsyncMock()
        mock_client.request.side_effect = responses

        await generator.run_scenario_cache_warmup(mock_client, iterations=5)

        # Should have tracked latency for all requests
        assert generator.stats.total_latency_ms > 0


class TestEnvironmentConfig:
    """Tests for environment configuration."""

    def test_environments_defined(self):
        """Both preprod and prod environments should be defined."""
        assert "preprod" in ENVIRONMENTS
        assert "prod" in ENVIRONMENTS

    def test_environment_urls_are_valid(self):
        """Environment URLs should be valid HTTPS URLs."""
        for env, url in ENVIRONMENTS.items():
            assert url.startswith("https://"), f"{env} URL should be HTTPS"
            assert ".lambda-url.us-east-1.on.aws" in url, f"{env} should be Lambda URL"

    def test_sample_data_populated(self):
        """Sample data should be populated for realistic testing."""
        assert len(SAMPLE_TICKERS) >= 5
        assert len(SAMPLE_CONFIG_NAMES) >= 3
        assert "AAPL" in SAMPLE_TICKERS
        assert "MSFT" in SAMPLE_TICKERS


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture
    def generator(self):
        """Create a traffic generator instance."""
        return TrafficGenerator(base_url="https://test-api.example.com", verbose=False)

    @pytest.mark.asyncio
    async def test_empty_config_id_handling(self, generator):
        """Should handle empty config_id gracefully."""
        mock_session = MagicMock()
        mock_session.status_code = 201
        mock_session.json.return_value = {
            "token": "test-token",
            "user_id": "user-test123",
            "session_id": "sess-test",
        }

        mock_health = MagicMock()
        mock_health.status_code = 200
        mock_health.json.return_value = {"status": "healthy"}

        mock_config = MagicMock()
        mock_config.status_code = 201
        mock_config.json.return_value = {}  # Missing config_id

        mock_list = MagicMock()
        mock_list.status_code = 200
        mock_list.json.return_value = {"configurations": []}

        mock_client = AsyncMock()
        mock_client.request.side_effect = [
            mock_health,
            mock_session,
            mock_config,
            mock_list,
        ]

        # Should not crash
        await generator.run_scenario_basic_flow(mock_client)

    @pytest.mark.asyncio
    async def test_none_json_response(self, generator):
        """Should handle None JSON responses."""
        mock_response = MagicMock()
        mock_response.status_code = 204  # No content
        mock_response.json.return_value = None

        mock_client = AsyncMock()
        mock_client.request.return_value = mock_response

        status, data = await generator.make_request(
            mock_client, "DELETE", "/api/v2/configurations/123"
        )

        assert status == 204
        assert data is None

    @pytest.mark.asyncio
    async def test_very_long_latency(self, generator):
        """Should handle requests that take a long time."""

        async def slow_request(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            mock = MagicMock()
            mock.status_code = 200
            mock.json.return_value = {"status": "ok"}
            return mock

        mock_client = AsyncMock()
        mock_client.request = slow_request

        status, data = await generator.make_request(mock_client, "GET", "/health")

        assert status == 200
        assert generator.stats.total_latency_ms >= 100

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, generator):
        """Should handle multiple concurrent sessions."""
        mock_session = MagicMock()
        mock_session.status_code = 201

        call_count = 0

        def get_session_response():
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            mock.status_code = 201
            mock.json.return_value = {
                "token": f"token-{call_count}",
                "user_id": f"user-{call_count:08d}",
                "session_id": f"sess-{call_count}",
            }
            return mock

        mock_client = AsyncMock()
        mock_client.request.side_effect = lambda *a, **k: get_session_response()

        # Create 3 sessions
        sessions = []
        for _ in range(3):
            session = await generator.create_session(mock_client)
            sessions.append(session)

        assert len(generator.sessions) == 3
        # Each session should have unique token
        tokens = [s["token"] for s in sessions]
        assert len(set(tokens)) == 3
