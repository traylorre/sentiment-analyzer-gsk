# Dashboard Lambda - Docker Image
# Powertools APIGatewayRestResolver for serving dashboard UI and API endpoints
# Feature 1036: Container-based deployment to fix pydantic binary incompatibility
#
# Build context: src/ (allows importing from lambdas/ and lib/)
# This allows importing from shared modules and lib
#
# Usage:
#   cd src && docker build -t dashboard-lambda -f lambdas/dashboard/Dockerfile .
#   docker run --rm dashboard-lambda python -c "from handler import lambda_handler; print('OK')"

# Stage 1: Builder - install dependencies
FROM public.ecr.aws/lambda/python:3.13 AS builder

WORKDIR /var/task

# Copy requirements and install dependencies
# Using --target to install to Lambda's expected location
COPY lambdas/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t /var/task/

# Stage 2: Runtime - minimal production image
FROM public.ecr.aws/lambda/python:3.13

WORKDIR /var/task

# Copy installed packages from builder
COPY --from=builder /var/task /var/task

# Copy application code
# handler.py must be at root for Lambda handler config "handler.lambda_handler"
COPY lambdas/dashboard/*.py ./

# Create package structure for internal imports (from src.lambdas.dashboard...)
RUN mkdir -p /var/task/src/lambdas/dashboard && \
    touch /var/task/src/__init__.py /var/task/src/lambdas/__init__.py /var/task/src/lambdas/dashboard/__init__.py

# Copy dashboard code to src/lambdas/dashboard for internal imports
COPY lambdas/dashboard/*.py /var/task/src/lambdas/dashboard/

# Copy shared modules for logging, models, utilities
COPY lambdas/shared /var/task/src/lambdas/shared

# Copy lib modules for timeseries
RUN mkdir -p /var/task/src/lib && \
    touch /var/task/src/lib/__init__.py
COPY lib /var/task/src/lib

# Copy static dashboard files for serving
COPY dashboard /var/task/src/dashboard

# Set Python path to find all modules
ENV PYTHONPATH=/var/task

# Lambda handler configuration
CMD ["handler.lambda_handler"]
