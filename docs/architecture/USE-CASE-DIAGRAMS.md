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

## UC3: User Authentication Flow (v3.0)

**Primary Actor:** New/Returning User
**Goal:** Authenticate via anonymous, magic link, or OAuth
**Preconditions:** None (public access)
**Roles:** anonymous → free → paid → operator (v3.0 hierarchy)

### UC3.1: Anonymous Authentication

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Amplify as Amplify<br/>(Next.js SSR)
    participant API as API Gateway
    participant Auth as Auth Lambda
    participant DDB as DynamoDB
    participant SM as Secrets Manager
    participant Cognito as Cognito

    User->>Browser: Visit dashboard URL
    Browser->>Amplify: GET /
    Amplify-->>Browser: Next.js SSR page
    Browser->>Browser: Hydrate React app

    Browser->>API: POST /api/v2/auth/anonymous
    API->>Auth: Invoke handler

    Auth->>SM: Get JWT_SECRET
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
        Note over Auth,DDB: PK: USER#{uuid}<br/>SK: PROFILE<br/>role: anonymous<br/>verification: none
        DDB-->>Auth: User created
        Auth->>Cognito: Generate JWT with jti claim
        Note over Auth,Cognito: JWT includes:<br/>sub, role, iat, exp, jti
        Cognito-->>Auth: Access token (15min)
        Auth->>DDB: Create session
        Note over Auth,DDB: sessions table<br/>TTL: 7 days
        Auth-->>API: Body: {access_token, user}
        Note over API,Browser: Set-Cookie: refresh_token<br/>HttpOnly; Secure; SameSite=None<br/>Path=/api/v2/auth
        API-->>Browser: Response + HttpOnly cookie
        Browser->>Browser: Store access_token in MEMORY ONLY
        Note over Browser: Never localStorage/sessionStorage
        Browser-->>User: Dashboard ready (role: anonymous)
    end
```

### UC3.2: Magic Link Authentication

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Auth as Auth Lambda
    participant DDB as DynamoDB
    participant SendGrid as SendGrid

    User->>Browser: Enter email address
    Browser->>Auth: POST /api/v2/auth/magic-link {email}

    Auth->>DDB: Check rate limit (5/hour/email)
    DDB-->>Auth: OK

    Auth->>Auth: Generate secrets.token_urlsafe(32)
    Note over Auth: 256-bit random token (NOT HMAC)

    Auth->>DDB: Store in magic-link-tokens
    Note over DDB: PK: TOKEN#{random}<br/>email, expires_at (1h)<br/>used: false, ttl
    DDB-->>Auth: Token stored

    Auth->>SendGrid: Send email
    Note over SendGrid: Link: /auth/verify/<token><br/>Token in PATH (NOT query string)<br/>Prevents Referer header leak
    SendGrid-->>Auth: Sent
    Auth-->>Browser: 200 OK (check email)
    Browser-->>User: Check your email

    Note over User,DDB: User clicks link in email

    User->>Browser: Click magic link
    Browser->>Auth: GET /api/v2/auth/magic-link/verify/<token>

    Auth->>DDB: Atomic conditional update
    Note over DDB: ConditionExpression:<br/>used = false AND expires_at > now<br/>SET used = true, used_at = now

    alt Token Valid (atomic success)
        DDB-->>Auth: Update succeeded
        Auth->>DDB: Create/update user
        Note over DDB: role: free<br/>verification: verified<br/>primary_email: {email}
        Auth->>DDB: Create session
        Auth-->>Browser: Access token + HttpOnly refresh cookie
        Browser-->>User: Authenticated (role: free)
    else Token Invalid/Used
        DDB-->>Auth: Condition check failed
        Auth-->>Browser: 400 Invalid/expired token
        Browser-->>User: Link expired or already used
    end
```

### UC3.3: OAuth Authentication with PKCE (RFC 7636)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Auth as Auth Lambda
    participant DDB as DynamoDB
    participant Cognito as Cognito
    participant Google as Google OAuth

    User->>Browser: Click "Sign in with Google"
    Browser->>Auth: GET /api/v2/auth/oauth/urls?provider=google

    Auth->>Auth: Generate PKCE pair
    Note over Auth: code_verifier: 43-128 chars<br/>code_challenge: base64url(SHA256(verifier))

    Auth->>Auth: Generate state parameter
    Note over Auth: Cryptographically random

    Auth->>DDB: Store in oauth-states
    Note over DDB: PK: OAUTH_STATE#{state}<br/>code_verifier, provider: google<br/>ip, user_agent, TTL: 5min
    DDB-->>Auth: Stored

    Auth-->>Browser: OAuth URL with state + code_challenge
    Browser->>Google: Redirect with PKCE challenge

    Note over Google: User authenticates

    Google-->>Browser: Redirect with code + state
    Browser->>Auth: POST /api/v2/auth/oauth/callback/google

    Auth->>DDB: Consume oauth-state (atomic)
    Note over DDB: Get and delete state<br/>One-time use
    DDB-->>Auth: code_verifier, provider

    Auth->>Auth: Validate provider matches (A13)
    Note over Auth: state.provider == "google"<br/>Prevents provider confusion

    Auth->>Cognito: Exchange code WITH code_verifier
    Note over Cognito: PKCE prevents code interception
    Cognito->>Google: Token exchange
    Google-->>Cognito: ID token + access token
    Cognito-->>Auth: JWT with jti claim

    Auth->>DDB: Create/update user
    Note over DDB: role: free<br/>verification: verified<br/>provider_metadata.google: {sub, avatar}

    Auth->>DDB: Create session (TransactWriteItems)
    Note over DDB: A11: Atomic session eviction<br/>if sessions > limit

    Auth-->>Browser: Access token + HttpOnly refresh cookie
    Browser->>Browser: Store access_token in MEMORY ONLY
    Browser-->>User: Authenticated (role: free)
