# Security Review: "Best of All Worlds" Redundancy Architecture

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-17
**Review Type**: Waterfall Trust Zone Analysis
**Reviewer**: Planning phase - automated security analysis
**Status**: 🔴 REQUIRES HUMAN REVIEW

---

## Executive Summary

This security review analyzes the impact of the new multi-tier database redundancy architecture on the existing 5 trust zones. The architecture introduces **3 new components** and **splits Trust Zone 4** into write and read tiers.

**Critical Findings**:
- ✅ Write tier isolation prevents read-path compromise from corrupting data
- ⚠️ Stream processor crosses trust boundaries (Zone 4 write → Zone 4 read)
- ⚠️ Global replicas introduce 3 new data residency regions (GDPR implications)
- ⚠️ Dashboard table exposure creates new attack surface for data exfiltration
- ⚠️ DAX cache (Phase 2) adds in-memory injection risk

**Recommendation**: Proceed with Phase 1A (no global replicas) for demo, defer global tables and DAX to staging after security review approval.

---

## 1. Trust Zone Mapping: Before vs After

### Before: Original 5 Trust Zones

| Zone | Color | Components | Security Posture |
|------|-------|------------|------------------|
| **Zone 1: UNTRUSTED** | 🔴 Red | External APIs (NewsAPI, Twitter) | Tainted input, no control |
| **Zone 2: VALIDATION** | 🟠 Orange | Ingestion Lambdas, API Gateway | Input validation, size limits |
| **Zone 3: PROCESSING** | 🟡 Yellow | Analysis Lambda, SNS/SQS | Processing untrusted data |
| **Zone 4: PROTECTED** | 🟢 Green | DynamoDB (single table) | Parameterized writes only |
| **Zone 5: INFRASTRUCTURE** | 🔵 Blue | Secrets Manager, CloudWatch, S3 | AWS-managed services |

### After: Updated Trust Zone Architecture

| Zone | Components | **NEW Components** | Security Changes |
|------|------------|-------------------|------------------|
| **Zone 1: UNTRUSTED** | External APIs | *(No changes)* | Same attack surface |
| **Zone 2: VALIDATION** | Ingestion Lambdas | *(No changes)* | Same validation logic |
| **Zone 3: PROCESSING** | Analysis Lambda | **+ Stream Processor Lambda** | New Lambda with cross-tier access |
| **Zone 4a: WRITE TIER** | DynamoDB Primary Table | **+ Global Replicas (3 regions)** | Multi-region write exposure |
| **Zone 4b: READ TIER** | *(New)* | **+ Dashboard Table + GSIs** | New read attack surface |
| **Zone 5: INFRASTRUCTURE** | AWS Services | **+ DAX Cluster (Phase 2)** | In-memory cache risk |

---

## 2. New Components Security Analysis

### 2.1 Primary Write Table (`sentiment-items-primary`)

**Description**: Write-optimized DynamoDB table, replaces original `sentiment-items` table

**Security Changes**:
- ✅ **POSITIVE**: No GSIs reduces write-path attack surface
- ✅ **POSITIVE**: Region-scoped IAM (us-east-1 only) prevents cross-region writes
- ⚠️ **RISK**: Global table replicas (Phase 1B) introduce data residency concerns

**Trust Zone**: Zone 4a (Write Tier - Protected)

**Attack Vectors**:
1. **Cross-Region Write Injection**: If IAM condition is misconfigured
   - **Likelihood**: Low (IAM condition enforced)
   - **Impact**: High (data corruption in primary table)
   - **Mitigation**: Terraform validation tests for IAM conditions

2. **Stream Event Tampering**: If DynamoDB Streams compromised
   - **Likelihood**: Very Low (AWS-managed service)
   - **Impact**: High (corrupted data propagates to dashboard table)
   - **Mitigation**: Stream processor validates all input fields

