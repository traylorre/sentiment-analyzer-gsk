"""The unit suite run under a linked worktree's pre-push environment.

git exports ``GIT_DIR=<repo>/.git/worktrees/<name>`` to a pre-push hook run from a linked
worktree, and the hook runs this suite. This test reproduces that environment against a scratch
repository and runs the suite's git-invoking test in a child pytest, as the hook would.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GIT_INVOKING_TEST = (
    "tests/unit/scripts/test_check_security_alerts.py"
    "::test_scan_copies_reads_tracked_files_through_git"
)


def git(*args: str) -> str:
    executable = shutil.which("git")
    assert executable, "git is not on PATH"
    return subprocess.run(  # noqa: S603 - fixed argv
        [executable, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def test_a_linked_worktree_git_dir_leaves_its_repository_non_bare(tmp_path):
    repo, worktree = tmp_path / "repo", tmp_path / "worktree"
    git("init", "-q", str(repo))
    git(
        "-C",
        str(repo),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "base",
    )
    git("-C", str(repo), "worktree", "add", "-q", str(worktree), "-b", "linked")
    hook_git_dir = git(
        "-C", str(worktree), "rev-parse", "--path-format=absolute", "--git-dir"
    )
    assert hook_git_dir == str(repo / ".git" / "worktrees" / "worktree")

    child = subprocess.run(  # noqa: S603 - fixed argv
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={tmp_path / 'child'}",
            GIT_INVOKING_TEST,
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "GIT_DIR": hook_git_dir},
        capture_output=True,
        text=True,
        check=False,
    )

    assert child.returncode == 0, child.stdout + child.stderr
    assert git("config", "--file", str(repo / ".git" / "config"), "core.bare") == (
        "false"
    )
