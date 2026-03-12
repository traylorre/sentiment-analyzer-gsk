#!/usr/bin/env python3
"""
Local development server for the Dashboard API.

This script runs the FastAPI application locally with uvicorn, allowing
frontend E2E tests to run without deploying to AWS.

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
from pathlib import Path

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
# These are required by the FastAPI app
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
    # Matches production schema from infrastructure/terraform/modules/dynamodb/main.tf
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


def main():
    """Run the local development server."""
    port = int(os.environ.get("PORT", "8000"))

    logger.info("Setting up mock AWS services...")
    mock = create_mock_tables()

    try:
        # Import uvicorn here to avoid issues with moto patching
        import uvicorn
        from fastapi.middleware.cors import CORSMiddleware

        # Import the FastAPI app after moto is started
        # This ensures DynamoDB calls use the mock
        from src.lambdas.dashboard.handler import app

        # Add CORS middleware for local development
        # In production, CORS is handled by Lambda Function URL
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],  # Next.js dev server
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("Added CORS middleware for local development")

        logger.info(f"Starting local API server on http://localhost:{port}")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        logger.info(
            "Ticker search endpoint: GET http://localhost:{port}/api/v2/tickers/search?q=AAPL"
        )
        logger.info("Health check: GET http://localhost:{port}/health")
        logger.info("")

        # Run the server
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="info",
            access_log=True,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        mock.stop()


if __name__ == "__main__":
    # Add src to path for imports
    src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, src_path)

    main()
