# Dead Code Map, `src/` production reachability

**Import-graph method (dotted + bare):** name-token refmap over `src/` + `tests/` (120 non-`__init__` modules). For each candidate, two grep passes: (1) **dotted**, `from src.lambdas.<pkg>.<mod> import` and `<pkg>.<mod>` module-path references; (2) **bare**, the exported symbol token (`\b<sym>\b`), excluding the defining module and any `__init__.py` re-export line. A target is production-DEAD when both passes return only its own definition + `tests/` consumers, with zero `src/` importer on the live handler chain. Coarser than a full AST resolver (a matched token need not be a real import), so it can false-positive toward LIVE, never toward DEAD, every DEAD verdict below is the strict case (only test imports found).

**Verdict key:** `DEAD` = zero production reachability, imported only by tests (production-dead / test-only). No `src/` module is *absolutely* unreferenced. `LIVE` = structural confirmation that no rescue channel exists. `UNKNOWN` = not applicable here; all targets resolved.

## Dead-code targets

| Target | Verdict | Evidence (grep / import) |
|---|---|---|
| `src/lambdas/ingestion/collector.py` (`FetchResult`:31, `fetch_news`:49, `create_orchestrator`:107, `create_collection_event`:135) | DEAD | `handler.py` imports dedup/alerting/metrics/parallel_fetcher/self_healing/shared.adapters.* (lines 83-112), never `collector`. Only refs: `tests/unit/ingestion/test_collector.py`, `tests/integration/ingestion/test_collection_flow.py`. |
| `src/lambdas/ingestion/audit.py` (`CollectionEventRepository`:23, `create_collection_event_repository`:183) | DEAD | `grep -rnE 'ingestion\.audit\|from src.lambdas.ingestion.audit' src tests` → only `tests/unit/ingestion/test_audit.py:14`. No `src` importer; `handler.py` does not import it. |
| `src/lambdas/ingestion/adapters/base.py` (`BaseAdapter`:26, `AdapterError`:76, `RateLimitError`:82, `AuthenticationError`:90, `ConnectionError`:96), dead duplicate of `shared/adapters/base.py` | DEAD | `handler.py:96` imports `from src.lambdas.shared.adapters.base import (...)`. Only ref to `ingestion.adapters.base`: `tests/unit/lambdas/shared/test_adapter_base.py:5`. |
| `src/lambdas/notification/alert_evaluator.py` (`evaluate_alerts_for_ticker`:111; cite :43 = `class SentimentUpdate`, imprecise) | DEAD | `notification/handler.py` imports digest_service/sendgrid_service/env_validation/metrics, NOT alert_evaluator. `grep -rnE 'alert_evaluator' src` (excl file) → nothing. Only import: `tests/unit/notification/test_alert_evaluator.py`. (`test_xray_tracer_standardization.py:140` is a string-literal path, not an import.) |
| `src/lambdas/shared/auth/audit.py` `create_role_audit_entry`:13 | DEAD | `auth/__init__.py` re-exports cognito/csrf/enums/merge/roles, NOT audit. `grep -rnE 'auth\.audit\|create_role_audit_entry' src` → only def + own docstring (33-39). Sole consumer: `tests/unit/shared/auth/test_audit.py`. |
| `src/lambdas/shared/schemas.py` (7 models: `SentimentItemCreate`:34, `SentimentItemUpdate`:138, `SentimentItemResponse`:184, `SNSAnalysisMessage`:252, `MetricsResponse`:285, `HealthResponse`:342, `ErrorResponse`:372) | DEAD | `grep -rnE 'shared\.schemas\|from src.lambdas.shared.schemas' src` (excl file) → nothing. Test: `tests/unit/test_schemas.py`. |
| `src/lambdas/sse_streaming/resolution_filter.py` `should_send_event`:19 | DEAD | Exact-token `grep -rnE 'should_send_event' src` → only the def. `resolution_filter import` only in `tests/unit/test_sse_resolution_filter.py:16`. (Prior broad hits were the unrelated `resolution_filters` connection field.) |
| `src/lib/deduplication.py` (`generate_source_id`:41, `is_duplicate`:133, `extract_hash`:156) | DEAD | `grep -rnE 'lib\.deduplication\|deduplication import' src` (excl file) → nothing. Sole ref: `tests/unit/test_deduplication.py`. Live dedup = `ingestion/dedup.py` + `shared/utils/dedup.py`. |
| `src/lib/timeseries/preload.py` (`get_adjacent_resolutions`:34, `get_adjacent_time_ranges`:63, `PreloadPriority`:95, `get_preload_priority`:104, `get_preload_priority_for_scroll`:130) | DEAD | `timeseries/__init__.py` re-exports aggregation/bucket/cache/fanout/models, NOT preload. `grep -rnE 'timeseries\.preload\|from src.lib.timeseries.preload' src` (excl file) → nothing. Tests: test_preload_strategy.py, test_timeseries_pagination.py, test_quota_tracker_hysteresis.py. |
| `src/lambdas/shared/errors_module.py` 7 convenience fns (`not_found_error`:206, `unauthorized_error`:233, `rate_limit_error`:259, `internal_error`:297, `database_error`:335, `secret_error`:364, `model_error`:399) | DEAD | All 7: `grep -rnE` across `src` (excl errors_module.py + errors/__init__.py) → NONE. Siblings `error_response`/`validation_error` also production-uncalled: errors package's only `src` importer `router_v2.py:51` imports session exception classes only; live `error_response(...)` resolves to `shared/utils/response_builder.py`; `alerts.py` `validation_error` is a local var. |
| `src/lambdas/shared/errors_module.py` `ErrorCode` enum:46 | DEAD | `grep -rnE '\bErrorCode\b' src` (excl file) → only `errors/__init__.py:25,39` re-export. Used internally only by `errors_module.error_response`, itself never called in production. |
| `src/lambdas/shared/utils/__init__.py` re-exports (`handle_request`:8, `validate_apigw_event`:16, `check_response_size`:19, `decode_path_param`:25) | DEAD | For each, `grep -rnE '\b<sym>\b' src` excluding def-module and `utils/__init__.py` → NONE. Zero production consumers; tests only. |

