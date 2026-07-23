# Diagram Drift: WS0 Chart Verification (full repo sweep)

Purpose: the WS0 sign-pole verifies charts before trusting them. This register holds every
architecture-diagram claim that drifted from live source, each pinned to a `file:line`. A diagram
is a SUSPECT, same as a comment. Nothing here is a fix; these are corrections the execution run applies.

Method: one agent per diagram-bearing file extracted every mermaid claim and checked it against live
Terraform/source; an independent skeptic re-opened each cited locus and re-counted. Verify then refute.

Result: **56 confirmed drifts** and 135 claims verified accurate across 16 files.

## Confirmed drifts by file

### README.md
blocks checked: 5

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| CI/CD pipeline builds exactly 2 container images: 'Build SSE Lambda Image' and 'Build Analysis Lambda Image' (Block 1, Container Images subgraph) | `README.md:27-30,44-47` | `.github/workflows/deploy.yml:497 (build-sse-image-preprod), :594 (build-analysis-image-preprod), :672 (build-dashboard-i` | Three preprod images are built, not two. Dashboard Lambda image (build-dashboard-image-preprod, src/lambdas/dashboard/Dockerfile, container deploy per Feature 1036) is missing from the diagram. deploy-preprod requires al |
| Storage Layer subgraph labeled '5 Tables' shows 4 DynamoDB tables (sentiment-items, sentiment-users, sentiment-timeseries, ohlc-cache) plus SQS DLQ; legend says | `README.md:233,327` | `infrastructure/terraform/modules/dynamodb/main.tf:4,259,374,442,524,591 (6 aws_dynamodb_table resources: sentiment_items` | Re-counted: 6 aws_dynamodb_table resources exist. Diagram shows only 4 DynamoDB tables and the legend's '5 DynamoDB tables' is wrong versus the real 6. chaos_experiments (main.tf:374) and chaos_reports (main.tf:442) are  |
| Auth flow: 'POST /api/v2/auth/magic-link/verify' (Block 5 sequence) | `README.md:555` | `src/lambdas/dashboard/handler.py:497 ('GET /api/v2/auth/magic-link/verify'); src/lambdas/dashboard/auth.py:7 (GET docstr` | Endpoint is GET, not POST: 'GET /api/v2/auth/magic-link/verify' per handler route table (handler.py:497) and auth.py:7 docstring. |
| Auth flow: 'GET /api/v2/auth/refresh' (Block 5, Token Refresh) | `README.md:566` | `src/lambdas/dashboard/handler.py:500 ('POST /api/v2/auth/refresh'); src/lambdas/dashboard/auth.py:10 (POST docstring)` | Endpoint is POST, not GET: 'POST /api/v2/auth/refresh' per handler.py:500 and auth.py:10. |
| (PLAUSIBLE) Legend: 'Purple nodes: Lambda functions (6 total)' | `README.md:326` | `infrastructure/terraform/main.tf:309,366,425,530,579,775,1114 (7 modules using ./modules/lambda: ingestion, analysis, da` | Re-counted: 7 Lambda function modules exist. Diagram shows and counts 6; canary_lambda (main.tf:1114, '${env}-sentiment-canary', X-Ray health canary) is omitted. Defensible as '6 app functions', but l |

### docs/architecture/DATA_FLOW_AUDIT.md
blocks checked: 4

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Block 1: Ingestion 'API Response Cache' node is labeled '(1hr TTL)' | `docs/architecture/DATA_FLOW_AUDIT.md:31` | `src/lambdas/shared/adapters/finnhub.py:35 (API_CACHE_TTL_NEWS_SECONDS default 1800), :39 (OHLC default 3600); src/lambda` | Confirmed: the ingestion flow fetches news; the news/sentiment API response cache defaults to 1800s (30 min) in both finnhub.py:35 and tiingo.py:31. 1 hour (3600s) is the OHLC TTL only, and OHLC is not fetched in the ing |
| Block 2 / SSE sequence: Metrics Cache TTL is 30s (dashboard in-memory) | `docs/architecture/DATA_FLOW_AUDIT.md:58 (node 'Metrics Cache 30s TTL'), :135 (M1 'TTL: 30s'), :229 & :238 (sequence '< 30s old?' / 'Store 30s TTL')` | `src/lambdas/dashboard/metrics.py:57 (METRICS_CACHE_TTL = int(os.environ.get('METRICS_CACHE_TTL','300'))), :53 (Feature 1` | Now pinned to live source: the dashboard/SSE metrics cache TTL defaults to 300s (5 min), not 30s. Feature 1085 raised it from 60s to 300s to prevent SSE 429 errors (metrics.py:22-23,53-57). handler.py:659 is the only cal |
| Block 3: SSE metrics query pattern = recent_items + by_sentiment x3 + ingestion_rate x2 (6-7 queries) | `docs/architecture/DATA_FLOW_AUDIT.md:211-218 (before-fix), :233-236 (after-fix), :222 (72K derivation)` | `src/lambdas/dashboard/metrics.py:454 (get_recent_items -> 1 query), :461-462 (loop over 3 SENTIMENT_VALUES -> 3 by_senti` | Re-counted against current aggregate_dashboard_metrics: recent_items(1) + by_sentiment x3(3) + ingestion_rate(4) = 8 DynamoDB queries, not 6-7. The recent_items + by_sentiment x3 portion is accurate, but calculate_ingest |

