# Diagram Drift Map

Per-file DRIFT findings only. `Claim | Diagram locus | Live source | Correction`. Verdict noted where PLAUSIBLE; unmarked rows are CONFIRMED.

## README.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| "Container Images" subgraph builds exactly two Lambda images (SSE + Analysis). | README.md:27-30 (nodes sse_img, analysis_img); edges 44-47 | deploy.yml three build jobs :497/:594/:672 (SSE, Analysis, Dashboard); deploy node :753 needs all three; three Dockerfiles under src/lambdas | Add a third image-build node for the Dashboard Lambda. Pipeline builds SSE + Analysis + Dashboard (three build jobs, three Dockerfiles); diagram draws two. |
| Storage Layer titled "5 Tables", draws 4 DynamoDB nodes + DLQ. | README.md:233 label; 234-238 four DDB nodes + DDBLQ | dynamodb/main.tf 6 tables (:4,:259,:374,:442,:524,:591) | Live count is 6 tables. Diagram draws 4 (omits chaos_experiments, chaos_reports); label says 5. Neither matches 6. |

## docs/architecture/DATA_FLOW_AUDIT.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Metrics Cache TTL is 30s. | Lines 58, 135, 229, 238 | metrics.py:57 default 300; comment :53 "60s -> 300s" | Live default is 300s (5 min), never 30s. All four loci should read 300s / 5 min. |
| Circuit Breaker under "Pending Implementation", "TTL: In-memory", DFA-008 deferred. | Line 152 (P2, Pending subgraph) | circuit_breaker.py:316-321 write-through to DynamoDB; save_state:438 -> put_item:452; get_item:372; cache TTL 60s :37 | Circuit breaker persists to DynamoDB (write-through). Not pending / not in-memory-only. Remove Pending placement and DFA-008 tag; in-memory read cache is 60s. |
| API Response Cache "1hr TTL". *(PLAUSIBLE)* | Line 31 (APIC, ingestion flow) | tiingo.py:31 news 1800s (30min), :32 OHLC 3600s; finnhub.py news 1800 | APIC sits on the news-fetch edge; news cache is 1800s (30min), not 1hr. 1hr applies only to OHLC. Block 2 P1 label "30min/1hr" is the accurate version. |
| Ticker Cache "TTL: Container lifetime" (M4, EXISTING). | Line 138 (M4) | ticker_cache.py:27 default 300s; docstring :5-7 Feature 1224 replaced cold-start @lru_cache with TTL + S3 ETag | Ticker cache is 300s (5 min) with S3 ETag refresh, not container-lifetime. "Container lifetime" is the superseded @lru_cache design. |
| sentiment-users GSIs are three: by_email, by_cognito_sub, by_entity_status. | Lines 269-272 (SU_GSI subgraph) | feature_006_users: by_email:309, by_cognito_sub:317, by_entity_status:328, by_provider_sub:338 | Table has FOUR GSIs; diagram omits by_provider_sub (Feature 1180 OAuth linking). Block 1's flat GSI box also mixes items+users indexes and omits by_cognito_sub/by_provider_sub. |

## docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| 3x Lambda Functions. | Line 264 (node G) | main.tf 7 lambda module calls (:309,:366,:425,:530,:579,:775,:1114) | 7 Lambda functions, not 3. |
| 1x DynamoDB Table. | Line 265 (node H) | dynamodb/main.tf 6 tables (:4,:259,:374,:442,:524,:591) | 6 tables, not 1. |
| 2x Secrets Manager. | Line 266 (node I) | secrets/main.tf 8 secrets (:4,:40,:71,:102,:133,:165,:207,:234) | 8 secrets, not 2. |
| 1x EventBridge Rule. | Line 269 (node L) | eventbridge/main.tf 4 rules (:3,:43,:83,:131) | 4 rules, not 1. |
| 8x CloudWatch Alarms. | Line 270 (node M) | 44 aws_cloudwatch_metric_alarm across modules (3+3+2+1+3+15+3+1+3+10) | 44 static alarm declarations, not 8. |
| 1x SNS Topic + DLQ. | Line 268 (node K) | sns/main.tf:20 analysis_requests, monitoring/main.tf:5 alarms; DLQ sns/main.tf:5 | 2 SNS topics + 1 SQS DLQ; undercounts topics by one. |
| Root main.tf calls exactly 7 modules. | Lines 302-318 (Modules subgraph) | 17 module dirs; 24 module calls in main.tf | The 7 shown exist but diagram omits 10 dirs (amplify, api_gateway, chaos, cloudfront_sse, cloudwatch-alarms, cloudwatch-rum, cognito, kms, waf, xray); 24 calls total. |
| Deploy gated by path filter "src/** or terraform/**"; else Skip Deploy. | Lines 11-13; 413 quick-ref | deploy.yml:22-40 "on: push branches [main]", paths-ignore removed, deploy on ALL pushes | No path filter; every push to main deploys. No "Skip Deploy" branch. |
| Pipeline is "Deploy Dev" workflow to a dev environment. | Line 16; :335 gantt; :413 quick-ref | deploy.yml deploy-preprod (:751) + deploy-prod (:1798); no deploy-dev; ENVIRONMENT:dev only on moto test step :442 | Pipeline targets preprod + prod (dev removed). "Deploy Dev" naming is stale; lone dev token is a moto-test env var. |
| Build = "Package Lambda Functions -> Upload to S3" (S3-zip for all). | Lines 24-25; block 2 node A :64 | deploy.yml container builds :497/:594/:672 (SSE/analysis/dashboard); zip for ingestion/analysis-legacy/metrics/notification/canary | Hybrid deploy: SSE/dashboard/analysis ship as ECR images; ingestion/metrics/notification/canary use S3 zip. Diagram omits the Docker image path. |

## docs/operations/OPERATIONAL_FLOWS.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Ingestion Errors >5 in 5 min. | Line 559 | monitoring/main.tf:64-88 threshold=3, period=300 | Threshold is >3 in 5 min. |
| Analysis Errors >5 in 5 min. | Line 560 | monitoring/main.tf:90-114 threshold=3, period=300 | Threshold is >3 in 5 min. |
| Analysis Duration >5 seconds. | Line 561 | monitoring/main.tf:146-155 p95=25000 (25s); main.tf:410 duration_alarm=10000 (10s) | No 5s alarm. P95 latency is 25s; module duration alarm is 10s. |
| Dashboard Errors >10 in 5 min. | Line 562 | monitoring/main.tf:116-140 threshold=5, period=300 | Threshold is >5 in 5 min. |
| Metrics Errors >3 in 5 min. | Line 563 | cloudwatch-alarms/main.tf:60-82 threshold=var default=1, eval_periods=2, period=300 | Only metrics error alarm fires at >1 over 10 min. Correct to ">1 in 10 min" or drop threshold. |
| Read Throttle Events (an alarm). | Line 567 | grep ReadThrottleEvents returns none; dynamodb/main.tf has only user_errors/system_errors/write_throttles | No Read-Throttle-Events alarm exists. Remove node or repoint to dynamodb-high-read-capacity. |
| Write Throttle Events (throttle-event alarm). *(PLAUSIBLE)* | Line 568 | dynamodb/main.tf:219-239 metric=ConsumedWriteCapacityUnits, threshold=1000 | "write-throttles" alarm watches consumed write capacity (>1000 WCU/min), not WriteThrottleEvents. Label is a semantic mismatch (resource is named write-throttles). |
| Stuck Items >10 for 3 periods (CloudWatch alarm). | Line 572; metrics flow :90-91; :112 | grep StuckItems returns no alarm; metrics/handler.py:60 emits metric only | StuckItems metric is emitted but no alarm defined. Add alarm or drop the node/threshold from both diagrams. |

## docs/security/DASHBOARD_SECURITY_ANALYSIS.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| API Gateway "Throttling: 100 req/min". | Line 361 | main.tf:896 rate_limit=100 "Requests per second"; api_gateway/main.tf:842-844 | It is 100 req/SECOND (~6000/min). Read "100 req/sec". |
| Secrets Manager "Auto-Rotation" (current prod arch). | Line 363 | main.tf:104 rotation_lambda_arn=null; secrets/main.tf rotation resources count=0 (all six) | No rotation deployed; all rotation resources resolve to count=0. Remove label or wire a rotation Lambda. |
| Internet -> CloudFront -> WAF -> API Gateway -> Dashboard (CloudFront fronts REST). | Lines 357-360 | main.tf:961 cloudfront_sse origin=SSE function_url; no api_gateway in cloudfront_sse module; REST path WAF REGIONAL on stage_arn | CloudFront fronts only the SSE Lambda URL. REST path is Amplify -> API Gateway (WAF REGIONAL) -> Dashboard, no CloudFront. Flow direction misrepresents live infra. |

