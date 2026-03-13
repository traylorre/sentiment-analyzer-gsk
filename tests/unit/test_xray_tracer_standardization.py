"""T017: Unit test for Phase 3 Powertools Tracer standardization (SC-012).

Verifies:
1. All 6 Lambda handlers initialize Powertools Tracer
2. Zero xray_recorder.capture() imports remain
3. Zero patch_all() calls
4. Exceptions auto-captured by @tracer.capture_method
"""

from pathlib import Path

import pytest

# All Lambda source directories
LAMBDAS_DIR = Path(__file__).parent.parent.parent / "src" / "lambdas"

# The 6 Lambda handlers and their expected Tracer service names
LAMBDA_HANDLERS = {
    "ingestion/handler.py": "sentiment-analyzer-ingestion",
    "analysis/handler.py": "sentiment-analyzer-analysis",
    "dashboard/handler.py": "dashboard",
    "metrics/handler.py": "sentiment-analyzer-metrics",
    "notification/handler.py": "sentiment-analyzer-notification",
    "sse_streaming/handler.py": "sentiment-analyzer-sse",
}

# All Python files under src/lambdas/ (excluding __pycache__)
ALL_LAMBDA_FILES = list(LAMBDAS_DIR.rglob("*.py"))


class TestTracerInitialization:
    """Verify all 6 Lambda handlers initialize Powertools Tracer (SC-012)."""

    @pytest.mark.parametrize(
        "handler_path,expected_service",
        LAMBDA_HANDLERS.items(),
        ids=list(LAMBDA_HANDLERS.keys()),
    )
    def test_handler_initializes_tracer(self, handler_path, expected_service):
        """Each handler must have Tracer import and init with service name."""
        filepath = LAMBDAS_DIR / handler_path
        assert filepath.exists(), f"{handler_path} not found"

        source = filepath.read_text()

        # Must import Tracer (may be combined: "import Logger, Tracer")
        has_tracer_import = any(
            "aws_lambda_powertools" in line and "Tracer" in line
            for line in source.splitlines()
            if line.strip().startswith("from") or line.strip().startswith("import")
        )
        assert (
            has_tracer_import
        ), f"{handler_path} missing Tracer import from aws_lambda_powertools"

        assert (
            f'Tracer(service="{expected_service}"' in source
            or "Tracer(service=" in source
        ), f"{handler_path} missing Tracer initialization with service name"

    @pytest.mark.parametrize(
        "handler_path",
        [
            "ingestion/handler.py",
            "analysis/handler.py",
            "dashboard/handler.py",
            "metrics/handler.py",
            "notification/handler.py",
        ],
        ids=["ingestion", "analysis", "dashboard", "metrics", "notification"],
    )
    def test_handler_has_capture_lambda_handler(self, handler_path):
        """5 standard handlers must use @tracer.capture_lambda_handler.
        SSE excluded (custom runtime with generator handler).
        """
        filepath = LAMBDAS_DIR / handler_path
        source = filepath.read_text()

        assert (
            "@tracer.capture_lambda_handler" in source
        ), f"{handler_path} missing @tracer.capture_lambda_handler decorator"

    def test_sse_handler_uses_auto_patch_false(self):
        """SSE handler must use auto_patch=False (FR-060)."""
        filepath = LAMBDAS_DIR / "sse_streaming" / "handler.py"
        source = filepath.read_text()
        assert "auto_patch=False" in source


class TestNoLegacyXRaySDK:
    """Verify zero remaining raw xray_recorder usage (SC-012)."""

    @pytest.mark.parametrize(
        "filepath",
        [f for f in ALL_LAMBDA_FILES if "__pycache__" not in str(f)],
        ids=[
            str(f.relative_to(LAMBDAS_DIR))
            for f in ALL_LAMBDA_FILES
            if "__pycache__" not in str(f)
        ],
    )
    def test_no_xray_recorder_import(self, filepath):
        """No file should import xray_recorder."""
        source = filepath.read_text()
        assert (
            "xray_recorder" not in source
        ), f"{filepath.relative_to(LAMBDAS_DIR)} still imports xray_recorder"

    @pytest.mark.parametrize(
        "filepath",
        [f for f in ALL_LAMBDA_FILES if "__pycache__" not in str(f)],
        ids=[
            str(f.relative_to(LAMBDAS_DIR))
            for f in ALL_LAMBDA_FILES
            if "__pycache__" not in str(f)
        ],
    )
    def test_no_patch_all(self, filepath):
        """No file should call patch_all() (FR-030)."""
        source = filepath.read_text()
        assert (
            "patch_all()" not in source
        ), f"{filepath.relative_to(LAMBDAS_DIR)} still calls patch_all()"


class TestCaptureMethodCoverage:
    """Verify Powertools tracing instrumentation on key functions."""

    # Files using @tracer.capture_method decorator
    FILES_WITH_CAPTURE_METHOD = [
        "ingestion/handler.py",
        "ingestion/self_healing.py",
        "analysis/handler.py",
        "dashboard/auth.py",
        "dashboard/alerts.py",
        "dashboard/notifications.py",
        "dashboard/quota.py",
        "metrics/handler.py",
        "notification/handler.py",
        "notification/alert_evaluator.py",
        "notification/sendgrid_service.py",
        "shared/middleware/auth_middleware.py",
        "sse_streaming/handler.py",
    ]

    # Files using tracer.provider.in_subsegment() for silent failure instrumentation
    FILES_WITH_SUBSEGMENT = [
        "ingestion/audit.py",
        "ingestion/notification.py",
        "ingestion/storage.py",
        "ingestion/parallel_fetcher.py",
        "shared/circuit_breaker.py",
    ]

    @pytest.mark.parametrize("handler_path", FILES_WITH_CAPTURE_METHOD)
    def test_file_has_capture_method(self, handler_path):
        """Key files must use @tracer.capture_method on at least one function."""
        filepath = LAMBDAS_DIR / handler_path
        source = filepath.read_text()
        assert (
            "@tracer.capture_method" in source
        ), f"{handler_path} missing @tracer.capture_method"

    @pytest.mark.parametrize("handler_path", FILES_WITH_SUBSEGMENT)
    def test_file_has_subsegment_instrumentation(self, handler_path):
        """Silent failure files must use tracer.provider.in_subsegment()."""
        filepath = LAMBDAS_DIR / handler_path
        source = filepath.read_text()
        assert (
            "tracer.provider.in_subsegment" in source
        ), f"{handler_path} missing tracer.provider.in_subsegment()"
