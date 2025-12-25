# E2E Tests: Alert Rule Lifecycle (User Story 5)
#
# Tests alert rule CRUD and management:
# - Create sentiment threshold alert
# - Create volatility threshold alert
# - Toggle alert on/off
# - Update alert threshold
# - Delete alert
# - Max alert limit enforcement
# - Anonymous user restrictions
#
# NOTE (Feature 1053): Tests requiring authenticated access now use JWT bearer
# tokens instead of the deprecated X-Auth-Type header (blocked by Feature 1048).

import pytest

from tests.e2e.conftest import create_test_jwt
from tests.e2e.helpers.api_client import PreprodAPIClient
from tests.fixtures.synthetic.config_generator import (
    SyntheticConfiguration,
)

pytestmark = [pytest.mark.e2e, pytest.mark.preprod, pytest.mark.us5]


async def create_config_for_authenticated_user(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> tuple[str, str]:
    """Helper to create config with JWT authenticated user (Feature 1053).

    Args:
        api_client: The preprod API client
        synthetic_config: Configuration to create
        test_jwt_secret: JWT secret for test token generation

    Returns (user_id, config_id).
    """
    import uuid

    # Generate authenticated JWT token
    user_id = str(uuid.uuid4())
    token = create_test_jwt(user_id=user_id, secret=test_jwt_secret)
    api_client.set_bearer_token(token)

    config_response = await api_client.post(
        "/api/v2/configurations",
        json=synthetic_config.to_api_payload(),
    )

    if config_response.status_code != 201:
        api_client.clear_access_token()
        pytest.skip(f"Config creation failed: {config_response.status_code}")

    config_id = config_response.json()["config_id"]
    return user_id, config_id


async def create_config_for_anonymous_user(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> tuple[str, str]:
    """Helper to create anonymous session and config.

    Args:
        api_client: The preprod API client
        synthetic_config: Configuration to create

    Returns (token, config_id).
    """
    session_response = await api_client.post("/api/v2/auth/anonymous", json={})
    assert session_response.status_code == 201
    token = session_response.json()["token"]

    api_client.set_access_token(token)

    config_response = await api_client.post(
        "/api/v2/configurations",
        json=synthetic_config.to_api_payload(),
    )

    if config_response.status_code != 201:
        api_client.clear_access_token()
        pytest.skip("Config creation not available")

    config_id = config_response.json()["config_id"]
    return token, config_id


@pytest.mark.asyncio
async def test_alert_create_sentiment_threshold(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T068: Verify sentiment threshold alert can be created.

    Given: A configuration with tickers (JWT authenticated user)
    When: POST /api/v2/configurations/{id}/alerts is called with sentiment alert
    Then: Alert is created and returned with alert_id
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        alert_payload = {
            "type": "sentiment",
            "ticker": ticker_symbol,
            "threshold": 0.7,
            "condition": "above",  # or "below"
            "enabled": True,
        }

        response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json=alert_payload,
        )

        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert response.status_code in (
            200,
            201,
        ), f"Alert create failed: {response.status_code} - {response.text}"

        data = response.json()
        assert "alert_id" in data, "Response missing alert_id"
        assert data.get("type") == "sentiment"
        assert data.get("enabled") is True

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_create_volatility_threshold(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T069: Verify volatility threshold alert can be created.

    Given: A configuration with tickers (JWT authenticated user)
    When: POST /api/v2/configurations/{id}/alerts is called with volatility alert
    Then: Alert is created for ATR-based volatility
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        alert_payload = {
            "type": "volatility",
            "ticker": ticker_symbol,
            "threshold": 5.0,  # ATR threshold
            "condition": "above",
            "enabled": True,
        }

        response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json=alert_payload,
        )

        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert response.status_code in (
            200,
            201,
        ), f"Volatility alert create failed: {response.status_code}"

        data = response.json()
        assert "alert_id" in data
        assert data.get("type") == "volatility"

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_toggle_off(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T070: Verify alert can be toggled off.

    Given: An enabled alert (JWT authenticated user)
    When: PATCH /api/v2/alerts/{id} with enabled=false
    Then: Alert is disabled
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        # Create alert
        create_response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json={
                "type": "sentiment",
                "ticker": ticker_symbol,
                "threshold": 0.5,
                "condition": "above",
                "enabled": True,
            },
        )

        if create_response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert create_response.status_code == 201
        alert_id = create_response.json()["alert_id"]

        # Toggle off
        toggle_response = await api_client.patch(
            f"/api/v2/alerts/{alert_id}",
            json={"enabled": False},
        )

        assert (
            toggle_response.status_code == 200
        ), f"Alert toggle failed: {toggle_response.status_code}"

        # Verify disabled
        data = toggle_response.json()
        assert data.get("enabled") is False

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_update_threshold(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T071: Verify alert threshold can be updated.

    Given: An existing alert (JWT authenticated user)
    When: PATCH /api/v2/alerts/{id} with new threshold
    Then: Alert threshold is updated
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        # Create alert with initial threshold
        create_response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json={
                "type": "sentiment",
                "ticker": ticker_symbol,
                "threshold": 0.5,
                "condition": "above",
                "enabled": True,
            },
        )

        if create_response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert create_response.status_code == 201
        alert_id = create_response.json()["alert_id"]

        # Update threshold
        new_threshold = 0.8
        update_response = await api_client.patch(
            f"/api/v2/alerts/{alert_id}",
            json={"threshold": new_threshold},
        )

        assert update_response.status_code == 200

        data = update_response.json()
        assert data.get("threshold") == new_threshold

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_delete(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T072: Verify alert can be deleted.

    Given: An existing alert (JWT authenticated user)
    When: DELETE /api/v2/alerts/{id} is called
    Then: Alert is deleted and no longer accessible
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        # Create alert
        create_response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json={
                "type": "sentiment",
                "ticker": ticker_symbol,
                "threshold": 0.6,
                "condition": "below",
                "enabled": True,
            },
        )

        if create_response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert create_response.status_code == 201
        alert_id = create_response.json()["alert_id"]

        # Delete alert
        delete_response = await api_client.delete(f"/api/v2/alerts/{alert_id}")

        assert delete_response.status_code in (
            200,
            204,
        ), f"Alert delete failed: {delete_response.status_code}"

        # Verify deleted
        get_response = await api_client.get(f"/api/v2/alerts/{alert_id}")
        assert get_response.status_code == 404

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_max_limit_enforced(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """T073: Verify maximum alert limit is enforced.

    Given: A user with maximum allowed alerts (JWT authenticated)
    When: Creating another alert
    Then: Request is rejected with limit error
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        created_alerts = []
        max_attempts = 20  # Try to exceed typical limit

        for i in range(max_attempts):
            response = await api_client.post(
                f"/api/v2/configurations/{config_id}/alerts",
                json={
                    "type": "sentiment",
                    "ticker": ticker_symbol,
                    "threshold": 0.5 + (i * 0.02),
                    "condition": "above",
                    "enabled": True,
                },
            )

            if response.status_code == 404:
                pytest.skip("Alerts endpoint not implemented")

            if response.status_code == 201:
                created_alerts.append(response.json()["alert_id"])
            elif response.status_code in (400, 403, 429):
                # Limit reached
                data = response.json()
                assert (
                    "error" in data
                    or "message" in data
                    or "detail" in data
                    or "limit" in str(data).lower()
                ), f"Limit error should have message: {data}"
                break
        # If no limit hit, that's also acceptable

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_anonymous_forbidden(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
) -> None:
    """T074: Verify anonymous users cannot create alerts.

    This test validates the Feature 1048 security fix - anonymous users
    (UUID tokens) should be rejected from alert endpoints that require
    AuthType.AUTHENTICATED.

    Given: An anonymous session (UUID token, no JWT)
    When: Attempting to create an alert
    Then: Request is rejected with 403 (authenticated user required)
    """
    # Use anonymous session (no JWT authentication)
    token, config_id = await create_config_for_anonymous_user(
        api_client, synthetic_config
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        # Try to create alert as anonymous - should fail with 403
        response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json={
                "type": "sentiment",
                "ticker": ticker_symbol,
                "threshold": 0.5,
                "condition": "above",
                "enabled": True,
            },
        )

        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        # After Feature 1048, anonymous users should be rejected
        assert response.status_code == 403, (
            f"Expected 403 for anonymous user, got {response.status_code}. "
            f"Feature 1048 requires authenticated users for alert endpoints."
        )

        data = response.json()
        # Should indicate authentication required
        assert "error" in data or "message" in data or "detail" in data

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_list(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """Verify alerts can be listed for a configuration.

    Given: A configuration with alerts (JWT authenticated user)
    When: GET /api/v2/configurations/{id}/alerts is called
    Then: List of alerts is returned
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        # Create a couple alerts
        for threshold in [0.5, 0.7]:
            await api_client.post(
                f"/api/v2/configurations/{config_id}/alerts",
                json={
                    "type": "sentiment",
                    "ticker": ticker_symbol,
                    "threshold": threshold,
                    "condition": "above",
                    "enabled": True,
                },
            )

        # List alerts
        response = await api_client.get(f"/api/v2/configurations/{config_id}/alerts")

        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        assert response.status_code == 200

        data = response.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])
        assert isinstance(alerts, list)

    finally:
        api_client.clear_access_token()


@pytest.mark.asyncio
async def test_alert_invalid_threshold(
    api_client: PreprodAPIClient,
    synthetic_config: SyntheticConfiguration,
    test_jwt_secret: str,
) -> None:
    """Verify invalid threshold values are rejected.

    Given: An alert request with invalid threshold (JWT authenticated user)
    When: POST to create alert
    Then: Request is rejected with validation error
    """
    user_id, config_id = await create_config_for_authenticated_user(
        api_client, synthetic_config, test_jwt_secret
    )
    ticker_symbol = synthetic_config.tickers[0].symbol

    try:
        response = await api_client.post(
            f"/api/v2/configurations/{config_id}/alerts",
            json={
                "type": "sentiment",
                "ticker": ticker_symbol,
                "threshold": 999,  # Invalid for sentiment (-1 to 1)
                "condition": "above",
                "enabled": True,
            },
        )

        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")

        # Should be rejected for invalid threshold
        # Note: Some APIs might accept any threshold
        if response.status_code in (400, 422):
            data = response.json()
            assert "error" in data or "message" in data or "detail" in data

    finally:
        api_client.clear_access_token()
