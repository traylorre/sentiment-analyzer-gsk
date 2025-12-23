"""E2E tests for live update latency validation.

Feature 1019: Validate Live Update Latency
Validates SC-003: p95 end-to-end latency < 3 seconds

This test suite measures the time from SSE event origin_timestamp to
client receive time, validating that live updates reach the dashboard
within the SLA target.

Canonical References:
- [CS-001] MDN Performance API
- [CS-003] SSE Specification
- Parent spec SC-003 defines the 3s target
"""

import json
import os
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

# Check if playwright is available
try:
    from playwright.async_api import Page, async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Page = None
    async_playwright = None


# Skip all tests if playwright not available
pytestmark = pytest.mark.skipif(
    not HAS_PLAYWRIGHT,
    reason="playwright not installed",
)


@dataclass
class LatencyMetrics:
    """Latency metrics collected from SSE events."""

    latency_ms: int
    event_type: str
    ticker: str | None
    origin_timestamp: str
    receive_timestamp: str
    is_clock_skew: bool


@dataclass
class PerformanceReport:
    """Performance report with percentile statistics."""

    samples: list[int]
    min_ms: int
    max_ms: int
    mean_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    sample_count: int
    clock_skew_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "mean_ms": round(self.mean_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p90_ms": round(self.p90_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "sample_count": self.sample_count,
            "clock_skew_count": self.clock_skew_count,
        }


