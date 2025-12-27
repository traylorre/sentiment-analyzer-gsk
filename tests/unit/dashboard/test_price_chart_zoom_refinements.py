"""
Price Chart Zoom Refinements Tests for Dashboard JavaScript.

Feature 1072: Tests that verify the Price Chart zoom refinements:
1. Auto-fit data on resolution change (resetZoom on data load)
2. Legend removed for cleaner display
3. $0 price floor when zooming out

These tests use static analysis of JavaScript source code to verify:
1. chart.resetZoom() is called in updateChart method
2. legend.display is set to false
3. zoom limits include min: 0 for price

Run: pytest tests/unit/dashboard/test_price_chart_zoom_refinements.py -v
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


class TestAutoFitOnDataLoad:
    """Test that chart auto-fits data on resolution change and initial load."""

    def test_reset_zoom_called_in_update_chart(self) -> None:
        """Verify resetZoom is called when updating chart with new data."""
        content = read_ohlc_js()

        # Find the updateChart method
        update_chart_match = re.search(
            r"updateChart\([^)]*\)\s*\{([\s\S]*?)(?=\n    \w+\([^)]*\)\s*\{|\n    \/\*\*|\Z)",
            content,
        )
        assert update_chart_match, "updateChart method not found in ohlc.js"

        method_body = update_chart_match.group(1)
        assert "this.chart.resetZoom()" in method_body, (
            "resetZoom not called in updateChart method. "
            "Add this.chart.resetZoom() to auto-fit data on load."
        )

    def test_reset_zoom_before_chart_update(self) -> None:
        """Verify resetZoom is called before chart.update for proper rendering."""
        content = read_ohlc_js()

        # resetZoom should come before the final chart.update('none')
        reset_idx = content.find("this.chart.resetZoom()")
        update_idx = content.rfind("this.chart.update('none')")

        assert reset_idx != -1, "this.chart.resetZoom() not found"
        assert update_idx != -1, "this.chart.update('none') not found"
        assert reset_idx < update_idx, (
            "resetZoom should be called before chart.update('none') "
            "for proper rendering order."
        )

    def test_has_feature_1072_comment_for_reset_zoom(self) -> None:
        """Verify Feature 1072 comment exists near resetZoom call."""
        content = read_ohlc_js()

        # Check for Feature 1072 comment and resetZoom in same file
        has_feature_comment = "Feature 1072" in content and "resetZoom" in content

        assert has_feature_comment, (
            "Missing Feature 1072 reference near resetZoom. "
            "Add a comment for traceability."
        )


class TestLegendRemoved:
    """Test that chart legend is disabled for cleaner display."""

    def test_legend_display_false(self) -> None:
        """Verify legend is disabled in chart options."""
        content = read_ohlc_js()

        # Look for legend configuration with display: false
        legend_pattern = r"legend:\s*\{[^}]*display:\s*false"
        assert re.search(legend_pattern, content, re.DOTALL), (
            "Legend not disabled. " "Add legend: { display: false } to chart plugins."
        )

    def test_has_feature_1072_legend_comment(self) -> None:
        """Verify Feature 1072 comment exists for legend configuration."""
        content = read_ohlc_js()

        # Look for Feature 1072 comment near legend config
        has_legend_comment = "Feature 1072" in content and "legend" in content.lower()

        assert has_legend_comment, (
            "Missing Feature 1072 reference for legend configuration. "
            "Add a comment for traceability."
        )


class TestPriceFloorLimit:
    """Test that price axis cannot go below $0 when zooming out."""

    def test_zoom_limits_has_min_zero(self) -> None:
        """Verify zoom limits include min: 0 for price axis."""
        content = read_ohlc_js()

        # Look for limits configuration with price min: 0
        limits_pattern = r"limits:\s*\{[^}]*price:\s*\{[^}]*min:\s*0"
        assert re.search(limits_pattern, content, re.DOTALL), (
            "Zoom limits missing min: 0 for price. "
            "Add limits: { price: { min: 0 } } to prevent negative prices."
        )

    def test_has_feature_1072_floor_comment(self) -> None:
        """Verify Feature 1072 comment exists for price floor configuration."""
        content = read_ohlc_js()

        # Look for Feature 1072 comment near min: 0 or price floor
        has_floor_comment = "Feature 1072" in content and (
            "min: 0" in content or "$0" in content or "price" in content.lower()
        )

        assert has_floor_comment, (
            "Missing Feature 1072 reference for price floor. "
            "Add a comment for traceability."
        )


class TestTooltipStillWorks:
    """Test that tooltip functionality is preserved despite legend removal."""

    def test_tooltip_configuration_exists(self) -> None:
        """Verify tooltip configuration is still present."""
        content = read_ohlc_js()

        assert "tooltip:" in content, (
            "Tooltip configuration not found. "
            "Tooltip should still work after legend removal."
        )

    def test_tooltip_callbacks_exist(self) -> None:
        """Verify tooltip has callbacks for custom display."""
        content = read_ohlc_js()

        assert "callbacks:" in content, (
            "Tooltip callbacks not found. "
            "Tooltip needs callbacks to display OHLC and sentiment values."
        )
