# X-Ray Helpers
#
# Utilities for querying and validating X-Ray traces during E2E tests.
# Used for observability validation (US11).

import asyncio
import json
import os
import time
from dataclasses import dataclass

import boto3


@dataclass
class TraceSegment:
    """Represents an X-Ray trace segment."""

    id: str
    name: str
    start_time: float
    end_time: float | None
    error: bool
    fault: bool
    annotations: dict
    metadata: dict
    subsegments: list["TraceSegment"]


@dataclass
class Trace:
    """Represents a complete X-Ray trace."""

    id: str
    duration: float | None
    segments: list[TraceSegment]
    has_error: bool
    has_fault: bool


def get_xray_client():
    """Get X-Ray client."""
    return boto3.client(
        "xray",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def parse_trace_id_from_header(header: str) -> str | None:
    """Parse trace ID from X-Amzn-Trace-Id header.

    Args:
        header: X-Amzn-Trace-Id header value
                Format: "Root=1-xxx;Parent=xxx;Sampled=1"

    Returns:
        Trace ID (Root value) or None if not found
    """
    if not header:
        return None

    for part in header.split(";"):
        if part.startswith("Root="):
            return part.split("=")[1]
    return None


def _parse_segment(segment_doc: dict) -> TraceSegment:
    """Parse a segment document into TraceSegment."""
    subsegments = []
    for sub in segment_doc.get("subsegments", []):
        subsegments.append(_parse_segment(sub))

    return TraceSegment(
        id=segment_doc.get("id", ""),
        name=segment_doc.get("name", ""),
        start_time=segment_doc.get("start_time", 0),
        end_time=segment_doc.get("end_time"),
        error=segment_doc.get("error", False),
        fault=segment_doc.get("fault", False),
        annotations=segment_doc.get("annotations", {}),
        metadata=segment_doc.get("metadata", {}),
        subsegments=subsegments,
    )


async def get_xray_trace(
    trace_id: str,
    max_wait_seconds: int = 60,
    poll_interval: int = 5,
) -> Trace | None:
    """Retrieve X-Ray trace by ID, waiting for segments to propagate.

    Args:
        trace_id: X-Ray trace ID (from X-Amzn-Trace-Id header)
        max_wait_seconds: Maximum time to wait for trace
        poll_interval: Seconds between attempts

    Returns:
        Trace object or None if not found within timeout
    """
    client = get_xray_client()

    start = time.time()
    while time.time() - start < max_wait_seconds:
        response = client.batch_get_traces(TraceIds=[trace_id])

        if response.get("Traces"):
            trace_data = response["Traces"][0]
            segments = []
            has_error = False
            has_fault = False

            for segment in trace_data.get("Segments", []):
                doc = json.loads(segment.get("Document", "{}"))
                parsed = _parse_segment(doc)
                segments.append(parsed)
                if parsed.error:
                    has_error = True
                if parsed.fault:
                    has_fault = True

            return Trace(
                id=trace_data.get("Id", trace_id),
                duration=trace_data.get("Duration"),
                segments=segments,
                has_error=has_error,
                has_fault=has_fault,
            )

        await asyncio.sleep(poll_interval)

    return None


def validate_trace_segments(
    trace: Trace,
    expected_segments: list[str],
) -> bool:
    """Validate trace contains expected Lambda segments.

    Args:
        trace: Trace object to validate
        expected_segments: List of expected segment names

    Returns:
        True if all expected segments are present
    """
    segment_names = {seg.name for seg in trace.segments}
    return all(name in segment_names for name in expected_segments)


def get_segment_by_name(trace: Trace, name: str) -> TraceSegment | None:
    """Get a specific segment from a trace by name.

    Args:
        trace: Trace to search
        name: Segment name to find

    Returns:
        TraceSegment or None if not found
    """
    for segment in trace.segments:
        if segment.name == name:
            return segment
        # Check subsegments recursively
        for sub in segment.subsegments:
            if sub.name == name:
                return sub
    return None


def validate_cross_lambda_trace(
    trace: Trace,
    lambda_names: list[str],
) -> bool:
    """Validate trace shows cross-Lambda invocation chain.

    Args:
        trace: Trace to validate
        lambda_names: Expected Lambda function names in order

    Returns:
        True if trace shows the expected Lambda invocation chain
    """
    found_names = []
    for segment in trace.segments:
        if segment.name in lambda_names:
            found_names.append(segment.name)

    # Check all expected Lambdas are present
    for name in lambda_names:
        if name not in found_names:
            return False

    return True


async def wait_for_trace_with_segment(
    trace_id: str,
    segment_name: str,
    max_wait_seconds: int = 60,
) -> Trace | None:
    """Wait for a trace to have a specific segment.

    Useful when waiting for async Lambda invocations to complete.

    Args:
        trace_id: X-Ray trace ID
        segment_name: Segment name to wait for
        max_wait_seconds: Maximum wait time

    Returns:
        Complete Trace or None if segment not found in time
    """
    start = time.time()
    while time.time() - start < max_wait_seconds:
        trace = await get_xray_trace(trace_id, max_wait_seconds=10)
        if trace:
            segment = get_segment_by_name(trace, segment_name)
            if segment and segment.end_time:
                return trace
        await asyncio.sleep(5)
    return None


def trace_has_annotation(
    trace: Trace,
    key: str,
    value: str | None = None,
) -> bool:
    """Check if any segment in trace has a specific annotation.

    Args:
        trace: Trace to check
        key: Annotation key to find
        value: Optional specific value to match

    Returns:
        True if annotation is found (with matching value if specified)
    """
    for segment in trace.segments:
        if key in segment.annotations:
            if value is None or segment.annotations[key] == value:
                return True
    return False
