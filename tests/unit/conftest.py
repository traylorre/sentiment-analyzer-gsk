"""
Shared fixtures for ALL unit-test trees.
=========================================

Fixtures placed here apply to every test under ``tests/unit/`` (both
``tests/unit/dashboard/`` and ``tests/unit/lambdas/dashboard/``, plus the rest).
Keep this file small — dir-specific fixtures belong in the nearest ``conftest.py``.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_from_git_hook_environment(monkeypatch):
    """The pre-push hook runs this suite, and git exports GIT_DIR to it. From a linked
    worktree that GIT_DIR is ``<repo>/.git/worktrees/<name>``, and a test's ``git init``
    under it re-initialises the shared repository with ``core.bare = true``, breaking git
    in every checkout. Every git child of a unit test must act only on the repository its
    own arguments name.
    """
    for name in [name for name in os.environ if name.startswith("GIT_")]:
        monkeypatch.delenv(name)


@pytest.fixture(autouse=True)
def default_app_jwt_secret(monkeypatch):
    """Feature 1396: the OAuth callback and refresh now mint a first-party app JWT and
    fail closed when JWT_SECRET is unset (production always sets it). Multiple unit-test
    trees drive ``handle_oauth_callback`` / ``refresh_access_tokens`` (notably
    ``tests/unit/dashboard/`` and ``tests/unit/lambdas/dashboard/``), so provide the
    default here — the highest-scoped conftest that covers them all — instead of in a
    single dir's conftest.

    Only sets JWT_SECRET when it is UNSET, so tests that need a specific secret (via
    ``monkeypatch.setenv`` / ``patch.dict``) or that must exercise the UNSET fail-closed
    path (via ``monkeypatch.delenv`` / ``patch.dict(..., clear=True)``) still override it
    cleanly — function-scoped monkeypatch composes with this autouse set.
    """
    if "JWT_SECRET" not in os.environ:
        monkeypatch.setenv(
            "JWT_SECRET", "test-default-app-jwt-secret"
        )  # pragma: allowlist secret
