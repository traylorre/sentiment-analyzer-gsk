"""Lambda direct invoke transport for E2E tests.

Replaces HTTP calls to API Gateway with boto3 lambda.invoke(),
bypassing network latency while preserving production event format.

Usage:
    client = PreprodAPIClient(transport="invoke")

Feature 1297: The transport constructs API Gateway REST v1 events from
HTTP request parameters, invokes the Lambda via boto3, and returns an
httpx-compatible response object. This matches the production path
(API Gateway → lambda:InvokeFunction → v1 events).
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlencode

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


def _build_apigw_rest_event(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | None = None,
    query_params: dict[str, Any] | None = None,
) -> dict:
    """Build an API Gateway REST v1 proxy event from HTTP request parameters.

    Feature 1297: Matches the production event format (API Gateway REST → Lambda).
    Previously built Function URL v2 events which bypassed security layers.
    """
    headers = headers or {}
    lowered_headers = {k.lower(): v for k, v in headers.items()}
    query_string_params = None
    if query_params:
        query_string = urlencode(query_params, doseq=True)
        query_string_params = {
            k: v[-1] if len(v) == 1 else ",".join(v)
            for k, v in parse_qs(query_string).items()
        }

    path_params = {"proxy": path.lstrip("/")} if path != "/" else None

    return {
        "resource": "/{proxy+}" if path != "/" else "/",
        "path": path,
        "httpMethod": method.upper(),
        "headers": lowered_headers,
        "multiValueHeaders": {k: [v] for k, v in lowered_headers.items()},
        "queryStringParameters": query_string_params,
        "multiValueQueryStringParameters": (
            {k: [v] for k, v in query_string_params.items()}
            if query_string_params
            else None
        ),
        "pathParameters": path_params,
        "stageVariables": None,
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "e2e-test",
            "resourceId": "e2e-test",
            "resourcePath": "/{proxy+}" if path != "/" else "/",
            "httpMethod": method.upper(),
            "path": f"/v1{path}",
            "stage": "v1",
            "requestId": f"e2e-{method.lower()}-{path.replace('/', '-')}",
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": "e2e-test-client",
            },
            "time": "01/Jan/2024:00:00:00 +0000",
            "timeEpoch": 1704067200000,
        },
    }


def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response."""
    status_code = payload.get("statusCode", 500)
    raw_headers = payload.get("headers", {})
    # Normalize header keys to lowercase (matching httpx.Response behavior)
    headers = {k.lower(): v for k, v in raw_headers.items()}

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
        event = _build_apigw_rest_event(method, path, headers, body, query_params)

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
