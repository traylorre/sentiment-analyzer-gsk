# CI User IAM Policies for GitHub Actions Deploy Pipeline
# ======================================================
#
# This file defines and ATTACHES IAM policies to CI deployer users:
# - sentiment-analyzer-dev-deployer (dev environment)
# - sentiment-analyzer-preprod-deployer (preprod environment)
# - sentiment-analyzer-prod-deployer (prod environment)
#
# POLICY SIZE LIMIT: AWS limits managed policies to 6,144 characters.
# To stay under this limit, permissions are split into 3 policies:
# - ci_deploy_core: Lambda, DynamoDB, SNS, SQS, EventBridge, Secrets
# - ci_deploy_monitoring: CloudWatch, Cognito, IAM, FIS
# - ci_deploy_storage: S3, CloudFront, ACM, Backup, Budgets, RUM
#
# BOOTSTRAP REQUIREMENT:
# ----------------------
# For FIRST-TIME SETUP, an admin must manually apply these policies:
#   cd infrastructure/terraform
#   terraform init
#   terraform apply -var="environment=dev" -var="aws_region=us-east-1" \
#     -target=aws_iam_policy.ci_deploy_core \
#     -target=aws_iam_policy.ci_deploy_monitoring \
#     -target=aws_iam_policy.ci_deploy_storage \
#     -target=aws_iam_user_policy_attachment.ci_deploy_core_dev \
#     -target=aws_iam_user_policy_attachment.ci_deploy_core_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_core_prod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_monitoring_dev \
#     -target=aws_iam_user_policy_attachment.ci_deploy_monitoring_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_monitoring_prod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_storage_dev \
#     -target=aws_iam_user_policy_attachment.ci_deploy_storage_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_storage_prod

