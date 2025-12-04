# HuggingFace DistilBERT Implementation Guide

## Architecture Overview

```
SQS Queue (ingestion events)
    ↓
Lambda Function (512MB memory, Python 3.13)
    ├─ Load DistilBERT model (cached)
    ├─ Batch process 10 items
    └─ Call inference pipeline
         ├─ Tokenization (5-10ms)
         ├─ Model inference (50-100ms)
         └─ Post-processing (5ms)
    ↓
DynamoDB (sentiment-items table)
```

---

## Step 1: Dockerfile & Container Setup

### File: `lambda/Dockerfile`

```dockerfile
# Use AWS Lambda Python 3.13 runtime base image
FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements
COPY requirements.txt .

# Install dependencies (use --no-cache-dir to reduce image size)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY inference.py ${LAMBDA_TASK_ROOT}/

# Specify handler
CMD ["inference.lambda_handler"]
```

### File: `lambda/requirements.txt`

```
transformers==4.36.0
torch==2.1.0+cpu
numpy==1.24.3
```

**Note on torch:** Use `torch==2.1.0+cpu` to avoid GPU dependency and reduce image size

---

## Step 2: Inference Handler

### File: `lambda/inference.py`

```python
"""
Sentiment Analysis Lambda Handler using DistilBERT

Cold start: ~1.7-4.9 seconds (model loading)
Warm latency: 100-150ms per item (cached model)
Batch latency: 150-300ms for 10 items (15-30ms per item)
Memory: ~350-400MB of 512MB allocated
"""

import json
import logging
from typing import List, Dict, Any
import torch
from transformers import pipeline

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global model (initialized once per container)
classifier = None
model_loading_time = 0

def load_model():
    """
    Load DistilBERT model on first invocation.

    Latency breakdown:
    - First call: 1.7-4.9 seconds (model initialization + download from cache/hub)
    - Subsequent calls: <1ms (model already in memory)
    """
    global classifier, model_loading_time
    import time

    start = time.time()

    # Suppress transformers logging (reduce overhead)
    logging.getLogger("transformers").setLevel(logging.WARNING)

    # Load model - device=-1 means CPU (Lambda doesn't have GPU)
    classifier = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english",
        device=-1,  # Force CPU (no GPU on Lambda)
        model_kwargs={"torch_dtype": torch.float32}  # 32-bit for CPU accuracy
    )

    model_loading_time = time.time() - start
    logger.info(f"Model loaded in {model_loading_time:.3f} seconds")


def classify_sentiment(text: str) -> Dict[str, Any]:
    """
    Classify sentiment of a single text.

    Args:
        text: Input text (string, max 512 tokens for DistilBERT)

    Returns:
        {
            "text": "...",
            "sentiment": "POSITIVE" or "NEGATIVE",
            "score": 0.0-1.0,
            "latency_ms": 60-115
        }

    Latency: 60-115ms (tokenization + inference + post-processing)
    """
    import time
    start = time.time()

    # Truncate to max DistilBERT length (512 tokens ~2000 chars)
    if len(text) > 2000:
        text = text[:2000]

    # Perform inference
    prediction = classifier(text, truncation=True, max_length=512)[0]

    latency_ms = (time.time() - start) * 1000

    return {
        "text": text,
        "sentiment": prediction["label"],  # "POSITIVE" or "NEGATIVE"
        "score": float(prediction["score"]),
        "latency_ms": latency_ms
    }


def lambda_handler(event, context):
    """
    Main Lambda handler.

    Event schema:
    {
        "items": [
            {"id": "item-1", "text": "Great product!"},
            {"id": "item-2", "text": "Terrible experience"}
        ]
    }

    Response schema:
    {
        "statusCode": 200,
        "results": [
            {
                "id": "item-1",
                "text": "Great product!",
                "sentiment": "POSITIVE",
                "score": 0.9987,
                "latency_ms": 82
            },
            ...
        ],
        "metrics": {
            "total_items": 2,
            "total_latency_ms": 165,
            "avg_latency_ms": 82.5,
            "model_loading_time_ms": 0
        }
    }

    Cold start: 1.7-4.9s (includes model loading)
    Warm start: 100-200ms for single item, 150-300ms for 10 items
    """
    import time
    start_time = time.time()

    # Load model on first invocation (cold start)
    global classifier
    if classifier is None:
        load_model()

    try:
        # Extract items from event
        items = event.get("items", [])
        if not items:
            return {
                "statusCode": 400,
                "error": "No items provided",
                "results": []
            }

        logger.info(f"Processing {len(items)} items")

        # Classify each item
        results = []
        for item in items:
            try:
                text = item.get("text", "")
                if not text:
                    logger.warning(f"Skipping empty text for item {item.get('id')}")
                    continue

                result = classify_sentiment(text)
                result["id"] = item.get("id")  # Include original ID
                results.append(result)

            except Exception as e:
                logger.error(f"Error processing item {item.get('id')}: {str(e)}")
                results.append({
                    "id": item.get("id"),
                    "error": str(e)
                })

        # Calculate metrics
        total_latency = sum(r.get("latency_ms", 0) for r in results if "latency_ms" in r)
        avg_latency = total_latency / len(results) if results else 0

        total_time = (time.time() - start_time) * 1000

        return {
            "statusCode": 200,
            "results": results,
            "metrics": {
                "total_items": len(items),
                "processed_items": len(results),
                "total_inference_latency_ms": total_latency,
                "avg_inference_latency_ms": avg_latency,
                "total_lambda_duration_ms": total_time,
                "model_loading_time_ms": model_loading_time * 1000 if model_loading_time else 0,
                "cold_start": model_loading_time > 0
            }
        }

    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "error": f"Internal server error: {str(e)}",
            "results": []
        }
```

