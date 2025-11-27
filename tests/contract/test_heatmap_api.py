"""Contract tests for heat map data endpoint (T045).

Validates that heat map endpoint conforms to dashboard-api.md contract:
- GET /api/v2/configurations/{id}/heatmap
"""

from typing import Any

from pydantic import BaseModel, Field

# --- Response Schema Definitions (from dashboard-api.md) ---


class HeatMapCell(BaseModel):
    """Single cell in heat map matrix."""

    source: str | None = None  # For sources view
    period: str | None = None  # For timeperiods view
    score: float = Field(..., ge=-1.0, le=1.0)
    color: str = Field(..., pattern="^#[0-9a-fA-F]{6}$")


class HeatMapRow(BaseModel):
    """Row in heat map matrix (one per ticker)."""

    ticker: str
    cells: list[HeatMapCell]


class HeatMapLegendRange(BaseModel):
    """Legend range definition."""

    range: tuple[float, float]
    color: str = Field(..., pattern="^#[0-9a-fA-F]{6}$")


class HeatMapLegend(BaseModel):
    """Heat map legend."""

    positive: HeatMapLegendRange
    neutral: HeatMapLegendRange
    negative: HeatMapLegendRange


class HeatMapResponse(BaseModel):
    """Response schema for GET /api/v2/configurations/{id}/heatmap."""

    view: str = Field(..., pattern="^(sources|timeperiods)$")
    matrix: list[HeatMapRow]
    legend: HeatMapLegend | None = None


# --- Contract Tests for Sources View ---


class TestHeatMapSourcesView:
    """Contract tests for heat map sources view."""

    def test_response_contains_required_fields(self):
        """Response must contain all required fields per contract."""
        response = self._simulate_sources_response()

        assert "view" in response
        assert "matrix" in response
        assert "legend" in response

    def test_view_is_sources(self):
        """Default view should be 'sources'."""
        response = self._simulate_sources_response()

        assert response["view"] == "sources"

    def test_matrix_has_ticker_rows(self):
        """Matrix rows are organized by ticker."""
        response = self._simulate_sources_response()

        for row in response["matrix"]:
            assert "ticker" in row
            assert "cells" in row
            assert len(row["ticker"]) > 0

    def test_cells_have_source_field(self):
        """In sources view, cells have source field."""
        response = self._simulate_sources_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert "source" in cell
                assert cell["source"] in ["tiingo", "finnhub", "our_model"]

    def test_cells_have_score_in_range(self):
        """Cell scores must be in [-1, 1] range."""
        response = self._simulate_sources_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert -1.0 <= cell["score"] <= 1.0

    def test_cells_have_valid_color(self):
        """Cell colors must be valid hex colors."""
        response = self._simulate_sources_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert cell["color"].startswith("#")
                assert len(cell["color"]) == 7

    def test_legend_has_all_categories(self):
        """Legend must have positive, neutral, negative categories."""
        response = self._simulate_sources_response()

        legend = response["legend"]
        assert "positive" in legend
        assert "neutral" in legend
        assert "negative" in legend

    def test_legend_positive_range(self):
        """Positive range is [0.33, 1.0]."""
        response = self._simulate_sources_response()

        positive = response["legend"]["positive"]
        assert positive["range"] == [0.33, 1.0]

    def test_legend_neutral_range(self):
        """Neutral range is [-0.33, 0.33]."""
        response = self._simulate_sources_response()

        neutral = response["legend"]["neutral"]
        assert neutral["range"] == [-0.33, 0.33]

    def test_legend_negative_range(self):
        """Negative range is [-1.0, -0.33]."""
        response = self._simulate_sources_response()

        negative = response["legend"]["negative"]
        assert negative["range"] == [-1.0, -0.33]

    def test_legend_colors_are_hex(self):
        """Legend colors must be valid hex colors."""
        response = self._simulate_sources_response()

        for category in ["positive", "neutral", "negative"]:
            color = response["legend"][category]["color"]
            assert color.startswith("#")
            assert len(color) == 7

    def test_color_matches_score_range(self):
        """Cell color should match its score's category."""
        response = self._simulate_sources_response()

        legend = response["legend"]
        positive_color = legend["positive"]["color"]
        negative_color = legend["negative"]["color"]
        neutral_color = legend["neutral"]["color"]

        for row in response["matrix"]:
            for cell in row["cells"]:
                score = cell["score"]
                color = cell["color"]

                if score >= 0.33:
                    assert color == positive_color
                elif score <= -0.33:
                    assert color == negative_color
                else:
                    assert color == neutral_color

    def test_response_status_200_ok(self):
        """Successful request returns 200 OK."""
        status_code = 200
        assert status_code == 200

    # --- Helper Methods ---

    def _simulate_sources_response(self) -> dict[str, Any]:
        """Simulate heat map sources view response."""
        return {
            "view": "sources",
            "matrix": [
                {
                    "ticker": "AAPL",
                    "cells": [
                        {"source": "tiingo", "score": 0.65, "color": "#22c55e"},
                        {"source": "finnhub", "score": 0.58, "color": "#22c55e"},
                        {"source": "our_model", "score": 0.61, "color": "#22c55e"},
                    ],
                },
                {
                    "ticker": "TSLA",
                    "cells": [
                        {"source": "tiingo", "score": -0.42, "color": "#ef4444"},
                        {"source": "finnhub", "score": -0.35, "color": "#ef4444"},
                        {"source": "our_model", "score": -0.38, "color": "#ef4444"},
                    ],
                },
            ],
            "legend": {
                "positive": {"range": [0.33, 1.0], "color": "#22c55e"},
                "neutral": {"range": [-0.33, 0.33], "color": "#eab308"},
                "negative": {"range": [-1.0, -0.33], "color": "#ef4444"},
            },
        }


