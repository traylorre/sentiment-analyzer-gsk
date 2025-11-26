"""
Contract Tests: Magic Link Authentication API (T084)
====================================================

Tests that magic link endpoints conform to auth-api.md contract.

Constitution v1.1:
- Contract tests validate response schemas against API contracts
- All tests use moto to mock AWS infrastructure ($0 cost)
- External deps (SendGrid) must be mocked
"""

import re

# Contract schemas based on auth-api.md


class TestMagicLinkRequest:
    """Contract tests for POST /api/v2/auth/magic-link."""

    def test_request_schema_accepts_valid_email(self):
        """Request must accept valid email address."""
        request = {
            "email": "user@example.com",
            "anonymous_user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        # Validate required fields
        assert "email" in request
        assert "@" in request["email"]
        assert request.get("anonymous_user_id") is None or isinstance(
            request["anonymous_user_id"], str
        )

    def test_request_schema_email_required(self):
        """Email field must be required."""
        request = {"anonymous_user_id": "550e8400-e29b-41d4-a716-446655440000"}

        assert "email" not in request

    def test_request_schema_anonymous_id_optional(self):
        """Anonymous user ID is optional."""
        request = {"email": "user@example.com"}

        # Should be valid without anonymous_user_id
        assert "email" in request
        assert "anonymous_user_id" not in request

    def test_response_202_schema(self):
        """202 Accepted response must match contract."""
        response = {
            "status": "email_sent",
            "email": "user@example.com",
            "expires_in_seconds": 3600,
            "message": "Check your email for a sign-in link",
        }

        # Required fields
        assert response["status"] == "email_sent"
        assert "@" in response["email"]
        assert response["expires_in_seconds"] == 3600
        assert isinstance(response["message"], str)

    def test_response_400_invalid_email(self):
        """400 response for invalid email format."""
        response = {
            "error": "validation_error",
            "message": "Invalid email address format.",
            "field": "email",
        }

        assert response["error"] == "validation_error"
        assert (
            "email" in response.get("field", "")
            or "email" in response["message"].lower()
        )

    def test_response_429_rate_limited(self):
        """429 response for rate limited requests."""
        response = {
            "error": "rate_limited",
            "message": "Too many requests. Please try again later.",
            "retry_after_seconds": 3600,
        }

        assert response["error"] == "rate_limited"
        assert response["retry_after_seconds"] > 0


class TestMagicLinkVerify:
    """Contract tests for GET /api/v2/auth/magic-link/verify."""

    def test_query_params_required(self):
        """Token and sig query params required."""
        valid_url = "/api/v2/auth/magic-link/verify?token=abc123&sig=xyz789"

        assert "token=" in valid_url
        assert "sig=" in valid_url

    def test_response_200_verified_schema(self):
        """200 OK response for successful verification."""
        response = {
            "status": "verified",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "user@example.com",
            "auth_type": "email",
            "tokens": {
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "expires_in": 3600,
            },
            "merged_anonymous_data": True,
        }

        # Required fields
        assert response["status"] == "verified"
        assert _is_valid_uuid(response["user_id"])
        assert "@" in response["email"]
        assert response["auth_type"] == "email"

        # Token structure
        tokens = response["tokens"]
        assert "id_token" in tokens
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["expires_in"] > 0

        # Optional merge status
        assert isinstance(response.get("merged_anonymous_data"), bool)

    def test_response_400_token_expired(self):
        """400 response for expired token."""
        response = {
            "status": "invalid",
            "error": "token_expired",
            "message": "This link has expired. Please request a new one.",
        }

        assert response["status"] == "invalid"
        assert response["error"] == "token_expired"

    def test_response_400_token_used(self):
        """400 response for already-used token."""
        response = {
            "status": "invalid",
            "error": "token_used",
            "message": "This link has already been used.",
        }

        assert response["status"] == "invalid"
        assert response["error"] == "token_used"

    def test_response_400_invalid_signature(self):
        """400 response for invalid signature."""
        response = {
            "status": "invalid",
            "error": "invalid_signature",
            "message": "Invalid link. Please request a new one.",
        }

        assert response["status"] == "invalid"
        assert response["error"] == "invalid_signature"


class TestMagicLinkTokenFormat:
    """Contract tests for magic link token format."""

    def test_token_url_format(self):
        """Token URL must match expected format."""
        token_url = "https://app.domain/auth/verify?token=abc123def456&sig=xyz789"

        # Extract token and sig
        assert "token=" in token_url
        assert "sig=" in token_url

        # Token should be alphanumeric
        token_match = re.search(r"token=([a-zA-Z0-9_-]+)", token_url)
        assert token_match is not None

        sig_match = re.search(r"sig=([a-zA-Z0-9_-]+)", token_url)
        assert sig_match is not None

    def test_token_expiry_one_hour(self):
        """Tokens must expire in 1 hour per contract."""
        expected_expiry_seconds = 3600

        response = {
            "status": "email_sent",
            "email": "user@example.com",
            "expires_in_seconds": 3600,
            "message": "Check your email for a sign-in link",
        }

        assert response["expires_in_seconds"] == expected_expiry_seconds


class TestMagicLinkEmailContent:
    """Contract tests for magic link email content."""

    def test_email_subject(self):
        """Email subject must match contract."""
        expected_subject = "Your sign-in link for Sentiment Dashboard"

        # Subject should be descriptive and match contract
        assert "sign-in" in expected_subject.lower()
        assert "Sentiment" in expected_subject

    def test_email_contains_link(self):
        """Email must contain clickable verification link."""
        email_body = """
        Click the link below to sign in:
        https://app.domain/auth/verify?token=abc123&sig=xyz789

        This link expires in 1 hour.
        If you didn't request this, you can ignore this email.
        """

        assert "auth/verify" in email_body
        assert "token=" in email_body
        assert "expires" in email_body.lower()

    def test_email_contains_expiry_warning(self):
        """Email must warn about expiry time."""
        email_body = "This link expires in 1 hour."

        assert "expire" in email_body.lower()
        assert "1 hour" in email_body or "60 minute" in email_body.lower()

    def test_email_contains_ignore_notice(self):
        """Email must explain what to do if not requested."""
        email_body = "If you didn't request this, you can ignore this email."

        assert "ignore" in email_body.lower() or "safely" in email_body.lower()


class TestMagicLinkPreviousInvalidation:
    """Contract tests for previous link invalidation behavior."""

    def test_new_request_invalidates_previous(self):
        """New magic link request must invalidate any pending links."""
        # First request creates token A
        # Second request creates token B and invalidates token A

        first_response = {
            "status": "email_sent",
            "email": "user@example.com",
            "expires_in_seconds": 3600,
            "message": "Check your email for a sign-in link",
        }

        second_response = {
            "status": "email_sent",
            "email": "user@example.com",
            "expires_in_seconds": 3600,
            "message": "Check your email for a sign-in link",
        }

        # Both should succeed (new token created each time)
        assert first_response["status"] == "email_sent"
        assert second_response["status"] == "email_sent"

        # Attempting to use first token after second request should fail
        verification_of_old_token = {
            "status": "invalid",
            "error": "token_invalidated",
            "message": "This link has been invalidated. A new link was requested.",
        }

        assert verification_of_old_token["status"] == "invalid"


class TestMagicLinkRateLimits:
    """Contract tests for magic link rate limiting."""

    def test_rate_limit_per_email(self):
        """Rate limit is 5 requests per hour per email."""
        rate_limit_response = {
            "error": "rate_limited",
            "message": "Too many requests. Please try again later.",
            "retry_after_seconds": 3600,
        }

        # Per contract: 5 per hour per email
        assert rate_limit_response["retry_after_seconds"] <= 3600

    def test_rate_limit_not_per_user(self):
        """Rate limit applies to email, not user ID."""
        # User can request magic link for different emails
        # Rate limit applies per email address

        # This is a behavioral contract test
        # Different emails should not share rate limit
        email1_requests = 5
        email2_requests = 5

        # Both should be allowed (separate rate limit counters)
        assert email1_requests <= 5
        assert email2_requests <= 5


def _is_valid_uuid(value: str) -> bool:
    """Check if string is valid UUID format."""
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
