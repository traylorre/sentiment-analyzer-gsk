"""Unit tests for ``scripts/check_security_alerts.py``.

No alert endpoint appears as a literal in this file. Every endpoint string is built from
``FAMILIES``, because a literal would be a restated query and ``--scan-copies`` would report this
module. Records are shaped like the live API's, trimmed to the fields the check reads.

``fetch`` is exercised through a stub ``gh`` on ``PATH``, which records its argv so the flags the
real ``gh`` needs are asserted. The live runs against GitHub are in
``specs/1402-prepush-alert-visibility/evidence.md``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys

import pytest

import scripts.check_security_alerts as mod

CODE_SCANNING, DEPENDABOT = mod.FAMILIES


def code_scanning_alert(number, state="fixed"):
    return {
        "number": number,
        "state": state,
        "rule": {"id": "py/clear-text-logging-sensitive-data"},
        "most_recent_instance": {"location": {"path": "src/lambdas/shared/logging.py"}},
    }


def dependabot_alert(number, state="fixed"):
    return {
        "number": number,
        "state": state,
        "security_advisory": {"severity": "high", "ghsa_id": "GHSA-vfj7-8cjw-p6xm"},
        "dependency": {
            "package": {"ecosystem": "npm", "name": "braces"},
            "manifest_path": "frontend/package-lock.json",
        },
    }


def with_floor(family, floor):
    return dataclasses.replace(family, floor=floor)


def with_path(family, label, path):
    fields = tuple(
        (name, path if name == label else old) for name, old in family.fields
    )
    return dataclasses.replace(family, fields=fields)


# --- dig ----------------------------------------------------------------------------


def test_dig_walks_nested_keys():
    assert mod.dig({"a": {"b": {"c": 3}}}, ("a", "b", "c")) == 3


def test_dig_returns_none_for_a_missing_key_or_a_non_mapping():
    assert mod.dig({"a": {}}, ("a", "b")) is None
    assert mod.dig({"a": "text"}, ("a", "b")) is None
    assert mod.dig(None, ("a",)) is None


# --- evaluate: floor and anchors ----------------------------------------------------


def test_clean_family_has_no_problems_and_no_open_alerts():
    records = [code_scanning_alert(n) for n in range(3)]
    result = mod.evaluate(with_floor(CODE_SCANNING, 3), records)
    assert result.problems == []
    assert result.verdict == mod.CLEAN
    assert result.examined == 3


def test_open_alerts_are_findings():
    records = [
        dependabot_alert(1, "open"),
        dependabot_alert(2),
        dependabot_alert(3, "open"),
    ]
    result = mod.evaluate(with_floor(DEPENDABOT, 3), records)
    assert result.verdict == mod.FINDINGS
    assert [r["number"] for r in result.open_alerts] == [1, 3]


def test_a_corpus_below_the_floor_is_undetermined_even_with_open_alerts():
    records = [code_scanning_alert(1, "open")]
    result = mod.evaluate(with_floor(CODE_SCANNING, 2), records)
    assert result.verdict == mod.UNDETERMINED
    assert any(
        p.startswith("corpus floor: fetched 1 records, floor is 2")
        for p in result.problems
    )


def test_an_empty_corpus_fails_the_floor():
    result = mod.evaluate(CODE_SCANNING, [])
    assert result.verdict == mod.UNDETERMINED
    assert any(p.startswith("corpus floor") for p in result.problems)


def test_an_unknown_state_fails_the_vocabulary_anchor():
    records = [dependabot_alert(1), dependabot_alert(2, "reopened")]
    result = mod.evaluate(with_floor(DEPENDABOT, 2), records)
    assert result.verdict == mod.UNDETERMINED
    assert any(
        "vocabulary anchor: 1 of 2" in p and "'reopened'" in p for p in result.problems
    )


def test_a_mistyped_state_field_fails_both_state_anchors():
    family = with_path(with_floor(DEPENDABOT, 2), "state", ("stat",))
    result = mod.evaluate(family, [dependabot_alert(1, "open"), dependabot_alert(2)])
    assert result.verdict == mod.UNDETERMINED
    assert any(p.startswith("vocabulary anchor: 2 of 2") for p in result.problems)
    assert any(p.startswith("field anchor 'state'") for p in result.problems)


def test_a_mistyped_projection_path_fails_its_field_anchor():
    family = with_path(
        with_floor(CODE_SCANNING, 2),
        "path",
        ("most_recent_instance", "locatio", "path"),
    )
    result = mod.evaluate(
        family, [code_scanning_alert(1, "open"), code_scanning_alert(2)]
    )
    assert result.verdict == mod.UNDETERMINED
    assert (
        "field anchor 'path': most_recent_instance.locatio.path resolves on 0 of 2 records"
        in result.problems
    )


def test_one_record_missing_a_field_fails_the_anchor():
    records = [dependabot_alert(1), dependabot_alert(2)]
    records[1]["dependency"]["manifest_path"] = ""
    result = mod.evaluate(with_floor(DEPENDABOT, 2), records)
    assert (
        "field anchor 'manifest': dependency.manifest_path resolves on 1 of 2 records"
        in (result.problems)
    )


def test_every_family_anchors_every_field_it_prints():
    for family in mod.FAMILIES:
        labels = [label for label, _ in family.fields]
        assert "state" in labels
        assert labels[0] == "number"


# --- check: verdict precedence and output -------------------------------------------


def fake_fetch(table):
    def fetch(repo, family):
        outcome = table[family.endpoint]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return fetch


def families_with_floor(floor):
    return tuple(with_floor(family, floor) for family in mod.FAMILIES)


def test_check_is_clean_only_when_every_family_is_clean(monkeypatch):
    monkeypatch.setattr(
        mod,
        "fetch",
        fake_fetch(
            {
                CODE_SCANNING.endpoint: [code_scanning_alert(1)],
                DEPENDABOT.endpoint: [dependabot_alert(1, "auto_dismissed")],
            }
        ),
    )
    verdict, lines = mod.check("o/r", families_with_floor(1))
    assert verdict == mod.CLEAN
    assert lines[-1].startswith("VERDICT: CLEAN (exit 0)")
    assert "2 records examined" in lines[-1]
    assert any("0 open of 1 records examined (floor 1)" in line for line in lines)


def test_findings_list_each_open_alert_by_its_fields(monkeypatch):
    monkeypatch.setattr(
        mod,
        "fetch",
        fake_fetch(
            {
                CODE_SCANNING.endpoint: [code_scanning_alert(144, "open")],
                DEPENDABOT.endpoint: [dependabot_alert(226, "open")],
            }
        ),
    )
    verdict, lines = mod.check("o/r", families_with_floor(1))
    assert verdict == mod.FINDINGS
    assert (
        "  #144  py/clear-text-logging-sensitive-data  src/lambdas/shared/logging.py"
        in lines
    )
    assert (
        "  #226  high  npm  braces  frontend/package-lock.json  GHSA-vfj7-8cjw-p6xm"
        in lines
    )


def test_one_unreadable_family_outranks_findings_in_the_other(monkeypatch):
    monkeypatch.setattr(
        mod,
        "fetch",
        fake_fetch(
            {
                CODE_SCANNING.endpoint: mod.Undetermined("gh exited 1: HTTP 403"),
                DEPENDABOT.endpoint: [dependabot_alert(1, "open")],
            }
        ),
    )
    verdict, lines = mod.check("o/r", families_with_floor(1))
    assert verdict == mod.UNDETERMINED
    assert "  - gh exited 1: HTTP 403" in lines
    assert not any(line.startswith("VERDICT: CLEAN") for line in lines)


# --- fetch through a stub gh ----------------------------------------------------------


@pytest.fixture
def stub_gh(tmp_path, monkeypatch):
    """Install a ``gh`` that prints ``stdout``, writes ``stderr`` and exits ``code``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_log = tmp_path / "argv.json"

    def install(stdout="", stderr="", code=0):
        script = bin_dir / "gh"
        script.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"open({str(argv_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.stderr.write({stderr!r})\n"
            f"sys.exit({code})\n"
        )
        script.chmod(0o755)
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        return argv_log

    return install


