"""Integration tests for accumulate_fanout concurrency and adoption semantics.

Covers the D1 optimistic-concurrency contract against real DynamoDB behavior
(LocalStack): version-race losers retry and converge, a crash mid-fanout
leaves only complete bucket states, and live accumulation onto a
legacy-unversioned (pre-cutover) bucket adopts it through the
attribute_not_exists(version) branch.

Fixed dates only, per Constitution section 3.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from src.lib.timeseries.fanout import FanoutWriteError, accumulate_fanout
from src.lib.timeseries.models import SentimentScore

FIXED_TS_A = datetime(2024, 1, 2, 10, 35, 10, tzinfo=UTC)
FIXED_TS_B = datetime(2024, 1, 2, 10, 35, 20, tzinfo=UTC)
DAY_SK = "2024-01-02T00:00:00+00:00"


def make_score(ticker: str, value: float, label: str, ts: datetime) -> SentimentScore:
    return SentimentScore(
        ticker=ticker, value=value, label=label, timestamp=ts, source="tiingo"
    )


def get_bucket(client: Any, table: str, pk: str, sk: str) -> dict | None:
    return client.get_item(
        TableName=table, Key={"PK": {"S": pk}, "SK": {"S": sk}}, ConsistentRead=True
    ).get("Item")


def assert_bucket_internally_consistent(item: dict) -> None:
    """Every observable bucket is a complete state at a single version."""
    count = int(item["count"]["N"])
    total = float(item["sum"]["N"])
    assert float(item["avg"]["N"]) == pytest.approx(total / count)
    assert (
        float(item["low"]["N"]) <= float(item["avg"]["N"]) <= float(item["high"]["N"])
    )
    label_total = sum(int(v["N"]) for v in item["label_counts"]["M"].values())
    assert label_total == count
    assert int(item["version"]["N"]) >= 1
    assert item["open_ts"]["S"] <= item["close_ts"]["S"]


class _InterleavingClient:
    """Proxy client that lets a competing writer finish a full accumulation
    between this writer's read and its first conditional put, forcing the
    version race deterministically."""

    def __init__(self, real_client: Any, table: str, competing: SentimentScore):
        self._real = real_client
        self._table = table
        self._competing = competing
        self._fired = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def put_item(self, **kwargs: Any) -> Any:
        if not self._fired:
            self._fired = True
            accumulate_fanout(self._real, self._table, self._competing)
        return self._real.put_item(**kwargs)


class TestConcurrentWriters:
    def test_race_loser_retries_and_converges(self, dynamodb_client, timeseries_table):
        """Two writers on one bucket: the interleaved loser retries, final
        count is 2 and every statistic is consistent."""
        winner = make_score("RACE", 0.8, "positive", FIXED_TS_A)
        loser = make_score("RACE", -0.9, "negative", FIXED_TS_B)

        proxy = _InterleavingClient(dynamodb_client, timeseries_table, winner)
        accumulate_fanout(proxy, timeseries_table, loser)

        item = get_bucket(dynamodb_client, timeseries_table, "RACE#24h", DAY_SK)
        assert item is not None
        assert int(item["count"]["N"]) == 2
        assert float(item["sum"]["N"]) == pytest.approx(-0.1)
        assert float(item["high"]["N"]) == 0.8
        assert float(item["low"]["N"]) == -0.9
        assert int(item["version"]["N"]) == 2
        assert_bucket_internally_consistent(item)


class _CrashingClient:
    """Proxy client whose put_item dies after N successful writes, simulating
    a crash partway through the six-resolution fanout."""

    def __init__(self, real_client: Any, survive_puts: int):
        self._real = real_client
        self._remaining = survive_puts

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)

    def put_item(self, **kwargs: Any) -> Any:
        if self._remaining <= 0:
            raise RuntimeError("simulated crash")
        self._remaining -= 1
        return self._real.put_item(**kwargs)


class TestCrashConsistency:
    def test_crash_mid_fanout_leaves_only_complete_states(
        self, dynamodb_client, timeseries_table
    ):
        """A crash between resolutions loses whole buckets, never partial
        statistics: every bucket that exists is complete and consistent."""
        score = make_score("CRSH", 0.7, "positive", FIXED_TS_A)

        proxy = _CrashingClient(dynamodb_client, survive_puts=3)
        with pytest.raises(RuntimeError):
            accumulate_fanout(proxy, timeseries_table, score)

        response = dynamodb_client.scan(TableName=timeseries_table)
        items = [
            i for i in response.get("Items", []) if i["PK"]["S"].startswith("CRSH#")
        ]
        assert 0 < len(items) < 6
        for item in items:
            assert int(item["count"]["N"]) == 1
            assert_bucket_internally_consistent(item)

    def test_crash_during_conditional_put_is_loud(
        self, dynamodb_client, timeseries_table
    ):
        """A non-conditional DynamoDB error surfaces as FanoutWriteError with
        repair coordinates rather than disappearing."""

        class BrokenClient(_CrashingClient):
            def put_item(self, **kwargs: Any) -> Any:
                from botocore.exceptions import ClientError

                raise ClientError({"Error": {"Code": "InternalServerError"}}, "PutItem")

        proxy = BrokenClient(dynamodb_client, survive_puts=0)
        with pytest.raises(FanoutWriteError) as excinfo:
            accumulate_fanout(
                proxy, timeseries_table, make_score("LOUD", 0.5, "positive", FIXED_TS_A)
            )
        assert excinfo.value.ticker == "LOUD"
        assert excinfo.value.error_class == "InternalServerError"


class TestLegacyAdoption:
    def test_live_accumulation_adopts_unversioned_bucket(
        self, dynamodb_client, timeseries_table
    ):
        """A pre-cutover bucket without a version attribute is adopted via
        attribute_not_exists(version) and accumulates normally afterwards."""
        dynamodb_client.put_item(
            TableName=timeseries_table,
            Item={
                "PK": {"S": "LGCY#24h"},
                "SK": {"S": DAY_SK},
                "open": {"N": "0.95"},
                "high": {"N": "0.95"},
                "low": {"N": "0.95"},
                "close": {"N": "0.95"},
                "count": {"N": "1"},
                "sum": {"N": "0.95"},
                "avg": {"N": "0.95"},
                "is_partial": {"BOOL": True},
                "sources": {"L": [{"S": "dedup:abc123"}]},
                "label_counts": {"M": {"positive": {"N": "1"}}},
                "original_timestamp": {"S": "2024-01-02T08:00:00+00:00"},
                "ttl": {"N": "1712059200"},
            },
        )

        accumulate_fanout(
            dynamodb_client,
            timeseries_table,
            make_score("LGCY", -0.9, "negative", FIXED_TS_A),
        )

        item = get_bucket(dynamodb_client, timeseries_table, "LGCY#24h", DAY_SK)
        assert item is not None
        assert int(item["version"]["N"]) == 1
        assert int(item["count"]["N"]) == 2
        assert float(item["low"]["N"]) == -0.9
        # Legacy dedup: list is dropped; sources restart as a provider set
        assert item["sources"] == {"SS": ["tiingo"]}
        # Subsequent write takes the versioned branch
        accumulate_fanout(
            dynamodb_client,
            timeseries_table,
            make_score("LGCY", 0.6, "positive", FIXED_TS_B),
        )
        item = get_bucket(dynamodb_client, timeseries_table, "LGCY#24h", DAY_SK)
        assert int(item["version"]["N"]) == 2
        assert int(item["count"]["N"]) == 3
