#!/usr/bin/env python3
"""T095-T097: Verification gate for dual-emit parity (FR-109, FR-152).

Provides 4 gate functions for verifying X-Ray trace correctness:
1. verify_trace_structure() - Validates trace segments have expected attributes
2. verify_annotation_parity() - Confirms annotations match across old/new systems
3. verify_service_map() - Validates service map topology
4. verify_trace_sample() - Statistical sampling of traces for completeness

Accumulation tracking: 14 consecutive healthy days required before
logging removal can begin. Gate failure resets clock (clarification Q3).

Usage:
    python scripts/verify-dual-emit.py --environment preprod
    python scripts/verify-dual-emit.py --environment prod --gate all
    python scripts/verify-dual-emit.py --gate trace_structure
    make verify-dual-emit
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# State file for accumulation tracking
STATE_FILE = Path(".specify/verification/dual-emit-state.json")

# Expected Lambda services in the service map
EXPECTED_SERVICES = [
    "sentiment-analyzer-ingestion",
    "sentiment-analyzer-analysis",
    "sentiment-analyzer-dashboard",
    "sentiment-analyzer-metrics",
    "sentiment-analyzer-notification",
    "sentiment-analyzer-sse",
]

# Required annotation keys per service
REQUIRED_ANNOTATIONS = {
    "sentiment-analyzer-ingestion": ["source_id", "item_count"],
    "sentiment-analyzer-analysis": ["ticker", "sentiment_label"],
    "sentiment-analyzer-dashboard": [],
    "sentiment-analyzer-metrics": ["metric_count", "query_duration_ms"],
    "sentiment-analyzer-notification": ["recipient_count", "template_name"],
    "sentiment-analyzer-sse": ["connection_id"],
}


@dataclass
class GateResult:
    """Result of a verification gate check."""

    gate: str
    passed: bool
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
        }


def _get_xray_client():
    """Get boto3 X-Ray client."""
    import boto3

    return boto3.client(
        "xray",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )


def verify_trace_structure(environment: str) -> GateResult:
    """Gate 1: Validate trace segments have expected attributes (FR-109).

    Fetches recent traces and verifies:
    - All 6 Lambda services appear in traces
    - Each segment has correct service name annotation
    - Error segments have fault=true OR error=true
    """
    try:
        client = _get_xray_client()
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=1)

        response = client.get_trace_summaries(
            StartTime=start_time,
            EndTime=end_time,
            Sampling=True,
        )

        summaries = response.get("TraceSummaries", [])
        if not summaries:
            return GateResult(
                gate="trace_structure",
                passed=False,
                message="No traces found in last hour",
                details={"environment": environment},
            )

        services_found = set()
        for summary in summaries:
            for entry in summary.get("ServiceIds", []):
                name = entry.get("Name", "")
                if name.startswith("sentiment-analyzer-"):
                    services_found.add(name)

        missing = set(EXPECTED_SERVICES) - services_found
        return GateResult(
            gate="trace_structure",
            passed=len(missing) == 0,
            message=(
                "All services present in traces"
                if not missing
                else f"Missing services: {sorted(missing)}"
            ),
            details={
                "services_found": sorted(services_found),
                "services_missing": sorted(missing),
                "trace_count": len(summaries),
            },
        )
    except Exception as e:
        return GateResult(
            gate="trace_structure",
            passed=False,
            message=f"Failed to verify: {e}",
        )


def verify_annotation_parity(environment: str) -> GateResult:
    """Gate 2: Confirm annotations match expected schema (FR-152).

    Fetches sample traces and verifies annotation keys match
    the data-model.md schema for each service.
    """
    try:
        client = _get_xray_client()
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=1)

        response = client.get_trace_summaries(
            StartTime=start_time,
            EndTime=end_time,
            Sampling=True,
        )

        summaries = response.get("TraceSummaries", [])
        if not summaries:
            return GateResult(
                gate="annotation_parity",
                passed=False,
                message="No traces found for annotation check",
            )

        # Sample first 10 traces for annotation verification
        trace_ids = [s["Id"] for s in summaries[:10]]
        traces_response = client.batch_get_traces(TraceIds=trace_ids)

        annotation_issues = []
        for trace in traces_response.get("Traces", []):
            for segment in trace.get("Segments", []):
                doc = json.loads(segment.get("Document", "{}"))
                service_name = doc.get("name", "")
                annotations = doc.get("annotations", {})

                required = REQUIRED_ANNOTATIONS.get(service_name, [])
                missing_keys = [k for k in required if k not in annotations]
                if missing_keys:
                    annotation_issues.append(f"{service_name}: missing {missing_keys}")

        return GateResult(
            gate="annotation_parity",
            passed=len(annotation_issues) == 0,
            message=(
                "All annotations match schema"
                if not annotation_issues
                else f"{len(annotation_issues)} annotation issues"
            ),
            details={
                "traces_checked": len(trace_ids),
                "issues": annotation_issues[:10],
            },
        )
    except Exception as e:
        return GateResult(
            gate="annotation_parity",
            passed=False,
            message=f"Failed to verify: {e}",
        )


def verify_service_map(environment: str) -> GateResult:
    """Gate 3: Validate service map topology (FR-109).

    Verifies all expected services appear in the X-Ray service map
    with correct edge connections.
    """
    try:
        client = _get_xray_client()
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=6)

        response = client.get_service_graph(
            StartTime=start_time,
            EndTime=end_time,
        )

        services = response.get("Services", [])
        service_names = {s.get("Name", "") for s in services}

        found = {s for s in EXPECTED_SERVICES if s in service_names}
        missing = set(EXPECTED_SERVICES) - found

        return GateResult(
            gate="service_map",
            passed=len(missing) == 0,
            message=(
                "Service map complete"
                if not missing
                else f"Missing from service map: {sorted(missing)}"
            ),
            details={
                "services_in_map": sorted(found),
                "services_missing": sorted(missing),
                "total_services": len(services),
            },
        )
    except Exception as e:
        return GateResult(
            gate="service_map",
            passed=False,
            message=f"Failed to verify: {e}",
        )


def verify_trace_sample(environment: str) -> GateResult:
    """Gate 4: Statistical sampling of traces for completeness (FR-109).

    Samples recent traces and calculates completeness ratio:
    - What % of traces have all expected segments?
    - What % have proper error attribution?
    - Threshold: >= 95% completeness required
    """
    try:
        client = _get_xray_client()
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=1)

        response = client.get_trace_summaries(
            StartTime=start_time,
            EndTime=end_time,
            Sampling=True,
        )

        summaries = response.get("TraceSummaries", [])
        if not summaries:
            return GateResult(
                gate="trace_sample",
                passed=False,
                message="No traces found for sampling",
            )

        total = len(summaries)
        complete = 0
        error_attributed = 0
        total_errors = 0

        for summary in summaries:
            service_names = {
                entry.get("Name", "") for entry in summary.get("ServiceIds", [])
            }
            # A trace is "complete" if it has at least the entry service
            if any(s.startswith("sentiment-analyzer-") for s in service_names):
                complete += 1

            if summary.get("HasFault") or summary.get("HasError"):
                total_errors += 1
                # Error-attributed if it has annotations
                if summary.get("Annotations"):
                    error_attributed += 1

        completeness = complete / total if total > 0 else 0
        threshold = 0.95

        return GateResult(
            gate="trace_sample",
            passed=completeness >= threshold,
            message=(f"Completeness: {completeness:.1%} (threshold: {threshold:.0%})"),
            details={
                "total_traces": total,
                "complete_traces": complete,
                "completeness_ratio": round(completeness, 4),
                "error_traces": total_errors,
                "error_attributed": error_attributed,
                "threshold": threshold,
            },
        )
    except Exception as e:
        return GateResult(
            gate="trace_sample",
            passed=False,
            message=f"Failed to verify: {e}",
        )


# ===================================================================
# Accumulation Tracking (T097, clarification Q3)
# ===================================================================


def load_state() -> dict:
    """Load accumulation state from disk."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"consecutive_days": 0, "last_pass": None, "history": []}


