"""Tests for retry module."""

from botocore.exceptions import ClientError

from src.lambdas.shared.retry import (
    _is_dynamodb_retryable,
    _is_s3_retryable,
)


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "op")


class TestIsDynamodbRetryable:
    """Tests for _is_dynamodb_retryable."""

    def test_retryable_error(self):
        assert _is_dynamodb_retryable(_make_client_error("ThrottlingException"))

    def test_non_retryable_error(self):
        assert not _is_dynamodb_retryable(_make_client_error("ValidationException"))

    def test_non_client_error(self):
        assert not _is_dynamodb_retryable(ValueError("not a client error"))


class TestIsS3Retryable:
    """Tests for _is_s3_retryable."""

    def test_retryable_error(self):
        assert _is_s3_retryable(_make_client_error("SlowDown"))

    def test_non_retryable_error(self):
        assert not _is_s3_retryable(_make_client_error("NoSuchBucket"))

    def test_non_client_error(self):
        assert not _is_s3_retryable(RuntimeError("not a client error"))
