# X-Ray Module Variables
# ======================

variable "environment" {
  description = "Deployment environment (dev, preprod, prod)"
  type        = string
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

# ===================================================================
# Non-Prod Sampling (dev/preprod)
# ===================================================================

variable "reservoir_size" {
  description = "Reservoir size for non-prod sampling rule (FR-034)"
  type        = number
  default     = 1
}

variable "fixed_rate" {
  description = "Fixed sampling rate for non-prod (1.0 = 100%)"
  type        = number
  default     = 1.0
}

# ===================================================================
# Prod Sampling -- Graduated per FR-179
# ===================================================================

variable "prod_apigw_reservoir_size" {
  description = "Reservoir size for prod API Gateway sampling rule"
  type        = number
  default     = 10
}

variable "prod_apigw_fixed_rate" {
  description = "Fixed sampling rate for prod API Gateway traces (0.10 = 10%)"
  type        = number
  default     = 0.10
}

variable "prod_fnurl_reservoir_size" {
  description = "Reservoir size for prod Function URL sampling rule"
  type        = number
  default     = 5
}

variable "prod_fnurl_fixed_rate" {
  description = "Fixed sampling rate for prod Function URL traces (0.05 = 5%)"
  type        = number
  default     = 0.05
}

variable "prod_default_reservoir_size" {
  description = "Reservoir size for prod default catch-all sampling rule"
  type        = number
  default     = 5
}

variable "prod_default_fixed_rate" {
  description = "Fixed sampling rate for prod default catch-all (0.10 = 10%)"
  type        = number
  default     = 0.10
}
