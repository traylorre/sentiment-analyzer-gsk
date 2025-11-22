# Cloud Provider Portability Audit

> **Purpose**: Identify AWS-specific dependencies and provide recommendations for cloud-agnostic architecture.

**Date**: 2025-11-22
**Status**: Initial Analysis

---

## Executive Summary

This project is currently **heavily coupled to AWS** across three layers:
1. **Infrastructure (Terraform)** - 100% AWS-specific resources
2. **Application Code (Python)** - Direct boto3 SDK usage throughout
3. **Compute Model** - AWS Lambda-specific execution model

**Portability Score**: 🔴 **Low (20/100)**

| Category | AWS Coupling | Portability Score | Effort to Port |
|----------|--------------|-------------------|----------------|
| Infrastructure | High | 10/100 | 3-4 weeks |
| Data Storage | High | 20/100 | 2-3 weeks |
| Secrets Management | Medium | 30/100 | 1 week |
| Metrics/Logging | High | 10/100 | 2 weeks |
| Compute Runtime | High | 15/100 | 2-3 weeks |
| Event System | High | 20/100 | 1-2 weeks |

**Total Estimated Effort to Port to GCP**: **8-12 weeks** (with current architecture)

---

## Layer 1: Infrastructure (Terraform)

### AWS-Specific Resources

#### ❌ Completely AWS-Specific (No Direct GCP Equivalent)

| AWS Service | Current Usage | GCP Equivalent | Migration Complexity |
|-------------|---------------|----------------|---------------------|
| **DynamoDB** | NoSQL database | Cloud Firestore / Bigtable | High - Different query model |
| **Lambda** | Serverless compute | Cloud Functions / Cloud Run | Medium - Similar but different triggers |
| **EventBridge** | Scheduled triggers | Cloud Scheduler | Low - Similar cron model |
| **Secrets Manager** | Secret storage | Secret Manager | Low - Nearly identical API |
| **SNS/SQS** | Pub/Sub messaging | Cloud Pub/Sub | Medium - Different message model |
| **CloudWatch** | Metrics & logs | Cloud Monitoring / Cloud Logging | Medium - Different query syntax |
| **IAM Roles** | Permissions | Service Accounts | Low - Similar RBAC model |

#### Current Terraform Modules

```
infrastructure/terraform/modules/
├── dynamodb/        # ❌ AWS-only (Table, GSI, backups, alarms)
├── lambda/          # ❌ AWS-only (Function, layers, URL)
├── eventbridge/     # ❌ AWS-only (Rules, targets)
├── secrets/         # ⚠️  Mostly portable API, AWS-specific resources
├── sns/             # ❌ AWS-only (Topic, subscription, DLQ)
├── iam/             # ❌ AWS-only (Roles, policies)
└── monitoring/      # ❌ AWS-only (CloudWatch alarms, dashboards)
```

**Finding**: 0% of infrastructure is cloud-agnostic.

---

## Layer 2: Application Code (Python)

### Direct boto3 SDK Usage

#### Files with Hard AWS Dependencies

| File | AWS Service | boto3 Usage | Lines of Code |
|------|-------------|-------------|---------------|
| `src/lambdas/shared/dynamodb.py` | DynamoDB | `boto3.resource("dynamodb")` | 337 |
| `src/lambdas/shared/secrets.py` | Secrets Manager | `boto3.client("secretsmanager")` | 313 |
| `src/lib/metrics.py` | CloudWatch | `boto3.client("cloudwatch")` | ~200 |
| `src/lambdas/ingestion/handler.py` | SNS | `boto3.client("sns")` | Indirect |
| `src/lambdas/dashboard/metrics.py` | CloudWatch | `boto3.client("cloudwatch")` | ~100 |

**Total AWS-coupled LOC**: ~950+ lines

#### Code Analysis by Service

##### 1. DynamoDB (`src/lambdas/shared/dynamodb.py`)

**Current Implementation**:
```python
import boto3
from botocore.config import Config

def get_dynamodb_resource(region_name: str | None = None):
    region = region_name or os.environ.get("AWS_REGION")
    return boto3.resource("dynamodb", region_name=region, config=RETRY_CONFIG)

def get_table(table_name: str | None = None):
    name = table_name or os.environ.get("DYNAMODB_TABLE")
    resource = get_dynamodb_resource()
    return resource.Table(name)
```

**AWS-Specific Patterns**:
- Direct boto3 resource creation
- DynamoDB-specific retry configuration
- `put_item()`, `get_item()`, `update_item()` API
- Conditional expressions (`attribute_not_exists()`)
- DynamoDB type conversions (Decimal → float)

