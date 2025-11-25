# Operational Flows and Troubleshooting Guide

This document provides operational flow diagrams and troubleshooting guides for the Sentiment Analyzer system. Use these diagrams to understand system behavior, diagnose issues, and respond to incidents.

**Target Audience:**
- On-call engineers responding to incidents
- Operators managing the system
- Contributors understanding operational patterns

---

## Table of Contents

1. [Common Operational Flows](#common-operational-flows)
   - [Normal Operation Flow](#normal-operation-flow)
   - [Metrics Collection Flow](#metrics-collection-flow)
   - [Deployment Flow](#deployment-flow)
   - [Incident Response Flow](#incident-response-flow)
2. [Troubleshooting Guides](#troubleshooting-guides)
   - [Lambda Failures](#lambda-failures)
   - [DynamoDB Issues](#dynamodb-issues)
   - [S3 Model Loading Issues](#s3-model-loading-issues)
   - [Dashboard Not Responding](#dashboard-not-responding)
3. [Monitoring and Alerts](#monitoring-and-alerts)
4. [Recovery Procedures](#recovery-procedures)

---

## Common Operational Flows

### Normal Operation Flow

This shows the happy path for article ingestion and sentiment analysis:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    Start[EventBridge Trigger<br/>Every 5 minutes] --> Ingest[Ingestion Lambda Invoked]
    Ingest --> FetchAPI[Fetch from NewsAPI]
    FetchAPI --> CheckDup{Duplicate<br/>Check}
    CheckDup -->|New Article| StoreDDB[Store in DynamoDB<br/>status: pending]
    CheckDup -->|Duplicate| Skip[Skip Article]
    StoreDDB --> PublishSNS[Publish to SNS Topic]
    PublishSNS --> AnalysisLambda[Analysis Lambda Triggered]
    AnalysisLambda --> LoadModel{Model in<br/>Memory?}
    LoadModel -->|No| FetchS3[Load from S3<br/>model.tar.gz]
    LoadModel -->|Yes| RunInference
    FetchS3 --> CacheModel[Cache in /tmp]
    CacheModel --> RunInference[Run DistilBERT<br/>Inference]
    RunInference --> UpdateDDB[Update DynamoDB<br/>with sentiment results<br/>status: analyzed]
    UpdateDDB --> LogMetrics[Log CloudWatch Metrics]
    LogMetrics --> End[Complete]
    Skip --> End

    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e
    classDef processNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef storageNode fill:#b39ddb,stroke:#673ab7,stroke-width:2px,color:#1a0a3e

    class Start,End successNode
    class Ingest,AnalysisLambda,FetchAPI,RunInference,CacheModel,LogMetrics,Skip processNode
    class CheckDup,LoadModel decisionNode
    class StoreDDB,UpdateDDB,FetchS3,PublishSNS storageNode
```

**Key Points:**
- Ingestion runs every 5 minutes via EventBridge
- Duplicate detection prevents reprocessing
- Model lazy loading reduces cold start time
- Model cached in Lambda /tmp for warm starts

---

### Metrics Collection Flow

This shows the operational monitoring flow for detecting stuck items:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    Start[EventBridge Trigger<br/>Every 1 minute] --> MetricsLambda[Metrics Lambda Invoked]
    MetricsLambda --> QueryGSI[Query by_status GSI<br/>status = 'pending']
    QueryGSI --> FilterOld[Filter items older than<br/>5 minutes]
    FilterOld --> Count{Stuck items<br/>found?}
    Count -->|Yes| EmitMetric[Emit CloudWatch Metric<br/>StuckItems count]
    Count -->|No| EmitZero[Emit CloudWatch Metric<br/>StuckItems = 0]
    EmitMetric --> LogResults[Log stuck item count<br/>and oldest timestamp]
    EmitZero --> LogResults
    LogResults --> CheckAlarm{StuckItems > 10?}
    CheckAlarm -->|Yes| TriggerAlarm[CloudWatch Alarm<br/>Triggers SNS]
    CheckAlarm -->|No| End[Complete]
    TriggerAlarm --> NotifyOnCall[Notify On-Call<br/>via Email/PagerDuty]
    NotifyOnCall --> End

    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e
    classDef processNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef alertNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff

    class Start,End successNode
    class MetricsLambda,QueryGSI,FilterOld,EmitMetric,EmitZero,LogResults processNode
    class Count,CheckAlarm decisionNode
    class TriggerAlarm,NotifyOnCall alertNode
```

**Key Points:**
- Metrics Lambda runs every 1 minute via EventBridge
- Queries `by_status` GSI for items with `status = 'pending'`
- Stuck threshold: items pending for more than 5 minutes
- Emits `SentimentAnalyzer/StuckItems` CloudWatch metric
- CloudWatch Alarm triggers if stuck items > 10 for 3 consecutive periods

**Stuck Items Causes:**
- Analysis Lambda failures (check DLQ)
- SNS/SQS delivery delays
- DynamoDB throttling preventing status updates
- Lambda concurrency limits reached

**Quick Investigation:**
```bash
# Check current stuck items count
aws cloudwatch get-metric-statistics \
  --namespace SentimentAnalyzer \
  --metric-name StuckItems \
  --dimensions Name=Environment,Value=preprod \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Maximum

# Check Metrics Lambda logs for details
aws logs tail /aws/lambda/preprod-sentiment-metrics --since 30m

# Query DynamoDB directly for stuck items
aws dynamodb query \
  --table-name preprod-sentiment-items \
  --index-name by_status \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":status": {"S": "pending"}}' \
  --select COUNT
```

---

### Deployment Flow

This shows the CI/CD deployment process from PR to production:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    PR[Create Pull Request] --> CIChecks{CI Checks<br/>Pass?}
    CIChecks -->|No| FixCode[Fix Code]
    FixCode --> PR
    CIChecks -->|Yes| Merge[Merge to Main]
    Merge --> BuildPackages[Build Lambda Packages<br/>SHA-versioned ZIPs]
    BuildPackages --> UploadS3[Upload to S3<br/>preprod bucket]
    UploadS3 --> TerraformPlan[Terraform Plan<br/>Preprod]
    TerraformPlan --> ApplyPreprod[Terraform Apply<br/>Preprod]
    ApplyPreprod --> IntegrationTests{Integration<br/>Tests Pass?}
    IntegrationTests -->|No| Rollback[Rollback Preprod]
    Rollback --> IncidentResponse[Create Incident]
    IntegrationTests -->|Yes| ManualGate{Manual<br/>Approval?}
    ManualGate -->|No| WaitApproval[Wait for Approval]
    WaitApproval --> ManualGate
    ManualGate -->|Yes| DeployProd[Deploy to Production]
    DeployProd --> SmokeTests{Smoke Tests<br/>Pass?}
    SmokeTests -->|No| RollbackProd[Rollback Production]
    RollbackProd --> IncidentResponse
    SmokeTests -->|Yes| Complete[Deployment Complete]

    classDef cicdNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef dangerNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e

    class PR,BuildPackages,UploadS3,TerraformPlan,ApplyPreprod,DeployProd,Merge,FixCode,WaitApproval cicdNode
    class CIChecks,IntegrationTests,ManualGate,SmokeTests decisionNode
    class Rollback,RollbackProd,IncidentResponse dangerNode
    class Complete successNode
```

**Key Points:**
- All deployments go through preprod first
- Integration tests must pass before production deployment
- Manual approval gate protects production
- Rollback procedures in place for both environments

---

### Incident Response Flow

This shows the decision tree for responding to production incidents:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    Alert[CloudWatch Alarm<br/>or User Report] --> Assess{Severity<br/>Assessment}
    Assess -->|P0: Complete Outage| P0Response[P0: Immediate Response]
    Assess -->|P1: Partial Outage| P1Response[P1: Urgent Response]
    Assess -->|P2: Degraded| P2Response[P2: Normal Response]

    P0Response --> PageTeam[Page On-Call Team]
    PageTeam --> CheckDashboard{Dashboard<br/>Accessible?}
    CheckDashboard -->|No| CheckLambda[Check Lambda Logs]
    CheckDashboard -->|Yes| DashboardOK[Dashboard OK]

    P1Response --> CheckLogs[Check CloudWatch Logs]
    P2Response --> CreateTicket[Create Ticket]

    CheckLambda --> IdentifyError{Error Type?}
    IdentifyError -->|Lambda Timeout| IncreaseMem[Increase Memory/Timeout]
    IdentifyError -->|S3 Model Load Fail| CheckS3[Verify S3 Model exists]
    IdentifyError -->|DynamoDB Throttle| CheckDDB[Check DynamoDB capacity]
    IdentifyError -->|Code Error| CodeFix[Deploy Hotfix]

    CheckS3 --> S3Exists{Model<br/>Exists?}
    S3Exists -->|No| UploadModel[Upload Model to S3]
    S3Exists -->|Yes| CheckPerms[Check IAM Permissions]

    CheckDDB --> Throttled{Throttling?}
    Throttled -->|Yes| IncreaseCapacity[Increase WCU/RCU]
    Throttled -->|No| CheckIndex[Check GSI status]

    IncreaseMem --> TestFix{Issue<br/>Resolved?}
    CheckPerms --> TestFix
    IncreaseCapacity --> TestFix
    CodeFix --> TestFix
    UploadModel --> TestFix
    CheckIndex --> TestFix

    TestFix -->|Yes| PostMortem[Create Post-Mortem]
    TestFix -->|No| Escalate[Escalate to Engineering]

    PostMortem --> CloseIncident[Close Incident]
    Escalate --> CodeFix

    classDef alertNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e

    class Alert,P0Response alertNode
    class Assess,CheckDashboard,IdentifyError,S3Exists,Throttled,TestFix decisionNode
    class PageTeam,CheckLambda,CheckLogs,CheckS3,CheckDDB,IncreaseMem,CodeFix,CheckPerms,P1Response,P2Response,DashboardOK,CreateTicket,UploadModel,IncreaseCapacity,CheckIndex,Escalate actionNode
    class PostMortem,CloseIncident successNode
```

**Key Points:**
- Severity assessment drives response urgency
- Check dashboard accessibility first
- Lambda logs are primary diagnostic tool
- Post-mortem required for all P0/P1 incidents

---

## Troubleshooting Guides

### Lambda Failures

**Common Issues:**

#### 1. Lambda Timeout

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart LR
    Timeout[Lambda Timeout Error] --> CheckLogs[Check CloudWatch Logs]
    CheckLogs --> FindDuration[Find execution duration]
    FindDuration --> Compare{Duration near<br/>timeout limit?}
    Compare -->|Yes| IncreaseTimeout[Increase timeout<br/>in Terraform]
    Compare -->|No| CheckLogic[Review slow code path]
    IncreaseTimeout --> Deploy[Deploy change]
    CheckLogic --> OptimizeCode[Optimize code]
    OptimizeCode --> Deploy

    classDef errorNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a

    class Timeout errorNode
    class Compare decisionNode
    class CheckLogs,IncreaseTimeout,CheckLogic,OptimizeCode,Deploy,FindDuration actionNode
```

**Quick Fix:**
```bash
# Check current timeout setting
terraform output analysis_lambda_arn
aws lambda get-function-configuration --function-name preprod-sentiment-analysis --query 'Timeout'

# Update in infrastructure/terraform/main.tf (module "analysis_lambda")
# Then redeploy
cd infrastructure/terraform
terraform apply
```

#### 2. Out of Memory Error

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart LR
    OOM[Out of Memory Error] --> CheckMetrics[Check CloudWatch<br/>Memory Metrics]
    CheckMetrics --> MemUsage{Memory usage<br/>>90%?}
    MemUsage -->|Yes| IncreaseMemory[Increase memory<br/>in Terraform]
    MemUsage -->|No| MemoryLeak[Investigate memory leak]
    IncreaseMemory --> Deploy[Deploy change]
    MemoryLeak --> ProfileCode[Profile code<br/>with memory profiler]
    ProfileCode --> FixLeak[Fix leak]
    FixLeak --> Deploy

    classDef errorNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a

    class OOM errorNode
    class MemUsage decisionNode
    class CheckMetrics,IncreaseMemory,MemoryLeak,ProfileCode,FixLeak,Deploy actionNode
```

**Quick Fix:**
```bash
# Check memory usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=preprod-sentiment-analysis \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Maximum

# Update memory in infrastructure/terraform/main.tf
# analysis_lambda: memory_size = 1024 -> 2048
terraform apply
```

---

### DynamoDB Issues

#### Throttling Errors

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    Throttle[DynamoDB<br/>Throttling Error] --> CheckMetrics[Check CloudWatch<br/>DynamoDB Metrics]
    CheckMetrics --> TableOrIndex{Table or<br/>GSI throttled?}
    TableOrIndex -->|Table| CheckWCU[Check WCU/RCU<br/>consumption]
    TableOrIndex -->|GSI| CheckGSI[Check GSI capacity]
    CheckWCU --> AtLimit{At capacity<br/>limit?}
    AtLimit -->|Yes| IncreaseCapacity[Increase capacity<br/>in Terraform]
    AtLimit -->|No| HotKey[Investigate hot<br/>partition keys]
    CheckGSI --> GSILimit{GSI at<br/>limit?}
    GSILimit -->|Yes| IncreaseGSI[Increase GSI capacity]
    GSILimit -->|No| QueryPattern[Review query patterns]
    IncreaseCapacity --> Deploy[Deploy change]
    IncreaseGSI --> Deploy
    HotKey --> RefactorKeys[Refactor partition keys]
    QueryPattern --> OptimizeQueries[Optimize queries]
    RefactorKeys --> Deploy
    OptimizeQueries --> Deploy

    classDef errorNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a

    class Throttle errorNode
    class TableOrIndex,AtLimit,GSILimit decisionNode
    class CheckMetrics,CheckWCU,CheckGSI,IncreaseCapacity,HotKey,IncreaseGSI,QueryPattern,RefactorKeys,OptimizeQueries,Deploy actionNode
```

**Quick Fix:**
```bash
# Check current capacity
aws dynamodb describe-table --table-name preprod-sentiment-items \
  --query 'Table.ProvisionedThroughput'

# View consumed capacity
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# Increase capacity in infrastructure/terraform/modules/dynamodb/main.tf
terraform apply
```

---

### S3 Model Loading Issues

#### Model Load Failures

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    LoadFail[S3 Model Load<br/>Failure] --> CheckLogs[Check Lambda Logs<br/>for S3 error]
    CheckLogs --> ErrorType{Error Type?}
    ErrorType -->|NoSuchKey| ModelMissing[Model file missing<br/>in S3]
    ErrorType -->|AccessDenied| PermissionError[IAM permission<br/>issue]
    ErrorType -->|Timeout| NetworkIssue[Network/S3 timeout]

    ModelMissing --> VerifyBucket[Verify S3 bucket<br/>and key]
    VerifyBucket --> BucketExists{Bucket<br/>exists?}
    BucketExists -->|No| CreateBucket[Create bucket and<br/>upload model]
    BucketExists -->|Yes| UploadModel[Upload model.tar.gz]

    PermissionError --> CheckIAM[Check Lambda<br/>IAM role]
    CheckIAM --> HasS3Perms{Has s3:GetObject<br/>permission?}
    HasS3Perms -->|No| UpdateIAM[Update IAM policy]
    HasS3Perms -->|Yes| CheckBucketPolicy[Check bucket policy]

    NetworkIssue --> CheckVPC[Check VPC config]
    CheckVPC --> InVPC{Lambda in<br/>VPC?}
    InVPC -->|Yes| CheckNAT[Verify NAT Gateway<br/>or VPC endpoint]
    InVPC -->|No| IncreaseTimeout[Increase Lambda<br/>timeout]

    CreateBucket --> TestAgain[Test Lambda again]
    UploadModel --> TestAgain
    UpdateIAM --> TestAgain
    CheckBucketPolicy --> TestAgain
    CheckNAT --> TestAgain
    IncreaseTimeout --> TestAgain

    TestAgain --> Success{Works?}
    Success -->|Yes| Complete[Issue Resolved]
    Success -->|No| Escalate[Escalate to<br/>Engineering]

    classDef errorNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e

    class LoadFail errorNode
    class ErrorType,BucketExists,HasS3Perms,InVPC,Success decisionNode
    class CheckLogs,VerifyBucket,CheckIAM,CheckVPC,CreateBucket,UploadModel,UpdateIAM,CheckBucketPolicy,CheckNAT,IncreaseTimeout,TestAgain,ModelMissing,PermissionError,NetworkIssue,Escalate actionNode
    class Complete successNode
```

**Quick Fix:**
```bash
# Check if model exists
aws s3 ls s3://sentiment-analyzer-models-218795110243/models/

# Verify model version in Lambda env vars
aws lambda get-function-configuration \
  --function-name preprod-sentiment-analysis \
  --query 'Environment.Variables.MODEL_VERSION'

# Check IAM permissions
aws iam get-role-policy \
  --role-name preprod-sentiment-analysis-role \
  --policy-name analysis-lambda-policy

# Manual upload if missing (use build script)
cd infrastructure/scripts
./build-and-upload-model-s3.sh
```

---

### Dashboard Not Responding

#### Dashboard Debugging Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
flowchart TD
    NotResponding[Dashboard Not<br/>Responding] --> CheckURL{Function URL<br/>accessible?}
    CheckURL -->|No| CheckLambda[Check Lambda<br/>Function URL config]
    CheckURL -->|Yes| TestEndpoint[Test /health endpoint]

    CheckLambda --> URLExists{Function URL<br/>exists?}
    URLExists -->|No| CreateURL[Create Function URL<br/>in Terraform]
    URLExists -->|Yes| CheckAuth[Verify auth_type=NONE]

    TestEndpoint --> HealthOK{/health returns<br/>200 OK?}
    HealthOK -->|No| CheckDeps[Check Lambda<br/>dependencies]
    HealthOK -->|Yes| TestAPI[Test /api/metrics]

    CheckDeps --> ImportError{Import errors<br/>in logs?}
    ImportError -->|Yes| RebuildPackage[Rebuild Lambda<br/>package with deps]
    ImportError -->|No| CheckCode[Review handler code]

    TestAPI --> MetricsOK{/api/metrics<br/>returns data?}
    MetricsOK -->|No| CheckAPIKey[Verify API key]
    MetricsOK -->|Yes| TestSSE[Test /api/items SSE]

    CheckAPIKey --> KeyValid{API key in<br/>Secrets Manager?}
    KeyValid -->|No| CreateAPIKey[Create API key<br/>in Secrets Manager]
    KeyValid -->|Yes| CheckEnvVar[Check DASHBOARD_API_KEY_SECRET_ARN<br/>env var]

    TestSSE --> SSEWorks{SSE stream<br/>working?}
    SSEWorks -->|No| CheckDDB[Verify DynamoDB<br/>access]
    SSEWorks -->|Yes| CheckFrontend[Check frontend<br/>JavaScript]

    CreateURL --> Redeploy[Redeploy with<br/>Terraform]
    CheckAuth --> Redeploy
    RebuildPackage --> Redeploy
    CreateAPIKey --> Redeploy
    CheckEnvVar --> Redeploy
    CheckDDB --> Redeploy

    Redeploy --> Verify{Issue<br/>resolved?}
    CheckCode --> Verify
    CheckFrontend --> Verify
    Verify -->|Yes| Complete[Dashboard Working]
    Verify -->|No| Escalate[Escalate to<br/>Engineering]

    classDef errorNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef decisionNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800
    classDef actionNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef successNode fill:#a8d5a2,stroke:#4a7c4e,stroke-width:2px,color:#1e3a1e

    class NotResponding errorNode
    class CheckURL,URLExists,HealthOK,ImportError,MetricsOK,KeyValid,SSEWorks,Verify decisionNode
    class CheckLambda,TestEndpoint,CheckDeps,TestAPI,CheckAPIKey,CreateAPIKey,CheckEnvVar,TestSSE,CheckDDB,CheckFrontend,CreateURL,CheckAuth,RebuildPackage,Redeploy,CheckCode,Escalate actionNode
    class Complete successNode
```

**Quick Fix:**
```bash
# Get dashboard URL
terraform output dashboard_function_url

# Test health endpoint
URL=$(terraform output -raw dashboard_function_url)
curl -i "$URL/health"

# Test metrics endpoint (requires API key)
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/dashboard-api-key \
  --query SecretString --output text | jq -r .api_key)
curl -H "Authorization: $API_KEY" "$URL/api/metrics"

# Check Lambda logs
aws logs tail /aws/lambda/preprod-sentiment-dashboard --follow
```

---

## Monitoring and Alerts

### CloudWatch Alarms

The system has the following CloudWatch alarms configured:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#fff8e1', 'primaryTextColor':'#333', 'primaryBorderColor':'#c9a227', 'lineColor':'#555'}}}%%
graph TD
    subgraph LambdaAlarms["Lambda Alarms"]
        IngestionErrors[Ingestion Errors<br/>>5 in 5 min]
        AnalysisErrors[Analysis Errors<br/>>5 in 5 min]
        AnalysisDuration[Analysis Duration<br/>>5 seconds]
        DashboardErrors[Dashboard Errors<br/>>10 in 5 min]
        MetricsErrors[Metrics Errors<br/>>3 in 5 min]
    end

    subgraph DDBAlarms["DynamoDB Alarms"]
        ReadThrottle[Read Throttle Events]
        WriteThrottle[Write Throttle Events]
    end

    subgraph OpsAlarms["Operational Alarms"]
        StuckItems[Stuck Items<br/>>10 for 3 periods]
    end

    subgraph CostAlarms["Cost Alarms"]
        BudgetAlert[Monthly Budget<br/>>$50]
    end

    IngestionErrors --> SNSTopic[SNS Alarm Topic]
    AnalysisErrors --> SNSTopic
    AnalysisDuration --> SNSTopic
    DashboardErrors --> SNSTopic
    MetricsErrors --> SNSTopic
    ReadThrottle --> SNSTopic
    WriteThrottle --> SNSTopic
    StuckItems --> SNSTopic
    BudgetAlert --> SNSTopic

    SNSTopic --> Email[Email Notification<br/>to On-Call]

    classDef stageBox fill:#fff8e1,stroke:#c9a227,stroke-width:2px,color:#333
    classDef alarmNode fill:#ef5350,stroke:#b71c1c,stroke-width:2px,color:#fff
    classDef notificationNode fill:#7ec8e3,stroke:#3a7ca5,stroke-width:2px,color:#1a3a4a
    classDef operationalNode fill:#ffb74d,stroke:#c77800,stroke-width:2px,color:#4a2800

    class LambdaAlarms,DDBAlarms,OpsAlarms,CostAlarms stageBox
    class IngestionErrors,AnalysisErrors,AnalysisDuration,DashboardErrors,MetricsErrors,ReadThrottle,WriteThrottle,BudgetAlert alarmNode
    class StuckItems operationalNode
    class SNSTopic,Email notificationNode
```

**Alarm Response:**

| Alarm | Severity | Response Time | Action |
|-------|----------|---------------|--------|
| Ingestion Errors | P1 | 15 minutes | Check NewsAPI status, verify API key |
| Analysis Errors | P1 | 15 minutes | Check S3 model, review Lambda logs |
| Analysis Duration | P2 | 1 hour | Review memory/timeout settings |
| Dashboard Errors | P0 | Immediate | Check Function URL, verify dependencies |
| Metrics Errors | P2 | 1 hour | Check Metrics Lambda logs, verify GSI access |
| Stuck Items | P1 | 15 minutes | Check Analysis Lambda, DLQ, SNS delivery |
| DynamoDB Throttle | P1 | 30 minutes | Increase capacity or optimize queries |
| Budget Alert | P2 | 1 business day | Review cost allocation, optimize resources |

---

## Recovery Procedures

### Rollback to Previous Version

```bash
# 1. Identify previous deployment
cd infrastructure/terraform
terraform workspace select preprod
terraform state list

# 2. Find previous Lambda package version
aws s3 ls s3://preprod-sentiment-lambda-deployments/analysis/ --recursive

# 3. Update Terraform to point to previous version
# Edit main.tf module "analysis_lambda" s3_key to previous SHA

# 4. Apply rollback
terraform apply

# 5. Verify rollback
aws lambda get-function --function-name preprod-sentiment-analysis \
  --query 'Code.Location'

# 6. Test functionality
curl $(terraform output -raw dashboard_function_url)/health
```

### Complete System Restart

```bash
# 1. Disable EventBridge schedule
aws events disable-rule --name preprod-sentiment-ingestion-schedule

# 2. Stop all in-flight Lambda executions (wait for completion)
# Check running executions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `preprod-sentiment`)].[FunctionName]' --output text | \
  while read func; do
    echo "$func concurrent executions:"
    aws cloudwatch get-metric-statistics \
      --namespace AWS/Lambda \
      --metric-name ConcurrentExecutions \
      --dimensions Name=FunctionName,Value=$func \
      --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
      --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
      --period 60 \
      --statistics Maximum
  done

# 3. Clear DLQ if needed
aws sqs purge-queue --queue-url $(aws sqs get-queue-url --queue-name preprod-sentiment-dlq --query QueueUrl --output text)

# 4. Restart EventBridge schedule
aws events enable-rule --name preprod-sentiment-ingestion-schedule

# 5. Monitor for normal operation
aws logs tail /aws/lambda/preprod-sentiment-ingestion --follow
```

### Database Recovery

```bash
# DynamoDB point-in-time recovery (if enabled)
# 1. Find recovery point
aws dynamodb describe-continuous-backups --table-name preprod-sentiment-items

# 2. Restore to specific time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name preprod-sentiment-items \
  --target-table-name preprod-sentiment-items-restored \
  --restore-date-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)

# 3. Update Terraform to use restored table (if needed)
# Edit infrastructure/terraform/modules/dynamodb/main.tf

# 4. Redeploy
cd infrastructure/terraform
terraform apply
```

---

## Quick Reference: Common Commands

### Check System Health

```bash
# Dashboard health
curl -i $(cd infrastructure/terraform && terraform output -raw dashboard_function_url)/health

# Lambda function status
aws lambda get-function --function-name preprod-sentiment-analysis --query 'Configuration.State'

# DynamoDB table status
aws dynamodb describe-table --table-name preprod-sentiment-items --query 'Table.TableStatus'

# Recent errors in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/preprod-sentiment-analysis \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) - 3600))000

# Current throttling metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=preprod-sentiment-items \
  --start-time $(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### Emergency Contacts

| Role | Responsibility | Contact |
|------|---------------|---------|
| On-Call Engineer | First responder for P0/P1 incidents | PagerDuty rotation |
| DevOps Lead | Infrastructure and deployment issues | Escalation path |
| Engineering Manager | Decision authority for production changes | Escalation path |

---

## Additional Resources

- [README.md](../README.md) - Project overview and architecture
- [TERRAFORM_DEPLOYMENT_FLOW.md](TERRAFORM_DEPLOYMENT_FLOW.md) - Deployment details
- [DASHBOARD_SECURITY_ANALYSIS.md](DASHBOARD_SECURITY_ANALYSIS.md) - Security considerations
- [CloudWatch Console](https://console.aws.amazon.com/cloudwatch/) - Monitoring and logs
- [Lambda Console](https://console.aws.amazon.com/lambda/) - Lambda function management
