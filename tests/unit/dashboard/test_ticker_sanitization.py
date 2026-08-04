# Target: Admin Dashboard (Lambda HTMX)
"""Allowlist tests for the ticker sanitizers in src/dashboard/timeseries.js.

Every ticker in that module arrives from `?ticker=` / `?tickers=` in the page URL or
from a free-text input, and then reaches markup, an object property key, a request path
and a console format string. `sanitizeTicker` is the single boundary that keeps those
sinks safe, so its allowlist is worth pinning.

The functions are pure and depend on nothing but a module-level regex, so the test
slices them out of the real file and runs them under node rather than reimplementing
them in Python. Reimplementing would test the copy, not the code that ships.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TIMESERIES_JS = REPO_ROOT / "src" / "dashboard" / "timeseries.js"

# The sanitizers and the pattern they use, as one contiguous block.
BLOCK_START = "const TICKER_PATTERN"
BLOCK_END = "window.latencySamples = [];"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is required to execute the sanitizers"
)


def _sanitizer_source() -> str:
    """Return the sanitizer block from the shipping file.

    Fails loudly rather than silently returning an empty string, because a test that
    evaluates nothing would pass on every input.
    """
    source = TIMESERIES_JS.read_text(encoding="utf-8")
    start = source.index(BLOCK_START)
    end = source.index(BLOCK_END)
    block = source[start:end]
    assert "function sanitizeTicker(" in block, (
        "sanitizeTicker missing from sliced block"
    )
    assert "function sanitizeTickerList(" in block, (
        "sanitizeTickerList missing from block"
    )
    return block


def _run(expression: str, argument: object) -> object:
    """Evaluate one sanitizer call under node and return the parsed result.

    The argument is embedded as a JSON literal rather than interpolated raw, so a probe
    string carrying a quote or a backtick cannot terminate the surrounding script.
    """
    node = shutil.which("node")
    assert node is not None, "guarded by the module-level skipif"
    script = (
        _sanitizer_source()
        + f"\nconst __arg = {json.dumps(argument)};"
        + f"\nprocess.stdout.write(JSON.stringify({expression}));"
    )
    completed = subprocess.run(  # noqa: S603 - fixed argv, absolute interpreter path
        [node, "-e", script], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(completed.stdout)


class TestSanitizeTicker:
    """The single-symbol allowlist."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("AAPL", "AAPL"),
            ("aapl", "AAPL"),  # normalised to upper case
            ("  MSFT  ", "MSFT"),  # surrounding whitespace trimmed
            ("BRK.B", "BRK.B"),  # class share
            ("BF-A", "BF-A"),  # preferred series
            ("A", "A"),  # one character is the lower bound
            ("ABCDEFGHIJ", "ABCDEFGHIJ"),  # ten characters is the upper bound
        ],
    )
    def test_accepts_real_symbols(self, raw: str, expected: str) -> None:
        assert _run("sanitizeTicker(__arg)", raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "ABCDEFGHIJK",  # eleven characters, over the bound
            "AA PL",  # inner whitespace
            "AA,PL",  # comma would split a list entry
            "A/B",
            "A%sB",  # console format specifier
            "A`B",
            "<script>",
            '"><img src=x onerror=alert(1)>',
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "__proto__",  # underscore is not in the character class
            "constructor",  # eleven characters, over the bound
            "../../etc/passwd",
            "http://evil.example",
        ],
    )
    def test_rejects_hostile_and_malformed_input(self, raw: str) -> None:
        assert _run("sanitizeTicker(__arg)", raw) is None

    @pytest.mark.parametrize("raw", [None, 42, True, {"ticker": "AAPL"}, ["AAPL"]])
    def test_rejects_non_strings(self, raw: object) -> None:
        assert _run("sanitizeTicker(__arg)", raw) is None

    def test_rejects_prototype_polluting_keys_case_insensitively(self) -> None:
        """`__proto__` is rejected on the character class, not on a name comparison.

        The allowlist admits no underscore, so every casing fails for the same reason.
        """
        for candidate in ["__proto__", "__PROTO__", "__Proto__"]:
            assert _run("sanitizeTicker(__arg)", candidate) is None

    def test_output_can_never_be_a_dangerous_property_key(self) -> None:
        """The survivors are used directly as object keys, so this is the property that matters.

        `prototype` survives the character class, but the sanitizer upper-cases before it
        tests, so what comes back is `PROTOTYPE` — a plain key with no meaning to the
        runtime. Every dangerous key contains a lower-case letter or an underscore, so no
        input can reach one. The keyed stores are additionally `Object.create(null)`, which
        leaves nothing on the chain to reach even if this property were lost.
        """
        dangerous = ["__proto__", "constructor", "prototype"]
        for candidate in dangerous + ["PROTOTYPE", "prototype", "AAPL"]:
            result = _run("sanitizeTicker(__arg)", candidate)
            assert result is None or result not in dangerous

    def test_survivors_always_match_the_advertised_shape(self) -> None:
        """A survivor is interpolated, keyed and pathed on, so its shape is the contract."""
        probes = ["aapl", "BRK.B", "bf-a", "prototype", "  msft  ", "ABCDEFGHIJ"]
        for probe in probes:
            result = _run("sanitizeTicker(__arg)", probe)
            if result is not None:
                assert re.fullmatch(r"[A-Z0-9.\-]{1,10}", result), result


class TestSanitizeTickerList:
    """The comma-separated list allowlist."""

    def test_accepts_a_plain_list(self) -> None:
        assert _run("sanitizeTickerList(__arg)", "AAPL,MSFT,GOOGL") == [
            "AAPL",
            "MSFT",
            "GOOGL",
        ]

    def test_trims_and_upper_cases_entries(self) -> None:
        assert _run("sanitizeTickerList(__arg)", " aapl , msft ") == ["AAPL", "MSFT"]

    def test_drops_bad_entries_and_keeps_good_ones(self) -> None:
        """One hostile symbol in a shared link must not blank the whole view."""
        assert _run("sanitizeTickerList(__arg)", "AAPL,<script>,MSFT") == [
            "AAPL",
            "MSFT",
        ]

    def test_deduplicates_while_preserving_order(self) -> None:
        assert _run("sanitizeTickerList(__arg)", "MSFT,AAPL,msft") == ["MSFT", "AAPL"]

    def test_accepts_an_array_argument(self) -> None:
        """The multi-ticker init() passes an array rather than a string."""
        assert _run("sanitizeTickerList(__arg)", ["AAPL", "bad symbol", "MSFT"]) == [
            "AAPL",
            "MSFT",
        ]

    @pytest.mark.parametrize("raw", ["", ",,,", "<script>", None, 42])
    def test_returns_empty_when_nothing_survives(self, raw: object) -> None:
        assert _run("sanitizeTickerList(__arg)", raw) == []


class TestSlicing:
    """Guards on the extraction itself, so a refactor cannot quietly empty this suite."""

    def test_block_markers_still_exist(self) -> None:
        source = TIMESERIES_JS.read_text(encoding="utf-8")
        assert BLOCK_START in source
        assert BLOCK_END in source
        assert source.index(BLOCK_START) < source.index(BLOCK_END)

    def test_pattern_is_anchored_at_both_ends(self) -> None:
        """An unanchored pattern would match a hostile string that merely contains a symbol."""
        block = _sanitizer_source()
        pattern = re.search(r"const TICKER_PATTERN = /(.+)/;", block)
        assert pattern is not None
        assert pattern.group(1).startswith("^")
        assert pattern.group(1).endswith("$")