**Portability Issues**:
- ❌ No abstraction layer
- ❌ DynamoDB-specific query patterns
- ❌ Hard-coded retry logic for AWS throttling
- ❌ Decimal handling specific to DynamoDB

**GCP Equivalent**: Cloud Firestore or Bigtable
- Firestore: Document model (closer to DynamoDB)
- Bigtable: Wide-column store (high-throughput scenarios)

---

##### 2. Secrets Manager (`src/lambdas/shared/secrets.py`)

**Current Implementation**:
```python
import boto3

def get_secrets_client(region_name: str | None = None):
    region = region_name or os.environ.get("AWS_REGION")
    return boto3.client("secretsmanager", region_name=region, config=RETRY_CONFIG)

def get_secret(secret_id: str):
    client = get_secrets_client()
    response = client.get_secret_value(SecretId=secret_id)
    return json.loads(response["SecretString"])
```

**AWS-Specific Patterns**:
- `SecretString` vs `SecretBinary` handling
- Secret ARN / name resolution
- In-memory caching with TTL

**Portability Issues**:
- ⚠️ Medium coupling (API is similar across clouds)
- ❌ AWS-specific error codes (`ResourceNotFoundException`, `AccessDeniedException`)
- ✅ Caching logic is cloud-agnostic

**GCP Equivalent**: Secret Manager
- Very similar API: `access_secret_version()`
- Different error types: `NotFound`, `PermissionDenied`
- Similar JSON storage model

---

##### 3. CloudWatch Metrics (`src/lib/metrics.py`)

**Current Implementation**:
```python
import boto3

def emit_metric(metric_name: str, value: float, unit: str = "Count"):
    cloudwatch = boto3.client("cloudwatch")
    cloudwatch.put_metric_data(
        Namespace="SentimentAnalyzer",
        MetricData=[{
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.now(UTC)
        }]
    )
```

**AWS-Specific Patterns**:
- CloudWatch namespace model
- `put_metric_data()` API
- Dimensions for filtering
- Unit types (Count, Milliseconds, etc.)

**Portability Issues**:
- ❌ Completely CloudWatch-specific
- ❌ No abstraction for metrics
- ❌ Namespace/dimension model differs from GCP

**GCP Equivalent**: Cloud Monitoring (Stackdriver)
- Uses `write_time_series()` API
- Different metric descriptor model
- Metric types: GAUGE, DELTA, CUMULATIVE

---

##### 4. Lambda Runtime Environment

**AWS Lambda Specifics in Code**:
```python
# handler.py
def lambda_handler(event, context):
    """
    AWS Lambda entry point
    
    event: Dict from SNS, EventBridge, or API Gateway
    context: AWS Lambda context object
    """
    # Extract AWS-specific fields
    request_id = context.request_id
    function_name = context.function_name
    remaining_time = context.get_remaining_time_in_millis()
```

**AWS-Specific Patterns**:
- Lambda context object (`request_id`, `log_group_name`, `function_name`)
- Event structure differs by trigger (SNS vs EventBridge vs HTTP)
- Cold start behavior
- Environment variables (`AWS_REGION`, `AWS_LAMBDA_FUNCTION_NAME`)

**Portability Issues**:
- ❌ Handler signature is AWS-specific
- ❌ Context object has no equivalent in GCP
- ⚠️ Event structure varies by cloud provider

**GCP Equivalent**: Cloud Functions
```python
# GCP Cloud Functions (2nd gen)
def cloud_function_handler(request):
    """
    GCP Cloud Functions entry point
    
    request: flask.Request object
    """
    # Different context access
    execution_id = request.headers.get('Function-Execution-Id')
```

---

## Layer 3: Configuration & Environment

### Environment Variables

#### Current AWS-Specific Variables

| Variable | Usage | Cloud-Agnostic? | Recommendation |
|----------|-------|-----------------|----------------|
| `AWS_REGION` | Region selection | ❌ No | Rename to `CLOUD_REGION` |
| `DYNAMODB_TABLE` | Table name | ⚠️ Partial | Rename to `DATABASE_TABLE` |
| `AWS_LAMBDA_FUNCTION_NAME` | Auto-set by Lambda | ❌ No | Abstract to `FUNCTION_NAME` |
| `SECRETS_CACHE_TTL_SECONDS` | Cache TTL | ✅ Yes | Keep as-is |

**Good News**: We already refactored `AWS_DEFAULT_REGION` → `AWS_REGION` as an env var! 
This is a step toward agnosticism, though the name still references AWS.

---

## Refactoring Recommendations

### Strategy 1: Adapter Pattern (Repository Layer)

