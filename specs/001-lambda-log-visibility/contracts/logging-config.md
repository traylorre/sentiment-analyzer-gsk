# Contract: configure_lambda_logging()

**Module**: `src/lambdas/shared/logging_config.py` (NEW)
**Consumers**: the six deployed non-SSE entrypoints (dashboard, ingestion,
analysis, metrics, notification, canary handler modules)

## Signature

```python
def configure_lambda_logging(*, default_level: int = logging.INFO) -> None:
    """Set root logger level, pin noisy third-party loggers, emit self-test.

    Level-setter ONLY: never creates/attaches handlers, never sets
    formatters, never touches propagation. Honors LOG_LEVEL env (name or
    int); unset -> INFO. Re-asserts levels on every call; emits its
    self-test line once per process.
    """
```

## Behavioral contract

| # | Guarantee | Verifying test |
|---|---|---|
| C-1 | After EVERY call, `logging.getLogger().level` == INFO (or explicit LOG_LEVEL) — the level set RE-ASSERTS on each call (idempotent by same-outcome, not by latch) | unit |
| C-2 | `httpx` and `httpcore` loggers at WARNING after every call, regardless of LOG_LEVEL (pins hold even under deliberate DEBUG) | unit |
| C-3 | Zero handlers added/removed anywhere (root handler count unchanged pre/post) | unit |
| C-4 | Self-test line (C-8) emits at most ONCE per process — the once-latch applies ONLY to the emission, never to the level assertions of C-1/C-2 | unit |
| C-5 | Importing `logging_config` itself is side-effect-free; configuration happens only on call. (The six ENTRYPOINT modules invoke the function at their own import top-level — that is C-7's requirement, not a violation of this one.) SSE importing shared modules therefore stays untouched (FR-006) | unit |
| C-6 | Levels of loggers OTHER THAN root/httpx/httpcore are untouched (e.g., an entrypoint logger pre-set to INFO stays INFO; none made stricter) | unit (FR-011) |
| C-7 | Every deployed non-SSE entrypoint calls it at module import top-level, before request handling. Coverage-guard derives the entrypoint set by GLOBBING `src/lambdas/*/handler.py` minus the documented exclusion list `{sse_streaming, chaos_restore}` — a new Lambda directory enters the walked set automatically (AR#2 F4: no hardcoded six-name list) | coverage-guard unit test |
| C-8 | Self-test probe: on first call per process, emits exactly one INFO line via `logging.getLogger("src.lambdas.shared.logging_config")` (an un-leveled child logger that inherits root). Its presence in a function's log group PROVES the root-level fix is live in that function — the universal FR-008 evidence line, and the ONLY possible evidence for canary/metrics, which have no other dark INFO site (AR#2 F1/F2). Message is static (no dynamic values → no injection/PII surface) | unit + preprod E2E |

## Emitted log-shape contract (unchanged — the point of O2+)

- Format stays the runtime Text application-line format. NOTE (AR#2 F8): the
  observed line shape (`[LEVEL]` first) disagrees with the field order the
  `dashboard_import_errors` metric filter pattern assumes (`[time,
  request_id, level=ERROR*, ...]`) — meaning the filter may NEVER have
  matched an application line even pre-change. SC-003's comparison therefore
  includes a positive control (see plan); if the filter proves
  dead-on-arrival, that is a PRE-EXISTING defect carded separately, not a
  regression of this feature.
- powertools JSON request lines and StructuredLogger/log_structured JSON
  lines are byte-identical to pre-change (no wrapper, no nesting).
- Delta is strictly additive: `[INFO]` lines from first-party modules plus
  one C-8 self-test line per cold start.

## Out-of-contract (explicitly not provided)

- No correlation-ID injection on module lines (signposted O3 migration).
- No JSON structuring of stdlib lines (signposted O1/O3 migration).
- Prevention (vs detection) of a future Lambda omitting the call: the C-7
  glob catches any new `src/lambdas/<name>/handler.py` in CI, which is
  detection at PR time — accepted as the strongest guard available without
  the platform-level mechanism (signposted O1).
