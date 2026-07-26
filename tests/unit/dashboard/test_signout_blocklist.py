"""Unit tests for blocklist_refresh_token (zombie-session fix 2026-07-25).

sign_out backdated session_expires_at but the refresh endpoint never consults
session expiry, so a surviving refresh_token cookie kept re-minting app JWTs
after sign-out. The signout route now blocklists the presented token (checked
FIRST by refresh_access_tokens for every token type) and expires the cookies.
"""

import uuid
from unittest.mock import MagicMock

from src.lambdas.dashboard.auth import (
    blocklist_refresh_token,
    hash_refresh_token,
    is_token_blocklisted,
)


class TestBlocklistRefreshToken:
    def test_puts_blocklist_row_with_1188_key_shape(self) -> None:
        """Key must match what is_token_blocklisted reads (BLOCK#refresh#<hash>)."""
        table = MagicMock()
        user_id = str(uuid.uuid4())
        token = "eyJjdHkiOiJKV1Qi.fake.jwe"

        blocklist_refresh_token(table, token, user_id, reason="sign_out")

        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs["Item"]
        assert item["PK"] == f"BLOCK#refresh#{hash_refresh_token(token)}"
        assert item["SK"] == "BLOCK"
        assert item["reason"] == "sign_out"
        assert item["user_id"] == user_id
        assert isinstance(item["ttl_timestamp"], int)

    def test_blocklisted_token_is_detected_by_reader(self) -> None:
        """Round-trip: the row written is the row is_token_blocklisted finds."""
        store = {}
        table = MagicMock()
        table.put_item.side_effect = lambda Item: store.update({Item["PK"]: Item})
        table.get_item.side_effect = lambda Key, **kw: (
            {"Item": store[Key["PK"]]} if Key["PK"] in store else {}
        )
        token = "anon.some-user.secret"

        blocklist_refresh_token(table, token, "some-user", reason="sign_out")

        assert is_token_blocklisted(table, hash_refresh_token(token)) is True
        assert is_token_blocklisted(table, hash_refresh_token("other")) is False

    def test_write_failure_does_not_raise(self) -> None:
        """Silent-failure pattern: cookie expiry still covers the common case."""
        table = MagicMock()
        table.put_item.side_effect = RuntimeError("boom")

        blocklist_refresh_token(table, "tok", str(uuid.uuid4()))  # must not raise
