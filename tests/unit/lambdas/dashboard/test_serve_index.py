"""Unit tests for serve_index() API key injection (Feature 1011).

Tests the API key injection mechanism using the actual index.html file.
"""

import os
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


class TestServeIndexApiKeyInjection:
    """Tests for API key injection in serve_index()."""

    @pytest.fixture(autouse=True)
    def setup_env(self):
        """Set up test environment."""
        # Ensure ENVIRONMENT is set for logging
        os.environ.setdefault("ENVIRONMENT", "test")
        yield

    def test_injects_api_key_when_configured(self):
        """When API_KEY is set, injects window.DASHBOARD_API_KEY script."""
        with patch.dict(os.environ, {"API_KEY": "test-api-key-12345"}):
            # Reimport to pick up the new API_KEY
            from src.lambdas.dashboard.handler import app, get_api_key

            # Verify get_api_key returns our test key
            assert get_api_key() == "test-api-key-12345"

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            assert "window.DASHBOARD_API_KEY" in response.text
            assert "test-api-key-12345" in response.text
            # Verify script is before </head>
            assert (
                '<script>window.DASHBOARD_API_KEY = "test-api-key-12345";</script>\n</head>'
                in response.text
            )

    def test_no_injection_when_api_key_not_configured(self):
        """When API_KEY is not set, no script injection occurs."""
        # Remove API_KEY if present
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("API_KEY", None)
            os.environ.pop("DASHBOARD_API_KEY_SECRET_ARN", None)

            from src.lambdas.dashboard.handler import app, get_api_key

            # Verify get_api_key returns empty
            assert get_api_key() == ""

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            # When no API key, DASHBOARD_API_KEY should not appear
            assert "DASHBOARD_API_KEY" not in response.text

    def test_html_structure_preserved_with_injection(self):
        """API key injection doesn't break HTML structure."""
        with patch.dict(os.environ, {"API_KEY": "test-key"}):
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
        with patch.dict(os.environ, {"API_KEY": "test-key"}):
            from src.lambdas.dashboard.handler import app

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    def test_script_injection_position(self):
        """API key script is injected before </head> tag."""
        with patch.dict(os.environ, {"API_KEY": "my-secret-key"}):
            from src.lambdas.dashboard.handler import app

            client = TestClient(app)
            response = client.get("/")

            assert response.status_code == 200
            # Find positions
            script_pos = response.text.find("window.DASHBOARD_API_KEY")
            head_close_pos = response.text.find("</head>")

            assert script_pos > 0, "Script should be present"
            assert head_close_pos > 0, "</head> should be present"
            assert script_pos < head_close_pos, "Script should be before </head>"
