"""Regression guard: the ingestion handler must never log Secrets Manager ARNs.

Feature 001-ingestion-arn-logging. Guards CodeQL rule
``py/clear-text-logging-sensitive-data`` at ``src/lambdas/ingestion/handler.py``
lines 264, 271 and 276 (alerts 148, 149, 150).

Assertion surface (FR-007, research D4): every assertion runs over
``record.getMessage()`` joined with ``str(v)`` for **every** value in
``record.__dict__``. ``caplog.text`` is deliberately never used anywhere in this
module: a rendered-text-only assertion passes against the two ``extra={...}``
sites even on unfixed code, so it proves nothing.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from src.lambdas.shared.quota_tracker import clear_quota_cache

# ---------------------------------------------------------------------------
# Fixture ARNs (research D5, plan Test design)
# ---------------------------------------------------------------------------
TIINGO_ARN = (
    "arn:aws:secretsmanager:eu-west-2:218795110243:secret:"
    "preprod/sentiment-analyzer/tiingo-AbCdEf"
)
FINNHUB_ARN = (
    "arn:aws:secretsmanager:eu-west-2:218795110243:secret:"
    "preprod/sentiment-analyzer/finnhub-GhIjKl"
)

# Six forbidden classes (research D5 / FR-007), eight concrete strings.
# Each is asserted on its own so a failure names exactly which class leaked.
#
# Two near-miss traps, both deliberate and both load-bearing:
#   * NEVER shorten "preprod/sentiment-analyzer" to "sentiment-analyzer".
#     The haystack includes ``record.pathname``, an absolute path inside a
#     checkout named ``sentiment-analyzer-gsk`` (and, for dependency records,
#     inside ``.venv/lib/python3.13/site-packages``). The short form matches
#     every record for a reason unrelated to the ARN.
#   * NEVER assert on bare "arn:aws:", which collides with SNS_TOPIC_ARN.
FORBIDDEN: list[tuple[str, str]] = [
    ("full ARN (tiingo)", TIINGO_ARN),
    ("full ARN (finnhub)", FINNHUB_ARN),
    ("service prefix", "arn:aws:secretsmanager"),
    ("account id", "218795110243"),
    ("region", "eu-west-2"),
    ("secret path segment", "preprod/sentiment-analyzer"),
    ("secret suffix (tiingo)", "AbCdEf"),
    ("secret suffix (finnhub)", "GhIjKl"),
]

HANDLER_LOGGER = "src.lambdas.ingestion.handler"


# ---------------------------------------------------------------------------
# Assertion surface helpers
# ---------------------------------------------------------------------------
def haystack(record: logging.LogRecord) -> str:
    """Rendered message plus every value in ``record.__dict__``.

    The ``str()`` coercion is load-bearing: ``record.__dict__`` holds non-string
    values (``args``, ``exc_info``, ``levelno``) and a bare membership test
    against them raises TypeError. Scanning all of ``__dict__`` rather than a
    named key list is deliberate: it survives a key rename and catches a leak
    that migrates to a new ``extra`` key.
    """
    parts = [record.getMessage()]
    parts.extend(str(v) for v in record.__dict__.values())
    return "\n".join(parts)


def where(record: logging.LogRecord, needle: str) -> list[str]:
    """Locations of ``needle`` in a record: "message" and/or "dict:<key>".

    Mandatory, not decorative. ``haystack()`` joins values and therefore
    discards the key, so a failure diff built from it alone cannot show whether
    a leak arrived through the rendered message or through a structured
    attribute. The RED gate (T007) requires exactly that distinction.
    """
    found = []
    if needle in record.getMessage():
        found.append("message")
    for key, value in record.__dict__.items():
        if needle in str(value):
            found.append(f"dict:{key}")
    return found


def assert_record_clean(record: logging.LogRecord) -> None:
    """Assert one record carries none of the six forbidden classes."""
    for label, needle in FORBIDDEN:
        assert needle not in haystack(record), (
            f"leak [{label}] {needle!r} at {where(record, needle)} "
            f"on logger={record.name} msg={record.getMessage()!r}"
        )


def handler_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Records emitted by this module's own logger only.

    ``caplog`` captures third-party records too (botocore, parallel_fetcher,
    failure_tracker). An unrestricted sweep would make this suite hostage to
    whatever any dependency happens to log.
    """
    return [r for r in caplog.records if r.name == HANDLER_LOGGER]


