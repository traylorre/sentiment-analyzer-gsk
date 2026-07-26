# Data Model: Lambda Log Visibility

No persistent data entities — observability-only feature. The "model" is the
logging configuration state machine per process.

## Entities

### LoggingConfiguration (per Lambda process, in-memory)

| Field | Type | Rules |
|---|---|---|
| root_level | int | INFO (20) after helper runs; overridable via LOG_LEVEL env, floor INFO for prod-normal ops (DEBUG requires explicit deliberate value; FR-002 default holds) |
| pinned_loggers | map[str,int] | `httpx`→WARNING, `httpcore`→WARNING (FR-010); pins win because those loggers get their OWN explicit level (application order is not load-bearing — AR#2 F14) |
| selftest_emitted | bool | once-per-process latch for the C-8 self-test line ONLY; level assertions (C-1/C-2) re-assert on every call (AR#2 F5); unit tests reset via the module's documented reset hook |

State transition: `unconfigured → configured` exactly once per process, at
entrypoint import time, before first request. No reverse transition.

### LogLine (emitted; contract with consumers — unchanged by this feature)

| Field | Source | Invariant |
|---|---|---|
| severity tag | runtime Text formatter (`[INFO]`/`[WARNING]`/…) | FR-009 distinguishable; FR-003 semantics unchanged |
| request id | runtime formatter | unchanged |
| message | application | FR-012: no secrets/credentials; masked PII in newly visible lines |

### VerificationBaseline (recorded artifact, evidence directory)

| Field | Rules |
|---|---|
| metrics_dup_count | StructuredLogger events per logical event over 24h pre-deploy window (FR-004); post-deploy must be ≤ baseline |
| consumer_inventory_snapshot | the 4-consumer inventory from spec US2; each verified matching post-deploy |

## Relationships

- One LoggingConfiguration per Lambda process; created by the shared helper;
  six entrypoints depend on it (coverage-guard test enforces the edge).
- SSE process explicitly has NO relationship to the helper (FR-006).
