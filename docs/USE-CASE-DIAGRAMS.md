# Use Case Diagrams

This document provides UML sequence diagrams for the top 5 use cases in the Sentiment Analyzer system.

**Target Audience:** All roles (developers, operators, product managers, stakeholders)

---

## Unified Color Palette

All diagrams in this project use a consistent color palette optimized for:
- **Accessibility**: WCAG 2.1 AA contrast ratios (4.5:1 minimum)
- **Consistency**: Same colors across all Mermaid diagrams
- **Readability**: Dark text on light backgrounds

### Mermaid Theme Configuration

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#e8f4fd',
    'primaryTextColor': '#1a365d',
    'primaryBorderColor': '#3182ce',
    'lineColor': '#4a5568',
    'secondaryColor': '#f0fff4',
    'tertiaryColor': '#fef3c7'
  }
}}%%
```

### Node Class Definitions

| Class Name | Purpose | Fill | Border | Text | Contrast |
|------------|---------|------|--------|------|----------|
| `userNode` | User/Actor | `#dbeafe` | `#2563eb` | `#1e3a5f` | 7.2:1 |
| `systemNode` | System Component | `#e0e7ff` | `#4f46e5` | `#1e1b4b` | 8.1:1 |
| `apiNode` | API Gateway/Endpoint | `#fef3c7` | `#d97706` | `#78350f` | 6.8:1 |
| `lambdaNode` | Lambda Function | `#ddd6fe` | `#7c3aed` | `#2e1065` | 7.5:1 |
| `storageNode` | Database/Storage | `#d1fae5` | `#059669` | `#064e3b` | 6.2:1 |
| `queueNode` | SNS/SQS Queue | `#fce7f3` | `#db2777` | `#831843` | 5.8:1 |
| `successNode` | Success State | `#bbf7d0` | `#16a34a` | `#14532d` | 5.4:1 |
| `errorNode` | Error State | `#fecaca` | `#dc2626` | `#7f1d1d` | 5.1:1 |
| `decisionNode` | Decision Point | `#fed7aa` | `#ea580c` | `#7c2d12` | 5.6:1 |
| `externalNode` | External Service | `#e5e7eb` | `#6b7280` | `#1f2937` | 9.4:1 |

### Standard Class Definitions (Copy to Diagrams)

```
classDef userNode fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
classDef systemNode fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b
classDef apiNode fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
classDef lambdaNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
classDef storageNode fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b
classDef queueNode fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
classDef successNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d
classDef errorNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
classDef externalNode fill:#e5e7eb,stroke:#6b7280,stroke-width:2px,color:#1f2937
```

---

## Table of Contents

