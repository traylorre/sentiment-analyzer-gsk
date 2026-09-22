"""
Accumulating time-series write fanout for multi-resolution sentiment data.

One signed sentiment contribution fans out into 6 resolution buckets
(1m/5m/15m/30m/1h/24h). Each bucket write is optimistic concurrency: read the
bucket, compute the complete next state locally, write it with a single
conditional PutItem guarded on a `version` attribute (research D1). Every
observable bucket is therefore a complete, internally consistent state at a
single version.

Import constraint: the SSE image copies src/lib/timeseries as a whole
directory but top-level src/lib files individually, so this module must not
import any top-level src/lib module other than metrics.py.
"""

import logging
import random
import time
from datetime import datetime
from typing import Any

from botocore.exceptions import ClientError

from src.lib.timeseries.bucket import floor_to_bucket
from src.lib.timeseries.models import Resolution, SentimentScore

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 0.05


class FanoutWriteError(Exception):
    """A bucket write failed after bounded retries.

    Carries the repair coordinates: run the backfill for this ticker/window
    (quickstart.md runbook).
    """

    def __init__(
        self, ticker: str, resolution: str, window: str, error_class: str
    ) -> None:
        self.ticker = ticker
        self.resolution = resolution
        self.window = window
        self.error_class = error_class
        super().__init__(
            f"fanout write failed for {ticker}#{resolution} window {window}: "
            f"{error_class}"
        )


def _parse_number(item: dict[str, Any], field: str) -> float:
    return float(item[field]["N"])


def _parse_label_counts(item: dict[str, Any]) -> dict[str, int]:
    raw = item.get("label_counts", {}).get("M", {})
    return {label: int(value["N"]) for label, value in raw.items()}


def _parse_sources(item: dict[str, Any]) -> set[str]:
    # Only the string-set shape survives; legacy list-of-dedup-ids sources are
    # dropped on adoption (research D8).
    if "sources" in item and "SS" in item["sources"]:
        return set(item["sources"]["SS"])
    return set()


def _next_state(
    current: dict[str, Any] | None,
    score: SentimentScore,
    bucket_timestamp: datetime,
    resolution: Resolution,
) -> tuple[dict[str, Any], int | None]:
    """Compute the complete next bucket state.

    Returns (item, expected_version); expected_version is None when the read
    found no version attribute (absent bucket or legacy pre-cutover bucket).
    """
    article_ts = score.timestamp.isoformat()
    ttl = int(bucket_timestamp.timestamp()) + resolution.ttl_seconds

    if current is None:
        expected_version = None
        count = 1
        total = score.value
        open_value, close_value = score.value, score.value
        open_ts, close_ts = article_ts, article_ts
        high, low = score.value, score.value
        label_counts: dict[str, int] = {score.label: 1} if score.label else {}
        sources: set[str] = {score.source} if score.source else set()
        version = 1
    else:
        expected_version = (
            int(current["version"]["N"]) if "version" in current else None
        )
        count = int(current["count"]["N"]) + 1
        total = _parse_number(current, "sum") + score.value
        high = max(_parse_number(current, "high"), score.value)
        low = min(_parse_number(current, "low"), score.value)

        # Legacy buckets predate open_ts/close_ts; original_timestamp is the
        # only ordering signal they carry.
        fallback_ts = current.get("original_timestamp", {}).get("S", article_ts)
        open_ts = current.get("open_ts", {}).get("S", fallback_ts)
        close_ts = current.get("close_ts", {}).get("S", fallback_ts)
        open_value = _parse_number(current, "open")
        close_value = _parse_number(current, "close")
        if article_ts < open_ts:
            open_value, open_ts = score.value, article_ts
        if article_ts >= close_ts:
            close_value, close_ts = score.value, article_ts

        label_counts = _parse_label_counts(current)
        if score.label:
            label_counts[score.label] = label_counts.get(score.label, 0) + 1
        sources = _parse_sources(current)
        if score.source:
            sources.add(score.source)
        version = (expected_version or 0) + 1

    item: dict[str, Any] = {
        "PK": {"S": f"{score.ticker}#{resolution.value}"},
        "SK": {"S": bucket_timestamp.isoformat()},
        "open": {"N": str(open_value)},
        "high": {"N": str(high)},
        "low": {"N": str(low)},
        "close": {"N": str(close_value)},
        "open_ts": {"S": open_ts},
        "close_ts": {"S": close_ts},
        "count": {"N": str(count)},
        "sum": {"N": str(total)},
        "avg": {"N": str(total / count)},
        "ttl": {"N": str(ttl)},
        "is_partial": {"BOOL": True},
        "label_counts": {
            "M": {label: {"N": str(n)} for label, n in label_counts.items()}
        },
        "version": {"N": str(version)},
        "original_timestamp": {"S": close_ts},
    }
    if sources:
        item["sources"] = {"SS": sorted(sources)}
    return item, expected_version


