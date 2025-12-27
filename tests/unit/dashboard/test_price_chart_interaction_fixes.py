"""
Price Chart Interaction Fixes Tests for Dashboard JavaScript.

Feature 1073: Tests that verify the fixes for Features 1070, 1071, 1072, 1075:
1. Hammer.js is loaded for pan gestures to work
2. Price axis uses dynamic limit calculation (Feature 1075: calculatePriceLimits)
3. Sentiment axis has fixed -1 to 1 limits

These tests use static analysis of JavaScript/HTML source code.

Run: pytest tests/unit/dashboard/test_price_chart_interaction_fixes.py -v
"""

import re
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parents[3]


def read_index_html() -> str:
    """Read the index.html file content."""
    repo_root = get_repo_root()
    index_path = repo_root / "src" / "dashboard" / "index.html"
    assert index_path.exists(), f"index.html not found at {index_path}"
    return index_path.read_text()


def read_ohlc_js() -> str:
    """Read the ohlc.js file content."""
    repo_root = get_repo_root()
    ohlc_path = repo_root / "src" / "dashboard" / "ohlc.js"
    assert ohlc_path.exists(), f"ohlc.js not found at {ohlc_path}"
    return ohlc_path.read_text()


class TestHammerJsLoaded:
    """Test that Hammer.js is loaded for pan gestures."""

    def test_hammerjs_script_tag_exists(self) -> None:
        """Verify Hammer.js is included via CDN."""
        content = read_index_html()

        assert "hammerjs" in content, (
            "Hammer.js not found in index.html. "
            "Add the Hammer.js library for pan gestures to work."
        )

    def test_hammerjs_loads_before_zoom_plugin(self) -> None:
        """Verify Hammer.js loads before chartjs-plugin-zoom."""
        content = read_index_html()

        # Find script tags specifically (not comments)
        hammer_match = re.search(r"<script[^>]*hammerjs[^>]*>", content)
        zoom_match = re.search(r"<script[^>]*chartjs-plugin-zoom[^>]*>", content)

        assert hammer_match, "Hammer.js script tag not found"
        assert zoom_match, "chartjs-plugin-zoom script tag not found"

        hammer_idx = hammer_match.start()
        zoom_idx = zoom_match.start()

        assert hammer_idx < zoom_idx, (
            "Hammer.js must be loaded BEFORE chartjs-plugin-zoom. "
            "The zoom plugin depends on Hammer.js for gesture recognition."
        )

    def test_hammerjs_has_integrity(self) -> None:
        """Verify Hammer.js has SRI integrity hash."""
        content = read_index_html()

        # Find the hammerjs script tag
        hammer_pattern = r"<script[^>]*hammerjs[^>]*>"
        match = re.search(hammer_pattern, content)
        assert match, "Hammer.js script tag not found"

        script_tag = match.group(0)
        assert "integrity=" in script_tag, (
            "Hammer.js missing SRI integrity hash. "
            "Add integrity attribute for security."
        )

    def test_has_feature_1073_comment_for_hammerjs(self) -> None:
        """Verify Feature 1073 comment exists near Hammer.js."""
        content = read_index_html()

        has_comment = "Feature 1073" in content and "Hammer" in content

        assert has_comment, (
            "Missing Feature 1073 reference near Hammer.js. "
            "Add a comment for traceability."
        )


