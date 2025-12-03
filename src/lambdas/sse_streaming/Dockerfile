# SSE Streaming Lambda - Docker Image
# Uses AWS Lambda Web Adapter for RESPONSE_STREAM mode
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --target /app/packages -r requirements.txt

# Production image
FROM python:3.13-slim

WORKDIR /app

# Copy AWS Lambda Web Adapter extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/

# Copy installed packages
COPY --from=builder /app/packages /app/packages

# Copy application code
COPY . .

# Set Python path to include packages
ENV PYTHONPATH=/app/packages:/app
ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM

# Expose port for Lambda Web Adapter
EXPOSE 8080

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8080"]
