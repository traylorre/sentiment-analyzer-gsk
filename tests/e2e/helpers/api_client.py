# Preprod API Client
#
# HTTP client wrapper for interacting with the preprod API during E2E tests.
# Handles authentication, request tracing, and response validation.

import os
from typing import Any

import httpx


class PreprodAPIClient:
    """Async HTTP client for preprod API interactions.

    Provides a thin wrapper around httpx.AsyncClient with:
    - Base URL configuration from environment
    - Authentication header management
    - Request ID tracking for observability tests
    - Response helpers for common assertions
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the API client.

        Args:
            base_url: API base URL (default: from PREPROD_API_URL env var)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.environ.get(
            "PREPROD_API_URL", "https://api.preprod.sentiment-analyzer.com"
        )
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
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
        """Set the access token for authenticated requests."""
        self._access_token = token

    def set_auth_type(self, auth_type: str) -> None:
        """Set the auth type for authenticated requests.

        Args:
            auth_type: Authentication type (e.g., 'email', 'oauth', 'anonymous')
        """
        self._auth_type = auth_type

    def clear_access_token(self) -> None:
        """Clear the access token (for testing unauthenticated endpoints)."""
        self._access_token = None
        self._auth_type = None

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

        The API v2 router uses X-User-ID header for user identification,
        not Authorization: Bearer. The access_token is the user_id returned
        from the anonymous session creation endpoint.

        X-Auth-Type header indicates the authentication method used
        (e.g., 'email', 'oauth', 'anonymous').
        """
        headers: dict[str, str] = {}
        if self._access_token:
            # API v2 uses X-User-ID header for authentication
            headers["X-User-ID"] = self._access_token
        if self._auth_type:
            # API v2 uses X-Auth-Type to distinguish auth methods
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

        # Create a client with short read timeout for SSE
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, read=timeout),
        ) as stream_client:
            async with stream_client.stream(
                "GET",
                path,
                headers=request_headers,
            ) as response:
                self._capture_response_headers(response)

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
