# CI User IAM Policies for GitHub Actions Deploy Pipeline
# ======================================================
#
# This file defines and ATTACHES IAM policies to CI deployer users:
# - sentiment-analyzer-preprod-deployer (preprod environment) - NOTE: legacy user name
# - sentiment-analyzer-prod-deployer (prod environment) - NOTE: legacy user name
#
# NAMING CONVENTION: All resource ARN patterns use {env}-sentiment-* pattern
# (e.g., preprod-sentiment-dashboard, prod-sentiment-ingestion)
#
# POLICY SIZE LIMIT: AWS limits managed policies to 6,144 characters.
# To stay under this limit, permissions are split into 4 policies:
# - ci_deploy_core: Lambda, DynamoDB, SNS, SQS, EventBridge, Secrets, ECR
# - ci_deploy_monitoring: CloudWatch, Cognito
# - ci_deploy_iam: IAM, FIS, X-Ray
# - ci_deploy_storage: S3, CloudFront, ACM, Backup, Budgets, RUM, KMS
#
# BOOTSTRAP REQUIREMENT:
# ----------------------
# For FIRST-TIME SETUP, an admin must manually apply these policies:
#   cd infrastructure/terraform
#   terraform init
#   terraform apply -var="environment=preprod" -var="aws_region=us-east-1" \
#     -target=aws_iam_policy.ci_deploy_core \
#     -target=aws_iam_policy.ci_deploy_monitoring \
#     -target=aws_iam_policy.ci_deploy_storage \
#     -target=aws_iam_policy.ci_deploy_iam \
#     -target=aws_iam_user_policy_attachment.ci_deploy_core_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_core_prod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_monitoring_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_monitoring_prod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_storage_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_storage_prod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_iam_preprod \
#     -target=aws_iam_user_policy_attachment.ci_deploy_iam_prod