## Structural confirmations (no rescue channel)

| Target | Verdict | Evidence (grep / import) |
|---|---|---|
| Whole-`src` census: no absolutely-dead module | LIVE | `find src -name '*.py' \| wc -l` = 141. Refmap over 120 non-`__init__` modules found 0 with zero external references. Every orphan above IS test-imported, so "production-dead / test-only," not absolutely unreferenced. |
| No dynamic-dispatch rescue | LIVE | `grep -rnE 'importlib\|__import__\|import_module' src` → nothing. `handler.py:189` = `getattr(context, 'aws_request_id', ...)`, a runtime attr on the Lambda context, not module-name dispatch. |
| No Dockerfile hidden entrypoint | LIVE | SSE Dockerfile copies only `lib/timeseries` (59) + `lib/metrics.py` (62), not `lib/deduplication.py` / `lib/timeseries/preload.py`. dashboard/analysis Dockerfiles `COPY lib` wholesale with `CMD ["handler.lambda_handler"]`; verified handler import chains never reach the orphans. |

## Caveats (do not change DEAD verdicts)

- **`ingestion/adapters/base.py`**, flagged as a *duplicate* of `shared/adapters/base.py`; semantic diff of the two files (redundant vs intentionally divergent) not re-verified. Production-dead either way.
- **`shared/schemas.py`**, finding also asserts contract-test imports; only `tests/unit/test_schemas.py` re-verified. Production-orphan unaffected. Possibly superseded by `response_models.py`.
- **Product intent (git/PR)** for collector.py, audit.py, alert_evaluator.py, resolution_filter.py, preload.py, whether each is unwired-future-feature vs deletable is a judgment call, not established here.
- **`errors_module` / `ErrorCode`**, the source finding's hedge to reclassify these LIVE via `error_response`/`validation_error` is refuted: those siblings are themselves production-uncalled.
