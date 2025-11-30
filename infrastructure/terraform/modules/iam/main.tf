# IAM Roles and Policies for Lambda Functions
# Following least-privilege principle per security review

# ===================================================================
# Ingestion Lambda IAM Role
# ===================================================================

resource "aws_iam_role" "ingestion_lambda" {
  name = "${var.environment}-ingestion-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Lambda      = "ingestion"
  }
}

# Ingestion Lambda policy (DynamoDB PutItem only)
resource "aws_iam_role_policy" "ingestion_dynamodb" {
  name = "${var.environment}-ingestion-dynamodb-policy"
  role = aws_iam_role.ingestion_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# Ingestion Lambda: Secrets Manager access (Tiingo/Finnhub API keys)
resource "aws_iam_role_policy" "ingestion_secrets" {
  name = "${var.environment}-ingestion-secrets-policy"
  role = aws_iam_role.ingestion_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          var.tiingo_secret_arn,
          var.finnhub_secret_arn
        ]
      }
    ]
  })
}

# Ingestion Lambda: SNS publish (trigger analysis)
resource "aws_iam_role_policy" "ingestion_sns" {
  name = "${var.environment}-ingestion-sns-policy"
  role = aws_iam_role.ingestion_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = var.analysis_topic_arn
      }
    ]
  })
}

# Ingestion Lambda: CloudWatch Logs
resource "aws_iam_role_policy_attachment" "ingestion_logs" {
  role       = aws_iam_role.ingestion_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Ingestion Lambda: CloudWatch Metrics
resource "aws_iam_role_policy" "ingestion_metrics" {
  name = "${var.environment}-ingestion-metrics-policy"
  role = aws_iam_role.ingestion_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SentimentAnalyzer"
          }
        }
      }
    ]
  })
}

# ===================================================================
# Analysis Lambda IAM Role
# ===================================================================

resource "aws_iam_role" "analysis_lambda" {
  name = "${var.environment}-analysis-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Lambda      = "analysis"
  }
}

# Analysis Lambda policy (DynamoDB UpdateItem + GetItem)
resource "aws_iam_role_policy" "analysis_dynamodb" {
  name = "${var.environment}-analysis-dynamodb-policy"
  role = aws_iam_role.analysis_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# Analysis Lambda: CloudWatch Logs
resource "aws_iam_role_policy_attachment" "analysis_logs" {
  role       = aws_iam_role.analysis_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Analysis Lambda: CloudWatch Metrics
resource "aws_iam_role_policy" "analysis_metrics" {
  name = "${var.environment}-analysis-metrics-policy"
  role = aws_iam_role.analysis_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SentimentAnalyzer"
          }
        }
      }
    ]
  })
}

# Analysis Lambda: SQS Dead Letter Queue
resource "aws_iam_role_policy" "analysis_dlq" {
  name = "${var.environment}-analysis-dlq-policy"
  role = aws_iam_role.analysis_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = var.dlq_arn
      }
    ]
  })
}

