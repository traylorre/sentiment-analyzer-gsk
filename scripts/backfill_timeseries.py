#!/usr/bin/env python3
"""Quiesced, re-runnable backfill of the sentiment timeseries table.

Recomputes trailing-horizon buckets from sentiment-items through the same
label_to_signed mapping the live fanout uses, writes complete versioned
states under the D1 conditional guard, and emits an auditable manifest
(contracts/backfill-manifest.md). Runbook: specs/001-signed-fanout/quickstart.md.

Preflight enforces quiescence (spec Clarifications Q3): the ingestion schedule
rule must be disabled (the script offers to disable it), then drain is
verified with one CloudWatch GetMetricData call: 240 seconds of zero
Invocations after the wait, zero Throttles over the trailing 6 hours, zero
Errors over the trailing 30 minutes. --force proceeds without quiescence and
is recorded in the manifest as an operator override.
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.lib.timeseries.bucket import floor_to_bucket
from src.lib.timeseries.models import Resolution
from src.lib.timeseries.signed import label_to_signed

HORIZON_DAYS = 30
FUTURE_SKEW = timedelta(minutes=5)
DRAIN_SILENCE_SECONDS = 240
THROTTLES_WINDOW = timedelta(hours=6)
ERRORS_WINDOW = timedelta(minutes=30)


class DrainNotClean(Exception):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, choices=["preprod", "prod", "test"])
    parser.add_argument(
        "--assume-role",
        default=None,
        help="Role ARN to assume (the env's backfill-timeseries-role)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Proceed without quiescence; recorded in the manifest",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        default=None,
        help="Restrict the repair to this ticker (repeatable)",
    )
    parser.add_argument(
        "--window",
        default=None,
        help="ISO instant or from/to interval; only buckets covering it are written",
    )
    args = parser.parse_args(argv)
    args.argv = list(argv) if argv is not None else sys.argv[1:]
    return args


def _names(env: str) -> dict[str, str]:
    return {
        "items_table": f"{env}-sentiment-items",
        "timeseries_table": f"{env}-sentiment-timeseries",
        "rule": f"{env}-sentiment-ingestion-schedule",
        "function": f"{env}-sentiment-analysis",
    }


def _parse_window_filter(raw: str | None) -> dict[str, str] | None:
    if raw is None:
        return None
    if "/" in raw:
        start, end = raw.split("/", 1)
    else:
        start = end = raw
    return {"from": start, "to": end}


def _quiesce(events: Any, rule: str, force: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "rule_name": rule,
        "disabled_at": None,
        "drain_verified_at": None,
        "reenabled_at": None,
        "forced": force,
    }
    try:
        state = events.describe_rule(Name=rule)["State"]
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
            print(f"Rule {rule} does not exist; nothing to quiesce", file=sys.stderr)
            return record
        raise
    if state == "ENABLED":
        if force:
            print(
                "WARNING: rule still enabled, proceeding under --force",
                file=sys.stderr,
            )
            return record
        answer = input(f"Rule {rule} is ENABLED. Disable it now? [y/N] ")
        if answer.strip().lower() != "y":
            raise SystemExit("Refusing to run against an enabled ingestion rule")
        events.disable_rule(Name=rule)
        record["disabled_at"] = datetime.now(UTC).isoformat()
    return record


def _verify_drain(cloudwatch: Any, function: str, now: datetime) -> None:
    """One GetMetricData call for the three-part criterion (spec Q3)."""
    queries = [
        {
            "Id": "invocations",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/Lambda",
                    "MetricName": "Invocations",
                    "Dimensions": [{"Name": "FunctionName", "Value": function}],
                },
                "Period": 60,
                "Stat": "Sum",
            },
        },
        {
            "Id": "throttles",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/Lambda",
                    "MetricName": "Throttles",
                    "Dimensions": [{"Name": "FunctionName", "Value": function}],
                },
                "Period": 300,
                "Stat": "Sum",
            },
        },
        {
            "Id": "errors",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/Lambda",
                    "MetricName": "Errors",
                    "Dimensions": [{"Name": "FunctionName", "Value": function}],
                },
                "Period": 60,
                "Stat": "Sum",
            },
        },
    ]
    response = cloudwatch.get_metric_data(
        MetricDataQueries=queries,
        StartTime=now - THROTTLES_WINDOW,
        EndTime=now,
    )
    windows = {
        "invocations": now - timedelta(seconds=DRAIN_SILENCE_SECONDS),
        "throttles": now - THROTTLES_WINDOW,
        "errors": now - ERRORS_WINDOW,
    }
    for result in response.get("MetricDataResults", []):
        cutoff = windows[result["Id"]]
        dirty = sum(
            value
            for ts, value in zip(
                result.get("Timestamps", []), result.get("Values", []), strict=True
            )
            if ts.replace(tzinfo=ts.tzinfo or UTC) >= cutoff
        )
        if dirty > 0:
            raise DrainNotClean(
                f"{result['Id']} not clean over its window ({dirty}); see the "
                "escalation path in research D5 before considering --force"
            )


def _scan_items(dynamodb: Any, table: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {
        "TableName": table,
        "FilterExpression": "#s = :analyzed",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":analyzed": {"S": "analyzed"}},
    }
    while True:
        response = dynamodb.scan(**kwargs)
        items.extend(response.get("Items", []))
        last = response.get("LastEvaluatedKey")
        if not last:
            return items
        kwargs["ExclusiveStartKey"] = last


def recompute(
    items: list[dict[str, Any]],
    now: datetime,
    ticker_filter: list[str] | None,
    window_filter: dict[str, str] | None,
) -> tuple[dict[tuple[str, str], dict[str, Any]], int, dict[str, int]]:
    """Aggregate analyzed items into complete bucket states.

    Returns (buckets keyed by (PK, SK), rejected_timestamps,
    skipped_ttl per resolution).
    """
    horizon_from = now - timedelta(days=HORIZON_DAYS)
    rejected = 0
    skipped_ttl = {r.value: 0 for r in Resolution}
    contributions: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for item in items:
        try:
            ts = datetime.fromisoformat(item["timestamp"]["S"].replace("Z", "+00:00"))
            label = item["sentiment"]["S"]
            confidence = float(item["score"]["N"])
            tickers = [t["S"] for t in item.get("matched_tickers", {}).get("L", [])]
        except (KeyError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts > now + FUTURE_SKEW or ts < horizon_from:
            rejected += 1
            continue
        sources = [s["S"] for s in item.get("sources", {}).get("L", [])]
        signed = label_to_signed(label, confidence)
        for ticker in tickers:
            if ticker_filter and ticker not in ticker_filter:
                continue
            for resolution in Resolution:
                window_start = floor_to_bucket(ts, resolution)
                window_end = window_start + timedelta(
                    seconds=resolution.duration_seconds
                )
                if window_filter:
                    f_from = datetime.fromisoformat(window_filter["from"])
                    f_to = datetime.fromisoformat(window_filter["to"])
                    if window_start > f_to or window_end <= f_from:
                        continue
                key = (f"{ticker}#{resolution.value}", window_start.isoformat())
                contributions.setdefault(key, []).append(
                    {
                        "value": signed,
                        "ts": ts.isoformat(),
                        "label": label,
                        "sources": sources,
                        "resolution": resolution,
                        "window_start": window_start,
                    }
                )

    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    seen_skipped: set[tuple[str, str]] = set()
    for key, rows in contributions.items():
        resolution = rows[0]["resolution"]
        window_start = rows[0]["window_start"]
        ttl = int(window_start.timestamp()) + resolution.ttl_seconds
        if datetime.fromtimestamp(ttl, tz=UTC) <= now:
            if key not in seen_skipped:
                skipped_ttl[resolution.value] += 1
                seen_skipped.add(key)
            continue
        ordered = sorted(rows, key=lambda r: r["ts"])
        values = [r["value"] for r in ordered]
        label_counts: dict[str, int] = {}
        sources: set[str] = set()
        for row in ordered:
            label_counts[row["label"]] = label_counts.get(row["label"], 0) + 1
            sources.update(row["sources"])
        total = sum(values)
        item_state: dict[str, Any] = {
            "PK": {"S": key[0]},
            "SK": {"S": key[1]},
            "open": {"N": str(ordered[0]["value"])},
            "high": {"N": str(max(values))},
            "low": {"N": str(min(values))},
            "close": {"N": str(ordered[-1]["value"])},
            "open_ts": {"S": ordered[0]["ts"]},
            "close_ts": {"S": ordered[-1]["ts"]},
            "count": {"N": str(len(values))},
            "sum": {"N": str(total)},
            "avg": {"N": str(total / len(values))},
            "ttl": {"N": str(ttl)},
            "is_partial": {"BOOL": True},
            "label_counts": {
                "M": {label: {"N": str(n)} for label, n in label_counts.items()}
            },
            "original_timestamp": {"S": ordered[-1]["ts"]},
        }
        if sources:
            item_state["sources"] = {"SS": sorted(sources)}
        buckets[key] = item_state
    return buckets, rejected, skipped_ttl


def write_buckets(
    dynamodb: Any,
    table: str,
    buckets: dict[tuple[str, str], dict[str, Any]],
    dry_run: bool,
) -> tuple[dict[str, int], list[dict[str, str]]]:
    written = {r.value: 0 for r in Resolution}
    failures: list[dict[str, str]] = []
    for (pk, sk), state in buckets.items():
        resolution = pk.split("#")[1]
        if dry_run:
            written[resolution] += 1
            continue
        try:
            existing = dynamodb.get_item(
                TableName=table,
                Key={"PK": {"S": pk}, "SK": {"S": sk}},
                ConsistentRead=True,
            ).get("Item")
            if existing and "version" in existing:
                expected = existing["version"]["N"]
                state["version"] = {"N": str(int(expected) + 1)}
                dynamodb.put_item(
                    TableName=table,
                    Item=state,
                    ConditionExpression="version = :expected",
                    ExpressionAttributeValues={":expected": {"N": expected}},
                )
            else:
                state["version"] = {"N": "1"}
                dynamodb.put_item(
                    TableName=table,
                    Item=state,
                    ConditionExpression="attribute_not_exists(version)",
                )
            written[resolution] += 1
        except ClientError as e:
            failures.append(
                {
                    "ticker": pk.split("#")[0],
                    "resolution": resolution,
                    "window": sk,
                    "error_class": e.response.get("Error", {}).get("Code", "Unknown"),
                }
            )
    return written, failures


def run(args: argparse.Namespace, session: Any) -> dict[str, Any]:
    names = _names(args.env)
    started_at = datetime.now(UTC)
    assumed_role_arn = None
    session_name = None
    if args.assume_role:
        session_name = f"backfill-timeseries-{int(started_at.timestamp())}"
        creds = session.client("sts").assume_role(
            RoleArn=args.assume_role, RoleSessionName=session_name
        )["Credentials"]
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
        assumed_role_arn = args.assume_role

    dynamodb = session.client("dynamodb")
    events = session.client("events")
    cloudwatch = session.client("cloudwatch")

    quiescence = {
        "rule_name": names["rule"],
        "disabled_at": None,
        "drain_verified_at": None,
        "reenabled_at": None,
        "forced": args.force,
    }
    if not args.dry_run:
        quiescence = _quiesce(events, names["rule"], args.force)
        if not args.force:
            time.sleep(DRAIN_SILENCE_SECONDS)
            _verify_drain(cloudwatch, names["function"], datetime.now(UTC))
            quiescence["drain_verified_at"] = datetime.now(UTC).isoformat()

    now = datetime.now(UTC)
    items = _scan_items(dynamodb, names["items_table"])
    window_filter = _parse_window_filter(args.window)
    buckets, rejected, skipped_ttl = recompute(items, now, args.ticker, window_filter)
    written, failures = write_buckets(
        dynamodb, names["timeseries_table"], buckets, args.dry_run
    )

    if quiescence["disabled_at"] and not args.dry_run:
        events.enable_rule(Name=names["rule"])
        quiescence["reenabled_at"] = datetime.now(UTC).isoformat()

    horizon_from = now - timedelta(days=HORIZON_DAYS)
    return {
        "assumed_role_arn": assumed_role_arn,
        "session_name": session_name,
        "environment": args.env,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "quiescence": quiescence,
        "window": {"from": horizon_from.isoformat(), "to": now.isoformat()},
        "scope": {
            "ticker_filter": args.ticker,
            "window_filter": window_filter,
            "argv": args.argv,
        },
        "per_resolution": {
            r.value: {
                "buckets_written": written[r.value],
                "buckets_skipped_ttl": skipped_ttl[r.value],
                "failures": sum(1 for f in failures if f["resolution"] == r.value),
            }
            for r in Resolution
        },
        "items_read": len(items),
        "rejected_timestamps": rejected,
        "failures": failures,
        "dry_run": args.dry_run,
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    manifest = run(args, boto3.Session())
    payload = json.dumps(manifest, indent=2, default=str)
    print(payload)
    stamp = manifest["started_at"].replace(":", "").replace("+0000", "Z")
    path = f"backfill-manifest-{args.env}-{stamp}.json"
    with open(path, "w") as f:
        f.write(payload)
    print(f"Manifest written to {path}", file=sys.stderr)
    return manifest


if __name__ == "__main__":
    main()
