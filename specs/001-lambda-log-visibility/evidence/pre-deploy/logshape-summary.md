# T002 Log-Shape Baseline Summary (pre-deploy)

Collected: 2026-07-26T03:50:21.730314+00:00
Method: `aws logs filter-log-events --log-group-name /aws/lambda/preprod-sentiment-<fn>`
(boto3 equivalent), starting at now-1h and widening through 6h/24h/72h/168h until
>=50 events or the 7-day window was exhausted; kept the most recent 50 events.

Shape classes: platform (START/END/REPORT/INIT), powertools/structured JSON
(single-line JSON with `level` key), stdlib `[LEVEL]` prefix, tab-separated
LEVEL (Lambda text-format wrapper), print/other.

| function | window used | events | platform | structured JSON | stdlib [LEVEL] | stdlib tab-LEVEL | print/other |
|---|---|---|---|---|---|---|---|
| dashboard | 6h | 50 | 37 | 12 | 1 | 0 | 0 |
| ingestion | 1h | 50 | 13 | 0 | 37 | 0 | 0 |
| analysis | 6h | 50 | 20 | 21 | 5 | 0 | 4 |
| metrics | 1h | 50 | 34 | 0 | 16 | 0 | 0 |
| notification | 168h | 0 | 0 | 0 | 0 | 0 | 0 |
| canary | 1h | 50 | 15 | 0 | 35 | 0 | 0 |

## Notes

- **metrics**: the 16 stdlib `[LEVEL]` lines are NOT healthy app logging — they are a
  crash loop (`LAMBDA_WARNING: Unhandled exception` + `[ERROR] Runtime.ImportModuleError:
  Unable to import module 'handler': No module named 'aws_lambda_powertools'`). Every
  invocation has failed at import for at least 7 days. See `metrics-dup-baseline.md`.
- **notification**: zero events in the full 7-day window — the function has not been
  invoked (or logs nothing). `logshape-notification.json` records the empty result.
- **dashboard**: structured JSON lines are aws-lambda-powertools Logger output
  (`"level"`, `"service"`, `"timestamp"` keys). The single stdlib line was a `[WARNING]`.
- **ingestion / canary**: no structured JSON at all; application output is entirely
  stdlib `[LEVEL]` text format.
- Raw samples: `logshape-<fn>.json` (each contains `windowUsed`, `eventCount`, and the
  raw `filter_log_events` events, most recent <=50).