def test_fetch_joins_every_page_and_passes_paginate_and_slurp(stub_gh):
    pages = [[code_scanning_alert(3), code_scanning_alert(2)], [code_scanning_alert(1)]]
    argv_log = stub_gh(stdout=json.dumps(pages))
    records = mod.fetch("o/r", CODE_SCANNING)
    assert [r["number"] for r in records] == [3, 2, 1]
    argv = json.loads(argv_log.read_text())
    assert argv[:3] == ["api", "--paginate", "--slurp"]
    assert argv[3] == f"repos/o/r/{CODE_SCANNING.endpoint}?per_page=100"


def test_fetch_reports_gh_failure_with_its_first_stderr_line(stub_gh):
    stub_gh(stderr="gh: Bad credentials (HTTP 401)\nmore\n", code=1)
    with pytest.raises(
        mod.Undetermined, match=r"gh exited 1: gh: Bad credentials \(HTTP 401\)"
    ):
        mod.fetch("o/r", DEPENDABOT)


def test_fetch_rejects_output_that_is_not_json(stub_gh):
    stub_gh(stdout="<html>")
    with pytest.raises(mod.Undetermined, match="not JSON"):
        mod.fetch("o/r", DEPENDABOT)


def test_fetch_rejects_a_single_unslurped_page(stub_gh):
    stub_gh(stdout=json.dumps([dependabot_alert(1)]))
    with pytest.raises(mod.Undetermined, match="not a list of pages"):
        mod.fetch("o/r", DEPENDABOT)


