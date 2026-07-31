# Target: legacy-term scanner (Feature 001-validate-gate-repair)
"""Unit tests for ``scripts/check_banned_terms.py``.

NO LEGACY TERM APPEARS AS A LITERAL IN THIS FILE.

Every fixture string is derived from the ``BANNED_TERMS`` tuple imported from the
checker. Writing one out would make the scanner flag its own test module, and the
scanner is wired into a required, fail-closed CI job. The indirection is not stylistic.

It also buys a property a literal suite would not have: ``test_every_term_is_detected``
iterates the imported tuple, so a term added to the checker later is covered here
automatically rather than silently going untested.

All trees are built under ``tmp_path``. Nothing reads live repository state; the
equivalence check against the real corpus was a one-shot verification step recorded in
``specs/001-validate-gate-repair/baseline-corpus.txt``, deliberately not a test case,
because the cleanup phase drives that corpus to zero and the assertion would invert.
(not preprod)
"""

from __future__ import annotations

from pathlib import Path

import scripts.check_banned_terms as mod

TERM = mod.BANNED_TERMS[0]
MARKER = mod.MARKER_TOKEN


def write(root, rel_path, text):
    """Create a file at ``rel_path`` under ``root``, making parents as needed."""
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paths_found(root):
    """Canonical paths of the unexempted findings in ``root``."""
    return {m.path for m in mod.scan(root) if not m.is_exempt}


# --- happy path and basic detection ----------------------------------------


def test_clean_tree_produces_no_findings(tmp_path):
    write(tmp_path, "docs/notes.md", "This document mentions nothing retired.\n")
    write(tmp_path, "src/app.py", "def main():\n    return 0\n")

    assert mod.scan(tmp_path) == []


def test_violation_is_reported_with_path_and_line(tmp_path):
    write(
        tmp_path, "docs/notes.md", f"line one\nwe still run {TERM} here\nline three\n"
    )

    matches = mod.scan(tmp_path)

    assert len(matches) == 1
    assert matches[0].path == "docs/notes.md"
    assert matches[0].line_number == 2
    assert matches[0].is_exempt is False


def test_every_term_is_detected(tmp_path):
    """Covers the whole imported tuple, including any term added after this was written."""
    for index, term in enumerate(mod.BANNED_TERMS):
        write(tmp_path, f"docs/f{index}.md", f"reference to {term}\n")

    found = {m.path for m in mod.scan(tmp_path)}

    assert found == {f"docs/f{i}.md" for i in range(len(mod.BANNED_TERMS))}


def test_matching_is_case_insensitive(tmp_path):
    write(tmp_path, "docs/upper.md", f"{TERM.upper()}\n")

    assert paths_found(tmp_path) == {"docs/upper.md"}


def test_scan_does_not_stop_at_the_first_finding(tmp_path):
    """FR-012: one pass reports everything, so a fix round is not one-at-a-time."""
    write(tmp_path, "docs/a.md", f"{TERM}\n")
    write(tmp_path, "docs/b.md", f"{TERM}\n")
    write(tmp_path, "docs/c.md", f"{TERM}\n{TERM}\n")

    assert len(mod.scan(tmp_path)) == 4


# --- the two bugs the rewrite exists to kill -------------------------------


def test_content_mentioning_an_excluded_path_still_reports_itself(tmp_path):
    """Regression: the shell version applied exclusions to grep's whole output line.

    A file whose *content* named an excluded path suppressed its own finding. Here the
    path and the line text are separate fields, so a document that discusses an archived
    spec is still scanned normally.
    """
    excluded_prefix = mod.EXCLUDED_PATH_PREFIXES[0]
    write(
        tmp_path,
        "docs/inventory.md",
        f"See {excluded_prefix}old-spec/plan.md, which still names {TERM}.\n",
    )

    assert paths_found(tmp_path) == {"docs/inventory.md"}