# ==================================================================
# POLICY 1: Core Infrastructure (Lambda, DynamoDB, SNS, SQS, Events, Secrets)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_core" {
  # Lambda Function Management
  statement {
    sid    = "Lambda"
    effect = "Allow"
    actions = [
      "lambda:CreateFunction",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:DeleteFunction",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:ListFunctions",
      "lambda:ListVersionsByFunction",
      "lambda:PublishVersion",
      "lambda:CreateAlias",
      "lambda:UpdateAlias",
      "lambda:DeleteAlias",
      "lambda:GetAlias",
      "lambda:AddPermission",
      "lambda:RemovePermission",
      "lambda:GetPolicy",
      "lambda:TagResource",
      "lambda:UntagResource",
      "lambda:ListTags",
      "lambda:CreateFunctionUrlConfig",
      "lambda:UpdateFunctionUrlConfig",
      "lambda:DeleteFunctionUrlConfig",
      "lambda:GetFunctionUrlConfig",
      "lambda:CreateEventSourceMapping",
      "lambda:UpdateEventSourceMapping",
      "lambda:DeleteEventSourceMapping",
      "lambda:GetEventSourceMapping",
      "lambda:ListEventSourceMappings",
      "lambda:PublishLayerVersion",
      "lambda:DeleteLayerVersion",
      "lambda:GetLayerVersion",
      "lambda:ListLayerVersions",
      "lambda:ListLayers"
    ]
    resources = ["*"]
  }

  # DynamoDB Table Management
  statement {
    sid    = "DynamoDB"
    effect = "Allow"
    actions = [
      "dynamodb:CreateTable",
      "dynamodb:UpdateTable",
      "dynamodb:DeleteTable",
      "dynamodb:DescribeTable",
      "dynamodb:ListTables",
      "dynamodb:DescribeTimeToLive",
      "dynamodb:UpdateTimeToLive",
      "dynamodb:DescribeContinuousBackups",
      "dynamodb:UpdateContinuousBackups",
      "dynamodb:TagResource",
      "dynamodb:UntagResource",
      "dynamodb:ListTagsOfResource"
    ]
    resources = ["*"]
  }

  # SNS Topic Management
  statement {
    sid    = "SNS"
    effect = "Allow"
    actions = [
      "sns:CreateTopic",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:SetTopicAttributes",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:ListSubscriptionsByTopic",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:ListTagsForResource"
    ]
    resources = ["*"]
  }

  # SQS Queue Management
  statement {
    sid    = "SQS"
    effect = "Allow"
    actions = [
      "sqs:CreateQueue",
      "sqs:DeleteQueue",
      "sqs:GetQueueAttributes",
      "sqs:SetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ListQueues",
      "sqs:TagQueue",
      "sqs:UntagQueue",
      "sqs:ListQueueTags"
    ]
    resources = ["*"]
  }

  # EventBridge Rules Management
  statement {
    sid    = "EventBridge"
    effect = "Allow"
    actions = [
      "events:PutRule",
      "events:DeleteRule",
      "events:DescribeRule",
      "events:EnableRule",
      "events:DisableRule",
      "events:PutTargets",
      "events:RemoveTargets",
      "events:ListTargetsByRule",
      "events:TagResource",
      "events:UntagResource",
      "events:ListTagsForResource"
    ]
    resources = ["*"]
  }

  # Secrets Manager
  statement {
    sid    = "SecretsManager"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:UpdateSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource"
    ]
    resources = ["*"]
  }

  # General Read Permissions
  statement {
    sid    = "GeneralRead"
    effect = "Allow"
    actions = [
      "sts:GetCallerIdentity",
      "ec2:DescribeAvailabilityZones",
      "ec2:DescribeVpcs",
      "ec2:DescribeSubnets",
      "ec2:DescribeSecurityGroups"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# POLICY 2: Monitoring & Security (CloudWatch, Cognito, IAM, FIS)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_monitoring" {
  # CloudWatch Logs
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DescribeLogGroups",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup",
      "logs:UntagLogGroup",
      "logs:ListTagsLogGroup",
      "logs:PutMetricFilter",
      "logs:DeleteMetricFilter",
      "logs:DescribeMetricFilters"
    ]
    resources = ["*"]
  }

  # CloudWatch Alarms and Dashboards
  statement {
    sid    = "CloudWatch"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:ListTagsForResource",
      "cloudwatch:PutDashboard",
      "cloudwatch:DeleteDashboards",
      "cloudwatch:GetDashboard",
      "cloudwatch:ListDashboards",
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:DescribeAlarmHistory"
    ]
    resources = ["*"]
  }

  # Cognito User Pools
  statement {
    sid    = "CognitoIDP"
    effect = "Allow"
    actions = [
      "cognito-idp:CreateUserPool",
      "cognito-idp:UpdateUserPool",
      "cognito-idp:DeleteUserPool",
      "cognito-idp:DescribeUserPool",
      "cognito-idp:ListUserPools",
      "cognito-idp:GetUserPoolMfaConfig",
      "cognito-idp:SetUserPoolMfaConfig",
      "cognito-idp:CreateUserPoolClient",
      "cognito-idp:UpdateUserPoolClient",
      "cognito-idp:DeleteUserPoolClient",
      "cognito-idp:DescribeUserPoolClient",
      "cognito-idp:ListUserPoolClients",
      "cognito-idp:CreateUserPoolDomain",
      "cognito-idp:UpdateUserPoolDomain",
      "cognito-idp:DeleteUserPoolDomain",
      "cognito-idp:DescribeUserPoolDomain",
      "cognito-idp:CreateResourceServer",
      "cognito-idp:UpdateResourceServer",
      "cognito-idp:DeleteResourceServer",
      "cognito-idp:DescribeResourceServer",
      "cognito-idp:ListResourceServers",
      "cognito-idp:CreateIdentityProvider",
      "cognito-idp:UpdateIdentityProvider",
      "cognito-idp:DeleteIdentityProvider",
      "cognito-idp:DescribeIdentityProvider",
      "cognito-idp:ListIdentityProviders",
      "cognito-idp:TagResource",
      "cognito-idp:UntagResource",
      "cognito-idp:ListTagsForResource"
    ]
    resources = ["*"]
  }

  # Cognito Identity Pools
  statement {
    sid    = "CognitoIdentity"
    effect = "Allow"
    actions = [
      "cognito-identity:CreateIdentityPool",
      "cognito-identity:UpdateIdentityPool",
      "cognito-identity:DeleteIdentityPool",
      "cognito-identity:DescribeIdentityPool",
      "cognito-identity:ListIdentityPools",
      "cognito-identity:GetIdentityPoolRoles",
      "cognito-identity:SetIdentityPoolRoles",
      "cognito-identity:TagResource",
      "cognito-identity:UntagResource",
      "cognito-identity:ListTagsForResource"
    ]
    resources = ["*"]
  }

  # IAM Role and Policy Management (scoped)
  statement {
    sid    = "IAMRoles"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:UpdateRole",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:TagRole",
      "iam:UntagRole"
    ]
    resources = [
      "arn:aws:iam::*:role/*-lambda-role",
      "arn:aws:iam::*:role/*-fis-execution-role",
      "arn:aws:iam::*:role/*-backup-role",
      "arn:aws:iam::*:role/*-cognito-*"
    ]
  }

  # IAM Policy Management
  statement {
    sid    = "IAMPolicies"
    effect = "Allow"
    actions = [
      "iam:CreatePolicy",
      "iam:DeletePolicy",
      "iam:GetPolicy",
      "iam:GetPolicyVersion",
      "iam:ListPolicyVersions",
      "iam:CreatePolicyVersion",
      "iam:DeletePolicyVersion",
      "iam:SetDefaultPolicyVersion"
    ]
    resources = ["*"]
  }

  # IAM PassRole for services
  statement {
    sid    = "IAMPassRole"
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::*:role/*-lambda-role",
      "arn:aws:iam::*:role/*-fis-execution-role",
      "arn:aws:iam::*:role/*-backup-role",
      "arn:aws:iam::*:role/*-cognito-*"
    ]
  }

  # IAM User Policy Attachments (for CI deployer users managing their own policies)
  statement {
    sid    = "IAMUserPolicyAttachments"
    effect = "Allow"
    actions = [
      "iam:ListAttachedUserPolicies",
      "iam:AttachUserPolicy",
      "iam:DetachUserPolicy"
    ]
    resources = [
      "arn:aws:iam::*:user/sentiment-analyzer-*-deployer"
    ]
  }

  # FIS (Fault Injection Simulator)
  statement {
    sid    = "FIS"
    effect = "Allow"
    actions = [
      "fis:CreateExperimentTemplate",
      "fis:GetExperimentTemplate",
      "fis:UpdateExperimentTemplate",
      "fis:DeleteExperimentTemplate",
      "fis:ListExperimentTemplates",
      "fis:StartExperiment",
      "fis:StopExperiment",
      "fis:GetExperiment",
      "fis:ListExperiments",
      "fis:GetAction",
      "fis:ListActions",
      "fis:GetTargetResourceType",
      "fis:ListTargetResourceTypes",
      "fis:TagResource",
      "fis:UntagResource",
      "fis:ListTagsForResource"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# POLICY 3: Storage & CDN (S3, CloudFront, ACM, Backup, Budgets, RUM)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_storage" {
  # S3 Bucket Management
  statement {
    sid    = "S3Buckets"
    effect = "Allow"
    actions = [
      "s3:CreateBucket",
      "s3:DeleteBucket",
      "s3:GetBucketLocation",
      "s3:GetBucketVersioning",
      "s3:PutBucketVersioning",
      "s3:GetBucketPublicAccessBlock",
      "s3:PutBucketPublicAccessBlock",
      "s3:GetBucketTagging",
      "s3:PutBucketTagging",
      "s3:GetBucketPolicy",
      "s3:PutBucketPolicy",
      "s3:DeleteBucketPolicy",
      "s3:GetEncryptionConfiguration",
      "s3:PutEncryptionConfiguration",
      "s3:GetBucketCORS",
      "s3:PutBucketCORS",
      "s3:DeleteBucketCORS",
      "s3:GetBucketWebsite",
      "s3:PutBucketWebsite",
      "s3:DeleteBucketWebsite",
      "s3:GetLifecycleConfiguration",
      "s3:PutLifecycleConfiguration",
      "s3:GetBucketAcl",
      "s3:PutBucketAcl"
    ]
    resources = [
      "arn:aws:s3:::sentiment-analyzer-*",
      "arn:aws:s3:::*-sentiment-*"
    ]
  }

  # S3 Object Management
  statement {
    sid    = "S3Objects"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetObjectAcl",
      "s3:PutObjectAcl"
    ]
    resources = [
      "arn:aws:s3:::sentiment-analyzer-*",
      "arn:aws:s3:::sentiment-analyzer-*/*",
      "arn:aws:s3:::*-sentiment-*",
      "arn:aws:s3:::*-sentiment-*/*"
    ]
  }

  # Terraform State S3 Access
  statement {
    sid    = "TerraformState"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]
    resources = [
      "arn:aws:s3:::sentiment-analyzer-tfstate-*",
      "arn:aws:s3:::sentiment-analyzer-tfstate-*/*",
      "arn:aws:s3:::sentiment-analyzer-terraform-*",
      "arn:aws:s3:::sentiment-analyzer-terraform-*/*"
    ]
  }

  # CloudFront Distribution
  statement {
    sid    = "CloudFront"
    effect = "Allow"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:UpdateDistribution",
      "cloudfront:DeleteDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:ListDistributions",
      "cloudfront:TagResource",
      "cloudfront:UntagResource",
      "cloudfront:ListTagsForResource",
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:GetOriginAccessControlConfig",
      "cloudfront:ListOriginAccessControls",
      "cloudfront:CreateCachePolicy",
      "cloudfront:UpdateCachePolicy",
      "cloudfront:DeleteCachePolicy",
      "cloudfront:GetCachePolicy",
      "cloudfront:ListCachePolicies",
      "cloudfront:CreateResponseHeadersPolicy",
      "cloudfront:UpdateResponseHeadersPolicy",
      "cloudfront:DeleteResponseHeadersPolicy",
      "cloudfront:GetResponseHeadersPolicy",
      "cloudfront:ListResponseHeadersPolicies"
    ]
    resources = ["*"]
  }

  # ACM Certificates (read-only)
  statement {
    sid    = "ACM"
    effect = "Allow"
    actions = [
      "acm:DescribeCertificate",
      "acm:ListCertificates",
      "acm:ListTagsForCertificate",
      "acm:GetCertificate"
    ]
    resources = ["*"]
  }

  # AWS Backup
  statement {
    sid    = "Backup"
    effect = "Allow"
    actions = [
      "backup:CreateBackupVault",
      "backup:DeleteBackupVault",
      "backup:DescribeBackupVault",
      "backup:ListBackupVaults",
      "backup:CreateBackupPlan",
      "backup:UpdateBackupPlan",
      "backup:DeleteBackupPlan",
      "backup:GetBackupPlan",
      "backup:ListBackupPlans",
      "backup:CreateBackupSelection",
      "backup:DeleteBackupSelection",
      "backup:GetBackupSelection",
      "backup:ListBackupSelections",
      "backup:TagResource",
      "backup:UntagResource",
      "backup:ListTags"
    ]
    resources = ["*"]
  }

  # AWS Budgets
  statement {
    sid    = "Budgets"
    effect = "Allow"
    actions = [
      "budgets:CreateBudget",
      "budgets:ModifyBudget",
      "budgets:DeleteBudget",
      "budgets:ViewBudget",
      "budgets:DescribeBudgets",
      "budgets:DescribeBudgetActionsForBudget"
    ]
    resources = ["*"]
  }

  # CloudWatch RUM
  statement {
    sid    = "RUM"
    effect = "Allow"
    actions = [
      "rum:CreateAppMonitor",
      "rum:UpdateAppMonitor",
      "rum:DeleteAppMonitor",
      "rum:GetAppMonitor",
      "rum:ListAppMonitors",
      "rum:TagResource",
      "rum:UntagResource",
      "rum:ListTagsForResource"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# IAM Policy Resources
# ==================================================================

resource "aws_iam_policy" "ci_deploy_core" {
  name        = "CIDeployCore"
  description = "CI/CD core infrastructure: Lambda, DynamoDB, SNS, SQS, EventBridge, Secrets"
  policy      = data.aws_iam_policy_document.ci_deploy_core.json

  tags = {
    Purpose   = "ci-deployment"
    ManagedBy = "Terraform"
    Category  = "core"
  }
}

resource "aws_iam_policy" "ci_deploy_monitoring" {
  name        = "CIDeployMonitoring"
  description = "CI/CD monitoring and security: CloudWatch, Cognito, IAM, FIS"
  policy      = data.aws_iam_policy_document.ci_deploy_monitoring.json

  tags = {
    Purpose   = "ci-deployment"
    ManagedBy = "Terraform"
    Category  = "monitoring"
  }
}

resource "aws_iam_policy" "ci_deploy_storage" {
  name        = "CIDeployStorage"
  description = "CI/CD storage and CDN: S3, CloudFront, ACM, Backup, Budgets, RUM"
  policy      = data.aws_iam_policy_document.ci_deploy_storage.json

  tags = {
    Purpose   = "ci-deployment"
    ManagedBy = "Terraform"
    Category  = "storage"
  }
}

# ==================================================================
# Policy Attachments - Dev Deployer
# ==================================================================

resource "aws_iam_user_policy_attachment" "ci_deploy_core_dev" {
  user       = "sentiment-analyzer-dev-deployer"
  policy_arn = aws_iam_policy.ci_deploy_core.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_monitoring_dev" {
  user       = "sentiment-analyzer-dev-deployer"
  policy_arn = aws_iam_policy.ci_deploy_monitoring.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_storage_dev" {
  user       = "sentiment-analyzer-dev-deployer"
  policy_arn = aws_iam_policy.ci_deploy_storage.arn
}

# ==================================================================
# Policy Attachments - Preprod Deployer
# ==================================================================

resource "aws_iam_user_policy_attachment" "ci_deploy_core_preprod" {
  user       = "sentiment-analyzer-preprod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_core.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_monitoring_preprod" {
  user       = "sentiment-analyzer-preprod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_monitoring.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_storage_preprod" {
  user       = "sentiment-analyzer-preprod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_storage.arn
}

# ==================================================================
# Policy Attachments - Prod Deployer
# ==================================================================

resource "aws_iam_user_policy_attachment" "ci_deploy_core_prod" {
  user       = "sentiment-analyzer-prod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_core.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_monitoring_prod" {
  user       = "sentiment-analyzer-prod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_monitoring.arn
}

resource "aws_iam_user_policy_attachment" "ci_deploy_storage_prod" {
  user       = "sentiment-analyzer-prod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_storage.arn
}

# ==================================================================
# Outputs
# ==================================================================

output "ci_policy_arns" {
  description = "ARNs of the CI deployment policies"
  value = {
    core       = aws_iam_policy.ci_deploy_core.arn
    monitoring = aws_iam_policy.ci_deploy_monitoring.arn
    storage    = aws_iam_policy.ci_deploy_storage.arn
  }
}

output "ci_policy_attached_users" {
  description = "List of IAM users with CI deployment policies attached"
  value = [
    "sentiment-analyzer-dev-deployer",
    "sentiment-analyzer-preprod-deployer",
    "sentiment-analyzer-prod-deployer"
  ]
}
