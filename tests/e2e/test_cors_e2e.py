"""E2E tests for CORS behavior (Feature 1267).

End-to-end validation that the full authentication flow works with
the corrected CORS headers. Making a credentialed API call and
receiving a response implicitly validates that CORS is configured
correctly (the browser would block the response otherwise).

For On-Call Engineers:
    If tests fail:
    1. Verify preprod API Gateway has Feature 1267 changes applied
    2. Check that OPTIONS responses echo Origin (not wildcard)
    3. Verify Access-Control-Allow-Credentials: true is present
"""

import os

import pytest
import requests

# Preprod API endpoint and auth token
API_ENDPOINT = os.getenv("PREPROD_API_ENDPOINT", "")
AUTH_TOKEN = os.getenv("PREPROD_AUTH_TOKEN", "")
ALLOWED_ORIGIN = "https://main.d29tlmksqcx494.amplifyapp.com"

pytestmark = [
    pytest.mark.preprod,
    pytest.mark.skipif(
        not API_ENDPOINT or not AUTH_TOKEN,
        reason="PREPROD_API_ENDPOINT and PREPROD_AUTH_TOKEN required for E2E CORS tests",
    ),
]


class TestCORSE2E:
    """Full end-to-end CORS validation against preprod."""

    def test_authenticated_api_call_succeeds(self) -> None:
        """T026: Authenticated API call with correct origin succeeds.

        This is an implicit CORS validation: if the API returns data
        with correct CORS headers, a browser would allow the response.
        We verify the headers explicitly here since we're not in a browser.
        """
        # Step 1: Verify OPTIONS preflight succeeds with origin echoing
        preflight = requests.options(
            f"{API_ENDPOINT}/api/v2/configurations",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
            timeout=10,
        )
        assert preflight.status_code == 200
        assert (
            preflight.headers.get("Access-Control-Allow-Origin") == ALLOWED_ORIGIN
        ), "Preflight must echo the allowed origin"
        assert (
            preflight.headers.get("Access-Control-Allow-Credentials") == "true"
        ), "Preflight must include Allow-Credentials: true"

        # Step 2: Make authenticated API call
        response = requests.get(
            f"{API_ENDPOINT}/api/v2/configurations",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Authorization": f"Bearer {AUTH_TOKEN}",
            },
            timeout=10,
        )
        # Should get a successful response (200) or at least not a CORS error
        assert (
            response.status_code == 200
        ), f"Expected 200 from authenticated API call, got {response.status_code}"

        # Step 3: Verify response includes correct CORS headers
        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
        assert (
            allow_origin == ALLOWED_ORIGIN
        ), f"Response must echo allowed origin, got: {allow_origin}"