## docs/chaos-testing/PHASE3_API_FAILURE.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| User starts "api_failure" experiment; Dashboard sets status="running" via dynamodb_flag injection. | Lines 46-47 (+ prose 70-77) | chaos.py:1646-1654,1785-1886 only 5 scenario_types (none api_failure); grep api_failure/dynamodb_flag empty | No api_failure scenario or dynamodb_flag method exists. Remove the sequence or restore the scenario in chaos.py. |
| Ingestion Lambda queries by_status GSI, gets experiment status="running", re-queries on stop. | Lines 50-51,59-60 | No chaos query in ingestion; chaos_injection.py and financial_handler.py don't exist; self_healing.py:117,136 queries by_status for pending NEWS items only | Ingestion performs no chaos-experiment status query; named helper/function/handler all absent. Its real by_status queries serve self-healing of pending news, unrelated. |
| When chaos active, Ingestion skips Tiingo/Finnhub fetch, returns 0 articles, resumes on stop. | Lines 52-53,61-62 | grep chaos in ingestion empty; is_chaos_active defined nowhere | No chaos-keyed skip/resume branch exists; fetch always runs normally. |

## docs/chaos-testing/PHASE4_LAMBDA_DELAY.md

| Claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| On start Dashboard writes delay_ms=2000 to DynamoDB as coordination signal. | Lines 40-41 | chaos.py:1837-1848 lambda_cold_start calls update_function_configuration(MemorySize=128); stores set_memory_128, no delay_ms | Dashboard reduces analysis Lambda MemorySize to 128MB (set_memory_128) to force cold starts; no delay_ms field written. |
| AnalysisLambda queries by_status GSI, DynamoDB returns status="running", delay_ms=2000. | Lines 44-45,53-54 | handler.py:82 entrypoint, no chaos/delay read; chaos_injection.py absent | Analysis Lambda does not read the chaos table for this scenario. Remove the Lambda-side by_status query; cold starts induced externally via control-plane memory reduction. |
| AnalysisLambda injects delay via time.sleep(2.0) at handler entry. | Line 46 | handler.py grep chaos/time.sleep/delay empty; only mechanism is chaos.py:1841-1843 MemorySize=128 | No application-level sleep. Replace with the real mechanism: control-plane memory reduction to 128MB causing AWS-level cold-start latency. |

## Summary

- **Files with DRIFT:** 7 of 8 chart files (docs/diagrams/TEMPLATE.md had no findings).
- **Total DRIFT rows:** 34 (32 CONFIRMED, 2 PLAUSIBLE).
- **Confirmed drifts:** 32.
- **Plausible drifts:** 2, DATA_FLOW_AUDIT.md API Response Cache "1hr" (imprecise: OHLC 1hr vs news 30min in same adapter), OPERATIONAL_FLOWS.md "Write Throttle Events" (label vs consumed-WCU metric on a resource literally named write-throttles).

Per-file confirmed-drift counts:

| File | DRIFT rows | Confirmed | Plausible |
|---|---|---|---|
| README.md | 2 | 2 | 0 |
| docs/architecture/DATA_FLOW_AUDIT.md | 5 | 4 | 1 |
| docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md | 10 | 10 | 0 |
| docs/operations/OPERATIONAL_FLOWS.md | 8 | 7 | 1 |
| docs/security/DASHBOARD_SECURITY_ANALYSIS.md | 3 | 3 | 0 |
| docs/chaos-testing/PHASE3_API_FAILURE.md | 3 | 3 | 0 |
| docs/chaos-testing/PHASE4_LAMBDA_DELAY.md | 3 | 3 | 0 |
| **Total** | **34** | **32** | **2** |

Dominant drift patterns: stale resource counts (TERRAFORM_DEPLOYMENT_FLOW every count node wrong except S3/Budget/Backup), stale TTLs and cache descriptions (DATA_FLOW), alarm-threshold mismatches (OPERATIONAL), and chaos-testing diagrams describing an unimplemented DynamoDB-flag coordination path that the shipped chaos.py replaced with control-plane injection (memory reduction, concurrency zero, IAM deny, EventBridge disable).