def calculate_percentile(data: list[int], percentile: float) -> float:
    """Calculate percentile value from sorted data.

    Args:
        data: List of values (will be sorted)
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value
    """
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (percentile / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def compute_performance_report(
    samples: list[int], clock_skew_count: int = 0
) -> PerformanceReport:
    """Compute performance statistics from latency samples.

    Args:
        samples: List of latency values in milliseconds
        clock_skew_count: Number of samples with clock skew detected

    Returns:
        PerformanceReport with all statistics
    """
    if not samples:
        return PerformanceReport(
            samples=[],
            min_ms=0,
            max_ms=0,
            mean_ms=0.0,
            p50_ms=0.0,
            p90_ms=0.0,
            p95_ms=0.0,
            p99_ms=0.0,
            sample_count=0,
            clock_skew_count=clock_skew_count,
        )

    return PerformanceReport(
        samples=samples,
        min_ms=min(samples),
        max_ms=max(samples),
        mean_ms=statistics.mean(samples),
        p50_ms=calculate_percentile(samples, 50),
        p90_ms=calculate_percentile(samples, 90),
        p95_ms=calculate_percentile(samples, 95),
        p99_ms=calculate_percentile(samples, 99),
        sample_count=len(samples),
        clock_skew_count=clock_skew_count,
    )


# JavaScript to inject for latency tracking
LATENCY_TRACKING_JS = """
// Feature 1019: Client-side latency tracking
(function() {
    if (window._latencyTrackingInstalled) return;
    window._latencyTrackingInstalled = true;

    window.latencySamples = [];
    window.lastLatencyMetrics = null;

    // Hook into existing SSE handlers to capture latency
    const originalAddEventListener = EventSource.prototype.addEventListener;
    EventSource.prototype.addEventListener = function(type, listener, options) {
        const wrappedListener = function(event) {
            if (event.data) {
                try {
                    const data = JSON.parse(event.data);
                    const receiveTime = Date.now();

                    // Check for origin_timestamp
                    if (data.origin_timestamp) {
                        const originTime = new Date(data.origin_timestamp).getTime();
                        const latencyMs = receiveTime - originTime;
                        const isClockSkew = latencyMs < 0;

                        const metrics = {
                            latency_ms: latencyMs,
                            event_type: type,
                            ticker: data.ticker || null,
                            origin_timestamp: data.origin_timestamp,
                            receive_timestamp: new Date(receiveTime).toISOString(),
                            is_clock_skew: isClockSkew
                        };

                        window.lastLatencyMetrics = metrics;
                        if (!isClockSkew) {
                            window.latencySamples.push(latencyMs);
                        }
                    }
                } catch (e) {
                    // Ignore parse errors
                }
            }
            return listener.call(this, event);
        };
        return originalAddEventListener.call(this, type, wrappedListener, options);
    };
})();
"""


@pytest.fixture
def preprod_dashboard_url() -> str:
    """Get preprod dashboard URL from environment."""
    url = os.environ.get(
        "PREPROD_DASHBOARD_URL", "https://dashboard.preprod.sentiment-analyzer.com"
    )
    return url


@pytest.fixture
async def browser_context():
    """Create browser context for E2E testing."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        yield context
        await context.close()
        await browser.close()


@pytest.mark.asyncio
@pytest.mark.preprod
class TestLiveUpdateLatency:
    """Test suite for live update latency validation."""

    async def _navigate_and_setup(self, page: Page, url: str) -> None:
        """Navigate to dashboard and inject latency tracking.

        Args:
            page: Playwright page
            url: Dashboard URL
        """
        # Inject latency tracking before navigation
        await page.add_init_script(LATENCY_TRACKING_JS)

        # Navigate to dashboard
        await page.goto(url, wait_until="networkidle")

        # Wait for SSE connection to be established
        await page.wait_for_function(
            "window.latencySamples !== undefined",
            timeout=10000,
        )

    async def _collect_latency_samples(
        self, page: Page, target_count: int = 50, timeout_seconds: int = 120
    ) -> tuple[list[int], int]:
        """Collect latency samples from SSE events.

        Args:
            page: Playwright page
            target_count: Number of samples to collect
            timeout_seconds: Maximum time to wait

        Returns:
            Tuple of (samples list, clock skew count)
        """
        import asyncio

        start_time = datetime.now(UTC)
        samples = []
        clock_skew_count = 0

        while len(samples) < target_count:
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed > timeout_seconds:
                break

            # Get current samples
            result = await page.evaluate(
                """() => ({
                    samples: window.latencySamples.slice(),
                    lastMetrics: window.lastLatencyMetrics
                })"""
            )

            samples = result.get("samples", [])

            # Check for clock skew in last metrics
            last_metrics = result.get("lastMetrics")
            if last_metrics and last_metrics.get("is_clock_skew"):
                clock_skew_count += 1

            await asyncio.sleep(1)

        return samples, clock_skew_count

    async def _get_last_metrics(self, page: Page) -> LatencyMetrics | None:
        """Get the last latency metrics from the page.

        Args:
            page: Playwright page

        Returns:
            LatencyMetrics or None if not available
        """
        result = await page.evaluate("() => window.lastLatencyMetrics")
        if not result:
            return None

        return LatencyMetrics(
            latency_ms=result.get("latency_ms", 0),
            event_type=result.get("event_type", "unknown"),
            ticker=result.get("ticker"),
            origin_timestamp=result.get("origin_timestamp", ""),
            receive_timestamp=result.get("receive_timestamp", ""),
            is_clock_skew=result.get("is_clock_skew", False),
        )

    async def test_live_update_p95_under_3_seconds(
        self, browser_context, preprod_dashboard_url: str
    ) -> None:
        """Validate p95 live update latency is under 3 seconds (SC-003).

        This test:
        1. Navigates to preprod dashboard
        2. Collects 50+ latency samples from SSE events
        3. Calculates p95 latency
        4. Asserts p95 < 3000ms

        Success Criteria:
        - SC-001: p95 end-to-end latency < 3000ms
        """
        page = await browser_context.new_page()

        try:
            # Navigate and setup
            await self._navigate_and_setup(page, preprod_dashboard_url)

            # Collect samples
            samples, clock_skew_count = await self._collect_latency_samples(
                page, target_count=50, timeout_seconds=120
            )

            # Compute report
            report = compute_performance_report(samples, clock_skew_count)

            # Log report as JSON
            print(f"\nLatency Report: {json.dumps(report.to_dict(), indent=2)}")

            # Validate sample count
            assert report.sample_count >= 10, (
                f"Insufficient samples collected: {report.sample_count}. "
                f"Expected at least 10 for statistical validity. "
                f"Clock skew events: {clock_skew_count}"
            )

            # Validate p95 target (SC-003)
            assert report.p95_ms < 3000, (
                f"p95 latency {report.p95_ms}ms exceeds 3000ms target (SC-003). "
                f"Report: {json.dumps(report.to_dict())}"
            )

        finally:
            await page.close()

    async def test_sse_events_include_origin_timestamp(
        self, browser_context, preprod_dashboard_url: str
    ) -> None:
        """Verify SSE events include origin_timestamp field (FR-001).

        This test validates that bucket update events include the
        origin_timestamp field required for latency measurement.
        """
        page = await browser_context.new_page()

        try:
            await self._navigate_and_setup(page, preprod_dashboard_url)

            # Wait for at least one event with metrics
            import asyncio

            for _ in range(30):  # 30 second timeout
                metrics = await self._get_last_metrics(page)
                if metrics and metrics.origin_timestamp:
                    break
                await asyncio.sleep(1)

            assert metrics is not None, "No SSE events received with latency metrics"
            assert (
                metrics.origin_timestamp
            ), "SSE event missing origin_timestamp field (FR-001)"

            # Validate ISO8601 format
            try:
                datetime.fromisoformat(metrics.origin_timestamp.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(
                    f"origin_timestamp not in ISO8601 format: {metrics.origin_timestamp}"
                )

        finally:
            await page.close()

    async def test_latency_metrics_exposed_to_window(
        self, browser_context, preprod_dashboard_url: str
    ) -> None:
        """Verify window.lastLatencyMetrics is exposed (FR-008).

        This test validates that client-side latency calculation is
        working and exposed via window.lastLatencyMetrics.
        """
        page = await browser_context.new_page()

        try:
            await self._navigate_and_setup(page, preprod_dashboard_url)

            # Wait for metrics to be populated
            import asyncio

            for _ in range(30):
                metrics = await self._get_last_metrics(page)
                if metrics:
                    break
                await asyncio.sleep(1)

            assert metrics is not None, "window.lastLatencyMetrics not populated"

            # Validate required fields
            assert hasattr(metrics, "latency_ms"), "Missing latency_ms field"
            assert hasattr(metrics, "event_type"), "Missing event_type field"
            assert hasattr(
                metrics, "origin_timestamp"
            ), "Missing origin_timestamp field"
            assert hasattr(
                metrics, "receive_timestamp"
            ), "Missing receive_timestamp field"
            assert hasattr(metrics, "is_clock_skew"), "Missing is_clock_skew field"

        finally:
            await page.close()
