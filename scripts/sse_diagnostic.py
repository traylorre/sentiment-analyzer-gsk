#!/usr/bin/env python3
"""
SSE Diagnostic Tool — Connect to SSE stream and display events.

Usage:
    python scripts/sse_diagnostic.py URL [options]

Examples:
    # Global stream (no auth)
    python scripts/sse_diagnostic.py https://FUNCTION_URL/api/v2/stream

    # Config stream with auth
    python scripts/sse_diagnostic.py https://FUNCTION_URL/api/v2/configurations/ID/stream --token TOKEN

    # Filter by event type and ticker
    python scripts/sse_diagnostic.py URL --event-type sentiment_update --ticker AAPL

    # JSON output for piping
    python scripts/sse_diagnostic.py URL --json | jq '.score'
"""

import argparse
import json
import signal
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime

# ─── SSE Protocol Parser ──────────────────────────────────────────────


def parse_sse_stream(response):
    """Parse SSE protocol from an HTTP streaming response.

    Yields (event_type, data_dict, event_id) tuples.

    SSE format:
        event: {type}
        id: {id}
        retry: {ms}
        data: {json}
        <empty line = dispatch>
    """
    event_type = "message"
    data_buffer = ""
    event_id = None

    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")

        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_part = line[5:].strip()
            data_buffer = data_buffer + data_part if data_buffer else data_part
        elif line.startswith("id:"):
            event_id = line[3:].strip()
        elif line.startswith("retry:"):
            pass  # Acknowledge but don't act on retry hints
        elif line.startswith(":"):
            pass  # SSE comment / keepalive
        elif line == "":
            # Empty line dispatches the event
            if data_buffer:
                try:
                    data_dict = json.loads(data_buffer)
                except json.JSONDecodeError:
                    data_dict = {"raw": data_buffer}
                yield (event_type, data_dict, event_id)
            event_type = "message"
            data_buffer = ""
            event_id = None


# ─── HTTP Connection ──────────────────────────────────────────────────


def connect(url, token=None, user_id=None, last_event_id=None):
    """Connect to SSE endpoint and return streaming response.

    Args:
        url: SSE endpoint URL
        token: Bearer token for config streams
        user_id: User ID header for config streams
        last_event_id: Resume from this event ID

    Returns:
        HTTP response object for streaming reads

    Raises:
        ConnectionError: On auth, limit, or network failures
    """
    req = urllib.request.Request(url)  # noqa: S310
    req.add_header("Accept", "text/event-stream")
    req.add_header("Cache-Control", "no-cache")

    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if user_id:
        req.add_header("X-User-ID", user_id)
    if last_event_id:
        req.add_header("Last-Event-ID", last_event_id)

    try:
        return urllib.request.urlopen(req, timeout=60)  # noqa: S310
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ConnectionError(
                "Authentication required. Use --token TOKEN or --user-id ID "
                "for config-specific streams."
            ) from e
        if e.code == 503:
            retry_after = e.headers.get("Retry-After", "30")
            raise ConnectionError(
                f"Connection limit reached. Retry after {retry_after} seconds."
            ) from e
        raise ConnectionError(f"HTTP {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot connect to {url}: {e.reason}. Check the endpoint is running."
        ) from e


# ─── Event Formatters ─────────────────────────────────────────────────

# ANSI colors for terminal
_COLORS = {
    "heartbeat": "\033[32m",  # green
    "metrics": "\033[33m",  # yellow
    "sentiment_update": "\033[34m",  # blue
    "partial_bucket": "\033[36m",  # cyan
    "deadline": "\033[31m",  # red
}
_ICONS = {
    "heartbeat": "❤",
    "metrics": "📊",
    "sentiment_update": "📈",
    "partial_bucket": "🔄",
    "deadline": "⏰",
}
_RESET = "\033[0m"


def _ts():
    """Current time formatted as [HH:MM:SS]."""
    return datetime.now(UTC).strftime("[%H:%M:%S]")


def format_heartbeat(data):
    """Format heartbeat event."""
    conns = data.get("connections", "?")
    uptime = data.get("uptime_seconds", "?")
    return f"connections={conns} uptime={uptime}s"