def test_empty_term_list_fails_closed(tmp_path, monkeypatch):
    """FR-009: unable to detect is not the same as found nothing.

    The shell version built an empty ``grep -Ev`` pattern from an empty exclusion list,
    which matched every line, dropped every finding, and printed PASS over a repository
    with real violations. Reporting success is the most dangerous available direction.
    """
    monkeypatch.setattr(mod, "BANNED_TERMS", ())

    assert mod._validate_config() != []
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_empty_marker_token_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "MARKER_TOKEN", "")

    assert mod._validate_config() != []
    assert mod.main(["--root", str(tmp_path)]) == 1


def test_empty_exclusion_configuration_does_not_report_success(tmp_path, monkeypatch):
    """SC-006 / FR-009. The shell version's most dangerous failure mode.

    An empty exclusion list built an empty ``grep -Ev`` pattern, which matched every
    line, discarded every finding, and printed PASS over a repository with real
    violations. Emptying the exclusions here filters *nothing* instead of everything, so
    the dangerous direction is unreachable rather than guarded.

    This asserts the property rather than a guard, which is the point: there is no branch
    to regress, and the test exists so the absence of one reads as intended.
    """
    monkeypatch.setattr(mod, "EXCLUDED_PATH_PREFIXES", ())
    monkeypatch.setattr(mod, "EXCLUDED_FILENAME_PREFIXES", ())
    write(tmp_path, "docs/notes.md", f"{TERM}\n")

    assert mod.main(["--root", str(tmp_path)]) == 1
    assert paths_found(tmp_path) == {"docs/notes.md"}


def test_emptying_exclusions_widens_the_scan_rather_than_voiding_it(
    tmp_path, monkeypatch
):
    """The direction matters: fewer exclusions must mean more findings, never fewer."""
    prefix = mod.EXCLUDED_PATH_PREFIXES[0]
    write(tmp_path, f"{prefix}doc.md", f"{TERM}\n")

    assert mod.scan(tmp_path) == [], "normally excluded"

    monkeypatch.setattr(mod, "EXCLUDED_PATH_PREFIXES", ())

    assert paths_found(tmp_path) == {f"{prefix}doc.md"}


# --- exemption semantics ---------------------------------------------------


def test_marker_with_justification_exempts_the_line(tmp_path):
    write(
        tmp_path,
        "docs/history.md",
        f"we used to run {TERM} <!-- {MARKER} records the pre-migration runtime -->\n",
    )

    matches = mod.scan(tmp_path)

    assert len(matches) == 1
    assert matches[0].is_exempt is True
    assert matches[0].justification == "records the pre-migration runtime"


def test_marker_without_justification_does_not_exempt(tmp_path):
    """An unexplained exemption is not sanctioned; it is just a silenced finding."""
    write(tmp_path, "docs/history.md", f"we used to run {TERM} <!-- {MARKER} -->\n")

    matches = mod.scan(tmp_path)

    assert matches[0].has_marker is True
    assert matches[0].justification is None
    assert matches[0].is_exempt is False


def test_marker_exempts_only_its_own_line(tmp_path):
    write(
        tmp_path,
        "docs/history.md",
        f"retired {TERM} <!-- {MARKER} historical record -->\ncurrent {TERM}\n",
    )

    assert {(m.line_number, m.is_exempt) for m in mod.scan(tmp_path)} == {
        (1, True),
        (2, False),
    }


def test_marker_detection_is_case_insensitive(tmp_path):
    """The term match and the marker match are two separate patterns.

    ``test_matching_is_case_insensitive`` covers the term. This covers the marker, which
    is compiled independently, so one could lose ``re.IGNORECASE`` without the other
    noticing. A contributor who capitalises the token in prose should still be exempt.
    """
    write(
        tmp_path,
        "docs/history.md",
        f"we used to run {TERM} <!-- {MARKER.upper()} historical record -->\n",
    )

    matches = mod.scan(tmp_path)

    assert len(matches) == 1
    assert matches[0].is_exempt is True
    assert matches[0].justification == "historical record"