```

### UC3.4: Identity Linking Scenarios (5 Flows)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
stateDiagram-v2
    [*] --> anonymous: App Start

    state "Flow 1: Anonymous → Magic Link" as F1
    anonymous --> F1: POST /auth/magic-link
    F1 --> free_email: Click verify link
    Note right of F1: Merge anonymous data<br/>role: anonymous → free

    state "Flow 2: Anonymous → OAuth" as F2
    anonymous --> F2: OAuth callback
    F2 --> free_oauth: OAuth success
    Note right of F2: Require email_verified: true<br/>Abandon pending magic link

    state "Flow 3: Email → OAuth (Same Domain)" as F3
    free_email --> F3: @gmail.com + Google
    F3 --> linked_both: Auto-link
    Note right of F3: Same domain = auto-link<br/>No manual confirmation

    state "Flow 4: OAuth → Magic Link" as F4
    free_oauth --> F4: POST /auth/magic-link
    F4 --> linked_both: Click verify link
    Note right of F4: Add email verification<br/>Link on success

    state "Flow 5: OAuth → OAuth" as F5
    free_oauth --> F5: Different provider
    F5 --> linked_both: Auto-link
    Note right of F5: Both OAuth verified<br/>Auto-link allowed

    linked_both --> [*]: Full access
```

### UC3.5: Session State Machine

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
stateDiagram-v2
    [*] --> UNAUTH: App Start

    UNAUTH --> AUTHED_ANONYMOUS: POST /auth/anonymous
    UNAUTH --> MAGIC_LINK_PENDING: POST /auth/magic-link
    UNAUTH --> OAUTH_PENDING: GET /auth/oauth/urls

    MAGIC_LINK_PENDING --> AUTHED_MAGIC_LINK: GET /auth/magic-link/verify/{token}
    MAGIC_LINK_PENDING --> UNAUTH: Token expires (1h)

    OAUTH_PENDING --> AUTHED_OAUTH: POST /auth/oauth/callback
    OAUTH_PENDING --> UNAUTH: State expires (5m)

    AUTHED_ANONYMOUS --> AUTHED_MAGIC_LINK: Magic link upgrade
    AUTHED_ANONYMOUS --> AUTHED_OAUTH: OAuth upgrade
    AUTHED_ANONYMOUS --> UNAUTH: POST /auth/signout

    AUTHED_MAGIC_LINK --> SESSION_EVICTED: Session limit exceeded
    AUTHED_MAGIC_LINK --> UNAUTH: POST /auth/signout
    AUTHED_MAGIC_LINK --> UNAUTH: Refresh token expires (7d)

    AUTHED_OAUTH --> SESSION_EVICTED: Session limit exceeded
    AUTHED_OAUTH --> UNAUTH: POST /auth/signout
    AUTHED_OAUTH --> UNAUTH: Refresh token expires (7d)

    SESSION_EVICTED --> UNAUTH: 401 on next request
```

### UC3.6: CSRF Protection (Double-Submit Cookie)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Auth as Auth Lambda

    Note over Browser,Auth: On authentication success
    Auth-->>Browser: Set-Cookie: csrf_token=xyz
    Note over Browser: HttpOnly: false (JS must read)<br/>Secure; SameSite=None; Path=/api/v2

    User->>Browser: Submit form (POST/PUT/PATCH/DELETE)
    Browser->>Browser: Read csrf_token cookie
    Browser->>Auth: Request with X-CSRF-Token: xyz
    Note over Browser,Auth: Cookie sent automatically<br/>Header set by JS

    Auth->>Auth: Compare cookie vs header
    Note over Auth: secrets.compare_digest()<br/>Timing-safe comparison

    alt Match
        Auth->>Auth: Process request
        Auth-->>Browser: 200 OK
    else Mismatch
        Auth-->>Browser: 403 CSRF validation failed
    end

    Note over Auth: Exempt endpoints:<br/>/auth/refresh (cookie-only)<br/>/auth/oauth/callback (state protection)
```

**Key Points:**
- **Roles:** anonymous (lowest) → free → paid → operator (highest, v3.0)
- **Access token:** MEMORY ONLY (never localStorage/sessionStorage)
- **Refresh token:** HttpOnly; Secure; SameSite=None; Path=/api/v2/auth
- **JWT claims:** sub, role, iat, exp, jti (Cognito generates jti)
- **PKCE:** Required for OAuth (RFC 7636) - prevents code interception
- **State validation (A13):** Provider must match stored state
- **Magic link tokens:** Random (NOT HMAC), in URL path (NOT query string)
- **Session eviction (A11):** TransactWriteItems for atomic eviction
- **CSRF:** Double-submit cookie pattern (exempt: refresh, callback)
- **5 identity linking flows:** All documented with auto-link rules

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
