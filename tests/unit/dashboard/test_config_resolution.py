"""
Test dashboard config.js resolution values match Python models.

Feature-1021: Dashboard Resolution Config
Validates that JavaScript config values are synchronized with
src/lib/timeseries/models.py Resolution enum.
"""

import re
from pathlib import Path

import pytest

from src.lib.timeseries.models import Resolution


class TestResolutionConfig:
    """Test resolution configuration in config.js."""

    @pytest.fixture
    def config_js_content(self) -> str:
        """Load config.js content."""
        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "dashboard"
            / "config.js"
        )
        return config_path.read_text()

    @pytest.fixture
    def parsed_resolutions(self, config_js_content: str) -> dict[str, dict]:
        """Parse RESOLUTIONS object from config.js."""
        resolutions = {}

        # Extract each resolution block using regex
        # Pattern matches: '1m': { key: '1m', displayName: '...', durationSeconds: N, ttlSeconds: N }
        pattern = r"'(\d+[mh])': \{\s*key: '(\d+[mh])',\s*displayName: '([^']+)',\s*durationSeconds: (\d+),\s*ttlSeconds: (\d+)"

        for match in re.finditer(pattern, config_js_content):
            key, _, display_name, duration, ttl = match.groups()
            resolutions[key] = {
                "displayName": display_name,
                "durationSeconds": int(duration),
                "ttlSeconds": int(ttl),
            }

        return resolutions

    def test_all_resolutions_defined(self, parsed_resolutions: dict) -> None:
        """Verify all 8 resolutions are defined in config.js."""
        expected_keys = {"1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"}
        assert set(parsed_resolutions.keys()) == expected_keys

    def test_ttl_matches_python_model(self, parsed_resolutions: dict) -> None:
        """Verify TTL values match Resolution.ttl_seconds."""
        for resolution in Resolution:
            js_ttl = parsed_resolutions[resolution.value]["ttlSeconds"]
            python_ttl = resolution.ttl_seconds
            assert (
                js_ttl == python_ttl
            ), f"TTL mismatch for {resolution.value}: JS={js_ttl}, Python={python_ttl}"

    def test_duration_matches_python_model(self, parsed_resolutions: dict) -> None:
        """Verify duration values match Resolution.duration_seconds."""
        for resolution in Resolution:
            js_duration = parsed_resolutions[resolution.value]["durationSeconds"]
            python_duration = resolution.duration_seconds
            assert js_duration == python_duration, (
                f"Duration mismatch for {resolution.value}: "
                f"JS={js_duration}, Python={python_duration}"
            )

    def test_default_resolution_is_5m(self, config_js_content: str) -> None:
        """Verify DEFAULT_RESOLUTION is set to '5m'."""
        assert "DEFAULT_RESOLUTION: '5m'" in config_js_content

    def test_timeseries_endpoint_exists(self, config_js_content: str) -> None:
        """Verify TIMESERIES endpoint is defined."""
        assert "TIMESERIES: '/api/v2/timeseries'" in config_js_content

    def test_resolution_order_defined(self, config_js_content: str) -> None:
        """Verify RESOLUTION_ORDER array is defined with correct order."""
        expected = (
            "RESOLUTION_ORDER: ['1m', '5m', '10m', '1h', '3h', '6h', '12h', '24h']"
        )
        assert expected in config_js_content

    def test_resolutions_are_frozen(self, config_js_content: str) -> None:
        """Verify RESOLUTIONS object is frozen."""
        assert "Object.freeze(CONFIG.RESOLUTIONS)" in config_js_content

    def test_resolution_order_is_frozen(self, config_js_content: str) -> None:
        """Verify RESOLUTION_ORDER array is frozen."""
        assert "Object.freeze(CONFIG.RESOLUTION_ORDER)" in config_js_content

    def test_display_names_are_human_readable(self, parsed_resolutions: dict) -> None:
        """Verify display names are human-readable."""
        expected_names = {
            "1m": "1 min",
            "5m": "5 min",
            "10m": "10 min",
            "1h": "1 hour",
            "3h": "3 hours",
            "6h": "6 hours",
            "12h": "12 hours",
            "24h": "24 hours",
        }
        for key, expected_name in expected_names.items():
            assert parsed_resolutions[key]["displayName"] == expected_name


class TestExistingEndpointsUnchanged:
    """Verify existing endpoints are not modified."""

    @pytest.fixture
    def config_js_content(self) -> str:
        """Load config.js content."""
        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "dashboard"
            / "config.js"
        )
        return config_path.read_text()

    @pytest.mark.parametrize(
        "endpoint",
        [
            "SENTIMENT: '/api/v2/sentiment'",
            "TRENDS: '/api/v2/trends'",
            "ARTICLES: '/api/v2/articles'",
            "METRICS: '/api/v2/metrics'",
            "STREAM: '/api/v2/stream'",
        ],
    )
    def test_existing_endpoint_unchanged(
        self, config_js_content: str, endpoint: str
    ) -> None:
        """Verify existing endpoint is still present."""
        assert endpoint in config_js_content
