"""Contract tests C-1..C-6, C-8 for configure_lambda_logging().

Contract: specs/001-lambda-log-visibility/contracts/logging-config.md
"""

import importlib
import logging

import pytest

from src.lambdas.shared import logging_config
from src.lambdas.shared.logging_config import (
    SELF_TEST_MESSAGE,
    configure_lambda_logging,
)

PINNED = ("httpx", "httpcore")
SELF_TEST_LOGGER = "src.lambdas.shared.logging_config"


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Snapshot and restore levels touched by the helper; reset the latch."""
    saved = {name: logging.getLogger(name).level for name in ("", *PINNED)}
    yield
    logging_config._reset_for_tests()
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


class TestC1LevelReassertsEveryCall:
    def test_sets_root_to_info_by_default(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        logging.getLogger().setLevel(logging.WARNING)
        configure_lambda_logging()
        assert logging.getLogger().level == logging.INFO

    def test_reasserts_after_external_mutation(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_lambda_logging()
        logging.getLogger().setLevel(logging.WARNING)
        configure_lambda_logging()
        assert logging.getLogger().level == logging.INFO

    def test_explicit_log_level_env_wins(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        configure_lambda_logging()
        assert logging.getLogger().level == logging.WARNING

    def test_invalid_log_level_falls_back_to_info(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "NOT_A_LEVEL")
        configure_lambda_logging()
        assert logging.getLogger().level == logging.INFO


class TestC2ThirdPartyPins:
    def test_httpx_httpcore_pinned_to_warning(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_lambda_logging()
        for name in PINNED:
            assert logging.getLogger(name).level == logging.WARNING

    def test_pins_hold_under_deliberate_debug(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_lambda_logging()
        assert logging.getLogger().level == logging.DEBUG
        for name in PINNED:
            assert logging.getLogger(name).level == logging.WARNING

    def test_httpx_info_record_not_emitted_even_at_root_debug(
        self, monkeypatch, caplog
    ):
        """FR-010/T017: worst case (root DEBUG), httpx INFO must not pass."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_lambda_logging()
        with caplog.at_level(logging.DEBUG):
            logging.getLogger("httpx").info(
                "HTTP Request: GET https://api.example.com/news?token=SHOULD-NEVER-APPEAR"
            )
        assert not any(
            r.name == "httpx" and "SHOULD-NEVER-APPEAR" in r.getMessage()
            for r in caplog.records
        )


class TestC3NoHandlerMutations:
    def test_handler_counts_unchanged(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        before = {
            name: list(logging.getLogger(name).handlers) for name in ("", *PINNED)
        }
        configure_lambda_logging()
        after = {name: list(logging.getLogger(name).handlers) for name in ("", *PINNED)}
        assert before == after


class TestC4SelfTestOncePerProcess:
    def test_emits_exactly_once_across_calls(self, monkeypatch, caplog):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        with caplog.at_level(logging.INFO):
            configure_lambda_logging()
            configure_lambda_logging()
            configure_lambda_logging()
        emissions = [
            r
            for r in caplog.records
            if r.name == SELF_TEST_LOGGER and r.getMessage() == SELF_TEST_MESSAGE
        ]
        assert len(emissions) == 1

    def test_latch_does_not_suppress_level_reassertion(self, monkeypatch):
        """The latch is emission-only — C-1 must still re-assert (AR#2 F5)."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_lambda_logging()
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        configure_lambda_logging()
        assert logging.getLogger().level == logging.INFO
        assert logging.getLogger("httpx").level == logging.WARNING


class TestC5ImportSideEffectFree:
    def test_reimport_does_not_configure(self):
        root = logging.getLogger()
        root.setLevel(logging.WARNING)
        handlers_before = list(root.handlers)
        importlib.reload(logging_config)
        assert root.level == logging.WARNING
        assert list(root.handlers) == handlers_before


class TestC6OtherLoggersUntouched:
    def test_first_party_logger_levels_preserved(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        preset = logging.getLogger("src.lambdas.test_preset_module")
        preset.setLevel(logging.INFO)
        unset = logging.getLogger("src.lambdas.test_unset_module")
        assert unset.level == logging.NOTSET
        configure_lambda_logging()
        assert preset.level == logging.INFO
        assert unset.level == logging.NOTSET


class TestC8SelfTestLineShape:
    def test_logger_name_level_and_static_message(self, monkeypatch, caplog):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        with caplog.at_level(logging.INFO):
            configure_lambda_logging()
        [record] = [r for r in caplog.records if r.name == SELF_TEST_LOGGER]
        assert record.levelno == logging.INFO
        assert record.getMessage() == SELF_TEST_MESSAGE
        assert record.args in (None, ())