# ==================================================================
# POLICY 1: Core Infrastructure (Lambda, DynamoDB, SNS, SQS, Events, Secrets)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_core" {
  # Lambda Function Management
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-001)
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
      "lambda:ListLayers",
      "lambda:GetFunctionCodeSigningConfig",
      "lambda:ListFunctionUrlConfigs",
      # Lambda concurrency management (required for reserved_concurrency changes)
      "lambda:PutFunctionConcurrency",
      "lambda:DeleteFunctionConcurrency",
      "lambda:GetFunctionConcurrency"
    ]
    resources = [
      # Pattern: {env}-sentiment-* (preprod-sentiment-ingestion, prod-sentiment-dashboard, etc.)
      "arn:aws:lambda:*:*:function:*-sentiment-*",
      "arn:aws:lambda:*:*:function:*-sentiment-*:*"
    ]
  }

  # Lambda Layers (scoped to *-sentiment-* layer names)
  statement {
    sid    = "LambdaLayers"
    effect = "Allow"
    actions = [
      "lambda:PublishLayerVersion",
      "lambda:DeleteLayerVersion",
      "lambda:GetLayerVersion",
      "lambda:ListLayerVersions",
      "lambda:ListLayers"
    ]
    resources = [
      "arn:aws:lambda:*:*:layer:*-sentiment-*",
      "arn:aws:lambda:*:*:layer:*-sentiment-*:*"
    ]
  }

  # DynamoDB Table Management
  # SECURITY: Scoped to {env}-sentiment-* naming pattern (FR-002)
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
      "dynamodb:ListTagsOfResource",
      # Data operations needed for integration tests
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:DeleteItem"
    ]
    resources = [
      # Pattern: {env}-sentiment-* (preprod-sentiment-items, prod-sentiment-users, etc.)
      "arn:aws:dynamodb:*:*:table/*-sentiment-*",
      "arn:aws:dynamodb:*:*:table/*-sentiment-*/stream/*",
      "arn:aws:dynamodb:*:*:table/*-sentiment-*/index/*",
      # Pattern: {env}-chaos-* (preprod-chaos-experiments, prod-chaos-experiments)
      "arn:aws:dynamodb:*:*:table/*-chaos-*",
      "arn:aws:dynamodb:*:*:table/*-chaos-*/stream/*",
      "arn:aws:dynamodb:*:*:table/*-chaos-*/index/*"
    ]
  }

  # SNS Topic Management
  # SECURITY: Scoped to {env}-sentiment-* naming pattern (FR-003)
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
      "sns:GetSubscriptionAttributes",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:ListTagsForResource"
    ]
    resources = [
      # Pattern: {env}-sentiment-* (preprod-sentiment-alarms, prod-sentiment-analysis-requests, etc.)
      "arn:aws:sns:*:*:*-sentiment-*"
    ]
  }

  # SQS Queue Management
  # SECURITY: Scoped to {env}-sentiment-* naming pattern (FR-004)
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
    resources = [
      # Pattern: {env}-sentiment-* (preprod-sentiment-analysis-dlq, etc.)
      "arn:aws:sqs:*:*:*-sentiment-*"
    ]
  }

  # EventBridge Rules Management
  # SECURITY: Scoped to {env}-sentiment-* naming pattern (FR-005)
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
    resources = [
      "arn:aws:events:*:*:rule/*-sentiment-*"
    ]
  }

  # API Gateway Management
  statement {
    sid    = "APIGateway"
    effect = "Allow"
    actions = [
      "apigateway:GET",
      "apigateway:POST",
      "apigateway:PUT",
      "apigateway:DELETE",
      "apigateway:PATCH",
      "apigateway:TagResource",
      "apigateway:UntagResource"
    ]
    resources = [
      "arn:aws:apigateway:*::/restapis",
      "arn:aws:apigateway:*::/restapis/*",
      "arn:aws:apigateway:*::/usageplans",
      "arn:aws:apigateway:*::/usageplans/*",
      "arn:aws:apigateway:*::/tags/*"
    ]
  }

  # Secrets Manager
  # SECURITY: Scoped to {env}/sentiment-analyzer/* naming pattern (FR-006)
  statement {
    sid    = "SecretsManager"
    effect = "Allow"
    actions = [
      "secretsmanager:CreateSecret",
      "secretsmanager:DeleteSecret",
      "secretsmanager:DescribeSecret",
      "secretsmanager:GetResourcePolicy",
      "secretsmanager:UpdateSecret",
      "secretsmanager:PutSecretValue",
      "secretsmanager:TagResource",
      "secretsmanager:UntagResource"
    ]
    resources = [
      # Pattern: {env}/sentiment-analyzer/* (preprod/sentiment-analyzer/tiingo, etc.)
      "arn:aws:secretsmanager:*:*:secret:*/sentiment-analyzer/*"
    ]
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

  # ECR Repository Management (for Docker-based Lambdas like SSE streaming, Analysis)
  # SECURITY: Scoped to {env}-sentiment-*, {env}-sse-streaming-*, {env}-analysis-* patterns (FR-012)
  statement {
    sid    = "ECR"
    effect = "Allow"
    actions = [
      "ecr:CreateRepository",
      "ecr:DeleteRepository",
      "ecr:DescribeRepositories",
      "ecr:ListTagsForResource",
      "ecr:TagResource",
      "ecr:UntagResource",
      "ecr:SetRepositoryPolicy",
      "ecr:GetRepositoryPolicy",
      "ecr:DeleteRepositoryPolicy",
      "ecr:PutLifecyclePolicy",
      "ecr:GetLifecyclePolicy",
      "ecr:DeleteLifecyclePolicy",
      "ecr:GetLifecyclePolicyPreview",
      "ecr:PutImageScanningConfiguration",
      "ecr:PutImageTagMutability"
    ]
    resources = [
      "arn:aws:ecr:*:*:repository/*-sentiment-*",
      "arn:aws:ecr:*:*:repository/*-sse-streaming-*",
      "arn:aws:ecr:*:*:repository/*-analysis-*"
    ]
  }

  # ECR Image Operations
  statement {
    sid    = "ECRImages"
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:BatchDeleteImage",
      "ecr:DescribeImages",
      "ecr:ListImages"
    ]
    resources = [
      "arn:aws:ecr:*:*:repository/*-sentiment-*",
      "arn:aws:ecr:*:*:repository/*-sse-streaming-*",
      "arn:aws:ecr:*:*:repository/*-analysis-*"
    ]
  }

  # ECR Authorization Token (required for docker login)
  statement {
    sid    = "ECRAuth"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# POLICY 2: Monitoring & Security (CloudWatch, Cognito, IAM, FIS)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_monitoring" {
  # CloudWatch Logs
  # SECURITY: Scoped to {env}-sentiment-* log groups (FR-007)
  statement {
    sid    = "CloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DescribeLogGroups",
      "logs:DescribeLogStreams",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup",
      "logs:UntagLogGroup",
      "logs:ListTagsLogGroup",
      "logs:ListTagsForResource",
      "logs:PutMetricFilter",
      "logs:DeleteMetricFilter",
      "logs:DescribeMetricFilters",
      # CloudWatch Logs Insights queries (for E2E observability tests)
      "logs:StartQuery",
      "logs:GetQueryResults",
      "logs:StopQuery"
    ]
    resources = [
      # Pattern: {env}-sentiment-* (preprod-sentiment-dashboard, prod-sentiment-ingestion, etc.)
      "arn:aws:logs:*:*:log-group:/aws/lambda/*-sentiment-*",
      "arn:aws:logs:*:*:log-group:/aws/lambda/*-sentiment-*:*",
      "arn:aws:logs:*:*:log-group:/aws/apigateway/*-sentiment-*",
      "arn:aws:logs:*:*:log-group:/aws/apigateway/*-sentiment-*:*",
      # FIS chaos experiment logs
      "arn:aws:logs:*:*:log-group:/aws/fis/*-chaos-*",
      "arn:aws:logs:*:*:log-group:/aws/fis/*-chaos-*:*"
    ]
  }

  # CloudWatch Alarms and Dashboards
  # SECURITY: Scoped to {env}-sentiment-* alarms (FR-008)
  # Note: CloudWatch alarms don't support resource-level ARNs for all actions
  # TEMPORARY: Also allow preprod-* and prod-* for legacy alarm migration
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
    resources = [
      "arn:aws:cloudwatch:*:*:alarm:*-sentiment-*",
      "arn:aws:cloudwatch::*:dashboard/*-sentiment-*",
      "arn:aws:cloudwatch:*:*:alarm:preprod-*",
      "arn:aws:cloudwatch:*:*:alarm:prod-*"
    ]
  }

  # CloudWatch read-only actions that require wildcard resource
  statement {
    sid    = "CloudWatchReadOnly"
    effect = "Allow"
    actions = [
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:DescribeAlarms",
      # GetMetricData for E2E observability tests (wildcard required by AWS)
      "cloudwatch:GetMetricData"
    ]
    resources = ["*"]
  }

  # CloudWatch PutMetricData - required for Lambda custom metrics emission
  # Note: PutMetricData doesn't support resource-level ARNs (AWS limitation)
  # Namespace isolation via application code (SentimentAnalyzer namespace)
  statement {
    sid    = "CloudWatchMetricsWrite"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData"
    ]
    resources = ["*"]
  }

  # CloudWatch Logs - DescribeLogGroups/DescribeMetricFilters require wildcard for resource enumeration
  # This is needed for Terraform to refresh state on log groups and metric filters
  statement {
    sid    = "CloudWatchLogsDescribe"
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups",
      "logs:DescribeMetricFilters"
    ]
    resources = ["*"]
  }

  # Cognito User Pools
  # SECURITY: Scoped to *-sentiment-* user pools via tag (FR-009)
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
    resources = [
      "arn:aws:cognito-idp:*:*:userpool/*"
    ]
    condition {
      test     = "StringLike"
      variable = "cognito-idp:ResourceTag/Name"
      values   = ["*-sentiment-*"]
    }
  }

  # Cognito User Pools - List/Describe operations (require wildcard)
  # Note: These require unconditional access for Terraform state refresh
  statement {
    sid    = "CognitoIDPList"
    effect = "Allow"
    actions = [
      "cognito-idp:ListUserPools",
      "cognito-idp:ListUserPoolClients",
      "cognito-idp:ListResourceServers",
      "cognito-idp:ListIdentityProviders",
      "cognito-idp:DescribeUserPool",
      "cognito-idp:DescribeUserPoolClient",
      "cognito-idp:DescribeUserPoolDomain",
      "cognito-idp:DescribeResourceServer",
      "cognito-idp:DescribeIdentityProvider",
      "cognito-idp:GetUserPoolMfaConfig"
    ]
    resources = ["*"]
  }

  # Cognito Identity Pools
  # SECURITY: Scoped to *-sentiment-* identity pools via tag (FR-009)
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
    resources = [
      "arn:aws:cognito-identity:*:*:identitypool/*"
    ]
    condition {
      test     = "StringLike"
      variable = "cognito-identity:ResourceTag/Name"
      values   = ["*-sentiment-*"]
    }
  }

  # Cognito Identity Pools - List/Get operations (require wildcard)
  # Note: These require unconditional access for Terraform state refresh
  statement {
    sid    = "CognitoIdentityList"
    effect = "Allow"
    actions = [
      "cognito-identity:ListIdentityPools",
      "cognito-identity:DescribeIdentityPool",
      "cognito-identity:GetIdentityPoolRoles",
      "cognito-identity:ListTagsForResource"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# POLICY 2b: IAM, FIS, X-Ray (split from monitoring due to size limit)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_iam" {
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
      "arn:aws:iam::*:role/*-cognito-*",
      "arn:aws:iam::*:role/*-rum-*"
    ]
  }

  # Service-Linked Roles (needed for services like RUM)
  statement {
    sid    = "ServiceLinkedRoles"
    effect = "Allow"
    actions = [
      "iam:CreateServiceLinkedRole"
    ]
    resources = [
      "arn:aws:iam::*:role/aws-service-role/rum.amazonaws.com/*"
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:AWSServiceName"
      values   = ["rum.amazonaws.com"]
    }
  }

  # IAM Policy Management
  # SECURITY: Scoped to *-sentiment-* and CIDeploy* policies (FR-010)
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
    resources = [
      "arn:aws:iam::*:policy/*-sentiment-*",
      "arn:aws:iam::*:policy/CIDeploy*"
    ]
  }

  # IAM List Policies - requires wildcard for ListPolicies action
  statement {
    sid    = "IAMPoliciesList"
    effect = "Allow"
    actions = [
      "iam:ListPolicies"
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
      "arn:aws:iam::*:role/*-cognito-*",
      "arn:aws:iam::*:role/*-rum-*"
    ]
  }

  # IAM User Policy Attachments (for CI deployer users managing their own policies)
  # Pattern: sentiment-analyzer-*-deployer (preprod, prod)
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
  # SECURITY: Scoped to *-sentiment-* templates via tag condition (FR-011)
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
    resources = [
      "arn:aws:fis:*:*:experiment-template/*",
      "arn:aws:fis:*:*:experiment/*"
    ]
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/Name"
      values   = ["*-sentiment-*"]
    }
  }

  # FIS List/Describe operations - require wildcard
  statement {
    sid    = "FISReadOnly"
    effect = "Allow"
    actions = [
      "fis:GetAction",
      "fis:ListActions",
      "fis:GetTargetResourceType",
      "fis:ListTargetResourceTypes",
      "fis:ListExperimentTemplates",
      "fis:ListExperiments"
    ]
    resources = ["*"]
  }

  # X-Ray Tracing
  # SECURITY: Scoped to *-sentiment-* groups (FR-011)
  statement {
    sid    = "XRay"
    effect = "Allow"
    actions = [
      "xray:CreateGroup",
      "xray:UpdateGroup",
      "xray:DeleteGroup",
      "xray:TagResource",
      "xray:UntagResource",
      "xray:ListTagsForResource"
    ]
    resources = [
      "arn:aws:xray:*:*:group/*-sentiment-*/*"
    ]
  }

  # X-Ray Sampling Rules - scoped
  statement {
    sid    = "XRaySamplingRules"
    effect = "Allow"
    actions = [
      "xray:CreateSamplingRule",
      "xray:UpdateSamplingRule",
      "xray:DeleteSamplingRule"
    ]
    resources = [
      "arn:aws:xray:*:*:sampling-rule/*-sentiment-*"
    ]
  }

  # X-Ray Read operations - require wildcard
  statement {
    sid    = "XRayReadOnly"
    effect = "Allow"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:GetSamplingStatisticSummaries",
      "xray:GetServiceGraph",
      "xray:GetTraceGraph",
      "xray:GetTraceSummaries",
      "xray:GetGroups",
      "xray:GetGroup",
      "xray:GetEncryptionConfig",
      "xray:PutEncryptionConfig",
      "xray:GetInsight",
      "xray:GetInsightEvents",
      "xray:GetInsightImpactGraph",
      "xray:GetInsightSummaries",
      # BatchGetTraces for E2E observability tests to verify tracing
      "xray:BatchGetTraces"
    ]
    resources = ["*"]
  }
}