def _read_bucket(
    dynamodb: Any, table_name: str, pk: str, sk: str
) -> dict[str, Any] | None:
    response = dynamodb.get_item(
        TableName=table_name,
        Key={"PK": {"S": pk}, "SK": {"S": sk}},
        ConsistentRead=True,
    )
    return response.get("Item")


def accumulate_fanout(
    dynamodb: Any,
    table_name: str,
    score: SentimentScore,
) -> None:
    """
    Accumulate one signed contribution into all 6 resolution buckets.

    Per resolution: read, compute complete next state, conditional PutItem.
    The guard has two branches chosen by what the read returned:
    `version = :expected` when the bucket carried a version, and
    `attribute_not_exists(version)` when it did not, which covers absent
    buckets and legacy pre-cutover buckets alike. Losers of a version race
    re-read and retry with jittered backoff, bounded at MAX_RETRIES.

    Raises:
        ValueError: if score.ticker is missing
        FanoutWriteError: when a bucket write fails after bounded retries
    """
    if not score.ticker:
        raise ValueError("Sentiment score must have a ticker for fanout")

    for resolution in Resolution:
        bucket_timestamp = floor_to_bucket(score.timestamp, resolution)
        pk = f"{score.ticker}#{resolution.value}"
        sk = bucket_timestamp.isoformat()

        attempt = 0
        while True:
            current = _read_bucket(dynamodb, table_name, pk, sk)
            item, expected_version = _next_state(
                current, score, bucket_timestamp, resolution
            )

            if expected_version is None:
                condition = "attribute_not_exists(version)"
                values = None
            else:
                condition = "version = :expected"
                values = {":expected": {"N": str(expected_version)}}

            kwargs: dict[str, Any] = {
                "TableName": table_name,
                "Item": item,
                "ConditionExpression": condition,
            }
            if values:
                kwargs["ExpressionAttributeValues"] = values

            try:
                dynamodb.put_item(**kwargs)
                break
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code != "ConditionalCheckFailedException":
                    logger.error(
                        "Fanout PutItem failed",
                        extra={
                            "error_code": error_code,
                            "ticker": score.ticker,
                            "resolution": resolution.value,
                            "window": sk,
                        },
                    )
                    raise FanoutWriteError(
                        ticker=score.ticker,
                        resolution=resolution.value,
                        window=sk,
                        error_class=error_code or type(e).__name__,
                    ) from e
                attempt += 1
                if attempt > MAX_RETRIES:
                    raise FanoutWriteError(
                        ticker=score.ticker,
                        resolution=resolution.value,
                        window=sk,
                        error_class="ConditionalCheckFailedException",
                    ) from e
                # Full jitter so concurrent losers do not retry in lockstep
                time.sleep(
                    random.uniform(  # noqa: S311 - backoff jitter, not crypto
                        BASE_BACKOFF_SECONDS / 2,
                        BASE_BACKOFF_SECONDS * (2**attempt),
                    )
                )