**IAM Permissions**:
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem"],
  "Resource": "arn:aws:dynamodb:us-east-1:*:table/sentiment-items-primary",
  "Condition": {
    "StringEquals": {"aws:RequestedRegion": "us-east-1"}
  }
}
```

**Residual Risks**:
- ⚠️ If us-east-1 region fails, no writes possible (single point of failure)
- ⚠️ DynamoDB Streams retain data for 24 hours (exposure window if stream compromised)

---

### 2.2 Stream Processor Lambda

**Description**: Transforms data from primary table → dashboard table via DynamoDB Streams

**Security Posture**: 🟡 **MEDIUM RISK** - Crosses trust boundary (write tier → read tier)

**Trust Zone**: Zone 3 (Processing) → Zone 4b (Read Tier)

**Critical Security Concern**: This Lambda is the **ONLY component** with write access to dashboard table AND read access to primary table stream.

**Attack Vectors**:

#### 2.2.1 Stream Event Injection
- **Scenario**: Attacker compromises primary table, inserts malicious stream events
- **Attack**: Inject oversized `matched_tags` (5000 tags instead of 5)
- **Impact**: Write amplification DoS (1 primary item → 5001 dashboard items)
- **Likelihood**: Low (requires primary table compromise)
- **Mitigation**:
  ```python
  # REQUIRED: Add input validation in stream processor
  if len(matched_tags) > 5:
      logger.error(f"Suspicious tag count: {len(matched_tags)}, skipping")
      return  # Skip processing, emit CloudWatch alarm
  ```

#### 2.2.2 Lambda Code Injection
- **Scenario**: Attacker exploits stream processor Lambda code vulnerability
- **Attack**: Malformed stream event triggers code execution
- **Impact**: Arbitrary writes to dashboard table
- **Likelihood**: Medium (depends on code quality)
- **Mitigation**:
  - ✅ Use Pydantic for strict schema validation on stream events
  - ✅ Input validation on ALL fields before writing to dashboard table
  - ✅ Reserved concurrency limit (10) prevents runaway Lambda

#### 2.2.3 DLQ Replay Attack
- **Scenario**: Attacker gains access to Dead Letter Queue (14-day retention)
- **Attack**: Replay old stream events to pollute dashboard table
- **Impact**: Stale data appears in dashboard, confuses users
- **Likelihood**: Low (requires SQS access)
- **Mitigation**:
  - ✅ TTL on dashboard table (7 days) - old replays auto-deleted
  - ⚠️ **TODO**: Add "processed_at" timestamp check in stream processor
  ```python
  # Reject stream events older than 1 hour
  event_time = datetime.fromisoformat(record['dynamodb']['ApproximateCreationDateTime'])
  if datetime.now() - event_time > timedelta(hours=1):
      logger.warning(f"Rejecting old stream event: {event_time}")
      return
  ```

#### 2.2.4 Excessive Write Amplification (DoS)
- **Scenario**: Legitimate traffic spike causes dashboard table throttling
- **Attack**: Not malicious, but architectural risk
- **Impact**: Dashboard table throttled, Lambda fails, stream backlog grows
- **Likelihood**: Medium (if traffic spikes 10x)
- **Mitigation**:
  - ✅ Reserved concurrency (10) limits Lambda invocations
  - ✅ Batching (100 records/5 sec) smooths write traffic
  - ⚠️ **TODO**: CloudWatch alarm on stream iterator age > 1 minute

**IAM Permissions** (Cross-Tier Access):
```json
{
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetRecords", "dynamodb:DescribeStream"],
      "Resource": "arn:aws:dynamodb:*:table/sentiment-items-primary/stream/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:BatchWriteItem"],
      "Resource": "arn:aws:dynamodb:*:table/sentiment-items-dashboard"
    }
  ]
}
```

**Trust Boundary Crossing**: This Lambda is the **bridge** between write tier (Zone 4a) and read tier (Zone 4b). If compromised, attacker can corrupt read tier without touching write tier.

---

### 2.3 Dashboard Table (`sentiment-items-dashboard`)

**Description**: Read-optimized table for dashboard queries, populated via streams

**Security Posture**: 🟢 **LOW RISK** - Read-only from application perspective

**Trust Zone**: Zone 4b (Read Tier - Protected, but separate from write tier)

**Attack Vectors**:

#### 2.3.1 Dashboard Lambda Compromise → Data Exfiltration
- **Scenario**: Dashboard Lambda compromised via code injection or leaked credentials
- **Attack**: Query ALL dashboard data (not just displayed subset)
- **Impact**: Privacy breach - attacker reads all sentiment analysis results
- **Likelihood**: Medium (public Lambda Function URL, no auth in demo)
- **Mitigation**:
  - ⚠️ **CRITICAL**: Add authentication to Lambda Function URL (Phase 1A)
  - ✅ Dashboard Lambda has NO write access (read-only IAM)
  - ✅ TTL (7 days) limits exposure window
  - ⚠️ **TODO**: Add CloudWatch alarm on unusual query patterns
  ```python
  # Example: Alarm on dashboard queries > 1000/hour from single IP
  ```

#### 2.3.2 GSI Abuse (Unintended Query Patterns)
- **Scenario**: Attacker discovers GSIs (`by_sentiment`, `by_tag`) allow efficient bulk queries
- **Attack**: Query all "negative" sentiment items using `by_sentiment` GSI
- **Impact**: Targeted data exfiltration (e.g., all negative news about a competitor)
- **Likelihood**: High (if Lambda Function URL is unauthenticated)
- **Mitigation**:
  - ⚠️ **CRITICAL**: Authentication required for dashboard Lambda
  - ✅ IAM permissions already scoped to dashboard table only
  - ⚠️ **TODO**: Rate limiting on dashboard Lambda (100 requests/min per IP)

#### 2.3.3 TTL Data Leak (7-Day Window)
- **Scenario**: Sensitive data remains in dashboard table for 7 days
- **Attack**: If item should be deleted immediately (e.g., GDPR "right to be forgotten"), TTL delay violates compliance
- **Impact**: Compliance violation, GDPR fines
- **Likelihood**: Low (demo doesn't handle PII)
- **Mitigation**:
  - ✅ Demo spec explicitly states "no full raw text persisted" (snippet only)
  - ⚠️ **TODO**: If PII is added, implement immediate delete operation (bypass TTL)

**IAM Permissions** (Read-Only):
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:Query", "dynamodb:GetItem"],
  "Resource": [
    "arn:aws:dynamodb:*:table/sentiment-items-dashboard",
    "arn:aws:dynamodb:*:table/sentiment-items-dashboard/index/by_sentiment",
    "arn:aws:dynamodb:*:table/sentiment-items-dashboard/index/by_tag"
  ]
}
```

