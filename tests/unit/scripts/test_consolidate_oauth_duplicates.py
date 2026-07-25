# Target: consolidation migration script (Feature 1397) — non-destructive paths
"""Enumerate / select / dry-run / env-guard / static-scan tests (moto, not preprod)."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

import scripts.consolidate_oauth_duplicates as mod
from tests.unit.scripts.conftest import (
    SpyTable,
    put_owned,
    seed_group,
)

UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


# --- enumeration & selection ----------------------------------------------


def test_enumerate_group_returns_full_group_not_limit1(dynamodb_table):
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table,
        sub,
        [
            "2026-07-24T03:16:42.164498Z",
            "2026-07-24T06:40:14.000000Z",
            "2026-07-24T21:18:06.865682Z",
        ],
    )
    group = mod.enumerate_group(dynamodb_table, sub)
    assert {r.user_id for r in group} == set(user_ids)
    assert len(group) == 3


def test_select_canonical_earliest_created_at(dynamodb_table):
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table,
        sub,
        [
            "2026-07-24T21:18:06.865682Z",
            "2026-07-24T03:16:42.164498Z",  # earliest — must win regardless of order
            "2026-07-24T06:40:14.000000Z",
        ],
    )
    group = mod.enumerate_group(dynamodb_table, sub)
    canonical, non_canonical = mod.select_canonical(group)
    assert canonical.created_at == "2026-07-24T03:16:42.164498Z"
    assert canonical.user_id == user_ids[1]
    assert len(non_canonical) == 2


def test_created_at_tie_breaks_user_id_asc_shuffle_stable():
    """T029: identical created_at -> lexicographically lowest user_id; shuffle-stable."""
    same = "2026-07-24T03:16:42.164498Z"
    ids = sorted([str(uuid4()) for _ in range(4)])
    lowest = ids[0]

    import random

    for _ in range(5):
        order = ids[:]
        random.shuffle(order)
        group = [
            mod.GroupRecord(
                user_id=uid,
                created_at=same,
                email="e@example.test",
                provider_sub="p",
                profile_item={},
            )
            for uid in order
        ]
        canonical, _ = mod.select_canonical(group)
        assert canonical.user_id == lowest


def test_null_created_at_never_canonical(dynamodb_table):
    """T024: a record missing created_at sorts LAST and is never canonical."""
    group = [
        mod.GroupRecord(str(uuid4()), None, "e@example.test", "p", {}),
        mod.GroupRecord(
            "aaaa-earliest", "2026-07-24T03:16:42Z", "e@example.test", "p", {}
        ),
    ]
    canonical, non_canonical = mod.select_canonical(group)
    assert canonical.created_at is not None
    assert non_canonical[-1].created_at is None


# --- coordination gate -----------------------------------------------------


def test_coordination_gate_blocked_by_default():
    assert mod.COORDINATION_CONFIRMED is False
    assert mod.coordination_gate() is not None


def test_apply_blocked_until_coordination(dynamodb_table, monkeypatch, tmp_path):
    """T025: apply_blocked (Open Q1 unconfirmed) prevents any destructive write."""
    sub = f"google-cognito-{uuid4().hex}"
    seed_group(
        dynamodb_table,
        sub,
        ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"],
    )
    monkeypatch.chdir(tmp_path)
    spy = SpyTable(dynamodb_table)
    result = mod.apply(spy, sub, None)  # COORDINATION_CONFIRMED still False
    assert result.status == "blocked"
    assert spy.writes == 0


# --- dry-run ---------------------------------------------------------------


def test_dry_run_makes_no_writes(dynamodb_table):
    """T016: default (dry-run) makes zero mutations and names the earliest canonical."""
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table,
        sub,
        [
            "2026-07-24T06:40:14Z",
            "2026-07-24T03:16:42Z",
            "2026-07-24T21:18:06Z",
        ],
    )
    earliest = user_ids[1]
    spy = SpyTable(dynamodb_table)
    report = mod.dry_run_report(spy, sub)
    assert spy.writes == 0
    assert earliest in report
    assert "DRY-RUN complete — zero DynamoDB writes performed." in report


def test_dry_run_prints_computed_canonical_and_plan(dynamodb_table):
    """T028: dry-run output has the runtime-computed canonical + rule + per-item plan."""
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table,
        sub,
        ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"],
    )
    canonical_id, other_id = user_ids
    put_owned(dynamodb_table, other_id, "CONFIG#cfg1", name="c1")
    put_owned(dynamodb_table, other_id, "ALERT#al1", name="a1")

    report = mod.dry_run_report(dynamodb_table, sub)
    assert canonical_id in report
    assert "2026-07-24T03:16:42Z" in report
    assert mod.CANONICAL_RULE in report
    assert "PLAN REASSIGN: CONFIG#cfg1" in report
    assert "PLAN REASSIGN: ALERT#al1" in report
    assert f"PLAN DELETE PROFILE: USER#{other_id}" in report


def test_script_source_has_no_uuid_literal():
    """T028 (static scan): no UUID-shaped literal may appear in the script source."""
    source = Path(mod.__file__).read_text(encoding="utf-8")
    matches = UUID_RE.findall(source)
    assert matches == [], f"UUID-shaped literal(s) found in script: {matches}"


# --- environment / prod guard ---------------------------------------------


@pytest.mark.parametrize(
    "name,is_prod",
    [
        ("preprod-sentiment-users", False),
        ("sentiment-preprod-users", False),
        ("preprod", False),
        ("prod-sentiment-users", True),
        ("sentiment-prod-users", True),
        ("production-sentiment-users", True),
        ("sentiment-users-prod", True),
        ("PROD-users", True),
        ("myproduction-users", True),
    ],
)
def test_resolves_to_prod_matrix(name, is_prod):
    """T030: prod-detection rule matrix (FR-014, AR#4/NF-2)."""
    assert mod._resolves_to_prod(name) is is_prod


def test_prod_guard_hard_stops_before_any_io():
    """T022: a prod-named table without --allow-prod hard-stops."""
    with pytest.raises(SystemExit):
        mod._env_guard("sentiment-prod-users", allow_prod=False)


def test_env_guard_allow_prod_override():
    """T031: prod table stops without override, proceeds with it; preprod never trips."""
    with pytest.raises(SystemExit):
        mod._env_guard("production-sentiment-users", allow_prod=False)
    # With override, no raise.
    mod._env_guard("production-sentiment-users", allow_prod=True)
    # Preprod never trips regardless.
    mod._env_guard("preprod-sentiment-users", allow_prod=False)
