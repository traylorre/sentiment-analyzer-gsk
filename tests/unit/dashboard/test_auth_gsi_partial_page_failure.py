# Target: Admin Dashboard (Lambda HTMX) backend auth helpers
"""Feature 1395 (fail-closed amendment): identity lookups must PROVE completeness or raise.

`_query_users_by_index` pages the identity GSIs. It may only return a result when it has
scanned the key range to exhaustion. Any condition under which completeness cannot be
proven MUST raise `IdentityLookupError` so the OAuth callback fails closed (5xx) instead of
reading a false "no account" and minting a DUPLICATE record (K-3 / CWE-636 — the exact
mechanism behind the live prod duplicates).

This file pins the three incompleteness classes:
- a page-query failure on ANY page (including page 1) -> raise (was: return None/partial);
- a `max_pages` cap trip with pagination unfinished -> WARN + raise (FR-013);
- a malformed (truthy non-dict) pagination cursor -> raise immediately (FR-014 / K-1
  infinite-loop regression pin; must complete in ms, not hang).

The WIP's `test_partial_failure_prefers_the_earliest_created_at_among_what_was_resolved`
and the O-1 "keep the partial result" rationale are DELETED: a partial result feeds
canonical selection a truncated set, so the resolved identity depends on which pages
happened to succeed and flaps across refreshes (refuter R-8).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.lambdas.dashboard.auth import (
    IdentityLookupError,
    get_user_by_cognito_sub,
    get_user_by_email_gsi,
    get_user_by_provider_sub,
)
from src.lambdas.shared.models.user import User

EMAIL = "paginated.user@example.com"
COGNITO_SUB = "cognito-sub-abcdef123456"
PROVIDER = "google"

_LOOKUPS = [
    (get_user_by_email_gsi, (EMAIL,)),
    (get_user_by_cognito_sub, (COGNITO_SUB,)),
    (get_user_by_provider_sub, (PROVIDER, COGNITO_SUB)),
]
_LOOKUP_IDS = ["by_email", "by_cognito_sub", "by_provider_sub"]


def _make_user_item(*, created_at: datetime, email: str = EMAIL) -> dict:
    user = User(
        user_id=str(uuid4()),
        email=email,
        auth_type=PROVIDER,
        created_at=created_at,
        last_active_at=created_at,
        session_expires_at=created_at + timedelta(days=30),
        cognito_sub=COGNITO_SUB,
        provider_sub=f"{PROVIDER}:{COGNITO_SUB}",
    )
    return user.to_dynamodb_item()


class _FailOnPageTable:
    """Emulated GSI query that raises once pagination reaches ``fail_on_page``.

    Pages are served in order; every page except the last advertises a
    ``LastEvaluatedKey`` (a non-empty dict — a valid cursor), so the helper is obliged to
    keep paging straight into the failure. ``calls`` records how many queries were
    attempted.
    """

    def __init__(self, pages: list[list[dict]], *, fail_on_page: int):
        self._pages = pages
        self._fail_on_page = fail_on_page
        self.calls = 0

    def query(self, **kwargs):
        start = kwargs.get("ExclusiveStartKey")
        idx = start["_page"] if start else 0
        self.calls += 1
        if idx + 1 == self._fail_on_page:
            raise RuntimeError("ProvisionedThroughputExceededException (simulated)")

        wanted_type = kwargs["ExpressionAttributeValues"][":type"]
        page = self._pages[idx]
        result = {"Items": [i for i in page if i.get("entity_type") == wanted_type]}
        if idx + 1 < len(self._pages):
            result["LastEvaluatedKey"] = {"_page": idx + 1}
        return result


class _NeverExhaustsTable:
    """Emulated GSI query that ALWAYS advertises a fresh (valid dict) cursor.

    Forces the ``max_pages`` cap to trip: the key range never exhausts, so a bounded
    scanner must WARN and raise rather than loop or truncate.
    """

    def __init__(self):
        self.calls = 0

    def query(self, **kwargs):
        self.calls += 1
        return {"Items": [], "LastEvaluatedKey": {"_page": self.calls}}


class _MalformedCursorTable:
    """Emulated GSI query whose ``LastEvaluatedKey`` is a truthy NON-dict.

    Mirrors refuter K-1: a bare ``MagicMock`` table's ``.get(...)`` is truthy forever, so
    an unguarded loop spins to a Lambda timeout (rc=124). The FR-014 type guard must raise
    on the first page — this test must complete in milliseconds.
    """

    def __init__(self):
        self.calls = 0

    def query(self, **kwargs):
        self.calls += 1
        return {"Items": [], "LastEvaluatedKey": MagicMock()}


@pytest.mark.parametrize(("lookup", "args"), _LOOKUPS, ids=_LOOKUP_IDS)
def test_page_one_failure_raises_identity_lookup_error(lookup, args):
    """A page-1 query failure MUST raise (was K-3: returned None -> minted a duplicate)."""
    table = _FailOnPageTable(
        [[_make_user_item(created_at=datetime.now(UTC))]], fail_on_page=1
    )

    with pytest.raises(IdentityLookupError):
        lookup(table, *args)

    assert table.calls == 1


@pytest.mark.parametrize(("lookup", "args"), _LOOKUPS, ids=_LOOKUP_IDS)
def test_later_page_failure_raises_identity_lookup_error(lookup, args):
    """A failure on a LATER page MUST raise — no partial survivors (refuter R-8)."""
    user_item = _make_user_item(created_at=datetime.now(UTC))
    table = _FailOnPageTable([[user_item], [user_item]], fail_on_page=2)

    with pytest.raises(IdentityLookupError):
        lookup(table, *args)

    assert table.calls == 2, "helper must have attempted the second page before raising"


@pytest.mark.parametrize(("lookup", "args"), _LOOKUPS, ids=_LOOKUP_IDS)
def test_cap_trip_raises_and_warns(lookup, args, caplog):
    """Pagination that never exhausts MUST WARN then raise at the cap (FR-013)."""
    import logging

    table = _NeverExhaustsTable()

    with caplog.at_level(logging.WARNING), pytest.raises(IdentityLookupError):
        lookup(table, *args)

    # Cap is 10 pages: the 10th page still advertises a cursor -> raise.
    assert table.calls == 10
    assert any(
        "max_pages" in rec.getMessage() or "cap" in rec.getMessage()
        for rec in caplog.records
    ), "FR-013 requires a sanitized WARN on cap trip"


@pytest.mark.parametrize(("lookup", "args"), _LOOKUPS, ids=_LOOKUP_IDS)
def test_malformed_cursor_raises_immediately(lookup, args):
    """A truthy non-dict cursor MUST raise on the first page (FR-014 / K-1 regression).

    Must complete in milliseconds — the WIP looped forever here (rc=124).
    """
    table = _MalformedCursorTable()

    with pytest.raises(IdentityLookupError):
        lookup(table, *args)

    assert table.calls == 1, "must fail closed on the first malformed cursor, not loop"
