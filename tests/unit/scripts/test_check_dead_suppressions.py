"""Tests for the dead-suppression checker.

BINDING RULE FOR THIS FILE: no single source line may contain a comment
introducer followed by a suppression marker. The checker's detection rule is
purely textual and does not know what a string literal is, so the natural way
to write a fixture would make the checker flag the file that tests it. Every
fixture is therefore assembled from separated constants, and no marker is ever
written in a real comment here.

Two independent mechanisms keep this file clean: the checker's exact-path
self-exclusion, and the rule above. Without the rule, only the exclusion holds
it, and the file would be one rename away from a permanently red gate.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.check_dead_suppressions as mod

SCRIPT = mod.REPO_ROOT / "scripts" / "check_dead_suppressions.py"

# Fixture building blocks, kept apart so no line below carries both halves.
HASH = "#"
SLASHES = "//"
HTML_OPEN = "<!--"
C_OPEN = "/*"
DASHES = "--"

LGTM = "lgtm[py/some-rule]"
CODEQL = "codeql[py/some-rule]"
LGTM_UPPER = "LGTM[py/some-rule]"
CODEQL_MIXED = "CodeQL[py/some-rule]"


def seed(directory: Path, name: str, body: str) -> Path:
    """Write a fixture file and return its path."""
    target = directory / name
    target.write_text(body, encoding="utf-8")
    return target


def run_in_process(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    roots: str | None,
) -> tuple[int, str]:
    """Run the checker in process against *roots*, returning code and stdout."""
    if roots is None:
        monkeypatch.delenv(mod.ROOTS_ENV, raising=False)
    else:
        monkeypatch.setenv(mod.ROOTS_ENV, roots)
    code = mod.main([])
    return code, capsys.readouterr().out


def run_cli(
    args: list[str],
    roots: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the checker as a command line, pinning the current interpreter.

    A bare ``python3`` resolves differently per machine and per shell, so the
    interpreter this test is running under is used instead.
    """
    env = dict(os.environ)
    if roots is None:
        env.pop(mod.ROOTS_ENV, None)
    else:
        env[mod.ROOTS_ENV] = roots
    # S603: argv is sys.executable plus a repository-fixed script path, and no
    # untrusted input reaches the subprocess.
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        timeout=300,
    )


def scanned_count(output: str) -> int:
    """Pull the file count out of a run's output."""
    for line in output.split("\n"):
        if line.startswith("Scanned "):
            return int(line.split()[1])
    raise AssertionError(f"no scanned-count line in output:\n{output}")


