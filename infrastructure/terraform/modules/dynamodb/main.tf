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
    type = "S" # String (e.g., "tiingo#abc123def456" or "finnhub#abc123def456")
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
  # Query pattern: Monitor pending items (operational dashboards)
  global_secondary_index {
    name            = "by_status"
    hash_key        = "status"
    range_key       = "timestamp"
    projection_type = "KEYS_ONLY" # Minimal storage for monitoring
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
  count = var.enable_backup ? 1 : 0
  name  = "${var.environment}-dynamodb-daily-backup"

  rule {
    rule_name         = "daily_backup"
    target_vault_name = aws_backup_vault.dynamodb[0].name
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
  count = var.enable_backup ? 1 : 0
  name  = "${var.environment}-dynamodb-backup-vault"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

# Backup selection (target DynamoDB table)
resource "aws_backup_selection" "dynamodb" {
  count        = var.enable_backup ? 1 : 0
  name         = "${var.environment}-dynamodb-backup-selection"
  plan_id      = aws_backup_plan.dynamodb_daily[0].id
  iam_role_arn = aws_iam_role.backup[0].arn

  resources = [
    aws_dynamodb_table.sentiment_items.arn
  ]
}

# IAM role for AWS Backup
resource "aws_iam_role" "backup" {
  count = var.enable_backup ? 1 : 0
  name  = "${var.environment}-dynamodb-backup-role"

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
  count      = var.enable_backup ? 1 : 0
  role       = aws_iam_role.backup[0].name
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

# ===================================================================
# DynamoDB Table: Feature 006 - User Data (Single-Table Design)
# ===================================================================
#
# Stores all Feature 006 user-related data using single-table design:
# - Users (PK=USER#{user_id}, SK=PROFILE)
# - Configurations (PK=USER#{user_id}, SK=CONFIG#{config_id})
# - Alert Rules (PK=USER#{user_id}, SK=ALERT#{alert_id})
# - Notifications (PK=USER#{user_id}, SK={timestamp})
# - Digest Settings (PK=USER#{user_id}, SK=DIGEST_SETTINGS)
# - Magic Links (PK=TOKEN#{token_id}, SK=TOKEN)
# - Circuit Breakers (PK=CIRCUIT#{service}, SK=STATE)
# - Quota Trackers (PK=SYSTEM#QUOTA, SK={date})
#
# For On-Call Engineers:
#   Query user's items: PK = USER#{user_id}
#   Filter by entity_type attribute to get specific types

resource "aws_dynamodb_table" "feature_006_users" {
  name         = "${var.environment}-sentiment-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  # Enable point-in-time recovery (35-day retention)
  point_in_time_recovery {
    enabled = true
  }

  # Primary key attributes
  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # GSI attributes
  attribute {
    name = "email"
    type = "S"
  }

  attribute {
    name = "cognito_sub"
    type = "S"
  }

  attribute {
    name = "entity_type"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  # GSI 1: by_email
  # Query pattern: Find user by email address (for login/conflict detection)
  global_secondary_index {
    name            = "by_email"
    hash_key        = "email"
    projection_type = "ALL"
  }

  # GSI 2: by_cognito_sub
  # Query pattern: Find user by Cognito sub (OAuth login)
  global_secondary_index {
    name            = "by_cognito_sub"
    hash_key        = "cognito_sub"
    projection_type = "ALL"
  }

  # GSI 3: by_entity_status
  # Query pattern: Filter notifications by status, filter alerts by enabled state
  # Composite key: entity_type (hash) + status (range) allows:
  #   - "Find all NOTIFICATION items with status=failed"
  #   - "Find all ALERT items with is_enabled=true"
  global_secondary_index {
    name            = "by_entity_status"
    hash_key        = "entity_type"
    range_key       = "status"
    projection_type = "ALL"
  }

  # TTL configuration (for magic links, sessions)
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  # Encryption at rest
  server_side_encryption {
    enabled     = true
    kms_key_arn = null # AWS-managed keys
  }

  tags = {
    Name        = "${var.environment}-sentiment-users"
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    ManagedBy   = "Terraform"
    CostCenter  = "demo"
  }
}

# ===================================================================
# DynamoDB Table: Chaos Testing Experiments (Phase 1)
# ===================================================================

resource "aws_dynamodb_table" "chaos_experiments" {
  name         = "${var.environment}-chaos-experiments"
  billing_mode = "PAY_PER_REQUEST" # On-demand pricing (~$0.50/month)
  hash_key     = "experiment_id"
  range_key    = "created_at"

  # Enable point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  # Primary table attributes
  attribute {
    name = "experiment_id"
    type = "S" # String (UUID)
  }

  attribute {
    name = "created_at"
    type = "S" # String (ISO8601 timestamp)
  }

  attribute {
    name = "status"
    type = "S" # String (pending|running|completed|failed|stopped)
  }

  # GSI: by_status - Query experiments by status
  global_secondary_index {
    name            = "by_status"
    hash_key        = "status"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  # TTL configuration (auto-delete experiments after 7 days)
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  # Encryption at rest
  server_side_encryption {
    enabled     = true
    kms_key_arn = null # Use AWS-managed keys
  }

  tags = {
    Name        = "${var.environment}-chaos-experiments"
    Environment = var.environment
    Feature     = "chaos-testing"
    ManagedBy   = "Terraform"
    CostCenter  = "demo"
  }
}
