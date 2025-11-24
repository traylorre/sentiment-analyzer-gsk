# IAM Permissions Required for Container Migration

**Date**: 2025-11-24
**Status**: PLANNING - Not yet implemented
**Related**: `CONTAINER_MIGRATION_SECURITY_ANALYSIS.md`

---

## Current State (ZIP Packaging with Docker Build)

**As of commit**: Current HEAD

The Dashboard Lambda uses **ZIP packaging** built inside a Docker container for binary compatibility:

```yaml
docker run --rm \
  -v $(pwd)/packages:/workspace \
  public.ecr.aws/lambda/python:3.13 \
  bash -c "pip install ... -t /workspace/dashboard-deps/"
```

**IAM Permissions**: ✅ No ECR permissions needed (Docker used only for local build, not deployment)

**Security Posture**:
- Lambda uses ZIP package uploaded to S3 (via Terraform)
- No container registry involved
- No new attack surface

---

## Future State (Full Container Image Deployment)

**When**: Planned for PR #59 (after preprod HTTP 502 fix is validated)

The Dashboard Lambda will use **ECR container images**:

```dockerfile
FROM public.ecr.aws/lambda/python:3.13@sha256:abc123...
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
CMD ["handler.lambda_handler"]
```

**IAM Permissions**: ❌ ECR permissions REQUIRED

---

## Required IAM Policy Updates

### 1. CI/CD Role (GitHub Actions)

**Location**: Create new file `infrastructure/terraform/modules/iam/cicd.tf`

```hcl
# ===================================================================
# CI/CD GitHub Actions IAM Role (OIDC)
# ===================================================================

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "github_actions_deploy" {
  name = "github-actions-deploy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:traylorre/sentiment-analyzer-gsk:*"
          }
        }
      }
    ]
  })

  tags = {
    Purpose = "CI/CD"
    ManagedBy = "Terraform"
  }
}

# ECR Push Permissions (for container image deployment)
resource "aws_iam_role_policy" "github_actions_ecr_push" {
  name = "ecr-push-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRGetAuthorizationToken"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"  # AWS limitation: this action requires wildcard
      },
      {
        Sid    = "ECRPushDashboardImage"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
          "ecr:DescribeImages",
          "ecr:DescribeRepositories"
        ]
        Resource = [
          "arn:aws:ecr:us-east-1:${data.aws_caller_identity.current.account_id}:repository/preprod-sentiment-dashboard",
          "arn:aws:ecr:us-east-1:${data.aws_caller_identity.current.account_id}:repository/prod-sentiment-dashboard"
        ]
      }
    ]
  })
}

# Terraform State Management (existing - document for completeness)
resource "aws_iam_role_policy" "github_actions_terraform" {
  name = "terraform-state-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TerraformStateRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::sentiment-analyzer-terraform-state-${data.aws_caller_identity.current.account_id}/*"
      },
      {
        Sid    = "TerraformStateLocking"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::sentiment-analyzer-terraform-state-${data.aws_caller_identity.current.account_id}/*/.tflock"
      }
    ]
  })
}

# Lambda Update Permissions (existing - document for completeness)
resource "aws_iam_role_policy" "github_actions_lambda" {
  name = "lambda-update-policy"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaUpdateCode"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:PublishVersion",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration"
        ]
        Resource = [
          "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:preprod-*",
          "arn:aws:lambda:us-east-1:${data.aws_caller_identity.current.account_id}:function:prod-*"
        ]
      }
    ]
  })
}
```

---

### 2. Dashboard Lambda Role (Runtime)

**Location**: Update existing `infrastructure/terraform/modules/iam/main.tf`

**Add after line 332** (after dashboard_metrics policy):

```hcl
# Dashboard Lambda: ECR Image Pull (for container deployment)
# NOTE: Only needed when Dashboard Lambda uses container images
# Safe to add even before migration (no-op if using ZIP)
resource "aws_iam_role_policy" "dashboard_ecr_pull" {
  name = "${var.environment}-dashboard-ecr-pull-policy"
  role = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRGetAuthorizationToken"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"  # AWS limitation: this action requires wildcard
      },
      {
        Sid    = "ECRPullDashboardImage"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = "arn:aws:ecr:us-east-1:${var.account_id}:repository/${var.environment}-sentiment-dashboard"
      }
    ]
  })
}
```

**Add to** `infrastructure/terraform/modules/iam/variables.tf`:

```hcl
variable "account_id" {
  description = "AWS Account ID for ECR repository ARNs"
  type        = string
}
```

---

### 3. ECR Repository Resources

**Location**: Create new module `infrastructure/terraform/modules/ecr/main.tf`

```hcl
# ===================================================================
# ECR Repositories for Lambda Container Images
# ===================================================================

resource "aws_ecr_repository" "dashboard" {
  name                 = "${var.environment}-sentiment-dashboard"
  image_tag_mutability = "IMMUTABLE"  # P0 Security Control

  image_scanning_configuration {
    scan_on_push = true  # P0 Security Control
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
  }

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Lambda      = "dashboard"
    ManagedBy   = "Terraform"
  }
}

# KMS Key for ECR Encryption
resource "aws_kms_key" "ecr" {
  description             = "${var.environment} ECR encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Environment = var.environment
    Purpose     = "ECR-Encryption"
    ManagedBy   = "Terraform"
  }
}

resource "aws_kms_alias" "ecr" {
  name          = "alias/${var.environment}-ecr-sentiment-analyzer"
  target_key_id = aws_kms_key.ecr.key_id
}

# Lifecycle Policy: Delete untagged images after 7 days
resource "aws_ecr_lifecycle_policy" "dashboard" {
  repository = aws_ecr_repository.dashboard.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Delete untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 10 production images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["prod-"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Repository Policy: Restrict access to CI/CD and Lambda roles only
resource "aws_ecr_repository_policy" "dashboard" {
  repository = aws_ecr_repository.dashboard.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCICDPush"
        Effect = "Allow"
        Principal = {
          AWS = var.cicd_role_arn
        }
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]
      },
      {
        Sid    = "AllowLambdaPull"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}
```

