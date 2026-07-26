"""Unit tests for _email_verified_claim_is_true (preprod 2026-07-25 incident).

Cognito re-emits mapped IdP attributes on federated id_tokens as the strings
"true"/"false"; native flows use a real boolean. A bare truthiness check
treats "false" as verified, and a missing mapping means the claim is absent
entirely (the state that produced free:none rows and duplicate minting).
"""

import pytest

from src.lambdas.dashboard.auth import _email_verified_claim_is_true


class TestEmailVerifiedClaim:
    @pytest.mark.parametrize(
        ("claims", "expected"),
        [
            ({"email_verified": True}, True),
            ({"email_verified": False}, False),
            ({"email_verified": "true"}, True),
            ({"email_verified": "True"}, True),
            ({"email_verified": " true "}, True),
            ({"email_verified": "false"}, False),
            ({"email_verified": "False"}, False),
            ({"email_verified": ""}, False),
            ({}, False),
            ({"email_verified": None}, False),
            ({"email_verified": 1}, True),
            ({"email_verified": 0}, False),
        ],
    )
    def test_claim_normalization(self, claims: dict, expected: bool) -> None:
        assert _email_verified_claim_is_true(claims) is expected