def project_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """All in-project records. Used by the case-5 sweep."""
    return [r for r in caplog.records if r.name.startswith("src.lambdas.")]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_caches():
    """Reset module-level caches before each test.

    Duplicated from ``test_handler.py`` on purpose: autouse fixtures are not
    shared across modules, and without this ``_active_tickers_cache`` leaks
    between modules in a full-directory run.
    """
    import src.lambdas.ingestion.handler as handler_module

    handler_module._active_tickers_cache = []
    handler_module._active_tickers_cache_timestamp = 0.0
    clear_quota_cache()
    yield
    handler_module._active_tickers_cache = []
    handler_module._active_tickers_cache_timestamp = 0.0
    clear_quota_cache()


@pytest.fixture
def arn_env():
    """Environment whose only source of the forbidden strings is the two ARNs.

    Isolation constraints (FR-007 as amended by Clarification Q3, plan review
    M4). Every variable below must contain none of ``218795110243``,
    ``eu-west-2`` or ``preprod/sentiment-analyzer``:
      * SNS_TOPIC_ARN keeps the unrelated account/region from ``test_handler``.
      * ALERT_TOPIC_ARN is left unset (``_get_config()`` defaults it to "").
      * AWS_REGION stays us-east-1 **and CLOUD_REGION is pinned to us-east-1**.
        ``_get_config()`` reads CLOUD_REGION first and only falls back to
        AWS_REGION, so an inherited CLOUD_REGION silently defeats the region
        isolation. spec.md FR-007 names three variables; this is the fourth.

    Teardown restores the prior value of every variable it set, or pops it.
    """
    values = {
        "DATABASE_TABLE": "test-financial-news",
        "USERS_TABLE": "test-financial-news",
        "SNS_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789:test-topic",
        "TIINGO_SECRET_ARN": TIINGO_ARN,
        "FINNHUB_SECRET_ARN": FINNHUB_ARN,
        "MODEL_VERSION": "v1.0.0",
        "AWS_REGION": "us-east-1",
        "CLOUD_REGION": "us-east-1",
        "ENVIRONMENT": "test",
    }
    previous = {key: os.environ.get(key) for key in values}
    previous_alert = os.environ.get("ALERT_TOPIC_ARN")
    os.environ.pop("ALERT_TOPIC_ARN", None)
    os.environ.update(values)
    yield
    for key, prior in previous.items():
        if prior is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = prior
    if previous_alert is not None:
        os.environ["ALERT_TOPIC_ARN"] = previous_alert
    else:
        os.environ.pop("ALERT_TOPIC_ARN", None)