**Fallback to Primary Table** (Emergency Only):
```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:Query"],
  "Resource": "arn:aws:dynamodb:*:table/sentiment-items-primary",
  "Condition": {
    "StringEquals": {"dynamodb:Select": "SPECIFIC_ATTRIBUTES"}
  }
}
```
- ⚠️ **RISK**: Fallback allows dashboard Lambda to query primary table (write tier)
- ✅ **MITIGATION**: `SPECIFIC_ATTRIBUTES` condition prevents full table scans
- ⚠️ **TODO**: Add CloudWatch alarm if fallback is used (should be rare)

---

### 2.4 Global Table Replicas (Phase 1B)

**Description**: DynamoDB Global Tables with 3 regional replicas

**Security Posture**: ⚠️ **MEDIUM-HIGH RISK** - Multi-region data residency

**Trust Zone**: Zone 4a (Write Tier - replicated to 3 additional regions)

**Regions**:
1. `us-west-2` (US West Coast)
2. `eu-west-1` (Ireland - **GDPR jurisdiction**)
3. `ap-south-1` (Mumbai - **India data residency laws**)

**Attack Vectors**:

#### 2.4.1 Cross-Region Data Residency Violation
- **Scenario**: User data from EU must stay in EU (GDPR Article 44)
- **Attack**: EU citizen's sentiment data replicated to us-west-2 and ap-south-1
- **Impact**: GDPR non-compliance, potential fines up to €20M or 4% global revenue
- **Likelihood**: High (if demo ingests EU user data)
- **Mitigation**:
  - ⚠️ **CRITICAL**: Demo spec must state "US-only data sources" (NewsAPI US region)
  - ⚠️ **TODO**: Add geo-tagging to items, filter by region before replication
  - ⚠️ **ALTERNATIVE**: Use conditional replication (DynamoDB Streams filter)
  ```python
  # Example: Only replicate non-EU data to global replicas
  if item.get('geo_region') != 'EU':
      replicate_to_global_tables(item)
  ```

#### 2.4.2 Regional AWS Account Compromise
- **Scenario**: Attacker compromises AWS account in eu-west-1
- **Attack**: Modify data in eu-west-1 replica, waits for replication to us-east-1
- **Impact**: Data corruption propagates to primary region
- **Likelihood**: Low (requires AWS account compromise)
- **Mitigation**:
  - ✅ Global Tables use **last-writer-wins** conflict resolution
  - ⚠️ **TODO**: Add DynamoDB Streams comparison (detect conflicting writes)
  - ⚠️ **TODO**: CloudWatch alarm on replication conflicts

#### 2.4.3 Replication Lag Exploitation
- **Scenario**: Attacker exploits < 1 second replication lag
- **Attack**: Write to us-east-1, quickly query eu-west-1 before replication completes
- **Impact**: Inconsistent reads (user sees old data)
- **Likelihood**: Low (replication typically < 500ms)
- **Mitigation**:
  - ✅ Dashboard reads from dashboard table (not replicas)
  - ⚠️ If replicas are used for reads (future), add "read your writes" consistency check

**Cost of Global Tables**:
- Phase 1A (no replicas): $0.09/month (primary table writes only)
- Phase 1B (3 replicas): $0.36/month (4x write cost)
- **Recommendation**: Defer Phase 1B until data residency is resolved

---

### 2.5 DAX Cache Cluster (Phase 2)

**Description**: In-memory cache for sub-10ms dashboard reads

**Security Posture**: 🟡 **MEDIUM RISK** - In-memory cache poisoning, VPC exposure

