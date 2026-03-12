"""Tests for dependencies module (lazy singletons)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.lambdas.shared.dependencies import (
    get_finnhub_adapter,
    get_no_cache_headers,
    get_ticker_cache_dependency,
    get_tiingo_adapter,
    get_users_table,
    reset_singletons,
)


@pytest.fixture(autouse=True)
def _reset():
    """Reset singletons before and after each test."""
    reset_singletons()
    yield
    reset_singletons()


class TestGetUsersTable:
    """Tests for get_users_table."""

    @patch("src.lambdas.shared.dynamodb.get_table")
    def test_returns_table(self, mock_get_table):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        with patch.dict(os.environ, {"USERS_TABLE": "test-users"}):
            result = get_users_table()
        assert result is mock_table
        mock_get_table.assert_called_once_with("test-users")

    @patch("src.lambdas.shared.dynamodb.get_table")
    def test_caches_singleton(self, mock_get_table):
        mock_get_table.return_value = MagicMock()
        with patch.dict(os.environ, {"USERS_TABLE": "test-users"}):
            first = get_users_table()
            second = get_users_table()
        assert first is second
        mock_get_table.assert_called_once()


class TestGetTiingoAdapter:
    """Tests for get_tiingo_adapter."""

    @patch("src.lambdas.shared.adapters.tiingo.TiingoAdapter")
    def test_from_env_var(self, mock_adapter_cls):
        mock_adapter_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"TIINGO_API_KEY": "test-key"}, clear=False):
            result = get_tiingo_adapter()
        mock_adapter_cls.assert_called_once_with(api_key="test-key")
        assert result is mock_adapter_cls.return_value

    @patch("src.lambdas.shared.secrets.get_api_key", return_value="secret-key")
    @patch("src.lambdas.shared.adapters.tiingo.TiingoAdapter")
    def test_from_secrets_manager(self, mock_adapter_cls, mock_get_key):
        mock_adapter_cls.return_value = MagicMock()
        env = {
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo"
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TIINGO_API_KEY", None)
            result = get_tiingo_adapter()
        mock_get_key.assert_called_once()
        assert result is mock_adapter_cls.return_value

    def test_no_key_raises_runtime_error(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TIINGO_API_KEY", None)
            os.environ.pop("TIINGO_SECRET_ARN", None)
            with pytest.raises(RuntimeError, match="unavailable"):
                get_tiingo_adapter()

    @patch("src.lambdas.shared.secrets.get_api_key", side_effect=Exception("denied"))
    def test_secrets_manager_failure_falls_through(self, mock_get_key):
        env = {
            "TIINGO_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:tiingo"
        }
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TIINGO_API_KEY", None)
            with pytest.raises(RuntimeError, match="unavailable"):
                get_tiingo_adapter()


class TestGetFinnhubAdapter:
    """Tests for get_finnhub_adapter."""

    @patch("src.lambdas.shared.adapters.finnhub.FinnhubAdapter")
    def test_from_env_var(self, mock_adapter_cls):
        mock_adapter_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"FINNHUB_API_KEY": "test-key"}, clear=False):
            get_finnhub_adapter()
        mock_adapter_cls.assert_called_once_with(api_key="test-key")

    @patch("src.lambdas.shared.secrets.get_api_key", return_value="secret-key")
    @patch("src.lambdas.shared.adapters.finnhub.FinnhubAdapter")
    def test_from_secrets_manager(self, mock_adapter_cls, mock_get_key):
        mock_adapter_cls.return_value = MagicMock()
        env = {"FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finn"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("FINNHUB_API_KEY", None)
            get_finnhub_adapter()
        mock_get_key.assert_called_once()

    def test_no_key_raises_runtime_error(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FINNHUB_API_KEY", None)
            os.environ.pop("FINNHUB_SECRET_ARN", None)
            with pytest.raises(RuntimeError, match="unavailable"):
                get_finnhub_adapter()

    @patch("src.lambdas.shared.secrets.get_api_key", side_effect=Exception("denied"))
    def test_secrets_manager_failure_falls_through(self, mock_get_key):
        env = {"FINNHUB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123:secret:finn"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("FINNHUB_API_KEY", None)
            with pytest.raises(RuntimeError, match="unavailable"):
                get_finnhub_adapter()


class TestGetTickerCacheDependency:
    """Tests for get_ticker_cache_dependency."""

    def test_no_bucket_returns_none(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TICKER_CACHE_BUCKET", None)
            assert get_ticker_cache_dependency() is None

    @patch("src.lambdas.shared.cache.ticker_cache.get_ticker_cache")
    def test_with_bucket_returns_cache(self, mock_get_cache):
        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache
        with patch.dict(os.environ, {"TICKER_CACHE_BUCKET": "my-bucket"}):
            result = get_ticker_cache_dependency()
        assert result is mock_cache

    @patch(
        "src.lambdas.shared.cache.ticker_cache.get_ticker_cache",
        side_effect=Exception("fail"),
    )
    def test_cache_init_failure_returns_none(self, mock_get_cache):
        with patch.dict(os.environ, {"TICKER_CACHE_BUCKET": "my-bucket"}):
            assert get_ticker_cache_dependency() is None


class TestGetNoCacheHeaders:
    """Tests for get_no_cache_headers."""

    def test_returns_cache_busting_headers(self):
        headers = get_no_cache_headers()
        assert "no-store" in headers["Cache-Control"]
        assert headers["Pragma"] == "no-cache"
        assert headers["Expires"] == "0"


class TestResetSingletons:
    """Tests for reset_singletons."""

    @patch("src.lambdas.shared.dynamodb.get_table")
    def test_reset_clears_cached_values(self, mock_get_table):
        mock_get_table.return_value = MagicMock()
        with patch.dict(os.environ, {"USERS_TABLE": "t"}):
            get_users_table()
            reset_singletons()
            get_users_table()
        assert mock_get_table.call_count == 2
