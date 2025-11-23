# VS Code Devcontainer for Lambda Development

This devcontainer provides a consistent development environment with Docker support for building and testing Lambda container images locally.

## Features

- Python 3.13 (matches Lambda runtime)
- Docker-outside-of-Docker (access to host Docker daemon)
- AWS CLI pre-installed
- Lambda development extensions

## Quick Start

### 1. Open in VS Code

```bash
# Open project in VS Code
code .

# Command Palette (Cmd+Shift+P / Ctrl+Shift+P)
> Dev Containers: Reopen in Container
```

### 2. Test Analysis Lambda Container Locally

```bash
# Build container image
cd src/lambdas/analysis
docker build --platform linux/amd64 -t analysis-lambda:local .

# Run with Lambda Runtime Interface Emulator
docker run --rm \
  -p 9000:8080 \
  analysis-lambda:local

# In another terminal, invoke the function
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"Records":[{"Sns":{"Message":"{\"source_id\":\"test-123\",\"text_for_analysis\":\"This product is amazing!\"}"}}]}'
```

### 3. Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires AWS credentials)
pytest tests/integration/test_container_image_preprod.py -v

# Cold start benchmark (long-running)
pytest tests/integration/test_container_image_preprod.py -m benchmark -v
```

## Requirements

- VS Code with Dev Containers extension
- Docker Desktop running
- AWS credentials configured (for integration tests)

## Ports

- **9000**: Lambda Runtime Interface Emulator (local testing)
- **9001**: Additional Lambda instance (if needed)
