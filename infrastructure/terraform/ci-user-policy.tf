# CI User IAM Policy for GitHub Actions Deploy Pipeline
# =====================================================
#
# This file defines the IAM policy attached to the manually-created CI users:
# - sentiment-analyzer-preprod-ci (preprod environment)
# - sentiment-analyzer-prod-ci (prod environment)
#
# These users are created manually outside of Terraform, but their policies
# are managed here to ensure consistency and track permission changes.
#
# To apply this policy to the CI users, run:
#   aws iam put-user-policy \
#     --user-name sentiment-analyzer-preprod-ci \
#     --policy-name TerraformDeployPolicy \
#     --policy-document file://ci-policy.json

# Generate the CI policy as a data source so it can be exported
data "aws_iam_policy_document" "ci_deploy" {
  # ==================================================================
  # AWS Fault Injection Simulator (FIS) - Comprehensive Permissions
  # ==================================================================
  # References:
  # - https://docs.aws.amazon.com/fis/latest/userguide/security_iam_id-based-policy-examples.html
  # - https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsfaultinjectionservice.html

  # FIS Experiment Template Management (CREATE, READ, UPDATE, DELETE)
  statement {
    sid    = "FISExperimentTemplateManagement"
    effect = "Allow"

    actions = [
      "fis:CreateExperimentTemplate",
      "fis:GetExperimentTemplate",
      "fis:UpdateExperimentTemplate",
      "fis:DeleteExperimentTemplate",
      "fis:ListExperimentTemplates",
      "fis:TagResource",
      "fis:UntagResource",
      "fis:ListTagsForResource"
    ]

    resources = ["*"]
  }

  # FIS Experiment Execution (START, STOP, READ)
  statement {
    sid    = "FISExperimentExecution"
    effect = "Allow"

    actions = [
      "fis:StartExperiment",
      "fis:StopExperiment",
      "fis:GetExperiment",
      "fis:ListExperiments"
    ]

    resources = ["*"]
  }

  # FIS Action Discovery (READ-ONLY)
  statement {
    sid    = "FISActionDiscovery"
    effect = "Allow"

    actions = [
      "fis:GetAction",
      "fis:ListActions",
      "fis:GetTargetResourceType",
      "fis:ListTargetResourceTypes"
    ]

    resources = ["*"]
  }

  # FIS Target Account Configuration (Multi-account chaos testing support)
  statement {
    sid    = "FISTargetAccountConfiguration"
    effect = "Allow"

    actions = [
      "fis:CreateTargetAccountConfiguration",
      "fis:GetTargetAccountConfiguration",
      "fis:UpdateTargetAccountConfiguration",
      "fis:DeleteTargetAccountConfiguration",
      "fis:ListTargetAccountConfigurations"
    ]

    resources = ["*"]
  }

  # ==================================================================
  # CloudWatch Logs - FIS Experiment Logs
  # ==================================================================

  statement {
    sid    = "CloudWatchLogsFISExperiments"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:DescribeLogGroups",
      "logs:PutRetentionPolicy",
      "logs:DeleteLogGroup",
      "logs:TagLogGroup",
      "logs:UntagLogGroup",
      "logs:ListTagsLogGroup"
    ]

    resources = [
      "arn:aws:logs:*:*:log-group:/aws/fis/*"
    ]
  }

  # ==================================================================
  # IAM - PassRole for FIS Execution Role
  # ==================================================================
  # FIS requires permission to assume the FIS execution role
  # when creating experiment templates

  statement {
    sid    = "IAMPassRoleForFIS"
    effect = "Allow"

    actions = [
      "iam:PassRole"
    ]

    resources = [
      "arn:aws:iam::*:role/*-fis-execution-role"
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["fis.amazonaws.com"]
    }
  }

  # ==================================================================
  # Lambda - Function Management
  # ==================================================================

  statement {
    sid    = "LambdaFunctionManagement"
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
      "lambda:ListTags"
    ]

    resources = ["*"]
  }

  # Lambda Function URL Configuration
  statement {
    sid    = "LambdaFunctionURL"
    effect = "Allow"

    actions = [
      "lambda:CreateFunctionUrlConfig",
      "lambda:UpdateFunctionUrlConfig",
      "lambda:DeleteFunctionUrlConfig",
      "lambda:GetFunctionUrlConfig"
    ]

    resources = ["*"]
  }

  # Lambda Event Source Mappings
  statement {
    sid    = "LambdaEventSourceMappings"
    effect = "Allow"

    actions = [
      "lambda:CreateEventSourceMapping",
      "lambda:UpdateEventSourceMapping",
      "lambda:DeleteEventSourceMapping",
      "lambda:GetEventSourceMapping",
      "lambda:ListEventSourceMappings"
    ]

    resources = ["*"]
  }

  # Lambda Layers
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

    resources = ["*"]
  }

  # ==================================================================
  # DynamoDB - Table Management
  # ==================================================================

  statement {
    sid    = "DynamoDBTableManagement"
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

  # ==================================================================
  # SNS - Topic Management
  # ==================================================================

  statement {
    sid    = "SNSTopicManagement"
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

  # ==================================================================
  # SQS - Queue Management (DLQ)
  # ==================================================================

  statement {
    sid    = "SQSQueueManagement"
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

  # ==================================================================
  # IAM - Role and Policy Management
  # ==================================================================

  statement {
    sid    = "IAMRolePolicyManagement"
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
      "arn:aws:iam::*:role/*-fis-execution-role"
    ]
  }

  # IAM Policy Management
  statement {
    sid    = "IAMPolicyManagement"
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

  # ==================================================================
  # CloudWatch - Logs and Alarms
  # ==================================================================

  # CloudWatch Logs (Lambda function logs)
  statement {
    sid    = "CloudWatchLogsLambda"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:DescribeLogGroups",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagLogGroup",
      "logs:UntagLogGroup"
    ]

    resources = [
      "arn:aws:logs:*:*:log-group:/aws/lambda/*"
    ]
  }

  # CloudWatch Alarms
  statement {
    sid    = "CloudWatchAlarms"
    effect = "Allow"

    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:ListTagsForResource"
    ]

    resources = ["*"]
  }

  # CloudWatch Dashboards (Feature 006)
  statement {
    sid    = "CloudWatchDashboards"
    effect = "Allow"

    actions = [
      "cloudwatch:PutDashboard",
      "cloudwatch:DeleteDashboards",
      "cloudwatch:GetDashboard",
      "cloudwatch:ListDashboards"
    ]

    resources = ["*"]
  }

  # CloudWatch Metrics Discovery
  statement {
    sid    = "CloudWatchMetrics"
    effect = "Allow"

    actions = [
      "cloudwatch:ListMetrics",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:DescribeAlarmHistory"
    ]

    resources = ["*"]
  }

  # CloudWatch Log Metric Filters
  statement {
    sid    = "CloudWatchLogMetricFilters"
    effect = "Allow"

    actions = [
      "logs:PutMetricFilter",
      "logs:DeleteMetricFilter",
      "logs:DescribeMetricFilters"
    ]

    resources = ["*"]
  }

  # ==================================================================
  # Cognito - User Pool Management (Feature 006)
  # ==================================================================
  # References:
  # - https://docs.aws.amazon.com/cognito/latest/developerguide/security-iam.html
  # - https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazoncognitouserpools.html

  statement {
    sid    = "CognitoUserPoolManagement"
    effect = "Allow"

    actions = [
      "cognito-idp:CreateUserPool",
      "cognito-idp:UpdateUserPool",
      "cognito-idp:DeleteUserPool",
      "cognito-idp:DescribeUserPool",
      "cognito-idp:ListUserPools",
      "cognito-idp:GetUserPoolMfaConfig",
      "cognito-idp:SetUserPoolMfaConfig"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CognitoUserPoolClient"
    effect = "Allow"

    actions = [
      "cognito-idp:CreateUserPoolClient",
      "cognito-idp:UpdateUserPoolClient",
      "cognito-idp:DeleteUserPoolClient",
      "cognito-idp:DescribeUserPoolClient",
      "cognito-idp:ListUserPoolClients"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CognitoUserPoolDomain"
    effect = "Allow"

    actions = [
      "cognito-idp:CreateUserPoolDomain",
      "cognito-idp:UpdateUserPoolDomain",
      "cognito-idp:DeleteUserPoolDomain",
      "cognito-idp:DescribeUserPoolDomain"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CognitoResourceServer"
    effect = "Allow"

    actions = [
      "cognito-idp:CreateResourceServer",
      "cognito-idp:UpdateResourceServer",
      "cognito-idp:DeleteResourceServer",
      "cognito-idp:DescribeResourceServer",
      "cognito-idp:ListResourceServers"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CognitoIdentityProvider"
    effect = "Allow"

    actions = [
      "cognito-idp:CreateIdentityProvider",
      "cognito-idp:UpdateIdentityProvider",
      "cognito-idp:DeleteIdentityProvider",
      "cognito-idp:DescribeIdentityProvider",
      "cognito-idp:ListIdentityProviders"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CognitoTagging"
    effect = "Allow"

    actions = [
      "cognito-idp:TagResource",
      "cognito-idp:UntagResource",
      "cognito-idp:ListTagsForResource"
    ]

    resources = ["*"]
  }

  # ==================================================================
  # Cognito Identity Pools (for CloudWatch RUM)
  # ==================================================================

  statement {
    sid    = "CognitoIdentityPools"
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

  # ==================================================================
  # CloudFront - Distribution Management (Feature 006)
  # ==================================================================

  statement {
    sid    = "CloudFrontDistribution"
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
      "cloudfront:ListTagsForResource"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CloudFrontOriginAccessControl"
    effect = "Allow"

    actions = [
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:GetOriginAccessControlConfig",
      "cloudfront:ListOriginAccessControls"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "CloudFrontCachePolicy"
    effect = "Allow"

    actions = [
      "cloudfront:CreateCachePolicy",
      "cloudfront:UpdateCachePolicy",
      "cloudfront:DeleteCachePolicy",
      "cloudfront:GetCachePolicy",
      "cloudfront:ListCachePolicies"
    ]

    resources = ["*"]
  }

  # ==================================================================
  # CloudWatch RUM - Real User Monitoring (Feature 006)
  # ==================================================================

  statement {
    sid    = "CloudWatchRUM"
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

  # ==================================================================
  # AWS Budgets - Cost Monitoring (Feature 006)
  # ==================================================================

  statement {
    sid    = "AWSBudgets"
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

  # ==================================================================
  # ACM - Certificate Management (for CloudFront custom domains)
  # ==================================================================

  statement {
    sid    = "ACMCertificates"
    effect = "Allow"

    actions = [
      "acm:DescribeCertificate",
      "acm:ListCertificates",
      "acm:ListTagsForCertificate",
      "acm:GetCertificate"
    ]

    resources = ["*"]
  }

  # ==================================================================
  # AWS Backup - DynamoDB Backup Management
  # ==================================================================

  statement {
    sid    = "AWSBackupManagement"
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

  # IAM PassRole for AWS Backup
  statement {
    sid    = "IAMPassRoleForBackup"
    effect = "Allow"

    actions = [
      "iam:PassRole"
    ]

    resources = [
      "arn:aws:iam::*:role/*-backup-role"
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["backup.amazonaws.com"]
    }
  }

  # ==================================================================
  # EventBridge - Rules Management
  # ==================================================================

  statement {
    sid    = "EventBridgeRulesManagement"
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

  # ==================================================================
  # Secrets Manager - Secret Management
  # ==================================================================

  statement {
    sid    = "SecretsManagerManagement"
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

  # ==================================================================
  # S3 - Model Bucket Management
  # ==================================================================

  statement {
    sid    = "S3BucketManagement"
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
    sid    = "S3ObjectManagement"
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
      "arn:aws:s3:::sentiment-analyzer-*/*",
      "arn:aws:s3:::*-sentiment-*/*"
    ]
  }

  # ==================================================================
  # Terraform State Management
  # ==================================================================

  # S3 State Bucket Access
  statement {
    sid    = "TerraformStateS3"
    effect = "Allow"

    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject"
    ]

    resources = [
      "arn:aws:s3:::sentiment-analyzer-tfstate-*",
      "arn:aws:s3:::sentiment-analyzer-tfstate-*/*"
    ]
  }

  # ==================================================================
  # General Read Permissions
  # ==================================================================

  # Allow reading AWS account information
  statement {
    sid    = "GeneralReadPermissions"
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

# Output the policy as JSON for easy application via AWS CLI
output "ci_deploy_policy_json" {
  description = "CI deploy policy in JSON format for manual application"
  value       = data.aws_iam_policy_document.ci_deploy.json
}

# Output AWS CLI command for easy copy-paste
output "apply_preprod_policy_command" {
  description = "Command to apply policy to preprod CI user"
  value       = <<-EOT
    # Save policy to file first:
    terraform output -raw ci_deploy_policy_json > /tmp/ci-policy.json

    # Apply to preprod CI user:
    aws iam put-user-policy \
      --user-name sentiment-analyzer-preprod-ci \
      --policy-name TerraformDeployPolicy \
      --policy-document file:///tmp/ci-policy.json
  EOT
}

output "apply_prod_policy_command" {
  description = "Command to apply policy to prod CI user"
  value       = <<-EOT
    # Save policy to file first:
    terraform output -raw ci_deploy_policy_json > /tmp/ci-policy.json

    # Apply to prod CI user:
    aws iam put-user-policy \
      --user-name sentiment-analyzer-prod-ci \
      --policy-name TerraformDeployPolicy \
      --policy-document file:///tmp/ci-policy.json
  EOT
}
