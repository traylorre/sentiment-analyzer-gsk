# SSE Streaming Lambda - Docker Image
# Custom Python runtime for RESPONSE_STREAM mode (chunked transfer encoding)
# Native Runtime API bootstrap for streaming responses
#
# Build context: src/ (allows importing from lambdas/ and lib/)
#
# Usage:
#   cd src && docker build -t sse-streaming -f lambdas/sse_streaming/Dockerfile .
#   docker run --rm sse-streaming python -c "from handler import handler; print('OK')"

# Stage 0: ADOT Lambda Extension binary (FR-062, FR-069, FR-070)
# Pin digest for reproducible builds in production
FROM public.ecr.aws/aws-observability/aws-otel-lambda-extension-amd64:latest AS adot

# Stage 1: Builder - install dependencies
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY lambdas/sse_streaming/requirements.txt .
RUN pip install --no-cache-dir --target /app/packages -r requirements.txt

# Stage 2: Runtime - minimal production image
FROM python:3.13-slim

# Create non-root user for security (090-security-first-burndown)
# UID 1000 is standard for Lambda containers
RUN adduser --disabled-password --gecos '' --uid 1000 lambda

WORKDIR /var/task

# Copy ADOT Lambda Extension collector binary (T031)
COPY --from=adot /opt/extensions/ /opt/extensions/

# Copy installed packages
COPY --from=builder /app/packages /var/task/packages

# Copy bootstrap (custom runtime entry point for RESPONSE_STREAM)
COPY lambdas/sse_streaming/bootstrap /var/task/bootstrap
RUN chmod +x /var/task/bootstrap

# Copy application code
COPY lambdas/sse_streaming /var/task

# Copy shared modules for logging utilities and models
# Structure: /var/task/src/lambdas/shared/
RUN mkdir -p /var/task/src/lambdas /var/task/src/lib && \
    touch /var/task/src/__init__.py /var/task/src/lambdas/__init__.py /var/task/src/lib/__init__.py
COPY lambdas/shared /var/task/src/lambdas/shared

# Copy lib/timeseries for Resolution and other models
COPY lib/timeseries /var/task/src/lib/timeseries

# Copy ADOT collector config (T032)
COPY lambdas/sse_streaming/collector-config.yaml /opt/collector-config/config.yaml

# Set Python path to include packages and app directories
ENV PYTHONPATH=/var/task/packages:/var/task

# ADOT Extension collector config path (T033)
ENV OPENTELEMETRY_COLLECTOR_CONFIG_FILE=/opt/collector-config/config.yaml

# Set ownership and switch to non-root user (090-security-first-burndown)
RUN chown -R lambda:lambda /var/task
USER lambda

# Custom runtime: bootstrap polls Runtime API and streams handler output
ENTRYPOINT ["python3", "/var/task/bootstrap"]