def test_marker_is_honoured_in_an_html_file(tmp_path):
    """FR-016 requires the marker to work in Markdown *and* HTML.

    Every other marker test writes HTML comment syntax into a ``.md`` file, which
    exercises the syntax but not the file type. After the board card is reworded there is
    no HTML exemption left anywhere in the repository, so the HTML half of FR-016 would
    otherwise be asserted and never executed. The checker is syntax-agnostic by design,
    so this test's real job is to keep that property from regressing into a Markdown
    special case.
    """
    write(
        tmp_path,
        "docs/board.html",
        f'<div class="card">retired {TERM}</div> <!-- {MARKER} archived board entry -->\n',
    )

    matches = mod.scan(tmp_path)

    assert len(matches) == 1
    assert matches[0].path == "docs/board.html"
    assert matches[0].is_exempt is True
    assert matches[0].justification == "archived board entry"


def test_comment_syntax_is_not_mistaken_for_a_justification(tmp_path):
    """``<!-- marker: -->`` must read as empty, not as the string ``-->``."""
    write(tmp_path, "docs/a.md", f"{TERM} <!-- {MARKER}   -->\n")
    write(tmp_path, "docs/b.md", f"{TERM} /* {MARKER}   */\n")

    assert paths_found(tmp_path) == {"docs/a.md", "docs/b.md"}


def test_justification_keeps_its_own_trailing_punctuation(tmp_path):
    """Terminators are stripped as whole tokens, not as a character set.

    ``str.rstrip("-->")`` removes any trailing run of ``-`` and ``>``, so a justification
    that legitimately ends in an arrow lost characters off its tail. Lint caught this;
    the original cases did not, because they all had a space before the terminator.
    """
    write(tmp_path, "docs/a.md", f"{TERM} <!-- {MARKER} superseded by A->B -->\n")

    matches = mod.scan(tmp_path)

    assert matches[0].justification == "superseded by A->B"


def test_justification_ends_at_the_terminator_not_at_end_of_line(tmp_path):
    """Regression: a marker inside a Markdown table cell is followed by ``|``.

    Suffix-stripping the terminator only worked when the comment ended the line. The
    single exemption this feature adds sits in a table cell, so the closing ``-->`` has
    ``|`` after it and nothing was stripped at all, putting comment and table syntax
    into the justification the listing prints.
    """
    write(
        tmp_path,
        "docs/table.md",
        f"| claim | {TERM} refuted below <!-- {MARKER} historical record --> |\n",
    )

    matches = mod.scan(tmp_path)

    assert matches[0].justification == "historical record"
    assert matches[0].is_exempt is True


def test_one_marker_covering_several_terms_counts_once(tmp_path):
    """The exemption unit is the marker, not the match.

    A line naming two banned terms produces two Match objects but carries one
    justification. Counting matches inflates the SC-012 exemption baseline, so a line
    would register as growth in the exemption surface for saying two words.
    """
    two_terms = f"{mod.BANNED_TERMS[0]} and {mod.BANNED_TERMS[1]}"
    write(
        tmp_path,
        "docs/history.md",
        f"the stack once ran {two_terms} <!-- {MARKER} migration record -->\n",
    )

    matches = mod.scan(tmp_path)
    assert len(matches) == 2, "fixture should produce one match per term"
    assert all(m.is_exempt for m in matches)

    assert mod.main(["--root", str(tmp_path), "--list-exemptions"]) == 0


def test_list_exemptions_reports_one_line_once(tmp_path, capsys):
    two_terms = f"{mod.BANNED_TERMS[0]} and {mod.BANNED_TERMS[1]}"
    write(
        tmp_path,
        "docs/history.md",
        f"once ran {two_terms} <!-- {MARKER} migration record -->\n",
    )

    mod.main(["--root", str(tmp_path), "--list-exemptions"])
    out = capsys.readouterr().out

    assert out.count("docs/history.md:1") == 1
    assert "Total: 1" in out


# --- FR-028: trees where a marker is itself an error -----------------------