### docs/chaos-testing/PHASE3_API_FAILURE.md
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| User starts an 'api_failure' experiment via the Dashboard (User->>Dashboard: Start api_failure experiment). | `docs/chaos-testing/PHASE3_API_FAILURE.md:46` | `src/lambdas/dashboard/chaos.py:1135-1141 (valid_scenarios = [dynamodb_throttle, ingestion_failure, lambda_cold_start, tr` | 'api_failure' is not a valid scenario_type. Re-read chaos.py:1135-1141: the only accepted values are dynamodb_throttle, ingestion_failure, lambda_cold_start, trigger_failure, api_timeout. Starting 'api_failure' raises Va |
| The Ingestion Lambda queries the by_status GSI to check for a running chaos experiment, and DynamoDB returns status='running' (Ingestion->>DynamoDB: Query by_st | `docs/chaos-testing/PHASE3_API_FAILURE.md:50-51` | `by_status GSI defined at infrastructure/terraform/modules/dynamodb/main.tf:401-407; the ONLY by_status query in src/lamb` | Ingestion does not query the chaos by_status GSI for experiment status. The by_status query that exists in ingestion (self_healing.py) is for pending self-healing items, not chaos. The chaos self-inspection path was remo |
| The Ingestion Lambda skips the Tiingo/Finnhub fetch (and returns 0 articles) while the chaos experiment is active (Ingestion->>Ingestion: Skip Tiingo/Finnhub fe | `docs/chaos-testing/PHASE3_API_FAILURE.md:52-53` | `grep -riE 'chaos|is_chaos_active' src/lambdas/ingestion/ returns no chaos gate; financial_handler.py does not exist; cha` | The 'is_chaos_active -> skip fetch, return 0 articles' path does not exist in live ingestion source. It was deleted in the Feature 1237 external-actor refactor (commit 979a652). The Lambda no longer inspects chaos flags  |
| On resume the Ingestion Lambda re-queries the by_status GSI, finds no running experiments, and resumes fetch (Ingestion->>DynamoDB: Query by_status GSI; DynamoD | `docs/chaos-testing/PHASE3_API_FAILURE.md:59-60` | `No chaos-experiment by_status query in src/lambdas/ingestion/ (only self_healing.py pending-item query at self_healing.p` | Ingestion does not re-query chaos experiment status to decide whether to resume; there is no chaos gate in ingestion at all after the Feature 1237 refactor. |

### docs/chaos-testing/PHASE4_LAMBDA_DELAY.md
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Dashboard stores delay_ms=2000 in the experiment record on start (edge 'Set status=running, delay_ms=2000') | `docs/chaos-testing/PHASE4_LAMBDA_DELAY.md:41` | `src/lambdas/dashboard/chaos.py:1837-1852 lambda_cold_start branch stores results={injection_method:"set_memory_128", fun` | The implemented lambda_cold_start scenario does NOT store delay_ms. It reduces the analysis Lambda memory to 128MB (update_function_configuration MemorySize=128, injection_method="set_memory_128", chaos.py:1841-1847). Di |
| The Analysis Lambda queries the by_status GSI to read the running experiment (edges 'Query by_status GSI' and 'experiment status=running, delay_ms=2000') | `docs/chaos-testing/PHASE4_LAMBDA_DELAY.md:44-45` | `src/lambdas/analysis/handler.py has no chaos/by_status/delay/time.sleep read-path (grep exit 1); get_chaos_delay_ms does` | The Analysis Lambda performs no chaos read-path and never queries the chaos table. Cold-start injection is done externally by the Dashboard reducing the analysis Lambda's memory to 128MB (chaos.py:1841-1843). This data-f |
| The Analysis Lambda executes time.sleep(2.0) to inject the delay | `docs/chaos-testing/PHASE4_LAMBDA_DELAY.md:46` | `src/lambdas/analysis/handler.py, no time.sleep-based chaos delay (grep time.sleep/chaos/delay exit 1); injection is memo` | No time.sleep delay injection exists in the analysis handler. Cold starts are forced via 128MB memory reduction applied by the Dashboard; the Lambda does not self-delay. The get_chaos_delay_ms function shown in the doc ( |
| On next trigger after stop, Analysis Lambda queries by_status, finds no running experiments, and processes with no delay | `docs/chaos-testing/PHASE4_LAMBDA_DELAY.md:52-55` | `src/lambdas/analysis/handler.py has no chaos query (grep exit 1); recovery path is src/lambdas/dashboard/chaos.py:1650-1` | The Analysis Lambda never queries the chaos table on any trigger. Recovery happens when the Dashboard restores the Lambda's original memory size via _restore_memory (called chaos.py:1651, defined 1702), not via the Lambd |

### docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md
blocks checked: 9

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Block 6 (Infrastructure Dependencies, graph TB): AWS Resources Managed = '3x Lambda Functions' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:264` | `infrastructure/terraform/main.tf:310,367,426,531,580,776,1115 (7x source="./modules/lambda")` | Re-counted: 7 lambda module invocations exist (main.tf lines 310,367,426,531,580,776,1115), not 3. |
| Block 6: AWS Resources = '1x DynamoDB Table' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:265` | `infrastructure/terraform/modules/dynamodb/main.tf:4,259,374,442,524,591 (6x aws_dynamodb_table)` | Re-counted: 6 aws_dynamodb_table resources (sentiment_items, feature_006_users, chaos_experiments, chaos_reports, sentiment_timeseries, ohlc_cache), not 1. |
| Block 6: AWS Resources = '2x Secrets Manager' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:266` | `infrastructure/terraform/modules/secrets/main.tf:4,40,71,102,133,165,207,234 (8x aws_secretsmanager_secret)` | Re-counted: 8 aws_secretsmanager_secret resources (dashboard_api_key, tiingo, finnhub, sendgrid, hcaptcha, stripe_webhook, google_oauth, github_oauth), not 2. |
| Block 6: AWS Resources = '1x SNS Topic + DLQ' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:268` | `infrastructure/terraform/modules/monitoring/main.tf:5 (aws_sns_topic.alarms), modules/sns/main.tf:20 (aws_sns_topic.anal` | Re-counted: 2 aws_sns_topic resources exist (alarms + analysis_requests), not 1. |
| Block 6: AWS Resources = '1x EventBridge Rule' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:269` | `infrastructure/terraform/modules/eventbridge/main.tf:3,43,83,131 (4x aws_cloudwatch_event_rule)` | Re-counted: 4 aws_cloudwatch_event_rule resources (ingestion_schedule, metrics_schedule, daily_digest_schedule, canary_schedule), not 1. |
| Block 6: AWS Resources = '8x CloudWatch Alarms' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:270` | `grep -rc 'resource "aws_cloudwatch_metric_alarm"' infrastructure/terraform/modules/ => 44` | Re-counted myself: 44 aws_cloudwatch_metric_alarm resources across modules, not 8. |
| Block 7 (Terraform Module Structure, graph LR): child modules are exactly lambda, iam, dynamodb, sns, secrets, monitoring, eventbridge (7) | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:302-310` | `ls infrastructure/terraform/modules/ => amplify, api_gateway, chaos, cloudfront_sse, cloudwatch-alarms, cloudwatch-rum, ` | Re-counted: 17 module directories exist. The 7 listed all exist, but 10 are omitted: amplify, api_gateway, chaos, cloudfront_sse, cloudwatch-alarms, cloudwatch-rum, cognito, kms, waf, xray. |
| Block 1 (Overview): merge to main triggers 'Trigger Deploy Dev' / 'Deploy Dev Workflow' deploying a dev environment | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:12,16` | `.github/workflows/deploy.yml:7-11 ('Dev environment removed'; flow: push to main -> build -> test -> deploy-preprod -> t` | deploy.yml explicitly removed the dev environment and deploys to preprod then prod. The 'Deploy Dev' naming and the recovery command at doc line 231 using dev/terraform.tfstate.tflock are both wrong; actual lock keys are |
| Block 1 (Overview): deploy path 'Package Lambda Functions' --> 'Upload to S3' (all lambdas ZIP-packaged, uploaded to S3) | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:24-25` | `.github/workflows/deploy.yml:541-542 (sse Dockerfile, push:true), :622-623 (analysis Dockerfile, push:true), :700-701 (d` | 3 lambdas (sse_streaming, analysis, dashboard) deploy as container images built from Dockerfiles and pushed to ECR, not ZIP-to-S3. The single 'Package -> Upload to S3' edge omits the container-image path. |
| Block 1 (Overview): workflow gated by a path filter decision 'Paths changed? src/** or terraform/**' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:11-13` | `.github/workflows/deploy.yml:23-45 (push on main, paths-ignore REMOVED, no paths filter); build job at :13-15 has no if:` | Upgraded from PLAUSIBLE: the path-gate decision drawn does not exist anywhere. paths-ignore was removed at workflow level AND there is no build-job path filter (the deploy.yml comment about a build-job filter is a future |
| Block 2 (Resource Creation Order): Phase 1 Foundation includes a single 'DynamoDB Table' node | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:67` | `infrastructure/terraform/modules/dynamodb/main.tf:4,259,374,442,524,591 (6x aws_dynamodb_table)` | Singular 'DynamoDB Table' understates the 6 tables created by the dynamodb module. |
| Block 2: Phase 1 'S3 Buckets' node lists 'Lambda Deployments' and 'ML Model Storage' | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:64` | `infrastructure/terraform/main.tf:215 (aws_s3_bucket.lambda_deployments COMMENTED OUT), main.tf:247-248 (model_s3_bucket ` | lambda_deployments bucket is commented out (not Terraform-managed); 'ML Model Storage' exists only as a local variable string (main.tf:248), no aws_s3_bucket resource. The one active app bucket is ticker_cache, which the |
| (PLAUSIBLE) Block 4 (For Developers): push to main -> CI -> deploy success -> integration tests -> done (procedural) | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:166-173` | `.github/workflows/deploy.yml:11 flow comment (push to main -> build -> test -> deploy-preprod -> test-preprod -> deploy-` | Procedural flow structurally matches deploy.yml; no numeric infra claim to contradict. Note the diagram omits the preprod/prod staging, but the developer-facing abstraction is not a false claim. |
| (PLAUSIBLE) Block 5 (On-Call Incident Response): lock recovery via 'aws s3 rm' of lock file, resource import, IAM/policy checks (procedural) | `docs/deployment/TERRAFORM_DEPLOYMENT_FLOW.md:199-214` | `.github/workflows/deploy.yml:876 'aws s3 rm s3://$BUCKET/$LOCK_KEY' guidance; CLAUDE.md documents same recovery; procedu` |  |

### docs/operations/OPERATIONAL_FLOWS.md
blocks checked: 10

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Block3 Deployment: 'Build Lambda Packages (SHA-versioned ZIPs)' uploaded to S3 preprod bucket | `docs/operations/OPERATIONAL_FLOWS.md:158-159` | `.github/workflows/deploy.yml:166/262/315/351 (ingestion/metrics/notification/canary zipped to S3 at :793-813); dashboard` | Confirmed drift. Deployment is mixed: ingestion/metrics/notification/canary are ZIPs to S3, but dashboard and sse are container-only (Docker->ECR, no ZIP), and the analysis Lambda actually runs from an ECR image (main.tf |
| Block3: A live 'Deploy to Production' path (manual approval -> smoke tests -> prod) is part of the pipeline | `docs/operations/OPERATIONAL_FLOWS.md:168-172` | `.github/workflows/deploy.yml:1800 (deploy-prod 'if: false'), :1644 (build-sse-image-prod if:false), :1732 (build-dashboa` | Upgraded from UNKNOWN to CONFIRMED-DRIFT. The prod deploy jobs exist but every one carries a literal 'if: false' guard (deploy-prod:1800, build-sse-image-prod:1644, build-dashboard-image-prod:1732, canary:2005), so the p |
| Block7 DynamoDB Throttling: remediation is to 'Increase WCU/RCU' / 'Increase GSI capacity' when 'At capacity limit' | `docs/operations/OPERATIONAL_FLOWS.md:351-357` | `infrastructure/terraform/modules/dynamodb/main.tf:6 (billing_mode = "PAY_PER_REQUEST"); all sentiment tables are on-dema` | Confirmed drift. sentiment_items is PAY_PER_REQUEST (on-demand) at dynamodb/main.tf:6. There are no provisioned WCU/RCU or GSI capacity settings to increase; describe-table ProvisionedThroughput (the doc's own line 378-3 |
| Block10: Analysis Duration alarm at >5 seconds | `docs/operations/OPERATIONAL_FLOWS.md:561 (and table row :608)` | `infrastructure/terraform/main.tf:410 (duration_alarm_threshold = 10000 = 10 seconds); modules/cloudwatch-alarms/variable` | Confirmed drift. Analysis duration alarm is 10 seconds (main.tf:410, duration_alarm_threshold=10000), not 5. The uniform-module latency alarm is 48s. No 5-second analysis duration alarm exists anywhere. Same 5s error rep |
| Block10: Metrics Errors alarm at >3 in 5 min | `docs/operations/OPERATIONAL_FLOWS.md:563` | `infrastructure/terraform/main.tf:565 (metrics module error_alarm_threshold = 5)` | Confirmed drift. Metrics Lambda error_alarm_threshold = 5 (main.tf:565), not 3. The uniform cloudwatch-alarms module default is 1 (variables.tf:50). Neither is 3. |
| Block10: A dedicated 'Read Throttle Events' DynamoDB alarm feeds SNS | `docs/operations/OPERATIONAL_FLOWS.md:567` | `infrastructure/terraform/modules/dynamodb/main.tf:175 (user_errors=UserErrors), :197 (system_errors=SystemErrors), :219 ` | Confirmed drift. The DynamoDB module defines exactly three alarms (UserErrors, SystemErrors, write-throttles). No ReadThrottleEvents alarm exists. |
| Block10: A 'Write Throttle Events' DynamoDB alarm feeds SNS | `docs/operations/OPERATIONAL_FLOWS.md:568` | `infrastructure/terraform/modules/dynamodb/main.tf:219-228 (aws_cloudwatch_metric_alarm.write_throttles, metric_name = "C` | Confirmed drift. An alarm named 'write-throttles' exists but monitors ConsumedWriteCapacityUnits (a capacity/cost proxy, threshold 1000 WCU/min), not the WriteThrottleEvents metric. It does not alarm on actual throttle e |

### docs/security/DASHBOARD_SECURITY_ANALYSIS.md
blocks checked: 3

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Block 3 ('Recommended Architecture', doc note line 352 asserts it IS 'the current production architecture'): Internet -> CloudFront CDN -> WAF -> API Gateway (C | `docs/security/DASHBOARD_SECURITY_ANALYSIS.md:357-359` | `infrastructure/terraform/main.tf:924-929 (module.waf REGIONAL attached directly to module.api_gateway.stage_arn, no Clou` | Re-verified. No CloudFront fronts API Gateway; the sole CloudFront distribution (cloudfront_sse) fronts only the SSE Lambda Function URL. The API/dashboard path is Internet -> WAF (REGIONAL) -> API Gateway -> Dashboard L |
| Block 3: API Gateway node label 'Throttling: 100 req/min' | `docs/security/DASHBOARD_SECURITY_ANALYSIS.md:359` | `infrastructure/terraform/main.tf:896 (rate_limit = 100 # Requests per second (steady state)), :897 (burst_limit = 200)` | Re-read main.tf:896-897. Throttle is 100 requests per SECOND steady-state / 200 burst, not 100 per minute. The diagram's unit is wrong by 60x. |
| Block 3: API Gateway uses a 'Custom Authorizer' | `docs/security/DASHBOARD_SECURITY_ANALYSIS.md:359` | `infrastructure/terraform/main.tf:871-872 (enable_cognito_auth = true, cognito_user_pool_arn = module.cognito.user_pool_a` | Re-verified. Authorization is a Cognito User Pools (JWT) authorizer (enable_cognito_auth = true, COGNITO_USER_POOLS endpoint_auth), not an API Gateway custom/Lambda authorizer. Since the doc asserts this block is the dep |
| Block 3: Dashboard Lambda node 'API Key Rotation' and Secrets Manager 'Auto-Rotation' | `docs/security/DASHBOARD_SECURITY_ANALYSIS.md:360,362` | `infrastructure/terraform/main.tf:104 (module.secrets is passed rotation_lambda_arn = null # 'No rotation Lambda for Demo` | Upgraded from UNKNOWN: the root value the prior reviewer needed is decisive. main.tf:104 passes rotation_lambda_arn = null, so ALL five aws_secretsmanager_secret_rotation resources evaluate count = 0 and are not created. |

### specs/1028-fix-readme-mermaid-diagram/spec.md
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Container Images stage has exactly two image builds: SSE and Analysis | `specs/1028-fix-readme-mermaid-diagram/spec.md:50-53` | `.github/workflows/deploy.yml:497 (build-sse-image-preprod), 594 (build-analysis-image-preprod), 672 (build-dashboard-ima` | Re-counted: THREE preprod container-image build jobs feed preprod (497, 594, 672) and THREE Dockerfiles exist (analysis, dashboard, sse_streaming). The diagram's Images subgraph (lines 50-53) shows only sse_img and analy |
| Edge: canary --> summary (Summary depends on Canary) | `specs/1028-fix-readme-mermaid-diagram/spec.md:74` | `.github/workflows/deploy.yml:2048 (summary needs); 2044-2045 (comment)` | summary.needs at line 2048 = [build, test, build-sse-image-preprod, build-analysis-image-preprod, build-dashboard-image-preprod, deploy-preprod, test-preprod]. canary is NOT present. The comment above the job explicitly  |
| Missing edge: Dashboard image build --> deploy_preprod | `specs/1028-fix-readme-mermaid-diagram/spec.md:69-70` | `.github/workflows/deploy.yml:753 (deploy-preprod needs)` | deploy-preprod.needs at line 753 = [build, test, build-sse-image-preprod, build-analysis-image-preprod, build-dashboard-image-preprod]. The diagram (lines 69-70) draws only sse_img-->deploy_preprod and analysis_img-->dep |
| Production stage: deploy_prod --> canary --> summary flow after test_preprod, with no prod image-build step | `specs/1028-fix-readme-mermaid-diagram/spec.md:60-64,72-74` | `.github/workflows/deploy.yml:1642 (build-sse-image-prod, if:false@1644), 1730 (build-dashboard-image-prod, if:false@1732` | deploy-prod.needs at line 1801 = [build, deploy-preprod, test-preprod, build-sse-image-prod, build-dashboard-image-prod]. Two prod image-build jobs (1642, 1730) sit between test-preprod and deploy-prod but are absent fro |

### specs/1100-sse-runtime-url/tasks.md
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Edge T002 --> T003 asserts T003 depends on / must follow T002 (sequential) | `specs/1100-sse-runtime-url/tasks.md:20` | `specs/1100-sse-runtime-url/tasks.md:63 ('T002 and T003 can be done in parallel (different files, no dependencies)'); T00` | Remove the T002 --> T003 edge. Prose at L63 explicitly states these are parallel with no dependency, and T003 carries the [P] tag. Both should branch from T001 independently (T001 --> T002 and T001 --> T003). |
| Edge T004 --> T005 asserts T005 depends on / must follow T004 (sequential) | `specs/1100-sse-runtime-url/tasks.md:22` | `specs/1100-sse-runtime-url/tasks.md:64 ('T004 and T005 can be done in parallel after T002/T003 complete')` | Remove the T004 --> T005 edge. Prose at L64 states T004 and T005 run in parallel after T002/T003. Both should depend on T002/T003 completion, not on each other. |

### specs/1215-fix-diagram-inconsistencies/research.md
blocks checked: 4

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Block 1 (lines 64-70, 'Current problematic lines'): a single CloudFront node CF fronts ALL browser traffic, Browser==>|HTTPS|CF, then CF==>|/static/*|Amplify an | `specs/1215-fix-diagram-inconsistencies/research.md:65-70` | `infrastructure/terraform/main.tf:957,961 (module cloudfront_sse, origin_url = module.sse_streaming_lambda.function_url o` | No single CloudFront fronts static+api+stream. The only CloudFront (cloudfront_sse, main.tf:957) fronts the SSE Lambda exclusively (origin_url = sse function_url, main.tf:961). Amplify and API Gateway are reached directl |
| Block 2 (lines 73-78, 'Corrected flow'): Browser ==>|Static| Amplify, the Amplify frontend serves static content. | `specs/1215-fix-diagram-inconsistencies/research.md:74` | `infrastructure/terraform/modules/amplify/main.tf:32 (platform = "WEB_COMPUTE"), :119 (framework = "Next.js - SSR"), :77 ` | Re-verified at exact loci: platform = WEB_COMPUTE (amplify/main.tf:32) and framework = 'Next.js - SSR' (amplify/main.tf:119). Browser->Amplify edge exists and is correct, but 'Static' label mischaracterizes an SSR/WEB_CO |
| Block 2: Browser ==>|/api/v2/stream*| SSELambda, the browser connects directly to the SSE Lambda for streaming. | `specs/1215-fix-diagram-inconsistencies/research.md:76` | `infrastructure/terraform/modules/amplify/main.tf:64 (NEXT_PUBLIC_SSE_URL = var.sse_cloudfront_url); main.tf:957,961 (clo` | Re-verified at exact loci: browser reaches SSE via CloudFront (NEXT_PUBLIC_SSE_URL = sse_cloudfront_url, amplify/main.tf:64); Function URL fallbacks removed because IAM-protected (amplify/main.tf:60). Correct edge: Brows |
| Block 3 (lines 83-88, architecture.mmd 'current/incorrect'): External Services includes NewsAPI ('News Articles'). | `specs/1215-fix-diagram-inconsistencies/research.md:85` | `grep -rln -i 'newsapi' src/ → 0 matches (exit 1); src/lambdas/shared/adapters/ contains only base.py, tiingo.py, finnhub` | Re-ran grep myself: no NewsAPI code in src/ (exit 1, zero matches). Adapters dir listing confirms only tiingo.py + finnhub.py (+ base.py). NewsAPI does not exist in live source (purged, Feature 501). Block correctly self |

### specs/archive/006-user-config-dashboard/plan.md  (archived spec, low priority)
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| Ingestion Lambda entrypoint is 'financial_handler.py' | `specs/archive/006-user-config-dashboard/plan.md:38` | `src/lambdas/ingestion/handler.py:164 (def lambda_handler); find src/lambdas/ingestion + grep -rn financial_handler src/ ` | [ARCHIVAL/low-priority] The ingestion entrypoint is handler.py::lambda_handler (line 164); there is no financial_handler.py anywhere under src/. Diagram node label is stale historical naming. |
| SNS Topic is named 'sentiment-events' and is what the Ingestion Lambda publishes to | `specs/archive/006-user-config-dashboard/plan.md:44 (SNS node) and edge line 90` | `infrastructure/terraform/modules/sns/main.tf:20-21 resource aws_sns_topic "analysis_requests" name="${env}-sentiment-ana` | [ARCHIVAL/low-priority] The processing SNS topic is '{env}-sentiment-analysis-requests' (sns/main.tf:20-21), not 'sentiment-events'. No topic named sentiment-events exists in code or terraform. |
| A CloudFront CDN serves 'Static Assets + API'; Browser->CloudFront, CloudFront->/api/*->DashboardLambda, CloudFront->Static->S3 | `specs/archive/006-user-config-dashboard/plan.md:50 (CloudFront node), edges lines 100-102` | `infrastructure/terraform/modules/ dir contains only cloudfront_sse (no general CDN); cloudfront_sse/main.tf:1-8,81 origi` | [ARCHIVAL/low-priority] No CloudFront distribution serves static assets + /api/*. The customer frontend is on AWS Amplify (main.tf:1284); the browser calls the API via NEXT_PUBLIC_API_URL. The sole CloudFront module (clo |
| Dashboard Lambda runtime is 'FastAPI + Mangum' | `specs/archive/006-user-config-dashboard/plan.md:51 (DashboardLambda node)` | `src/lambdas/dashboard/handler.py:47 imports APIGatewayRestResolver from aws_lambda_powertools, :188 app = APIGatewayRest` | [ARCHIVAL/low-priority] The dashboard Lambda uses AWS Lambda Powertools APIGatewayRestResolver (handler.py:188), not FastAPI + Mangum. |
| A separate 'SNS Alert Topic' (AlertSNS) exists that the Dashboard Lambda evaluates/publishes to, triggering the Notification Lambda | `specs/archive/006-user-config-dashboard/plan.md:58 (AlertSNS), edges lines 112,115` | `grep 'resource "aws_sns_topic"' infrastructure/terraform/ => only modules/sns/main.tf:20 (analysis_requests) and modules` | [ARCHIVAL/low-priority] No dedicated user-alert SNS topic exists (only analysis_requests and the CloudWatch alarms topic). The dashboard Lambda has no SNS publish call. Notification triggering runs via the EventBridge da |
| Analysis Lambda performs Dual-Source Sentiment + ATR Calculation, X-Ray traced | `specs/archive/006-user-config-dashboard/plan.md:45` | `src/lambdas/analysis/handler.py:61-64 imports only analyze_sentiment (single DistilBERT model) + :74 write_fanout; :81 @` | FLIPPED from ACCURATE to CONFIRMED-DRIFT. The prior reviewer relied on CLAUDE.md (a doc, not source) for the ATR claim. Live source shows ATR/volatility lives in the DASHBOARD lambda (src/lambdas/dashboard/volatility.py) |

### specs/archive/1126-auth-httponly-migration/spec-v2.md  (archived spec, low priority)
blocks checked: 1

| Diagram claim | Diagram locus | Live source | Correction |
|---|---|---|---|
| MAGIC_LINK_PENDING --> AUTHED_MAGIC_LINK via 'GET /auth/magic-link/verify/{token}' (token as path parameter) | `specs/archive/1126-auth-httponly-migration/spec-v2.md:531` | `src/lambdas/dashboard/router_v2.py:463-464 route registered as "/api/v2/auth/magic-link/verify" with NO {token} path seg` | ARCHIVAL / LOW-PRIORITY (archived spec, historical record). Re-verified: the deployed route at router_v2.py:463-464 has no path segment for the token, and router_v2.py:481 reads it from the query string. Diagram's '.../v |
| AUTHED_MAGIC_LINK / AUTHED_OAUTH --> UNAUTH: 'Refresh token expires (7d)' | `specs/archive/1126-auth-httponly-migration/spec-v2.md:543` | `src/lambdas/dashboard/auth.py:128 (SESSION_DURATION_DAYS = 30), applied for session/refresh expiry at auth.py:149,368,69` | ARCHIVAL / LOW-PRIORITY (archived spec, historical record). Re-verified: the only session/refresh lifetime constant in deployed code is SESSION_DURATION_DAYS = 30 (auth.py:128), used everywhere the session/refresh expiry |

## Highest-severity (not cosmetic count drift)

- **Chaos docs describe deleted code.** `docs/chaos-testing/PHASE3_API_FAILURE.md` and `PHASE4_LAMBDA_DELAY.md`
  diagram an ingestion/analysis chaos gate (by_status GSI query, `time.sleep` injection) that was removed in
  Feature 1237. The live mechanism is external (Dashboard reduces Analysis memory to 128MB). The docs mislead.
- **Ops runbook gives wrong remediation.** `docs/operations/OPERATIONAL_FLOWS.md` Block7 says increase WCU/RCU on
  throttling; tables are PAY_PER_REQUEST (`dynamodb/main.tf:6`), so there is no capacity to raise. Alarm thresholds
  and the 'Deploy to Production' path (every prod job carries `if: false`) are also wrong.
- **Security doc off by 60x.** `docs/security/DASHBOARD_SECURITY_ANALYSIS.md` says throttle 100 req/min; real is
  100 req/second (`main.tf:896-897`). Claims custom authorizer (real: Cognito JWT) and API-key auto-rotation
  (real: `rotation_lambda_arn = null`, no rotation).
- **Missed docstring drift the comments domain should have caught:** `fanout.py:31,139,224` and README:481 say
  '8 resolutions / 8 bucket updates'; the `Resolution` enum has exactly 6 (`src/lib/timeseries/models.py:24-29`).

## Dead-module check (import graph): honest outcome

An AST import graph flagged `sse_streaming/cache_logger.py`, `latency_logger.py`, `tracing.py` as unreferenced.
The adversarial refute step proved all three **LIVE**: they are imported by *bare* name
(`from cache_logger import ...` at `stream.py:22,24`; `from tracing import ...` at `metrics.py:15`, `polling.py:20`,
`connection.py:251`) because the SSE Dockerfile flattens the package into the task root. The AST script keyed on
dotted module paths and missed bare imports: a methodology bug in the tool, caught by the refuter. Net new
confirmed-dead modules from the import graph: **0**. `storage.py` remains the only confirmed-dead code (seeded run).
Lesson folded into the skill: any import-graph pass must resolve bare/flattened imports before asserting deadness.