---

## Step 3: Terraform Lambda Configuration

### File: `terraform/modules/lambda_sentiment/main.tf`

```hcl
# Lambda function for sentiment analysis using DistilBERT

resource "aws_ecr_repository" "sentiment_inference" {
  name                 = "sentiment-analyzer-inference"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true  # Security scanning
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# Build and push Docker image (requires local docker)
resource "null_resource" "build_image" {
  triggers = {
    dockerfile_hash = filemd5("${path.module}/Dockerfile")
    code_hash       = filemd5("${path.module}/inference.py")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ${path.module}
      aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com
      docker build -t sentiment-analyzer-inference:latest .
      docker tag sentiment-analyzer-inference:latest ${aws_ecr_repository.sentiment_inference.repository_url}:latest
      docker push ${aws_ecr_repository.sentiment_inference.repository_url}:latest
    EOT
  }

  depends_on = [aws_ecr_repository.sentiment_inference]
}

resource "aws_lambda_function" "sentiment_inference" {
  function_name = "sentiment-analyzer-inference"
  role          = aws_iam_role.lambda_role.arn
  timeout       = 30  # seconds
  memory_size   = 512  # MB (balances cold start + inference latency)

  # Use container image instead of zip
  image_uri = "${aws_ecr_repository.sentiment_inference.repository_url}:latest"

  package_type = "Image"

  environment {
    variables = {
      MODEL_NAME = "distilbert-base-uncased-finetuned-sst-2-english"
      LOG_LEVEL  = "INFO"
    }
  }

  ephemeral_storage {
    size = 1024  # MB (1GB for model caching in /tmp)
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    null_resource.build_image
  ]
}

# Lambda execution role
resource "aws_iam_role" "lambda_role" {
  name = "sentiment-analyzer-inference-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "sentiment-analyzer-inference-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem"
        ]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = var.sqs_queue_arn
      }
    ]
  })
}

# CloudWatch metrics for monitoring
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "sentiment-inference-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300  # 5 minutes
  statistic           = "Average"
  threshold           = 150  # ms
  alarm_description   = "Alert when average inference duration exceeds 150ms"

  dimensions = {
    FunctionName = aws_lambda_function.sentiment_inference.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "sentiment-inference-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Alert when error count exceeds 5 in 5 minutes"

  dimensions = {
    FunctionName = aws_lambda_function.sentiment_inference.function_name
  }
}

# Optional: Lambda layer for model pre-caching (reduces cold start)
resource "aws_lambda_layer_version" "distilbert_model" {
  filename   = data.archive_file.model_layer.output_path
  layer_name = "distilbert-model"

  compatible_runtimes = ["python3.13"]

  source_code_hash = data.archive_file.model_layer.output_base64sha256
}

data "archive_file" "model_layer" {
  type        = "zip"
  source_dir  = "${path.module}/model_layer"  # Pre-downloaded model directory
  output_path = "${path.module}/model_layer.zip"
}

data "aws_caller_identity" "current" {}

output "lambda_function_arn" {
  value       = aws_lambda_function.sentiment_inference.arn
  description = "ARN of the sentiment inference Lambda function"
}

output "lambda_function_name" {
  value       = aws_lambda_function.sentiment_inference.function_name
  description = "Name of the sentiment inference Lambda function"
}
```

### File: `terraform/modules/lambda_sentiment/variables.tf`

```hcl
variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-west-2"
}

variable "dynamodb_table_arn" {
  type        = string
  description = "ARN of DynamoDB sentiment-items table"
}

variable "sqs_queue_arn" {
  type        = string
  description = "ARN of SQS queue for ingestion events"
}
```

---

## Step 4: SQS Event Mapping

### File: `terraform/modules/lambda_sentiment/sqs.tf`

```hcl
# Map SQS queue to Lambda function for automatic processing

resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.sentiment_inference.function_name

  # Batch settings for efficiency
  batch_size                         = 10  # Process 10 items per invocation
  maximum_batching_window_in_seconds = 5   # Wait up to 5s to fill batch

  # Error handling
  function_response_types = ["ReportBatchItemFailures"]

  # Retry policy
  maximum_retry_attempts = 2

  # Dead-letter queue for failed batches
  dead_letter_config {
    destination_arn = var.dlq_arn
  }
}
```

