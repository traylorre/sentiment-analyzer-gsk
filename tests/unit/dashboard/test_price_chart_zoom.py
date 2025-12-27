"""
Price Chart Vertical Zoom Tests for Dashboard JavaScript.

Feature 1070: Tests that verify the Price Chart has vertical zoom
functionality enabled via chartjs-plugin-zoom.

These tests use static analysis of JavaScript/HTML source code to verify:
1. chartjs-plugin-zoom is loaded in index.html
2. Zoom configuration exists in ohlc.js initChart() method
3. Zoom is configured for Y-axis only (mode: 'y')
4. Double-click reset handler is bound

Run: pytest tests/unit/dashboard/test_price_chart_zoom.py -v
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


class TestZoomPluginLoaded:
    """Test that chartjs-plugin-zoom is loaded in index.html."""

    def test_chartjs_plugin_zoom_script_tag(self) -> None:
        """Verify chartjs-plugin-zoom is included via CDN."""
        content = read_index_html()

        assert "chartjs-plugin-zoom" in content, (
            "chartjs-plugin-zoom not found in index.html. "
            "Add the plugin via CDN for zoom functionality."
        )

    def test_chartjs_plugin_zoom_has_integrity(self) -> None:
        """Verify chartjs-plugin-zoom has SRI integrity hash."""
        content = read_index_html()

        # Find the chartjs-plugin-zoom script tag
        zoom_pattern = r"<script[^>]*chartjs-plugin-zoom[^>]*>"
        match = re.search(zoom_pattern, content)
        assert match, "chartjs-plugin-zoom script tag not found"

        script_tag = match.group(0)
        assert "integrity=" in script_tag, (
            "chartjs-plugin-zoom missing SRI integrity hash. "
            "Add integrity attribute for security."
        )

    def test_chartjs_plugin_zoom_version(self) -> None:
        """Verify chartjs-plugin-zoom uses compatible version with Chart.js 4.x."""
        content = read_index_html()

        # Should use v2.x for Chart.js 4.x compatibility
        assert "chartjs-plugin-zoom@2" in content, (
            "chartjs-plugin-zoom should use v2.x for Chart.js 4.x compatibility. "
            "Found different version or pattern."
        )

    def test_has_feature_1070_comment(self) -> None:
        """Verify Feature 1070 comment exists in index.html or ohlc.js."""
        html_content = read_index_html()
        js_content = read_ohlc_js()

        has_comment = "Feature 1070" in html_content or "1070" in js_content

        assert has_comment, (
            "Missing Feature 1070 reference. " "Add a comment for traceability."
        )


class TestZoomConfiguration:
    """Test that zoom is properly configured in ohlc.js."""

    def test_zoom_plugin_in_chart_options(self) -> None:
        """Verify zoom plugin is configured in chart options."""
        content = read_ohlc_js()

        # Find the initChart method and look for zoom configuration
        assert "plugins:" in content, "Chart plugins configuration not found"
        assert "zoom:" in content, (
            "Zoom plugin configuration not found in chart options. "
            "Add zoom: { ... } to plugins section."
        )

    def test_zoom_wheel_enabled(self) -> None:
        """Verify mouse wheel zoom is enabled."""
        content = read_ohlc_js()

        # Look for wheel configuration
        wheel_pattern = r"wheel:\s*\{\s*enabled:\s*true"
        assert re.search(wheel_pattern, content), (
            "Mouse wheel zoom not enabled. "
            "Add wheel: { enabled: true } to zoom configuration."
        )

    def test_zoom_mode_y_axis(self) -> None:
        """Verify zoom is configured for Y-axis only (vertical zoom)."""
        content = read_ohlc_js()

        # Look for mode: 'y' configuration
        mode_pattern = r"mode:\s*['\"]y['\"]"
        assert re.search(mode_pattern, content), (
            "Zoom mode not set to 'y'. " "Use mode: 'y' for vertical-only zoom."
        )


class TestZoomResetFunctionality:
    """Test that zoom reset is properly implemented."""

    def test_reset_zoom_method_exists(self) -> None:
        """Verify resetZoom method exists in OHLCChart class."""
        content = read_ohlc_js()

        assert "resetZoom()" in content, (
            "resetZoom method not found in OHLCChart class. "
            "Add method to reset chart zoom to default."
        )

    def test_double_click_handler_bound(self) -> None:
        """Verify double-click event listener is bound for zoom reset."""
        content = read_ohlc_js()

        assert "dblclick" in content, (
            "Double-click event handler not found. "
            "Add dblclick listener to reset zoom."
        )

    def test_reset_zoom_calls_chart_method(self) -> None:
        """Verify resetZoom uses Chart.js resetZoom method."""
        content = read_ohlc_js()

        # Find the resetZoom method
        reset_match = re.search(
            r"resetZoom\(\)\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        )
        assert reset_match, "Could not find resetZoom method body"

        method_body = reset_match.group(1)
        assert "this.chart.resetZoom()" in method_body, (
            "resetZoom should call this.chart.resetZoom() to reset zoom. "
            "This is the Chart.js zoom plugin method."
        )


class TestSentimentAxisFixed:
    """Test that sentiment axis remains fixed during zoom."""

    def test_sentiment_axis_has_fixed_min_max(self) -> None:
        """Verify sentiment Y-axis has fixed min/max in scale configuration."""
        content = read_ohlc_js()

        # Look for sentiment scale with fixed min and max
        sentiment_min_pattern = r"sentiment:\s*\{[^}]*min:"
        sentiment_max_pattern = r"sentiment:\s*\{[^}]*max:"

        # Need to find both min and max in the scales section
        assert re.search(sentiment_min_pattern, content, re.DOTALL), (
            "Sentiment axis missing min configuration. "
            "Add min: -1.0 to sentiment scale."
        )
        assert re.search(sentiment_max_pattern, content, re.DOTALL), (
            "Sentiment axis missing max configuration. "
            "Add max: 1.0 to sentiment scale."
        )

    def test_zoom_on_zoom_callback_restores_sentiment(self) -> None:
        """Verify onZoom callback restores sentiment axis bounds."""
        content = read_ohlc_js()

        # Look for onZoom callback that handles sentiment axis
        has_on_zoom = "onZoom:" in content
        has_sentiment_scale_restore = (
            "sentimentScale" in content or "scales.sentiment" in content
        )

        assert has_on_zoom, (
            "Missing onZoom callback. "
            "Add callback to restore sentiment axis after zoom."
        )
        assert has_sentiment_scale_restore, (
            "onZoom callback should reference sentiment scale "
            "to prevent it from zooming."
        )
