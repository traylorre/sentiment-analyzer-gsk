# Preprod API Client
#
# HTTP client wrapper for interacting with the preprod API during E2E tests.
# Handles authentication, request tracing, and response validation.

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PreprodAPIClient:
    """Async HTTP client for preprod API interactions.

    Provides a thin wrapper around httpx.AsyncClient with:
    - Base URL configuration from environment
    - Authentication header management
    - Request ID tracking for observability tests
    - Response helpers for common assertions

    Two-Lambda Architecture:
        The sentiment-analyzer uses two Lambda functions with different streaming modes:
        - Dashboard Lambda (BUFFERED): Handles non-streaming requests like /api/v2/configurations
        - SSE Lambda (RESPONSE_STREAM): Handles streaming requests like /api/v2/stream

        The SSE Lambda requires RESPONSE_STREAM invoke mode to support Server-Sent Events.
        Using the Dashboard Lambda (BUFFERED mode) for SSE requests causes timeouts because
        the entire response must be buffered before sending.

        Environment variables:
        - PREPROD_API_URL: Dashboard Lambda Function URL (non-streaming requests)
        - SSE_LAMBDA_URL: SSE Lambda Function URL (streaming requests)

        See: specs/082-fix-sse-e2e-timeouts/spec.md for details.
    """

    def __init__(
        self,
        base_url: str | None = None,
        sse_url: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the API client.

        Args:
            base_url: API base URL (default: from PREPROD_API_URL env var)
            sse_url: SSE Lambda URL for streaming endpoints (default: from SSE_LAMBDA_URL env var)
            timeout: Request timeout in seconds
        """
        # Normalize URLs by removing trailing slashes to prevent httpx path issues
        raw_base_url = base_url or os.environ.get(
            "PREPROD_API_URL", "https://api.preprod.sentiment-analyzer.com"
        )
        self.base_url = raw_base_url.rstrip("/")

        # SSE Lambda URL for streaming endpoints
        # IMPORTANT: If SSE_LAMBDA_URL is not set, SSE requests will route to base_url
        # which uses BUFFERED mode and will cause 404 errors for streaming endpoints
        raw_sse_url = sse_url or os.environ.get("SSE_LAMBDA_URL", "")
        self.sse_url = raw_sse_url.rstrip("/") if raw_sse_url else self.base_url

        # Log URL configuration for debugging routing issues
        if self.sse_url == self.base_url:
            logger.warning(
                "SSE_LAMBDA_URL not set - SSE requests will route to base_url (%s). "
                "This may cause 404 errors if base_url uses BUFFERED invoke mode.",
                self.base_url,
            )
        else:
            logger.debug(
                "API client initialized: base_url=%s, sse_url=%s",
                self.base_url,
                self.sse_url,
            )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._bearer_token: str | None = None  # JWT bearer token (Feature 1053)
        self._auth_type: str | None = None
        self._last_trace_id: str | None = None
        self._last_request_id: str | None = None

    async def __aenter__(self) -> "PreprodAPIClient":
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def set_access_token(self, token: str) -> None:
        """Set the access token for authenticated requests (X-User-ID header).

        This is for anonymous session tokens (UUIDs) which are sent via X-User-ID.
        For authenticated JWT tokens, use set_bearer_token() instead.
        """
        self._access_token = token

    def set_bearer_token(self, jwt_token: str) -> None:
        """Set a JWT bearer token for authenticated requests (Feature 1053).

        This sends the token via Authorization: Bearer header, which the auth
        middleware validates as AuthType.AUTHENTICATED (vs ANONYMOUS for UUIDs).

        Args:
            jwt_token: A valid JWT token (use create_test_jwt() for tests)
        """
        self._bearer_token = jwt_token

    def set_auth_type(self, auth_type: str) -> None:
        """DEPRECATED: Set the auth type header (no longer effective).

        WARNING: Feature 1048 blocked X-Auth-Type header bypass vulnerability.
        This method is kept for backwards compatibility but the header is ignored
        by the auth middleware. Use set_bearer_token() for authenticated access.

        Args:
            auth_type: Authentication type (ignored by server)
        """
        # Log deprecation warning
        import warnings

        warnings.warn(
            "set_auth_type() is deprecated after Feature 1048 security fix. "
            "Use set_bearer_token() with a valid JWT for authenticated access.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._auth_type = auth_type

    def clear_access_token(self) -> None:
        """Clear all authentication tokens."""
        self._access_token = None
        self._auth_type = None
        self._bearer_token = None

    @property
    def last_trace_id(self) -> str | None:
        """Get the X-Ray trace ID from the last response."""
        return self._last_trace_id

    @property
    def last_request_id(self) -> str | None:
        """Get the request ID from the last response."""
        return self._last_request_id

    def _build_headers(
        self, extra_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Build request headers including auth if set.

        Authentication priority (Feature 1053):
        1. Bearer token (JWT) - sends Authorization: Bearer header
           → Server validates JWT and returns AuthType.AUTHENTICATED
        2. Access token (UUID) - sends X-User-ID header
           → Server returns AuthType.ANONYMOUS

        Note: X-Auth-Type header is deprecated and ignored by server (Feature 1048).
        """
        headers: dict[str, str] = {}

        # Bearer token takes priority (authenticated JWT)
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        elif self._access_token:
            # Fallback to X-User-ID for anonymous UUID tokens
            headers["X-User-ID"] = self._access_token

        # X-Auth-Type is deprecated but kept for backwards compatibility
        # Server ignores this header after Feature 1048 security fix
        if self._auth_type:
            headers["X-Auth-Type"] = self._auth_type

        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _capture_response_headers(self, response: httpx.Response) -> None:
        """Capture trace and request IDs from response headers."""
        self._last_trace_id = response.headers.get("X-Amzn-Trace-Id")
        self._last_request_id = response.headers.get("X-Request-Id")

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a GET request.

        Args:
            path: API path (e.g., "/api/v2/configurations")
            params: Query parameters
            headers: Additional headers

        Returns:
            httpx.Response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        response = await self._client.get(
            path,
            params=params,
            headers=self._build_headers(headers),
        )
        self._capture_response_headers(response)
        return response

    async def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a POST request.

        Args:
            path: API path
            json: JSON body
            data: Form data
            headers: Additional headers

        Returns:
            httpx.Response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        response = await self._client.post(
            path,
            json=json,
            data=data,
            headers=self._build_headers(headers),
        )
        self._capture_response_headers(response)
        return response

    async def put(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a PUT request.

        Args:
            path: API path
            json: JSON body
            headers: Additional headers

        Returns:
            httpx.Response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        response = await self._client.put(
            path,
            json=json,
            headers=self._build_headers(headers),
        )
        self._capture_response_headers(response)
        return response

    async def patch(
        self,
        path: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a PATCH request.

        Args:
            path: API path
            json: JSON body
            headers: Additional headers

        Returns:
            httpx.Response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        response = await self._client.patch(
            path,
            json=json,
            headers=self._build_headers(headers),
        )
        self._capture_response_headers(response)
        return response

    async def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make a DELETE request.

        Args:
            path: API path
            headers: Additional headers

        Returns:
            httpx.Response
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        response = await self._client.delete(
            path,
            headers=self._build_headers(headers),
        )
        self._capture_response_headers(response)
        return response

    async def health_check(self) -> bool:
        """Check if the API is healthy.

        Returns:
            True if API returns 200 on health endpoint
        """
        try:
            response = await self.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def stream_sse(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        timeout: float = 5.0,
    ) -> tuple[int, dict[str, str], str]:
        """Make a GET request to an SSE endpoint with streaming support.

        SSE endpoints never complete - they keep the connection open indefinitely.
        This method reads only the initial response (headers + first event) with
        a short timeout to validate the endpoint is working.

        URL Routing:
            Paths starting with "/api/v2/stream" are routed to the SSE Lambda
            (self.sse_url) which uses RESPONSE_STREAM invoke mode. Other paths
            are routed to the Dashboard Lambda (self.base_url).

        Args:
            path: API path (e.g., "/api/v2/stream")
            headers: Additional headers
            timeout: Read timeout in seconds (default: 5s)

        Returns:
            Tuple of (status_code, response_headers, initial_content)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context.")

        # Merge default SSE headers
        request_headers = self._build_headers(headers)
        if "Accept" not in request_headers:
            request_headers["Accept"] = "text/event-stream"

        # Route to SSE Lambda URL for any streaming endpoint (contains /stream)
        effective_url = self.sse_url if "/stream" in path else self.base_url

        # Log routing decision for debugging
        logger.debug(
            "SSE request routing: path=%s -> %s (base=%s, sse=%s)",
            path,
            effective_url,
            self.base_url,
            self.sse_url,
        )

        # Create a client with short read timeout for SSE
        async with httpx.AsyncClient(
            base_url=effective_url,
            timeout=httpx.Timeout(timeout, read=timeout),
        ) as stream_client:
            async with stream_client.stream(
                "GET",
                path,
                headers=request_headers,
            ) as response:
                self._capture_response_headers(response)

                # Detect routing failures for /stream paths
                if "/stream" in path and response.status_code == 404:
                    logger.error(
                        "SSE ROUTING FAILURE: Received 404 for stream endpoint %s. "
                        "This usually indicates the request was routed to the wrong Lambda. "
                        "Expected URL: %s, base_url: %s, sse_url: %s",
                        path,
                        effective_url,
                        self.base_url,
                        self.sse_url,
                    )

                # Read initial content (first event or timeout)
                content_parts = []
                try:
                    async for chunk in response.aiter_text():
                        content_parts.append(chunk)
                        # Stop after receiving some content
                        if len("".join(content_parts)) > 100:
                            break
                except httpx.ReadTimeout:
                    # Expected - SSE streams don't complete
                    pass

                return (
                    response.status_code,
                    dict(response.headers),
                    "".join(content_parts),
                )
