# T025 SC-005 p50 Delta: INFO events per dashboard invocation (post-deploy)

Collected: 2026-07-29T14:04–14:06Z (UTC). Fix live since 2026-07-26 ~07:35Z.
Function: `preprod-sentiment-dashboard` qualifier `live` (boto3 `lambda.invoke`,
RequestResponse, API Gateway REST v1 event via
`tests/e2e/helpers/lambda_invoke_transport._build_apigw_rest_event`).
Route: `GET /health`. Invocations: 20 identical requests, serial.
Same method as pre-deploy `dashboard-p50-baseline.md`: request id from
`ResponseMetadata.RequestId`, 45s settle, all group events in [start-10s, end+60s]
pulled (85 events; pre-deploy pulled 83), every non-platform line containing the
request id classified stdlib `[INFO]` vs powertools JSON `"level":"INFO"` vs other.

## Results (per invocation)

| metric | p50 | min | max | mean | pre-deploy p50 | delta |
|---|---|---|---|---|---|---|
| stdlib `[INFO]` lines | 0.0 | 0 | 1 | 0.05 | 0.0 | **0.0** |
| powertools JSON INFO lines | 1.0 | 1 | 1 | 1.00 | 1.0 | **0.0** |
| invoke wall latency (ms) | 155.9 | 140.1 | 3469.2 | 324.6 | 154 | +1.9 |

Status codes: [200]; FunctionError: [None]. Raw per-invocation data:
`t025-p50-raw.json`.

The single non-zero stdlib count was invocation 0 (the cold start, 3469ms wall /
2120ms Init): one newly visible botocore line,
`[INFO]\t2026-07-29T14:04:32.837Z\t<rid>\tFound credentials in environment variables.`
Warm invocations emit exactly what they did pre-deploy: one powertools JSON INFO
("Dashboard Lambda invoked"), zero stdlib lines.

## SC-005 verdict

**PASS.** p50 INFO events per invocation: stdlib 0.0 (unchanged), powertools 1.0
(unchanged). Delta = 0, well under the ≤10 ceiling; even the worst case (cold start)
adds exactly 1 line. Root INFO visibility costs nothing on the warm request path for
this function.
