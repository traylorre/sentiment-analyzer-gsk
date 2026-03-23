# E2E Tests: Sentiment History Regression (PRs #782, #783)
#
# Regression tests for the sentiment history 500 bug:
# - DynamoDB FilterExpression on SK sort key (illegal, caused ValidationException)
# - SentimentSourceType Literal missing "dedup" (caused pydantic ValidationError)
#
# Tests:
# 1. API returns 200 with valid data for a single ticker
# 2. API returns 200 for multiple tickers
# 3. Response schema validation (required fields, types, ranges)
# 4. Dashboard renders sentiment data visually (chart not empty)

import os

import pytest

# Check if playwright is available
try:
    from playwright.sync_api import Page

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None  # Type hint placeholder

pytestmark = [pytest.mark.e2e, pytest.mark.preprod]

# Tickers known to have real sentiment data in preprod
TICKERS_WITH_DATA = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]

# Dashboard URL
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    os.environ.get("SSE_LAMBDA_URL", "http://localhost:8000"),
)

# Preprod API URL (for direct API tests)
PREPROD_API_URL = os.environ.get(
    "PREPROD_API_URL",
    "https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws",
)


# =========================================================================
# API Tests (1-3): Sentiment History Endpoint
# =========================================================================


class TestSentimentHistoryAPI:
    """Verify /api/v2/tickers/{ticker}/sentiment/history returns valid data.

    Regression for PRs #782 (FilterExpression) and #783 (SentimentSourceType).
    """

    @pytest.fixture
    def api_client(self):
        """Sync httpx client for API tests."""
        import httpx

        return httpx.Client(base_url=PREPROD_API_URL, timeout=15.0)

    @pytest.fixture
    def auth_token(self, api_client):
        """Get anonymous auth token."""
        response = api_client.post(
            "/api/v2/auth/anonymous",
            json={},
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 201, f"Auth failed: {response.text}"
        return response.json()["token"]

    def test_sentiment_history_returns_200(self, api_client, auth_token):
        """GET /api/v2/tickers/AAPL/sentiment/history MUST return 200.

        This was the primary bug: DynamoDB rejected FilterExpression on SK,
        causing HTTP 500 on every request.
        """
        response = api_client.get(
            "/api/v2/tickers/AAPL/sentiment/history",
            params={"range": "1M", "source": "aggregated"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["count"] > 0, "Expected at least 1 data point"
        assert len(data["history"]) > 0, "History array should not be empty"

    @pytest.mark.parametrize("ticker", TICKERS_WITH_DATA)
    def test_sentiment_history_multiple_tickers(self, api_client, auth_token, ticker):
        """Sentiment history MUST work for all tracked tickers, not just AAPL."""
        response = api_client.get(
            f"/api/v2/tickers/{ticker}/sentiment/history",
            params={"range": "1M", "source": "aggregated"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # 200 with data, or 200 with empty history (ticker may lack data)
        assert (
            response.status_code == 200
        ), f"{ticker}: Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["ticker"] == ticker

    def test_sentiment_history_response_schema(self, api_client, auth_token):
        """Response MUST conform to SentimentHistoryResponse schema.

        Validates all required fields, types, and value ranges.
        Regression for PR #783: source field must accept "dedup".
        """
        response = api_client.get(
            "/api/v2/tickers/AAPL/sentiment/history",
            params={"range": "1M", "source": "aggregated"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        # Top-level required fields
        assert "ticker" in data
        assert "source" in data
        assert "history" in data
        assert "start_date" in data
        assert "end_date" in data
        assert "count" in data

        # Type checks
        assert isinstance(data["ticker"], str)
        assert isinstance(data["history"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["history"])

        # Validate each SentimentPoint
        for point in data["history"]:
            assert "date" in point, "SentimentPoint missing 'date'"
            assert "score" in point, "SentimentPoint missing 'score'"
            assert "source" in point, "SentimentPoint missing 'source'"

            # Score in valid range [-1.0, 1.0]
            assert -1.0 <= point["score"] <= 1.0, f"Score {point['score']} out of range"

            # Source must be a known type (regression: "dedup" was missing)
            valid_sources = {
                "tiingo",
                "finnhub",
                "our_model",
                "aggregated",
                "dedup",
                "unknown",
            }
            assert (
                point["source"] in valid_sources
            ), f"Unknown source '{point['source']}' — add to SentimentSourceType"

            # Label if present must be valid
            if point.get("label"):
                assert point["label"] in {"positive", "neutral", "negative"}

            # Date format YYYY-MM-DD
            assert len(point["date"]) == 10, f"Bad date format: {point['date']}"


# =========================================================================
# Visual Test (4): Dashboard Chart Renders Sentiment Data
# =========================================================================


@pytest.mark.skipif(
    not PLAYWRIGHT_AVAILABLE,
    reason="pytest-playwright not installed (pip install pytest-playwright)",
)
class TestSentimentChartVisual:
    """Verify sentiment data is visually rendered on the dashboard.

    The sentiment distribution chart (doughnut) and sentiment trend chart
    must show non-zero data when the page loads. Previously, all users
    saw empty sentiment because the overview endpoint returned {}.
    """

    @pytest.fixture
    def dashboard_page(self, page: Page) -> Page:
        """Navigate to dashboard and wait for data to load."""
        page.goto(DASHBOARD_URL)
        # Wait for dashboard to initialize (status indicator appears)
        page.wait_for_selector("#status-indicator", timeout=15000)
        return page

    def test_sentiment_percentages_are_not_zero(self, dashboard_page: Page):
        """At least one sentiment percentage (positive/neutral/negative) MUST be non-zero.

        If all three show "0%", sentiment data is not reaching the frontend.
        This was the user-facing symptom of the broken overview endpoint.
        """
        # Wait for metrics to load (skeleton removed)
        dashboard_page.wait_for_function(
            """() => {
                const pos = document.getElementById('positive-pct');
                const neu = document.getElementById('neutral-pct');
                const neg = document.getElementById('negative-pct');
                if (!pos || !neu || !neg) return false;
                // At least one must be non-zero
                return pos.textContent !== '0%'
                    || neu.textContent !== '0%'
                    || neg.textContent !== '0%';
            }""",
            timeout=15000,
        )

        # Read actual values for the assertion message
        pos = dashboard_page.text_content("#positive-pct")
        neu = dashboard_page.text_content("#neutral-pct")
        neg = dashboard_page.text_content("#negative-pct")

        has_data = pos != "0%" or neu != "0%" or neg != "0%"
        assert has_data, (
            f"All sentiment percentages are 0% "
            f"(positive={pos}, neutral={neu}, negative={neg}) — "
            f"data is not reaching the frontend"
        )

    def test_sentiment_chart_canvas_has_content(self, dashboard_page: Page):
        """The sentiment doughnut chart canvas MUST have rendered pixels.

        A blank canvas means Chart.js received [0, 0, 0] data — i.e.,
        the sentiment overview returned empty.
        """
        # Wait for chart initialization
        dashboard_page.wait_for_function(
            "typeof Chart !== 'undefined'",
            timeout=10000,
        )

        # Give chart time to render with data
        dashboard_page.wait_for_timeout(3000)

        # Check if canvas has been drawn on (non-blank)
        has_content = dashboard_page.evaluate(
            """() => {
                const canvas = document.getElementById('sentiment-chart');
                if (!canvas) return false;
                const ctx = canvas.getContext('2d');
                // Sample pixels from center area of chart
                const w = canvas.width;
                const h = canvas.height;
                const imageData = ctx.getImageData(
                    Math.floor(w * 0.3), Math.floor(h * 0.3),
                    Math.floor(w * 0.4), Math.floor(h * 0.4)
                );
                // Check if any pixel has non-zero alpha (i.e., something was drawn)
                for (let i = 3; i < imageData.data.length; i += 4) {
                    if (imageData.data[i] > 0) return true;
                }
                return false;
            }"""
        )

        assert has_content, (
            "Sentiment chart canvas is blank — Chart.js rendered nothing. "
            "Check that sentiment data is flowing from API to chart."
        )

    def test_timeseries_chart_loads_sentiment_data(self, dashboard_page: Page):
        """The timeseries trend chart MUST display sentiment data points.

        Checks that the Chart.js timeseries chart has at least 1 data point
        in its dataset, indicating sentiment trend data loaded successfully.
        """
        # Wait for timeseries module
        dashboard_page.wait_for_function(
            "typeof timeseriesManager !== 'undefined'",
            timeout=10000,
        )

        # Wait for chart to load data
        dashboard_page.wait_for_timeout(3000)

        # Check if timeseries chart has data points
        data_count = dashboard_page.evaluate(
            """() => {
                const canvas = document.getElementById('timeseries-chart');
                if (!canvas) return -1;
                // Access Chart.js instance from canvas
                const chart = Chart.getChart(canvas);
                if (!chart) return -2;
                // Check first dataset for data points
                const datasets = chart.data.datasets;
                if (!datasets || datasets.length === 0) return 0;
                return datasets[0].data ? datasets[0].data.length : 0;
            }"""
        )

        assert data_count > 0, (
            f"Timeseries chart has {data_count} data points "
            f"(expected > 0). Sentiment trend data is not loading."
        )
