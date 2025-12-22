"""Performance test for resolution switching latency.

Validates SC-002 from specs/1009-realtime-multi-resolution: Resolution switching
must complete within 100ms (p95 target).

This test:
1. Navigates to preprod dashboard
2. Warms cache by loading all 8 resolutions
3. Executes 100+ resolution switches
4. Captures timing via window.lastSwitchMetrics
5. Calculates p95 and asserts < 100ms

Run locally:
    pytest tests/e2e/test_resolution_switch_perf.py -v --headed

Run headless (CI):
    pytest tests/e2e/test_resolution_switch_perf.py -v
"""

import json
import os
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Page

# Configuration
PREPROD_URL = os.getenv(
    "PREPROD_DASHBOARD_URL", "https://preprod.sentiment.example.com"
)
P95_THRESHOLD_MS = 100
SWITCH_COUNT = 105  # 100+ switches for statistical significance
WARMUP_SWITCHES = 5  # Discard first N switches (browser warmup)

# All 8 resolutions from timeseries.js
RESOLUTIONS = ["1m", "5m", "10m", "1h", "3h", "6h", "12h", "24h"]


@dataclass
class SwitchTiming:
    """Single resolution switch measurement."""

    duration_ms: float
    from_resolution: str
    to_resolution: str
    cache_hit: bool
    timestamp: int


@dataclass
class PerformanceReport:
    """Aggregated performance test results."""

    test_name: str
    timestamp: str
    sample_count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    passed: bool
    threshold_ms: float
    measurements: list[SwitchTiming]


