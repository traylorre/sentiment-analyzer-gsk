# E2E Tests - Preprod environment tests
#
# These tests run ONLY in the CI pipeline against the preprod AWS environment.
# They use real DynamoDB, Cognito, and other AWS services but mock external APIs
# (Tiingo, Finnhub, SendGrid) with synthetic data generators.
#
# Run locally: NOT SUPPORTED (requires preprod AWS credentials)
# Run in CI: pytest tests/e2e/ -m e2e
#
# See specs/008-e2e-validation-suite/quickstart.md for details.

import pytest

# Register e2e marker for preprod-only tests
pytest.mark.e2e = pytest.mark.e2e

# User story markers for selective test execution
pytest.mark.us1 = pytest.mark.us1  # Anonymous -> Authenticated
pytest.mark.us2 = pytest.mark.us2  # OAuth flows
pytest.mark.us3 = pytest.mark.us3  # Config CRUD
pytest.mark.us4 = pytest.mark.us4  # Sentiment/Volatility
pytest.mark.us5 = pytest.mark.us5  # Alerts
pytest.mark.us6 = pytest.mark.us6  # Notifications
pytest.mark.us7 = pytest.mark.us7  # Rate Limiting
pytest.mark.us8 = pytest.mark.us8  # Circuit Breaker
pytest.mark.us9 = pytest.mark.us9  # Ticker Validation
pytest.mark.us10 = pytest.mark.us10  # SSE
pytest.mark.us11 = pytest.mark.us11  # Observability
pytest.mark.us12 = pytest.mark.us12  # Market Status

# Test categorization markers
pytest.mark.auth = pytest.mark.auth  # Authentication tests
pytest.mark.slow = pytest.mark.slow  # Slow tests (> 10s)
pytest.mark.preprod = pytest.mark.preprod  # Preprod-only tests (all e2e tests)
