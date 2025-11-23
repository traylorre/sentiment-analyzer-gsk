"""
Integration Tests for Lambda Container Images (Preprod)
========================================================

P1 tests validating container image deployment and performance.

Based on AWS best practices and industry patterns:
- AWS Lambda Runtime Interface Client testing
- Container image type validation via Lambda API
- Cold start latency benchmarking

For On-Call Engineers:
    If these tests fail:
    1. Check Lambda configuration shows PackageType=Image
    2. Verify ECR image exists and is accessible
    3. Check cold start times in CloudWatch Logs (InitDuration metric)
    4. Review image size (must be < 10GB)

For Developers:
    Tests validate:
    - Lambda is using container image (not ZIP)
    - Image URI points to ECR repository
    - Cold start performance meets SLA (<5s)
    - Container initialization succeeds
"""

import os
import time

import boto3
import pytest

# Test configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "preprod")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
ANALYSIS_LAMBDA_NAME = f"{ENVIRONMENT}-sentiment-analysis"


@pytest.fixture(scope="module")
def lambda_client():
    """Create Lambda client for testing."""
    return boto3.client("lambda", region_name=AWS_REGION)


@pytest.fixture(scope="module")
def lambda_config(lambda_client):
    """Get Lambda function configuration."""
    response = lambda_client.get_function(FunctionName=ANALYSIS_LAMBDA_NAME)
    return response["Configuration"]


class TestContainerImageDeployment:
    """Validate Lambda is using container image (not ZIP package)."""

    def test_package_type_is_image(self, lambda_config):
        """
        Verify Lambda PackageType is 'Image' (not 'Zip').

        This confirms the container image deployment was successful.
        """
        package_type = lambda_config.get("PackageType")
        assert package_type == "Image", (
            f"Expected PackageType='Image', got '{package_type}'. "
            "Lambda may still be using ZIP package deployment."
        )

    def test_image_uri_is_ecr(self, lambda_client):
        """
        Verify ImageUri points to Amazon ECR repository.

        Expected format: {account}.dkr.ecr.{region}.amazonaws.com/{repo}:{tag}
        """
        response = lambda_client.get_function(FunctionName=ANALYSIS_LAMBDA_NAME)
        image_uri = response["Code"].get("ImageUri", "")

        assert "ecr" in image_uri, (
            f"ImageUri '{image_uri}' does not contain 'ecr'. "
            "Lambda should be using ECR container image."
        )
        assert ".amazonaws.com/" in image_uri, (
            f"ImageUri '{image_uri}' is not from AWS ECR. "
            "Expected format: {account}.dkr.ecr.{region}.amazonaws.com/..."
        )
        assert f"{ENVIRONMENT}-sentiment-analysis" in image_uri, (
            f"ImageUri '{image_uri}' does not match expected repository name. "
            f"Expected: {ENVIRONMENT}-sentiment-analysis"
        )

    def test_image_tag_is_git_sha(self, lambda_client):
        """
        Verify image tag is a git SHA (not 'latest').

        This ensures reproducible deployments and easy rollback.
        """
        response = lambda_client.get_function(FunctionName=ANALYSIS_LAMBDA_NAME)
        image_uri = response["Code"].get("ImageUri", "")

        # Extract tag from ImageUri (format: repo:tag)
        if ":" in image_uri:
            tag = image_uri.split(":")[-1]
            assert tag != "latest", (
                "Image tag is 'latest'. Use specific git SHA for production. "
                "This prevents deployment inconsistencies and rollback issues."
            )
            assert len(tag) == 7, (
                f"Image tag '{tag}' should be 7-char git SHA, got length {len(tag)}. "
                "Expected format: {repo}:a1b2c3d"
            )

    def test_no_layers_with_container_image(self, lambda_config):
        """
        Verify Lambda has no layers when using container images.

        Layers are incompatible with container image deployments.
        """
        layers = lambda_config.get("Layers", [])
        assert len(layers) == 0, (
            f"Container image Lambda should not have layers. Found {len(layers)} layers. "
            "Dependencies must be baked into the container image."
        )

    def test_handler_is_configured(self, lambda_config):
        """
        Verify handler is configured (required even for containers).

        Handler format: filename.function_name (e.g., handler.lambda_handler)
        """
        handler = lambda_config.get("Handler")
        assert handler is not None, "Handler is not configured"
        assert "." in handler, (
            f"Handler '{handler}' should be in format 'filename.function'. "
            "Even container images need handler specification."
        )


