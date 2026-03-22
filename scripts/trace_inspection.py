#!/usr/bin/env python3
"""End-to-end trace inspection diagnostic.

Creates anonymous session, queries 3 ticker scenarios (warm/cold/invalid),
captures X-Ray traces, CloudWatch cache metrics, and generates a
portfolio-quality markdown report.

Usage:
    python scripts/trace_inspection.py [--output reports/trace-inspection.md]
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import httpx

# -- Configuration --
DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws",
)
REGION = os.environ.get("AWS_REGION", "us-east-1")
CW_NAMESPACE = "SentimentAnalyzer"

# Tickers: warm (recently cached), cold (never queried), invalid
WARM_TICKER = os.environ.get("WARM_TICKER", "AAPL")
COLD_TICKER = os.environ.get("COLD_TICKER", "LCID")
INVALID_TICKER = os.environ.get("INVALID_TICKER", "ZZZZXQ9")


@dataclass
class RequestResult:
    """Captured data from a single API request."""

    ticker: str
    endpoint: str
    scenario: str  # cold, warm, invalid
    status_code: int
    latency_ms: float
    trace_id: str | None
    cache_source: str | None
    cache_age: str | None
    content_type: str | None
    response_body: dict | None
    error: str | None = None


@dataclass
class TraceTree:
    """Parsed X-Ray trace."""

    trace_id: str
    total_duration_ms: float
    has_error: bool
    has_fault: bool
    segments: list[dict] = field(default_factory=list)
    subsegments: list[dict] = field(default_factory=list)


@dataclass
class CacheMetricSnapshot:
    """CloudWatch cache metrics for a time window."""

    cache_name: str
    hits: float
    misses: float
    evictions: float

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


# -- HTTP Client --


def create_session(base_url: str) -> tuple[str, str]:
    """Create anonymous session, return (token, user_id)."""
    resp = httpx.post(
        f"{base_url}/api/v2/auth/anonymous",
        json={},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["token"], data["user_id"]


def make_request(
    base_url: str,
    token: str,
    ticker: str,
    endpoint: str,
    scenario: str,
    params: dict | None = None,
) -> RequestResult:
    """Make an authenticated API request and capture diagnostics."""
    url = f"{base_url}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    start = time.monotonic()
    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=30)
        latency_ms = (time.monotonic() - start) * 1000

        trace_header = resp.headers.get("x-amzn-trace-id", "")
        trace_id = None
        if "Root=" in trace_header:
            trace_id = trace_header.split("Root=")[1].split(";")[0]

        body = None
        try:
            body = resp.json()
        except Exception:
            pass

        return RequestResult(
            ticker=ticker,
            endpoint=endpoint,
            scenario=scenario,
            status_code=resp.status_code,
            latency_ms=latency_ms,
            trace_id=trace_id,
            cache_source=resp.headers.get("x-cache-source"),
            cache_age=resp.headers.get("x-cache-age"),
            content_type=resp.headers.get("content-type"),
            response_body=body,
        )
    except Exception as e:
        latency_ms = (time.monotonic() - start) * 1000
        return RequestResult(
            ticker=ticker,
            endpoint=endpoint,
            scenario=scenario,
            status_code=0,
            latency_ms=latency_ms,
            trace_id=None,
            cache_source=None,
            cache_age=None,
            content_type=None,
            response_body=None,
            error=str(e),
        )


# -- X-Ray --


def fetch_trace(trace_id: str, xray_client) -> TraceTree | None:
    """Fetch and parse a single X-Ray trace."""
    resp = xray_client.batch_get_traces(TraceIds=[trace_id])
    traces = resp.get("Traces", [])
    if not traces:
        return None

    trace = traces[0]
    segments = []
    subsegments = []

    for seg_data in trace.get("Segments", []):
        doc = json.loads(seg_data["Document"])
        origin = doc.get("origin", "")
        duration = (doc.get("end_time", 0) - doc.get("start_time", 0)) * 1000

        seg_info = {
            "name": doc.get("name"),
            "origin": origin,
            "duration_ms": duration,
            "annotations": doc.get("annotations", {}),
            "metadata_keys": {
                ns: list(data.keys())
                for ns, data in doc.get("metadata", {}).items()
            },
            "fault": doc.get("fault", False),
            "error": doc.get("error", False),
        }
        segments.append(seg_info)

        # Only parse subsegments from the Lambda function segment
        if "Function" in origin:
            _extract_subsegments(doc.get("subsegments", []), subsegments, depth=0)

    total_duration = max((s["duration_ms"] for s in segments), default=0)
    has_error = any(s["error"] for s in segments)
    has_fault = any(s["fault"] for s in segments)

    return TraceTree(
        trace_id=trace_id,
        total_duration_ms=total_duration,
        has_error=has_error,
        has_fault=has_fault,
        segments=segments,
        subsegments=subsegments,
    )


def _extract_subsegments(subs: list, result: list, depth: int) -> None:
    """Recursively extract subsegments into a flat list with depth."""
    for sub in subs:
        duration = (sub.get("end_time", 0) - sub.get("start_time", 0)) * 1000
        namespace = sub.get("namespace", "")

        # AWS service details
        aws_info = sub.get("aws", {})
        operation = aws_info.get("operation", "")
        table_name = aws_info.get("table_name", "")

        # HTTP details
        http_info = sub.get("http", {})
        http_status = http_info.get("response", {}).get("status")
        http_url = http_info.get("request", {}).get("url", "")

        result.append(
            {
                "name": sub.get("name", "?"),
                "depth": depth,
                "duration_ms": duration,
                "namespace": namespace,
                "operation": operation,
                "table_name": table_name,
                "http_status": http_status,
                "http_url": http_url,
                "fault": sub.get("fault", False),
                "error": sub.get("error", False),
            }
        )

        if "subsegments" in sub:
            _extract_subsegments(sub["subsegments"], result, depth + 1)


# -- CloudWatch --


def fetch_cache_metrics(
    cw_client,
    start_time: datetime,
    end_time: datetime,
) -> list[CacheMetricSnapshot]:
    """Fetch cache hit/miss/eviction metrics from CloudWatch."""
    cache_names = [
        "ticker",
        "metrics",
        "ohlc_response",
        "sentiment",
        "config",
        "tiingo",
        "finnhub",
        "secrets",
        "circuit_breaker",
    ]

    results = []
    for cache_name in cache_names:
        snapshot = CacheMetricSnapshot(
            cache_name=cache_name, hits=0, misses=0, evictions=0
        )

        for metric_name, attr in [
            ("Cache/Hits", "hits"),
            ("Cache/Misses", "misses"),
            ("Cache/Evictions", "evictions"),
        ]:
            try:
                resp = cw_client.get_metric_statistics(
                    Namespace=CW_NAMESPACE,
                    MetricName=metric_name,
                    Dimensions=[
                        {"Name": "Cache", "Value": cache_name},
                        {"Name": "Environment", "Value": "preprod"},
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=60,
                    Statistics=["Sum"],
                )
                datapoints = resp.get("Datapoints", [])
                total = sum(dp.get("Sum", 0) for dp in datapoints)
                setattr(snapshot, attr, total)
            except Exception:
                pass

        results.append(snapshot)

    return results


# -- Report Generation --


def generate_report(
    requests: list[RequestResult],
    traces: dict[str, TraceTree | None],
    cache_before: list[CacheMetricSnapshot],
    cache_after: list[CacheMetricSnapshot],
    session_info: dict,
    test_start: datetime,
    test_end: datetime,
) -> str:
    """Generate the full markdown report."""
    lines = []

    lines.append("# Trace Inspection Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Environment:** preprod")
    lines.append(f"**Dashboard URL:** `{DASHBOARD_URL}`")
    lines.append(f"**Test Window:** {test_start.strftime('%H:%M:%S')} → {test_end.strftime('%H:%M:%S')} UTC ({(test_end - test_start).seconds}s)")
    lines.append(f"**Session:** `{session_info['user_id'][:8]}...` (anonymous)")
    lines.append("")

    # --- Executive Summary ---
    lines.append("## Executive Summary")
    lines.append("")
    total = len(requests)
    ok = sum(1 for r in requests if r.status_code in (200, 400, 404))
    traced = sum(1 for r in requests if r.trace_id and traces.get(r.trace_id))
    lines.append(f"- **{total} requests** made across 3 ticker scenarios")
    lines.append(f"- **{ok}/{total}** returned expected status codes")
    lines.append(f"- **{traced}/{total}** produced inspectable X-Ray traces")

    cold_req = [r for r in requests if r.scenario == "cold_miss"]
    warm_req = [r for r in requests if r.scenario == "cold_hit"]
    if cold_req and warm_req:
        speedup = cold_req[0].latency_ms / warm_req[0].latency_ms if warm_req[0].latency_ms > 0 else 0
        lines.append(
            f"- **Cache speedup:** {cold_req[0].latency_ms:.0f}ms (cold) → "
            f"{warm_req[0].latency_ms:.0f}ms (warm) = **{speedup:.1f}x faster**"
        )
    lines.append("")

    # --- Request Summary Table ---
    lines.append("## Request Results")
    lines.append("")
    lines.append("| # | Ticker | Scenario | Endpoint | Status | Latency | Cache Source | Trace |")
    lines.append("|---|--------|----------|----------|--------|---------|-------------|-------|")
    for i, r in enumerate(requests, 1):
        trace_link = f"`{r.trace_id[:16]}...`" if r.trace_id else "—"
        cache = r.cache_source or "—"
        lines.append(
            f"| {i} | {r.ticker} | {r.scenario} | `{r.endpoint}` | "
            f"{r.status_code} | {r.latency_ms:.0f}ms | {cache} | {trace_link} |"
        )
    lines.append("")

    # --- Trace Waterfall per request ---
    lines.append("## X-Ray Trace Analysis")
    lines.append("")

    for r in requests:
        if not r.trace_id or r.trace_id not in traces or traces[r.trace_id] is None:
            lines.append(f"### {r.ticker} ({r.scenario})")
            lines.append(f"*No trace data available (trace_id: {r.trace_id or 'none'})*")
            lines.append("")
            continue

        tree = traces[r.trace_id]
        lines.append(f"### {r.ticker} ({r.scenario}) — {tree.total_duration_ms:.0f}ms")
        err_badge = ""
        if tree.has_fault:
            err_badge = " ⛔ FAULT"
        elif tree.has_error:
            err_badge = " ⚠️ ERROR"
        lines.append(f"Trace ID: `{r.trace_id}`{err_badge}")
        lines.append("")

        if tree.subsegments:
            lines.append("```")
            lines.append(f"{'Subsegment':<55} {'Duration':>10} {'Details'}")
            lines.append(f"{'─' * 55} {'─' * 10} {'─' * 30}")
            for sub in tree.subsegments:
                indent = "  " * sub["depth"]
                name = sub["name"]
                if len(indent + name) > 50:
                    name = name[: 50 - len(indent)] + "…"
                display = f"{indent}{name}"

                details_parts = []
                if sub["namespace"]:
                    details_parts.append(f"[{sub['namespace']}]")
                if sub["operation"]:
                    details_parts.append(sub["operation"])
                if sub["table_name"]:
                    details_parts.append(f"table={sub['table_name']}")
                if sub["http_status"]:
                    details_parts.append(f"HTTP {sub['http_status']}")
                if sub["fault"]:
                    details_parts.append("FAULT")
                if sub["error"]:
                    details_parts.append("ERROR")
                details = " ".join(details_parts)

                lines.append(f"{display:<55} {sub['duration_ms']:>8.1f}ms {details}")
            lines.append("```")
        lines.append("")

    # --- Cold vs Warm Comparison ---
    cold_ohlc = [r for r in requests if r.scenario == "cold_miss" and "ohlc" in r.endpoint]
    warm_ohlc = [r for r in requests if r.scenario == "cold_hit" and "ohlc" in r.endpoint]
    if cold_ohlc and warm_ohlc:
        lines.append("## Cold vs Warm Path Comparison (OHLC)")
        lines.append("")
        c, w = cold_ohlc[0], warm_ohlc[0]
        lines.append("| Metric | Cold (1st request) | Warm (2nd request) |")
        lines.append("|--------|-------------------|-------------------|")
        lines.append(f"| **Client latency** | {c.latency_ms:.0f}ms | {w.latency_ms:.0f}ms |")
        lines.append(f"| **Cache source** | {c.cache_source or '—'} | {w.cache_source or '—'} |")
        lines.append(f"| **Cache age** | {c.cache_age or '—'}s | {w.cache_age or '—'}s |")
        lines.append(f"| **Status** | {c.status_code} | {w.status_code} |")

        # Compare trace subsegments
        ct = traces.get(c.trace_id)
        wt = traces.get(w.trace_id)
        if ct and wt:
            c_ext = [s for s in ct.subsegments if s["namespace"] in ("aws", "remote")]
            w_ext = [s for s in wt.subsegments if s["namespace"] in ("aws", "remote")]
            lines.append(f"| **External calls** | {len(c_ext)} | {len(w_ext)} |")
            lines.append(f"| **Trace duration** | {ct.total_duration_ms:.0f}ms | {wt.total_duration_ms:.0f}ms |")

            c_tiingo = [s for s in ct.subsegments if "tiingo" in s["name"].lower()]
            w_tiingo = [s for s in wt.subsegments if "tiingo" in s["name"].lower()]
            c_tiingo_str = f"Yes ({c_tiingo[0]['duration_ms']:.0f}ms)" if c_tiingo else "No"
            w_tiingo_str = f"Yes ({w_tiingo[0]['duration_ms']:.0f}ms)" if w_tiingo else "No"
            lines.append(f"| **Tiingo API call** | {c_tiingo_str} | {w_tiingo_str} |")

            c_dynamo = [s for s in ct.subsegments if "dynamo" in s["name"].lower()]
            w_dynamo = [s for s in wt.subsegments if "dynamo" in s["name"].lower()]
            lines.append(
                f"| **DynamoDB calls** | {len(c_dynamo)} ({sum(s['duration_ms'] for s in c_dynamo):.0f}ms) | "
                f"{len(w_dynamo)} ({sum(s['duration_ms'] for s in w_dynamo):.0f}ms) |"
            )
        lines.append("")

    # --- Cache Metrics ---
    lines.append("## CloudWatch Cache Metrics (during test window)")
    lines.append("")
    lines.append(
        "Metrics are flushed every 60s. Showing delta between pre-test and post-test snapshots."
    )
    lines.append("")
    lines.append("| Cache | Hits (Δ) | Misses (Δ) | Evictions (Δ) | Hit Rate |")
    lines.append("|-------|---------|-----------|--------------|----------|")

    any_data = False
    for before, after in zip(cache_before, cache_after):
        d_hits = after.hits - before.hits
        d_misses = after.misses - before.misses
        d_evictions = after.evictions - before.evictions
        if d_hits > 0 or d_misses > 0 or d_evictions > 0:
            any_data = True
            total = d_hits + d_misses
            rate = d_hits / total if total > 0 else 0
            lines.append(
                f"| {after.cache_name} | +{d_hits:.0f} | +{d_misses:.0f} | +{d_evictions:.0f} | {rate:.0%} |"
            )
        else:
            lines.append(f"| {after.cache_name} | — | — | — | — |")

    if not any_data:
        lines.append("")
        lines.append(
            "> **Note:** No metric deltas detected. The 60s flush interval may not have "
            "elapsed during the test window. See Visibility Gaps below."
        )
    lines.append("")

    # --- Visibility Gaps ---
    lines.append("## Visibility Gaps")
    lines.append("")
    lines.append("| Gap | Impact | Recommendation |")
    lines.append("|-----|--------|----------------|")
    lines.append(
        "| In-memory cache hits/misses invisible in X-Ray | "
        "Can't see if response was served from memory vs fell through to DynamoDB/API | "
        "Add custom X-Ray subsegment annotation on cache lookup |"
    )
    lines.append(
        "| CacheStats 60s flush interval | "
        "Short tests may complete before metrics are emitted to CloudWatch | "
        "Add on-demand flush endpoint or reduce interval in preprod |"
    )
    lines.append(
        "| `x-cache-source` header only on OHLC endpoint | "
        "Sentiment, config, and ticker endpoints don't report cache provenance | "
        "Add `x-cache-source` header to all cached endpoints |"
    )
    lines.append(
        "| No per-ticker cache key in CloudWatch dimensions | "
        "Can't tell which ticker caused a cache miss vs hit | "
        "Add `Ticker` dimension to CacheStats (high cardinality tradeoff) |"
    )
    lines.append(
        "| Invoke transport drops `X-Amzn-Trace-Id` | "
        "CI tests via invoke transport can't correlate requests to traces | "
        "Parse trace ID from Lambda invoke response metadata |"
    )
    lines.append(
        "| Quota tracker cache not in CacheStats | "
        "DynamoDB sync cache (60s) not instrumented for hit/miss tracking | "
        "Register quota tracker with CacheMetricEmitter |"
    )
    lines.append("")

    # --- Invalid Ticker ---
    invalid_reqs = [r for r in requests if r.scenario == "invalid"]
    if invalid_reqs:
        lines.append("## Error Path Validation")
        lines.append("")
        for r in invalid_reqs:
            lines.append(f"**`{r.endpoint}`** → HTTP {r.status_code}")
            if r.response_body:
                lines.append(f"```json\n{json.dumps(r.response_body, indent=2)[:300]}\n```")
            tree = traces.get(r.trace_id)
            if tree:
                lines.append(f"Trace duration: {tree.total_duration_ms:.0f}ms | Error: {tree.has_error} | Fault: {tree.has_fault}")
            lines.append("")

    # --- Raw Trace IDs ---
    lines.append("## Appendix: Trace IDs")
    lines.append("")
    lines.append("For manual inspection in the AWS X-Ray console:")
    lines.append("```")
    for r in requests:
        lines.append(f"{r.scenario:15} {r.ticker:10} {r.trace_id or '(none)'}")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# -- Main --


def main():
    parser = argparse.ArgumentParser(description="Trace inspection diagnostic")
    parser.add_argument(
        "--output",
        default="reports/trace-inspection.md",
        help="Output report path",
    )
    args = parser.parse_args()

    xray = boto3.client("xray", region_name=REGION)
    cw = boto3.client("cloudwatch", region_name=REGION)

    print("=" * 60)
    print("TRACE INSPECTION DIAGNOSTIC")
    print("=" * 60)

    # -- Step 1: Create session --
    print("\n[1/7] Creating anonymous session...")
    token, user_id = create_session(DASHBOARD_URL)
    print(f"  Session: {user_id[:8]}... | Token: {token[:12]}...")
    session_info = {"user_id": user_id, "token": token}

    # -- Step 2: Snapshot cache metrics BEFORE --
    print("\n[2/7] Snapshotting cache metrics (before)...")
    test_start = datetime.now(UTC)
    metric_window_start = test_start - timedelta(minutes=5)
    cache_before = fetch_cache_metrics(cw, metric_window_start, test_start)
    active_caches = [c for c in cache_before if c.hits + c.misses > 0]
    print(f"  {len(active_caches)} caches with activity in last 5min")

    # -- Step 3: Make requests --
    print("\n[3/7] Making requests...")
    requests_list: list[RequestResult] = []

    # 3a: Warm ticker (AAPL) — likely already cached
    print(f"  → {WARM_TICKER} OHLC (warm)...")
    r = make_request(DASHBOARD_URL, token, WARM_TICKER, f"/api/v2/tickers/{WARM_TICKER}/ohlc", "warm", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    print(f"  → {WARM_TICKER} sentiment (warm)...")
    r = make_request(DASHBOARD_URL, token, WARM_TICKER, f"/api/v2/tickers/{WARM_TICKER}/sentiment/history", "warm", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    # 3b: Cold ticker (LCID) — first request (cache miss)
    print(f"  → {COLD_TICKER} OHLC (cold miss)...")
    r = make_request(DASHBOARD_URL, token, COLD_TICKER, f"/api/v2/tickers/{COLD_TICKER}/ohlc", "cold_miss", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    print(f"  → {COLD_TICKER} sentiment (cold miss)...")
    r = make_request(DASHBOARD_URL, token, COLD_TICKER, f"/api/v2/tickers/{COLD_TICKER}/sentiment/history", "cold_miss", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    # 3c: Wait for cache to be populated
    print("  ⏳ Waiting 3s for cache write...")
    time.sleep(3)

    # 3d: Cold ticker again (should be cache hit now)
    print(f"  → {COLD_TICKER} OHLC (warm hit)...")
    r = make_request(DASHBOARD_URL, token, COLD_TICKER, f"/api/v2/tickers/{COLD_TICKER}/ohlc", "cold_hit", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    print(f"  → {COLD_TICKER} sentiment (warm hit)...")
    r = make_request(DASHBOARD_URL, token, COLD_TICKER, f"/api/v2/tickers/{COLD_TICKER}/sentiment/history", "cold_hit", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms | cache={r.cache_source}")

    # 3e: Invalid ticker
    print(f"  → {INVALID_TICKER} OHLC (invalid)...")
    r = make_request(DASHBOARD_URL, token, INVALID_TICKER, f"/api/v2/tickers/{INVALID_TICKER}/ohlc", "invalid", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms")

    print(f"  → {INVALID_TICKER} sentiment (invalid)...")
    r = make_request(DASHBOARD_URL, token, INVALID_TICKER, f"/api/v2/tickers/{INVALID_TICKER}/sentiment/history", "invalid", {"range": "1W"})
    requests_list.append(r)
    print(f"    {r.status_code} | {r.latency_ms:.0f}ms")

    # -- Step 4: Wait for trace propagation --
    print("\n[4/7] Waiting 10s for X-Ray trace propagation...")
    time.sleep(10)

    # -- Step 5: Fetch traces --
    print("\n[5/7] Fetching X-Ray traces...")
    trace_ids = {r.trace_id for r in requests_list if r.trace_id}
    traces: dict[str, TraceTree | None] = {}
    for tid in trace_ids:
        tree = fetch_trace(tid, xray)
        traces[tid] = tree
        status = f"{tree.total_duration_ms:.0f}ms, {len(tree.subsegments)} subsegments" if tree else "NOT FOUND"
        print(f"  {tid[:20]}... → {status}")

    # -- Step 6: Snapshot cache metrics AFTER --
    print("\n[6/7] Snapshotting cache metrics (after)...")
    test_end = datetime.now(UTC)
    # Wait a bit more to allow metric flush
    cache_after = fetch_cache_metrics(cw, metric_window_start, test_end + timedelta(minutes=2))
    deltas = []
    for b, a in zip(cache_before, cache_after):
        d = a.hits - b.hits + a.misses - b.misses
        if d > 0:
            deltas.append(f"{a.cache_name}: +{a.hits - b.hits:.0f}H/+{a.misses - b.misses:.0f}M")
    print(f"  Deltas: {', '.join(deltas) if deltas else '(none yet — 60s flush interval)'}")

    # -- Step 7: Generate report --
    print("\n[7/7] Generating report...")
    report = generate_report(
        requests_list, traces, cache_before, cache_after,
        session_info, test_start, test_end,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"\n✅ Report written to {output_path}")
    print(f"   {len(report)} bytes, {report.count(chr(10))} lines")

    # Print quick summary
    print("\n" + "=" * 60)
    print("QUICK SUMMARY")
    print("=" * 60)
    for r in requests_list:
        emoji = "✅" if r.status_code in (200,) else "⚠️" if r.status_code in (400, 404) else "❌"
        print(f"  {emoji} {r.scenario:12} {r.ticker:8} {r.status_code} {r.latency_ms:>7.0f}ms {r.cache_source or ''}")


if __name__ == "__main__":
    main()
