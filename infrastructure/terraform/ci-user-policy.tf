# CI User IAM Policies for GitHub Actions Deploy Pipeline
# ======================================================
#
# This file defines and ATTACHES IAM policies to CI deployer users:
# - sentiment-analyzer-preprod-deployer (preprod environment)
# - sentiment-analyzer-prod-deployer (prod environment)
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
      "lambda:ListFunctionUrlConfigs"
    ]
    resources = [
      "arn:aws:lambda:*:*:function:sentiment-analyzer-*",
      "arn:aws:lambda:*:*:function:sentiment-analyzer-*:*"
    ]
  }

  # DynamoDB Table Management
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-002)
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
      # Pattern: sentiment-analyzer-* (legacy)
      "arn:aws:dynamodb:*:*:table/sentiment-analyzer-*",
      "arn:aws:dynamodb:*:*:table/sentiment-analyzer-*/stream/*",
      "arn:aws:dynamodb:*:*:table/sentiment-analyzer-*/index/*",
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
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-003)
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
      # Pattern: sentiment-analyzer-* (legacy)
      "arn:aws:sns:*:*:sentiment-analyzer-*",
      # Pattern: {env}-sentiment-* (preprod-sentiment-alarms, prod-sentiment-analysis-requests, etc.)
      "arn:aws:sns:*:*:*-sentiment-*"
    ]
  }

  # SQS Queue Management
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-004)
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
      # Pattern: sentiment-analyzer-* (legacy)
      "arn:aws:sqs:*:*:sentiment-analyzer-*",
      # Pattern: {env}-sentiment-* (preprod-sentiment-analysis-dlq, etc.)
      "arn:aws:sqs:*:*:*-sentiment-*"
    ]
  }

  # EventBridge Rules Management
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-005)
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
      "arn:aws:events:*:*:rule/sentiment-analyzer-*"
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
  # SECURITY: Scoped to sentiment-analyzer-* naming pattern (FR-006)
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
      # Pattern: sentiment-analyzer-* (legacy)
      "arn:aws:secretsmanager:*:*:secret:sentiment-analyzer-*",
      # Pattern: {env}/sentiment-analyzer/* (preprod/sentiment-analyzer/newsapi, etc.)
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

  # ECR Repository Management (for Docker-based Lambdas like SSE streaming)
  # SECURITY: Scoped to sentiment-analyzer-* and preprod/prod naming patterns (FR-012)
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
      "arn:aws:ecr:*:*:repository/sentiment-analyzer-*",
      "arn:aws:ecr:*:*:repository/preprod-*",
      "arn:aws:ecr:*:*:repository/prod-*"
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
      "arn:aws:ecr:*:*:repository/sentiment-analyzer-*",
      "arn:aws:ecr:*:*:repository/preprod-*",
      "arn:aws:ecr:*:*:repository/prod-*"
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
  # SECURITY: Scoped to sentiment-analyzer-* log groups (FR-007)
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
      "logs:DescribeMetricFilters"
    ]
    resources = [
      "arn:aws:logs:*:*:log-group:/aws/lambda/sentiment-analyzer-*",
      "arn:aws:logs:*:*:log-group:/aws/lambda/sentiment-analyzer-*:*",
      "arn:aws:logs:*:*:log-group:/aws/apigateway/sentiment-analyzer-*",
      "arn:aws:logs:*:*:log-group:/aws/apigateway/sentiment-analyzer-*:*"
    ]
  }

  # CloudWatch Alarms and Dashboards
  # SECURITY: Scoped to sentiment-analyzer-* alarms via condition (FR-008)
  # Note: CloudWatch alarms don't support resource-level ARNs for all actions,
  # so we use condition keys to restrict to sentiment-analyzer-* alarm names
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
      "arn:aws:cloudwatch:*:*:alarm:sentiment-analyzer-*",
      "arn:aws:cloudwatch::*:dashboard/sentiment-analyzer-*"
    ]
  }

  # CloudWatch read-only actions that require wildcard resource
  statement {
    sid    = "CloudWatchReadOnly"
    effect = "Allow"
    actions = [
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:DescribeAlarms"
    ]
    resources = ["*"]
  }

  # Cognito User Pools
  # SECURITY: Scoped to sentiment-analyzer-* user pools (FR-009)
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
      values   = ["sentiment-analyzer-*"]
    }
  }

  # Cognito User Pools - List operations (require wildcard)
  statement {
    sid    = "CognitoIDPList"
    effect = "Allow"
    actions = [
      "cognito-idp:ListUserPools",
      "cognito-idp:DescribeUserPool"
    ]
    resources = ["*"]
  }

  # Cognito Identity Pools
  # SECURITY: Scoped to sentiment-analyzer-* identity pools (FR-009)
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
      values   = ["sentiment-analyzer-*"]
    }
  }

  # Cognito Identity Pools - List operations (require wildcard)
  statement {
    sid    = "CognitoIdentityList"
    effect = "Allow"
    actions = [
      "cognito-identity:ListIdentityPools",
      "cognito-identity:DescribeIdentityPool"
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
  # SECURITY: Scoped to sentiment-analyzer-* and CIDeploy* policies (FR-010)
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
      "arn:aws:iam::*:policy/sentiment-analyzer-*",
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
  # SECURITY: Scoped to sentiment-analyzer-* templates via tag condition (FR-011)
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
      values   = ["sentiment-analyzer-*"]
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
  # SECURITY: Scoped to sentiment-analyzer-* groups (FR-011)
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
      "arn:aws:xray:*:*:group/sentiment-analyzer-*/*"
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
      "arn:aws:xray:*:*:sampling-rule/sentiment-analyzer-*"
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
      "xray:GetInsightSummaries"
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
      "s3:PutObjectAcl",
      "s3:GetObjectTagging",
      "s3:PutObjectTagging"
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
  # SECURITY: Scoped via tag condition (FR-011)
  # Note: CloudFront distributions don't support resource-level permissions
  # for most actions, so we use tag-based conditions where possible
  statement {
    sid    = "CloudFront"
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
      "arn:aws:cloudfront::*:distribution/*",
      "arn:aws:cloudfront::*:origin-access-control/*",
      "arn:aws:cloudfront::*:cache-policy/*",
      "arn:aws:cloudfront::*:response-headers-policy/*"
    ]
    condition {
      test     = "StringLike"
      variable = "aws:ResourceTag/Name"
      values   = ["sentiment-analyzer-*"]
    }
  }

  # CloudFront List operations - require wildcard
  statement {
    sid    = "CloudFrontList"
    effect = "Allow"
    actions = [
      "cloudfront:ListDistributions",
      "cloudfront:ListOriginAccessControls",
      "cloudfront:ListCachePolicies",
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
  # SECURITY: Scoped to sentiment-analyzer-* backup resources (FR-011)
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
      "arn:aws:backup:*:*:backup-vault:sentiment-analyzer-*",
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
  # SECURITY: Scoped to sentiment-analyzer-* budgets via condition (FR-011)
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
      "arn:aws:budgets::*:budget/sentiment-analyzer-*"
    ]
  }

  # Budgets List operations - require wildcard
  statement {
    sid    = "BudgetsList"
    effect = "Allow"
    actions = [
      "budgets:DescribeBudgets"
    ]
    resources = ["*"]
  }

  # CloudWatch RUM
  # SECURITY: Scoped to sentiment-analyzer-* app monitors (FR-011)
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
      "arn:aws:rum:*:*:appmonitor/sentiment-analyzer-*"
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
  # SECURITY: Scoped to sentiment-analyzer-* keys via alias pattern (FR-013)
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
      values   = ["alias/sentiment-analyzer-*"]
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
  statement {
    sid    = "KMSAlias"
    effect = "Allow"
    actions = [
      "kms:CreateAlias",
      "kms:DeleteAlias",
      "kms:UpdateAlias"
    ]
    resources = [
      "arn:aws:kms:*:*:alias/sentiment-analyzer-*"
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
    "sentiment-analyzer-preprod-deployer",
    "sentiment-analyzer-prod-deployer"
  ]
}
