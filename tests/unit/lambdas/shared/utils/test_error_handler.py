"""Tests for error_handler module."""

import orjson
from pydantic import BaseModel

from src.lambdas.shared.utils.error_handler import handle_request


class StrictModel(BaseModel):
    name: str
    age: int


class TestHandleRequest:
    """Tests for handle_request."""

    def test_success_passthrough(self):
        """Handler return value is passed through."""

        def handler(event, context):
            return {"statusCode": 200, "body": "ok"}

        result = handle_request(handler, {"path": "/test", "httpMethod": "GET"}, None)
        assert result["statusCode"] == 200

    def test_validation_error_returns_422(self):
        """Pydantic ValidationError produces 422."""

        def handler(event, context):
            StrictModel(name=123, age="not_int")  # type: ignore[arg-type]

        result = handle_request(handler, {"path": "/test", "httpMethod": "POST"}, None)
        assert result.status_code == 422
        body = orjson.loads(result.body)
        assert "detail" in body

    def test_generic_exception_returns_500(self):
        """Unhandled exceptions produce 500."""

        def handler(event, context):
            raise RuntimeError("boom")

        result = handle_request(handler, {"path": "/test", "httpMethod": "GET"}, None)
        assert result.status_code == 500
        body = orjson.loads(result.body)
        assert body["detail"] == "Internal server error"

    def test_generic_exception_with_missing_event_keys(self):
        """Handler works even with minimal event dict."""

        def handler(event, context):
            raise ValueError("bad")

        result = handle_request(handler, {}, None)
        assert result.status_code == 500
