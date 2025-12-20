# Analysis Lambda - Docker Image
# Deploys PyTorch + Transformers for DistilBERT sentiment inference
# ADR-005 Phase 2: Container image deployment
#
# Build context: src/ (allows importing from lambdas/ and lib/)
# This allows importing from shared modules and lib
#
# Usage:
#   cd src && docker build -t analysis-lambda -f lambdas/analysis/Dockerfile .
#   docker run --rm analysis-lambda python -c "from handler import lambda_handler; print('OK')"

# Stage 1: Builder - install dependencies
FROM public.ecr.aws/lambda/python:3.13 AS builder

WORKDIR /var/task

# Copy requirements and install dependencies
# Using --target to install to Lambda's expected location
COPY lambdas/analysis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /var/task/

# Stage 2: Runtime - minimal production image
FROM public.ecr.aws/lambda/python:3.13

WORKDIR /var/task

# Copy installed packages from builder
COPY --from=builder /var/task /var/task

# Copy application code
# handler.py must be at root for Lambda handler config "handler.lambda_handler"
COPY lambdas/analysis/*.py ./

# Create package structure for internal imports (from src.lambdas.analysis...)
RUN mkdir -p /var/task/src/lambdas/analysis && \
    touch /var/task/src/__init__.py /var/task/src/lambdas/__init__.py /var/task/src/lambdas/analysis/__init__.py

# Copy analysis code to src/lambdas/analysis for internal imports
COPY lambdas/analysis/*.py /var/task/src/lambdas/analysis/

# Copy shared modules for logging, models, utilities
COPY lambdas/shared /var/task/src/lambdas/shared

# Copy lib modules for metrics
RUN mkdir -p /var/task/src/lib && \
    touch /var/task/src/lib/__init__.py
COPY lib /var/task/src/lib

# Set Python path to find all modules
ENV PYTHONPATH=/var/task

# Lambda handler configuration
CMD ["handler.lambda_handler"]