# ---------------------------------------------------------------------------
# T029: the red-test. The checker must be observed failing.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", [LGTM, CODEQL])
def test_seeded_marker_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    marker: str,
) -> None:
    """A marker in a comment exits 1 and names file, line and marker."""
    fixture = seed(tmp_path, "bad.py", f"x = 1  {HASH} {marker}\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 1
    resolved = str(fixture.resolve())
    assert resolved in out
    assert f"{resolved}:1" in out
    assert marker in out


def test_marker_without_introducer_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Control: the failure must come from the rule, not from the file."""
    seed(tmp_path, "ok.py", f'text = "{LGTM}"\n')

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 0, out


# ---------------------------------------------------------------------------
# T030: scanned nothing is not the same as found nothing.
# ---------------------------------------------------------------------------


def test_zero_files_exits_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    code, _ = run_in_process(monkeypatch, capsys, str(empty))

    assert code == 2
    assert code != 0, (
        "a scan that examined nothing must not report the same result as a "
        "scan that found nothing, or a moved root reads as a clean tree"
    )


# ---------------------------------------------------------------------------
# T031: self-exclusion is by exact path and by nothing else.
# ---------------------------------------------------------------------------


def test_self_exclusions_are_exactly_two_exact_paths() -> None:
    assert mod.SELF_EXCLUSIONS == frozenset(
        {
            Path("scripts/check_dead_suppressions.py"),
            Path("tests/unit/scripts/test_check_dead_suppressions.py"),
        }
    )
    assert len(mod.SELF_EXCLUSIONS) == 2


def test_same_basename_elsewhere_is_still_flagged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The exclusion is a path, not a basename glob."""
    seed(tmp_path, "check_dead_suppressions.py", f"x = 1  {HASH} {LGTM}\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 1, out


def test_paths_outside_the_repository_do_not_raise(tmp_path: Path) -> None:
    outside = tmp_path / "somewhere.py"
    outside.write_text("x = 1\n", encoding="utf-8")

    assert mod.repo_relative(outside) is None
    assert mod.is_self_excluded(outside) is False
    assert mod.display_path(outside) == str(outside.resolve())


# ---------------------------------------------------------------------------
# T032: the positional detection rule.
# ---------------------------------------------------------------------------


def test_marker_in_a_string_literal_does_not_fire() -> None:
    assert mod.marker_in_comment(f'value = "{LGTM}"') is None


def test_marker_in_a_url_does_not_fire() -> None:
    assert mod.marker_in_comment(f'link = "example.com/rules/{LGTM}"') is None


def test_scheme_prefixed_url_is_a_known_false_positive() -> None:
    """Documented consequence of keeping the loosest introducers.

    An absolute URL carries a slash pair, which is a comment introducer, so a
    marker later on that line matches. The contract's own summary claims URLs
    never match; that claim holds only for scheme-less URLs. Pinned here so the
    behaviour is a recorded limitation rather than a surprise.
    """
    assert mod.marker_in_comment(f'link = "https:{SLASHES}x.dev/{LGTM}"') == LGTM


@pytest.mark.parametrize("introducer", [HASH, SLASHES, HTML_OPEN, C_OPEN, DASHES])
def test_every_introducer_fires(introducer: str) -> None:
    assert mod.marker_in_comment(f"x = 1  {introducer} {LGTM}") == LGTM


@pytest.mark.parametrize("marker", [LGTM_UPPER, CODEQL_MIXED])
def test_detection_is_case_insensitive(marker: str) -> None:
    assert mod.marker_in_comment(f"x = 1  {HASH} {marker}") == marker


def test_extension_outside_the_allowlist_is_not_scanned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Prose describing a marker has to write it, so docs stay out."""
    seed(tmp_path, "notes.md", f"x = 1  {HASH} {LGTM}\n")
    seed(tmp_path, "real.py", "x = 1\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 0, out
    assert scanned_count(out) == 1


def test_skip_list_applies_under_an_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    seed(cache, "bad.py", f"x = 1  {HASH} {LGTM}\n")
    seed(tmp_path, "real.py", "x = 1\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 0, out
    assert scanned_count(out) == 1


# ---------------------------------------------------------------------------
# T033: the failure has to be actionable.
# ---------------------------------------------------------------------------


def test_failure_output_explains_itself(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = seed(tmp_path, "bad.py", f"x = 1  {HASH} {LGTM}\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 1
    assert str(fixture.resolve()) in out
    assert ":1" in out
    assert LGTM in out
    assert "suppress nothing" in out
    assert "dismissal workflow" in out


def test_clean_output_states_a_file_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed(tmp_path, "fine.py", "x = 1\n")

    code, out = run_in_process(monkeypatch, capsys, str(tmp_path))

    assert code == 0
    assert scanned_count(out) > 0


# ---------------------------------------------------------------------------
# T034: the exit-code contract through the command-line surface.
# ---------------------------------------------------------------------------


def test_cli_exits_zero_against_the_real_tree() -> None:
    result = run_cli([])
    assert result.returncode == 0, result.stdout + result.stderr


def test_cli_exits_one_on_a_seeded_root(tmp_path: Path) -> None:
    seed(tmp_path, "bad.py", f"x = 1  {HASH} {LGTM}\n")
    result = run_cli([], roots=str(tmp_path))
    assert result.returncode == 1, result.stdout + result.stderr


def test_cli_exits_two_on_an_empty_root(tmp_path: Path) -> None:
    result = run_cli([], roots=str(tmp_path))
    assert result.returncode == 2, result.stdout + result.stderr


def test_cli_runs_from_any_working_directory(tmp_path: Path) -> None:
    """The repository root comes from the script's own location."""
    result = run_cli([], cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_positional_arguments_do_not_narrow_the_scan() -> None:
    bare = run_cli([])
    narrowed = run_cli([str(SCRIPT)])

    assert bare.returncode == 0, bare.stdout + bare.stderr
    assert narrowed.returncode == 0, narrowed.stdout + narrowed.stderr
    assert scanned_count(narrowed.stdout) == scanned_count(bare.stdout)


# ---------------------------------------------------------------------------
# T035: the canary. Red the day somebody adds a marker to an audited root.
# ---------------------------------------------------------------------------


def test_default_roots_are_clean(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, out = run_in_process(monkeypatch, capsys, None)

    assert code == 0, out
    assert scanned_count(out) > 0
