"""T029: Integration test for X-Ray silent failure instrumentation.

Verifies via static source analysis that every silent failure path in the
ingestion pipeline has the required X-Ray subsegment instrumentation and
emits the SilentFailure/Count CloudWatch metric.

Pattern verified in each except block:
    with tracer.provider.in_subsegment("<name>") as subseg:
        subseg.put_annotation("error", True)
        subseg.add_exception(e)
    emit_metric("SilentFailure/Count", ...)

Expected subsegment names:
    circuit_breaker_load, circuit_breaker_save, audit_trail,
    notification_delivery, fanout_partial_write, self_healing_fetch,
    parallel_fetcher_aggregate
"""

import re
from pathlib import Path

import pytest

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SOURCE_FILES: dict[str, Path] = {
    "circuit_breaker": _REPO_ROOT / "src/lambdas/shared/circuit_breaker.py",
    "audit": _REPO_ROOT / "src/lambdas/ingestion/audit.py",
    "notification": _REPO_ROOT / "src/lambdas/ingestion/notification.py",
    "storage": _REPO_ROOT / "src/lambdas/ingestion/storage.py",
    "self_healing": _REPO_ROOT / "src/lambdas/ingestion/self_healing.py",
    "parallel_fetcher": _REPO_ROOT / "src/lambdas/ingestion/parallel_fetcher.py",
}

# Subsegment names that must be present across all source files.
EXPECTED_SUBSEGMENT_NAMES: set[str] = {
    "circuit_breaker_load",
    "circuit_breaker_save",
    "audit_trail",
    "notification_delivery",
    "fanout_partial_write",
    "self_healing_fetch",
    "parallel_fetcher_aggregate",
}

