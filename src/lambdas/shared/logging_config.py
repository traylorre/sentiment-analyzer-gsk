"""Central logging-level configuration for Lambda entrypoints (feature 001).

Sets the ROOT logger level so first-party module loggers' INFO records become
visible in CloudWatch, and pins noisy third-party HTTP-client loggers to
WARNING so their per-request URL logging (which can carry credentials in
query strings) never lights up. Level-setter ONLY: never attaches handlers or
formatters, never touches propagation.

Stated dependency (research R-1, AR#3): awslambdaric's bootstrap ``main()``
runs ``_setup_logging`` — attaching the LambdaLoggerHandler to the root
logger — BEFORE ``_get_handler`` imports the entrypoint module that calls
this function. That ordering is what makes the once-per-process self-test
line below land in CloudWatch on every cold start. If it ever changed, the
line would fall to ``logging.lastResort`` (WARNING threshold) and drop.

Deliberately NOT imported by src/lambdas/sse_streaming (FR-006): importing
this module has no side effects; only an explicit call configures anything.
"""

import logging
import os

_PINNED_LOGGERS = ("httpx", "httpcore")

SELF_TEST_MESSAGE = "logging configured: root INFO visibility active (feature 001)"

_selftest_emitted = False


def configure_lambda_logging(*, default_level: int = logging.INFO) -> None:
    """Set root logger level, pin third-party loggers, emit self-test once.

    Level resolution: explicit ``LOG_LEVEL`` env (name or numeric) wins —
    including a deliberate DEBUG for temporary diagnostics; unset or invalid
    falls back to ``default_level`` (INFO). Levels re-assert on EVERY call
    (contract C-1); only the self-test emission is once-per-process (C-4).
    The httpx/httpcore pins hold regardless of LOG_LEVEL (C-2, FR-010).
    """
    global _selftest_emitted

    logging.getLogger().setLevel(
        _resolve_level(os.environ.get("LOG_LEVEL"), default_level)
    )
    for name in _PINNED_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    _repair_powertools_suppress_filters()

    if not _selftest_emitted:
        _selftest_emitted = True
        logging.getLogger(__name__).info(SELF_TEST_MESSAGE)


class _BoundarySuppressFilter(logging.Filter):
    """Name-boundary-aware replacement for powertools' SuppressFilter (C-9).

    Powertools installs SuppressFilter(service) on every ROOT handler to
    dedup its own propagated records, but its filter() is a raw SUBSTRING
    test: with service="dashboard" it also rejects every record from
    "src.lambdas.dashboard.*" module loggers — total log loss for the
    subtree, discovered live 2026-07-26. This filter suppresses exactly the
    powertools logger and its children (the documented intent) and nothing
    else.
    """

    def __init__(self, service: str):
        super().__init__()
        self.logger = service  # attribute name mirrors SuppressFilter's

    def filter(self, record: logging.LogRecord) -> bool:
        return not (
            record.name == self.logger or record.name.startswith(self.logger + ".")
        )


def _repair_powertools_suppress_filters() -> None:
    """Swap any powertools SuppressFilter on root handlers for the boundary-
    aware version. No-op when powertools is absent or no filter is installed.

    Ordering: powertools installs the filter during the first
    ``Logger(service=...)`` init, so the entrypoint must call
    ``configure_lambda_logging()`` AFTER constructing its powertools Logger
    (the dashboard handler does; the other five have no powertools Logger
    and this is a no-op).
    """
    try:
        from aws_lambda_powertools.logging.filters import SuppressFilter
    except ImportError:  # powertools not packaged in this Lambda
        return
    for handler in logging.getLogger().handlers:
        for flt in list(handler.filters):
            if type(flt) is SuppressFilter:
                handler.removeFilter(flt)
                handler.addFilter(_BoundarySuppressFilter(flt.logger))


def _resolve_level(raw: str | None, default: int) -> int:
    if not raw:
        return default
    value = raw.strip().upper()
    if value.isdigit():
        return int(value)
    resolved = logging.getLevelName(value)
    return resolved if isinstance(resolved, int) else default


def _reset_for_tests() -> None:
    """Test hook: re-arm the self-test latch (unit tests only)."""
    global _selftest_emitted
    _selftest_emitted = False
