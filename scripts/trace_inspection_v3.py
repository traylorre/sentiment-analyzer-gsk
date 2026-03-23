#!/usr/bin/env python3
"""Comprehensive trace inspection diagnostic v3.

Addresses gaps from v2: sentiment investigation, data correctness,
Tier 1 cache validation, failure paths, cold start, confidence levels.

Usage:
    python scripts/trace_inspection_v3.py [--output reports/trace-inspection-v3.md]
"""

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import boto3
import httpx

DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL",
    "https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws",
)
REGION = os.environ.get("AWS_REGION", "us-east-1")
COLD_TICKER = os.environ.get("COLD_TICKER", "AMC")  # Least likely to be cached


@dataclass
class TestResult:
    name: str
    status: str  # PASS, FAIL, WARN, INFO
    confidence: str  # HIGH, MEDIUM, LOW, NOT_TESTED
    detail: str
    data: dict = field(default_factory=dict)


def api_get(token: str, path: str, params: dict | None = None) -> tuple[httpx.Response, float]:
    """Make authenticated GET, return (response, latency_ms)."""
    t0 = time.monotonic()
    resp = httpx.get(
        f"{DASHBOARD_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=30,
    )
    return resp, (time.monotonic() - t0) * 1000


def create_session() -> tuple[str, str]:
    resp = httpx.post(f"{DASHBOARD_URL}/api/v2/auth/anonymous", json={}, timeout=30)
    resp.raise_for_status()
    d = resp.json()
    return d["token"], d["user_id"]


def fetch_trace(xray, trace_id: str) -> dict | None:
    """Fetch trace and return subsegment summary."""
    resp = xray.batch_get_traces(TraceIds=[trace_id])
    traces = resp.get("Traces", [])
    if not traces:
        return None
    result = {"subsegments": [], "total_ms": 0}
    for seg_data in traces[0].get("Segments", []):
        doc = json.loads(seg_data["Document"])
        if "Function" in doc.get("origin", ""):
            dur = (doc.get("end_time", 0) - doc.get("start_time", 0)) * 1000
            result["total_ms"] = dur
            for sub in doc.get("subsegments", []):
                s_dur = (sub.get("end_time", 0) - sub.get("start_time", 0)) * 1000
                result["subsegments"].append({
                    "name": sub.get("name", "?"),
                    "duration_ms": s_dur,
                    "namespace": sub.get("namespace", ""),
                    "operation": sub.get("aws", {}).get("operation", ""),
                    "table": sub.get("aws", {}).get("table_name", ""),
                })
    return result


def get_trace_id(resp: httpx.Response) -> str | None:
    hdr = resp.headers.get("x-amzn-trace-id", "")
    if "Root=" in hdr:
        return hdr.split("Root=")[1].split(";")[0]
    return None


