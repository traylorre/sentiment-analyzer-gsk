"""
Time Axis Formatting Tests for Dashboard JavaScript.

Feature 1081: Tests that verify the time axis includes date context
for multi-day intraday data.

These tests use static analysis of JavaScript source code to verify:
1. isDifferentDay helper method exists
2. formatTimestamp accepts index and candles parameters
3. Day boundary detection logic exists with abbreviated date format
4. Feature 1081 comment exists for traceability

Run: pytest tests/unit/dashboard/test_time_axis_formatting.py -v
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


class TestDayBoundaryDetection:
    """Test that day boundary detection is implemented."""

    def test_is_different_day_method_exists(self) -> None:
        """Verify isDifferentDay helper method exists."""
        content = read_ohlc_js()

        assert "isDifferentDay" in content, (
            "isDifferentDay method not found. "
            "Add helper to detect day boundaries (Feature 1081)."
        )

    def test_is_different_day_compares_dates(self) -> None:
        """Verify isDifferentDay uses toDateString for comparison."""
        content = read_ohlc_js()

        assert "toDateString()" in content, (
            "toDateString not found. "
            "Use toDateString() for reliable day comparison (Feature 1081)."
        )

    def test_has_feature_1081_comment(self) -> None:
        """Verify Feature 1081 comment exists in ohlc.js for traceability."""
        content = read_ohlc_js()

        assert "Feature 1081" in content or "1081" in content, (
            "Missing Feature 1081 reference in ohlc.js. "
            "Add a comment for traceability."
        )


class TestFormatTimestampSignature:
    """Test that formatTimestamp accepts context parameters."""

    def test_format_timestamp_accepts_index(self) -> None:
        """Verify formatTimestamp has index parameter."""
        content = read_ohlc_js()

        # Look for formatTimestamp with index parameter
        pattern = r"formatTimestamp\s*\([^)]*index"
        assert re.search(pattern, content), (
            "formatTimestamp missing index parameter. "
            "Add index for day boundary detection (Feature 1081)."
        )

    def test_format_timestamp_accepts_candles(self) -> None:
        """Verify formatTimestamp has candles parameter."""
        content = read_ohlc_js()

        # Look for formatTimestamp with candles parameter
        pattern = r"formatTimestamp\s*\([^)]*candles"
        assert re.search(pattern, content), (
            "formatTimestamp missing candles parameter. "
            "Add candles array for day boundary context (Feature 1081)."
        )


class TestDayBoundaryFormatting:
    """Test that day boundaries show abbreviated date format."""

    def test_weekday_format_exists(self) -> None:
        """Verify weekday abbreviation is used for day boundaries."""
        content = read_ohlc_js()

        # Look for weekday format option
        pattern = r"weekday:\s*['\"]short['\"]"
        assert re.search(pattern, content), (
            "Weekday abbreviation not found. "
            "Use { weekday: 'short' } for day labels (Feature 1081)."
        )

    def test_month_day_format_exists(self) -> None:
        """Verify month/day format is used for day boundaries."""
        content = read_ohlc_js()

        # Look for month/day construction
        pattern = r"getMonth\(\)|getDate\(\)"
        assert re.search(pattern, content), (
            "Month/day extraction not found. "
            "Use getMonth()/getDate() for 'Mon 12/23' format (Feature 1081)."
        )


class TestLabelGeneration:
    """Test that label generation passes context to formatTimestamp."""

    def test_labels_map_passes_index(self) -> None:
        """Verify labels.map passes index to formatTimestamp."""
        content = read_ohlc_js()

        # Look for map with index parameter
        pattern = r"candles\.map\s*\(\s*\(\s*c\s*,\s*i\s*\)"
        assert re.search(pattern, content), (
            "Labels map not passing index. "
            "Use candles.map((c, i) => ...) for index access (Feature 1081)."
        )

    def test_labels_map_passes_candles(self) -> None:
        """Verify formatTimestamp is called with candles array."""
        content = read_ohlc_js()

        # Look for formatTimestamp call with candles
        pattern = r"formatTimestamp\s*\([^)]+,\s*i\s*,\s*candles\s*\)"
        assert re.search(pattern, content), (
            "formatTimestamp not receiving candles. "
            "Pass candles array for day boundary detection (Feature 1081)."
        )


class TestDayResolutionUnchanged:
    """Test that Day resolution formatting is preserved."""

    def test_day_resolution_uses_month_short(self) -> None:
        """Verify Day resolution still uses 'Dec 23' format."""
        content = read_ohlc_js()

        # Look for month: 'short' in the Day resolution branch
        pattern = r"month:\s*['\"]short['\"]"
        assert re.search(pattern, content), (
            "Day resolution format missing month: 'short'. "
            "Preserve 'Dec 23' format for Day resolution."
        )

    def test_day_resolution_check_exists(self) -> None:
        """Verify resolution === 'D' check exists."""
        content = read_ohlc_js()

        pattern = r"resolution\s*===\s*['\"]D['\"]"
        assert re.search(pattern, content), (
            "Day resolution check not found. "
            "Use resolution === 'D' to detect daily data."
        )
