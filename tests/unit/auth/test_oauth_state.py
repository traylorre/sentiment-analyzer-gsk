"""Unit tests for OAuth state management."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.lambdas.shared.auth.oauth_state import (
    OAUTH_STATE_TTL_SECONDS,
    generate_state,
    get_oauth_state,
    store_oauth_state,
    validate_oauth_state,
)


@pytest.fixture
def mock_table():
    table = MagicMock()
    table.meta.client.exceptions.ConditionalCheckFailedException = type(
        "ConditionalCheckFailedException", (Exception,), {}
    )
    return table


class TestGenerateState:
    def test_returns_string(self):
        assert isinstance(generate_state(), str)

    def test_unique(self):
        assert generate_state() != generate_state()

    def test_length(self):
        assert len(generate_state()) == 43


class TestStoreOAuthState:
    def test_stores_and_returns_state(self, mock_table):
        state = store_oauth_state(
            mock_table, "state-1", "google", "https://example.com/callback"
        )
        assert state.state_id == "state-1"
        assert state.provider == "google"
        assert state.used is False
        mock_table.put_item.assert_called_once()

    def test_stores_ttl_derived_from_the_configured_lifetime(self, mock_table):
        """The item is what actually expires, so the TTL is asserted on the item.

        This previously rode on a log-field assertion, which only ever proved that a
        constant had been copied into a log line.
        """
        before = datetime.now(UTC)
        store_oauth_state(
            mock_table, "state-ttl", "google", "https://example.com/callback"
        )
        after = datetime.now(UTC)

        item = mock_table.put_item.call_args.kwargs["Item"]
        assert isinstance(item["ttl_timestamp"], int)
        assert (
            int((before + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)).timestamp())
            <= item["ttl_timestamp"]
            <= int((after + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)).timestamp())
        )

    def test_stores_with_user_id(self, mock_table):
        state = store_oauth_state(
            mock_table, "state-2", "github", "https://example.com/cb", user_id="u-1"
        )
        assert state.user_id == "u-1"
        item = mock_table.put_item.call_args.kwargs["Item"]
        assert item["user_id"] == "u-1"

    def test_log_context_excludes_provider(self, mock_table, caplog):
        """Regression guard for py/clear-text-logging-sensitive-data (alert 144).

        No value derived from `provider` may reach the logger's extra context.
        `logging` promotes every extra key to a LogRecord attribute, so this
        asserts on the sink itself rather than on rendered output, which is bare
        in production and would pass either way.
        """
        with caplog.at_level(
            logging.INFO, logger="src.lambdas.shared.auth.oauth_state"
        ):
            store_oauth_state(
                mock_table, "state-1", "google", "https://example.com/callback"
            )

        records = [r for r in caplog.records if r.getMessage() == "OAuth state stored"]
        assert len(records) == 1
        assert not hasattr(records[0], "provider")
        assert records[0].has_user_id is False
        # OAUTH_STATE_TTL_SECONDS is no longer logged. CodeQL's sensitive-data heuristic
        # classifies any identifier containing "oauth" as a password, so the constant was
        # reported as a cleartext credential; it never varied, so it was dropped rather
        # than renamed. The TTL is asserted on the stored item instead, by
        # test_stores_ttl_derived_from_the_configured_lifetime above.
        assert not hasattr(records[0], "ttl_seconds")


class TestGetOAuthState:
    def test_returns_state_when_found(self, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "provider": "google",
                "redirect_uri": "https://example.com/cb",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                "used": False,
                "user_id": "u-1",
            }
        }
        state = get_oauth_state(mock_table, "state-1")
        assert state is not None
        assert state.provider == "google"
        assert state.user_id == "u-1"

    def test_returns_none_when_not_found(self, mock_table):
        mock_table.get_item.return_value = {}
        assert get_oauth_state(mock_table, "missing") is None

    def test_returns_none_on_exception(self, mock_table):
        mock_table.get_item.side_effect = RuntimeError("DynamoDB error")
        assert get_oauth_state(mock_table, "state-1") is None


class TestValidateOAuthState:
    def _setup_valid_state(self, mock_table):
        now = datetime.now(UTC)
        mock_table.get_item.return_value = {
            "Item": {
                "provider": "google",
                "redirect_uri": "https://example.com/cb",
                "created_at": now.isoformat(),
                "used": False,
            }
        }

    def test_valid_state(self, mock_table):
        self._setup_valid_state(mock_table)
        valid, error, _cv = validate_oauth_state(
            mock_table, "state-1", "google", "https://example.com/cb"
        )
        assert valid is True
        assert error == ""

    def test_state_not_found(self, mock_table):
        mock_table.get_item.return_value = {}
        valid, error, _cv = validate_oauth_state(
            mock_table, "missing", "google", "https://example.com/cb"
        )
        assert valid is False
        assert error == "Invalid OAuth state"

    def test_state_expired(self, mock_table):
        old_time = datetime.now(UTC) - timedelta(seconds=OAUTH_STATE_TTL_SECONDS + 60)
        mock_table.get_item.return_value = {
            "Item": {
                "provider": "google",
                "redirect_uri": "https://example.com/cb",
                "created_at": old_time.isoformat(),
                "used": False,
            }
        }
        valid, _, _cv = validate_oauth_state(
            mock_table, "state-1", "google", "https://example.com/cb"
        )
        assert valid is False

    def test_state_already_used(self, mock_table):
        now = datetime.now(UTC)
        mock_table.get_item.return_value = {
            "Item": {
                "provider": "google",
                "redirect_uri": "https://example.com/cb",
                "created_at": now.isoformat(),
                "used": True,
            }
        }
        valid, _, _cv = validate_oauth_state(
            mock_table, "state-1", "google", "https://example.com/cb"
        )
        assert valid is False

    def test_provider_mismatch(self, mock_table):
        self._setup_valid_state(mock_table)
        valid, _, _cv = validate_oauth_state(
            mock_table, "state-1", "github", "https://example.com/cb"
        )
        assert valid is False

    def test_redirect_uri_mismatch(self, mock_table):
        self._setup_valid_state(mock_table)
        valid, _, _cv = validate_oauth_state(
            mock_table, "state-1", "google", "https://evil.com/cb"
        )
        assert valid is False

    def test_concurrent_use_race_condition(self, mock_table):
        self._setup_valid_state(mock_table)
        mock_table.update_item.side_effect = (
            mock_table.meta.client.exceptions.ConditionalCheckFailedException()
        )
        valid, _, _cv = validate_oauth_state(
            mock_table, "state-1", "google", "https://example.com/cb"
        )
        assert valid is False
