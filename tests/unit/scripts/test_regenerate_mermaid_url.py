"""Regression tests for ``scripts/regenerate-mermaid-url.py``.

The subject is the arrow-without-target check, which used to be a regex
pattern match and is now a plain line scan. The differential test rebuilds
the original expression as a local oracle and asserts the shipped check
agrees with it over several thousand generated inputs, so the rewrite is
proven behaviour-preserving rather than assumed to be.
"""

from __future__ import annotations

import importlib.util
import itertools
import random
import re
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "regenerate-mermaid-url.py"

ARROW_MSG = "Arrow without target node (line ends with -->)"
THICK_ARROW_MSG = "Thick arrow without target node (line ends with ==>)"


def _load_script() -> ModuleType:
    """Load the script by path.

    The filename is hyphenated and therefore not importable by name, and
    renaming it is out of scope: it is referenced by path in documentation.
    The path is resolved from this file rather than from the cwd.
    """
    spec = importlib.util.spec_from_file_location("regenerate_mermaid_url", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def fires(code: str) -> bool:
    """True when the shipped validator reports arrow-without-target."""
    return ARROW_MSG in script.validate_mermaid_syntax(code)


def thick_fires(code: str) -> bool:
    """True when the shipped validator reports thick-arrow-without-target."""
    return THICK_ARROW_MSG in script.validate_mermaid_syntax(code)


def oracle(code: str) -> bool:
    """The original expression the check replaced, rebuilt verbatim."""
    return bool(re.search(r"-->\s*$", code, re.MULTILINE))


# Atom set for the generated corpus. Every exotic line separator that
# str.splitlines() honours and regex ``$`` does not is present, because that
# difference is the whole reason the rewrite uses split("\n").
ATOMS = (
    "-->",
    "==>",
    "<!--",
    "--!>",
    " ",
    "\t",
    "\r",
    "\n",
    "\v",
    "\f",
    "\x85",
    "\u2028",
    "\u2029",
    "\xa0",
    "A",
)

HAND_PICKED = (
    "",
    "   ",
    "\n\n\n",
    "-->",
    "-->   ",
    "-->\t\t",
    "-->\xa0",
    "-->\v",
    "-->\n\n\n",
    "A --> B",
    "A --> B\nC -->",
    "A -->\rB",
    "A -->\r\n",
    "graph TD\nA-->B\n",
    "==>",
    "flowchart LR\nA ==> ",
)

RANDOM_SEED = 20260730
RANDOM_SAMPLES = 3000


def build_corpus() -> list[str]:
    """Exhaustive short products, seeded random longer strings, hand cases."""
    corpus: list[str] = []
    for size in (1, 2, 3):
        corpus.extend("".join(parts) for parts in itertools.product(ATOMS, repeat=size))
    rng = random.Random(RANDOM_SEED)
    for _ in range(RANDOM_SAMPLES):
        length = rng.randint(4, 5)
        corpus.append("".join(rng.choice(ATOMS) for _ in range(length)))
    corpus.extend(HAND_PICKED)
    return corpus


def test_corpus_is_large_enough() -> None:
    """Without this the differential result is unfalsifiable.

    A corpus that silently shrank to a dozen inputs still reports zero
    mismatches.
    """
    corpus = build_corpus()
    assert len(corpus) >= 1500, (
        f"differential corpus shrank to {len(corpus)} inputs; zero mismatches "
        "over a tiny corpus proves nothing"
    )


def test_differential_against_original_expression() -> None:
    """The rewrite must agree with the original expression on every input."""
    corpus = build_corpus()
    assert len(corpus) >= 1500
    mismatches = [code for code in corpus if fires(code) != oracle(code)]
    assert not mismatches, (
        f"{len(mismatches)} of {len(corpus)} inputs disagree with the original "
        f"expression; first five: {[repr(code) for code in mismatches[:5]]}"
    )


def test_trailing_spaces_after_arrow_fire() -> None:
    assert fires("graph TD\nA -->   ")


def test_trailing_tabs_after_arrow_fire() -> None:
    assert fires("graph TD\nA -->\t\t")


def test_trailing_nbsp_and_vertical_tab_after_arrow_fire() -> None:
    assert fires("graph TD\nA -->\xa0")
    assert fires("graph TD\nA -->\v")


def test_crlf_and_lf_agree() -> None:
    assert fires("graph TD\nA -->\r\n") == fires("graph TD\nA -->\n")
    assert fires("graph TD\nA -->\r\n")


def test_empty_input_does_not_fire() -> None:
    assert not fires("")


def test_whitespace_only_input_does_not_fire() -> None:
    assert not fires("   \t\n  ")


def test_trailing_blank_lines_after_arrow_fire() -> None:
    assert fires("graph TD\nA -->\n\n\n")


def test_arrow_with_target_does_not_fire() -> None:
    assert not fires("graph TD\nA --> B\n")


def test_arrow_with_target_then_bare_arrow_fires() -> None:
    assert fires("graph TD\nA --> B\nC -->\n")


def test_carriage_return_separator_does_not_fire() -> None:
    """The counterexample that separates split("\\n") from splitlines().

    The original expression is False on this input because regex ``$`` under
    MULTILINE does not treat a bare carriage return as a line boundary. A
    splitlines() rewrite would return True.
    """
    assert not fires("A -->\rB")
    assert not oracle("A -->\rB")


def test_thick_arrow_control_still_fires() -> None:
    """The sibling check is untouched and must still work."""
    assert thick_fires("graph TD\nA ==>")
    assert not thick_fires("graph TD\nA ==> B\n")


def test_both_arrow_checks_report_independently() -> None:
    both = script.validate_mermaid_syntax("graph TD\nA -->\nB ==>\n")
    assert ARROW_MSG in both
    assert THICK_ARROW_MSG in both

    thin_only = script.validate_mermaid_syntax("graph TD\nA -->\nB ==> C\n")
    assert ARROW_MSG in thin_only
    assert THICK_ARROW_MSG not in thin_only

    thick_only = script.validate_mermaid_syntax("graph TD\nA --> B\nC ==>\n")
    assert ARROW_MSG not in thick_only
    assert THICK_ARROW_MSG in thick_only
