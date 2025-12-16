# SSE Streaming Lambda - Docker Image
# Uses AWS Lambda Web Adapter for RESPONSE_STREAM mode
#
# Build context: src/lambdas (parent directory)
# This allows importing from shared modules
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies from sse_streaming subdirectory
COPY sse_streaming/requirements.txt .
RUN pip install --no-cache-dir --target /app/packages -r requirements.txt

# Production image
FROM python:3.13-slim

# Create non-root user for security (090-security-first-burndown)
# UID 1000 is standard for Lambda containers
RUN adduser --disabled-password --gecos '' --uid 1000 lambda

WORKDIR /app

# Copy AWS Lambda Web Adapter extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/

# Copy installed packages
COPY --from=builder /app/packages /app/packages

# Copy application code from sse_streaming subdirectory
COPY sse_streaming /app

# Copy shared modules for logging utilities and models
# Structure: /app/src/lambdas/shared/
RUN mkdir -p /app/src/lambdas && \
    touch /app/src/__init__.py /app/src/lambdas/__init__.py
COPY shared /app/src/lambdas/shared

# Set Python path to include packages and app directories
# Both paths needed: /app/packages for pip dependencies, /app for src.lambdas.shared imports
# Note: Also set via Lambda env vars in Terraform as belt-and-suspenders
ENV PYTHONPATH=/app/packages:/app
ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM

# Expose port for Lambda Web Adapter
EXPOSE 8080

# Set ownership and switch to non-root user (090-security-first-burndown)
RUN chown -R lambda:lambda /app
USER lambda

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "handler:app", "--host", "0.0.0.0", "--port", "8080"]