# Analysis Lambda: S3 Model Access (lazy loading from S3)
resource "aws_iam_role_policy" "analysis_s3_model" {
  name = "${var.environment}-analysis-s3-model-policy"
  role = aws_iam_role.analysis_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${var.model_s3_bucket_arn}/*"
      }
    ]
  })
}

# ===================================================================
# Dashboard Lambda IAM Role
# ===================================================================

resource "aws_iam_role" "dashboard_lambda" {
  name = "${var.environment}-dashboard-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Lambda      = "dashboard"
  }
}

# Dashboard Lambda policy (DynamoDB Query + GetItem + DescribeTable - READ ONLY)
resource "aws_iam_role_policy" "dashboard_dynamodb" {
  name = "${var.environment}-dashboard-dynamodb-policy"
  role = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/by_sentiment",
          "${var.dynamodb_table_arn}/index/by_tag",
          "${var.dynamodb_table_arn}/index/by_status"
        ]
      }
    ]
  })
}

# Dashboard Lambda: Secrets Manager (API key)
resource "aws_iam_role_policy" "dashboard_secrets" {
  name = "${var.environment}-dashboard-secrets-policy"
  role = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.dashboard_api_key_secret_arn
      }
    ]
  })
}

# Dashboard Lambda: CloudWatch Logs
resource "aws_iam_role_policy_attachment" "dashboard_logs" {
  role       = aws_iam_role.dashboard_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Dashboard Lambda: CloudWatch Metrics
resource "aws_iam_role_policy" "dashboard_metrics" {
  name = "${var.environment}-dashboard-metrics-policy"
  role = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SentimentAnalyzer"
          }
        }
      }
    ]
  })
}

# Dashboard Lambda: Chaos Testing (FIS + Chaos Experiments DynamoDB)
# Only in preprod/dev environments
resource "aws_iam_role_policy" "dashboard_chaos" {
  count = var.environment != "prod" ? 1 : 0
  name  = "${var.environment}-dashboard-chaos-policy"
  role  = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "fis:StartExperiment",
          "fis:StopExperiment",
          "fis:GetExperiment",
          "fis:ListExperiments"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          var.chaos_experiments_table_arn,
          "${var.chaos_experiments_table_arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:GetMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

# Dashboard Lambda: Ticker Cache S3 Read Access (Feature 006)
resource "aws_iam_role_policy" "dashboard_ticker_cache" {
  count = var.enable_feature_006 ? 1 : 0
  name  = "${var.environment}-dashboard-ticker-cache-policy"
  role  = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${var.ticker_cache_bucket_arn}/*"
      }
    ]
  })
}

# Dashboard Lambda: Feature 006 Users Table Access (full CRUD for configs, alerts, users)
resource "aws_iam_role_policy" "dashboard_feature_006_users" {
  count = var.enable_feature_006 ? 1 : 0
  name  = "${var.environment}-dashboard-feature-006-users-policy"
  role  = aws_iam_role.dashboard_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          var.feature_006_users_table_arn,
          "${var.feature_006_users_table_arn}/index/by_email",
          "${var.feature_006_users_table_arn}/index/by_cognito_sub",
          "${var.feature_006_users_table_arn}/index/by_entity_status"
        ]
      }
    ]
  })
}

# ===================================================================
# Metrics Lambda IAM Role (Operational Monitoring)
# ===================================================================

resource "aws_iam_role" "metrics_lambda" {
  name = "${var.environment}-metrics-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Lambda      = "metrics"
  }
}

# Metrics Lambda policy (DynamoDB Query on by_status GSI only)
resource "aws_iam_role_policy" "metrics_dynamodb" {
  name = "${var.environment}-metrics-dynamodb-policy"
  role = aws_iam_role.metrics_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query"
        ]
        Resource = "${var.dynamodb_table_arn}/index/by_status"
      }
    ]
  })
}

# Metrics Lambda: CloudWatch Logs
resource "aws_iam_role_policy_attachment" "metrics_logs" {
  role       = aws_iam_role.metrics_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Metrics Lambda: CloudWatch Metrics (emit stuck items metric)
resource "aws_iam_role_policy" "metrics_cloudwatch" {
  name = "${var.environment}-metrics-cloudwatch-policy"
  role = aws_iam_role.metrics_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SentimentAnalyzer"
          }
        }
      }
    ]
  })
}

# ===================================================================
# Notification Lambda IAM Role (Feature 006 - Email Alerts)
# ===================================================================

resource "aws_iam_role" "notification_lambda" {
  name = "${var.environment}-notification-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Lambda      = "notification"
  }
}

# Notification Lambda: DynamoDB access (read/write notifications, user prefs)
# Uses Feature 006 users table for notifications and user preferences
resource "aws_iam_role_policy" "notification_dynamodb" {
  name = "${var.environment}-notification-dynamodb-policy"
  role = aws_iam_role.notification_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = concat(
          # Legacy sentiment-items table (for reading sentiment data)
          [
            var.dynamodb_table_arn,
            "${var.dynamodb_table_arn}/index/*"
          ],
          # Feature 006 users table (for notifications, alerts, user prefs)
          var.feature_006_users_table_arn != "" ? [
            var.feature_006_users_table_arn,
            "${var.feature_006_users_table_arn}/index/by_email",
            "${var.feature_006_users_table_arn}/index/by_cognito_sub",
            "${var.feature_006_users_table_arn}/index/by_entity_status"
          ] : []
        )
      }
    ]
  })
}

# Notification Lambda: Secrets Manager (SendGrid API key)
resource "aws_iam_role_policy" "notification_secrets" {
  name = "${var.environment}-notification-secrets-policy"
  role = aws_iam_role.notification_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.sendgrid_secret_arn
      }
    ]
  })
}

# Notification Lambda: CloudWatch Logs
resource "aws_iam_role_policy_attachment" "notification_logs" {
  role       = aws_iam_role.notification_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Notification Lambda: X-Ray tracing
resource "aws_iam_role_policy_attachment" "notification_xray" {
  role       = aws_iam_role.notification_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Notification Lambda: CloudWatch Metrics
resource "aws_iam_role_policy" "notification_metrics" {
  name = "${var.environment}-notification-metrics-policy"
  role = aws_iam_role.notification_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "SentimentAnalyzer"
          }
        }
      }
    ]
  })
}
