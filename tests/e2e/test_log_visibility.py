# Target: Infrastructure (backend Lambda CloudWatch log groups, not either dashboard UI)
"""FR-008 preprod E2E: dark-line evidence per function (feature 001).

Each assertion targets a line that CANNOT appear pre-deploy:
- dashboard: refresh.* classification lines (un-leveled stdlib logger)
- ingestion: storage.py "Storage operation complete" (dark module INFO)
- analysis: sentiment.py dark module INFO
- metrics + canary: the C-8 self-test line (their ONLY discriminating line)
- notification: digest_service dark INFO on a synthetic empty-digest invoke

AR#3 flake guard: C-8 emits once per COLD START, so C-8 queries window from
the function's LastModified timestamp, never "now minus N minutes".
"""

import json
import os
import time
from datetime import UTC, datetime

import boto3
import pytest

pytestmark = pytest.mark.preprod

REGION = os.environ.get("AWS_REGION", "us-east-1")
ENV = os.environ.get("AWS_ENV", "preprod")
SELF_TEST_MESSAGE = "logging configured: root INFO visibility active (feature 001)"
# Kept tight: the preprod integration job has a 720s budget for the WHOLE
# suite, and this file's assertions poll serially — 180s each timed the job
# out on deploy run 30188812074.
POLL_TIMEOUT_S = 60
POLL_INTERVAL_S = 10


def _log_group(fn: str) -> str:
    return f"/aws/lambda/{ENV}-sentiment-{fn}"


def _function_name(fn: str) -> str:
    return f"{ENV}-sentiment-{fn}"


def _last_modified_ms(lambda_client, fn: str) -> int:
    cfg = lambda_client.get_function_configuration(FunctionName=_function_name(fn))
    dt = datetime.strptime(cfg["LastModified"], "%Y-%m-%dT%H:%M:%S.%f%z")
    return int(dt.timestamp() * 1000)


def _find_line(logs_client, group: str, pattern: str, start_ms: int) -> bool:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        resp = logs_client.filter_log_events(
            logGroupName=group,
            startTime=start_ms,
            filterPattern=f'"{pattern}"',
            limit=1,
        )
        if resp.get("events"):
            return True
        time.sleep(POLL_INTERVAL_S)
    return False


@pytest.fixture(scope="module")
def logs_client():
    return boto3.client("logs", region_name=REGION)


@pytest.fixture(scope="module")
def lambda_client():
    return boto3.client("lambda", region_name=REGION)


class TestSelfTestLinePerColdStart:
    """C-8 probe: the only discriminating evidence for metrics and canary.

    HARD LESSON (metrics, 2026-07-26..29): C-8 emits during handler import
    BEFORE later imports/constructions can fail — the metrics function
    crash-looped for 3 days on Tracer()'s lazy aws_xray_sdk import while
    this test's C-8 assertion passed. C-8 proves the LOGGING fix only;
    function health needs its own probe (below).
    """

    @pytest.mark.parametrize("fn", ["metrics", "canary"])
    def test_self_test_line_since_deploy(self, logs_client, lambda_client, fn):
        start_ms = _last_modified_ms(lambda_client, fn)
        assert _find_line(logs_client, _log_group(fn), SELF_TEST_MESSAGE, start_ms), (
            f"{fn}: C-8 self-test line absent since LastModified — root-level "
            "fix not live (or no cold start yet in window)"
        )

    def test_metrics_function_actually_healthy(self, lambda_client):
        """Synthetic invoke must complete without FunctionError — catches the
        packaging-onion class (ImportModuleError) that C-8 cannot see."""
        resp = lambda_client.invoke(FunctionName=_function_name("metrics"))
        assert resp.get("FunctionError") is None, (
            "metrics invoke errored — packaging/import regression "
            "(C-8 alone cannot detect this)"
        )


class TestDashboardRefreshClassification:
    """SC-006 drill — asserted via scripts/verify-log-visibility.py logic."""

    def test_refresh_lines_visible(self, logs_client, lambda_client):
        import subprocess
        import sys
        from pathlib import Path

        script = (
            Path(__file__).resolve().parents[2] / "scripts" / "verify-log-visibility.py"
        )
        # S603: argv is sys.executable + a repo-fixed script path — no
        # untrusted input reaches the subprocess.
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"verify-log-visibility failed:\n{result.stdout}\n{result.stderr}"
        )


class TestNotificationDigestDarkLines:
    def test_synthetic_digest_invoke_and_c8_evidence(self, logs_client, lambda_client):
        """Deploy-run-30191660741 correction: the planned digest_service dark
        lines are UNREACHABLE on preprod today — the digest user query fails
        (Card E), so get_users_for_digest raises before either INFO line, and
        the completion line that DOES emit (handler.py:261 "Daily digest
        processing complete") is the ENTRYPOINT logger — visible pre-fix,
        zero discriminating power. Until Card E lands, notification's honest
        FR-008 evidence is the C-8 self-test line windowed from LastModified
        (same class as metrics/canary), plus a healthy 200 from the synthetic
        invoke proving the import chain (the packaging onion) is closed.
        """
        resp = lambda_client.invoke(
            FunctionName=_function_name("notification"),
            Payload=json.dumps({"notification_type": "digest"}).encode(),
        )
        assert resp.get("FunctionError") is None, (
            "notification invoke errored — packaging/import regression"
        )
        start_ms = _last_modified_ms(lambda_client, "notification")
        assert _find_line(
            logs_client, _log_group("notification"), SELF_TEST_MESSAGE, start_ms
        ), "notification: C-8 self-test line absent since LastModified"


class TestScheduledFunctionsDarkModuleLines:
    """Ingestion/analysis emit dark module INFO on every real cycle."""

    def test_ingestion_storage_line(self, logs_client, lambda_client):
        # Quiet-period tolerant: a weekend/closed-market cycle can collect
        # zero items so storage.py never logs; the C-8 line since deploy has
        # the same discriminating power (root fix live in this function).
        start_ms = int((datetime.now(UTC).timestamp() - 2 * 3600) * 1000)
        found = _find_line(
            logs_client, _log_group("ingestion"), "Storage operation complete", start_ms
        ) or _find_line(
            logs_client,
            _log_group("ingestion"),
            SELF_TEST_MESSAGE,
            _last_modified_ms(lambda_client, "ingestion"),
        )
        assert found, "ingestion: no dark INFO (storage line or C-8) since deploy"

    def test_analysis_sentiment_line(self, logs_client, lambda_client):
        # Analysis runs on ingestion notifications; window from last deploy to
        # tolerate quiet market periods, and accept the C-8 line as fallback
        # evidence (same discriminating power).
        start_ms = _last_modified_ms(lambda_client, "analysis")
        found = _find_line(
            logs_client, _log_group("analysis"), "Sentiment analysis", start_ms
        ) or _find_line(
            logs_client, _log_group("analysis"), SELF_TEST_MESSAGE, start_ms
        )
        assert found, "analysis: no dark INFO (module line or C-8) since deploy"