**Create** `infrastructure/terraform/modules/ecr/variables.tf`:

```hcl
variable "environment" {
  description = "Environment name (preprod or prod)"
  type        = string
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "cicd_role_arn" {
  description = "ARN of CI/CD IAM role (GitHub Actions)"
  type        = string
}
```

**Create** `infrastructure/terraform/modules/ecr/outputs.tf`:

```hcl
output "repository_url" {
  description = "ECR repository URL for Dashboard Lambda"
  value       = aws_ecr_repository.dashboard.repository_url
}

output "repository_arn" {
  description = "ECR repository ARN for Dashboard Lambda"
  value       = aws_ecr_repository.dashboard.arn
}

output "kms_key_arn" {
  description = "KMS key ARN for ECR encryption"
  value       = aws_kms_key.ecr.arn
}
```

---

## Security Review Checklist

Before deploying ECR permissions to production:

- [ ] **Principle of Least Privilege**: ECR push limited to CI/CD role only
- [ ] **Separation of Duties**: CI/CD can push, Lambda can only pull (not push)
- [ ] **Encryption**: ECR uses KMS encryption (not default AWS managed key)
- [ ] **Immutability**: Image tags cannot be overwritten (prevents malicious replacement)
- [ ] **Scanning**: Images scanned on push (CVE detection before deployment)
- [ ] **Lifecycle**: Old images auto-deleted (reduces attack surface, saves costs)
- [ ] **Audit**: CloudTrail logs all ECR operations (push, pull, delete)
- [ ] **Resource Restriction**: IAM policies specify exact repository ARNs (no wildcards)

---

## Deployment Order

**Phase 1** (Current): ZIP packaging with Docker build
- ✅ No ECR permissions needed
- ✅ No Terraform changes required
- ✅ GitHub Actions workflow updated (`.github/workflows/deploy.yml`)

**Phase 2** (PR #59): ECR infrastructure setup
1. Create ECR module: `infrastructure/terraform/modules/ecr/`
2. Create CI/CD IAM role: `infrastructure/terraform/modules/iam/cicd.tf`
3. Update Dashboard Lambda IAM: Add ECR pull permissions
4. Deploy to preprod: `terraform apply -var="environment=preprod"`
5. Verify: ECR repository created, scanning enabled, lifecycle policy active

**Phase 3** (PR #60): Container image deployment
1. Create Dockerfile: `infrastructure/docker/dashboard/Dockerfile`
2. Update GitHub Actions: Add container build + push steps
3. Update Lambda Terraform: Change `package_type = "Zip"` → `"Image"`
4. Deploy to preprod: Test container-based Lambda
5. Run E2E tests: Verify HTTP 502 errors resolved
6. Monitor for 1 week: Check cold start times, CloudWatch logs, GuardDuty alerts

**Phase 4** (PR #61): Production rollout
1. Deploy to production: `terraform apply -var="environment=prod"`
2. Run production canary: Verify dashboard responds
3. Monitor for 24 hours: Watch for regressions
4. Update documentation: Reflect container-based architecture
5. Remove ZIP packaging code: Clean up legacy build scripts

---

## Rollback Plan

If container migration causes issues:

**Immediate rollback** (< 5 minutes):
```bash
# Revert Lambda to previous ZIP package
terraform apply -var="environment=preprod" -var="lambda_package_type=Zip"
```

**Emergency hotfix** (< 15 minutes):
1. Checkout previous commit: `git checkout <last-working-commit>`
2. Rebuild ZIP package: Run GitHub Actions workflow
3. Deploy to affected environment: `terraform apply`

**Permanent revert** (if fundamental issues):
1. Revert PR #59, #60, #61 via GitHub
2. Remove ECR repositories: `terraform destroy -target=module.ecr`
3. Update documentation: Note reasons for revert
4. Create incident report: Document root cause, impact, lessons learned

---

## Cost Impact

**Current (ZIP)**: Free (S3 storage: < $0.01/month)

**Future (Container)**:
- ECR storage: $0.10/GB/month (~0.2GB = **$0.02/month**)
- ECR data transfer: Free (within us-east-1)
- Image scanning: Free (Amazon Inspector integration)
- **Total**: < **$0.05/month** additional cost

---

## Compliance Notes

### NIST 800-190 (Container Security)
- ✅ Section 4.1: Image provenance (AWS-signed base image)
- ✅ Section 4.2: Registry security (ECR with KMS encryption)
- ✅ Section 4.3: Runtime security (Lambda Firecracker isolation)
- ✅ Section 4.4: Orchestration (Lambda service handles lifecycle)

### CIS Docker Benchmark
- ✅ 4.1: Image scanning enabled
- ✅ 4.2: Trusted registries only (ECR + public.ecr.aws)
- ✅ 4.5: Content trust (AWS Signer)
- ✅ 5.1: Least privilege (separate CI/CD and runtime roles)

---

## References

- **Security Analysis**: `CONTAINER_MIGRATION_SECURITY_ANALYSIS.md`
- **Root Cause**: `PREPROD_HTTP_502_ROOT_CAUSE.md`
- **Permissions Audit**: `ZERO_TRUST_PERMISSIONS_AUDIT.md`
- **AWS ECR Docs**: https://docs.aws.amazon.com/AmazonECR/latest/userguide/security_iam_service-with-iam.html
- **Lambda Container Docs**: https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
