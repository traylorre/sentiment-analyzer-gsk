# SSE Streaming Lambda - Docker Image
# Custom Python runtime for RESPONSE_STREAM mode (chunked transfer encoding)
# Native Runtime API bootstrap for streaming responses
#
# Build context: src/ (allows importing from lambdas/ and lib/)
#
# Usage:
#   cd src && docker build -t sse-streaming -f lambdas/sse_streaming/Dockerfile .
#   docker run --rm sse-streaming python -c "from handler import handler; print('OK')"

# ADOT Collector Extension (1220-xray-instrumentation-hardening FR-001)
# The ADOT Collector sidecar receives OTel spans on localhost:4318 (OTLP HTTP)
# and exports to X-Ray. Only the Collector Layer is needed (not the Python SDK
# Layer) because this Lambda manages its own OTel SDK (pinned in requirements.txt).
# The layer zip is downloaded in CI (deploy.yml) to lambdas/sse_streaming/adot-layer/.
# If the layer is absent, the COPY is skipped and tracing.py degrades gracefully
# (ECONNREFUSED caught, Powertools/Active mode traces still export via Lambda service).

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

# Set Python path to include packages and app directories
ENV PYTHONPATH=/var/task/packages:/var/task

# ADOT Collector Extension (1220-xray-instrumentation-hardening FR-001).
# CI downloads the layer to lambdas/sse_streaming/adot-layer/ before build.
# For local dev: mkdir -p src/lambdas/sse_streaming/adot-layer/{extensions,collector-config}
# Must remain root-owned; Lambda runtime invokes extensions as root.
COPY lambdas/sse_streaming/adot-layer/extensions/ /opt/extensions/
COPY lambdas/sse_streaming/adot-layer/collector-config/ /opt/collector-config/
RUN if [ -f /opt/extensions/collector ]; then \
      chmod +x /opt/extensions/collector && \
      echo "ADOT Collector Extension installed"; \
    fi

# Set ownership and switch to non-root user (090-security-first-burndown)
# NOTE: /opt/extensions/ intentionally NOT chowned - must remain root-owned
RUN chown -R lambda:lambda /var/task
USER lambda

# Custom runtime: bootstrap polls Runtime API and streams handler output
ENTRYPOINT ["python3", "/var/task/bootstrap"]
