# E2E Tests: Alert Email Quota Tracking (Issue #125)
#
# Tests the alert email quota API:
# - GET /api/v2/alerts/quota - Get current quota status
# - Quota structure validation (used, limit, remaining, resets_at)
# - Anonymous user quota access
# - Quota persistence across requests
#
# Note: Incrementing quota to test limits is marked TODO as it would
# incur costs by triggering actual email sends.

import pytest

from tests.e2e.helpers.api_client import PreprodAPIClient

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us6]


async def create_anonymous_session(
    api_client: PreprodAPIClient,
) -> str:
    """Helper to create an anonymous session.

    Returns:
        Access token for the anonymous session
    """
    response = await api_client.post("/api/v2/auth/anonymous")
    assert response.status_code == 200, f"Anonymous session failed: {response.text}"
    return response.json()["token"]


@pytest.mark.asyncio
async def test_quota_endpoint_returns_status(
    api_client: PreprodAPIClient,
) -> None:
    """T145: Verify quota endpoint returns valid status structure.

    Given: An authenticated user (anonymous)
    When: GET /api/v2/alerts/quota is called
    Then: Response contains used, limit, remaining, resets_at, is_exceeded
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/alerts/quota")

        if response.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response.status_code == 200, f"Quota request failed: {response.text}"

        data = response.json()

        # Validate required fields
        assert "used" in data, "Response missing 'used' field"
        assert "limit" in data, "Response missing 'limit' field"
        assert "remaining" in data, "Response missing 'remaining' field"
        assert "resets_at" in data, "Response missing 'resets_at' field"
        assert "is_exceeded" in data, "Response missing 'is_exceeded' field"

        # Validate field types
        assert isinstance(data["used"], int), "used should be integer"
        assert isinstance(data["limit"], int), "limit should be integer"
        assert isinstance(data["remaining"], int), "remaining should be integer"
        assert isinstance(data["resets_at"], str), "resets_at should be string"
        assert isinstance(data["is_exceeded"], bool), "is_exceeded should be boolean"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_quota_values_are_consistent(
    api_client: PreprodAPIClient,
) -> None:
    """Verify quota values are mathematically consistent.

    Given: Quota status from API
    When: Comparing used, limit, and remaining
    Then: remaining = limit - used (clamped at 0)
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/alerts/quota")

        if response.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response.status_code == 200
        data = response.json()

        used = data["used"]
        limit = data["limit"]
        remaining = data["remaining"]
        is_exceeded = data["is_exceeded"]

        # Verify mathematical consistency
        expected_remaining = max(0, limit - used)
        assert remaining == expected_remaining, (
            f"Remaining should be max(0, limit - used): "
            f"got {remaining}, expected {expected_remaining}"
        )

        # Verify is_exceeded flag
        expected_exceeded = used >= limit
        assert (
            is_exceeded == expected_exceeded
        ), f"is_exceeded should be {expected_exceeded} when used={used}, limit={limit}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_quota_resets_at_is_valid_iso_datetime(
    api_client: PreprodAPIClient,
) -> None:
    """Verify resets_at is a valid ISO datetime in the future.

    Given: Quota status from API
    When: Parsing resets_at
    Then: It's a valid ISO datetime in the future
    """
    from datetime import UTC, datetime

    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/alerts/quota")

        if response.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response.status_code == 200
        data = response.json()

        resets_at_str = data["resets_at"]

        # Parse ISO datetime
        try:
            resets_at = datetime.fromisoformat(resets_at_str.replace("Z", "+00:00"))
        except ValueError as e:
            pytest.fail(f"resets_at is not valid ISO format: {resets_at_str} - {e}")

        # Should be in the future (within 24 hours typically)
        now = datetime.now(UTC)
        assert resets_at > now, f"resets_at should be in the future: {resets_at}"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_quota_is_consistent_across_requests(
    api_client: PreprodAPIClient,
) -> None:
    """Verify quota is consistent when queried multiple times.

    Given: An authenticated session
    When: Querying quota multiple times
    Then: Values are consistent (no changes without email sends)
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        # First request
        response1 = await api_client.get("/api/v2/alerts/quota")

        if response1.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response1.status_code == 200
        data1 = response1.json()

        # Second request
        response2 = await api_client.get("/api/v2/alerts/quota")
        assert response2.status_code == 200
        data2 = response2.json()

        # Values should be the same (no emails sent between requests)
        assert data1["used"] == data2["used"], "used should be consistent"
        assert data1["limit"] == data2["limit"], "limit should be consistent"
        assert (
            data1["remaining"] == data2["remaining"]
        ), "remaining should be consistent"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_quota_unauthorized_without_token(
    api_client: PreprodAPIClient,
) -> None:
    """Verify quota endpoint requires authentication.

    Given: No authentication token
    When: GET /api/v2/alerts/quota is called
    Then: Response is 401 Unauthorized
    """
    # Ensure no token is set
    api_client.clear_access_token()

    response = await api_client.get("/api/v2/alerts/quota")

    # Should require authentication
    assert response.status_code in (
        401,
        403,
    ), f"Quota should require auth, got {response.status_code}"


@pytest.mark.asyncio
async def test_quota_fresh_user_has_zero_used(
    api_client: PreprodAPIClient,
) -> None:
    """Verify fresh anonymous user has zero quota used.

    Given: A new anonymous session (never sent emails)
    When: GET /api/v2/alerts/quota is called
    Then: used is 0 and remaining equals limit
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/alerts/quota")

        if response.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response.status_code == 200
        data = response.json()

        # Fresh user should have 0 used
        assert data["used"] == 0, f"Fresh user should have 0 used, got {data['used']}"

        # Remaining should equal limit
        assert data["remaining"] == data["limit"], (
            f"Fresh user should have remaining == limit: "
            f"remaining={data['remaining']}, limit={data['limit']}"
        )

        # Should not be exceeded
        assert data["is_exceeded"] is False, "Fresh user should not be exceeded"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_quota_limit_is_reasonable(
    api_client: PreprodAPIClient,
) -> None:
    """Verify quota limit is set to a reasonable value.

    Given: Quota status from API
    When: Checking the limit
    Then: Limit is within expected range (e.g., 10-1000)
    """
    token = await create_anonymous_session(api_client)
    api_client.set_access_token(token)

    try:
        response = await api_client.get("/api/v2/alerts/quota")

        if response.status_code == 404:
            pytest.skip("Quota endpoint not implemented")

        assert response.status_code == 200
        data = response.json()

        limit = data["limit"]

        # Limit should be positive and reasonable
        assert limit > 0, f"Limit should be positive, got {limit}"
        assert limit <= 1000, f"Limit seems unreasonably high: {limit}"

    finally:
        api_client.clear_access_token()


# TODO: The following tests require actually sending emails to increment quota.
# These are marked as TODO because they would incur costs (SendGrid API calls).
#
# @pytest.mark.asyncio
# async def test_quota_increments_after_alert_send():
#     """Verify quota increments after sending alert email."""
#     pass
#
# @pytest.mark.asyncio
# async def test_quota_blocks_when_exceeded():
#     """Verify quota enforcement when limit is reached."""
#     pass
#
# @pytest.mark.asyncio
# async def test_quota_race_condition_protection():
#     """Verify concurrent increments are handled atomically."""
#     pass
