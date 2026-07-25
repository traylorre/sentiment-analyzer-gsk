# Target: Customer Dashboard (Next.js/Amplify) — backend surfacing
"""Feature 1380: OAuth avatar / profile picture surfacing + SSRF allowlist.

These tests pin the security-critical host allowlist in `_validate_avatar_url`
and the provider-selection logic in `_select_avatar`. The reject cases MUST fail
against a naive `endswith("googleusercontent.com")` or `"googleusercontent.com"
in url` implementation — that is the whole point (AR#3: highest-risk task).
"""

from datetime import UTC, datetime

import pytest

from src.lambdas.dashboard.auth import (
    OAuthCallbackResponse,
    _select_avatar,
    _validate_avatar_url,
)
from src.lambdas.shared.models.user import ProviderMetadata, User
from src.lambdas.shared.response_models import UserMeResponse

_GOOD = "https://lh3.googleusercontent.com/a/ACg8ocK...=s96-c"


def _user(**kwargs) -> User:
    now = datetime.now(UTC)
    base = {
        "user_id": "u-1",
        "email": "user@example.com",
        "auth_type": "google",
        "created_at": now,
        "last_active_at": now,
        "session_expires_at": now,
        "role": "free",
        "verification": "verified",
    }
    base.update(kwargs)
    return User(**base)


def _meta(avatar: str | None) -> ProviderMetadata:
    return ProviderMetadata(
        sub="s", email="user@example.com", avatar=avatar, linked_at=datetime.now(UTC)
    )


# --------------------------------------------------------------------------
# _validate_avatar_url — SSRF host allowlist
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _GOOD,
        "https://googleusercontent.com/a/x",  # exact host
        "https://lh4.googleusercontent.com/x",
        "https://play-lh.googleusercontent.com/x",
    ],
)
def test_accepts_google_hosts(url):
    assert _validate_avatar_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        # Lookalike: leading-dot boundary is load-bearing (naive endswith passes this).
        "https://evil-googleusercontent.com/x",
        # Suffix trick: hostname ends with .evil.com, not .googleusercontent.com.
        "https://googleusercontent.com.evil.com/x",
        "https://foo.googleusercontent.com.evil.com/x",
        # Path trick: hostname is evil.com (naive `in url` passes this).
        "https://evil.com/googleusercontent.com/x",
        # Non-https scheme.
        "http://lh3.googleusercontent.com/x",
        # Userinfo trick: .hostname yields evil.com, NOT googleusercontent.com.
        "https://googleusercontent.com@evil.com/x",
        "https://lh3.googleusercontent.com@evil.com/x",
        # Other dangerous schemes.
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "file:///etc/passwd",
        # Malformed / non-URL.
        "not a url",
        "",
    ],
)
def test_rejects_non_google(url):
    assert _validate_avatar_url(url) is None


def test_rejects_none_and_nonstring():
    assert _validate_avatar_url(None) is None
    assert _validate_avatar_url(12345) is None  # type: ignore[arg-type]


def test_uppercase_host_is_normalized_and_accepted():
    # urlparse lowercases the hostname; an uppercase Google host must still pass.
    url = "https://LH3.GOOGLEUSERCONTENT.COM/x"
    assert _validate_avatar_url(url) == url


def test_uppercase_lookalike_still_rejected():
    assert _validate_avatar_url("https://EVIL-GOOGLEUSERCONTENT.COM/x") is None


def test_trailing_dot_fqdn_accepted():
    # Trailing-dot FQDN form of a real Google host resolves to the same host.
    url = "https://lh3.googleusercontent.com./x"
    assert _validate_avatar_url(url) == url


def test_trailing_dot_lookalike_rejected():
    assert _validate_avatar_url("https://evil-googleusercontent.com./x") is None


# --------------------------------------------------------------------------
# _select_avatar — provider selection over persisted metadata
# --------------------------------------------------------------------------


def test_select_returns_google_avatar():
    u = _user(
        linked_providers=["google"],
        provider_metadata={"google": _meta(_GOOD)},
        last_provider_used="google",
    )
    assert _select_avatar(u) == _GOOD


def test_select_none_when_no_metadata():
    u = _user()
    assert _select_avatar(u) is None


def test_select_none_for_spoofed_stored_avatar():
    # Even a persisted spoofed avatar must fail closed at surface time.
    u = _user(
        linked_providers=["google"],
        provider_metadata={"google": _meta("https://evil-googleusercontent.com/x")},
        last_provider_used="google",
    )
    assert _select_avatar(u) is None


def test_select_prefers_last_provider_used():
    gh = (
        "https://avatars.githubusercontent.com/u/1"  # not allowlisted -> None if picked
    )
    u = _user(
        linked_providers=["google", "github"],
        provider_metadata={"google": _meta(_GOOD), "github": _meta(gh)},
        last_provider_used="google",
    )
    assert _select_avatar(u) == _GOOD


def test_select_falls_back_when_last_provider_has_no_avatar():
    u = _user(
        linked_providers=["github", "google"],
        provider_metadata={"github": _meta(None), "google": _meta(_GOOD)},
        last_provider_used="github",
    )
    # last_provider_used (github) has no avatar → fall back to google's.
    assert _select_avatar(u) == _GOOD


# --------------------------------------------------------------------------
# Response-model shape (FR-001, FR-002, FR-005) — additive, nullable
# --------------------------------------------------------------------------


def test_callback_response_carries_picture():
    resp = OAuthCallbackResponse(status="authenticated", picture=_GOOD)
    assert resp.model_dump()["picture"] == _GOOD


def test_callback_response_picture_defaults_null():
    resp = OAuthCallbackResponse(status="authenticated")
    dumped = resp.model_dump()
    assert "picture" in dumped
    assert dumped["picture"] is None


def test_userme_response_carries_picture():
    resp = UserMeResponse(auth_type="google", configs_count=0, picture=_GOOD)
    assert resp.model_dump()["picture"] == _GOOD


def test_userme_response_picture_defaults_null():
    resp = UserMeResponse(auth_type="email", configs_count=0)
    dumped = resp.model_dump()
    assert "picture" in dumped
    assert dumped["picture"] is None
