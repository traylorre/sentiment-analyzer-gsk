"""
CloudWatch Observability Tests for Preprod Environment

These tests validate that Lambda metrics and logs are being properly
generated and are queryable in CloudWatch. This ensures our monitoring
and alerting systems will work correctly.

CRITICAL: These tests require the Lambda warmup step to have run first.
If metrics are missing, the warmup step may have failed.

Test Debt Item: TD-001
Spec: 003-preprod-metrics-generation
"""

import os
from datetime import UTC, datetime, timedelta

import boto3
import pytest


@pytest.fixture(scope="module")
def cloudwatch_client():
    """Create CloudWatch client for preprod region."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("cloudwatch", region_name=region)


@pytest.fixture(scope="module")
def logs_client():
    """Create CloudWatch Logs client for preprod region."""
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("logs", region_name=region)


@pytest.fixture(scope="module")
def environment():
    """Get current environment."""
    return os.environ.get("ENVIRONMENT", "preprod")


class TestLambdaMetricsExist:
    """Verify Lambda metrics are being generated.

    These tests fail (not skip) when metrics are missing because
    the CI warmup step should guarantee metrics exist.
    """

    def test_dashboard_lambda_invocation_metrics(self, cloudwatch_client, environment):
        """Verify dashboard Lambda has invocation metrics."""
        function_name = f"{environment}-sentiment-dashboard"

        response = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=datetime.now(UTC) - timedelta(hours=1),
            EndTime=datetime.now(UTC),
            Period=300,
            Statistics=["Sum"],
        )

        datapoints = response.get("Datapoints", [])
        assert datapoints, (
            f"No invocation metrics found for {function_name} in last hour. "
            f"The CI warmup step should have generated metrics. "
            f"Check the 'Warm Up Lambdas' step in deploy.yml."
        )

        total_invocations = sum(dp["Sum"] for dp in datapoints)
        assert total_invocations > 0, (
            f"Zero invocations recorded for {function_name}. "
            f"Warmup step may have failed."
        )

    def test_dashboard_lambda_duration_metrics(self, cloudwatch_client, environment):
        """Verify dashboard Lambda has duration metrics."""
        function_name = f"{environment}-sentiment-dashboard"

        response = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Duration",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=datetime.now(UTC) - timedelta(hours=1),
            EndTime=datetime.now(UTC),
            Period=300,
            Statistics=["Average", "Maximum"],
        )

        datapoints = response.get("Datapoints", [])
        assert datapoints, (
            f"No duration metrics found for {function_name}. "
            f"This indicates the Lambda hasn't been invoked."
        )

    def test_dashboard_lambda_error_rate(self, cloudwatch_client, environment):
        """Verify dashboard Lambda error rate is acceptable."""
        function_name = f"{environment}-sentiment-dashboard"

        # Get invocations
        invocations_response = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Invocations",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=datetime.now(UTC) - timedelta(hours=1),
            EndTime=datetime.now(UTC),
            Period=3600,
            Statistics=["Sum"],
        )

        # Get errors
        errors_response = cloudwatch_client.get_metric_statistics(
            Namespace="AWS/Lambda",
            MetricName="Errors",
            Dimensions=[{"Name": "FunctionName", "Value": function_name}],
            StartTime=datetime.now(UTC) - timedelta(hours=1),
            EndTime=datetime.now(UTC),
            Period=3600,
            Statistics=["Sum"],
        )

        invocation_datapoints = invocations_response.get("Datapoints", [])
        error_datapoints = errors_response.get("Datapoints", [])

        if not invocation_datapoints:
            pytest.fail(
                f"No invocation metrics for {function_name}. "
                f"Cannot calculate error rate without invocations."
            )

        total_invocations = sum(dp["Sum"] for dp in invocation_datapoints)
        total_errors = (
            sum(dp["Sum"] for dp in error_datapoints) if error_datapoints else 0
        )

        if total_invocations > 0:
            error_rate = (total_errors / total_invocations) * 100
            assert error_rate < 10, (
                f"Error rate {error_rate:.1f}% exceeds 10% threshold. "
                f"Errors: {total_errors}, Invocations: {total_invocations}"
            )


class TestCloudWatchLogsExist:
    """Verify CloudWatch Log Groups exist and have recent events."""

    def test_dashboard_log_group_exists(self, logs_client, environment):
        """Verify dashboard Lambda log group exists."""
        log_group_name = f"/aws/lambda/{environment}-sentiment-dashboard"

        try:
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_name, limit=1
            )
            log_groups = response.get("logGroups", [])
            assert log_groups, f"Log group {log_group_name} not found"
        except logs_client.exceptions.ResourceNotFoundException:
            pytest.fail(f"Log group {log_group_name} does not exist")

    def test_dashboard_has_recent_logs(self, logs_client, environment):
        """Verify dashboard Lambda has recent log events."""
        log_group_name = f"/aws/lambda/{environment}-sentiment-dashboard"

        try:
            # Get log streams from last hour
            response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy="LastEventTime",
                descending=True,
                limit=5,
            )

            streams = response.get("logStreams", [])
            assert streams, (
                f"No log streams found in {log_group_name}. "
                f"Lambda may not have been invoked."
            )

            # Check most recent stream has events from last hour
            most_recent = streams[0]
            last_event_time = most_recent.get("lastEventTimestamp", 0)

            if last_event_time:
                last_event_dt = datetime.fromtimestamp(last_event_time / 1000, tz=UTC)
                age = datetime.now(UTC) - last_event_dt

                assert age < timedelta(hours=1), (
                    f"Most recent log event is {age} old. "
                    f"Expected logs from last hour."
                )

        except logs_client.exceptions.ResourceNotFoundException:
            pytest.fail(f"Log group {log_group_name} does not exist")


class TestMetricAlarms:
    """Verify CloudWatch alarms are configured (optional)."""

    def test_alarm_exists_for_errors(self, cloudwatch_client, environment):
        """Check if error alarm exists (informational)."""
        response = cloudwatch_client.describe_alarms(
            AlarmNamePrefix=f"{environment}-sentiment",
            MaxRecords=10,
        )

        alarms = response.get("MetricAlarms", [])
        # This is informational - we don't fail if no alarms exist
        if not alarms:
            print(f"INFO: No CloudWatch alarms configured for {environment}")
        else:
            print(f"Found {len(alarms)} alarms: {[a['AlarmName'] for a in alarms]}")

        # Always pass - this is just informational
        assert True