def format_metrics(data):
    """Format metrics event."""
    total = data.get("total", "?")
    pos = data.get("positive", 0)
    neu = data.get("neutral", 0)
    neg = data.get("negative", 0)
    rate_h = data.get("rate_last_hour", 0)
    return f"total={total} +{rate_h}/h positive={pos} neutral={neu} negative={neg}"


def format_sentiment_update(data):
    """Format sentiment_update event."""
    ticker = data.get("ticker", "???")
    score = data.get("score", 0)
    label = data.get("label", "unknown")
    source = data.get("source", "unknown")
    confidence = data.get("confidence", "?")
    sign = "+" if score >= 0 else ""
    return f"{ticker} {sign}{score:.4f} {label} ({source}) confidence={confidence}"


def format_partial_bucket(data):
    """Format partial_bucket event."""
    ticker = data.get("ticker", "???")
    resolution = data.get("resolution", "?")
    progress = data.get("progress_pct", 0)
    bucket = data.get("bucket", {})
    o = bucket.get("open", 0)
    h = bucket.get("high", 0)
    lo = bucket.get("low", 0)
    c = bucket.get("close", 0)
    count = bucket.get("count", 0)
    return (
        f"{ticker}#{resolution} {progress:.1f}% "
        f"open={o:.2f} high={h:.2f} low={lo:.2f} close={c:.2f} count={count}"
    )


def format_deadline(data):
    """Format deadline event."""
    reason = data.get("reason", "Lambda timeout approaching")
    return reason


_FORMATTERS = {
    "heartbeat": format_heartbeat,
    "metrics": format_metrics,
    "sentiment_update": format_sentiment_update,
    "partial_bucket": format_partial_bucket,
    "deadline": format_deadline,
}


def format_event(event_type, data):
    """Format an event for human-readable terminal output."""
    formatter = _FORMATTERS.get(event_type)
    if formatter:
        detail = formatter(data)
    else:
        detail = json.dumps(data, separators=(",", ":"))

    color = _COLORS.get(event_type, "")
    icon = _ICONS.get(event_type, "•")
    reset = _RESET if color else ""

    label = event_type.ljust(17)
    return f"{_ts()} {color}{icon} {label}{reset} {detail}"


# ─── Event Filtering ──────────────────────────────────────────────────


def should_display(event_type, data, args):
    """Check if event passes user-specified filters.

    Args:
        event_type: SSE event type string
        data: Parsed event data dict
        args: CLI arguments with event_type and ticker filters

    Returns:
        True if event should be displayed
    """
    if args.event_type and event_type != args.event_type:
        return False

    if args.ticker:
        ticker_upper = args.ticker.upper()
        # Check direct ticker field
        if data.get("ticker", "").upper() == ticker_upper:
            return True
        # Check by_tag dict (metrics events)
        if ticker_upper in {k.upper() for k in data.get("by_tag", {})}:
            return True
        # If event has no ticker field (heartbeat, deadline), pass through
        if "ticker" not in data and "by_tag" not in data:
            return True
        return False

    return True


# ─── Session Statistics ───────────────────────────────────────────────


class SessionStats:
    """Track event counts, duration, and health for session summary."""

    def __init__(self):
        self.start_time = time.monotonic()
        self.event_counts = defaultdict(int)
        self.total_events = 0
        self.last_heartbeat_time = None
        self.max_heartbeat_gap = 0.0
        self.reconnect_count = 0

    def record_event(self, event_type):
        """Record an event occurrence."""
        self.event_counts[event_type] += 1
        self.total_events += 1

        if event_type == "heartbeat":
            now = time.monotonic()
            if self.last_heartbeat_time is not None:
                gap = now - self.last_heartbeat_time
                self.max_heartbeat_gap = max(self.max_heartbeat_gap, gap)
            self.last_heartbeat_time = now

    def summary(self):
        """Generate session summary string."""
        duration = time.monotonic() - self.start_time
        mins, secs = divmod(int(duration), 60)

        lines = [
            "",
            "═══ Session Summary ═══",
            f"Duration:      {mins}m {secs}s",
            f"Total events:  {self.total_events}",
        ]

        if self.event_counts:
            lines.append("By type:")
            for etype, count in sorted(self.event_counts.items()):
                lines.append(f"  {etype}: {count}")

        if self.reconnect_count > 0:
            lines.append(f"Reconnections: {self.reconnect_count}")

        # Health warnings
        if self.max_heartbeat_gap > 60:
            lines.append(
                f"⚠ WARNING: Heartbeat gap detected ({self.max_heartbeat_gap:.0f}s > 60s expected)"
            )

        if self.total_events == 0 and duration > 60:
            lines.append(f"⚠ WARNING: No events received in {duration:.0f}s")

        lines.append("═══════════════════════")
        return "\n".join(lines)