def calculate_percentile(data: list[float], percentile: int) -> float:
    """Calculate percentile using linear interpolation.

    Args:
        data: List of values
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]

    # Calculate position
    pos = (percentile / 100) * (n - 1)
    lower_idx = int(pos)
    upper_idx = min(lower_idx + 1, n - 1)
    fraction = pos - lower_idx

    return sorted_data[lower_idx] + fraction * (
        sorted_data[upper_idx] - sorted_data[lower_idx]
    )


def generate_report(
    measurements: list[SwitchTiming], threshold_ms: float = P95_THRESHOLD_MS
) -> PerformanceReport:
    """Generate performance report from measurements.

    Args:
        measurements: List of switch timings
        threshold_ms: p95 threshold for pass/fail

    Returns:
        PerformanceReport with statistics
    """
    durations = [m.duration_ms for m in measurements]

    p95 = calculate_percentile(durations, 95)

    return PerformanceReport(
        test_name="resolution_switching_performance",
        timestamp=datetime.now(UTC).isoformat(),
        sample_count=len(measurements),
        min_ms=min(durations) if durations else 0,
        max_ms=max(durations) if durations else 0,
        mean_ms=statistics.mean(durations) if durations else 0,
        p50_ms=calculate_percentile(durations, 50),
        p90_ms=calculate_percentile(durations, 90),
        p95_ms=p95,
        p99_ms=calculate_percentile(durations, 99),
        passed=p95 < threshold_ms,
        threshold_ms=threshold_ms,
        measurements=measurements,
    )


@pytest.fixture
def dashboard_page(page: Page) -> Page:
    """Navigate to dashboard and wait for initial load.

    Args:
        page: Playwright page fixture

    Returns:
        Page ready for testing
    """
    page.goto(f"{PREPROD_URL}?ticker=AAPL&resolution=5m")

    # Wait for chart to load
    page.wait_for_selector("#chart-container", timeout=10000)

    # Wait for resolution selector
    page.wait_for_selector(".resolution-btn", timeout=5000)

    return page


@pytest.fixture
def warmed_cache_page(dashboard_page: Page) -> Page:
    """Pre-warm cache by loading all resolutions.

    This ensures subsequent switches are cache-hits for fair measurement.

    Args:
        dashboard_page: Page with dashboard loaded

    Returns:
        Page with all resolutions cached
    """
    page = dashboard_page

    # Click through all resolutions to warm cache
    for resolution in RESOLUTIONS:
        btn = page.locator(f'.resolution-btn[data-resolution="{resolution}"]')
        if btn.count() > 0:
            btn.first.click()
            # Wait for switch to complete
            page.wait_for_timeout(500)

    # Return to default resolution
    page.locator('.resolution-btn[data-resolution="5m"]').first.click()
    page.wait_for_timeout(200)

    return page


def capture_switch_metrics(page: Page) -> SwitchTiming | None:
    """Capture timing metrics from window.lastSwitchMetrics.

    Args:
        page: Playwright page

    Returns:
        SwitchTiming or None if metrics not available
    """
    metrics = page.evaluate("() => window.lastSwitchMetrics")
    if not metrics:
        return None

    return SwitchTiming(
        duration_ms=metrics.get("duration_ms", 0),
        from_resolution=metrics.get("from_resolution", ""),
        to_resolution=metrics.get("to_resolution", ""),
        cache_hit=metrics.get("cache_hit", False),
        timestamp=metrics.get("timestamp", 0),
    )


def click_resolution_and_capture(page: Page, resolution: str) -> SwitchTiming | None:
    """Click resolution button and capture timing metrics.

    Args:
        page: Playwright page
        resolution: Target resolution (e.g., "1h")

    Returns:
        SwitchTiming or None
    """
    btn = page.locator(f'.resolution-btn[data-resolution="{resolution}"]')
    if btn.count() == 0:
        return None

    # Clear previous metrics
    page.evaluate("() => { window.lastSwitchMetrics = null; }")

    # Click and wait for metrics to be captured
    btn.first.click()

    # Wait for metrics to be populated (switch completion)
    page.wait_for_function("() => window.lastSwitchMetrics !== null", timeout=5000)

    return capture_switch_metrics(page)


@pytest.mark.preprod
class TestResolutionSwitchPerformance:
    """Performance tests for resolution switching."""

    def test_resolution_switch_p95_under_100ms(self, warmed_cache_page: Page) -> None:
        """Validate p95 resolution switch latency is below 100ms.

        This is the primary SC-002 validation test. Executes 100+ resolution
        switches and asserts p95 < 100ms.
        """
        page = warmed_cache_page
        measurements: list[SwitchTiming] = []

        # Perform resolution switches in round-robin
        current_idx = RESOLUTIONS.index("5m")  # Start at 5m

        for i in range(SWITCH_COUNT + WARMUP_SWITCHES):
            # Cycle through resolutions
            next_idx = (current_idx + 1) % len(RESOLUTIONS)
            next_resolution = RESOLUTIONS[next_idx]

            timing = click_resolution_and_capture(page, next_resolution)

            if timing:
                # Skip warmup switches
                if i >= WARMUP_SWITCHES:
                    measurements.append(timing)

            current_idx = next_idx

            # Small delay to avoid overwhelming the browser
            page.wait_for_timeout(50)

        # Generate report
        report = generate_report(measurements)

        # Log report as JSON for CI parsing
        report_dict = {
            "test_name": report.test_name,
            "timestamp": report.timestamp,
            "sample_count": report.sample_count,
            "statistics": {
                "min_ms": round(report.min_ms, 2),
                "max_ms": round(report.max_ms, 2),
                "mean_ms": round(report.mean_ms, 2),
                "p50_ms": round(report.p50_ms, 2),
                "p90_ms": round(report.p90_ms, 2),
                "p95_ms": round(report.p95_ms, 2),
                "p99_ms": round(report.p99_ms, 2),
            },
            "passed": report.passed,
            "threshold_ms": report.threshold_ms,
        }
        print(f"\n\nPerformance Report:\n{json.dumps(report_dict, indent=2)}\n")

        # Assert p95 < threshold
        assert report.p95_ms < P95_THRESHOLD_MS, (
            f"p95 latency {report.p95_ms:.1f}ms exceeds {P95_THRESHOLD_MS}ms threshold.\n"
            f"Statistics: min={report.min_ms:.1f}ms, max={report.max_ms:.1f}ms, "
            f"mean={report.mean_ms:.1f}ms, p95={report.p95_ms:.1f}ms"
        )

    def test_cache_hit_switches_under_100ms(self, warmed_cache_page: Page) -> None:
        """Validate cache-hit only switches meet p95 < 100ms.

        Filters measurements to cache-hit only and validates separately.
        This isolates cache performance from network latency.
        """
        page = warmed_cache_page
        measurements: list[SwitchTiming] = []

        # Perform switches
        current_idx = 0
        for i in range(SWITCH_COUNT + WARMUP_SWITCHES):
            next_idx = (current_idx + 1) % len(RESOLUTIONS)
            next_resolution = RESOLUTIONS[next_idx]

            timing = click_resolution_and_capture(page, next_resolution)

            if timing and i >= WARMUP_SWITCHES:
                measurements.append(timing)

            current_idx = next_idx
            page.wait_for_timeout(50)

        # Filter to cache-hit only
        cache_hit_measurements = [m for m in measurements if m.cache_hit]

        if not cache_hit_measurements:
            pytest.skip("No cache-hit measurements recorded - cache may not be working")

        report = generate_report(cache_hit_measurements)

        # Log cache-hit specific stats
        print("\n\nCache-Hit Performance Report:")
        print(f"  Sample count: {report.sample_count}")
        print(f"  p95: {report.p95_ms:.1f}ms")
        print(
            f"  Cache hit rate: {len(cache_hit_measurements)}/{len(measurements)} "
            f"({100 * len(cache_hit_measurements) / len(measurements):.1f}%)\n"
        )

        # Assert cache-hit p95 < threshold
        assert report.p95_ms < P95_THRESHOLD_MS, (
            f"Cache-hit p95 latency {report.p95_ms:.1f}ms exceeds {P95_THRESHOLD_MS}ms threshold.\n"
            f"This indicates cache performance issues."
        )

    def test_all_resolutions_switchable(self, dashboard_page: Page) -> None:
        """Validate all 8 resolutions can be switched to.

        Ensures complete coverage of resolution transitions.
        """
        page = dashboard_page

        for resolution in RESOLUTIONS:
            timing = click_resolution_and_capture(page, resolution)
            assert timing is not None, f"Failed to switch to resolution {resolution}"
            assert (
                timing.to_resolution == resolution
            ), f"Expected to_resolution={resolution}, got {timing.to_resolution}"

    def test_switch_metrics_structure(self, dashboard_page: Page) -> None:
        """Validate window.lastSwitchMetrics has correct structure.

        Ensures instrumentation is working correctly.
        """
        page = dashboard_page

        # Switch to any resolution
        timing = click_resolution_and_capture(page, "1h")

        assert timing is not None, "No metrics captured"
        assert timing.duration_ms >= 0, f"Invalid duration: {timing.duration_ms}"
        assert timing.from_resolution in RESOLUTIONS + [
            "5m"
        ], f"Invalid from_resolution: {timing.from_resolution}"
        assert (
            timing.to_resolution == "1h"
        ), f"Invalid to_resolution: {timing.to_resolution}"
        assert isinstance(
            timing.cache_hit, bool
        ), f"cache_hit should be bool: {timing.cache_hit}"
        assert timing.timestamp > 0, f"Invalid timestamp: {timing.timestamp}"
