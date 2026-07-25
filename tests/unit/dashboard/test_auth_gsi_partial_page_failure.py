# Target: Admin Dashboard (Lambda HTMX) backend auth helpers
"""Feature 1395 / finding O-1: a mid-pagination failure must not erase found USERs.

`_query_users_by_index` pages the identity GSIs to full exhaustion. If the `try` wraps
the whole loop, a failure on page N discards every USER already resolved on pages
1..N-1 and the helper returns `None`. The OAuth callback reads that `None` as "this
human has no account" and mints a DUPLICATE record — a transient DynamoDB error turned
into permanent identity fragmentation, which is the exact failure this feature exists
to stop.

These tests pin the correct scoping: keep what was already resolved, stop paginating,
log the failure and the partial-result degradation. The FR-010 contract (a lookup that
resolved nothing returns `None`, never raises) is pinned alongside it, since the safe
fix must not quietly widen the error contract for the other 7 call sites.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.lambdas.dashboard.auth import (
    get_user_by_cognito_sub,
    get_user_by_email_gsi,
    get_user_by_provider_sub,
)
from src.lambdas.shared.models.user import User

EMAIL = "paginated.user@example.com"
COGNITO_SUB = "cognito-sub-abcdef123456"
PROVIDER = "google"


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
    """Emulated GSI query that raises once pagination reaches `fail_on_page`.

    Pages are served in order; every page except the last advertises a
    `LastEvaluatedKey`, so the helper is obliged to keep paging straight into the
    failure. `calls` records how many queries were attempted.
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


@pytest.mark.parametrize(
    ("lookup", "args"),
    [
        (get_user_by_email_gsi, (EMAIL,)),
        (get_user_by_cognito_sub, (COGNITO_SUB,)),
        (get_user_by_provider_sub, (PROVIDER, COGNITO_SUB)),
    ],
    ids=["by_email", "by_cognito_sub", "by_provider_sub"],
)
def test_user_found_on_earlier_page_survives_a_later_page_failure(lookup, args):
    """O-1: page 1 resolved a USER, page 2 blows up — the USER must still be returned.

    Against the pre-fix scoping (one `try` around the whole loop) this returns `None`,
    which is the duplicate-minting path.
    """
    user_item = _make_user_item(created_at=datetime.now(UTC))
    table = _FailOnPageTable([[user_item], [user_item]], fail_on_page=2)

    result = lookup(table, *args)

    assert table.calls == 2, "helper must have attempted the second page"
    assert result is not None, (
        "a transient failure on a later page must not erase the USER already resolved "
        "— returning None here is what mints a duplicate account"
    )
    assert result.user_id == user_item["user_id"]


@pytest.mark.parametrize(
    ("lookup", "args"),
    [
        (get_user_by_email_gsi, (EMAIL,)),
        (get_user_by_cognito_sub, (COGNITO_SUB,)),
        (get_user_by_provider_sub, (PROVIDER, COGNITO_SUB)),
    ],
    ids=["by_email", "by_cognito_sub", "by_provider_sub"],
)
def test_failure_on_the_first_page_still_returns_none_without_raising(lookup, args):
    """FR-010 contract is unchanged: nothing resolved -> log and return None.

    The O-1 fix must not widen the error contract; 7 existing call sites (registration,
    magic link, password reset, router_v2) depend on `None` rather than an exception.
    """
    table = _FailOnPageTable(
        [[_make_user_item(created_at=datetime.now(UTC))]], fail_on_page=1
    )

    result = lookup(table, *args)

    assert table.calls == 1
    assert result is None


def test_partial_failure_prefers_the_earliest_created_at_among_what_was_resolved():
    """Canonical selection still applies to a partial result set (degraded, not wrong).

    The earliest record on the pages we did read wins. The helper logs the result set as
    incomplete so the degraded pick is observable rather than silent.
    """
    now = datetime.now(UTC)
    oldest = _make_user_item(created_at=now - timedelta(hours=3))
    newer = _make_user_item(created_at=now)
    table = _FailOnPageTable([[newer], [oldest], [newer]], fail_on_page=3)

    result = get_user_by_email_gsi(table, EMAIL)

    assert result is not None
    assert result.user_id == oldest["user_id"]
