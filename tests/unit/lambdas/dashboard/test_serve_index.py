"""Unit tests for serve_index() (Feature 1039: API key injection removed).

Tests that serve_index() serves static HTML without modification.
Feature 1011 (API key injection) has been replaced by session auth in Feature 1039.
"""

import os
from unittest.mock import patch

import pytest

from src.lambdas.dashboard.handler import lambda_handler
from tests.conftest import make_event


class TestServeIndex:
    """Tests for serve_index() serving static HTML."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up test environment."""
        # Ensure ENVIRONMENT is set for logging
        os.environ.setdefault("ENVIRONMENT", "test")
        yield

    def test_serves_index_html(self, mock_lambda_context):
        """Serves index.html as static file."""
        response = lambda_handler(
            make_event(method="GET", path="/"),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200

    def test_no_api_key_injection(self, mock_lambda_context):
        """Feature 1039: No API key injection - frontend uses session auth."""
        with patch.dict(os.environ, {"API_KEY": "test-api-key-12345"}):
            response = lambda_handler(
                make_event(method="GET", path="/"),
                mock_lambda_context,
            )

            assert response["statusCode"] == 200
            # API key injection removed in Feature 1039
            assert "window.DASHBOARD_API_KEY" not in response["body"]
            assert "test-api-key-12345" not in response["body"]

    def test_html_structure_preserved(self, mock_lambda_context):
        """HTML structure is preserved when serving static file."""
        response = lambda_handler(
            make_event(method="GET", path="/"),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        body = response["body"]
        # Verify basic HTML structure elements exist
        assert "<!DOCTYPE html>" in body
        assert "<html" in body
        assert "</html>" in body
        assert "<head>" in body
        assert "</head>" in body
        assert "<body>" in body
        assert "</body>" in body

    def test_returns_html_content_type(self, mock_lambda_context):
        """Response has correct content type."""
        response = lambda_handler(
            make_event(method="GET", path="/"),
            mock_lambda_context,
        )

        assert response["statusCode"] == 200
        headers = response.get("headers", {})
        # Check for content-type header (case-insensitive lookup)
        content_type = ""
        for key, value in headers.items():
            if key.lower() == "content-type":
                content_type = value
                break
        assert "text/html" in content_type
