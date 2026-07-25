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
