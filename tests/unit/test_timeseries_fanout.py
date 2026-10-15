"""
Tests for the accumulating time-series fanout writer.

Contract under test (research D1/D8, data-model.md):
- accumulate_fanout reads the bucket, computes the complete next state
  locally, and writes it with a single conditional PutItem per resolution.
- Guard has two branches: `version = :expected` when the read returned a
  version, `attribute_not_exists(version)` when it did not (covers absent
  buckets and legacy pre-cutover buckets alike).
- On ConditionalCheckFailedException: bounded, jittered retry after re-read.
- Statistics: count/sum/avg over signed contributions; open/close ordered by
  article timestamp via open_ts/close_ts; high/low extremes; label_counts
  merged; sources a bounded provider-name string set; is_partial always True.
"""

import random
from datetime import datetime
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.lib.timeseries import Resolution, SentimentScore
from src.lib.timeseries.fanout import accumulate_fanout

TABLE = "test-sentiment-timeseries"


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def make_score(
    value: float,
    label: str,
    ts: str = "2025-12-21T10:35:47Z",
    ticker: str = "AAPL",
    source: str = "tiingo",
) -> SentimentScore:
    return SentimentScore(
        ticker=ticker, value=value, label=label, timestamp=parse_iso(ts), source=source
    )


@pytest.fixture
def dynamodb_client():
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


def get_bucket(client, ticker: str, resolution: str, sk: str) -> dict:
    resp = client.get_item(
        TableName=TABLE,
        Key={"PK": {"S": f"{ticker}#{resolution}"}, "SK": {"S": sk}},
        ConsistentRead=True,
    )
    return resp.get("Item")


class TestAccumulateCreates:
    def test_first_write_creates_six_versioned_buckets(self, dynamodb_client):
        accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        for resolution in Resolution:
            resp = dynamodb_client.query(
                TableName=TABLE,
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": {"S": f"AAPL#{resolution.value}"}},
            )
            assert resp["Count"] == 1, resolution
            item = resp["Items"][0]
            assert item["version"]["N"] == "1"
            assert item["count"]["N"] == "1"
            assert float(item["sum"]["N"]) == 0.8
            assert float(item["avg"]["N"]) == 0.8
            assert item["is_partial"]["BOOL"] is True

    def test_first_write_records_ohlc_and_timestamps(self, dynamodb_client):
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(-0.9, "negative", "2025-12-21T10:35:47Z")
        )

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        for field in ("open", "high", "low", "close"):
            assert float(item[field]["N"]) == -0.9
        assert item["open_ts"]["S"] == "2025-12-21T10:35:47+00:00"
        assert item["close_ts"]["S"] == "2025-12-21T10:35:47+00:00"

    def test_sources_written_as_provider_string_set(self, dynamodb_client):
        accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert item["sources"] == {"SS": ["tiingo"]}


class TestAccumulateStatistics:
    def test_spec_us2_example(self, dynamodb_client):
        """Three articles: positive 0.8, negative 0.9, positive 0.6 into one window."""
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.8, "positive", "2025-12-21T10:01:00Z")
        )
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(-0.9, "negative", "2025-12-21T10:02:00Z")
        )
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.6, "positive", "2025-12-21T10:03:00Z")
        )

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert item["count"]["N"] == "3"
        assert float(item["sum"]["N"]) == pytest.approx(0.5)
        assert float(item["avg"]["N"]) == pytest.approx(0.5 / 3)
        assert float(item["high"]["N"]) == 0.8
        assert float(item["low"]["N"]) == -0.9
        assert item["label_counts"]["M"]["positive"]["N"] == "2"
        assert item["label_counts"]["M"]["negative"]["N"] == "1"
        assert item["version"]["N"] == "3"

    def test_open_close_ordered_by_article_timestamp(self, dynamodb_client):
        """Out-of-order arrival: the later-arriving but earlier-timestamped
        article becomes open, not close."""
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.7, "positive", "2025-12-21T12:00:00Z")
        )
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(-0.6, "negative", "2025-12-21T09:00:00Z")
        )

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert float(item["open"]["N"]) == -0.6
        assert item["open_ts"]["S"] == "2025-12-21T09:00:00+00:00"
        assert float(item["close"]["N"]) == 0.7
        assert item["close_ts"]["S"] == "2025-12-21T12:00:00+00:00"

    def test_is_partial_stays_true_across_writes(self, dynamodb_client):
        accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))
        accumulate_fanout(dynamodb_client, TABLE, make_score(0.6, "positive"))

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert item["is_partial"]["BOOL"] is True

    def test_sources_deduplicate_across_providers(self, dynamodb_client):
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.8, "positive", source="tiingo")
        )
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.6, "positive", source="finnhub")
        )
        accumulate_fanout(
            dynamodb_client, TABLE, make_score(0.7, "positive", source="finnhub")
        )

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert sorted(item["sources"]["SS"]) == ["finnhub", "tiingo"]