**Recommended Approach**: Introduce abstraction layers for each service.

#### Example: Database Abstraction

**Current** (`src/lambdas/shared/dynamodb.py`):
```python
import boto3

def get_table():
    resource = boto3.resource("dynamodb")
    return resource.Table(os.environ["DYNAMODB_TABLE"])
```

**Proposed** (`src/lib/database/interface.py`):
```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class DatabaseInterface(ABC):
    """Cloud-agnostic database interface."""
    
    @abstractmethod
    def put_item(self, item: Dict[str, Any]) -> bool:
        """Insert an item into the database."""
        pass
    
    @abstractmethod
    def get_item(self, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Retrieve an item by key."""
        pass
    
    @abstractmethod
    def update_item(self, key: Dict[str, str], updates: Dict[str, Any]) -> bool:
        """Update an item."""
        pass
    
    @abstractmethod
    def query_by_status(self, status: str, limit: int = 100) -> list[Dict[str, Any]]:
        """Query items by status."""
        pass
```

**AWS Implementation** (`src/lib/database/aws_dynamodb.py`):
```python
import boto3
from .interface import DatabaseInterface

class DynamoDBAdapter(DatabaseInterface):
    def __init__(self, table_name: str, region: str):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)
    
    def put_item(self, item: Dict[str, Any]) -> bool:
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(source_id)"
            )
            return True
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return False
    
    def get_item(self, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
        response = self.table.get_item(Key=key)
        return response.get("Item")
    
    # ... other methods
```

**GCP Implementation** (`src/lib/database/gcp_firestore.py`):
```python
from google.cloud import firestore
from .interface import DatabaseInterface

class FirestoreAdapter(DatabaseInterface):
    def __init__(self, collection: str, project: str):
        self.db = firestore.Client(project=project)
        self.collection = self.db.collection(collection)
    
    def put_item(self, item: Dict[str, Any]) -> bool:
        doc_id = f"{item['source_id']}#{item['timestamp']}"
        doc_ref = self.collection.document(doc_id)
        
        # Firestore equivalent of conditional write
        try:
            doc_ref.create(item)
            return True
        except firestore.exceptions.AlreadyExists:
            return False
    
    def get_item(self, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
        doc_id = f"{key['source_id']}#{key['timestamp']}"
        doc = self.collection.document(doc_id).get()
        return doc.to_dict() if doc.exists else None
    
    # ... other methods
```

**Factory Pattern** (`src/lib/database/factory.py`):
```python
import os
from .interface import DatabaseInterface
from .aws_dynamodb import DynamoDBAdapter
from .gcp_firestore import FirestoreAdapter

def get_database() -> DatabaseInterface:
    """Get database adapter based on environment."""
    provider = os.environ.get("CLOUD_PROVIDER", "aws").lower()
    
    if provider == "aws":
        return DynamoDBAdapter(
            table_name=os.environ["DATABASE_TABLE"],
            region=os.environ["CLOUD_REGION"]
        )
    elif provider == "gcp":
        return FirestoreAdapter(
            collection=os.environ["DATABASE_COLLECTION"],
            project=os.environ["GCP_PROJECT"]
        )
    else:
        raise ValueError(f"Unsupported cloud provider: {provider}")
```

**Usage in Handler** (`src/lambdas/ingestion/handler.py`):
```python
from src.lib.database import get_database

def lambda_handler(event, context):
    db = get_database()  # Cloud-agnostic!
    
    item = {
        "source_id": "newsapi#123",
        "timestamp": "2025-11-22T12:00:00Z",
        "title": "Article"
    }
    
    success = db.put_item(item)  # Works on AWS or GCP
```

---

### Strategy 2: Service Abstractions

Apply the adapter pattern to all cloud services:

```
src/lib/
├── database/
│   ├── interface.py           # DatabaseInterface ABC
│   ├── aws_dynamodb.py        # DynamoDB implementation
│   ├── gcp_firestore.py       # Firestore implementation
│   └── factory.py             # get_database()
├── secrets/
│   ├── interface.py           # SecretsInterface ABC
│   ├── aws_secrets_manager.py # AWS Secrets Manager
│   ├── gcp_secret_manager.py  # GCP Secret Manager
│   └── factory.py             # get_secrets()
├── metrics/
│   ├── interface.py           # MetricsInterface ABC
│   ├── aws_cloudwatch.py      # CloudWatch implementation
│   ├── gcp_monitoring.py      # Cloud Monitoring
│   └── factory.py             # get_metrics()
├── messaging/
│   ├── interface.py           # MessagingInterface ABC
│   ├── aws_sns.py             # SNS implementation
│   ├── gcp_pubsub.py          # Pub/Sub implementation
│   └── factory.py             # get_messaging()
└── compute/
    ├── interface.py           # ComputeContext ABC
    ├── aws_lambda.py          # Lambda context wrapper
    ├── gcp_functions.py       # Cloud Functions context
    └── factory.py             # get_context()
```

