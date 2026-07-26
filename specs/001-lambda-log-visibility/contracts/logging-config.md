# Contract: configure_lambda_logging()

**Module**: `src/lambdas/shared/logging_config.py` (NEW)
**Consumers**: the six deployed non-SSE entrypoints (dashboard, ingestion,
analysis, metrics, notification, canary handler modules)

## Signature

```python
def configure_lambda_logging(*, default_level: int = logging.INFO) -> None:
    """Set root logger level and pin noisy third-party loggers.

    Level-setter ONLY: never creates/attaches handlers, never sets
    formatters, never touches propagation. Idempotent per process.
    Honors LOG_LEVEL env (name or int); values below INFO are applied
    only when explicitly set (deliberate DEBUG), default floor is INFO.
    """
```

## Behavioral contract

| # | Guarantee | Verifying test |
|---|---|---|
| C-1 | After call, `logging.getLogger().level == INFO` (or explicit LOG_LEVEL) | unit |
| C-2 | `httpx` and `httpcore` loggers at WARNING after call, regardless of LOG_LEVEL | unit |
| C-3 | Zero handlers added/removed anywhere (root handler count unchanged pre/post) | unit |
| C-4 | Idempotent: second call changes nothing (incl. after level mutation between calls — latch, not re-assert) | unit |
| C-5 | No import-time side effects: importing the module does NOT configure anything; only the call does (SSE safety, FR-006) | unit |
| C-6 | Existing module-logger levels untouched (e.g., a logger pre-set to INFO stays INFO; none made stricter) | unit (FR-011) |
| C-7 | Every deployed non-SSE entrypoint calls it at module import top-level, before request handling | coverage-guard unit test walking the six handler files |

## Emitted log-shape contract (unchanged — the point of O2+)

- Format stays runtime Text: `[LEVEL]\t<ts>\t<request-id>\t<message>`.
- The `dashboard_import_errors` metric filter pattern continues to match.
- powertools JSON request lines and StructuredLogger/log_structured JSON
  lines are byte-identical to pre-change (no wrapper, no nesting).
- Delta is strictly additive: `[INFO]` lines from first-party modules.

## Out-of-contract (explicitly not provided)

- No correlation-ID injection on module lines (signposted O3 migration).
- No JSON structuring of stdlib lines (signposted O1/O3 migration).
- No coverage of a hypothetical future Lambda whose handler omits the call —
  the coverage-guard test fails CI when the deployed-entrypoint set grows
  without a corresponding call, which is detection, not prevention.