# Map from subsegment name to the source module that owns it.
SUBSEGMENT_TO_MODULE: dict[str, str] = {
    "circuit_breaker_load": "circuit_breaker",
    "circuit_breaker_save": "circuit_breaker",
    "audit_trail": "audit",
    "notification_delivery": "notification",
    "fanout_partial_write": "storage",
    "self_healing_fetch": "self_healing",
    "parallel_fetcher_aggregate": "parallel_fetcher",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source(module_name: str) -> str:
    """Return the full text of a source module."""
    path = _SOURCE_FILES[module_name]
    assert path.exists(), (
        f"Source file not found: {path}. "
        "The integration test assumes the production source tree is present."
    )
    return path.read_text(encoding="utf-8")


def _find_subsegment_blocks(source: str, subsegment_name: str) -> list[str]:
    """Return all text windows that open the named subsegment.

    Each window spans from the ``in_subsegment(...)`` call up to and
    including the closing ``except Exception`` guard block that wraps it,
    giving enough context to assert on the three required lines:
        subseg.put_annotation("error", True)
        subseg.add_exception(e)
        emit_metric("SilentFailure/Count", ...)

    Strategy: find every occurrence of ``in_subsegment("<name>")`` in the
    full source text (handles multi-line calls), then extract a window of
    lines around each match.
    """
    pattern = re.compile(
        r'in_subsegment\(\s*["\']' + re.escape(subsegment_name) + r'["\']',
        re.DOTALL,
    )
    blocks: list[str] = []
    lines = source.splitlines()
    for match in pattern.finditer(source):
        # Find the line number of the match start
        lineno = source[: match.start()].count("\n")
        # Capture from 2 lines before (the ``try:``) to 30 lines after
        start = max(0, lineno - 2)
        end = min(len(lines), lineno + 30)
        blocks.append("\n".join(lines[start:end]))
    return blocks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestXRaySilentFailureInstrumentation:
    """Static-analysis tests for X-Ray silent failure instrumentation."""

    def test_all_source_files_exist(self):
        """All source files under test must be present on disk."""
        for module_name, path in _SOURCE_FILES.items():
            assert (
                path.exists()
            ), f"Source file missing for module '{module_name}': {path}"

    def test_expected_subsegment_names_are_present_in_codebase(self):
        """Every expected subsegment name must appear in at least one source file."""
        all_source = "\n".join(_read_source(name) for name in _SOURCE_FILES)
        missing: list[str] = []
        for name in EXPECTED_SUBSEGMENT_NAMES:
            pattern = re.compile(
                r'in_subsegment\(\s*["\']' + re.escape(name) + r'["\']'
            )
            if not pattern.search(all_source):
                missing.append(name)
        assert not missing, f"Subsegment names not found in any source file: {missing}"

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_is_in_correct_module(self, subsegment_name: str):
        """Each subsegment must appear in its designated module."""
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        pattern = re.compile(
            r'in_subsegment\(\s*["\']' + re.escape(subsegment_name) + r'["\']'
        )
        assert pattern.search(source), (
            f"Subsegment '{subsegment_name}' not found in module "
            f"'{module_name}' ({_SOURCE_FILES[module_name]})"
        )

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_sets_error_annotation(self, subsegment_name: str):
        """Each subsegment block must call put_annotation("error", True)."""
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        blocks = _find_subsegment_blocks(source, subsegment_name)
        assert blocks, (
            f"No in_subsegment block found for '{subsegment_name}' "
            f"in {_SOURCE_FILES[module_name]}"
        )
        pattern = re.compile(r'put_annotation\(\s*["\']error["\'],\s*True\s*\)')
        for block in blocks:
            assert pattern.search(block), (
                f"Subsegment '{subsegment_name}' block does not call "
                f'put_annotation("error", True).\nBlock:\n{block}'
            )

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_calls_add_exception(self, subsegment_name: str):
        """Each subsegment block must call add_exception(e)."""
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        blocks = _find_subsegment_blocks(source, subsegment_name)
        assert blocks, (
            f"No in_subsegment block found for '{subsegment_name}' "
            f"in {_SOURCE_FILES[module_name]}"
        )
        pattern = re.compile(r"add_exception\(\s*e\s*\)")
        for block in blocks:
            assert pattern.search(block), (
                f"Subsegment '{subsegment_name}' block does not call "
                f"add_exception(e).\nBlock:\n{block}"
            )

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_emits_silent_failure_metric(self, subsegment_name: str):
        """Each silent failure path must emit the SilentFailure/Count metric."""
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        blocks = _find_subsegment_blocks(source, subsegment_name)
        assert blocks, (
            f"No in_subsegment block found for '{subsegment_name}' "
            f"in {_SOURCE_FILES[module_name]}"
        )
        metric_pattern = re.compile(r'["\']SilentFailure/Count["\']')
        failure_path_pattern = re.compile(
            r'["\']FailurePath["\'].*?["\']' + re.escape(subsegment_name) + r'["\']',
            re.DOTALL,
        )
        for block in blocks:
            assert metric_pattern.search(block), (
                f"Subsegment '{subsegment_name}' block does not emit "
                f"'SilentFailure/Count' metric.\nBlock:\n{block}"
            )
            assert failure_path_pattern.search(block), (
                f"Subsegment '{subsegment_name}' block does not set "
                f"FailurePath dimension to '{subsegment_name}'.\nBlock:\n{block}"
            )

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_metric_uses_reliability_namespace(self, subsegment_name: str):
        """Each silent failure metric must use the SentimentAnalyzer/Reliability namespace."""
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        blocks = _find_subsegment_blocks(source, subsegment_name)
        assert blocks, (
            f"No in_subsegment block found for '{subsegment_name}' "
            f"in {_SOURCE_FILES[module_name]}"
        )
        namespace_pattern = re.compile(r'["\']SentimentAnalyzer/Reliability["\']')
        for block in blocks:
            assert namespace_pattern.search(block), (
                f"Subsegment '{subsegment_name}' metric does not use "
                f"'SentimentAnalyzer/Reliability' namespace.\nBlock:\n{block}"
            )

    @pytest.mark.parametrize("subsegment_name", sorted(EXPECTED_SUBSEGMENT_NAMES))
    def test_subsegment_wrapped_in_besteffort_guard(self, subsegment_name: str):
        """Each in_subsegment call must be wrapped in a try/except guard.

        The guard prevents X-Ray instrumentation failures from propagating to
        the application layer (best-effort pattern).
        """
        module_name = SUBSEGMENT_TO_MODULE[subsegment_name]
        source = _read_source(module_name)
        blocks = _find_subsegment_blocks(source, subsegment_name)
        assert blocks, (
            f"No in_subsegment block found for '{subsegment_name}' "
            f"in {_SOURCE_FILES[module_name]}"
        )
        # The try wrapping the in_subsegment call must appear within 5 lines
        # before it; _find_subsegment_blocks already starts 2 lines before the
        # match, so a bare ``try:`` in the captured block is sufficient.
        try_guard_pattern = re.compile(r"\btry\s*:")
        except_guard_pattern = re.compile(r"\bexcept\s+Exception\s*:")
        for block in blocks:
            assert try_guard_pattern.search(block), (
                f"Subsegment '{subsegment_name}' block is not wrapped in "
                f"a try block.\nBlock:\n{block}"
            )
            assert except_guard_pattern.search(block), (
                f"Subsegment '{subsegment_name}' block is not wrapped in "
                f"an 'except Exception:' guard.\nBlock:\n{block}"
            )

    def test_no_unexpected_subsegments_in_sources(self):
        """Document any in_subsegment calls that are not in the expected set.

        This is an informational assertion: it fails if a new silent failure
        path is added to a tracked source file without updating
        EXPECTED_SUBSEGMENT_NAMES and SUBSEGMENT_TO_MODULE.
        """
        pattern = re.compile(r'in_subsegment\(\s*["\']([^"\']+)["\']')
        found_names: set[str] = set()
        for module_name in _SOURCE_FILES:
            source = _read_source(module_name)
            for match in pattern.finditer(source):
                found_names.add(match.group(1))

        unexpected = found_names - EXPECTED_SUBSEGMENT_NAMES
        assert not unexpected, (
            f"Found in_subsegment calls with names not listed in "
            f"EXPECTED_SUBSEGMENT_NAMES: {sorted(unexpected)}. "
            "Add them to both EXPECTED_SUBSEGMENT_NAMES and "
            "SUBSEGMENT_TO_MODULE in this test file."
        )