1. [UC1: User Configures Sentiment Alerts](#uc1-user-configures-sentiment-alerts)
2. [UC2: System Processes News and Triggers Alerts](#uc2-system-processes-news-and-triggers-alerts)
3. [UC3: Anonymous User Authentication Flow](#uc3-anonymous-user-authentication-flow)
4. [UC4: CI/CD Deployment Pipeline](#uc4-cicd-deployment-pipeline)
5. [UC5: Notification Delivery Flow](#uc5-notification-delivery-flow)

---

## UC1: User Configures Sentiment Alerts

**Primary Actor:** End User (Anonymous or Authenticated)
**Goal:** Create a configuration with tickers and set up sentiment alerts
**Preconditions:** User has access to the dashboard

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant UI as Dashboard UI
    participant API as API Gateway
    participant Auth as Auth Lambda
    participant Config as Config Lambda
    participant DDB as DynamoDB
    participant Cache as Ticker Cache

    User->>UI: Open dashboard
    UI->>API: GET /api/v2/auth/anonymous
    API->>Auth: Invoke auth handler
    Auth->>DDB: Create anonymous user
    DDB-->>Auth: User created
    Auth-->>API: JWT token
    API-->>UI: Token + session
    UI-->>User: Dashboard loaded

    User->>UI: Click "New Configuration"
    UI->>API: GET /api/v2/tickers/search?q=AAPL
    API->>Config: Search tickers
    Config->>Cache: Check ticker cache
    Cache-->>Config: Cached results
    Config-->>API: Ticker suggestions
    API-->>UI: Display suggestions
    UI-->>User: Show ticker options

    User->>UI: Select tickers & set alert
    UI->>API: POST /api/v2/configurations
    API->>Config: Create configuration
    Config->>DDB: Validate user quota
    DDB-->>Config: Quota OK (< 3 configs)
    Config->>DDB: Put config item
    DDB-->>Config: Config saved
    Config->>DDB: Put alert rules
    DDB-->>Config: Alerts saved
    Config-->>API: Configuration created
    API-->>UI: Success response
    UI-->>User: Show confirmation

    Note over User,DDB: User now has active sentiment monitoring
```

**Key Points:**
- Anonymous users get JWT tokens automatically
- Ticker search uses cached data for performance
- Configuration quotas enforced (3 configs for anonymous)
- Alert rules stored with configuration

---

## UC2: System Processes News and Triggers Alerts

**Primary Actor:** System (EventBridge Scheduler)
**Goal:** Ingest news, analyze sentiment, trigger alerts when thresholds crossed
**Preconditions:** Users have active configurations with alerts

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    participant EB as EventBridge
    participant Ingest as Ingestion Lambda
    participant Tiingo as Tiingo API
    participant Finnhub as Finnhub API
    participant SNS as SNS Topic
    participant Analysis as Analysis Lambda
    participant S3 as S3 (Model)
    participant DDB as DynamoDB
    participant Alert as Alert Lambda
    participant SG as SendGrid

    EB->>Ingest: Trigger (every 5 min)
    Ingest->>Tiingo: GET /news?tickers=AAPL,MSFT
    Tiingo-->>Ingest: News articles
    Ingest->>Finnhub: GET /news?symbol=AAPL
    Finnhub-->>Ingest: Additional articles

    Ingest->>DDB: Check duplicates (hash)
    DDB-->>Ingest: New articles only
    Ingest->>DDB: Store articles (pending)
    DDB-->>Ingest: Saved
    Ingest->>SNS: Publish article IDs
    SNS-->>Ingest: Published

    SNS->>Analysis: Trigger (batch)

    alt Cold Start
        Analysis->>S3: Load DistilBERT model
        S3-->>Analysis: model.tar.gz
        Analysis->>Analysis: Cache in /tmp
    end

    loop For each article
        Analysis->>Analysis: Run inference
        Analysis->>DDB: Update with sentiment
        DDB-->>Analysis: Updated
    end

    Analysis->>DDB: Query matching alerts
    DDB-->>Analysis: Alert rules

    alt Threshold Crossed
        Analysis->>Alert: Invoke alert handler
        Alert->>DDB: Check user preferences
        DDB-->>Alert: Email enabled
        Alert->>DDB: Check email quota
        DDB-->>Alert: Quota OK
        Alert->>SG: Send alert email
        SG-->>Alert: Email queued
        Alert->>DDB: Increment quota
        DDB-->>Alert: Quota updated
        Alert->>DDB: Log notification
        DDB-->>Alert: Logged
    end

    Note over EB,SG: Complete pipeline: ingest → analyze → alert
```

**Key Points:**
- EventBridge triggers ingestion every 5 minutes
- Dual-source strategy (Tiingo primary, Finnhub secondary)
- Model lazy-loaded and cached in Lambda /tmp
- Alerts checked after each sentiment update
- Email quota enforced before sending

---

## UC3: Anonymous User Authentication Flow

**Primary Actor:** New User
**Goal:** Access the application without registration
**Preconditions:** None (public access)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant CF as CloudFront
    participant API as API Gateway
    participant Auth as Auth Lambda
    participant Captcha as hCaptcha
    participant DDB as DynamoDB
    participant SM as Secrets Manager

    User->>Browser: Visit dashboard URL
    Browser->>CF: GET /
    CF-->>Browser: SPA bundle (index.html)
    Browser->>Browser: Initialize React app

    Browser->>API: GET /api/v2/auth/anonymous
    API->>Auth: Invoke handler

    Auth->>SM: Get JWT secret
    SM-->>Auth: Secret value

    alt Rate Limited
        Auth->>DDB: Check rate limit
        DDB-->>Auth: Limit exceeded
        Auth-->>API: 429 Too Many Requests
        API-->>Browser: Rate limit error
        Browser-->>User: Show retry message
    else Within Limits
        Auth->>DDB: Check rate limit
        DDB-->>Auth: OK
        Auth->>DDB: Create anonymous user
        Note over Auth,DDB: PK: USER#{uuid}<br/>SK: PROFILE<br/>auth_type: anonymous
        DDB-->>Auth: User created
        Auth->>Auth: Generate JWT (24h expiry)
        Auth-->>API: JWT + refresh token
        API-->>Browser: Set cookies
        Browser->>Browser: Store in memory
        Browser-->>User: Dashboard ready
    end

    Note over User,DDB: Anonymous sessions last 24 hours

    rect rgb(254, 243, 199)
        Note over User,DDB: Optional: User upgrades account
        User->>Browser: Click "Sign in with Google"
        Browser->>API: GET /api/v2/auth/google
        API->>Auth: OAuth redirect
        Auth-->>Browser: Redirect to Google
        Browser->>Browser: Google OAuth flow
        Browser->>API: Callback with code
        API->>Auth: Exchange code
        Auth->>DDB: Merge anonymous → Google
        Note over Auth,DDB: Preserve configs/alerts<br/>Update auth_type: google
        DDB-->>Auth: User merged
        Auth-->>API: New JWT
        API-->>Browser: Upgraded session
        Browser-->>User: Account linked
    end
```

**Key Points:**
- Anonymous access without friction (no captcha for read)
- Rate limiting protects against abuse
- JWT stored in memory (XSS protection)
- Seamless upgrade path to OAuth
- Anonymous data preserved on upgrade

---

## UC4: CI/CD Deployment Pipeline

**Primary Actor:** Developer
**Goal:** Deploy code changes through preprod to production
**Preconditions:** Code changes committed to feature branch

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant GH as GitHub
    participant CI as GitHub Actions
    participant S3 as S3 Artifacts
    participant TF as Terraform
    participant AWS as AWS (Preprod)
    participant Prod as AWS (Prod)

    Dev->>GH: Push feature branch
    GH->>CI: Trigger workflow

    par Parallel Checks
        CI->>CI: Run pytest (unit tests)
        CI->>CI: Run black (formatting)
        CI->>CI: Run ruff (linting)
        CI->>CI: Run terraform validate
    end

    CI-->>GH: All checks passed

    Dev->>GH: Create Pull Request
    GH->>CI: PR checks workflow
    CI->>CI: Run E2E tests (mocked)
    CI-->>GH: PR ready for review

    Dev->>GH: Merge to main
    GH->>CI: Deploy workflow triggered

    rect rgb(219, 234, 254)
        Note over CI,AWS: Preprod Deployment
        CI->>CI: Build Lambda packages
        CI->>S3: Upload SHA-versioned ZIPs
        S3-->>CI: Upload complete
        CI->>TF: terraform plan (preprod)
        TF-->>CI: Plan output
        CI->>TF: terraform apply (preprod)
        TF->>AWS: Create/update resources
        AWS-->>TF: Resources deployed
        TF-->>CI: Apply complete
    end

    CI->>AWS: Run integration tests
    AWS-->>CI: Tests passed

    rect rgb(254, 226, 226)
        Note over CI,Prod: Production Deployment (Protected)
        CI->>GH: Request approval
        GH-->>Dev: Approval notification
        Dev->>GH: Approve deployment
        GH->>CI: Approval granted
        CI->>TF: terraform plan (prod)
        TF-->>CI: Plan output
        CI->>TF: terraform apply (prod)
        TF->>Prod: Create/update resources
        Prod-->>TF: Resources deployed
        TF-->>CI: Apply complete
    end

    CI->>Prod: Run smoke tests
    Prod-->>CI: Smoke tests passed
    CI-->>GH: Deployment successful
    GH-->>Dev: Notification

    Note over Dev,Prod: Full deployment: ~15 minutes
```

**Key Points:**
- Parallel CI checks for speed
- Preprod deployment automatic on merge
- Production requires manual approval
- SHA-versioned artifacts for rollback
- Integration tests gate production

---

## UC5: Notification Delivery Flow

**Primary Actor:** System (Alert Trigger)
**Goal:** Deliver alert notification via email with quota management
**Preconditions:** Alert threshold crossed, user has email enabled

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    participant Analysis as Analysis Lambda
    participant SNS as Alert SNS
    participant Notify as Notification Lambda
    participant DDB as DynamoDB
    participant CB as Circuit Breaker
    participant SG as SendGrid API
    participant DLQ as Dead Letter Queue
    participant User as User Inbox

    Analysis->>SNS: Publish alert event
    Note over Analysis,SNS: {user_id, ticker, sentiment,<br/>threshold, alert_id}
    SNS->>Notify: Trigger notification

    Notify->>DDB: Get user preferences
    DDB-->>Notify: Preferences

    alt Email Disabled
        Notify->>DDB: Log skipped notification
        DDB-->>Notify: Logged
        Notify-->>SNS: Complete (skipped)
    else Email Enabled
        Notify->>DDB: Check email quota
        DDB-->>Notify: Quota status

        alt Quota Exceeded
            Notify->>DDB: Log quota exceeded
            DDB-->>Notify: Logged
            Notify-->>SNS: Complete (quota)
        else Quota OK
            Notify->>CB: Check SendGrid circuit
            CB-->>Notify: Circuit status

            alt Circuit Open
                Notify->>DLQ: Queue for retry
                DLQ-->>Notify: Queued
                Notify-->>SNS: Deferred
            else Circuit Closed
                Notify->>SG: POST /mail/send

                alt SendGrid Success
                    SG-->>Notify: 202 Accepted
                    SG->>User: Deliver email
                    Notify->>DDB: Increment quota
                    DDB-->>Notify: Quota updated
                    Notify->>DDB: Log notification sent
                    DDB-->>Notify: Logged
                    Notify->>CB: Record success
                    CB-->>Notify: OK
                    Notify-->>SNS: Complete (sent)
                else SendGrid Failure
                    SG-->>Notify: Error (429/5xx)
                    Notify->>CB: Record failure
                    CB-->>Notify: Updated

                    alt Retry Available
                        Notify->>DLQ: Queue for retry
                        DLQ-->>Notify: Queued
                        Notify-->>SNS: Retry scheduled
                    else Max Retries
                        Notify->>DDB: Log permanent failure
                        DDB-->>Notify: Logged
                        Notify-->>SNS: Failed
                    end
                end
            end
        end
    end

    Note over Analysis,User: Email quota: 100/day (SendGrid free tier)
```

**Key Points:**
- User preferences checked first (respect opt-out)
- Quota enforced (100 emails/day free tier)
- Circuit breaker prevents cascade failures
- DLQ enables retry with backoff
- All outcomes logged for debugging

---

## Diagram Legend

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart LR
    subgraph Legend["Color Legend"]
        U[User/Actor]
        S[System Component]
        A[API Endpoint]
        L[Lambda Function]
        D[Database/Storage]
        Q[Message Queue]
        OK[Success State]
        ERR[Error State]
        DEC[Decision Point]
        EXT[External Service]
    end

    classDef userNode fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef systemNode fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b
    classDef apiNode fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef lambdaNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
    classDef storageNode fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b
    classDef queueNode fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
    classDef successNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef errorNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef externalNode fill:#e5e7eb,stroke:#6b7280,stroke-width:2px,color:#1f2937

    class U userNode
    class S systemNode
    class A apiNode
    class L lambdaNode
    class D storageNode
    class Q queueNode
    class OK successNode
    class ERR errorNode
    class DEC decisionNode
    class EXT externalNode
```

---

## Additional Resources

- [OPERATIONAL_FLOWS.md](OPERATIONAL_FLOWS.md) - Troubleshooting flowcharts
- [TERRAFORM_DEPLOYMENT_FLOW.md](TERRAFORM_DEPLOYMENT_FLOW.md) - Infrastructure diagrams
- [docs/diagrams/README.md](diagrams/README.md) - Canva diagram specifications

---

**Last Updated:** 2025-11-29
**Diagram Count:** 5 sequence diagrams + 1 legend
