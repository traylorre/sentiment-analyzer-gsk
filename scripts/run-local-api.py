#!/usr/bin/env python3
"""
Local development server for the Dashboard API.

This script runs the Powertools-based Lambda handler locally using a simple
HTTP server, allowing frontend E2E tests to run without deploying to AWS.

Usage:
    python scripts/run-local-api.py

    Or with custom port:
    PORT=8000 python scripts/run-local-api.py

Environment Variables:
    PORT: Server port (default: 8000)
    ENVIRONMENT: Environment name (default: local)

The server uses mock DynamoDB tables via moto for local development.
This enables full API functionality without AWS credentials.

API Keys:
    Loads from .env.local if available:
    - TIINGO_API_KEY: For OHLC price data
    - FINNHUB_API_KEY: For intraday data
"""

import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Configure logging before other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_env_file(env_path: Path) -> dict:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


# Load API keys from .env.local if available
# This is at the repo root, not the scripts directory
repo_root = Path(__file__).parent.parent
env_local_path = repo_root / ".env.local"
env_vars = load_env_file(env_local_path)

if env_vars:
    logger.info(f"Loaded {len(env_vars)} variables from .env.local")
    for key in ["TIINGO_API_KEY", "FINNHUB_API_KEY"]:
        if key in env_vars:
            os.environ.setdefault(key, env_vars[key])
            logger.info(f"  {key}: configured")

# Set environment variables BEFORE importing the handler
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("USERS_TABLE", "local-users")
os.environ.setdefault("SENTIMENTS_TABLE", "local-sentiments")
os.environ.setdefault("CHAOS_EXPERIMENTS_TABLE", "local-chaos")
os.environ.setdefault("OHLC_CACHE_TABLE", "local-ohlc-cache")  # CACHE-001
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("CLOUD_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

# Disable X-Ray tracing for local development
os.environ.setdefault("AWS_XRAY_SDK_ENABLED", "false")


def create_mock_tables():
    """Create mock DynamoDB tables using moto."""
    import boto3
    from moto import mock_aws

    # Start moto mock
    mock = mock_aws()
    mock.start()

    # Create mock DynamoDB client
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Create users table
    dynamodb.create_table(
        TableName="local-users",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create sentiments table
    dynamodb.create_table(
        TableName="local-sentiments",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # Create OHLC cache table (CACHE-001)
    dynamodb.create_table(
        TableName="local-ohlc-cache",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    logger.info(
        "Created mock DynamoDB tables: local-users, local-sentiments, local-ohlc-cache"
    )
    return mock


class _FakeLambdaContext:
    """Minimal Lambda context for local invocation."""

    function_name = "local-dashboard"
    memory_limit_in_mb = 512
    invoked_function_arn = (
        "arn:aws:lambda:us-east-1:000000000000:function:local-dashboard"
    )
    aws_request_id = "local-request-id"


class LambdaProxyHandler(BaseHTTPRequestHandler):
    """HTTP handler that translates requests to Lambda events."""

    def _build_event(self, method: str) -> dict:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length else None

        headers = {k.lower(): v for k, v in self.headers.items()}
        query_params = (
            {k: v[0] for k, v in parse_qs(parsed.query).items()}
            if parsed.query
            else None
        )

        return {
            "httpMethod": method,
            "path": parsed.path,
            "headers": headers,
            "queryStringParameters": query_params,
            "body": body,
            "isBase64Encoded": False,
            "requestContext": {
                "identity": {"sourceIp": "127.0.0.1"},
                "requestId": "local-request",
            },
        }

    def _invoke_handler(self, method: str) -> None:
        from src.lambdas.dashboard.handler import lambda_handler

        event = self._build_event(method)
        response = lambda_handler(event, _FakeLambdaContext())

        status_code = response.get("statusCode", 500)
        body = response.get("body", "")
        resp_headers = response.get("headers", {})

        self.send_response(status_code)

        # CORS headers for local development
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "*")

        for key, value in resp_headers.items():
            self.send_header(key, value)

        # Set-Cookie from multiValueHeaders
        for cookie in response.get("multiValueHeaders", {}).get("Set-Cookie", []):
            self.send_header("Set-Cookie", cookie)

        self.end_headers()
        if body:
            self.wfile.write(body.encode() if isinstance(body, str) else body)

    def do_GET(self):
        self._invoke_handler("GET")

    def do_POST(self):
        self._invoke_handler("POST")

    def do_PUT(self):
        self._invoke_handler("PUT")

    def do_DELETE(self):
        self._invoke_handler("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://localhost:3000")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


def main():
    """Run the local development server."""
    port = int(os.environ.get("PORT", "8000"))

    logger.info("Setting up mock AWS services...")
    mock = create_mock_tables()

    try:
        server = HTTPServer(("127.0.0.1", port), LambdaProxyHandler)
        logger.info(f"Starting local API server on http://localhost:{port}")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        logger.info(
            f"Ticker search: GET http://localhost:{port}/api/v2/tickers/search?q=AAPL"
        )
        logger.info("")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.server_close()
    finally:
        mock.stop()


if __name__ == "__main__":
    # Add src to path for imports
    src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, src_path)

    main()
