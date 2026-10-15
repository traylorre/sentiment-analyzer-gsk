"""Unit tests for ``scripts/check-branch-collision.sh``.

Each test builds a scratch clone of a scratch bare origin with real git. ``gh`` is a stub on
``PATH`` that reports a PR only for the heads named in ``GH_PR_HEADS``. The pre-push suite runs
with git's hook environment exported, so every git child here runs with ``GIT_*`` stripped and
the user's git config ignored.

The origin holds ``card-7`` (a Hydrostat claim ref, no PR), ``orphan-branch`` (no PR),
``feature-with-pr`` and ``team/topic``. The clone is checked out on ``card-7`` with one commit
the origin lacks, as a card worktree is.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "check-branch-collision.sh"
HOOK_ID = "check-branch-collision"
GIT = shutil.which("git")
BASH = shutil.which("bash")

GH_STUB = """#!/bin/sh
head=
prev=
for arg in "$@"; do
    [ "$prev" = "--head" ] && head=$arg
    prev=$arg
done
case " $GH_PR_HEADS " in
    *" $head "*) echo 1 ;;
    *) echo 0 ;;
esac
"""


def scratch_env(tmp_path: Path) -> dict[str, str]:
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT"))
    }
    env.update(
        PATH=f"{tmp_path / 'bin'}{os.pathsep}{env['PATH']}",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.invalid",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.invalid",
        GH_PR_HEADS="feature-with-pr",
        PRE_COMMIT_HOME=str(tmp_path / "pre-commit-home"),
    )
    return env


def git(env: dict[str, str], cwd: Path, *args: str) -> str:
    assert GIT, "git is not on PATH"
    return subprocess.run(  # noqa: S603 - fixed argv
        [GIT, *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path):
    (tmp_path / "bin").mkdir()
    gh = tmp_path / "bin" / "gh"
    gh.write_text(GH_STUB)
    gh.chmod(0o755)
    env = scratch_env(tmp_path)

    origin, work = tmp_path / "origin.git", tmp_path / "work"
    git(env, tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(env, tmp_path, "init", "-q", "-b", "main", str(work))
    git(env, work, "remote", "add", "origin", str(origin))
    git(env, work, "commit", "-q", "--allow-empty", "-m", "base")
    for ref in ("main", "card-7", "orphan-branch", "feature-with-pr", "team/topic"):
        git(env, work, "push", "-q", "--no-verify", "origin", f"HEAD:refs/heads/{ref}")
    git(env, work, "checkout", "-q", "-b", "card-7")
    git(env, work, "commit", "-q", "--allow-empty", "-m", "card work")
    return work, env


def run_check(work: Path, env: dict[str, str], remote_branch: str | None = None):
    if remote_branch is not None:
        env = {
            **env,
            "PRE_COMMIT_REMOTE_NAME": "origin",
            "PRE_COMMIT_REMOTE_BRANCH": remote_branch,
            "PRE_COMMIT_LOCAL_BRANCH": "refs/heads/card-7",
        }
    assert BASH, "bash is not on PATH"
    return subprocess.run(  # noqa: S603 - fixed argv
        [BASH, str(SCRIPT)], cwd=work, env=env, capture_output=True, text=True
    )


def test_a_card_checkout_pushing_to_a_new_branch_passes(clone):
    result = run_check(*clone, "refs/heads/card-7-frontend-ci")
    assert result.returncode == 0, result.stdout
    assert "New branch 'card-7-frontend-ci' - safe to push" in result.stdout


def test_a_card_checkout_pushing_to_an_orphan_is_refused_naming_the_pushed_branch(
    clone,
):
    result = run_check(*clone, "refs/heads/orphan-branch")
    assert result.returncode == 1
    assert (
        "Branch 'orphan-branch' exists on remote but has no associated PR."
        in result.stdout
    )


def test_a_push_to_the_claim_ref_passes(clone):
    result = run_check(*clone, "refs/heads/card-7")
    assert result.returncode == 0, result.stdout
    assert "'card-7' is a Hydrostat claim ref - safe to push" in result.stdout


def test_a_push_to_a_branch_with_a_pr_passes(clone):
    result = run_check(*clone, "refs/heads/feature-with-pr")
    assert result.returncode == 0, result.stdout
    assert "Branch 'feature-with-pr' has PR - safe to push" in result.stdout


def test_a_tag_push_is_not_judged(clone):
    result = run_check(*clone, "refs/tags/v1")
    assert result.returncode == 0, result.stdout
    assert "'refs/tags/v1' is not a branch - nothing to check" in result.stdout


def test_a_branch_matching_only_the_tail_of_a_remote_branch_is_new(clone):
    result = run_check(*clone, "refs/heads/topic")
    assert result.returncode == 0, result.stdout
    assert "New branch 'topic' - safe to push" in result.stdout


def test_a_manual_run_judges_the_checked_out_branch(clone):
    work, env = clone
    git(env, work, "checkout", "-q", "orphan-branch")
    result = run_check(work, env)
    assert result.returncode == 1
    assert (
        "Branch 'orphan-branch' exists on remote but has no associated PR."
        in result.stdout
    )


def test_a_manual_run_from_a_card_checkout_passes(clone):
    result = run_check(*clone)
    assert result.returncode == 0, result.stdout
    assert "'card-7' is a Hydrostat claim ref - safe to push" in result.stdout


def test_git_push_through_pre_commit_judges_the_pushed_ref(clone):
    """The hook as the repo's own config declares it, run by real pre-commit under git push."""
    work, env = clone
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text())
    hook = next(
        h for repo in config["repos"] for h in repo["hooks"] if h["id"] == HOOK_ID
    )
    (work / "scripts").mkdir()
    shutil.copy2(SCRIPT, work / "scripts" / SCRIPT.name)
    (work / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [hook]}]})
    )
    git(env, work, "add", ".")
    git(env, work, "commit", "-q", "-m", "hook")
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-push"],
        cwd=work,
        env=env,
        check=True,
        capture_output=True,
    )

    def push(target: str):
        assert GIT, "git is not on PATH"
        return subprocess.run(  # noqa: S603 - fixed argv
            [GIT, "push", "origin", f"HEAD:refs/heads/{target}"],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
        )

    passed = push("card-7-frontend-ci")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert git(env, work, "ls-remote", "origin", "refs/heads/card-7-frontend-ci")

    git(env, work, "commit", "-q", "--allow-empty", "-m", "more card work")
    refused = push("orphan-branch")
    assert refused.returncode != 0
    assert "Branch 'orphan-branch' exists on remote but has no associated PR." in (
        refused.stdout + refused.stderr
    )
