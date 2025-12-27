"""
Window Export Registry for Dashboard JavaScript Files.

This registry defines the required window exports for each vanilla JS dashboard file.
Tests validate that all exports exist via static analysis (regex parsing).

This prevents regressions like Feature 1066 where functions were defined but not exported.

Usage:
    from tests.unit.dashboard.window_export_registry import WINDOW_EXPORT_REGISTRY
"""

# Registry of required window exports per file
# Format: { "relative/path/to/file.js": ["export1", "export2", ...] }
WINDOW_EXPORT_REGISTRY: dict[str, list[str]] = {
    # OHLC Chart - candlestick visualization with sentiment overlay
    "src/dashboard/ohlc.js": [
        "OHLCChart",  # Class export
        "setOHLCResolution",  # Change chart resolution
        "hideOHLCResolutionSelector",  # Hide resolution UI
        "loadOHLCSentimentOverlay",  # Load sentiment data on chart
        "initOHLCChart",  # Initialize chart (Feature 1066 fix)
        "updateOHLCTicker",  # Update ticker symbol (Feature 1066 fix)
    ],
    # Timeseries Chart - sentiment trends over time
    "src/dashboard/timeseries.js": [
        "setSentimentResolution",  # Change resolution
        "hideSentimentResolutionSelector",  # Hide resolution UI
        "getTimeseriesManager",  # Get chart manager instance
    ],
    # Unified Resolution Selector - shared resolution control
    "src/dashboard/unified-resolution.js": [
        "initUnifiedResolution",  # Initialize selector
        "getUnifiedResolution",  # Get current resolution
    ],
}

# Files that are intentionally exempt from export validation
# (e.g., utility files, config files, internal modules)
EXEMPT_FILES: set[str] = {
    "src/dashboard/cache.js",  # Internal caching utility
    "src/dashboard/config.js",  # Configuration constants
    "src/dashboard/app.js",  # Consumer, not exporter
}
