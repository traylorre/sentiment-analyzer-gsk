# T004 SC-005 p50 Baseline: INFO events per dashboard invocation (pre-deploy)

Collected: 2026-07-26T03:54:23.848717+00:00
Function: `preprod-sentiment-dashboard` qualifier `live` (direct boto3 `lambda.invoke`,
RequestResponse, API Gateway REST v1 event built by
`tests/e2e/helpers/lambda_invoke_transport._build_apigw_rest_event`).
Route: `GET /health` (cheap read-only; DynamoDB table_status check only).
Invocations: 20 identical requests, serial.

## Methodology

Each invoke's Lambda request id was taken from `ResponseMetadata.RequestId`
(equals the function's `aws_request_id`). 45s after the last invoke, all events in
`/aws/lambda/preprod-sentiment-dashboard` for the window [start-10s, end+60s] were pulled
(83 events) and every non-platform line containing the request id was
classified: stdlib `[INFO]`-prefixed vs powertools single-line JSON with
`"level":"INFO"` vs other.

## Results (per invocation)

| metric | p50 | min | max | mean |
|---|---|---|---|---|
| stdlib `[INFO]` lines | 0.0 | 0 | 0 | 0.00 |
| powertools JSON INFO lines | 1.0 | 1 | 1 | 1.00 |
| invoke wall latency (ms) | 154 | 127 | 3321 | 311.1 |

Status codes: [200];
FunctionError: ['None'].

**SC-005 baseline p50 (stdlib INFO events per invocation): 0.0**
**Powertools JSON INFO events per invocation (p50): 1.0**

Raw per-invocation data: `dashboard-p50-raw.json`.
