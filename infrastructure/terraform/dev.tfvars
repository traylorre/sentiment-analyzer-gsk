# Development Environment Configuration

environment   = "dev"
aws_region    = "us-east-1"
watch_tags    = "AI,climate,economy,health,sports"
model_version = "v1.0.0"

# CORS: Allow localhost for local development
cors_allowed_origins = ["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000"]

# Feature 1189: Environment-specific JWT audience (A16)
# Prevents cross-environment token replay attacks
jwt_audience = "sentiment-api-dev"