def test_fetch_without_gh_is_undetermined(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(mod.Undetermined, match="gh is not installed"):
        mod.fetch("o/r", DEPENDABOT)


def test_main_exits_2_when_gh_fails(stub_gh, capsys):
    stub_gh(stderr="error connecting to api.github.com\n", code=1)
    assert mod.main(["--repo", "o/r"]) == mod.UNDETERMINED
    out = capsys.readouterr().out
    assert "VERDICT: COULD-NOT-DETERMINE (exit 2)" in out
    assert "VERDICT: CLEAN" not in out


def test_main_rejects_a_malformed_repo():
    with pytest.raises(SystemExit) as exc:
        mod.main(["--repo", "not a repo"])
    assert exc.value.code == 2


# --- scan_copies --------------------------------------------------------------------


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


@pytest.fixture
def tree(tmp_path):
    """A tree holding a copy of the real sanctioned script and one clean document."""
    sanctioned = (mod.REPO_ROOT / mod.SANCTIONED).read_text(encoding="utf-8")
    paths = [
        write(tmp_path, mod.SANCTIONED, sanctioned),
        write(
            tmp_path,
            "docs/notes.md",
            "Run `make check-security-alerts` before a push.\n",
        ),
    ]
    return tmp_path, paths


def restated(family):
    return f"gh api 'repos/o/r/{family.endpoint}?state=open&per_page=100' --jq length\n"


def test_a_clean_tree_anchors_on_the_sanctioned_script(tree):
    root, paths = tree
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.CLEAN
    endpoints = ", ".join(sorted(f.endpoint for f in mod.FAMILIES))
    assert f"anchored on {mod.SANCTIONED}: {endpoints}" in lines


@pytest.mark.parametrize("family", mod.FAMILIES, ids=lambda f: f.name)
def test_a_restated_query_is_reported_by_path_and_line(tree, family):
    root, paths = tree
    paths.append(write(root, "AGENTS.md", "intro\n" + restated(family)))
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.FINDINGS
    assert any(line.startswith("  AGENTS.md:2: gh api") for line in lines)


def test_a_single_alert_path_is_not_a_list_query(tree):
    root, paths = tree
    paths.append(
        write(root, "docs/x.md", f"gh api repos/o/r/{CODE_SCANNING.endpoint}/144\n")
    )
    assert mod.scan_copies(root, paths)[0] == mod.CLEAN


def test_excluded_prefixes_are_not_scanned(tree):
    root, paths = tree
    for prefix in mod.COPY_SCAN_EXCLUDED:
        paths.append(write(root, f"{prefix}x.md", restated(DEPENDABOT)))
    assert mod.scan_copies(root, paths)[0] == mod.CLEAN


def test_binary_files_are_skipped(tree):
    root, paths = tree
    (root / "img.png").write_bytes(b"\x89PNG\0" + restated(DEPENDABOT).encode())
    paths.append("img.png")
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.CLEAN
    assert "1 skipped" in lines[0]


def test_an_unreadable_file_is_undetermined(tree):
    root, paths = tree
    paths.append("docs/deleted.md")
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.UNDETERMINED
    assert any(line.startswith("  - cannot read docs/deleted.md") for line in lines)


def test_a_scan_that_misses_the_sanctioned_script_is_undetermined(tree):
    root, paths = tree
    paths.remove(mod.SANCTIONED)
    paths.append(write(root, "AGENTS.md", restated(DEPENDABOT)))
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.UNDETERMINED
    assert any("AGENTS.md:1" in line for line in lines)
    assert not any(line.startswith("VERDICT: CLEAN") for line in lines)


def test_a_sanctioned_script_missing_an_endpoint_is_undetermined(tree):
    root, paths = tree
    write(root, mod.SANCTIONED, f'endpoint = "{CODE_SCANNING.endpoint}"\n')
    verdict, lines = mod.scan_copies(root, paths)
    assert verdict == mod.UNDETERMINED
    assert any(f"does not find {DEPENDABOT.endpoint}" in line for line in lines)


def test_scan_copies_reads_tracked_files_through_git(tree, capsys):
    root, _ = tree
    write(root, "AGENTS.md", restated(CODE_SCANNING))
    write(root, "untracked.md", restated(DEPENDABOT))
    git = shutil.which("git")
    assert git, "git is not on PATH"
    subprocess.run([git, "init", "-q", str(root)], check=True)  # noqa: S603 - fixed argv
    subprocess.run(  # noqa: S603 - fixed argv
        [git, "-C", str(root), "add", mod.SANCTIONED, "docs/notes.md", "AGENTS.md"],
        check=True,
    )
    assert mod.main(["--scan-copies", "--root", str(root)]) == mod.FINDINGS
    out = capsys.readouterr().out
    assert "AGENTS.md:1" in out
    assert "untracked.md" not in out


def test_scan_copies_outside_a_repository_is_undetermined(tmp_path, capsys):
    assert mod.main(["--scan-copies", "--root", str(tmp_path)]) == mod.UNDETERMINED
    assert "git ls-files exited" in capsys.readouterr().out