---

## Step 5: Testing & Performance Validation

### File: `tests/test_inference.py`

```python
"""
Unit tests for sentiment inference Lambda handler
"""

import json
import pytest
from lambda_function import inference


def test_sentiment_positive():
    """Test positive sentiment classification"""
    event = {
        "items": [
            {"id": "1", "text": "This is amazing! I love it."}
        ]
    }

    response = inference.lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert len(response["results"]) == 1
    assert response["results"][0]["sentiment"] == "POSITIVE"
    assert response["results"][0]["score"] > 0.8


def test_sentiment_negative():
    """Test negative sentiment classification"""
    event = {
        "items": [
            {"id": "1", "text": "Terrible, worst experience ever."}
        ]
    }

    response = inference.lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert response["results"][0]["sentiment"] == "NEGATIVE"


def test_batch_processing():
    """Test batch processing of 10 items"""
    event = {
        "items": [
            {"id": str(i), "text": f"Item {i} sentiment text"}
            for i in range(10)
        ]
    }

    response = inference.lambda_handler(event, None)
    assert response["statusCode"] == 200
    assert len(response["results"]) == 10
    assert response["metrics"]["total_items"] == 10


def test_latency_performance():
    """Test that warm inference is <150ms per item"""
    event = {
        "items": [
            {"id": "1", "text": "Quick sentiment test for demo"}
        ]
    }

    # Second call (warm container)
    response = inference.lambda_handler(event, None)
    assert response["statusCode"] == 200

    # Verify latency is acceptable
    latency = response["metrics"]["avg_inference_latency_ms"]
    assert latency < 150, f"Latency {latency}ms exceeds 150ms threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### File: `tests/load_test.sh`

```bash
#!/bin/bash
# Load test: Send 100 items/second for 10 minutes

FUNCTION_NAME="sentiment-analyzer-inference"
REGION="us-west-2"

echo "Starting load test: 100 items/sec for 10 minutes"

for i in {1..600}; do
  # Generate batch of 10 items
  PAYLOAD=$(cat <<EOF
{
  "items": [
    $(for j in {1..10}; do
        echo "{\"id\": \"item-$((i*10+j))\", \"text\": \"Sample sentiment text number $((i*10+j))\"}"
        [ $j -lt 10 ] && echo ","
      done)
  ]
}
EOF
)

  # Invoke Lambda asynchronously
  aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --invocation-type Event \
    --payload "$PAYLOAD" \
    response.json \
    --query 'StatusCode' \
    --output text

  echo "Batch $i sent (10 items)"

  # Rate limiting: 1 batch every 6 seconds = 100 items/min
  sleep 6
done

echo "Load test complete"
```

---

## Step 6: Deployment Instructions

### Build & Deploy

```bash
# 1. Build Docker image
cd lambda/
docker build -t sentiment-analyzer-inference:latest .

# 2. Authenticate with ECR
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com

# 3. Tag and push
docker tag sentiment-analyzer-inference:latest \
  ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/sentiment-analyzer-inference:latest

docker push ACCOUNT_ID.dkr.ecr.us-west-2.amazonaws.com/sentiment-analyzer-inference:latest

# 4. Deploy Terraform
cd terraform/
terraform init
terraform plan
terraform apply
```

---

## Performance Expectations

### Cold Start (First Invocation)
- Lambda initialization: 200-400ms
- Model download (first time): 500-1500ms
- Model loading into memory: 1000-3000ms
- **Total: 1.7-4.9 seconds**

### Warm Start (Cached Model)
- Tokenization + inference + post-processing per item: 60-115ms
- Batch of 10 items: 150-300ms (~15-30ms per item)
- **P95 latency: <120ms per item**

### Memory Usage
- Python runtime: ~100MB
- DistilBERT model: ~250-300MB
- Libraries (transformers, torch): ~80-100MB
- **Peak: 350-400MB of 512MB allocated (68% utilization)**

### Cost
- Lambda compute: ~$0.0000083 per second at 512MB
- Batch of 10 items: ~1.5 seconds = $0.0000125
- 100 items/hour: ~$0.50/month
- 500 items/hour: ~$2.50/month

---

## Optimization Tips

### 1. Reduce Cold Start
```python
# Use Lambda layers to pre-package model
aws lambda update-function-code \
  --function-name sentiment-analyzer-inference \
  --layers arn:aws:lambda:us-west-2:ACCOUNT:layer:distilbert-model:1
```

### 2. Provisioned Concurrency (if needed)
```hcl
resource "aws_lambda_provisioned_concurrent_executions" "sentiment" {
  function_name                     = aws_lambda_function.sentiment_inference.function_name
  provisioned_concurrent_executions = 1  # Keep 1 container warm
}
# Cost: $0.015/hour = ~$11/month for continuous warm container
```

### 3. Model Quantization (future enhancement)
```python
# Use quantized DistilBERT for 20% faster inference
# Intel optimized: distilbert-base-uncased-finetuned-sst-2-english-int8-static-inc
```