# ─── Main Event Loop ──────────────────────────────────────────────────


def run(args):
    """Main event loop: connect, parse, format, display."""
    stats = SessionStats()
    last_event_id = None
    retries = 0
    max_retries = 3

    # Signal handler for clean Ctrl+C
    def handle_sigint(_signum, _frame):
        print(stats.summary(), file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    print(f"Connecting to {args.url}...", file=sys.stderr)
    if args.event_type:
        print(f"Filter: event_type={args.event_type}", file=sys.stderr)
    if args.ticker:
        print(f"Filter: ticker={args.ticker}", file=sys.stderr)
    print("Press Ctrl+C to stop and show summary.\n", file=sys.stderr)

    while retries <= max_retries:
        try:
            response = connect(
                args.url,
                token=args.token,
                user_id=args.user_id,
                last_event_id=last_event_id,
            )
            retries = 0  # Reset on successful connection

            for event_type, data, event_id in parse_sse_stream(response):
                if event_id:
                    last_event_id = event_id

                stats.record_event(event_type)

                if not should_display(event_type, data, args):
                    continue

                if args.json:
                    # JSONL output mode
                    output = {
                        "event_type": event_type,
                        "event_id": event_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                        "data": data,
                    }
                    print(json.dumps(output, separators=(",", ":")))
                else:
                    print(format_event(event_type, data))

                sys.stdout.flush()

        except ConnectionError as e:
            print(f"\n✗ {e}", file=sys.stderr)
            # Don't retry auth errors
            if "Authentication required" in str(e):
                break
            retries += 1
            stats.reconnect_count += 1
            if retries > max_retries:
                print(
                    f"✗ Max retries ({max_retries}) exceeded. Giving up.",
                    file=sys.stderr,
                )
                break
            delay = 2 ** (retries - 1)  # 1s, 2s, 4s
            print(
                f"  Reconnecting in {delay}s (attempt {retries}/{max_retries})...",
                file=sys.stderr,
            )
            if last_event_id:
                print(f"  Resuming from event ID: {last_event_id}", file=sys.stderr)
            time.sleep(delay)

        except Exception as e:
            print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
            retries += 1
            stats.reconnect_count += 1
            if retries > max_retries:
                break
            delay = 2 ** (retries - 1)
            print(f"  Reconnecting in {delay}s...", file=sys.stderr)
            time.sleep(delay)

    print(stats.summary(), file=sys.stderr)
    return 1 if stats.total_events == 0 else 0


# ─── CLI ──────────────────────────────────────────────────────────────


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SSE Diagnostic Tool — Connect to SSE stream and display events.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://FUNCTION_URL/api/v2/stream
  %(prog)s URL --token TOKEN
  %(prog)s URL --event-type sentiment_update --ticker AAPL
  %(prog)s URL --json | jq '.score'
        """,
    )
    parser.add_argument("url", help="SSE endpoint URL")
    parser.add_argument("--token", help="Bearer token for config-specific streams")
    parser.add_argument("--user-id", help="User ID for config-specific streams")
    parser.add_argument(
        "--event-type",
        choices=[
            "heartbeat",
            "metrics",
            "sentiment_update",
            "partial_bucket",
            "deadline",
        ],
        help="Show only this event type",
    )
    parser.add_argument("--ticker", help="Show only events for this ticker symbol")
    parser.add_argument(
        "--json", action="store_true", help="Output events as JSON lines (JSONL)"
    )

    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
