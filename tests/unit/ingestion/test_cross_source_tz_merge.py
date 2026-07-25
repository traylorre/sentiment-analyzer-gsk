"""Regression test for Feature 1398 — cross-source dedup merge (LB-1).

Proves that the SAME news story ingested from Tiingo (ISO string) and Finnhub
(epoch int) collapses into ONE DynamoDB item after the Finnhub adapter is fixed
to parse its epoch as tz-aware UTC.

NON-VACUOUS BY CONSTRUCTION: ``published_at`` is produced by the REAL adapter
parse code (mocked HTTP payloads only), never by hand-built datetimes handed to
the dedup layer. That is precisely why ``test_cross_source_dedup.py`` passes
while production fails, and why this file fails-before / passes-after the
one-line fix at ``finnhub.py:227``.

Fixture epoch is computed from the aware datetime (self-verifying), not hardcoded.
"""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.ingestion.dedup import generate_dedup_key
from src.lambdas.ingestion.handler import _process_article
from src.lambdas.shared.adapters.finnhub import FinnhubAdapter
from src.lambdas.shared.adapters.finnhub import clear_cache as clear_finnhub_cache
from src.lambdas.shared.adapters.tiingo import TiingoAdapter
from src.lambdas.shared.adapters.tiingo import clear_cache as clear_tiingo_cache

# One UTC instant, one story, two feeds. Different headline casing exercises
# headline normalization too.
INSTANT = datetime(2026, 1, 15, 14, 30, 0, tzinfo=UTC)
EPOCH = int(INSTANT.timestamp())  # self-verifying — no hardcoded literal
TIINGO_HEADLINE = "Apple Reports Q4 Earnings Beat"
FINNHUB_HEADLINE = "Apple reports Q4 earnings beat"


@pytest.fixture(autouse=True)
def _clear_adapter_caches():
    clear_finnhub_cache()
    clear_tiingo_cache()
    yield
    clear_finnhub_cache()
    clear_tiingo_cache()


def _mock_http(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.is_success = True
    resp.json.return_value = payload
    return resp


def _parse_tiingo(published_iso: str = "2026-01-15T14:30:00Z"):
    """Obtain a NewsArticle through the REAL Tiingo parse path."""
    adapter = TiingoAdapter(api_key="test-key")
    payload = [
        {
            "id": 91144751,
            "title": TIINGO_HEADLINE,
            "description": "Apple Inc. beat estimates.",
            "url": "https://tiingo.example/aapl-q4",
            "publishedDate": published_iso,
            "tickers": ["AAPL"],
            "tags": ["earnings"],
            "source": "reuters",
        }
    ]
    with patch.object(adapter.client, "get", return_value=_mock_http(payload)):
        articles = adapter.get_news(["AAPL"])
    assert len(articles) == 1
    return articles[0]


def _parse_finnhub(epoch: int = EPOCH):
    """Obtain a NewsArticle through the REAL Finnhub parse path."""
    adapter = FinnhubAdapter(api_key="test-key")
    payload = [
        {
            "id": 555,
            "headline": FINNHUB_HEADLINE,
            "summary": "Apple Inc. beat estimates.",
            "url": "https://finnhub.example/aapl-q4",
            "datetime": epoch,
            "category": "earnings",
            "source": "reuters",
        }
    ]
    with patch.object(adapter.client, "get", return_value=_mock_http(payload)):
        articles = adapter.get_news(["AAPL"])
    assert len(articles) == 1
    return articles[0]


@pytest.fixture
def items_table():
    """Moto DynamoDB table matching the ingestion item key schema."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-sentiment-items",
            KeySchema=[
                {"AttributeName": "source_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "source_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(
            TableName="test-sentiment-items"
        )
        yield table


class TestCrossSourceTzMerge:
    """FR-004: fails on unmodified code, passes after the finnhub.py:227 fix."""

    def test_1_adapter_sk_strings_are_byte_identical(self):
        """Test 1 — SK smoking gun: both adapters' isoformat() must match.

        Unmodified: Tiingo emits ``...+00:00`` (aware) while Finnhub emits a bare
        string (naive) -> different SK -> different DynamoDB Key -> no merge.
        """
        tiingo = _parse_tiingo()
        finnhub = _parse_finnhub()

        assert tiingo.published_at.isoformat() == finnhub.published_at.isoformat()
        # And the dedup PK date-hash agrees too.
        assert generate_dedup_key(
            tiingo.title, tiingo.published_at
        ) == generate_dedup_key(finnhub.title, finnhub.published_at)

    def test_2_tiingo_then_finnhub_collapses_to_one_row(self, items_table):
        """Test 2 — end-to-end merge, Tiingo first."""
        tiingo = _parse_tiingo()
        finnhub = _parse_finnhub()

        first = _process_article(tiingo, "tiingo", items_table, "v-test")
        second = _process_article(finnhub, "finnhub", items_table, "v-test")

        assert first is not None  # created -> SNS message
        assert second is None  # updated/duplicate -> no SNS message

        items = items_table.scan()["Items"]
        assert len(items) == 1, "cross-source merge failed: two rows written"
        assert sorted(items[0]["sources"]) == ["finnhub", "tiingo"]

    def test_2b_finnhub_then_tiingo_collapses_to_one_row(self, items_table):
        """Test 2 (swapped) — end-to-end merge, Finnhub first."""
        tiingo = _parse_tiingo()
        finnhub = _parse_finnhub()

        first = _process_article(finnhub, "finnhub", items_table, "v-test")
        second = _process_article(tiingo, "tiingo", items_table, "v-test")

        assert first is not None
        assert second is None

        items = items_table.scan()["Items"]
        assert len(items) == 1, "cross-source merge failed: two rows written"
        assert sorted(items[0]["sources"]) == ["finnhub", "tiingo"]

    def test_3_utc_midnight_is_host_tz_invariant(self, monkeypatch):
        """Test 3 — midnight/PK edge under a non-UTC host tz.

        A story at exactly ``00:00:00Z`` parsed naively on a host west of UTC
        lands on the PREVIOUS calendar date, diverging even the dedup PK hash.
        The fix (epoch -> UTC-aware) removes host-tz sensitivity entirely.
        """
        midnight = datetime(2026, 1, 15, 0, 0, 0, tzinfo=UTC)
        midnight_epoch = int(midnight.timestamp())

        monkeypatch.setenv("TZ", "America/Los_Angeles")
        time.tzset()
        try:
            tiingo = _parse_tiingo("2026-01-15T00:00:00Z")
            finnhub = _parse_finnhub(midnight_epoch)

            assert tiingo.published_at.isoformat() == finnhub.published_at.isoformat()
            assert generate_dedup_key(
                tiingo.title, tiingo.published_at
            ) == generate_dedup_key(finnhub.title, finnhub.published_at)
        finally:
            monkeypatch.delenv("TZ", raising=False)
            time.tzset()
