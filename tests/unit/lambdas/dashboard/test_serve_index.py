"""Unit tests for serve_index() (Feature 1039: API key injection removed).

Tests that serve_index() serves static HTML without modification.
Feature 1011 (API key injection) has been replaced by session auth in Feature 1039.
"""

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


class TestServeIndex:
    """Tests for serve_index() serving static HTML."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up test environment."""
        # Ensure ENVIRONMENT is set for logging
        os.environ.setdefault("ENVIRONMENT", "test")
        yield

    def test_serves_index_html(self):
        """Serves index.html as static file."""
        from src.lambdas.dashboard.handler import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200

    def test_no_api_key_injection(self):
        """Feature 1039: No API key injection - frontend uses session auth."""
        with patch.dict(os.environ, {"API_KEY": "test-api-key-12345"}):
            from src.lambdas.dashboard.handler import app

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            # API key injection removed in Feature 1039
            assert "window.DASHBOARD_API_KEY" not in response.text
            assert "test-api-key-12345" not in response.text

    def test_html_structure_preserved(self):
        """HTML structure is preserved when serving static file."""
        from src.lambdas.dashboard.handler import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        # Verify basic HTML structure elements exist
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
        assert "</html>" in response.text
        assert "<head>" in response.text
        assert "</head>" in response.text
        assert "<body>" in response.text
        assert "</body>" in response.text

    def test_returns_html_content_type(self):
        """Response has correct content type."""
        from src.lambdas.dashboard.handler import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