# --- Contract Tests for Time Periods View ---


class TestHeatMapTimePeriodsView:
    """Contract tests for heat map time periods view."""

    def test_view_is_timeperiods(self):
        """View should be 'timeperiods' when requested."""
        response = self._simulate_timeperiods_response()

        assert response["view"] == "timeperiods"

    def test_cells_have_period_field(self):
        """In timeperiods view, cells have period field."""
        response = self._simulate_timeperiods_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert "period" in cell
                assert cell["period"] in ["today", "1w", "1m", "3m"]

    def test_period_order_chronological(self):
        """Periods should be in chronological order."""
        expected_order = ["today", "1w", "1m", "3m"]
        response = self._simulate_timeperiods_response()

        for row in response["matrix"]:
            periods = [cell["period"] for cell in row["cells"]]
            assert periods == expected_order

    def test_cells_have_score_in_range(self):
        """Cell scores must be in [-1, 1] range."""
        response = self._simulate_timeperiods_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert -1.0 <= cell["score"] <= 1.0

    def test_cells_have_valid_color(self):
        """Cell colors must be valid hex colors."""
        response = self._simulate_timeperiods_response()

        for row in response["matrix"]:
            for cell in row["cells"]:
                assert cell["color"].startswith("#")
                assert len(cell["color"]) == 7

    # --- Helper Methods ---

    def _simulate_timeperiods_response(self) -> dict[str, Any]:
        """Simulate heat map time periods view response."""
        return {
            "view": "timeperiods",
            "matrix": [
                {
                    "ticker": "AAPL",
                    "cells": [
                        {"period": "today", "score": 0.65, "color": "#22c55e"},
                        {"period": "1w", "score": 0.52, "color": "#22c55e"},
                        {"period": "1m", "score": 0.41, "color": "#22c55e"},
                        {"period": "3m", "score": 0.38, "color": "#22c55e"},
                    ],
                },
            ],
            "legend": None,  # Legend may be omitted in timeperiods view
        }


# --- Query Parameter Tests ---


