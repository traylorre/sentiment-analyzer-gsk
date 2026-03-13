"""Unit tests for X-Ray Canary Lambda Handler."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


@pytest.fixture(autouse=True)
def _canary_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("POWERTOOLS_TRACE_DISABLED", "true")
    monkeypatch.setenv("_X_AMZN_TRACE_ID", "1-abc-def123")


@pytest.fixture
def xray_client():
    return MagicMock()


@pytest.fixture
def cloudwatch_client():
    return MagicMock()


class TestHandler:
    def test_healthy_canary(self, xray_client, cloudwatch_client, monkeypatch):
        xray_client.get_trace_summaries.return_value = {
            "TraceSummaries": [
                {"TraceId": "1-abc-def", "IsPartial": False},
                {"TraceId": "1-abc-ghi", "IsPartial": False},
            ]
        }

        with patch("boto3.client") as mock_boto:
            mock_boto.side_effect = lambda svc, **kw: (
                xray_client if svc == "xray" else cloudwatch_client
            )
            from src.lambdas.canary.handler import handler

            result = handler({}, MagicMock())

        assert result["status"] == "HEALTHY"
        assert result["completeness_ratio"] == 1.0
        assert "trace_id" in result
        cloudwatch_client.put_metric_data.assert_called_once()

    def test_degraded_when_partial_traces(self, xray_client, cloudwatch_client):
        xray_client.get_trace_summaries.return_value = {
            "TraceSummaries": [
                {"TraceId": "1-abc-def", "IsPartial": True},
                {"TraceId": "1-abc-ghi", "IsPartial": True},
            ]
        }

        with patch("boto3.client") as mock_boto:
            mock_boto.side_effect = lambda svc, **kw: (
                xray_client if svc == "xray" else cloudwatch_client
            )
            from src.lambdas.canary.handler import handler

            result = handler({}, MagicMock())

        assert result["status"] == "DEGRADED"
        assert result["completeness_ratio"] == 0.0


class TestSubmitTestTrace:
    def test_returns_trace_id(self, monkeypatch):
        monkeypatch.setenv("_X_AMZN_TRACE_ID", "1-test-trace")
        from src.lambdas.canary.handler import _submit_test_trace

        trace_id = _submit_test_trace(MagicMock())
        assert trace_id == "1-test-trace"


class TestVerifyTraceIngestion:
    def test_returns_ratio_on_first_attempt(self, xray_client):
        xray_client.get_trace_summaries.return_value = {
            "TraceSummaries": [
                {"TraceId": "1-a", "IsPartial": False},
                {"TraceId": "1-b", "IsPartial": True},
            ]
        }
        from src.lambdas.canary.handler import _verify_trace_ingestion

        ratio = _verify_trace_ingestion(xray_client, "1-a")
        assert ratio == 0.5

    def test_returns_zero_when_no_traces_after_retries(self, xray_client):
        xray_client.get_trace_summaries.return_value = {"TraceSummaries": []}
        from src.lambdas.canary.handler import _verify_trace_ingestion

        with patch("src.lambdas.canary.handler.RETRY_DELAYS", [0, 0, 0]):
            ratio = _verify_trace_ingestion(xray_client, "1-x")
        assert ratio == 0.0
        assert xray_client.get_trace_summaries.call_count == 3

    def test_returns_zero_on_client_error_after_retries(self, xray_client):
        xray_client.get_trace_summaries.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "fail"}}, "GetTraceSummaries"
        )
        from src.lambdas.canary.handler import _verify_trace_ingestion

        with patch("src.lambdas.canary.handler.RETRY_DELAYS", [0, 0, 0]):
            ratio = _verify_trace_ingestion(xray_client, "1-x")
        assert ratio == 0.0


class TestEmitMetrics:
    def test_emits_health_and_completeness(self, cloudwatch_client):
        from src.lambdas.canary.handler import _emit_metrics

        _emit_metrics(cloudwatch_client, 1, 0.98)
        call_args = cloudwatch_client.put_metric_data.call_args
        metric_data = call_args.kwargs["MetricData"]
        names = {m["MetricName"] for m in metric_data}
        assert names == {"CanaryHealth", "completeness_ratio"}

    def test_handles_client_error_gracefully(self, cloudwatch_client):
        cloudwatch_client.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "fail"}}, "PutMetricData"
        )
        from src.lambdas.canary.handler import _emit_metrics

        # Should not raise
        _emit_metrics(cloudwatch_client, 0, 0.0)
