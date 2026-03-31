"""Feature 1290: Runtime environment variable validation.

Detects missing or empty critical env vars at cold start and emits structured
logs for CloudWatch metric extraction. Continues execution (degraded mode) —
does not crash the Lambda.

Usage at module level (runs once per cold start):
    from lambdas.shared.env_validation import validate_critical_env_vars
    validate_critical_env_vars(["SCHEDULER_ROLE_ARN"])
"""

import logging
import os

logger = logging.getLogger(__name__)


def validate_critical_env_vars(var_names: list[str]) -> list[str]:
    """Check that critical env vars are non-empty.

    Returns list of missing/empty var names.
    Emits structured warning log for each missing var with metric dimension
    for CloudWatch metric filter extraction.
    """
    environment = os.environ.get("ENVIRONMENT", "unknown")
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "unknown")
    missing = []

    for name in var_names:
        value = os.environ.get(name, "")
        if not value:
            missing.append(name)
            logger.warning(
                "Critical env var is empty or missing — feature may be degraded",
                extra={
                    "metric": "env_var_missing",
                    "var_name": name,
                    "lambda": function_name,
                    "environment": environment,
                },
            )

    return missing