**Trust Zone**: Zone 5 (Infrastructure) - but caches Zone 4b data

**Attack Vectors**:

#### 2.5.1 Cache Poisoning (In-Memory Injection)
- **Scenario**: Attacker exploits DAX cache eviction policy
- **Attack**: Flood cache with malicious items, evict legitimate cache entries
- **Impact**: Dashboard displays incorrect sentiment scores
- **Likelihood**: Low (requires knowledge of cache eviction algorithm)
- **Mitigation**:
  - ✅ DAX write-through disabled (read-only cache)
  - ⚠️ **TODO**: Add cache key validation (reject keys with special characters)
  - ⚠️ **TODO**: CloudWatch alarm on cache miss rate > 50%

#### 2.5.2 VPC Security (DAX Requires VPC)
- **Scenario**: DAX cluster must run in VPC, Lambda must also be in VPC
- **Attack**: VPC misconfiguration exposes DAX to internet
- **Impact**: Public access to in-memory cache
- **Likelihood**: Medium (VPC security groups often misconfigured)
- **Mitigation**:
  - ⚠️ **CRITICAL**: DAX security group ONLY allows Lambda security group
  - ⚠️ **CRITICAL**: No public IPs on DAX cluster
  - ⚠️ **TODO**: Terraform validation: Deny all inbound except Lambda SG

#### 2.5.3 Cache Timing Attack
- **Scenario**: Attacker measures cache hit/miss latency to infer data
- **Attack**: Query dashboard Lambda repeatedly, measure response time
- **Impact**: Information disclosure (attacker knows which items are cached)
- **Likelihood**: Low (minimal information leakage)
- **Mitigation**:
  - ✅ Cache TTL (5 minutes) limits exposure window
  - ⚠️ **TODO**: Add jitter to response times (prevent timing attacks)

**DAX Cluster Configuration**:
```hcl
resource "aws_dax_cluster" "sentiment_cache" {
  cluster_name       = "sentiment-items-cache"
  node_type          = "dax.t3.small"
  replication_factor = 3  # Multi-AZ for HA

  subnet_group_name = aws_dax_subnet_group.private.name  # Private subnets only
  security_group_ids = [aws_security_group.dax.id]

  parameter_group_name = aws_dax_parameter_group.default.name
}

resource "aws_security_group" "dax" {
  name = "dax-cluster-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port   = 8111  # DAX port
    to_port     = 8111
    protocol    = "tcp"
    security_groups = [aws_security_group.dashboard_lambda.id]  # ONLY Lambda
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

**Recommendation**: Defer DAX to Phase 2, only enable when read traffic > 10 queries/sec

---

## 3. Trust Zone Boundary Analysis

### 3.1 Zone 4 Split: Write Tier vs Read Tier

**Previous Architecture**: Single DynamoDB table in Zone 4 (Protected)

**New Architecture**: Zone 4 split into two sub-zones

| Sub-Zone | Components | Trust Boundary |
|----------|------------|----------------|
| **Zone 4a: Write Tier** | Primary table + Global replicas | Only Ingestion/Analysis Lambdas can write |
| **Zone 4b: Read Tier** | Dashboard table + GSIs | Only Stream Processor can write, Dashboard Lambda reads |

**Trust Boundary Crossing**: Stream Processor Lambda

```
┌─────────────────────────────────────────────────┐
│  Zone 4a: WRITE TIER (Primary Table)           │
│  ✅ Strong write protection (region-scoped)    │
└────────────┬────────────────────────────────────┘
             │ DynamoDB Streams (24-hour buffer)
             ▼
┌─────────────────────────────────────────────────┐
│  Stream Processor Lambda (Trust Boundary)       │
│  ⚠️ CRITICAL: Only component with cross-tier   │
│     access (read from write, write to read)    │
└────────────┬────────────────────────────────────┘
             │ Batch writes (100 records/5 sec)
             ▼