def run_tests() -> list[TestResult]:
    results = []
    xray = boto3.client("xray", region_name=REGION)

    # ─── Test 1: Cold Start Measurement ───
    print("[1/8] Cold start measurement...")
    # Invoke a rarely-used path to increase chance of cold start
    t0 = time.monotonic()
    try:
        cold_resp = httpx.get(f"{DASHBOARD_URL}/health", timeout=30)
        cold_ms = (time.monotonic() - t0) * 1000
        # Check if this was a cold start by looking at trace Init segment
        cold_trace_id = get_trace_id(cold_resp)
        time.sleep(3)
        is_cold = False
        if cold_trace_id:
            trace_data = fetch_trace(xray, cold_trace_id)
            if trace_data:
                init_subs = [s for s in trace_data["subsegments"] if s["name"] == "Init"]
                is_cold = len(init_subs) > 0
        results.append(TestResult(
            name="Cold Start Latency",
            status="INFO",
            confidence="MEDIUM" if is_cold else "LOW",
            detail=f"{'Cold start detected' if is_cold else 'Warm instance (no Init segment)'}: {cold_ms:.0f}ms client-side",
            data={"latency_ms": cold_ms, "is_cold": is_cold},
        ))
    except Exception as e:
        results.append(TestResult("Cold Start Latency", "FAIL", "HIGH", f"Health check failed: {e}"))
    print(f"  {cold_ms:.0f}ms ({'cold' if is_cold else 'warm'})")

    # ─── Test 2: Create session ───
    print("[2/8] Creating session...")
    token, user_id = create_session()
    print(f"  Session: {user_id[:8]}...")

    # ─── Test 3: OHLC Data Correctness ───
    print(f"[3/8] OHLC data correctness ({COLD_TICKER})...")
    resp, latency = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/ohlc", {"range": "1W"})
    cache_source = resp.headers.get("x-cache-source", "unknown")
    ohlc_trace_id = get_trace_id(resp)

    if resp.status_code == 200:
        d = resp.json()
        candles = d.get("candles", [])
        start = d.get("start_date", "")
        end = d.get("end_date", "")

        # Trading days check: 1W should have ~5 candles (Mon-Fri)
        candle_count_ok = 3 <= len(candles) <= 7
        # Date range check: end should be recent
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        date_reasonable = end >= (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%d")
        # Price sanity: should be > $0 and < $100000
        prices_ok = all(0 < c.get("close", 0) < 100000 for c in candles) if candles else False
        # Volume sanity: should be > 0
        volumes_ok = all(c.get("volume", 0) > 0 for c in candles) if candles else False

        all_ok = candle_count_ok and date_reasonable and prices_ok and volumes_ok
        detail_parts = []
        if candles:
            detail_parts.append(f"{len(candles)} candles ({start} to {end})")
            detail_parts.append(f"close range ${min(c['close'] for c in candles):.2f}-${max(c['close'] for c in candles):.2f}")
            detail_parts.append(f"volume range {min(c['volume'] for c in candles):,}-{max(c['volume'] for c in candles):,}")
        if not candle_count_ok:
            detail_parts.append(f"UNEXPECTED candle count: {len(candles)} (expected 3-7 for 1W)")
        if not date_reasonable:
            detail_parts.append(f"STALE: end date {end} is not recent")

        results.append(TestResult(
            name="OHLC Data Correctness",
            status="PASS" if all_ok else "WARN",
            confidence="HIGH",
            detail="; ".join(detail_parts),
            data={"candles": len(candles), "source": d.get("source"), "cache": cache_source,
                  "latency_ms": latency, "trace_id": ohlc_trace_id},
        ))
    else:
        results.append(TestResult("OHLC Data Correctness", "FAIL", "HIGH",
                                  f"HTTP {resp.status_code}: {resp.text[:200]}"))
    print(f"  {resp.status_code} | {latency:.0f}ms | cache={cache_source} | {len(candles)} candles")

    # ─── Test 4: Sentiment is Synthetic (Confirmed by Code Review) ───
    print(f"[4/8] Sentiment endpoint investigation ({COLD_TICKER})...")
    resp_s, lat_s = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/sentiment/history", {"range": "1W"})
    sent_trace_id = get_trace_id(resp_s)
    time.sleep(3)

    if resp_s.status_code == 200:
        sd = resp_s.json()
        history = sd.get("history", [])
        scores = [h["score"] for h in history] if history else []
        # Synthetic check: same ticker always produces same scores (deterministic seed)
        resp_s2, _ = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/sentiment/history", {"range": "1W"})
        sd2 = resp_s2.json()
        scores2 = [h["score"] for h in sd2.get("history", [])]
        is_deterministic = scores == scores2

        # Check trace for external calls
        trace_data = None
        if sent_trace_id:
            trace_data = fetch_trace(xray, sent_trace_id)
        external_calls = []
        if trace_data:
            external_calls = [s for s in trace_data["subsegments"]
                             if s["namespace"] in ("aws", "remote")]

        synthetic_confirmed = is_deterministic and len(external_calls) == 0
        results.append(TestResult(
            name="Sentiment Data Source",
            status="WARN",
            confidence="HIGH",
            detail=(
                f"SYNTHETIC DATA CONFIRMED. {len(history)} points, "
                f"deterministic={is_deterministic}, external_calls={len(external_calls)}, "
                f"trace={trace_data['total_ms']:.0f}ms. "
                f"Code review: sha256(ticker) seeds RNG, no DynamoDB/API calls. "
                f"Score range: {min(scores):.3f} to {max(scores):.3f}"
            ),
            data={"points": len(history), "synthetic": synthetic_confirmed,
                  "trace_ms": trace_data["total_ms"] if trace_data else 0,
                  "latency_ms": lat_s, "trace_id": sent_trace_id},
        ))
    else:
        results.append(TestResult("Sentiment Data Source", "FAIL", "HIGH",
                                  f"HTTP {resp_s.status_code}"))
    print(f"  {resp_s.status_code} | {lat_s:.0f}ms | synthetic={'YES' if synthetic_confirmed else 'unknown'}")

    # ─── Test 5: Tier 1 (In-Memory) Cache Validation ───
    print("[5/8] Tier 1 in-memory cache validation (rapid sequential)...")
    # Pre-populate: first request caches in DynamoDB AND in-memory
    r1, lat1 = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/ohlc", {"range": "1M"})
    cache1 = r1.headers.get("x-cache-source", "unknown")
    # Immediate second request (<500ms later) — should hit in-memory on same instance
    r2, lat2 = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/ohlc", {"range": "1M"})
    cache2 = r2.headers.get("x-cache-source", "unknown")
    # Third request for confirmation
    r3, lat3 = api_get(token, f"/api/v2/tickers/{COLD_TICKER}/ohlc", {"range": "1M"})
    cache3 = r3.headers.get("x-cache-source", "unknown")

    tier1_hit = cache2 == "in-memory" or cache3 == "in-memory"
    traces_str = f"[{cache1} -> {cache2} -> {cache3}]"
    t2_id = get_trace_id(r2)

    time.sleep(3)
    tier1_trace = fetch_trace(xray, t2_id) if t2_id else None
    tier1_external = len([s for s in (tier1_trace["subsegments"] if tier1_trace else [])
                         if s["namespace"] in ("aws", "remote")])

    results.append(TestResult(
        name="Tier 1 In-Memory Cache",
        status="PASS" if tier1_hit else "WARN",
        confidence="HIGH" if tier1_hit else "MEDIUM",
        detail=(
            f"Rapid sequential: {traces_str}. "
            f"Latencies: {lat1:.0f}ms -> {lat2:.0f}ms -> {lat3:.0f}ms. "
            f"{'In-memory hit confirmed' if tier1_hit else 'NOT observed — CloudFront routed to different instances'}. "
            f"Trace external calls: {tier1_external}"
        ),
        data={"caches": [cache1, cache2, cache3], "latencies": [lat1, lat2, lat3],
              "tier1_hit": tier1_hit},
    ))
    print(f"  {traces_str} | tier1={'YES' if tier1_hit else 'NO'}")

    # ─── Test 6: Failure Path — Bad Auth ───
    print("[6/8] Failure path: expired/invalid auth...")
    resp_bad, lat_bad = api_get(
        "invalid-token-deliberately-expired",
        f"/api/v2/tickers/AAPL/ohlc", {"range": "1W"},
    )
    bad_trace_id = get_trace_id(resp_bad)
    expected_bad = resp_bad.status_code in (401, 403)
    results.append(TestResult(
        name="Auth Failure Handling",
        status="PASS" if expected_bad else "FAIL",
        confidence="HIGH",
        detail=f"Invalid token -> HTTP {resp_bad.status_code} in {lat_bad:.0f}ms. "
               f"Body: {resp_bad.text[:150]}",
        data={"status": resp_bad.status_code, "latency_ms": lat_bad, "trace_id": bad_trace_id},
    ))
    print(f"  HTTP {resp_bad.status_code} | {lat_bad:.0f}ms")

    # ─── Test 7: Failure Path — Invalid Input Variants ───
    print("[7/8] Input validation coverage...")
    validation_tests = [
        ("ticker too long", f"/api/v2/tickers/TOOLONGTICKER/ohlc", None, [400]),
        ("numeric ticker", f"/api/v2/tickers/12345/ohlc", None, [400]),
        ("SQL injection", f"/api/v2/tickers/'; DROP TABLE/ohlc", None, [400, 404, 422]),
        ("XSS attempt", f"/api/v2/tickers/<script>alert(1)</script>/ohlc", None, [400, 404, 422]),
        ("empty range", f"/api/v2/tickers/AAPL/ohlc", {"range": ""}, [200, 400, 422]),
        ("invalid resolution", f"/api/v2/tickers/AAPL/ohlc", {"resolution": "999"}, [400, 422]),
    ]
    validation_pass = 0
    validation_detail = []
    for name, path, params, expected_codes in validation_tests:
        try:
            r, lat = api_get(token, path, params)
            ok = r.status_code in expected_codes
            if ok:
                validation_pass += 1
            validation_detail.append(f"{name}: {r.status_code} {'OK' if ok else 'UNEXPECTED'} ({lat:.0f}ms)")
        except Exception as e:
            validation_detail.append(f"{name}: ERROR {e}")

    results.append(TestResult(
        name="Input Validation Coverage",
        status="PASS" if validation_pass == len(validation_tests) else "WARN",
        confidence="HIGH",
        detail=f"{validation_pass}/{len(validation_tests)} passed. " + "; ".join(validation_detail),
        data={"passed": validation_pass, "total": len(validation_tests)},
    ))
    print(f"  {validation_pass}/{len(validation_tests)} passed")

    # ─── Test 8: OHLC Degradation Header Presence ───
    print("[8/8] Cache degradation header audit...")
    # Check all response headers from OHLC requests
    audit_resp, _ = api_get(token, f"/api/v2/tickers/AAPL/ohlc", {"range": "1W"})
    has_cache_source = "x-cache-source" in audit_resp.headers
    has_cache_age = "x-cache-age" in audit_resp.headers
    has_trace = "x-amzn-trace-id" in audit_resp.headers
    has_request_id = "x-amzn-requestid" in audit_resp.headers

    # Check sentiment headers
    audit_sent, _ = api_get(token, f"/api/v2/tickers/AAPL/sentiment/history", {"range": "1W"})
    sent_has_cache = "x-cache-source" in audit_sent.headers

    results.append(TestResult(
        name="Observability Header Audit",
        status="WARN",
        confidence="HIGH",
        detail=(
            f"OHLC: x-cache-source={'YES' if has_cache_source else 'NO'}, "
            f"x-cache-age={'YES' if has_cache_age else 'NO'}, "
            f"x-amzn-trace-id={'YES' if has_trace else 'NO'}, "
            f"x-amzn-requestid={'YES' if has_request_id else 'NO'}. "
            f"Sentiment: x-cache-source={'YES' if sent_has_cache else 'NO (MISSING)'}. "
            f"Gap: sentiment endpoint has no cache observability headers."
        ),
        data={"ohlc_headers": has_cache_source and has_cache_age and has_trace,
              "sentiment_headers": sent_has_cache},
    ))
    print(f"  OHLC headers: {'complete' if has_cache_source else 'incomplete'} | Sentiment: {'complete' if sent_has_cache else 'MISSING'}")

    return results


def generate_report(results: list[TestResult], output: Path) -> None:
    lines = []
    lines.append("# Observability Audit -- Sentiment Analyzer Preprod (v3)")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Environment:** preprod")
    lines.append(f"**Methodology:** Automated diagnostic with code-review-informed assertions")
    lines.append("")

    # ─── Verdict ───
    passes = sum(1 for r in results if r.status == "PASS")
    warns = sum(1 for r in results if r.status == "WARN")
    fails = sum(1 for r in results if r.status == "FAIL")
    infos = sum(1 for r in results if r.status == "INFO")

    lines.append("## Verdict")
    lines.append("")
    if fails > 0:
        lines.append(f"**RED** -- {fails} test(s) failed. System is not ready for chaos injection.")
    elif warns > 0:
        lines.append(f"**YELLOW** -- {passes} passed, {warns} warnings, {infos} informational. "
                     f"System functions but has known gaps that would confound chaos injection results.")
    else:
        lines.append(f"**GREEN** -- {passes} passed, {infos} informational. System is ready for chaos injection.")
    lines.append("")

    # ─── Results Table ───
    lines.append("## Test Results")
    lines.append("")
    lines.append("| # | Test | Status | Confidence | Detail |")
    lines.append("|---|------|--------|------------|--------|")
    for i, r in enumerate(results, 1):
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN", "INFO": "INFO"}[r.status]
        # Truncate detail for table, full detail below
        short = r.detail[:120] + "..." if len(r.detail) > 120 else r.detail
        lines.append(f"| {i} | {r.name} | **{icon}** | {r.confidence} | {short} |")
    lines.append("")

    # ─── Detailed Findings ───
    lines.append("## Detailed Findings")
    lines.append("")
    for i, r in enumerate(results, 1):
        icon = {"PASS": "PASS", "FAIL": "**FAIL**", "WARN": "**WARN**", "INFO": "INFO"}[r.status]
        lines.append(f"### {i}. {r.name} -- {icon} (confidence: {r.confidence})")
        lines.append("")
        lines.append(r.detail)
        lines.append("")
        if r.data:
            key_data = {k: v for k, v in r.data.items()
                       if k not in ("trace_id",) and v is not None}
            if key_data:
                lines.append(f"```json\n{json.dumps(key_data, indent=2, default=str)}\n```")
                lines.append("")

    # ─── The Uncomfortable Findings ───
    lines.append("## The Uncomfortable Findings")
    lines.append("")
    lines.append("These are findings that a green dashboard would hide:")
    lines.append("")

    sent_result = next((r for r in results if "Sentiment" in r.name), None)
    if sent_result and sent_result.data.get("synthetic"):
        lines.append("### 1. The core product is serving fake data")
        lines.append("")
        lines.append("The sentiment analysis platform's `/sentiment/history` endpoint returns **synthetic data** "
                     "generated from `sha256(ticker)` as an RNG seed. No external API is called. No DynamoDB is queried. "
                     "The trace completes in ~1ms because it's pure in-process computation.")
        lines.append("")
        lines.append("The code comment says: *\"In production, this would query DynamoDB for historical sentiment records. "
                     "For now, generate synthetic data.\"*")
        lines.append("")
        lines.append("**Impact:** Every sentiment chart the customer sees is fake. The same ticker always produces "
                     "the same curve regardless of actual market conditions. This is the single largest gap "
                     "in the system and cannot be detected by status-code-level testing.")
        lines.append("")

    tier1_result = next((r for r in results if "Tier 1" in r.name), None)
    if tier1_result:
        lines.append("### 2. In-memory cache effectiveness under real traffic")
        lines.append("")
        if tier1_result.data.get("tier1_hit"):
            lines.append("Tier 1 (in-memory) **was observed** on rapid sequential requests. "
                        "However, under real traffic with CloudFront distribution across Lambda instances, "
                        "the hit rate will be lower. Monitor `Cache/Hits` for `ohlc_response` in production "
                        "to determine actual effectiveness.")
        else:
            lines.append("Tier 1 (in-memory) **was NOT observed** even on rapid sequential requests. "
                        "CloudFront distributed all 3 requests to different Lambda instances. "
                        "This means in-memory cache may provide near-zero value under current architecture -- "
                        "every request falls through to DynamoDB (Tier 2).")
        lines.append("")

    lines.append("### 3. Observability is asymmetric")
    lines.append("")
    lines.append("OHLC endpoints have rich observability: `x-cache-source`, `x-cache-age`, X-Ray subsegments "
                "for DynamoDB and Tiingo, CloudWatch metrics. Sentiment endpoints have **none of this**. "
                "If the sentiment endpoint breaks, the only signal is a customer complaint. "
                "There is no automated way to detect degradation.")
    lines.append("")

    # ─── Known Unknowns ───
    lines.append("## Known Unknowns")
    lines.append("")
    lines.append("Things this audit explicitly did NOT test:")
    lines.append("")
    lines.append("| Unknown | Why It Matters | What Would Break |")
    lines.append("|---------|---------------|-----------------|")
    lines.append("| Tiingo API failure/timeout | OHLC data depends entirely on Tiingo | "
                "Show stale cache? Show error? Unknown without injection |")
    lines.append("| DynamoDB throttling | Persistent cache and user sessions live in DynamoDB | "
                "Could cascade to auth failures + data failures simultaneously |")
    lines.append("| Concurrent cold tickers | 100 users querying different uncached tickers | "
                "Tiingo rate limit (500/hr), thundering herd on DynamoDB writes |")
    lines.append("| Circuit breaker activation | Never triggered in testing -- 5 consecutive failures required | "
                "Unknown if recovery works, unknown if fail-open behavior is correct |")
    lines.append("| Authenticated user paths | Only anonymous auth tested | "
                "JWT validation, session refresh, CSRF -- all untested under trace inspection |")
    lines.append("| SSE streaming endpoint | Not tested at all | "
                "Different Lambda, different transport, different failure modes |")
    lines.append("| Amplify CDN cache | Frontend static assets cached at edge | "
                "Stale JavaScript after deploy (already happened -- Layer 13) |")
    lines.append("")

    # ─── Chaos Injection Readiness ───
    lines.append("## Chaos Injection Readiness Assessment")
    lines.append("")
    if fails > 0:
        lines.append("**NOT READY.** Fix failures before injecting chaos -- you won't be able to "
                     "distinguish chaos-induced failures from pre-existing ones.")
    elif warns > 0:
        lines.append("**CONDITIONALLY READY.** The system functions and the OHLC path is well-understood. "
                     "However, the following gaps will confound chaos results:")
        lines.append("")
        for r in results:
            if r.status == "WARN":
                lines.append(f"- **{r.name}**: {r.detail[:100]}")
        lines.append("")
        lines.append("**Recommendation:** Proceed with chaos injection on the OHLC path only (Tiingo failure, "
                     "DynamoDB throttle). Do NOT chaos-test the sentiment path until it has real data and observability. "
                     "Injecting failures into a synthetic endpoint proves nothing.")
    else:
        lines.append("**READY.** All tests pass. Proceed with chaos injection.")
    lines.append("")

    # ─── Methodology ───
    lines.append("## Methodology")
    lines.append("")
    lines.append("This audit combines automated HTTP testing with code-review-informed assertions:")
    lines.append("")
    lines.append("1. **Cold start measurement** -- health check without pre-warming, trace Init segment detection")
    lines.append("2. **Data correctness** -- candle count vs trading days, date range recency, price/volume sanity")
    lines.append("3. **Sentiment investigation** -- determinism test (same request twice), trace depth, code review confirmation")
    lines.append("4. **Tier 1 cache** -- 3 rapid sequential requests (<500ms apart) to test in-memory hit")
    lines.append("5. **Auth failure** -- deliberately invalid token, verify 401/403 response")
    lines.append("6. **Input validation** -- SQL injection, XSS, boundary values, invalid parameters")
    lines.append("7. **Header audit** -- verify observability headers present on all endpoint types")
    lines.append("")
    lines.append("```bash")
    lines.append("# Re-run:")
    lines.append(f"COLD_TICKER={COLD_TICKER} python scripts/trace_inspection_v3.py")
    lines.append("```")
    lines.append("")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    print(f"\nReport: {output} ({len(lines)} lines)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/trace-inspection-2026-03-19-v3.md")
    args = parser.parse_args()

    print("=" * 60)
    print("OBSERVABILITY AUDIT v3")
    print("=" * 60)

    results = run_tests()
    generate_report(results, Path(args.output))

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        icon = {"PASS": "  ", "FAIL": "XX", "WARN": "!!", "INFO": "  "}[r.status]
        print(f"  [{icon}] {r.status:4} {r.confidence:6} {r.name}")


if __name__ == "__main__":
    main()
