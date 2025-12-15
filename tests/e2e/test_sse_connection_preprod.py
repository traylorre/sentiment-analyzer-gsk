# E2E Tests: SSE Connection Health (Preprod)
#
# Validates that SSE Lambda is running correctly and dashboard can connect.
# These tests catch deployment issues like:
# - Missing Python package __init__.py files (fix(128))
# - Lambda Runtime.ExitError on startup
# - Content-Type header mismatches
#
# See: specs/128-fix-sse-lambda-import/

import os

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.preprod]

# Get dashboard URL from environment (set by CI workflow)
PREPROD_DASHBOARD_URL = os.environ.get("PREPROD_DASHBOARD_URL", "")


@pytest.fixture
def dashboard_url() -> str:
    """Get preprod dashboard URL from environment."""
    if not PREPROD_DASHBOARD_URL:
        pytest.skip("PREPROD_DASHBOARD_URL not set")
    return PREPROD_DASHBOARD_URL.rstrip("/")


class TestSSEConnectionHealth:
    """Tests for SSE Lambda connection health.

    These tests verify the SSE Lambda starts successfully and can serve streams.
    Catches deployment-time issues that cause dashboard "Disconnected" status.
    """

    @pytest.mark.asyncio
    async def test_sse_lambda_no_runtime_error(self, dashboard_url: str) -> None:
        """T128a: Verify SSE Lambda starts without Runtime.ExitError.

        Given: SSE Lambda is deployed
        When: Connecting to /api/v2/stream
        Then: Response does NOT contain Runtime.ExitError

        This catches the exact error from fix(128): Missing __init__.py files
        caused Lambda to crash on import, returning Runtime.ExitError JSON.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Use stream to avoid waiting for full response
            async with client.stream(
                "GET", f"{dashboard_url}/api/v2/stream"
            ) as response:
                # Read just enough to check for error
                content = b""
                async for chunk in response.aiter_bytes():
                    content += chunk
                    if len(content) > 500:  # Enough to detect error JSON
                        break

                content_str = content.decode("utf-8", errors="ignore")

                # Check for Runtime.ExitError (the exact error from fix(128))
                assert "Runtime.ExitError" not in content_str, (
                    f"SSE Lambda crashed with Runtime.ExitError!\n"
                    f"This usually means missing __init__.py files in Docker image.\n"
                    f"Response: {content_str[:200]}"
                )

                # Check for other Lambda errors
                assert (
                    "errorType" not in content_str
                ), f"SSE Lambda returned error response: {content_str[:200]}"

    @pytest.mark.asyncio
    async def test_sse_stream_returns_200(self, dashboard_url: str) -> None:
        """T128b: Verify SSE stream returns HTTP 200.

        Given: SSE Lambda is deployed and healthy
        When: Connecting to /api/v2/stream
        Then: HTTP status is 200

        Dashboard shows "Disconnected" if this fails.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream(
                "GET", f"{dashboard_url}/api/v2/stream"
            ) as response:
                assert response.status_code == 200, (
                    f"Expected 200, got {response.status_code}. "
                    f"Dashboard will show 'Disconnected' status."
                )

    @pytest.mark.asyncio
    async def test_sse_content_type_is_event_stream(self, dashboard_url: str) -> None:
        """T128c: Verify SSE Content-Type for EventSource compatibility.

        Given: SSE Lambda is deployed
        When: Connecting to /api/v2/stream
        Then: Content-Type contains 'event-stream' or 'stream'

        EventSource API requires text/event-stream for proper connection.
        Note: Lambda Function URLs may return application/octet-stream,
        but CloudFront should preserve the original Content-Type.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream(
                "GET", f"{dashboard_url}/api/v2/stream"
            ) as response:
                content_type = response.headers.get("content-type", "")

                # Accept text/event-stream (correct) or octet-stream (Lambda URL quirk)
                valid_types = ["text/event-stream", "application/octet-stream"]
                assert any(t in content_type for t in valid_types), (
                    f"Expected event-stream content type, got: {content_type}. "
                    f"Browser EventSource may fail to connect."
                )

    @pytest.mark.asyncio
    async def test_sse_receives_heartbeat_event(self, dashboard_url: str) -> None:
        """T128d: Verify SSE stream sends heartbeat events.

        Given: SSE Lambda is healthy
        When: Connected to /api/v2/stream for 5 seconds
        Then: At least one heartbeat or metrics event is received

        Dashboard uses heartbeats to show "Connected" status indicator.
        """
        async with httpx.AsyncClient(timeout=35.0) as client:
            events_received = []

            try:
                async with client.stream(
                    "GET", f"{dashboard_url}/api/v2/stream"
                ) as response:
                    assert response.status_code == 200

                    # Read stream for up to 5 seconds
                    import asyncio

                    async def read_events():
                        buffer = ""
                        async for chunk in response.aiter_text():
                            buffer += chunk
                            # Parse SSE events (format: "event: type\ndata: ...\n\n")
                            while "\n\n" in buffer:
                                event_text, buffer = buffer.split("\n\n", 1)
                                if event_text.strip():
                                    events_received.append(event_text)
                                    # Exit early if we got an event
                                    if len(events_received) >= 1:
                                        return

                    # Wait max 5 seconds for an event
                    await asyncio.wait_for(read_events(), timeout=5.0)

            except TimeoutError:
                pass  # Expected - SSE streams don't end

            assert len(events_received) >= 1, (
                "No SSE events received within 5 seconds. "
                "Dashboard will show 'Connecting...' indefinitely. "
                "Check Lambda logs for errors."
            )


class TestDashboardConnectionIndicator:
    """Tests that validate dashboard can show "Connected" status.

    These are higher-level tests that check the full connection flow
    that the Interview Dashboard uses.
    """

    @pytest.mark.asyncio
    async def test_dashboard_sse_connection_flow(self, dashboard_url: str) -> None:
        """T128e: Simulate browser EventSource connection flow.

        Given: Dashboard is loaded
        When: JavaScript creates EventSource to /api/v2/stream
        Then: Connection succeeds with proper headers

        This simulates what app.js connectSSE() does:
        1. new EventSource(`${baseUrl}/api/v2/stream`)
        2. Wait for onopen callback
        3. updateConnectionStatus(true)
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            # EventSource sends these headers
            headers = {
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
            }

            async with client.stream(
                "GET", f"{dashboard_url}/api/v2/stream", headers=headers
            ) as response:
                # Check connection established (equivalent to onopen)
                assert response.status_code == 200, "EventSource onopen would not fire"

                # Read first chunk to verify streaming works
                first_chunk = b""
                async for chunk in response.aiter_bytes():
                    first_chunk = chunk
                    break

                # Should not be an error response
                chunk_str = first_chunk.decode("utf-8", errors="ignore")
                assert (
                    "errorType" not in chunk_str
                ), f"Lambda error would trigger onerror callback: {chunk_str[:100]}"