# ==================================================================
# POLICY 3: Storage & CDN (S3, CloudFront, ACM, Backup, Budgets, RUM)
# ==================================================================

data "aws_iam_policy_document" "ci_deploy_storage" {
  # S3 Bucket Management
  # SECURITY: Scoped to *-sentiment-* naming pattern
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
      "s3:PutBucketAcl",
      "s3:GetAccelerateConfiguration",
      "s3:PutAccelerateConfiguration",
      "s3:GetBucketRequestPayment",
      "s3:GetBucketLogging",
      "s3:GetBucketNotification",
      "s3:GetReplicationConfiguration",
      "s3:GetBucketObjectLockConfiguration",
      "s3:GetBucketOwnershipControls"
    ]
    resources = [
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
      "s3:PutObjectAcl",
      "s3:GetObjectTagging",
      "s3:PutObjectTagging"
    ]
    resources = [
      "arn:aws:s3:::*-sentiment-*",
      "arn:aws:s3:::*-sentiment-*/*"
    ]
  }

  # Terraform State S3 Access
  # Fix: Match actual bucket name pattern (sentiment-analyzer-terraform-state-{account_id})
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
      "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
      "arn:aws:s3:::sentiment-analyzer-terraform-state-*/*"
    ]
  }

  # CloudFront Distribution (tag-protected)
  # SECURITY: Scoped via tag condition to *-sentiment-* (FR-011)
  # Note: Only distributions support ABAC (tag-based conditions) in CloudFront
  statement {
    sid    = "CloudFrontDistribution"
    effect = "Allow"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:UpdateDistribution",
      "cloudfront:DeleteDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:TagResource",
      "cloudfront:UntagResource",
      "cloudfront:ListTagsForResource",
      "cloudfront:CreateInvalidation" # For deploy workflow cache invalidation
    ]
    resources = [
      "arn:aws:cloudfront::*:distribution/*"
    ]
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/Name"
      values   = ["*-sentiment-*"]
    }
  }

  # CloudFront Policies (no tag support)
  # SECURITY: Origin access controls, cache policies, and response headers policies
  # do NOT support ABAC (tag-based conditions) in CloudFront. Access is scoped by
  # naming convention in Terraform code (preprod-sentiment-*, prod-sentiment-*).
  # See: https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncloudfront.html
  statement {
    sid    = "CloudFrontPolicies"
    effect = "Allow"
    actions = [
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:GetOriginAccessControlConfig",
      "cloudfront:CreateCachePolicy",
      "cloudfront:UpdateCachePolicy",
      "cloudfront:DeleteCachePolicy",
      "cloudfront:GetCachePolicy",
      "cloudfront:CreateResponseHeadersPolicy",
      "cloudfront:UpdateResponseHeadersPolicy",
      "cloudfront:DeleteResponseHeadersPolicy",
      "cloudfront:GetResponseHeadersPolicy"
    ]
    resources = [
      "arn:aws:cloudfront::*:origin-access-control/*",
      "arn:aws:cloudfront::*:cache-policy/*",
      "arn:aws:cloudfront::*:response-headers-policy/*"
    ]
  }

  # CloudFront List/Get operations - require wildcard for Terraform state refresh
  statement {
    sid    = "CloudFrontRead"
    effect = "Allow"
    actions = [
      "cloudfront:ListDistributions",
      "cloudfront:ListOriginAccessControls",
      "cloudfront:ListCachePolicies",
      "cloudfront:ListResponseHeadersPolicies",
      "cloudfront:ListTagsForResource",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:GetOriginAccessControlConfig",
      "cloudfront:GetCachePolicy",
      "cloudfront:GetResponseHeadersPolicy"
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
  # SECURITY: Scoped to *-sentiment-* backup resources (FR-011)
  statement {
    sid    = "Backup"
    effect = "Allow"
    actions = [
      "backup:CreateBackupVault",
      "backup:DeleteBackupVault",
      "backup:DescribeBackupVault",
      "backup:CreateBackupPlan",
      "backup:UpdateBackupPlan",
      "backup:DeleteBackupPlan",
      "backup:GetBackupPlan",
      "backup:CreateBackupSelection",
      "backup:DeleteBackupSelection",
      "backup:GetBackupSelection",
      "backup:ListBackupSelections",
      "backup:TagResource",
      "backup:UntagResource",
      "backup:ListTags"
    ]
    resources = [
      "arn:aws:backup:*:*:backup-vault:*-sentiment-*",
      "arn:aws:backup:*:*:backup-plan:*"
    ]
  }

  # AWS Backup List operations - require wildcard
  statement {
    sid    = "BackupList"
    effect = "Allow"
    actions = [
      "backup:ListBackupVaults",
      "backup:ListBackupPlans"
    ]
    resources = ["*"]
  }

  # AWS Budgets
  # SECURITY: Scoped to *-sentiment-* budgets (FR-011)
  # Note: Budget ARNs use account ID, not resource name pattern
  statement {
    sid    = "Budgets"
    effect = "Allow"
    actions = [
      "budgets:CreateBudget",
      "budgets:ModifyBudget",
      "budgets:DeleteBudget",
      "budgets:ViewBudget",
      "budgets:DescribeBudgetActionsForBudget",
      "budgets:TagResource",
      "budgets:UntagResource",
      "budgets:ListTagsForResource"
    ]
    resources = [
      "arn:aws:budgets::*:budget/*-sentiment-*"
    ]
  }

  # Budgets List/View operations - require wildcard
  # ViewBudget and DescribeBudget may need wildcard for Terraform state refresh
  statement {
    sid    = "BudgetsList"
    effect = "Allow"
    actions = [
      "budgets:DescribeBudgets",
      "budgets:ViewBudget",
      "budgets:DescribeBudget"
    ]
    resources = ["*"]
  }

  # CloudWatch RUM
  # SECURITY: Scoped to *-sentiment-* app monitors (FR-011)
  statement {
    sid    = "RUM"
    effect = "Allow"
    actions = [
      "rum:CreateAppMonitor",
      "rum:UpdateAppMonitor",
      "rum:DeleteAppMonitor",
      "rum:GetAppMonitor",
      "rum:TagResource",
      "rum:UntagResource",
      "rum:ListTagsForResource"
    ]
    resources = [
      "arn:aws:rum:*:*:appmonitor/*-sentiment-*"
    ]
  }

  # RUM List operations - require wildcard
  statement {
    sid    = "RUMList"
    effect = "Allow"
    actions = [
      "rum:ListAppMonitors"
    ]
    resources = ["*"]
  }

  # KMS Key Management (for shared encryption key)
  # SECURITY: Scoped to *-sentiment-* keys via alias pattern (FR-013)
  statement {
    sid    = "KMS"
    effect = "Allow"
    actions = [
      "kms:CreateKey",
      "kms:DescribeKey",
      "kms:GetKeyPolicy",
      "kms:GetKeyRotationStatus",
      "kms:ListResourceTags",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:EnableKeyRotation",
      "kms:DisableKeyRotation",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
      "kms:PutKeyPolicy"
    ]
    resources = ["*"]
    condition {
      test     = "StringLike"
      variable = "kms:RequestAlias"
      values   = ["alias/*-sentiment-*"]
    }
  }

  # KMS Key creation (requires different condition)
  statement {
    sid    = "KMSCreate"
    effect = "Allow"
    actions = [
      "kms:CreateKey",
      "kms:TagResource"
    ]
    resources = ["*"]
  }

  # KMS Alias Management
  # Updated to use only *-sentiment-* pattern per 090-security-first-burndown
  # Legacy sentiment-analyzer-* pattern removed
  statement {
    sid    = "KMSAlias"
    effect = "Allow"
    actions = [
      "kms:CreateAlias",
      "kms:DeleteAlias",
      "kms:UpdateAlias"
    ]
    resources = [
      "arn:aws:kms:*:*:alias/*-sentiment-*"
    ]
  }

  # KMS List operations
  statement {
    sid    = "KMSList"
    effect = "Allow"
    actions = [
      "kms:ListKeys",
      "kms:ListAliases"
    ]
    resources = ["*"]
  }

  # NOTE: KMS encryption operations (Encrypt, Decrypt, GenerateDataKey) are granted
  # via KMS key policy in modules/kms/main.tf (CIDeployerEncryption statement).
  # Key policies are authoritative and don't require IAM policy grants.
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
  description = "CI/CD storage and CDN: S3, CloudFront, ACM, Backup, Budgets, RUM, KMS"
  policy      = data.aws_iam_policy_document.ci_deploy_storage.json

  tags = {
    Purpose   = "ci-deployment"
    ManagedBy = "Terraform"
    Category  = "storage"
  }
}

resource "aws_iam_policy" "ci_deploy_iam" {
  name        = "CIDeployIAM"
  description = "CI/CD IAM, FIS, and X-Ray management"
  policy      = data.aws_iam_policy_document.ci_deploy_iam.json

  tags = {
    Purpose   = "ci-deployment"
    ManagedBy = "Terraform"
    Category  = "iam"
  }
}

# ==================================================================
# Policy Attachments - Preprod Deployer
# ==================================================================
# NOTE: User name follows *-sentiment-deployer pattern per 090-security-first-burndown
# Admin must create sentiment-analyzer-preprod-deployer user before applying

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

resource "aws_iam_user_policy_attachment" "ci_deploy_iam_preprod" {
  user       = "sentiment-analyzer-preprod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_iam.arn
}

# ==================================================================
# Policy Attachments - Prod Deployer
# ==================================================================
# NOTE: User name follows sentiment-analyzer-*-deployer pattern
# Admin must create sentiment-analyzer-prod-deployer user before applying

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

resource "aws_iam_user_policy_attachment" "ci_deploy_iam_prod" {
  user       = "sentiment-analyzer-prod-deployer"
  policy_arn = aws_iam_policy.ci_deploy_iam.arn
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
    iam        = aws_iam_policy.ci_deploy_iam.arn
  }
}

output "ci_policy_attached_users" {
  description = "List of IAM users with CI deployment policies attached"
  value = [
    "preprod-sentiment-deployer",
    "prod-sentiment-deployer"
  ]
}
