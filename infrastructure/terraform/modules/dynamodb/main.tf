# DynamoDB Table: sentiment-items
# Regional Multi-AZ architecture with GSIs

resource "aws_dynamodb_table" "sentiment_items" {
  name             = "${var.environment}-sentiment-items"
  billing_mode     = "PAY_PER_REQUEST" # On-demand pricing
  hash_key         = "source_id"
  range_key        = "timestamp"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  # Enable point-in-time recovery (35-day retention)
  point_in_time_recovery {
    enabled = true
  }

  # Primary table attributes
  attribute {
    name = "source_id"
    type = "S" # String (e.g., "newsapi#abc123def456")
  }

  attribute {
    name = "timestamp"
    type = "S" # String (ISO8601: "2025-11-17T14:30:00.000Z")
  }

  # GSI attributes
  attribute {
    name = "sentiment"
    type = "S" # String (positive|neutral|negative)
  }

  attribute {
    name = "tag"
    type = "S" # String (individual tag for fan-out queries)
  }

  attribute {
    name = "status"
    type = "S" # String (pending|analyzed)
  }

  # GSI 1: by_sentiment
  # Query pattern: Get items by sentiment classification
  global_secondary_index {
    name            = "by_sentiment"
    hash_key        = "sentiment"
    range_key       = "timestamp"
    projection_type = "ALL" # Project all attributes
  }

  # GSI 2: by_tag
  # Query pattern: Get items by individual tag
  # Note: Application code must fan-out matched_tags into separate writes
  global_secondary_index {
    name            = "by_tag"
    hash_key        = "tag"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI 3: by_status
  # Query pattern: Dashboard displays recent items (needs all fields for display)
  global_secondary_index {
    name            = "by_status"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "ALL" # Dashboard needs all fields to display items
  }

  # TTL configuration (30-day auto-deletion)
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  # Encryption at rest (AWS-managed keys)
  server_side_encryption {
    enabled     = true
    kms_key_arn = null # Use AWS-managed keys (default, no extra cost)
  }

  # Tags for resource management
  tags = {
    Name        = "${var.environment}-sentiment-items"
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    ManagedBy   = "Terraform"
    CostCenter  = "demo"
  }
}

# On-demand backup schedule (daily at 02:00 UTC)
resource "aws_backup_plan" "dynamodb_daily" {
  name = "${var.environment}-dynamodb-daily-backup"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.dynamodb.name
    schedule          = "cron(0 2 * * ? *)" # 02:00 UTC daily

    lifecycle {
      delete_after = 7 # 7-day retention
    }

    recovery_point_tags = {
      Environment = var.environment
      Feature     = "001-interactive-dashboard-demo"
    }
  }
}

# Backup vault
resource "aws_backup_vault" "dynamodb" {
  name = "${var.environment}-dynamodb-backup-vault"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

# Backup selection (target DynamoDB table)
resource "aws_backup_selection" "dynamodb" {
  name         = "${var.environment}-dynamodb-backup-selection"
  plan_id      = aws_backup_plan.dynamodb_daily.id
  iam_role_arn = aws_iam_role.backup.arn

  resources = [
    aws_dynamodb_table.sentiment_items.arn
  ]
}

# IAM role for AWS Backup
resource "aws_iam_role" "backup" {
  name = "${var.environment}-dynamodb-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

# Attach AWS managed backup policy
resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

# CloudWatch alarms for DynamoDB
resource "aws_cloudwatch_metric_alarm" "user_errors" {
  alarm_name          = "${var.environment}-dynamodb-user-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "UserErrors"
  namespace           = "AWS/DynamoDB"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when DynamoDB user errors > 10 in 5 minutes (validation failures)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.sentiment_items.name
  }

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_cloudwatch_metric_alarm" "system_errors" {
  alarm_name          = "${var.environment}-dynamodb-system-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SystemErrors"
  namespace           = "AWS/DynamoDB"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when DynamoDB system errors > 5 in 5 minutes (throttling)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.sentiment_items.name
  }

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_cloudwatch_metric_alarm" "write_throttles" {
  alarm_name          = "${var.environment}-dynamodb-write-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ConsumedWriteCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = 60 # 1 minute
  statistic           = "Sum"
  threshold           = 1000
  alarm_description   = "Alert when write capacity > 1000 WCUs in 1 minute (unexpected traffic spike)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = aws_dynamodb_table.sentiment_items.name
  }

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}
