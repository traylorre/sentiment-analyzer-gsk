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
      "s3:DeleteBucketPolicy"
    ]

    resources = [
      "arn:aws:s3:::sentiment-analyzer-*"
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
      "s3:ListBucket"
    ]

    resources = [
      "arn:aws:s3:::sentiment-analyzer-*/*"
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