def _create_table_with_gsi(dynamodb, table_name: str = "test-financial-news"):
    """DynamoDB table with the by_entity_status GSI (mirrors test_handler.py)."""
    return dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "entity_type", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by_entity_status",
                "KeySchema": [
                    {"AttributeName": "entity_type", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _seed_active_config() -> None:
    """One active configuration, so lambda_handler reaches the ARN sites."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_table_with_gsi(dynamodb)
    table.put_item(
        Item={
            "PK": "USER#user1",
            "SK": "CONFIG#config1",
            "entity_type": "CONFIGURATION",
            "status": "active",
            "tickers": [{"symbol": "AAPL"}],
        }
    )


def _empty_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.get_news.return_value = []
    adapter.close = MagicMock()
    return adapter


def _invoke(get_api_key_mock) -> dict:
    """Run lambda_handler with the adapters and side effects stubbed out.

    The entrypoint is ``lambda_handler``; there is no symbol named ``handler``
    in this module and importing one raises ImportError.
    """
    from src.lambdas.ingestion.handler import lambda_handler

    context = MagicMock()
    context.aws_request_id = "test-request-id"

    with (
        patch(
            "src.lambdas.ingestion.handler.get_api_key",
            get_api_key_mock,
        ),
        patch(
            "src.lambdas.ingestion.handler.TiingoAdapter",
            return_value=_empty_adapter(),
        ),
        patch(
            "src.lambdas.ingestion.handler.FinnhubAdapter",
            return_value=_empty_adapter(),
        ),
        patch(
            "src.lambdas.ingestion.handler._get_sns_client",
            return_value=MagicMock(),
        ),
        patch("src.lambdas.ingestion.handler.emit_metrics_batch"),
    ):
        return lambda_handler({"source": "test"}, context)


def _key_for(tiingo: str | None, finnhub: str | None) -> MagicMock:
    """get_api_key stub keyed on the ARN it is called with."""

    def side_effect(secret_arn, *args, **kwargs):
        if secret_arn == TIINGO_ARN:
            return tiingo
        if secret_arn == FINNHUB_ARN:
            return finnhub
        raise AssertionError(f"unexpected secret arn: {secret_arn!r}")

    return MagicMock(side_effect=side_effect)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
class TestIngestionHandlerNeverLogsSecretArns:
    """Five cases. Case 4 is a pin, not a discriminator (see its docstring)."""

    @mock_aws
    def test_case1_both_credentials_unavailable(self, arn_env, caplog):
        """Site 1: the definitely-rendered CONFIGURATION ERROR record."""
        _seed_active_config()
        with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
            _invoke(_key_for(None, None))

        config_errors = [
            r
            for r in handler_records(caplog)
            if r.levelno == logging.ERROR and "CONFIGURATION ERROR" in r.getMessage()
        ]
        assert config_errors, (
            "no CONFIGURATION ERROR record captured from "
            f"{HANDLER_LOGGER}; saw {[r.getMessage() for r in handler_records(caplog)]}"
        )
        record = config_errors[0]

        # FR-002: the record must still name both sources in fixed literal text.
        message = record.getMessage()
        assert "Tiingo" in message, f"source name missing (case-sensitive): {message!r}"
        assert "Finnhub" in message, (
            f"source name missing (case-sensitive): {message!r}"
        )

        assert_record_clean(record)

    @mock_aws
    def test_case2_tiingo_only_unavailable(self, arn_env, caplog):
        """Site 2: the structured-context WARNING for Tiingo."""
        _seed_active_config()
        with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
            _invoke(_key_for(None, "finnhub-key"))

        warnings = [
            r
            for r in handler_records(caplog)
            if r.levelno == logging.WARNING and "Tiingo" in r.getMessage()
        ]
        assert warnings, (
            "no degraded-mode WARNING naming Tiingo captured; saw "
            f"{[r.getMessage() for r in handler_records(caplog)]}"
        )
        for record in warnings:
            assert_record_clean(record)

    @mock_aws
    def test_case3_finnhub_only_unavailable(self, arn_env, caplog):
        """Site 3: the structured-context WARNING for Finnhub."""
        _seed_active_config()
        with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
            _invoke(_key_for("tiingo-key", None))

        warnings = [
            r
            for r in handler_records(caplog)
            if r.levelno == logging.WARNING and "Finnhub" in r.getMessage()
        ]
        assert warnings, (
            "no degraded-mode WARNING naming Finnhub captured; saw "
            f"{[r.getMessage() for r in handler_records(caplog)]}"
        )
        for record in warnings:
            assert_record_clean(record)

    @mock_aws
    def test_case4_outer_exception_path(self, arn_env, caplog):
        """Acceptance Scenario 4 / FR-005: the outer ``except`` record.

        PIN, NOT A DISCRIMINATOR. ``get_safe_error_info(e)`` returns
        ``{"error_type": ...}`` only, so this record is clean **by construction
        even on unfixed code**. Its green must never be read as evidence the
        fix landed. It exists to prove the raised RuntimeError message cannot
        reintroduce the ARN downstream.
        """
        _seed_active_config()
        with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
            response = _invoke(_key_for(None, None))

        assert response["statusCode"] == 500

        outer = [
            r
            for r in handler_records(caplog)
            if r.getMessage() == "Financial ingestion failed"
        ]
        assert outer, (
            "outer except record not captured; saw "
            f"{[r.getMessage() for r in handler_records(caplog)]}"
        )
        for record in outer:
            assert_record_clean(record)

    @mock_aws
    def test_case5_sweep_every_record(self, arn_env, caplog):
        """Sweep: every in-project record from the case-1 invocation is clean.

        Catches a leak that migrates to a fourth site in this module.
        """
        _seed_active_config()
        with caplog.at_level(logging.WARNING, logger=HANDLER_LOGGER):
            _invoke(_key_for(None, None))

        records = project_records(caplog)
        assert records, "sweep captured no in-project records at all (read failed)"
        for record in records:
            assert_record_clean(record)
