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

    if not _selftest_emitted:
        _selftest_emitted = True
        logging.getLogger(__name__).info(SELF_TEST_MESSAGE)


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
