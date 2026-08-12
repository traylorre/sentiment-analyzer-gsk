"""Unit tests for scripts/backfill_timeseries.py (moto).

Contract: recompute from sentiment-items through the shared label_to_signed
oracle, versioned conditional writes per research D1, TTL-scoped horizon
(FR-004/FR-005), manifest per contracts/backfill-manifest.md, re-runs
bucket-identical (SC-004). Fixed dates/freezegun throughout: TTL comparisons
are time-relative.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import boto3
import pytest
from freezegun import freeze_time
from moto import mock_aws

import scripts.backfill_timeseries as backfill
from src.lib.timeseries.fanout import accumulate_fanout
from src.lib.timeseries.models import SentimentScore

FROZEN_NOW = "2026-01-15T12:00:00Z"
NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
ENV = "test"
ITEMS_TABLE = f"{ENV}-sentiment-items"
TS_TABLE = f"{ENV}-sentiment-timeseries"


def make_item(
    source_id: str,
    ts: str,
    sentiment: str,
    score: float,
    tickers: list[str],
    sources: list[str] | None = None,
    status: str = "analyzed",
) -> dict:
    return {
        "source_id": source_id,
        "timestamp": ts,
        "status": status,
        "sentiment": sentiment,
        "score": Decimal(str(score)),
        "matched_tickers": tickers,
        "sources": sources or ["tiingo"],
    }


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    with mock_aws():
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        for table, keys in (
            (ITEMS_TABLE, [("source_id", "HASH"), ("timestamp", "RANGE")]),
            (TS_TABLE, [("PK", "HASH"), ("SK", "RANGE")]),
        ):
            dynamodb.create_table(
                TableName=table,
                KeySchema=[{"AttributeName": n, "KeyType": t} for n, t in keys],
                AttributeDefinitions=[
                    {"AttributeName": n, "AttributeType": "S"} for n, _ in keys
                ],
                BillingMode="PAY_PER_REQUEST",
            )
        yield dynamodb


def put_items(items: list[dict]) -> None:
    resource = boto3.resource("dynamodb", region_name="us-east-1")
    table = resource.Table(ITEMS_TABLE)
    for item in items:
        table.put_item(Item=item)


def run_backfill(argv_extra: list[str] | None = None) -> dict:
    argv = ["--env", ENV, *(argv_extra or [])]
    with patch.object(backfill.time, "sleep"):
        return backfill.run(backfill.parse_args(argv), boto3.Session())


def scan_ts(dynamodb) -> dict:
    items = dynamodb.scan(TableName=TS_TABLE).get("Items", [])
    return {(i["PK"]["S"], i["SK"]["S"]): i for i in items}


STAT_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "count",
    "sum",
    "avg",
    "label_counts",
    "sources",
    "open_ts",
    "close_ts",
)


class TestRecomputeOracle:
    @freeze_time(FROZEN_NOW)
    def test_recompute_matches_live_accumulation(self, aws):
        """Backfilled buckets equal accumulating the same items through
        label_to_signed (shared oracle)."""
        items = [
            make_item("a#1", "2026-01-14T10:01:00+00:00", "positive", 0.8, ["NVDA"]),
            make_item("a#2", "2026-01-14T10:02:00+00:00", "negative", 0.9, ["NVDA"]),
            make_item("a#3", "2026-01-14T10:03:00+00:00", "positive", 0.6, ["NVDA"]),
        ]
        put_items(items)

        run_backfill()
        backfilled = scan_ts(aws)

        # Oracle: drain the table and accumulate the same items live
        for key in backfilled:
            aws.delete_item(
                TableName=TS_TABLE, Key={"PK": {"S": key[0]}, "SK": {"S": key[1]}}
            )
        for item in items:
            score = SentimentScore(
                ticker="NVDA",
                value=backfill.label_to_signed(item["sentiment"], float(item["score"])),
                timestamp=datetime.fromisoformat(item["timestamp"]),
                label=item["sentiment"],
                source="tiingo",
            )
            accumulate_fanout(aws, TS_TABLE, score)
        live = scan_ts(aws)

        # The backfill skips TTL-dead windows (1m/5m/15m here); live
        # accumulation writes all six. Equality holds on the TTL-live set.
        assert set(backfilled) == {
            ("NVDA#30m", "2026-01-14T10:00:00+00:00"),
            ("NVDA#1h", "2026-01-14T10:00:00+00:00"),
            ("NVDA#24h", "2026-01-14T00:00:00+00:00"),
        }
        assert set(backfilled) <= set(live)
        numeric = ("open", "high", "low", "close", "sum", "avg")
        for key, bucket in backfilled.items():
            for field in numeric:
                # One-shot recompute and stepwise accumulation may differ by
                # float rounding order; equality is up to float tolerance.
                assert float(bucket[field]["N"]) == pytest.approx(
                    float(live[key][field]["N"])
                ), (key, field)
            for field in ("count", "label_counts", "sources", "open_ts", "close_ts"):
                assert bucket.get(field) == live[key].get(field), (key, field)

    @freeze_time(FROZEN_NOW)
    def test_rerun_is_bucket_identical(self, aws):
        """SC-004: a second quiesced run over an unchanged item set changes
        zero bucket values."""
        put_items(
            [
                make_item(
                    "a#1", "2026-01-14T10:01:00+00:00", "positive", 0.8, ["NVDA"]
                ),
                make_item(
                    "a#2", "2026-01-13T09:00:00+00:00", "negative", 0.7, ["AAPL"]
                ),
            ]
        )

        manifest_one = run_backfill()
        first = scan_ts(aws)
        manifest_two = run_backfill()
        second = scan_ts(aws)

        assert set(first) == set(second)
        for key in first:
            for field in STAT_FIELDS:
                assert first[key].get(field) == second[key].get(field)
        for resolution, stats in manifest_one["per_resolution"].items():
            two = manifest_two["per_resolution"][resolution]
            assert stats["buckets_written"] == two["buckets_written"]
            assert stats["buckets_skipped_ttl"] == two["buckets_skipped_ttl"]


class TestHorizonAndTtl:
    @freeze_time(FROZEN_NOW)
    def test_ttl_passed_windows_skipped_and_counted(self, aws):
        """A 20-day-old article's 1h windows are TTL-dead (7d) and skipped;
        its 24h window (90d TTL) is written."""
        put_items(
            [make_item("a#1", "2025-12-26T10:00:00+00:00", "positive", 0.8, ["NVDA"])]
        )

        manifest = run_backfill()
        buckets = scan_ts(aws)

        assert ("NVDA#24h", "2025-12-26T00:00:00+00:00") in buckets
        assert not any(pk == "NVDA#1h" for pk, _ in buckets)
        assert manifest["per_resolution"]["1h"]["buckets_skipped_ttl"] == 1
        assert manifest["per_resolution"]["1h"]["buckets_written"] == 0
        assert manifest["per_resolution"]["24h"]["buckets_written"] == 1

    @freeze_time(FROZEN_NOW)
    def test_buckets_outside_horizon_untouched(self, aws):
        """FR-005: a pre-existing bucket older than the 30-day horizon is not
        rewritten."""
        aws.put_item(
            TableName=TS_TABLE,
            Item={
                "PK": {"S": "NVDA#24h"},
                "SK": {"S": "2025-11-01T00:00:00+00:00"},
                "open": {"N": "0.9"},
                "high": {"N": "0.9"},
                "low": {"N": "0.9"},
                "close": {"N": "0.9"},
                "count": {"N": "1"},
                "sum": {"N": "0.9"},
                "avg": {"N": "0.9"},
                "is_partial": {"BOOL": True},
                "ttl": {"N": "9999999999"},
            },
        )
        put_items(
            [make_item("a#1", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"])]
        )

        run_backfill()

        old = aws.get_item(
            TableName=TS_TABLE,
            Key={
                "PK": {"S": "NVDA#24h"},
                "SK": {"S": "2025-11-01T00:00:00+00:00"},
            },
        )["Item"]
        assert old["count"]["N"] == "1"
        assert "version" not in old

    @freeze_time(FROZEN_NOW)
    def test_rejected_timestamps_counted(self, aws):
        """FR-010 rejects (future-dated stored items) are counted, not
        backfilled."""
        put_items(
            [
                make_item(
                    "a#1", "2026-01-16T13:00:00+00:00", "positive", 0.8, ["NVDA"]
                ),
                make_item(
                    "a#2", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"]
                ),
            ]
        )

        manifest = run_backfill()

        assert manifest["rejected_timestamps"] == 1
        assert manifest["items_read"] == 2


class TestConditionalWrites:
    @freeze_time(FROZEN_NOW)
    def test_legacy_unversioned_bucket_rewritten(self, aws):
        """A pre-cutover bucket in the horizon is rewritten through the
        attribute_not_exists(version) branch."""
        aws.put_item(
            TableName=TS_TABLE,
            Item={
                "PK": {"S": "NVDA#24h"},
                "SK": {"S": "2026-01-14T00:00:00+00:00"},
                "open": {"N": "0.95"},
                "high": {"N": "0.95"},
                "low": {"N": "0.95"},
                "close": {"N": "0.95"},
                "count": {"N": "1"},
                "sum": {"N": "0.95"},
                "avg": {"N": "0.95"},
                "is_partial": {"BOOL": True},
                "sources": {"L": [{"S": "dedup:abc"}]},
                "ttl": {"N": "9999999999"},
            },
        )
        put_items(
            [make_item("a#1", "2026-01-14T10:00:00+00:00", "negative", 0.9, ["NVDA"])]
        )

        run_backfill()

        item = aws.get_item(
            TableName=TS_TABLE,
            Key={
                "PK": {"S": "NVDA#24h"},
                "SK": {"S": "2026-01-14T00:00:00+00:00"},
            },
        )["Item"]
        assert item["version"]["N"] == "1"
        assert float(item["sum"]["N"]) == pytest.approx(-0.9)
        assert item["count"]["N"] == "1"

    @freeze_time(FROZEN_NOW)
    def test_failing_write_lands_in_manifest_and_run_continues(self, aws):
        put_items(
            [
                make_item(
                    "a#1", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"]
                ),
                make_item(
                    "a#2", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["AAPL"]
                ),
            ]
        )

        from botocore.exceptions import ClientError

        original = aws.put_item

        def flaky_put(**kwargs):
            if kwargs["Item"]["PK"]["S"].startswith("NVDA#"):
                raise ClientError({"Error": {"Code": "InternalServerError"}}, "PutItem")
            return original(**kwargs)

        with (
            patch.object(backfill.time, "sleep"),
            patch.object(aws, "put_item", flaky_put),
        ):
            with patch.object(backfill.boto3, "Session") as mock_session:
                mock_session.return_value.client.side_effect = lambda service, **kw: (
                    aws
                    if service == "dynamodb"
                    else boto3.client(service, region_name="us-east-1")
                )
                manifest = backfill.run(
                    backfill.parse_args(["--env", ENV]), mock_session.return_value
                )

        assert manifest["failures"]
        assert all(f["ticker"] == "NVDA" for f in manifest["failures"])
        assert all(
            f["error_class"] == "InternalServerError" for f in manifest["failures"]
        )
        # The AAPL side of the run still completed
        buckets = scan_ts(aws)
        assert any(pk.startswith("AAPL#") for pk, _ in buckets)


class TestScopeAndDryRun:
    @freeze_time(FROZEN_NOW)
    def test_dry_run_emits_manifest_with_zero_writes(self, aws):
        put_items(
            [make_item("a#1", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"])]
        )

        manifest = run_backfill(["--dry-run"])

        assert manifest["dry_run"] is True
        assert scan_ts(aws) == {}
        assert manifest["per_resolution"]["24h"]["buckets_written"] == 1

    @freeze_time(FROZEN_NOW)
    def test_manifest_scope_records_filters_and_argv(self, aws):
        put_items(
            [
                make_item(
                    "a#1", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"]
                ),
                make_item(
                    "a#2", "2026-01-14T10:00:00+00:00", "negative", 0.9, ["AAPL"]
                ),
            ]
        )

        manifest = run_backfill(
            ["--ticker", "NVDA", "--window", "2026-01-14T00:00:00+00:00"]
        )

        assert manifest["scope"]["ticker_filter"] == ["NVDA"]
        assert manifest["scope"]["window_filter"] == {
            "from": "2026-01-14T00:00:00+00:00",
            "to": "2026-01-14T00:00:00+00:00",
        }
        assert "--ticker" in manifest["scope"]["argv"]
        buckets = scan_ts(aws)
        assert all(pk.startswith("NVDA#") for pk, _ in buckets)
        # Only windows containing the filter instant are written
        assert ("NVDA#24h", "2026-01-14T00:00:00+00:00") in buckets

    @freeze_time(FROZEN_NOW)
    def test_manifest_carries_contract_fields(self, aws, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        put_items(
            [make_item("a#1", "2026-01-14T10:00:00+00:00", "positive", 0.8, ["NVDA"])]
        )

        with patch.object(backfill.time, "sleep"):
            manifest = backfill.main(["--env", ENV, "--dry-run"])

        for field in (
            "assumed_role_arn",
            "session_name",
            "environment",
            "started_at",
            "finished_at",
            "quiescence",
            "window",
            "scope",
            "per_resolution",
            "items_read",
            "rejected_timestamps",
            "failures",
            "dry_run",
        ):
            assert field in manifest, field
        manifest_files = list(tmp_path.glob("backfill-manifest-*.json"))
        assert len(manifest_files) == 1
        assert json.loads(manifest_files[0].read_text()) == manifest