class TestColdStartPerformance:
    """
    Benchmark Lambda cold start latency.

    Based on AWS best practices for container image cold starts:
    - P50: < 2 seconds
    - P95: < 5 seconds
    - P99: < 10 seconds
    """

    @pytest.fixture(scope="class")
    def force_cold_start(self, lambda_client):
        """
        Force a cold start by updating function configuration.

        This creates a new container instance.
        """
        current_config = lambda_client.get_function_configuration(
            FunctionName=ANALYSIS_LAMBDA_NAME
        )
        current_timeout = current_config["Timeout"]

        # Update timeout to force new container (change back immediately)
        lambda_client.update_function_configuration(
            FunctionName=ANALYSIS_LAMBDA_NAME, Timeout=current_timeout + 1
        )

        # Wait for update to complete
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=ANALYSIS_LAMBDA_NAME)

        # Restore original timeout
        lambda_client.update_function_configuration(
            FunctionName=ANALYSIS_LAMBDA_NAME, Timeout=current_timeout
        )
        waiter.wait(FunctionName=ANALYSIS_LAMBDA_NAME)

        yield

    def test_cold_start_latency_single(self, lambda_client, force_cold_start):
        """
        Measure cold start latency for a single invocation.

        Validates container initialization time meets SLA.
        """
        # Create test event
        test_event = {
            "Records": [
                {
                    "Sns": {
                        "Message": '{"source_id": "test-cold-start", "text_for_analysis": "This is a test for cold start measurement."}'
                    }
                }
            ]
        }

        # Invoke Lambda and measure time
        start = time.time()
        response = lambda_client.invoke(
            FunctionName=ANALYSIS_LAMBDA_NAME,
            InvocationType="RequestResponse",
            LogType="Tail",  # Get execution logs
            Payload=bytes(str(test_event), "utf-8"),
        )
        elapsed_ms = (time.time() - start) * 1000

        # Check invocation succeeded
        assert (
            response["StatusCode"] == 200
        ), f"Lambda invocation failed with status {response['StatusCode']}"

        # Parse logs to extract InitDuration (cold start time)
        import base64

        log_result = base64.b64decode(response["LogResult"]).decode("utf-8")

        # Look for "Init Duration: X ms" in logs
        init_duration_ms = None
        for line in log_result.split("\n"):
            if "Init Duration:" in line:
                # Format: "Init Duration: 1234.56 ms"
                parts = line.split("Init Duration:")
                if len(parts) > 1:
                    duration_str = parts[1].strip().split(" ")[0]
                    init_duration_ms = float(duration_str)
                    break

        # Validate cold start time
        if init_duration_ms:
            print("\n✅ Cold Start Metrics:")
            print(f"   Init Duration: {init_duration_ms:.2f} ms")
            print(f"   Total Latency: {elapsed_ms:.2f} ms")

            assert init_duration_ms < 5000, (
                f"Cold start time {init_duration_ms:.2f}ms exceeds 5s SLA. "
                "Container image may be too large or initialization too slow. "
                "Consider: (1) Reduce image size, (2) Increase memory, (3) Optimize imports."
            )
        else:
            # If no InitDuration found, this might be a warm start
            pytest.skip(
                "No InitDuration found in logs - may not be a cold start. "
                "Try running test again to force cold start."
            )

    @pytest.mark.benchmark
    def test_cold_start_p95_latency(self, lambda_client):
        """
        Benchmark P95 cold start latency over multiple iterations.

        This test takes ~5 minutes to run (10 iterations with pauses).
        Run with: pytest -m benchmark
        """
        cold_start_times = []
        iterations = 10

        print(f"\n📊 Running {iterations} cold start iterations...")

        for i in range(iterations):
            # Force cold start by updating env var
            lambda_client.update_function_configuration(
                FunctionName=ANALYSIS_LAMBDA_NAME,
                Environment={"Variables": {"BENCHMARK_RUN": str(i)}},
            )

            # Wait for update
            waiter = lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=ANALYSIS_LAMBDA_NAME)

            # Invoke and measure
            test_event = {
                "Records": [
                    {
                        "Sns": {
                            "Message": f'{{"source_id": "benchmark-{i}", "text_for_analysis": "Test iteration {i}"}}'
                        }
                    }
                ]
            }

            response = lambda_client.invoke(
                FunctionName=ANALYSIS_LAMBDA_NAME,
                InvocationType="RequestResponse",
                LogType="Tail",
                Payload=bytes(str(test_event), "utf-8"),
            )

            # Extract InitDuration
            import base64

            log_result = base64.b64decode(response["LogResult"]).decode("utf-8")
            for line in log_result.split("\n"):
                if "Init Duration:" in line:
                    duration_str = line.split("Init Duration:")[1].strip().split(" ")[0]
                    cold_start_times.append(float(duration_str))
                    print(f"   Iteration {i+1}: {float(duration_str):.2f} ms")
                    break

            # Pause between iterations
            time.sleep(5)

        # Calculate P95
        if cold_start_times:
            cold_start_times.sort()
            p50 = cold_start_times[len(cold_start_times) // 2]
            p95_index = int(len(cold_start_times) * 0.95)
            p95 = cold_start_times[p95_index]
            avg = sum(cold_start_times) / len(cold_start_times)

            print("\n📊 Cold Start Benchmark Results:")
            print(f"   Iterations: {len(cold_start_times)}")
            print(f"   Average: {avg:.2f} ms")
            print(f"   P50: {p50:.2f} ms")
            print(f"   P95: {p95:.2f} ms")
            print(f"   Min: {min(cold_start_times):.2f} ms")
            print(f"   Max: {max(cold_start_times):.2f} ms")

            assert p95 < 5000, (
                f"P95 cold start {p95:.2f}ms exceeds 5s SLA. "
                f"This will impact {100 - 95}% of cold start users. "
                "Recommend: (1) Increase Lambda memory, (2) Reduce image size, (3) Use provisioned concurrency."
            )

            assert avg < 3000, (
                f"Average cold start {avg:.2f}ms is above 3s target. "
                "Consider optimizing container initialization."
            )


class TestContainerConfiguration:
    """Validate container-specific Lambda configuration."""

    def test_memory_allocation_sufficient(self, lambda_config):
        """
        Verify Lambda has sufficient memory for ML model.

        DistilBERT model requires ~1GB RAM. With container overhead,
        recommend minimum 1024MB (current allocation).
        """
        memory_mb = lambda_config["MemorySize"]
        assert memory_mb >= 1024, (
            f"Memory allocation {memory_mb}MB is insufficient for ML model. "
            "DistilBERT requires minimum 1024MB. Recommend 2048MB for better cold starts."
        )

    def test_ephemeral_storage_minimal(self, lambda_config):
        """
        Verify ephemeral storage is minimal (model baked into image).

        Container images don't need large /tmp for model files.
        """
        ephemeral_storage_mb = lambda_config["EphemeralStorage"]["Size"]
        assert ephemeral_storage_mb <= 1024, (
            f"Ephemeral storage {ephemeral_storage_mb}MB is excessive for container images. "
            "Model is baked into container, so /tmp should be minimal (512-1024MB)."
        )

    def test_timeout_reasonable(self, lambda_config):
        """
        Verify timeout allows for cold start + inference.

        Cold start: ~3s, Inference: ~1s, Buffer: 5s → Total: ~10s minimum
        """
        timeout_sec = lambda_config["Timeout"]
        assert timeout_sec >= 10, (
            f"Timeout {timeout_sec}s may be too short for cold start + inference. "
            "Recommend minimum 30s to handle cold starts reliably."
        )

        assert timeout_sec <= 300, (
            f"Timeout {timeout_sec}s is very high. "
            "Sentiment analysis should complete in <30s. "
            "High timeout may mask performance issues."
        )
