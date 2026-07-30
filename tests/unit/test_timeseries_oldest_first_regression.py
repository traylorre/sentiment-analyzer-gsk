"""Regression tests for the oldest-first truncation defect.

Found 2026-07-30 by probing preprod: GET /api/v2/tickers/{t}/sentiment/history
returned at most 7 points taken from the OLDEST end of the requested range, so a
"3 months" request answered with the first week of May while the price chart beside
it showed the current day.

Two independent causes, both in TimeseriesQueryService.query:

1. When a caller supplied an explicit start/end range but no limit, the small
   per-resolution DEFAULT_LIMITS fallback (7 for 24h) was applied to that range,
   silently truncating it.
2. The scan is ascending, so that truncation kept the OLDEST rows. A caller reading
   buckets[-1] to get "the current value" therefore got the 7th-oldest bucket ever
   recorded -- a number that never changes as new data arrives.

Cause 2 was the more severe of the two: it drove get_sentiment_by_configuration,
which is the customer dashboard's headline sentiment number.

These tests fail against the pre-fix implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.lib.timeseries import Resolution


def _item(sk: str, close: str = "0.75") -> dict[str, Any]:
    """Build a minimal DynamoDB item for a daily sentiment bucket."""
    return {
        "PK": "AAPL#24h",
        "SK": sk,
        "open": Decimal("0.65"),
        "high": Decimal("0.85"),
        "low": Decimal("0.55"),
        "close": Decimal(close),
        "sum": Decimal("7.5"),
        "count": 10,
        "label_counts": {"positive": 6, "negative": 2, "neutral": 2},
        "is_partial": False,
    }


@pytest.fixture
def table() -> MagicMock:
    t = MagicMock()
    t.query.return_value = {"Items": []}
    return t


def _service(table: MagicMock, **kwargs: Any):
    from src.lambdas.dashboard.timeseries import TimeseriesQueryService

    with patch("boto3.resource") as mock_boto:
        mock_boto.return_value.Table.return_value = table
        return TimeseriesQueryService("test-table", **kwargs)


class TestRangeDerivedLimit:
    """Cause 1: an explicit range must not be truncated by the fallback limit."""

    def test_range_query_derives_limit_from_range_not_fallback(
        self, table: MagicMock
    ) -> None:
        """A 90-day daily range must not be capped at the 7-bucket fallback."""
        svc = _service(table, use_cache=False)
        end = datetime(2026, 7, 30, tzinfo=UTC)
        start = end - timedelta(days=90)

        svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS, start=start, end=end)

        sent_limit = table.query.call_args.kwargs["Limit"]
        assert sent_limit >= 90, (
            f"90-day range asked DynamoDB for only {sent_limit} buckets. "
            "This is the defect: the range is silently truncated."
        )
        assert sent_limit != 7, "fallback limit was applied to an explicit range"

    def test_derived_limit_is_capped(self, table: MagicMock) -> None:
        """A pathological range must not ask DynamoDB for an unbounded page."""
        from src.lambdas.dashboard.timeseries import TimeseriesQueryService

        svc = _service(table, use_cache=False)
        end = datetime(2026, 7, 30, tzinfo=UTC)
        start = end - timedelta(days=365 * 20)  # 20 years of 1-minute buckets

        svc.query("AAPL", Resolution.ONE_MINUTE, start=start, end=end)

        assert (
            table.query.call_args.kwargs["Limit"]
            == TimeseriesQueryService.MAX_DERIVED_LIMIT
        )

    def test_explicit_limit_still_wins(self, table: MagicMock) -> None:
        """An explicit limit must override the derived one."""
        svc = _service(table, use_cache=False)
        end = datetime(2026, 7, 30, tzinfo=UTC)
        start = end - timedelta(days=90)

        svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS, start=start, end=end, limit=5)

        assert table.query.call_args.kwargs["Limit"] == 5

    def test_fallback_still_used_without_a_range(self, table: MagicMock) -> None:
        """With no range and no limit, the per-resolution fallback still applies."""
        svc = _service(table, use_cache=False)

        svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS)

        assert table.query.call_args.kwargs["Limit"] == 7


class TestLatestOrdering:
    """Cause 2: 'give me the current value' must not return the oldest rows."""

    def test_latest_scans_backwards(self, table: MagicMock) -> None:
        svc = _service(table, use_cache=False)

        svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS, latest=True)

        assert table.query.call_args.kwargs["ScanIndexForward"] is False

    def test_default_still_scans_forwards(self, table: MagicMock) -> None:
        svc = _service(table, use_cache=False)

        svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS)

        assert table.query.call_args.kwargs["ScanIndexForward"] is True

    def test_latest_restores_ascending_order_so_last_is_newest(
        self, table: MagicMock
    ) -> None:
        """DynamoDB returns newest-first for latest=True; callers read buckets[-1]."""
        # Newest-first, as a backwards scan would return them.
        table.query.return_value = {
            "Items": [
                _item("2026-07-29T00:00:00Z", "0.90"),
                _item("2026-07-28T00:00:00Z", "0.80"),
                _item("2026-07-27T00:00:00Z", "0.70"),
            ]
        }
        svc = _service(table, use_cache=False)

        resp = svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS, latest=True)

        stamps = [b.timestamp for b in resp.buckets]
        assert stamps == sorted(stamps), "buckets must be returned ascending"
        assert resp.buckets[-1].close == pytest.approx(0.90), (
            "buckets[-1] must be the NEWEST bucket -- callers use it as the "
            "current value"
        )

    def test_latest_bypasses_the_resolution_cache(self) -> None:
        """A newest-first slice must not be served from, or written to, the cache.

        Cache entries are stored under oldest-first semantics, so sharing them
        across modes would reintroduce the inversion this fix removes.
        """
        table = MagicMock()
        table.query.return_value = {"Items": [_item("2026-07-29T00:00:00Z")]}
        cache = MagicMock()
        cache.get.return_value = None

        with patch(
            "src.lambdas.dashboard.timeseries.get_global_cache", return_value=cache
        ):
            svc = _service(table, use_cache=True)
            svc.query("AAPL", Resolution.TWENTY_FOUR_HOURS, latest=True)

        cache.get.assert_not_called()
        cache.set.assert_not_called()


class TestCallSites:
    """The fix is only real if the call sites actually opt in."""

    def test_config_sentiment_requests_latest(self) -> None:
        """get_sentiment_by_configuration must ask for the NEWEST bucket.

        It reads buckets[-1] as the current sentiment. Without latest=True that is
        the 7th-oldest bucket ever recorded for the ticker.
        """
        from src.lambdas.dashboard import sentiment as sentiment_mod

        captured: dict[str, Any] = {}

        def fake_query(**kwargs: Any):
            captured.update(kwargs)
            resp = MagicMock()
            resp.buckets = []
            resp.partial_bucket = None
            return resp

        # sentiment.py imports query_timeseries inside the function body, so the
        # name must be patched where it is defined rather than on this module.
        with patch(
            "src.lambdas.dashboard.timeseries.query_timeseries",
            side_effect=fake_query,
        ):
            sentiment_mod.get_sentiment_by_configuration(
                config_id="cfg-1", tickers=["AAPL"], skip_cache=True
            )

        assert captured.get("latest") is True, (
            "get_sentiment_by_configuration must pass latest=True; without it the "
            "dashboard reports the 7th-oldest day as the current sentiment"
        )

    @pytest.mark.parametrize(
        "module_name,func_name",
        [
            ("src.lambdas.dashboard.ohlc", "get_sentiment_history"),
            ("src.lambdas.dashboard.sentiment", "get_ticker_sentiment_history"),
        ],
    )
    def test_history_call_sites_pass_a_range(
        self, module_name: str, func_name: str
    ) -> None:
        """Both history readers must supply start AND end.

        That is what makes the limit range-derived rather than the 7-bucket
        fallback. A future edit dropping either argument silently restores the bug.
        """
        import importlib
        import inspect

        mod = importlib.import_module(module_name)
        src = inspect.getsource(getattr(mod, func_name))
        call = src[src.index("query_timeseries(") :]
        head = call[: call.index(")")]
        assert ("start" in head or "start_dt" in head) and (
            "end" in head or "now" in head
        ), f"{module_name}.{func_name} must pass a start/end range to query_timeseries"
