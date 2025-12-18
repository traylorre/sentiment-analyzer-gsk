# E2E Tests: SSE Connection Health (Preprod)
#
# Validates that SSE Lambda is running correctly and dashboard can connect.
# These tests catch deployment issues like:
# - Missing Python package __init__.py files (fix(128))
# - Lambda Runtime.ExitError on startup
# - Content-Type header mismatches
#
# See: specs/128-fix-sse-lambda-import/
#
# IMPORTANT: These tests must use SSE_LAMBDA_URL, not PREPROD_DASHBOARD_URL.
# The SSE routes (/api/v2/stream, /api/v2/stream/status) only exist on the
# SSE Lambda, not on the Dashboard Lambda. Using PREPROD_DASHBOARD_URL
# causes 404 errors because the Dashboard Lambda doesn't have these routes.
# Fix: Issue #141 (fix-sse-test-url)

import asyncio
import os

import httpx
import pytest

# Retry configuration for Docker Lambda cold starts (10-20s)
# Docker Lambda containers can take 10-20s to initialize on cold start
MAX_RETRIES = 3
INITIAL_TIMEOUT = 15.0  # Allow for cold start delay
BACKOFF_MULTIPLIER = 2.0  # Double timeout per retry: 15s -> 30s -> 60s

pytestmark = [pytest.mark.e2e, pytest.mark.preprod]

# Get SSE Lambda URL from environment (set by CI workflow)
# SSE routes only exist on the SSE Lambda, not the Dashboard Lambda
SSE_LAMBDA_URL = os.environ.get("SSE_LAMBDA_URL", "")


@pytest.fixture
def sse_lambda_url() -> str:
    """Get SSE Lambda URL from environment.

    The SSE Lambda is a separate function with RESPONSE_STREAM invoke mode
    that handles real-time streaming. SSE routes like /api/v2/stream only
    exist on this Lambda, not on the Dashboard Lambda.
    """
    if not SSE_LAMBDA_URL:
        pytest.skip("SSE_LAMBDA_URL not set")
    return SSE_LAMBDA_URL.rstrip("/")