def test_marker_is_refused_under_application_source(tmp_path):
    """Exemptions record that a framework was retired. Code does not hold records."""
    for prefix in mod.MARKER_REFUSED_PREFIXES:
        write(
            tmp_path,
            f"{prefix}mod_{prefix.strip('/').replace('/', '_')}.py",
            f"# {TERM} <!-- {MARKER} a justification that must not be honoured -->\n",
        )

    matches = mod.scan(tmp_path)

    assert matches, "fixture built no scannable files"
    assert all(m.marker_is_refused for m in matches)
    assert all(not m.is_exempt for m in matches)


def test_refused_marker_is_reported_as_its_own_error(tmp_path, capsys):
    """SC-013. The message must name the MARKER as the error, not the term.

    A refused marker that reported as an ordinary violation would read as though the
    marker were malformed, and the contributor's next move would be to fix its syntax.
    That move cannot succeed, because there is no syntax that works here. The distinct
    message is what stops that loop.
    """
    prefix = mod.MARKER_REFUSED_PREFIXES[0]
    write(tmp_path, f"{prefix}app.py", f"# {TERM}  # {MARKER} a plausible reason\n")

    code = mod.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    assert "exemption markers are not permitted" in out
    assert "FR-028" in out
    assert f"{prefix}app.py:1" in out


def test_ordinary_source_violation_does_not_get_the_marker_message(tmp_path, capsys):
    """The two remedies must stay distinguishable, or the distinct message is noise."""
    prefix = mod.MARKER_REFUSED_PREFIXES[0]
    write(tmp_path, f"{prefix}app.py", f"# {TERM}\n")

    mod.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert "exemption markers are not permitted" not in out
    assert "this is application source" in out


def test_marker_is_honoured_in_the_documentation_exception(tmp_path):
    """``infrastructure/docs/`` is a record tree inside a refused prefix."""
    exception = mod.MARKER_REFUSED_EXCEPTIONS[0]
    write(
        tmp_path,
        f"{exception}history.md",
        f"the stack once used {TERM} <!-- {MARKER} migration record -->\n",
    )

    matches = mod.scan(tmp_path)

    assert len(matches) == 1
    assert matches[0].marker_is_refused is False
    assert matches[0].is_exempt is True


# --- scan scoping ----------------------------------------------------------


def test_excluded_path_prefixes_are_not_scanned(tmp_path):
    for prefix in mod.EXCLUDED_PATH_PREFIXES:
        write(tmp_path, f"{prefix}doc.md", f"{TERM}\n")

    assert mod.scan(tmp_path) == []


def test_excluded_directory_names_are_skipped_at_any_depth(tmp_path):
    excluded_dir = sorted(mod.EXCLUDED_DIR_NAMES)[0]
    write(tmp_path, f"{excluded_dir}/doc.md", f"{TERM}\n")
    write(tmp_path, f"deep/nested/{excluded_dir}/doc.md", f"{TERM}\n")

    assert mod.scan(tmp_path) == []


def test_carryover_files_are_skipped_including_suffixed_spellings(tmp_path):
    """The shell glob missed ``CONTEXT-CARRYOVER.md.loaded`` (no dash after the prefix).

    With this checker in a required fail-closed job, one such file holding a term would
    block every merge in the repository.
    """
    prefix = mod.EXCLUDED_FILENAME_PREFIXES[0]
    for name in (f"{prefix}.md", f"{prefix}.md.loaded", f"{prefix}-abc123.md.stable"):
        write(tmp_path, name, f"{TERM}\n")

    assert mod.scan(tmp_path) == []


def test_the_checkers_own_files_are_not_reported(tmp_path):
    """Both checkers enumerate the terms in order to search for them."""
    for self_path in mod.CHECKER_SELF_PATHS:
        write(tmp_path, self_path, f"terms = ({TERM},)\n")

    assert mod.scan(tmp_path) == []


# --- robustness ------------------------------------------------------------


def test_undecodable_and_binary_files_do_not_crash_the_scan(tmp_path):
    """The repository holds a SQLite coverage database and editor swap files.

    An unguarded text read raises on the first one, and a crash inside a fail-closed
    required job is a repository-wide merge outage rather than a failed check.
    """
    (tmp_path / "data.bin").write_bytes(b"\xfe\xed\xfa\xce\x00\xff")
    (tmp_path / "nul.dat").write_bytes(TERM.encode() + b"\x00" + TERM.encode())
    write(tmp_path, "docs/real.md", f"{TERM}\n")

    assert paths_found(tmp_path) == {"docs/real.md"}