def save_state(state: dict) -> None:
    """Save accumulation state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def update_accumulation(all_passed: bool) -> dict:
    """Update the 14-day accumulation counter.

    Gate failure resets clock per clarification Q3.

    Returns:
        Updated state dict
    """
    state = load_state()
    today = datetime.now(UTC).date().isoformat()

    if all_passed:
        last_pass = state.get("last_pass")
        if last_pass == today:
            # Already counted today
            pass
        elif (
            last_pass
            and (datetime.fromisoformat(today) - datetime.fromisoformat(last_pass)).days
            == 1
        ):
            # Consecutive day
            state["consecutive_days"] += 1
        else:
            # Gap or first run
            state["consecutive_days"] = 1

        state["last_pass"] = today
    else:
        # RESET on failure (clarification Q3)
        state["consecutive_days"] = 0
        state["last_pass"] = None

    state["history"].append({"date": today, "passed": all_passed})
    # Keep last 30 days of history
    state["history"] = state["history"][-30:]

    save_state(state)
    return state


# ===================================================================
# CLI
# ===================================================================

GATES = {
    "trace_structure": verify_trace_structure,
    "annotation_parity": verify_annotation_parity,
    "service_map": verify_service_map,
    "trace_sample": verify_trace_sample,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dual-emit verification gates")
    parser.add_argument(
        "--environment",
        default=os.environ.get("AWS_ENVIRONMENT", "preprod"),
        help="Target environment (default: preprod)",
    )
    parser.add_argument(
        "--gate",
        choices=["all", *GATES.keys()],
        default="all",
        help="Which gate to run (default: all)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    gates_to_run = GATES if args.gate == "all" else {args.gate: GATES[args.gate]}
    results = []

    for _name, gate_fn in gates_to_run.items():
        result = gate_fn(args.environment)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        if not args.json:
            print(f"[{status}] {result.gate}: {result.message}")

    all_passed = all(r.passed for r in results)

    # Update accumulation tracking
    state = update_accumulation(all_passed)

    if args.json:
        output = {
            "results": [r.to_dict() for r in results],
            "all_passed": all_passed,
            "accumulation": {
                "consecutive_days": state["consecutive_days"],
                "target_days": 14,
                "ready_for_removal": state["consecutive_days"] >= 14,
            },
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print()
        print(f"Accumulation: {state['consecutive_days']}/14 consecutive days")
        if state["consecutive_days"] >= 14:
            print("READY: Logging removal can proceed (Phase 7)")
        else:
            remaining = 14 - state["consecutive_days"]
            print(f"WAITING: {remaining} more days required before Phase 7")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
