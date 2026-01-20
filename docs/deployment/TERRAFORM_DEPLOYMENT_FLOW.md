# Terraform Deployment Flow

This document explains the Terraform deployment process with visual diagrams for different roles.

## Overview Diagram

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart TB
    subgraph DevWorkflow["Developer Workflow"]
        A[Push to main] --> B{Paths changed?}
        B -->|src/** or terraform/**| C[Trigger Deploy Dev]
        B -->|Other| D[Skip Deploy]
    end

    subgraph DeployWorkflow["Deploy Dev Workflow"]
        C --> E[Checkout Code]
        E --> F[Configure AWS Credentials]
        F --> G[Check for S3 Lock Files]
        G --> H{Lock File Exists?}
        H -->|Yes| I[Report Lock & Proceed]
        H -->|No| J[Continue]
        I --> J
        J --> K[Package Lambda Functions]
        K --> L[Upload to S3]
        L --> M[Terraform Init]
        M --> N[Terraform Plan]
        N --> O[Terraform Apply]
        O --> P[Update Lambda Code]
        P --> Q[Verify Deployment]
        Q --> R{Success?}
        R -->|Yes| S[Trigger Integration Tests]
        R -->|No| T[Deployment Failed]
    end

    subgraph IntegrationTests["Integration Tests"]
        S --> U[Run pytest]
        U --> V[Validate Data Flow]
        V --> W[Check Lambda Health]
        W --> X{Tests Pass?}
        X -->|Yes| Y[Deployment Complete]
        X -->|No| Z[Tests Failed]
    end

    classDef stageBox fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef processNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
    classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef successNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef failNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d

    class DevWorkflow,DeployWorkflow,IntegrationTests stageBox
    class A,C,D,E,F,G,I,J,K,L,M,N,O,P,Q,S,U,V,W processNode
    class B,H,R,X decisionNode
    class Y successNode
    class T,Z failNode
```

## Resource Creation Order

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart LR
    subgraph Phase1["Phase 1: Foundation"]
        A[S3 Buckets<br/>Lambda Deployments<br/>ML Model Storage]
        B[Secrets Manager]
        C[SNS Topic & DLQ]
        D[DynamoDB Table]
    end

    subgraph Phase2["Phase 2: IAM"]
        E[IAM Roles]
        F[IAM Policies]
    end

    subgraph Phase3["Phase 3: Compute"]
        G[Lambda Functions]
        H[Function URLs]
        I[CloudWatch Log Groups]
    end

    subgraph Phase4["Phase 4: Triggers"]
        J[EventBridge Rules]
        K[SNS Subscriptions]
        L[Lambda Permissions]
    end

    subgraph Phase5["Phase 5: Monitoring"]
        M[CloudWatch Alarms]
        N[Budget Alerts]
        O[Backup Plans]
    end

    A --> E
    B --> E
    C --> E
    D --> E
    E --> F
    F --> G
    G --> H
    G --> I
    G --> J
    G --> K
    G --> L
    G --> M

    classDef stageBox fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef phase1Node fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef phase2Node fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b
    classDef phase3Node fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b
    classDef phase4Node fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef phase5Node fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843

    class Phase1,Phase2,Phase3,Phase4,Phase5 stageBox
    class A,B,C,D phase1Node
    class E,F phase2Node
    class G,H,I phase3Node
    class J,K,L phase4Node
    class M,N,O phase5Node
```

## State Management Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub Actions
    participant S3 as S3 State Bucket
    participant Lock as S3 Lock File
    participant AWS as AWS Resources

    Dev->>GH: Push to main
    GH->>Lock: Create .tflock file

    alt Lock created
        Lock-->>GH: Lock acquired
        GH->>S3: Read current state
        S3-->>GH: State file
        GH->>AWS: terraform plan
        AWS-->>GH: Planned changes
        GH->>AWS: terraform apply
        AWS-->>GH: Apply complete
        GH->>S3: Write new state
        GH->>Lock: Delete .tflock file
    else Lock file exists
        Lock-->>GH: Lock denied
        GH->>GH: Wait (lock-timeout=5m)
        alt Lock file deleted
            GH->>Lock: Retry create
        else Timeout
            GH-->>Dev: Deployment failed
        end
    end
```

---

## Role-Specific Views

### For Developers

**What you need to know:**

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart LR
    A[Your Code Change] --> B[Push to main]
    B --> C[CI Runs Automatically]
    C --> D{Deploy Success?}
    D -->|Yes| E[Integration Tests Run]
    D -->|No| F[Check Terraform Plan Output]
    E --> G{Tests Pass?}
    G -->|Yes| H[Done!]
    G -->|No| I[Check Test Logs]

    classDef processNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
    classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef successNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef errorNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d

    class A,B,C,E processNode
    class D,G decisionNode
    class H successNode
    class F,I errorNode
```

**Key Points:**
- Merging to main triggers automatic deployment
- Watch the Deploy Dev workflow for your changes
- Integration tests validate the deployment worked
- Never run `terraform` locally during CI deployment

### For On-Call Engineers

**Incident Response Flow:**

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart TB
    A[Alert: Deploy Failed] --> B{Check Error Type}

    B -->|State Lock| C[Check S3 Lock File]
    C --> D{Lock File Exists?}
    D -->|Yes| E[Delete lock file via aws s3 rm]
    D -->|No| F[Check workflow logs]

    B -->|Resource Exists| G[Resource created outside Terraform]
    G --> H[Import into state]
    H --> I[terraform import command]

    B -->|Permission Denied| J[Check IAM policies]
    J --> K[Verify role has required permissions]

    B -->|S3 NoSuchKey| L[Lambda package missing]
    L --> M[Check S3 upload step succeeded]

    classDef alertNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef processNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
    classDef actionNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d

    class A alertNode
    class B,D decisionNode
    class C,F,G,H,J,L processNode
    class E,I,K,M actionNode
```

**Recovery Commands:**

```bash
# Remove orphaned lock file
aws s3 rm s3://sentiment-analyzer-terraform-state-218795110243/dev/terraform.tfstate.tflock

# Or use terraform force-unlock with Lock ID from workflow logs
cd infrastructure/terraform
terraform force-unlock <LOCK_ID>

# Import missing resource
terraform import -var="environment=dev" "RESOURCE_ADDRESS" "RESOURCE_ID"

# Refresh state after manual changes
terraform refresh -var="environment=dev"
```

### For DevOps/Platform Engineers

**Infrastructure Dependencies:**

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
graph TB
    subgraph StateBackend["Terraform State Backend"]
        A[S3 Bucket<br/>sentiment-analyzer-terraform-state-*]
        B[S3 Lock Files<br/>*.tfstate.tflock]
    end

    subgraph GHSecrets["GitHub Secrets Required"]
        C[AWS_ACCESS_KEY_ID]
        D[AWS_SECRET_ACCESS_KEY]
        E[AWS_REGION]
        F[DEPLOYMENT_BUCKET]
    end

    subgraph AWSResources["AWS Resources Managed"]
        G[3x Lambda Functions]
        H[1x DynamoDB Table]
        I[2x Secrets Manager]
        J[1x S3 Bucket]
        K[1x SNS Topic + DLQ]
        L[1x EventBridge Rule]
        M[8x CloudWatch Alarms]
        N[1x Budget]
        O[1x Backup Plan]
    end

    A --> G
    B --> G
    C --> G
    D --> G
    E --> G
    F --> G

    classDef stageBox fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef stateNode fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065
    classDef secretNode fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#1e1b4b
    classDef resourceNode fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#064e3b

    class StateBackend,GHSecrets,AWSResources stageBox
    class A,B stateNode
    class C,D,E,F secretNode
    class G,H,I,J,K,L,M,N,O resourceNode
```

**Terraform Module Structure:**

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
graph LR
    subgraph MainTF["main.tf"]
        A[Root Module]
    end

    subgraph Modules["Modules"]
        B[modules/lambda]
        C[modules/iam]
        D[modules/dynamodb]
        E[modules/sns]
        F[modules/secrets]
        G[modules/monitoring]
        H[modules/eventbridge]
    end

    A --> B
    A --> C
    A --> D
    A --> E
    A --> F
    A --> G
    A --> H

    classDef stageBox fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef rootModule fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef childModule fill:#ddd6fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065

    class MainTF,Modules stageBox
    class A rootModule
    class B,C,D,E,F,G,H childModule
```

---

## CI/CD Pipeline Timeline

```mermaid
gantt
    title Deploy Dev Workflow Timeline
    dateFormat mm:ss
    axisFormat %M:%S

    section Setup
    Checkout           :a1, 00:00, 10s
    AWS Credentials    :a2, after a1, 5s
    Check S3 Lock Files:a3, after a2, 10s

    section Build
    Setup Python       :b1, after a3, 15s
    Install Deps       :b2, after b1, 30s
    Package Lambdas    :b3, after b2, 20s
    Upload to S3       :b4, after b3, 15s

    section Terraform
    Init               :c1, after b4, 10s
    Plan               :c2, after c1, 30s
    Apply              :c3, after c2, 60s

    section Deploy
    Update Lambdas     :d1, after c3, 20s
    Verify             :d2, after d1, 10s
```

---

## Troubleshooting Decision Tree

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#e8f4fd', 'primaryTextColor': '#1a365d', 'primaryBorderColor': '#3182ce', 'lineColor': '#4a5568'}}}%%
flowchart TD
    A[Deployment Failed] --> B{Which step failed?}

    B -->|Configure AWS| C[Check GitHub Secrets]
    C --> C1[Verify AWS_ACCESS_KEY_ID set]
    C --> C2[Verify AWS_SECRET_ACCESS_KEY set]
    C --> C3[Verify AWS_REGION = us-east-1]

    B -->|Upload to S3| D[Check S3 Configuration]
    D --> D1[Verify DEPLOYMENT_BUCKET secret]
    D --> D2[Verify bucket exists in us-east-1]

    B -->|Terraform Init| E[Check State Backend]
    E --> E1[Verify S3 state bucket exists]
    E --> E2[Verify S3 lock file permissions]

    B -->|Terraform Plan| F[Check Resources]
    F --> F1[Run terraform plan locally]
    F --> F2[Check for resource conflicts]

    B -->|Terraform Apply| G[Check Apply Errors]
    G --> G1{Error type?}
    G1 -->|AlreadyExists| G2[Import resource into state]
    G1 -->|NoSuchKey| G3[S3 upload path mismatch]
    G1 -->|Permission| G4[Update IAM policies]

    B -->|Update Lambda| H[Check Lambda Status]
    H --> H1[Verify functions exist]
    H --> H2[Check S3 key paths match]

    classDef errorNode fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef decisionNode fill:#fed7aa,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef checkNode fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef actionNode fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#14532d

    class A errorNode
    class B,G1 decisionNode
    class C,D,E,F,G,H checkNode
    class C1,C2,C3,D1,D2,E1,E2,F1,F2,G2,G3,G4,H1,H2 actionNode
```

---

## Quick Reference

| Workflow | Trigger | Duration | On Failure |
|----------|---------|----------|------------|
| Deploy Dev | Push to main (src/**, terraform/**) | ~2-3 min | Check Terraform logs |
| Integration Tests | After Deploy Dev success | ~2 min | Check pytest output |

| Secret | Purpose | Required By |
|--------|---------|-------------|
| AWS_ACCESS_KEY_ID | AWS authentication | Deploy, Integration |
| AWS_SECRET_ACCESS_KEY | AWS authentication | Deploy, Integration |
| AWS_REGION | Target region (us-east-1) | Deploy, Integration |
| DEPLOYMENT_BUCKET | Lambda package storage | Deploy |

---

*Diagrams created with Mermaid. View in GitHub or any Mermaid-compatible viewer.*