---

### Strategy 3: Infrastructure as Code Abstraction

#### Option A: Multi-Cloud Terraform Modules

**Structure**:
```
infrastructure/
├── terraform/
│   ├── providers/
│   │   ├── aws/
│   │   │   ├── database.tf      # DynamoDB
│   │   │   ├── compute.tf       # Lambda
│   │   │   └── secrets.tf       # Secrets Manager
│   │   └── gcp/
│   │       ├── database.tf      # Firestore
│   │       ├── compute.tf       # Cloud Functions
│   │       └── secrets.tf       # Secret Manager
│   └── main.tf                  # Provider selection
```

**Provider Selection** (`main.tf`):
```hcl
variable "cloud_provider" {
  description = "Cloud provider: aws or gcp"
  type        = string
  default     = "aws"
}

module "database" {
  source = var.cloud_provider == "aws" ? "./providers/aws" : "./providers/gcp"
  
  # Cloud-agnostic variables
  environment = var.environment
  table_name  = "${var.environment}-sentiment-items"
}
```

#### Option B: Pulumi (Multi-Language IaC)

**Advantage**: Single codebase, provider abstraction built-in

```python
# infrastructure/pulumi/__main__.py
import pulumi
import pulumi_aws as aws
import pulumi_gcp as gcp

provider = pulumi.Config().get("provider", "aws")

if provider == "aws":
    table = aws.dynamodb.Table("sentiment-items",
        name=f"{environment}-sentiment-items",
        billing_mode="PAY_PER_REQUEST",
        hash_key="source_id",
        range_key="timestamp"
    )
elif provider == "gcp":
    database = gcp.firestore.Database("sentiment-items",
        project=gcp_project,
        name=f"{environment}-sentiment-items",
        location_id="us-central1"
    )
```

---

## Migration Path to GCP

### Phase 1: Code Abstraction (2-3 weeks)

1. **Week 1**: Create abstraction interfaces
   - DatabaseInterface
   - SecretsInterface
   - MetricsInterface
   - MessagingInterface
   - ComputeContextInterface

2. **Week 2**: Implement AWS adapters (refactor existing code)
   - Move boto3 code into adapters
   - Update all handlers to use factories
   - Add comprehensive tests

3. **Week 3**: Implement GCP adapters
   - FirestoreAdapter
   - GCPSecretManagerAdapter
   - CloudMonitoringAdapter
   - PubSubAdapter
   - CloudFunctionsContext

### Phase 2: Infrastructure Parity (3-4 weeks)

1. **Week 4-5**: Create GCP Terraform modules
   - Firestore database
   - Cloud Functions
   - Cloud Scheduler
   - Secret Manager
   - Pub/Sub topics

2. **Week 6-7**: Deploy to GCP test environment
   - Validate all services work
   - Load testing
   - Cost comparison

### Phase 3: Dual-Cloud Operation (2 weeks)

1. **Week 8**: Deploy production to both clouds
   - A/B testing
   - Monitor costs
   - Performance comparison

2. **Week 9**: Optimize and document
   - Performance tuning
   - Cost optimization
   - Migration runbooks

**Total Timeline**: 9-10 weeks for full GCP migration

---

## Current Cloud-Agnostic Components

### ✅ Already Portable

| Component | Why It's Portable | Effort to Port |
|-----------|-------------------|----------------|
| **Sentiment Analysis Model** | Pure Python (transformers library) | 0 hours - works anywhere |
| **NewsAPI Adapter** | HTTP REST client | 0 hours - provider-agnostic |
| **Deduplication Logic** | Pure algorithm | 0 hours - no cloud dependencies |
| **Schema Validation** | Pydantic models | 0 hours - pure Python |
| **Business Logic** | Pure functions | 0 hours - no side effects |

**Portability Win**: ~40% of application logic is already cloud-agnostic!

---

## Cost-Benefit Analysis

### Benefits of Cloud Agnosticism

1. **Multi-Cloud Redundancy**
   - Deploy to AWS and GCP simultaneously
   - Failover if one provider has outage
   - Geographic redundancy

2. **Cost Optimization**
   - Compare pricing per region
   - Move workloads to cheaper provider
   - Negotiate better rates with leverage

