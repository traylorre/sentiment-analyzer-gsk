# URL & Endpoint Surface Inventory

Source: reconciled `urls` domain. All 11 findings carry verdict CONFIRMED. State column uses the finding's reconciled state (LIVE / DISABLED / ORPHANED, plus one DRIFT).

| Surface | Emitter | Consumer | State | Citation | Notes |
|---|---|---|---|---|---|
| Dashboard Lambda Function URL | `create_function_url=false` (disabled by Feature 1300; zombie since 1253/1256) | None, module output guards on `var.create_function_url`, returns null | DISABLED | `infrastructure/terraform/main.tf:508` | `:509` `AWS_IAM` auth exists only to satisfy Checkov (count=0). Output-removed comment at `main.tf:1458`; guard at `modules/lambda/outputs.tf:47`. |
| SSE streaming Lambda Function URL | `create_function_url=true`, `AWS_IAM`, `RESPONSE_STREAM` | CloudFront origin (`main.tf:961`) and dashboard env `SSE_LAMBDA_URL` (`main.tf:501`) | LIVE | `infrastructure/terraform/main.tf:824` | Feature 1256 CloudFront OAC. Emitted via `modules/lambda/outputs.tf:45-47`. |
| API Gateway REST (primary API) | `aws_api_gateway_stage.dashboard.invoke_url` | `NEXT_PUBLIC_API_URL` → `constants.ts:1` `API_URL` → `client.ts:120` | LIVE | `infrastructure/terraform/modules/api_gateway/outputs.tf:13` | Wired `main.tf:1295`, emitted `amplify/main.tf:63`. Cognito auth on (`main.tf:870`), public_routes `main.tf:874-893`. |
| CloudFront SSE distribution URL | `NEXT_PUBLIC_SSE_URL=var.sse_cloudfront_url` | None in `frontend/src`, grep returned zero hits | ORPHANED | `infrastructure/terraform/modules/amplify/main.tf:64` | CloudFront module itself is LIVE (`main.tf:957`), but the wire to the frontend is dead. Frontend SSE base comes from `runtime-store.ts:74-85` instead. |
| Cognito hosted-UI / client config | `NEXT_PUBLIC_COGNITO_*` → `COGNITO_CONFIG` (`constants.ts:3`) | None, grep found only the definition, no import/use | ORPHANED | `frontend/src/lib/constants.ts:3` | Env vars emitted (`amplify/main.tf:65-67`) and parsed, resulting object never referenced. |
| Runtime discovery endpoint `/api/v2/runtime` | `get_runtime_config` (def `handler.py:613`) | Frontend `getSseBaseUrl` (`runtime-store.ts:78-85`) | DRIFT | `src/lambdas/dashboard/handler.py:626` | Non-dev returns `sse_url=None`; dev returns raw IAM Lambda URL, never CloudFront. Prod falls back to API Gateway. Contradicts `amplify/main.tf:59` comment "CloudFront is the sole SSE endpoint". |
| Next.js same-origin SSE proxy `/api/sse/[...path]` | Reads `process.env.SSE_LAMBDA_URL` | Returns 503 when unset, always unset in Amplify env | ORPHANED | `frontend/src/app/api/sse/[...path]/route.ts:30` | Amplify emits only `NEXT_PUBLIC_*` (`amplify/main.tf:62-72`), no `SSE_LAMBDA_URL` → proxy env always undefined → 503. Branch only taken when proxy toggle true. |
| `NEXT_PUBLIC_USE_SSE_PROXY` toggle | Consumed at `use-sse.ts:106` | Never emitted, grep of Terraform returned none | ORPHANED | `frontend/src/hooks/use-sse.ts:106` | Not in Amplify env (`amplify/main.tf:62-72`) → always falsy → proxy branches (`use-sse.ts:111-113,123`) dead. Frontend uses direct token-in-URL SSE. |
| Admin / HTMX dashboard root routes (`/`, `/favicon.ico`, `/static/*`, `/api`) | `serve_index` (def `handler.py:385`) and siblings | 404 in non-dev via `_make_not_found_response` | DISABLED | `src/lambdas/dashboard/handler.py:387` | Fail-closed `_is_dev_environment` (`:139-147`): preprod/prod/unset → 404. Also only reachable via API Gateway since dashboard Function URL disabled. |
| SSE Lambda config-specific stream route | Dispatch handles `/api/v2/stream/status`, `/api/v2/stream`, config stream via `_match_config_stream_path` | Frontend builds `/api/v2/configurations/{configId}/stream` (`use-sse.ts:117`) and `/api/v2/stream` (`:124`) | LIVE | `src/lambdas/sse_streaming/handler.py:560` | Routes align. Reachability depends on baseUrl, see the runtime `/api/v2/runtime` DRIFT row (prod baseUrl falls back to API Gateway). |
| Amplify hosting URL | `amplify_production_url` output = `module.amplify_frontend[0].production_url` | Cognito callback provisioner (`main.tf:1330-1333`), notification Lambda `DASHBOARD_URL` (`main.tf:1372-1376`) | LIVE | `infrastructure/terraform/main.tf:1645` | Amplify WEB_COMPUTE SSR (`amplify/main.tf:32`), count-gated on `var.enable_amplify` (`main.tf:1286`). |

## State Summary

| State | Count | Surfaces |
|---|---|---|
| LIVE | 4 | SSE Lambda Function URL, API Gateway REST, SSE config stream route, Amplify hosting URL |
| DISABLED | 2 | Dashboard Lambda Function URL, Admin/HTMX dashboard root routes |
| ORPHANED | 4 | CloudFront SSE distribution URL, Cognito config, Next.js SSE proxy, `NEXT_PUBLIC_USE_SSE_PROXY` toggle |
| DRIFT | 1 | `/api/v2/runtime` discovery endpoint |

## Cross-Cutting SSE Note

Four separate SSE plumbing surfaces are all dead or drifting at once: the CloudFront SSE URL is emitted but unconsumed, the same-origin proxy always 503s, the proxy toggle is never emitted, and the runtime endpoint hands prod a null/`API Gateway` fallback instead of CloudFront. Net effect: prod SSE resolves through `getSseBaseUrl` → `NEXT_PUBLIC_API_URL` (API Gateway), not the intended CloudFront path. The `amplify/main.tf:59` "CloudFront is the sole SSE endpoint" comment is not what the code does.

## Open Questions

None. Every finding in the `urls` domain resolved to verdict CONFIRMED, there are no UNKNOWN verdicts to escalate. The one non-terminal state is the `/api/v2/runtime` DRIFT (CONFIRMED as a drift, not an open question): the fix is a decision, wire CloudFront into the runtime response or update the `amplify/main.tf:59` comment to match the API Gateway fallback the code actually uses.
