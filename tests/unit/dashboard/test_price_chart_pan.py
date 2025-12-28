"""
Price Chart Horizontal Pan Tests for Dashboard JavaScript.

Feature 1071: Tests that verify the Price Chart has horizontal pan
functionality enabled via chartjs-plugin-zoom.

These tests use static analysis of JavaScript/HTML source code to verify:
1. Pan configuration exists in ohlc.js initChart() method
2. Pan is configured for X-axis only (mode: 'x')
3. Pan uses left-click-drag (no modifier key)
4. Pan threshold is set for smooth interaction

Run: pytest tests/unit/dashboard/test_price_chart_pan.py -v
"""

import re
from pathlib import Path


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parents[3]


def read_ohlc_js() -> str:
    """Read the ohlc.js file content."""
    repo_root = get_repo_root()
    ohlc_path = repo_root / "src" / "dashboard" / "ohlc.js"
    assert ohlc_path.exists(), f"ohlc.js not found at {ohlc_path}"
    return ohlc_path.read_text()


class TestPanConfiguration:
    """Test that pan is properly configured in ohlc.js."""

    def test_pan_configuration_exists(self) -> None:
        """Verify pan configuration exists in zoom plugin options."""
        content = read_ohlc_js()

        assert "pan:" in content, (
            "Pan configuration not found in chart options. "
            "Add pan: { ... } to zoom plugin section."
        )

    def test_pan_enabled(self) -> None:
        """Verify pan is enabled."""
        content = read_ohlc_js()

        # Look for pan enabled configuration
        pan_enabled_pattern = r"pan:\s*\{[^}]*enabled:\s*true"
        assert re.search(pan_enabled_pattern, content, re.DOTALL), (
            "Pan not enabled. " "Add enabled: true to pan configuration."
        )

    def test_pan_mode_xy_axis(self) -> None:
        """Verify pan is configured for XY-axis (bi-directional pan, Feature 1080)."""
        content = read_ohlc_js()

        # Feature 1080: Look for mode: 'xy' in pan configuration
        # Changed from 'x' to 'xy' to enable vertical panning after zoom
        pan_mode_pattern = r"pan:\s*\{[^}]*mode:\s*['\"]xy['\"]"
        assert re.search(pan_mode_pattern, content, re.DOTALL), (
            "Pan mode not set to 'xy'. "
            "Use mode: 'xy' for bi-directional panning (Feature 1080)."
        )

    def test_pan_has_threshold(self) -> None:
        """Verify pan has a threshold configured for smooth interaction."""
        content = read_ohlc_js()

        # Look for threshold in pan configuration
        pan_threshold_pattern = r"pan:\s*\{[^}]*threshold:\s*\d+"
        assert re.search(pan_threshold_pattern, content, re.DOTALL), (
            "Pan missing threshold configuration. "
            "Add threshold: N to prevent accidental panning."
        )

    def test_pan_no_modifier_key(self) -> None:
        """Verify pan uses left-click without modifier key."""
        content = read_ohlc_js()

        # Look for modifierKey: null in pan configuration
        modifier_pattern = r"pan:\s*\{[^}]*modifierKey:\s*null"
        assert re.search(modifier_pattern, content, re.DOTALL), (
            "Pan should use plain left-click (modifierKey: null). "
            "Add modifierKey: null to pan configuration."
        )

    def test_has_feature_1071_comment(self) -> None:
        """Verify Feature 1071 comment exists in ohlc.js for traceability."""
        content = read_ohlc_js()

        assert "1071" in content, (
            "Missing Feature 1071 reference in ohlc.js. "
            "Add a comment for traceability."
        )


class TestPanAndZoomCoexistence:
    """Test that pan and zoom can coexist without conflicts."""

    def test_zoom_still_works_on_y_axis(self) -> None:
        """Verify zoom is still configured for Y-axis."""
        content = read_ohlc_js()

        # Zoom should still be on Y-axis
        # Note: chartjs-plugin-zoom uses nested structure: zoom: { zoom: { mode: 'y' } }
        # The inner 'zoom' key configures the zoom behavior
        # We need to check for wheel.enabled and mode: 'y' in that context
        has_wheel_enabled = re.search(
            r"wheel:\s*\{[^}]*enabled:\s*true", content, re.DOTALL
        )
        has_mode_y = "mode: 'y'" in content or 'mode: "y"' in content

        assert has_wheel_enabled, (
            "Zoom wheel should be enabled. "
            "Add wheel: { enabled: true } to zoom configuration."
        )
        assert has_mode_y, (
            "Zoom mode should be 'y' for vertical zoom. "
            "Pan is 'xy' for bi-directional, zoom is 'y' for vertical."
        )

    def test_pan_xy_zoom_y_configuration(self) -> None:
        """Verify pan is XY-axis and zoom is Y-axis (Feature 1080)."""
        content = read_ohlc_js()

        # Check that we have both modes configured correctly
        # Pan is in its own block: pan: { mode: 'xy' } for bi-directional
        has_pan_xy = re.search(
            r"pan:\s*\{[^}]*mode:\s*['\"]xy['\"]", content, re.DOTALL
        )

        # For zoom mode, just check that mode: 'y' appears in the file
        # along with scaleMode: 'y' which confirms it's for Y-axis zoom
        has_zoom_y = "mode: 'y'" in content and "scaleMode: 'y'" in content

        assert (
            has_pan_xy
        ), "Pan should be configured for XY-axis (mode: 'xy', Feature 1080)"
        assert (
            has_zoom_y
        ), "Zoom should be configured for Y-axis (mode: 'y' and scaleMode: 'y')"

    def test_reset_zoom_also_resets_pan(self) -> None:
        """Verify resetZoom method exists (resets both zoom and pan)."""
        content = read_ohlc_js()

        # Chart.js resetZoom() resets both zoom and pan
        assert "this.chart.resetZoom()" in content, (
            "resetZoom should call this.chart.resetZoom() "
            "which resets both zoom and pan to default."
        )


class TestPanUserExperience:
    """Test user experience aspects of pan functionality."""

    def test_double_click_resets_view(self) -> None:
        """Verify double-click resets both zoom and pan."""
        content = read_ohlc_js()

        assert "dblclick" in content, (
            "Double-click handler should exist to reset view. "
            "This resets both zoom and pan."
        )

    def test_zoom_plugin_has_limits(self) -> None:
        """Verify zoom plugin has limits configured."""
        content = read_ohlc_js()

        assert "limits:" in content, (
            "Zoom plugin should have limits configured "
            "to prevent over-panning or over-zooming."
        )
