"""Lambda direct invoke transport for E2E tests.

Replaces HTTP calls to Function URLs with boto3 lambda.invoke(),
bypassing CloudFront propagation delays that cause 404s in CI.

Usage:
    client = PreprodAPIClient(transport="invoke")

The transport constructs Function URL v2 events from HTTP request
parameters, invokes the Lambda via boto3, and returns an
httpx-compatible response object.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Lambda function names (default to preprod)
DASHBOARD_FUNCTION_NAME = os.environ.get(
    "DASHBOARD_FUNCTION_NAME", "preprod-sentiment-dashboard"
)
SSE_FUNCTION_NAME = os.environ.get(
    "SSE_FUNCTION_NAME", "preprod-sentiment-sse-streaming"
)
LAMBDA_QUALIFIER = os.environ.get("LAMBDA_QUALIFIER", "live")


@dataclass
class LambdaResponse:
    """httpx.Response-compatible object from Lambda invoke result."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    _json: Any = None

    def json(self) -> Any:
        if self._json is not None:
            return self._json
        return json.loads(self.text) if self.text else {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}: {self.text[:200]}")


def _build_function_url_event(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    query_params: dict[str, Any] | None = None,
) -> dict:
    """Build a Lambda Function URL v2 event from HTTP request parameters."""
    headers = headers or {}
    query_string = ""
    if query_params:
        from urllib.parse import urlencode

        query_string = urlencode(query_params, doseq=True)

    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": query_string,
        "headers": {k.lower(): v for k, v in headers.items()},
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "e2e-test",
            "domainName": "e2e-test.lambda-url.us-east-1.on.aws",
            "domainPrefix": "e2e-test",
            "http": {
                "method": method.upper(),
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "e2e-test-client",
            },
            "requestId": f"e2e-{method.lower()}-{path.replace('/', '-')}",
            "routeKey": "$default",
            "stage": "$default",
            "time": "01/Jan/2024:00:00:00 +0000",
            "timeEpoch": 1704067200000,
        },
        "body": body,
        "isBase64Encoded": False,
    }


def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response."""
    status_code = payload.get("statusCode", 500)
    headers = payload.get("headers", {})

    # Response body can be in 'body' field
    body = payload.get("body", "")
    if isinstance(body, dict):
        body = json.dumps(body)

    # Try to parse JSON for the _json field
    parsed_json = None
    if body:
        try:
            parsed_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass

    return LambdaResponse(
        status_code=status_code,
        headers=headers,
        text=body if isinstance(body, str) else json.dumps(body),
        _json=parsed_json,
    )


class LambdaInvokeTransport:
    """Invoke Lambda directly via boto3, bypassing Function URL CloudFront.

    Drop-in replacement for httpx-based requests in E2E tests.
    """

    def __init__(
        self,
        function_name: str = DASHBOARD_FUNCTION_NAME,
        qualifier: str = LAMBDA_QUALIFIER,
        region: str | None = None,
    ):
        self.function_name = function_name
        self.qualifier = qualifier
        self._client = boto3.client(
            "lambda", region_name=region or os.environ.get("AWS_REGION", "us-east-1")
        )

    def invoke(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> LambdaResponse:
        """Invoke Lambda and return an httpx-compatible response."""
        event = _build_function_url_event(method, path, headers, body, query_params)

        response = self._client.invoke(
            FunctionName=self.function_name,
            Qualifier=self.qualifier,
            InvocationType="RequestResponse",
            Payload=json.dumps(event),
        )

        # Check for function-level errors
        if "FunctionError" in response:
            error_payload = json.loads(response["Payload"].read())
            logger.error(
                "Lambda FunctionError: %s",
                error_payload.get("errorMessage", "unknown"),
            )
            return LambdaResponse(
                status_code=502,
                text=json.dumps(error_payload),
                _json=error_payload,
            )

        # Parse the Lambda response
        payload = json.loads(response["Payload"].read())
        return _parse_lambda_response(payload)