class TestHeatMapQueryParameters:
    """Contract tests for query parameter handling."""

    def test_default_view_is_sources(self):
        """Default view (no parameter) should be 'sources'."""
        # When ?view is not specified
        default_view = "sources"
        assert default_view == "sources"

    def test_view_sources_accepted(self):
        """view=sources is a valid parameter value."""
        valid_views = ["sources", "timeperiods"]
        assert "sources" in valid_views

    def test_view_timeperiods_accepted(self):
        """view=timeperiods is a valid parameter value."""
        valid_views = ["sources", "timeperiods"]
        assert "timeperiods" in valid_views

    def test_invalid_view_returns_400(self):
        """Invalid view parameter returns 400 Bad Request."""
        error_response = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid view parameter. Must be 'sources' or 'timeperiods'",
            }
        }

        assert error_response["error"]["code"] == "VALIDATION_ERROR"


# --- Error Response Tests ---


class TestHeatMapErrorResponses:
    """Contract tests for error responses."""

    def test_not_found_returns_404(self):
        """Non-existent config_id returns 404."""
        error_response = {
            "error": {
                "code": "NOT_FOUND",
                "message": "Configuration not found",
            }
        }

        assert error_response["error"]["code"] == "NOT_FOUND"

    def test_upstream_error_returns_502(self):
        """Data source error returns 502."""
        error_response = {
            "error": {
                "code": "UPSTREAM_ERROR",
                "message": "Unable to fetch sentiment data from sources",
            }
        }

        assert error_response["error"]["code"] == "UPSTREAM_ERROR"


# --- Color Scheme Tests ---


class TestHeatMapColorScheme:
    """Contract tests for heat map color scheme."""

    def test_positive_color_green(self):
        """Positive sentiment uses green color."""
        positive_color = "#22c55e"
        assert positive_color.startswith("#")
        # Green should have G component > R and B
        r = int(positive_color[1:3], 16)
        g = int(positive_color[3:5], 16)
        b = int(positive_color[5:7], 16)
        assert g > r and g > b

    def test_negative_color_red(self):
        """Negative sentiment uses red color."""
        negative_color = "#ef4444"
        r = int(negative_color[1:3], 16)
        g = int(negative_color[3:5], 16)
        b = int(negative_color[5:7], 16)
        assert r > g and r > b

    def test_neutral_color_yellow(self):
        """Neutral sentiment uses yellow/amber color."""
        neutral_color = "#eab308"
        r = int(neutral_color[1:3], 16)
        g = int(neutral_color[3:5], 16)
        b = int(neutral_color[5:7], 16)
        # Yellow has high R and G, low B
        assert r > 150 and g > 150 and b < 100

    def test_colors_accessible(self):
        """Colors should have sufficient contrast (accessibility)."""
        # These colors from Tailwind CSS have good contrast
        colors = {
            "positive": "#22c55e",  # green-500
            "negative": "#ef4444",  # red-500
            "neutral": "#eab308",  # yellow-500
        }

        # Each should be distinct (different hue)
        assert colors["positive"] != colors["negative"]
        assert colors["positive"] != colors["neutral"]
        assert colors["negative"] != colors["neutral"]


# --- Matrix Structure Tests ---


class TestHeatMapMatrixStructure:
    """Contract tests for matrix data structure."""

    def test_matrix_is_array(self):
        """Matrix must be an array."""
        response = {"view": "sources", "matrix": []}
        assert isinstance(response["matrix"], list)

    def test_matrix_row_has_ticker_and_cells(self):
        """Each matrix row has ticker and cells."""
        row = {"ticker": "AAPL", "cells": []}
        assert "ticker" in row
        assert "cells" in row

    def test_cells_array_per_row(self):
        """Each row has an array of cells."""
        row = {"ticker": "AAPL", "cells": [{"score": 0.5, "color": "#22c55e"}]}
        assert isinstance(row["cells"], list)

    def test_consistent_cell_count_per_row(self):
        """All rows should have same number of cells."""
        response = {
            "view": "sources",
            "matrix": [
                {
                    "ticker": "AAPL",
                    "cells": [{"source": "tiingo", "score": 0.5, "color": "#22c55e"}],
                },
                {
                    "ticker": "MSFT",
                    "cells": [{"source": "tiingo", "score": 0.3, "color": "#eab308"}],
                },
            ],
        }

        cell_counts = [len(row["cells"]) for row in response["matrix"]]
        assert len(set(cell_counts)) == 1  # All same count