┌─────────────────────────────────────────────────┐
│  Zone 4b: READ TIER (Dashboard Table)          │
│  ⚠️ Weaker protection (public Lambda URL)      │
└─────────────────────────────────────────────────┘
```

**Security Implications**:

✅ **POSITIVE**: Compromise of dashboard Lambda (Zone 4b) CANNOT corrupt primary table (Zone 4a)
- Dashboard Lambda has **read-only** IAM permissions
- Even if attacker gains full control of dashboard Lambda, they cannot modify primary table

⚠️ **RISK**: Compromise of stream processor Lambda (Zone 3 → Zone 4b) CAN corrupt dashboard table
- Stream processor has **write access** to dashboard table
- If attacker exploits stream processor code vulnerability, they can inject fake sentiment data

**Mitigation Strategy**:
1. ✅ Stream processor Lambda has **NO direct internet access** (VPC with no NAT)
2. ⚠️ **TODO**: Add input validation on ALL stream events (Pydantic schemas)
3. ⚠️ **TODO**: CloudWatch alarm on anomalous write patterns (>5000 writes/hour)
4. ⚠️ **TODO**: Lambda code signing (prevent unauthorized code deployment)

---

### 3.2 Cross-Zone Communication Matrix

| From Zone | To Zone | Component | Protocol | Security Control |
|-----------|---------|-----------|----------|------------------|
| Zone 1 → Zone 2 | Untrusted → Validation | Ingestion Lambda | HTTPS | TLS 1.2+, size limits |
| Zone 2 → Zone 4a | Validation → Write Tier | DynamoDB PutItem | AWS API | Parameterized writes, region-scoped IAM |
| Zone 4a → Zone 3 | Write Tier → Processing | DynamoDB Streams | AWS internal | 24-hour buffer, no encryption in transit |
| Zone 3 → Zone 4b | Processing → Read Tier | Stream Processor | AWS API | Input validation, reserved concurrency |
| Zone 4b → Zone 2 | Read Tier → Validation | Dashboard Lambda | AWS API | Read-only IAM, fallback alarm |
| Zone 5 → All | Infrastructure → All | CloudWatch | AWS internal | Secrets filtering, 7-year retention |

**New Cross-Zone Communication** (not in original architecture):
- ⚠️ **Zone 4a → Zone 3**: DynamoDB Streams (NEW)
- ⚠️ **Zone 3 → Zone 4b**: Stream Processor writes (NEW)

**Security Concern**: DynamoDB Streams data is **NOT encrypted in transit** (AWS internal network)
- ✅ **MITIGATION**: AWS guarantees physical isolation within their network
- ⚠️ **RISK**: If AWS internal network is compromised (highly unlikely), stream data is exposed
- ⚠️ **TODO**: Add application-level encryption for sensitive fields (text_snippet) before writing to primary table

---

## 4. Attack Surface Comparison

### 4.1 Attack Surface: Before

| Attack Vector | Exposure | Risk Level |
|---------------|----------|------------|
| Ingestion Lambda (NewsAPI) | Internet (HTTPS) | 🟡 Medium |
| Analysis Lambda (SNS trigger) | Internal (AWS SNS) | 🟢 Low |
| Dashboard Lambda (Function URL) | Internet (HTTPS, no auth) | 🔴 High |
| DynamoDB table | Internal (IAM-protected) | 🟢 Low |
| Secrets Manager | Internal (IAM-protected) | 🟢 Low |

**Total Attack Surface**: 5 components, 2 internet-exposed

---

### 4.2 Attack Surface: After (Phase 1A - No Global Replicas)

| Attack Vector | Exposure | Risk Level | **NEW?** |
|---------------|----------|------------|----------|
| Ingestion Lambda | Internet (HTTPS) | 🟡 Medium | *(unchanged)* |
| Analysis Lambda | Internal (SNS) | 🟢 Low | *(unchanged)* |
| **Stream Processor Lambda** | Internal (DynamoDB Streams) | 🟡 Medium | ✅ **NEW** |
| Dashboard Lambda | Internet (HTTPS, no auth) | 🔴 High | *(unchanged, but queries different table)* |
| Primary DynamoDB table | Internal (IAM) | 🟢 Low | *(renamed, same security)* |
| **Dashboard DynamoDB table** | Internal (IAM, read-heavy) | 🟡 Medium | ✅ **NEW** |
| Secrets Manager | Internal (IAM) | 🟢 Low | *(unchanged)* |

**Total Attack Surface**: 7 components (+2 new), 2 internet-exposed (same)

**Attack Surface Increase**: +28% (5 → 7 components)

---

### 4.3 Attack Surface: After (Phase 1B - With Global Replicas)

| Attack Vector | Exposure | Risk Level | **NEW?** |
|---------------|----------|------------|----------|
| *(All Phase 1A components)* | *(see above)* | | |
| **Global Replica (us-west-2)** | Internal (DynamoDB) | 🟡 Medium | ✅ **NEW** |
| **Global Replica (eu-west-1)** | Internal (DynamoDB) | 🟠 Medium-High (GDPR) | ✅ **NEW** |
| **Global Replica (ap-south-1)** | Internal (DynamoDB) | 🟠 Medium-High (India data laws) | ✅ **NEW** |

**Total Attack Surface**: 10 components (+5 vs original), 2 internet-exposed

**Attack Surface Increase**: +100% (5 → 10 components)

**Data Residency Risk**: 🔴 **HIGH** - Data replicated to 3 additional countries

---

### 4.4 Attack Surface: After (Phase 2 - With DAX)

| Attack Vector | Exposure | Risk Level | **NEW?** |
|---------------|----------|------------|----------|
| *(All Phase 1B components)* | *(see above)* | | |
| **DAX Cache Cluster (3 nodes)** | VPC (private subnets) | 🟡 Medium (VPC misconfiguration risk) | ✅ **NEW** |
| **Dashboard Lambda (in VPC)** | Internet (HTTPS, no auth) | 🔴 High (VPC adds complexity) | ✅ **CHANGED** |

**Total Attack Surface**: 12 components (+7 vs original), 2 internet-exposed

**Attack Surface Increase**: +140% (5 → 12 components)

**VPC Risk**: ✅ DAX cluster isolated, but VPC security groups must be correctly configured

---

## 5. Specific Attack Scenarios & Mitigations

### Scenario 1: Dashboard Lambda Compromise → Data Exfiltration

**Attack Flow**:
1. Attacker exploits dashboard Lambda code injection vulnerability
2. Attacker modifies dashboard Lambda code to query ALL dashboard data
3. Dashboard Lambda has `dynamodb:Query` on dashboard table (legitimate permission)
4. Attacker exfiltrates all sentiment analysis results (privacy breach)

**Impact**: 🔴 **HIGH** - Full data exfiltration of last 7 days (TTL window)

**Likelihood**: 🟡 **MEDIUM** - Public Lambda Function URL with no authentication

**Mitigation**:
- ⚠️ **CRITICAL (Phase 1A)**: Add authentication to Lambda Function URL
  ```hcl
  resource "aws_lambda_function_url" "dashboard" {
    authorization_type = "AWS_IAM"  # Require IAM signing
  }
  ```
- ⚠️ **CRITICAL (Phase 1A)**: Add rate limiting (100 requests/min per IP)
- ⚠️ **TODO**: CloudWatch alarm on unusual query patterns (>1000 queries/hour)
- ⚠️ **TODO**: Lambda code signing (prevent unauthorized code deployment)

---

### Scenario 2: Stream Processor Exploitation → Dashboard Table Corruption

**Attack Flow**:
1. Attacker compromises primary table (highly unlikely, but assume breach)
2. Attacker inserts malicious item with `matched_tags: [5000 tags]`
3. DynamoDB Streams emits event with 5000 tags
4. Stream processor creates 1 + 5000 = 5001 dashboard items (write amplification)
5. Dashboard table throttled, stream processor fails, backlog grows

**Impact**: 🟠 **MEDIUM-HIGH** - Denial of service on dashboard table

**Likelihood**: 🟢 **LOW** - Requires primary table compromise

**Mitigation**:
- ✅ **TODO (Phase 1A)**: Add input validation in stream processor
  ```python
  MAX_TAGS = 10  # Allow some buffer above expected 5
  if len(matched_tags) > MAX_TAGS:
      logger.error(f"Suspicious tag count: {len(matched_tags)}, skipping")
      cloudwatch.put_metric_data(
          Namespace='SentimentAnalyzer',
          MetricData=[{'MetricName': 'SuspiciousTagCount', 'Value': 1}]
      )
      return  # Skip processing
  ```
- ✅ Reserved concurrency (10) limits damage scope
- ⚠️ **TODO**: CloudWatch alarm on stream iterator age > 5 minutes

---

### Scenario 3: Global Replica Data Residency Violation (GDPR)

**Attack Flow**:
1. NewsAPI returns article authored by EU citizen (e.g., French journalist)
2. Ingestion Lambda writes to primary table (us-east-1)
3. DynamoDB Global Tables replicates to eu-west-1 (✅ OK), us-west-2 (⚠️ violation), ap-south-1 (⚠️ violation)
4. EU citizen exercises GDPR "right to be forgotten"
5. Data deleted from us-east-1 and eu-west-1, but may still exist in us-west-2/ap-south-1 due to replication lag

**Impact**: 🔴 **HIGH** - GDPR non-compliance, fines up to €20M or 4% global revenue

**Likelihood**: 🟡 **MEDIUM** - If demo ingests EU-authored content (NewsAPI UK region)

**Mitigation**:
- ⚠️ **CRITICAL (Phase 1B)**: Defer global replicas until data residency is resolved
- ⚠️ **ALTERNATIVE 1**: Only use US-based data sources (NewsAPI US region only)
- ⚠️ **ALTERNATIVE 2**: Add geo-tagging to items, conditional replication
  ```python
  # Only replicate non-EU data to global replicas
  if item.get('author_country') not in ['EU', 'UK']:
      enable_global_replication = True
  ```
- ⚠️ **ALTERNATIVE 3**: Use DynamoDB Streams filter to prevent EU data replication
  ```hcl
  # Terraform: Filter EU data before replication
  filter_criteria {
    filter {
      pattern = jsonencode({
        dynamodb = {
          NewImage = {
            author_country = { S = [{ "anything-but": ["EU", "UK"] }] }
          }
        }
      })
    }
  }
  ```

**Recommendation**: **DEFER Phase 1B** (global replicas) until data residency strategy is approved

---

### Scenario 4: DAX Cache Poisoning (Phase 2)

**Attack Flow**:
1. Attacker discovers DAX cache endpoint (VPC internal)
2. Attacker exploits VPC security group misconfiguration (e.g., SSH tunnel)
3. Attacker floods DAX cache with fake sentiment items
4. Legitimate dashboard queries return cached fake data

**Impact**: 🟡 **MEDIUM** - Dashboard displays incorrect sentiment scores

**Likelihood**: 🟢 **LOW** - Requires VPC access (very unlikely if SG configured correctly)

**Mitigation**:
- ✅ **CRITICAL (Phase 2)**: DAX security group ONLY allows Lambda security group
  ```hcl
  ingress {
    from_port   = 8111
    to_port     = 8111
    protocol    = "tcp"
    security_groups = [aws_security_group.dashboard_lambda.id]  # ONLY Lambda SG
  }
  ```
- ✅ DAX write-through disabled (read-only cache)
- ✅ Cache TTL (5 minutes) limits exposure window
- ⚠️ **TODO**: CloudWatch alarm on cache miss rate > 50% (indicates poisoning)

**Recommendation**: **DEFER Phase 2** (DAX) until VPC security is validated and read traffic justifies cost

---

## 6. Residual Risks & Acceptance Criteria

### 6.1 Accepted Risks (Demo Scope)

| Risk | Severity | Acceptance Rationale |
|------|----------|---------------------|
| No authentication on dashboard Lambda | 🔴 High | Demo environment only, no PII, short-lived deployment |
| TTL window (7 days) | 🟡 Medium | Demo spec states "no full raw text", snippet only (<200 chars) |
| DynamoDB Streams not encrypted in transit | 🟢 Low | AWS internal network, physical isolation guaranteed |
| Stream processor has cross-tier access | 🟡 Medium | Architectural necessity, mitigated by input validation |

### 6.2 Unacceptable Risks (Must Fix Before Production)

| Risk | Severity | Required Mitigation |
|------|----------|---------------------|
| Dashboard Lambda has no authentication | 🔴 High | **MUST**: Add IAM authentication or API key before production |
| Global replicas without data residency strategy | 🔴 High | **MUST**: Defer Phase 1B or implement geo-filtering |
| Stream processor has no input validation | 🟠 Medium-High | **MUST**: Add Pydantic schema validation on stream events |
| No rate limiting on dashboard Lambda | 🟠 Medium-High | **MUST**: Add 100 requests/min per IP limit |
| DAX VPC security groups not validated | 🟡 Medium | **MUST**: Terraform tests to verify security group isolation |

---

## 7. Security Controls Checklist

### Phase 1A (Demo - Minimal Viable Security)

- [ ] **AUTH-01**: Add authentication to dashboard Lambda Function URL
  - Option 1: AWS IAM (requires signing)
  - Option 2: API key in environment variable (simpler for demo)
  - **Deadline**: Before demo deployment

- [ ] **VALID-01**: Add input validation in stream processor Lambda
  ```python
  from pydantic import BaseModel, Field, validator

  class StreamEvent(BaseModel):
      source_id: str = Field(..., max_length=256, regex=r'^[a-z]+#[a-zA-Z0-9_-]+$')
      matched_tags: list[str] = Field(..., max_items=10)  # Allow buffer above 5
      sentiment: str = Field(..., regex=r'^(positive|neutral|negative)$')
      score: float = Field(..., ge=0.0, le=1.0)

      @validator('matched_tags')
      def validate_tags(cls, tags):
          if len(tags) > 10:
              raise ValueError(f"Too many tags: {len(tags)}")
          return tags
  ```
  - **Deadline**: Before demo deployment

- [ ] **ALARM-01**: CloudWatch alarm on stream iterator age > 5 minutes
  - **Deadline**: Before demo deployment

- [ ] **ALARM-02**: CloudWatch alarm on dashboard Lambda queries > 1000/hour
  - **Deadline**: Before demo deployment

- [ ] **DOC-01**: Update trust zone diagram with Zone 4a/4b split
  - **Deadline**: Before security review signoff

### Phase 1B (Staging - Global Replicas)

- [ ] **DATA-01**: Resolve data residency strategy (GDPR compliance)
  - Option 1: US-only data sources
  - Option 2: Geo-tagging + conditional replication
  - Option 3: Regional isolation (EU users → EU replica only)
  - **Deadline**: Before Phase 1B deployment

- [ ] **ALARM-03**: CloudWatch alarm on DynamoDB replication conflicts
  - **Deadline**: Before Phase 1B deployment

- [ ] **TEST-01**: Terraform validation test for IAM region conditions
  ```hcl
  # Example test: Verify IAM denies cross-region writes
  resource "test_assertions" "region_scoped_iam" {
    test {
      command = "aws dynamodb put-item --table-name sentiment-items-primary --region us-west-2"
      expect_error = "AccessDeniedException"
    }
  }
  ```
  - **Deadline**: Before Phase 1B deployment

### Phase 2 (Production - DAX Cache)

- [ ] **VPC-01**: DAX security group ONLY allows Lambda security group
  - **Deadline**: Before Phase 2 deployment

- [ ] **VPC-02**: Dashboard Lambda deployed in VPC (private subnets)
  - **Deadline**: Before Phase 2 deployment

- [ ] **ALARM-04**: CloudWatch alarm on DAX cache miss rate > 50%
  - **Deadline**: Before Phase 2 deployment

- [ ] **CODE-01**: Lambda code signing enabled (prevent unauthorized code changes)
  - **Deadline**: Before Phase 2 deployment

---

## 8. Recommendations

### 8.1 Immediate Actions (Before Demo Deployment)

1. ✅ **ADD AUTHENTICATION** to dashboard Lambda Function URL
   - Severity: 🔴 **CRITICAL**
   - Effort: 1 hour (add API key check)
   - Impact: Prevents unauthorized data exfiltration

2. ✅ **ADD INPUT VALIDATION** in stream processor Lambda
   - Severity: 🟠 **HIGH**
   - Effort: 2 hours (Pydantic schemas)
   - Impact: Prevents write amplification DoS

3. ✅ **ADD CLOUDWATCH ALARMS** for anomalous patterns
   - Severity: 🟡 **MEDIUM**
   - Effort: 1 hour (Terraform alarm definitions)
   - Impact: Early detection of attacks

### 8.2 Phased Rollout Strategy

**Phase 1A (Demo)**: Primary table + Dashboard table (NO global replicas, NO DAX)
- ✅ Minimal attack surface increase (+28%)
- ✅ No data residency concerns
- ✅ Cost: $1.19/month (affordable for demo)
- ⚠️ Authentication required before deployment

**Phase 1B (Staging)**: Add global replicas
- ⚠️ **DEFER** until data residency strategy approved
- ⚠️ Attack surface increase: +100%
- ⚠️ GDPR compliance review required

**Phase 2 (Production)**: Add DAX cache
- ⚠️ **DEFER** until read traffic > 10 queries/sec
- ⚠️ VPC security validation required
- ⚠️ Cost: $98/month (only justified at scale)

### 8.3 Security Review Signoff Criteria

Before proceeding to Terraform implementation, the following must be completed:

- [ ] Human review of this security analysis (security engineer or architect)
- [ ] Approval of phased rollout strategy (Phase 1A only for demo)
- [ ] Commitment to add authentication before demo deployment
- [ ] Commitment to add input validation in stream processor
- [ ] Update trust zone diagram (Zone 4a/4b split)
- [ ] Document data residency strategy for Phase 1B (if approved)

**Estimated Review Time**: 2-4 hours (human security review)

---

## 9. Conclusion

The "Best of All Worlds" architecture introduces **significant security complexity** but maintains **strong security boundaries** through tier isolation.

**Key Security Wins**:
- ✅ Write tier isolated from read tier (Zone 4a vs 4b)
- ✅ Dashboard Lambda compromise cannot corrupt primary table
- ✅ Region-scoped IAM prevents cross-region write attacks

**Key Security Concerns**:
- ⚠️ Stream processor crosses trust boundary (requires strict input validation)
- ⚠️ Global replicas introduce data residency risks (defer to Phase 1B)
- ⚠️ Dashboard Lambda has no authentication (fix before demo)
- ⚠️ DAX adds VPC complexity (defer to Phase 2)

**Overall Risk Rating**: 🟡 **MEDIUM** (Phase 1A), 🟠 **MEDIUM-HIGH** (Phase 1B/2)

**Recommendation**: **APPROVE Phase 1A** (primary + dashboard tables only) with required authentication fix. **DEFER Phase 1B and Phase 2** pending further security review.

---

**Document Status**: 🔴 **DRAFT - REQUIRES HUMAN REVIEW**

**Next Steps**:
1. Security engineer review this document
2. Approve phased rollout strategy
3. Proceed to Terraform implementation ("terraform next")
4. Add authentication and input validation before demo deployment

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