class TestSSEConnectionHealth:
    """Tests for SSE Lambda connection health.

    These tests verify the SSE Lambda starts successfully and can serve streams.
    Catches deployment-time issues that cause dashboard "Disconnected" status.
    """

    @pytest.mark.asyncio
    async def test_sse_lambda_no_runtime_error(self, sse_lambda_url: str) -> None:
        """T128a: Verify SSE Lambda starts without Runtime.ExitError.

        Given: SSE Lambda is deployed
        When: Connecting to /api/v2/stream
        Then: Response does NOT contain Runtime.ExitError

        This catches the exact error from fix(128): Missing __init__.py files
        caused Lambda to crash on import, returning Runtime.ExitError JSON.

        Note: Uses retry with backoff for Docker Lambda cold starts (10-20s).
        """
        timeout = INITIAL_TIMEOUT
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "GET", f"{sse_lambda_url}/api/v2/stream"
                    ) as response:
                        content = b""
                        async for chunk in response.aiter_bytes():
                            content += chunk
                            if len(content) > 500:
                                break

                        content_str = content.decode("utf-8", errors="ignore")

                        assert "Runtime.ExitError" not in content_str, (
                            f"SSE Lambda crashed with Runtime.ExitError!\n"
                            f"Response: {content_str[:200]}"
                        )

                        assert (
                            "errorType" not in content_str
                        ), f"SSE Lambda returned error: {content_str[:200]}"

                        return  # Success
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0)
                    timeout *= BACKOFF_MULTIPLIER

        raise last_error  # Re-raise after all retries

    @pytest.mark.asyncio
    async def test_sse_stream_returns_200(self, sse_lambda_url: str) -> None:
        """T128b: Verify SSE stream returns HTTP 200.

        Given: SSE Lambda is deployed and healthy
        When: Connecting to /api/v2/stream
        Then: HTTP status is 200

        Dashboard shows "Disconnected" if this fails.
        Note: Uses retry with backoff for Docker Lambda cold starts (10-20s).
        """
        timeout = INITIAL_TIMEOUT
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "GET", f"{sse_lambda_url}/api/v2/stream"
                    ) as response:
                        assert response.status_code == 200, (
                            f"Expected 200, got {response.status_code}. "
                            f"Dashboard will show 'Disconnected' status."
                        )
                        return  # Success
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0)
                    timeout *= BACKOFF_MULTIPLIER

        raise last_error

    @pytest.mark.asyncio
    async def test_sse_content_type_is_event_stream(self, sse_lambda_url: str) -> None:
        """T128c: Verify SSE Content-Type for EventSource compatibility.

        Given: SSE Lambda is deployed
        When: Connecting to /api/v2/stream
        Then: Content-Type contains 'event-stream' or 'stream'

        EventSource API requires text/event-stream for proper connection.
        Note: Lambda Function URLs may return application/octet-stream,
        but CloudFront should preserve the original Content-Type.
        """
        timeout = INITIAL_TIMEOUT
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "GET", f"{sse_lambda_url}/api/v2/stream"
                    ) as response:
                        content_type = response.headers.get("content-type", "")

                        valid_types = ["text/event-stream", "application/octet-stream"]
                        assert any(
                            t in content_type for t in valid_types
                        ), f"Expected event-stream content type, got: {content_type}."
                        return  # Success
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0)
                    timeout *= BACKOFF_MULTIPLIER

        raise last_error

    @pytest.mark.asyncio
    async def test_sse_receives_heartbeat_event(self, sse_lambda_url: str) -> None:
        """T128d: Verify SSE stream sends heartbeat events.

        Given: SSE Lambda is healthy
        When: Connected to /api/v2/stream for 5 seconds
        Then: At least one heartbeat or metrics event is received

        Dashboard uses heartbeats to show "Connected" status indicator.
        Note: Uses 45s total timeout for cold start + heartbeat wait.
        """
        # Higher timeout to handle cold start (20s) + heartbeat wait (5s) + buffer
        async with httpx.AsyncClient(timeout=45.0) as client:
            events_received = []

            try:
                async with client.stream(
                    "GET", f"{sse_lambda_url}/api/v2/stream"
                ) as response:
                    assert response.status_code == 200

                    async def read_events():
                        buffer = ""
                        async for chunk in response.aiter_text():
                            buffer += chunk
                            while "\n\n" in buffer:
                                event_text, buffer = buffer.split("\n\n", 1)
                                if event_text.strip():
                                    events_received.append(event_text)
                                    if len(events_received) >= 1:
                                        return

                    await asyncio.wait_for(read_events(), timeout=10.0)

            except TimeoutError:
                pass

            assert len(events_received) >= 1, (
                "No SSE events received within 10 seconds. "
                "Check Lambda logs for errors."
            )


class TestDashboardConnectionIndicator:
    """Tests that validate dashboard can show "Connected" status.

    These are higher-level tests that check the full connection flow
    that the Interview Dashboard uses.
    """

    @pytest.mark.asyncio
    async def test_dashboard_sse_connection_flow(self, sse_lambda_url: str) -> None:
        """T128e: Simulate browser EventSource connection flow.

        Given: Dashboard is loaded
        When: JavaScript creates EventSource to /api/v2/stream
        Then: Connection succeeds with proper headers

        This simulates what app.js connectSSE() does:
        1. new EventSource(`${baseUrl}/api/v2/stream`)
        2. Wait for onopen callback
        3. updateConnectionStatus(true)

        Note: Uses retry with backoff for Docker Lambda cold starts (10-20s).
        """
        timeout = INITIAL_TIMEOUT
        last_error = None
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "GET", f"{sse_lambda_url}/api/v2/stream", headers=headers
                    ) as response:
                        assert (
                            response.status_code == 200
                        ), "EventSource onopen would not fire"

                        first_chunk = b""
                        async for chunk in response.aiter_bytes():
                            first_chunk = chunk
                            break

                        chunk_str = first_chunk.decode("utf-8", errors="ignore")
                        assert (
                            "errorType" not in chunk_str
                        ), f"Lambda error: {chunk_str[:100]}"
                        return  # Success
            except httpx.ReadTimeout as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0)
                    timeout *= BACKOFF_MULTIPLIER

        raise last_error