def test_result_is_independent_of_how_the_root_is_spelled(tmp_path):
    """FR-027: exclusions in the shell version worked only because grep emitted ``./``.

    Changing the scan root would have disabled every exclusion at once, silently.
    """
    write(tmp_path, "docs/notes.md", f"{TERM}\n")
    write(tmp_path, f"{mod.EXCLUDED_PATH_PREFIXES[0]}doc.md", f"{TERM}\n")

    direct = mod.scan(tmp_path)
    indirect = mod.scan(tmp_path / "docs" / "..")

    assert [(m.path, m.line_number) for m in direct] == [
        (m.path, m.line_number) for m in indirect
    ]
    assert [m.path for m in direct] == ["docs/notes.md"]


def test_relative_and_absolute_roots_produce_identical_results(tmp_path, monkeypatch):
    """FR-027 for the case a caller actually hits: ``--root .`` from a shell.

    ``test_result_is_independent_of_how_the_root_is_spelled`` compares two absolute
    spellings. This compares an absolute root against a relative one, which is the form
    the Makefile and a developer at a prompt both use, and the form under which the
    shell version's exclusions silently stopped working: they matched only because GNU
    grep emitted a ``./`` prefix.
    """
    write(tmp_path, "docs/notes.md", f"{TERM}\n")
    write(tmp_path, f"{mod.EXCLUDED_PATH_PREFIXES[0]}doc.md", f"{TERM}\n")

    absolute = mod.scan(tmp_path)

    monkeypatch.chdir(tmp_path)
    relative = mod.scan(Path("."))

    key = lambda ms: [(m.path, m.line_number, m.term) for m in ms]  # noqa: E731
    assert key(absolute) == key(relative)
    assert [m.path for m in relative] == ["docs/notes.md"]


def test_symlinks_are_not_followed(tmp_path):
    """A symlink out of the tree would break the relative_to() canonicalisation."""
    write(tmp_path, "docs/real.md", f"{TERM}\n")
    (tmp_path / "link.md").symlink_to(tmp_path / "docs" / "real.md")

    assert [m.path for m in mod.scan(tmp_path)] == ["docs/real.md"]


# --- CLI surface -----------------------------------------------------------


def test_main_exits_zero_on_a_clean_tree(tmp_path):
    write(tmp_path, "docs/notes.md", "nothing retired here\n")

    assert mod.main(["--root", str(tmp_path)]) == 0


def test_main_exits_one_on_an_unexempted_finding(tmp_path):
    write(tmp_path, "docs/notes.md", f"{TERM}\n")

    assert mod.main(["--root", str(tmp_path)]) == 1


def test_main_exits_zero_when_every_finding_is_exempt(tmp_path):
    write(tmp_path, "docs/notes.md", f"{TERM} <!-- {MARKER} historical record -->\n")

    assert mod.main(["--root", str(tmp_path)]) == 0


def test_list_exemptions_enumerates_and_exits_zero(tmp_path, capsys):
    """FR-026: the sanctioned set has one mechanism, so this listing is complete."""
    write(tmp_path, "docs/a.md", f"{TERM} <!-- {MARKER} first record -->\n")
    write(tmp_path, "docs/b.md", f"{TERM}\n")

    code = mod.main(["--root", str(tmp_path), "--list-exemptions"])
    out = capsys.readouterr().out

    assert code == 0
    assert "docs/a.md:1" in out
    assert "first record" in out
    assert "docs/b.md" not in out, "unexempted findings are not exemptions"
    assert "Total: 1" in out


def test_failure_output_names_the_file_and_offers_a_remedy(tmp_path, capsys):
    write(tmp_path, "docs/notes.md", f"{TERM}\n")

    mod.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert "docs/notes.md:1" in out
    assert "remedy" in out
    assert MARKER in out, "the remedy should show the marker syntax"
