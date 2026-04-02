"""Unit tests for _parse_lambda_response() multiValueHeaders support (Feature 1306).

Verifies that the Lambda invoke transport correctly handles both
API Gateway REST v1 (multiValueHeaders) and v2 (headers) response formats.
"""

from tests.e2e.helpers.lambda_invoke_transport import _parse_lambda_response


class TestParseMultiValueHeaders:
    """Tests for multiValueHeaders extraction in _parse_lambda_response."""

    def test_multivalue_headers_only(self):
        """Production case: Lambda returns only multiValueHeaders (v1 format)."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Type": ["application/json"]},
            "body": "{}",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "application/json"

    def test_headers_only_v2(self):
        """V2 format: Lambda returns only headers."""
        payload = {
            "statusCode": 200,
            "headers": {"content-type": "text/html"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_both_present_multivalue_wins(self):
        """When both present, multiValueHeaders takes precedence."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Type": ["text/html"]},
            "headers": {"content-type": "application/json"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_empty_list_skipped(self):
        """Empty list values should not produce headers."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Empty": [], "Content-Type": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-empty" not in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_none_in_list_skipped(self):
        """None values in list should be filtered, taking first non-None."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Val": [None, "good"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["x-val"] == "good"

    def test_all_none_list_skipped(self):
        """List with only None values should be treated as empty."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Val": [None]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-val" not in response.headers

    def test_none_value_not_list_skipped(self):
        """None as entire value (not in a list) should be skipped."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Null": None, "Content-Type": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-null" not in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_mv_headers_none_falls_back_to_headers(self):
        """When multiValueHeaders is None, fall back to headers."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": None,
            "headers": {"content-type": "text/html"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_neither_present(self):
        """When neither headers nor multiValueHeaders present, headers is empty."""
        payload = {"statusCode": 200, "body": "{}"}
        response = _parse_lambda_response(payload)
        assert response.headers == {}

    def test_keys_lowercased(self):
        """All header keys should be normalized to lowercase."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-TYPE": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_int_value_coerced_to_string(self):
        """Non-string values in lists should be coerced to strings."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Length": [42]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-length"] == "42"

    def test_empty_dict_mv_headers_falls_back(self):
        """Empty dict multiValueHeaders should fall back to headers."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {},
            "headers": {"content-type": "application/json"},
            "body": "{}",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "application/json"