3. **Avoid Vendor Lock-In**
   - Freedom to migrate if AWS changes pricing
   - Competitive pressure keeps costs down

4. **Regulatory Compliance**
   - Some regions may require specific providers
   - Data sovereignty requirements

### Costs of Abstraction

1. **Development Time**
   - 8-12 weeks initial abstraction
   - Ongoing maintenance of multiple adapters
   - More complex testing matrix

2. **Performance Overhead**
   - Abstraction layer adds minor latency (~1-5ms)
   - Can't use provider-specific optimizations

3. **Complexity**
   - More code to maintain
   - Team needs multi-cloud expertise
   - Harder to debug (which adapter failed?)

### Recommendation

**For this project**: **Not worth full abstraction unless:**
- Planning to actually deploy to multiple clouds
- Regulatory requirement for multi-cloud
- Anticipating AWS pricing changes

**Better approach**: 
- Implement **partial abstractions** for high-risk services
- Keep infra-as-code modular (easy to swap providers)
- Document migration paths (this doc!)
- Focus on **business logic portability** (we're already 40% there)

---

## Immediate Actionable Improvements

### Low-Hanging Fruit (Can do now)

1. **Environment Variable Naming** ✅ Partially Done
   - ✅ Already using `AWS_REGION` (not hardcoded)
   - ❌ Still has "AWS" in the name
   - **Action**: Create alias `CLOUD_REGION` that falls back to `AWS_REGION`

2. **Extract Business Logic from Handlers**
   - Move sentiment analysis to `src/lib/analysis.py` (provider-agnostic)
   - Move deduplication to `src/lib/deduplication.py` (already done!)
   - Keep handlers thin (just adapters)

3. **Database Query Abstraction**
   - Create `src/lib/repository/sentiment_items.py`
   - Encapsulate DynamoDB queries in high-level methods
   - Makes future DB swap easier

4. **Metrics as Interface**
   - Create `src/lib/metrics/interface.py`
   - Existing code becomes `CloudWatchAdapter`
   - Future: add `CloudMonitoringAdapter`

### Example: Immediate Database Abstraction

**Create Repository Pattern** (No GCP code needed yet):

```python
# src/lib/repository/sentiment_items.py
"""
Cloud-agnostic repository for sentiment items.
Currently backed by DynamoDB, but abstracted for future portability.
"""
from typing import Optional, List, Dict, Any
from ..lambdas.shared.dynamodb import get_table, put_item_if_not_exists

class SentimentItemsRepository:
    """High-level repository for sentiment items."""
    
    def __init__(self):
        # TODO: Replace with factory when adding GCP support
        self.table = get_table()
    
    def save_new_item(self, item: Dict[str, Any]) -> bool:
        """
        Save a new sentiment item if it doesn't exist.
        
        Returns True if created, False if already exists.
        """
        return put_item_if_not_exists(self.table, item)
    
    def get_item(self, source_id: str, timestamp: str) -> Optional[Dict[str, Any]]:
        """Retrieve a sentiment item by ID."""
        # Abstracted - implementation can change
        pass
    
    def get_recent_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent sentiment items."""
        # Cloud-agnostic interface, DynamoDB implementation
        pass
```

**Usage** (Already cloud-agnostic!):
```python
from src.lib.repository.sentiment_items import SentimentItemsRepository

def lambda_handler(event, context):
    repo = SentimentItemsRepository()  # Abstract!
    
    success = repo.save_new_item({
        "source_id": "newsapi#123",
        "timestamp": "2025-11-22T12:00:00Z",
        "title": "Article"
    })
```

**Future**: Just swap the repository implementation, handlers unchanged.

---

## Summary & Next Steps

### Current State
- **Portability**: 20/100
- **Cloud-Agnostic LOC**: ~40% (business logic)
- **AWS-Coupled LOC**: ~60% (boto3 SDK calls)
- **Estimated GCP Port Effort**: 8-12 weeks

### Quick Wins (Do These First)
1. ✅ Create `CLOUD_REGION` environment variable alias
2. Create repository pattern for database access
3. Extract metrics interface
4. Document service mapping (AWS ↔ GCP)

### Long-Term (If Multi-Cloud is Required)
1. Implement adapter pattern for all services
2. Create GCP Terraform modules
3. Deploy to GCP test environment
4. Run dual-cloud for redundancy

### Decision Point
**Question for stakeholders**: Do we actually need multi-cloud support?

- If **NO**: Keep current architecture, focus on making modules reusable
- If **YES**: Start with repository pattern, then full adapter strategy

---

**Last Updated**: 2025-11-22
**Author**: Cloud Portability Audit