class TestConditionGuard:
    def _capture_puts(self, client):
        calls = []
        original = client.put_item

        def recording_put(**kwargs):
            calls.append(kwargs)
            return original(**kwargs)

        return calls, recording_put

    def test_absent_bucket_uses_attribute_not_exists(self, dynamodb_client):
        calls, recorder = self._capture_puts(dynamodb_client)
        with patch.object(dynamodb_client, "put_item", recorder):
            accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        assert len(calls) == 6
        for call in calls:
            assert call["ConditionExpression"] == "attribute_not_exists(version)"

    def test_versioned_bucket_guards_on_expected_version(self, dynamodb_client):
        accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        calls, recorder = self._capture_puts(dynamodb_client)
        with patch.object(dynamodb_client, "put_item", recorder):
            accumulate_fanout(dynamodb_client, TABLE, make_score(0.6, "positive"))

        assert len(calls) == 6
        for call in calls:
            assert call["ConditionExpression"] == "version = :expected"
            assert call["ExpressionAttributeValues"][":expected"] == {"N": "1"}
            assert call["Item"]["version"]["N"] == "2"

    def test_legacy_unversioned_bucket_adopted(self, dynamodb_client):
        """A pre-cutover bucket (no version attribute) is written through the
        attribute_not_exists(version) branch and comes out versioned."""
        dynamodb_client.put_item(
            TableName=TABLE,
            Item={
                "PK": {"S": "AAPL#24h"},
                "SK": {"S": "2025-12-21T00:00:00+00:00"},
                "open": {"N": "0.95"},
                "high": {"N": "0.95"},
                "low": {"N": "0.95"},
                "close": {"N": "0.95"},
                "count": {"N": "1"},
                "sum": {"N": "0.95"},
                "avg": {"N": "0.95"},
                "is_partial": {"BOOL": True},
                "sources": {"L": [{"S": "dedup:abc"}]},
                "label_counts": {"M": {"positive": {"N": "1"}}},
                "original_timestamp": {"S": "2025-12-21T08:00:00+00:00"},
                "ttl": {"N": "1766448000"},
            },
        )

        calls, recorder = self._capture_puts(dynamodb_client)
        with patch.object(dynamodb_client, "put_item", recorder):
            accumulate_fanout(
                dynamodb_client,
                TABLE,
                make_score(-0.9, "negative", "2025-12-21T10:00:00Z"),
            )

        adopt = [c for c in calls if c["Item"]["PK"]["S"] == "AAPL#24h"]
        assert adopt[0]["ConditionExpression"] == "attribute_not_exists(version)"

        item = get_bucket(dynamodb_client, "AAPL", "24h", "2025-12-21T00:00:00+00:00")
        assert item["version"]["N"] == "1"
        assert item["count"]["N"] == "2"
        assert float(item["low"]["N"]) == -0.9
        # Legacy dedup: list is dropped; sources restart as a provider set.
        assert item["sources"] == {"SS": ["tiingo"]}

    def test_conditional_failure_retries_and_succeeds(self, dynamodb_client):
        """Loser of a version race re-reads and retries."""
        failures = {"n": 0}
        original = dynamodb_client.put_item

        def flaky_put(**kwargs):
            if failures["n"] < 3:
                failures["n"] += 1
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException"}},
                    "PutItem",
                )
            return original(**kwargs)

        with (
            patch.object(dynamodb_client, "put_item", flaky_put),
            patch("src.lib.timeseries.fanout.time.sleep") as mock_sleep,
        ):
            accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        assert failures["n"] == 3
        assert mock_sleep.call_count == 3
        # Jitter: every backoff is positive and none are identical zero-jitter
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert all(d > 0 for d in delays)

    def test_retries_are_bounded(self, dynamodb_client):
        def always_fail(**kwargs):
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
            )

        from src.lib.timeseries.fanout import FanoutWriteError

        with (
            patch.object(dynamodb_client, "put_item", always_fail),
            patch("src.lib.timeseries.fanout.time.sleep"),
        ):
            with pytest.raises(FanoutWriteError) as excinfo:
                accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))
        assert excinfo.value.error_class == "ConditionalCheckFailedException"

    def test_jitter_randomized(self, dynamodb_client):
        """Backoff consults the RNG so concurrent losers do not retry in
        lockstep."""
        failures = {"n": 0}
        original = dynamodb_client.put_item

        def flaky_put(**kwargs):
            if failures["n"] < 1:
                failures["n"] += 1
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException"}},
                    "PutItem",
                )
            return original(**kwargs)

        with (
            patch.object(dynamodb_client, "put_item", flaky_put),
            patch("src.lib.timeseries.fanout.time.sleep"),
            patch(
                "src.lib.timeseries.fanout.random.uniform",
                wraps=random.uniform,
            ) as mock_uniform,
        ):
            accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))

        assert mock_uniform.called

    def test_non_conditional_error_raises_immediately(self, dynamodb_client):
        def broken_put(**kwargs):
            raise ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException"}},
                "PutItem",
            )

        from src.lib.timeseries.fanout import FanoutWriteError

        with (
            patch.object(dynamodb_client, "put_item", broken_put),
            patch("src.lib.timeseries.fanout.time.sleep") as mock_sleep,
        ):
            with pytest.raises(FanoutWriteError) as excinfo:
                accumulate_fanout(dynamodb_client, TABLE, make_score(0.8, "positive"))
        assert mock_sleep.call_count == 0
        assert excinfo.value.error_class == "ProvisionedThroughputExceededException"


