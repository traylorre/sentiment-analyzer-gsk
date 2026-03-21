# CloudWatch Alarms Module Variables
# ====================================

variable "environment" {
  description = "Deployment environment (dev, preprod, prod)"
  type        = string
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarm fires (SNS topics)"
  type        = list(string)
  default     = []
}

variable "ok_actions" {
  description = "List of ARNs to notify when alarm returns to OK"
  type        = list(string)
  default     = []
}

# ===================================================================
# Lambda Function Names (for metric dimensions)
# ===================================================================

variable "lambda_function_names" {
  description = "Map of Lambda service name to function name"
  type = object({
    ingestion    = string
    analysis     = string
    dashboard    = string
    notification = string
    metrics      = string
    sse          = string
  })
}

# ===================================================================
# Category 1: Lambda Error Thresholds (FR-040)
# ===================================================================

variable "error_threshold" {
  description = "Error count threshold per evaluation period"
  type        = number
  default     = 1
}

# ===================================================================
# Category 2: Lambda Latency Thresholds (FR-041)
# Phase 1: 80% of timeout. Phase 2: 2x observed P95.
# ===================================================================

variable "latency_thresholds" {
  description = "P95 latency thresholds in milliseconds per Lambda"
  type = object({
    ingestion    = number
    analysis     = number
    dashboard    = number
    notification = number
    metrics      = number
    sse          = number
  })
  default = {
    ingestion    = 48000  # 60s timeout × 80%
    analysis     = 48000  # 60s timeout × 80%
    dashboard    = 24000  # 30s timeout × 80%
    notification = 24000  # 30s timeout × 80%
    metrics      = 48000  # 60s timeout × 80%
    sse          = 720000 # 900s timeout × 80%
  }
}

# ===================================================================
# Category 7: Canary Thresholds (FR-121)
# ===================================================================

variable "canary_function_name" {
  description = "Canary Lambda function name (empty to skip canary alarms)"
  type        = string
  default     = ""
}

variable "canary_completeness_threshold" {
  description = "Minimum completeness ratio for canary traces"
  type        = number
  default     = 0.95
}

# ===================================================================
# Category 8: API Gateway (FR-138)
# ===================================================================

variable "api_gateway_name" {
  description = "API Gateway REST API name for metric dimensions"
  type        = string
  default     = ""
}

variable "api_gateway_stage" {
  description = "API Gateway stage name"
  type        = string
  default     = "v1"
}

variable "api_gateway_latency_threshold" {
  description = "API Gateway IntegrationLatency P99 threshold in ms"
  type        = number
  default     = 24000 # 80% of 30s dashboard Lambda timeout
}

# ===================================================================
# Category 9: SSE Connection Count (chaos-readiness)
# ===================================================================

variable "sse_max_connections" {
  description = "Maximum SSE connections before alarm fires (alarm at 80% of this value)"
  type        = number
  default     = 100
}

# ===================================================================
# Silent Failure Alarm Toggle
# ===================================================================

variable "create_silent_failure_alarms" {
  description = "Create individual silent failure path alarms"
  type        = bool
  default     = true
}
