#!/usr/bin/env python3
# Target: backend Lambda CloudWatch log groups (not either dashboard UI)
"""On-demand FR-008 verifier + SC-006 refresh-classification drill (feature 001).

Drives the dashboard Lambda (alias-qualified, direct invoke) through all
three session-refresh outcomes, then asserts the classification INFO lines
and the C-8 self-test line are queryable in CloudWatch. Exits non-zero on
any missing line — run pre-deploy it MUST fail (lines are dark), post-deploy
it MUST pass; that asymmetry is the discrimination proof.

Usage:
    AWS_REGION=us-east-1 .venv/bin/python scripts/verify-log-visibility.py

The refresh.success probe needs NO secret and NO real login (AR#3): an
anonymous session mint returns an `anon.` refresh cookie; replaying it to
/refresh takes the anonymous branch to the refresh.success log line.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("AWS_REGION", "us-east-1")

import boto3

from tests.e2e.helpers.lambda_invoke_transport import (
    LambdaInvokeTransport,
    _build_apigw_rest_event,
)

LOG_GROUP = "/aws/lambda/preprod-sentiment-dashboard"
SELF_TEST_MESSAGE = "logging configured: root INFO visibility active (feature 001)"
EXPECTED_LINES = (
    "refresh.cookie_absent",
    "refresh.rejected",
    "refresh.success",
    SELF_TEST_MESSAGE,
)
POLL_TIMEOUT_S = 120
POLL_INTERVAL_S = 10


def _mint_anon_refresh_cookie(transport: LambdaInvokeTransport) -> str:
    """POST /auth/anonymous and pull the anon refresh cookie from the raw payload.

    Raw invoke (not transport.invoke): the flattened header dict keeps only
    the FIRST Set-Cookie value and the response sets several cookies.
    """
    event = _build_apigw_rest_event("POST", "/api/v2/auth/anonymous", None, None, None)
    raw = transport._client.invoke(
        FunctionName=transport.function_name,
        Qualifier=transport.qualifier,
        Payload=json.dumps(event).encode(),
    )
    payload = json.loads(raw["Payload"].read())
    set_cookies: list[str] = []
    for key, values in (payload.get("multiValueHeaders") or {}).items():
        if key.lower() == "set-cookie" and isinstance(values, list):
            set_cookies.extend(str(v) for v in values)
    for cookie in set_cookies:
        match = re.match(r"refresh_token=([^;]+)", cookie)
        if match and match.group(1).startswith("anon."):
            return match.group(1)
    print(
        f"FATAL: no anon refresh_token cookie in /auth/anonymous response "
        f"(status {payload.get('statusCode')}, cookies seen: {len(set_cookies)})"
    )
    sys.exit(2)


def main() -> int:
    transport = LambdaInvokeTransport()
    window_start_ms = int(time.time() * 1000) - 30_000

    print("probe (a): POST /refresh, no cookie -> expect refresh.cookie_absent")
    r_absent = transport.invoke("POST", "/api/v2/auth/refresh")
    print(f"  -> {r_absent.status_code}")

    print("probe (b): POST /refresh, garbage cookie -> expect refresh.rejected")
    r_rejected = transport.invoke(
        "POST",
        "/api/v2/auth/refresh",
        headers={"Cookie": "refresh_token=garbage-not-a-real-token"},
    )
    print(f"  -> {r_rejected.status_code}")

    print("probe (c): anon mint -> replay cookie -> expect refresh.success")
    anon_cookie = _mint_anon_refresh_cookie(transport)
    r_success = transport.invoke(
        "POST",
        "/api/v2/auth/refresh",
        headers={"Cookie": f"refresh_token={anon_cookie}"},
    )
    print(f"  -> {r_success.status_code} (must be 2xx for the branch to log success)")

    logs = boto3.client("logs", region_name=os.environ["AWS_REGION"])
    missing = set(EXPECTED_LINES)
    deadline = time.time() + POLL_TIMEOUT_S
    while missing and time.time() < deadline:
        time.sleep(POLL_INTERVAL_S)
        for line in list(missing):
            resp = logs.filter_log_events(
                logGroupName=LOG_GROUP,
                startTime=window_start_ms,
                filterPattern=f'"{line}"',
                limit=1,
            )
            if resp.get("events"):
                print(f"  FOUND: {line}")
                missing.discard(line)

    if missing:
        print("\nFAIL — lines not found in CloudWatch (dark or not deployed):")
        for line in sorted(missing):
            print(f"  MISSING: {line}")
        return 1
    print(
        "\nPASS — all three refresh classifications + C-8 self-test visible (SC-006)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
