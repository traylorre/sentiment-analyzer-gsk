"""Tests for event_validator module."""

import pytest

from src.lambdas.shared.utils.event_validator import (
    InvalidEventError,
    validate_apigw_event,
)


class TestValidateApigwEvent:
    """Tests for validate_apigw_event."""

    def test_valid_event_passes(self):
        """Event with all required keys passes validation."""
        event = {
            "httpMethod": "GET",
            "path": "/api/test",
            "requestContext": {"stage": "prod"},
        }
        validate_apigw_event(event)  # Should not raise

    def test_missing_keys_raises(self):
        """Event missing required keys raises InvalidEventError."""
        with pytest.raises(InvalidEventError, match="missing required"):
            validate_apigw_event({"httpMethod": "GET"})

    def test_non_dict_raises(self):
        """Non-dict event raises InvalidEventError."""
        with pytest.raises(InvalidEventError, match="must be a dict"):
            validate_apigw_event("not a dict")  # type: ignore[arg-type]

    def test_empty_dict_raises(self):
        """Empty dict raises InvalidEventError."""
        with pytest.raises(InvalidEventError, match="missing required"):
            validate_apigw_event({})
