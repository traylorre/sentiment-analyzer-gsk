# Feature Specification: Unit suite ignores the git hook environment

**Feature Branch**: `card-21`
**Created**: 2026-10-15
**Status**: Implemented
**Card**: `cards/21.json`

## Problem

A push from any linked worktree set `core.bare = true` in the shared repository's `.git/config`, and
every git command in the root checkout and every card worktree then failed with
`fatal: this operation must be run in a work tree`. It happened twice during card 17.

The chain, under git 2.43.0:

1. git exports `GIT_DIR=<repo>/.git/worktrees/<name>` to a pre-push hook run from a linked worktree. From
   the root checkout it exports `GIT_DIR=.git`, which does no harm.
2. The pre-push stage runs `pytest tests/unit` (hook `pytest`, `.pre-commit-config.yaml:142`).
3. `test_scan_copies_reads_tracked_files_through_git` (`tests/unit/scripts/test_check_security_alerts.py`)
   runs `git init -q <tmp root>` with the environment inherited. Under a linked worktree's `GIT_DIR`, git
   re-initialises that repository and writes `core.bare = true` into the shared config.

Reproduced at `27019bac` against a scratch repository and linked worktree:
`GIT_DIR=<scratch>/.git/worktrees/w python -m pytest <that test>` reported `1 passed`, and the scratch
repository's `core.bare` went from `false` to `true`. A green suite is therefore no evidence that the
repository survived.

## Decision

An autouse fixture in `tests/unit/conftest.py`, `isolate_from_git_hook_environment`, deletes every
`GIT_*` variable before each unit test. The test's own git calls and the module's `git ls-files` both
inherit `os.environ`, so one fixture covers both. Each git child then acts only on the repository its
arguments name.

Rejected:

- Passing a cleaned `env=` to the one test's subprocess calls. That leaves the module's `git ls-files`,
  and every git-invoking unit test written later, exposed.
- `env -u GIT_DIR` in the pre-push hook's entry. That covers one runner. The conftest covers every
  runner of the unit suite, including `make test-unit` started from inside any other git hook.
- Deleting only `GIT_DIR`. githooks(5) says hooks receive "GIT_DIR, GIT_WORK_TREE, etc." and tells a
  hook running git elsewhere to clear `git rev-parse --local-env-vars`. Under git 2.43.0 that list has
  15 names, every one prefixed `GIT_`, so deleting the prefix covers it.
- Deleting `git rev-parse --local-env-vars` itself. It costs a git process per test or a cached list
  read once, for no case the prefix misses. No unit test reads a `GIT_*` variable
  (`grep -rn GIT_ tests/unit` before this card found none), so the wider deletion breaks nothing.

## Verification

- `tests/unit/test_git_hook_environment.py` builds a scratch repository with a linked worktree. It runs
  the git-invoking test in a child pytest with `GIT_DIR` set to that worktree's gitdir, as the hook
  would, and asserts the child passes and the scratch repository's `core.bare` stays `false`.
- Mutant: with the fixture's `monkeypatch.delenv(name)` replaced by `pass`, the regression test fails on
  `AssertionError: assert 'true' == 'false'`. Restored, it passes.
- End to end: see "Pre-push proof" below.

## Pre-push proof

A scratch bare remote and a clone of `331a0562` whose `origin` is that remote. The clone's `.venv` links
the root checkout's venv, it has pre-commit's pre-push hook installed over a legacy hook that prints
`$GIT_DIR`, and it has a linked worktree `wt`. Each push sends one new commit from `wt`, because
pre-commit's pre-push runs nothing for a push that carries no commit the remote lacks.

| Push from `wt` | Legacy hook printed | Pre-push result | Clone `core.bare` after |
|---|---|---|---|
| card 21 tip | `GIT_DIR=<clone>/.git/worktrees/wt` | pytest, collision and ERROR-log hooks Passed; push exit 0 | `false` |
| fixture disabled (mutant) | same | `1 failed, 2044 passed`; push refused, exit 1 | `true` |

The mutant's failure is `test_scan_copies_reads_tracked_files_through_git`: `main` returned
UNDETERMINED (2) where FINDINGS (1) was expected. Its `git ls-files` listed the clone's own tracked
files and reported each as `cannot read` under the test's temporary root. The real repository read
`core.bare = false` after both pushes.

## Land gate

The land gate's `make test-unit` receives no `GIT_DIR` from git. hydrostat starts the gate itself, with
cwd set to the card worktree and an environment equal to its own minus `FILTER`, `BENCH_MIN_SUITES` and
`ONLY` (`run_gate` in `~/dotfiles/tools/hydrostat.py`, `GATE_ENV_DROP`). The fixture makes the answer
irrelevant to this defect either way.

## Census command

Tests that invoke git, as of `331a0562`:
`grep -rlE 'subprocess|check_output' tests | xargs grep -lE "\"git\"|'git'|which\(\"git\"\)"`
lists `tests/unit/scripts/test_check_security_alerts.py` and this card's
`tests/unit/test_git_hook_environment.py`. Both are under `tests/unit/`, which the fixture covers.