class TestPriceAxisAutoFit:
    """Test that price axis uses dynamic data range, not $0 floor."""

    def test_calculate_price_limits_function_exists(self) -> None:
        """Verify calculatePriceLimits function exists (Feature 1075)."""
        content = read_ohlc_js()

        # Look for the calculatePriceLimits function definition
        assert "calculatePriceLimits" in content, (
            "calculatePriceLimits function not found. "
            "Feature 1075 requires dynamic price limit calculation."
        )

    def test_price_limits_calculated_from_data(self) -> None:
        """Verify price limits are calculated from candle low/high values."""
        content = read_ohlc_js()

        # Check that we extract lows and highs from candles
        assert (
            "candles.map(c => c.low)" in content
        ), "Price limits should extract low values from candles."
        assert (
            "candles.map(c => c.high)" in content
        ), "Price limits should extract high values from candles."

    def test_price_limits_have_padding(self) -> None:
        """Verify price limits include padding for visual clarity."""
        content = read_ohlc_js()

        # Check for 5% padding calculation
        padding_pattern = r"range \* 0\.05"
        assert re.search(padding_pattern, content), (
            "Price limits should include 5% padding above and below. "
            "This provides visual clarity at chart edges."
        )

    def test_price_limits_applied_dynamically(self) -> None:
        """Verify price limits are updated in updateChart method."""
        content = read_ohlc_js()

        # Check that limits are set dynamically, not just at init
        assert (
            "this.chart.options.plugins.zoom.limits.price.min" in content
        ), "Price limits should be updated dynamically in updateChart."
        assert (
            "this.chart.options.plugins.zoom.limits.price.max" in content
        ), "Price limits should be updated dynamically in updateChart."


class TestSentimentAxisFixed:
    """Test that sentiment axis has fixed -1 to 1 limits."""

    def test_sentiment_limits_exist(self) -> None:
        """Verify sentiment axis has limits configured."""
        content = read_ohlc_js()

        # Look for sentiment limits in the limits section
        assert "sentiment:" in content and "limits:" in content, (
            "Sentiment limits not configured. "
            "Add sentiment: { min: -1, max: 1 } to limits."
        )

    def test_sentiment_min_is_negative_one(self) -> None:
        """Verify sentiment min is -1."""
        content = read_ohlc_js()

        # Find the limits section and check for sentiment min: -1
        limits_match = re.search(
            r"limits:\s*\{[\s\S]*?sentiment:\s*\{[^}]*min:\s*-1",
            content,
        )
        assert limits_match, (
            "Sentiment axis missing min: -1 in limits. "
            "Add to prevent zoom from changing sentiment range."
        )

    def test_sentiment_max_is_one(self) -> None:
        """Verify sentiment max is 1."""
        content = read_ohlc_js()

        # Find the limits section and check for sentiment max: 1
        limits_match = re.search(
            r"limits:\s*\{[\s\S]*?sentiment:\s*\{[^}]*max:\s*1",
            content,
        )
        assert limits_match, (
            "Sentiment axis missing max: 1 in limits. "
            "Add to prevent zoom from changing sentiment range."
        )

    def test_sentiment_minrange_is_two(self) -> None:
        """Verify sentiment minRange is 2 (full -1 to 1 range)."""
        content = read_ohlc_js()

        # minRange: 2 ensures the full -1 to 1 range is always visible
        limits_match = re.search(
            r"limits:\s*\{[\s\S]*?sentiment:\s*\{[^}]*minRange:\s*2",
            content,
        )
        assert limits_match, (
            "Sentiment axis missing minRange: 2 in limits. "
            "This ensures full -1 to 1 range is always visible."
        )


class TestPanConfiguration:
    """Test that pan configuration is correct."""

    def test_pan_enabled(self) -> None:
        """Verify pan is enabled."""
        content = read_ohlc_js()

        pan_enabled_pattern = r"pan:\s*\{[^}]*enabled:\s*true"
        assert re.search(
            pan_enabled_pattern, content
        ), "Pan not enabled. Add pan: { enabled: true } to zoom config."

    def test_pan_mode_x(self) -> None:
        """Verify pan mode is 'x' for horizontal navigation."""
        content = read_ohlc_js()

        pan_mode_pattern = r"pan:\s*\{[^}]*mode:\s*['\"]x['\"]"
        assert re.search(pan_mode_pattern, content), (
            "Pan mode not set to 'x'. " "Use mode: 'x' for horizontal-only panning."
        )
