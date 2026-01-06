"""Unit tests for Feature 1157: Auth Cache-Control Headers.

Tests that the no_cache_headers dependency sets correct cache prevention headers
on all auth endpoint responses per RFC 7234.

Requirements tested:
- FR-001: Cache-Control: no-store, no-cache, must-revalidate
- FR-002: Pragma: no-cache (HTTP/1.0 compatibility)
- FR-003: Expires: 0 (Legacy proxy compatibility)
"""

import pytest
from fastapi import Response

from src.lambdas.dashboard.router_v2 import no_cache_headers


class TestNoCacheHeaders:
    """Test suite for no_cache_headers dependency function."""

    @pytest.mark.asyncio
    async def test_sets_cache_control_header(self) -> None:
        """Test that Cache-Control header is set correctly (FR-001)."""
        response = Response()
        await no_cache_headers(response)

        assert (
            response.headers.get("Cache-Control")
            == "no-store, no-cache, must-revalidate"
        )

    @pytest.mark.asyncio
    async def test_sets_pragma_header(self) -> None:
        """Test that Pragma header is set for HTTP/1.0 compatibility (FR-002)."""
        response = Response()
        await no_cache_headers(response)

        assert response.headers.get("Pragma") == "no-cache"

    @pytest.mark.asyncio
    async def test_sets_expires_header(self) -> None:
        """Test that Expires header is set for legacy proxy compatibility (FR-003)."""
        response = Response()
        await no_cache_headers(response)

        assert response.headers.get("Expires") == "0"

    @pytest.mark.asyncio
    async def test_sets_all_headers_together(self) -> None:
        """Test that all three headers are set in a single call."""
        response = Response()
        await no_cache_headers(response)

        assert (
            response.headers.get("Cache-Control")
            == "no-store, no-cache, must-revalidate"
        )
        assert response.headers.get("Pragma") == "no-cache"
        assert response.headers.get("Expires") == "0"

    @pytest.mark.asyncio
    async def test_overwrites_existing_cache_control(self) -> None:
        """Test that existing Cache-Control header is overwritten."""
        response = Response()
        response.headers["Cache-Control"] = "max-age=3600"

        await no_cache_headers(response)

        assert (
            response.headers.get("Cache-Control")
            == "no-store, no-cache, must-revalidate"
        )

    @pytest.mark.asyncio
    async def test_returns_none(self) -> None:
        """Test that the dependency returns None (modifies response in-place)."""
        response = Response()
        result = await no_cache_headers(response)

        assert result is None