class TestValidation:
    def test_ticker_required(self, dynamodb_client):
        score = SentimentScore(
            value=0.8, label="positive", timestamp=parse_iso("2025-12-21T10:35:47Z")
        )
        with pytest.raises(ValueError):
            accumulate_fanout(dynamodb_client, TABLE, score)


class TestLabelToSigned:
    """Signed mapping contract (research D2): one source of truth for handler,
    backfill, and the test oracle."""

    def test_positive_maps_to_plus_confidence(self):
        from src.lib.timeseries.signed import label_to_signed

        assert label_to_signed("positive", 0.92) == 0.92

    def test_negative_maps_to_minus_confidence(self):
        from src.lib.timeseries.signed import label_to_signed

        assert label_to_signed("negative", 0.78) == -0.78

    def test_neutral_maps_to_zero(self):
        from src.lib.timeseries.signed import label_to_signed

        assert label_to_signed("neutral", 0.55) == 0.0

    def test_unknown_label_maps_to_zero(self):
        from src.lib.timeseries.signed import label_to_signed

        assert label_to_signed("mixed", 0.9) == 0.0

    @pytest.mark.parametrize(
        ("label", "confidence"),
        [("positive", 1.0), ("negative", 1.0), ("positive", 0.0), ("neutral", 1.0)],
    )
    def test_output_bounded(self, label, confidence):
        from src.lib.timeseries.signed import label_to_signed

        assert -1.0 <= label_to_signed(label, confidence) <= 1.0
