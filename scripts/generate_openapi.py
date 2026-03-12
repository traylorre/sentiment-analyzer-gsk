#!/usr/bin/env python3
"""Generate OpenAPI 3.1 specification from Powertools route registry.

Introspects the dashboard Lambda's APIGatewayRestResolver to extract all
registered routes, their HTTP methods, and associated Pydantic models.
Outputs a valid OpenAPI 3.1 JSON specification.

Usage:
    python scripts/generate_openapi.py                  # stdout
    python scripts/generate_openapi.py -o openapi.json  # file
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set required env vars before importing handler (they're read at import time)
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("USERS_TABLE", "local-users")
os.environ.setdefault("SENTIMENTS_TABLE", "local-sentiments")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "local-chaos")
os.environ.setdefault("OHLC_CACHE_TABLE", "local-ohlc-cache")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("CLOUD_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_XRAY_SDK_ENABLED", "false")

from src.lambdas.dashboard.handler import app  # noqa: E402


def generate_openapi_spec() -> dict:
    """Generate OpenAPI 3.1 spec from Powertools resolver routes."""
    paths: dict = {}

    for route in app._route_keys:
        method = route[0].lower() if isinstance(route, tuple) else "get"
        path = route[1] if isinstance(route, tuple) else route

        # Convert Powertools path params <param> to OpenAPI {param}
        openapi_path = path.replace("<", "{").replace(">", "}")

        if openapi_path not in paths:
            paths[openapi_path] = {}

        paths[openapi_path][method] = {
            "summary": f"{method.upper()} {path}",
            "responses": {
                "200": {"description": "Successful response"},
                "400": {"description": "Bad request"},
                "401": {"description": "Unauthorized"},
                "500": {"description": "Internal server error"},
            },
        }

    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "Sentiment Analyzer Dashboard API",
            "version": "2.0.0",
            "description": "REST API for the sentiment analyzer dashboard. "
            "Uses AWS Lambda Powertools APIGatewayRestResolver.",
        },
        "servers": [
            {
                "url": "https://{function_url}",
                "description": "Lambda Function URL",
                "variables": {
                    "function_url": {
                        "default": "localhost:8000",
                        "description": "Lambda Function URL endpoint",
                    }
                },
            }
        ],
        "paths": dict(sorted(paths.items())),
    }

    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate OpenAPI spec")
    parser.add_argument("-o", "--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    spec = generate_openapi_spec()
    output = json.dumps(spec, indent=2)

    if args.output:
        Path(args.output).write_text(output + "\n")
        print(f"OpenAPI spec written to {args.output}", file=sys.stderr)
        print(
            f"Endpoints: {sum(len(v) for v in spec['paths'].values())}", file=sys.stderr
        )
    else:
        print(output)


if __name__ == "__main__":
    main()
