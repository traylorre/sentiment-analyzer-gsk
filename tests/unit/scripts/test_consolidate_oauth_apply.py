# Target: consolidation migration script (Feature 1397) — destructive paths
"""apply / collision / idempotency / partial / rollback / verify / FR-019 / FR-020 /
gate-inside-apply tests. All run against an in-memory moto table (safe). (not preprod)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import scripts.consolidate_oauth_duplicates as mod
from tests.unit.scripts.conftest import (
    FaultTable,
    SpyTable,
    count_user_profiles,
    put_owned,
    seed_group,
)


@pytest.fixture
def confirmed(monkeypatch):
    """Flip the coordination gate for tests that exercise the destructive path."""
    monkeypatch.setattr(mod, "COORDINATION_CONFIRMED", True)


def _scan_pk_sks(table):
    return {(i["PK"], i["SK"]) for i in table.scan().get("Items", [])}


def test_consolidation_preserves_owned_data(
    dynamodb_table, confirmed, monkeypatch, tmp_path
):
    """T017: a non-canonical's configs/alerts/notifs land under the canonical, none lost."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    canonical_id, other_id = user_ids
    put_owned(dynamodb_table, other_id, "CONFIG#c1", name="cfg")
    put_owned(dynamodb_table, other_id, "ALERT#a1", name="alert")
    put_owned(dynamodb_table, other_id, "NOTIF#n1", body="note")

    result = mod.apply(dynamodb_table, sub, None)
    assert result.status == "completed"
    assert result.canonical_user_id == canonical_id

    keys = _scan_pk_sks(dynamodb_table)
    assert (f"USER#{canonical_id}", "CONFIG#c1") in keys
    assert (f"USER#{canonical_id}", "ALERT#a1") in keys
    assert (f"USER#{canonical_id}", "NOTIF#n1") in keys
    # source records gone
    assert (f"USER#{other_id}", "CONFIG#c1") not in keys
    assert (f"USER#{other_id}", "PROFILE") not in keys
    assert count_user_profiles(dynamodb_table, sub) == 1


def test_collision_preserves_loser(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T018: same-SK collision keeps canonical, preserves loser under #dup- SK."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    canonical_id, other_id = user_ids
    put_owned(dynamodb_table, canonical_id, "CONFIG#x", name="canonical-value")
    put_owned(dynamodb_table, other_id, "CONFIG#x", name="loser-value")

    result = mod.apply(dynamodb_table, sub, None)
    assert result.status == "completed"

    canonical_item = dynamodb_table.get_item(
        Key={"PK": f"USER#{canonical_id}", "SK": "CONFIG#x"}
    )["Item"]
    assert canonical_item["name"] == "canonical-value"  # untouched

    src_short = other_id[:8]
    loser = dynamodb_table.get_item(
        Key={"PK": f"USER#{canonical_id}", "SK": f"CONFIG#x#dup-{src_short}"}
    )["Item"]
    assert loser["name"] == "loser-value"
    assert loser["collision"] is True
    assert loser["merged_from"] == other_id


def test_idempotent_apply(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T019: second apply is a no-op (already-consolidated), zero destructive writes."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    seed_group(dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"])

    first = mod.apply(dynamodb_table, sub, None)
    assert first.status == "completed"

    spy = SpyTable(dynamodb_table)
    second = mod.apply(spy, sub, None)
    assert second.status == "already-consolidated"
    assert spy.writes == 0


def test_partial_failure_resumable(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T020: a reassignment failure retains the source + PROFILE (partial); re-run completes."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    canonical_id, other_id = user_ids
    put_owned(dynamodb_table, other_id, "CONFIG#a", name="a")
    put_owned(dynamodb_table, other_id, "CONFIG#b", name="b")
    put_owned(dynamodb_table, other_id, "CONFIG#c", name="c")

    fault = FaultTable(dynamodb_table, fail_on_sk="CONFIG#b")
    result = mod.apply(fault, sub, None)
    assert result.status == "partial"

    keys = _scan_pk_sks(dynamodb_table)
    # failed child's source retained, PROFILE retained
    assert (f"USER#{other_id}", "CONFIG#b") in keys
    assert (f"USER#{other_id}", "PROFILE") in keys

    # Re-run without the fault completes.
    result2 = mod.apply(dynamodb_table, sub, None)
    assert result2.status == "completed"
    keys2 = _scan_pk_sks(dynamodb_table)
    assert (f"USER#{other_id}", "PROFILE") not in keys2
    assert (f"USER#{canonical_id}", "CONFIG#b") in keys2
    assert count_user_profiles(dynamodb_table, sub) == 1


def test_rollback_restores_all(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T021: rollback from backup restores every original record byte-for-byte."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    other_id = user_ids[1]
    put_owned(dynamodb_table, other_id, "CONFIG#c1", name="cfg")

    before = {(i["PK"], i["SK"]): i for i in dynamodb_table.scan().get("Items", [])}

    backup_path = str(tmp_path / "backup.json")
    mod.backup_group(list(before.values()), backup_path)
    assert mod.validate_backup(backup_path, list(before.keys()))

    result = mod.apply(dynamodb_table, sub, backup_path)
    assert result.status == "completed"
    assert count_user_profiles(dynamodb_table, sub) == 1

    mod.rollback(dynamodb_table, backup_path)
    after = {(i["PK"], i["SK"]): i for i in dynamodb_table.scan().get("Items", [])}
    for key, item in before.items():
        assert after.get(key) == item


def test_validate_backup_rejects_right_count_wrong_keys(
    dynamodb_table, monkeypatch, tmp_path
):
    """Backup with the CORRECT count but a WRONG (PK, SK) key-set must be rejected.

    Last-safety-net guard for a destructive migration: count-only validation is
    insufficient (right count, wrong items). A count-only regression in
    ``validate_backup`` would pass every other test; this one refutes it.
    All ids are SYNTHETIC (FR-018).
    """
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, _, _ = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    put_owned(dynamodb_table, user_ids[1], "CONFIG#c1", name="cfg")

    before = list(dynamodb_table.scan().get("Items", []))
    backup_path = str(tmp_path / "backup.json")
    mod.backup_group(before, backup_path)

    real_keys = [(i["PK"], i["SK"]) for i in before]
    assert mod.validate_backup(backup_path, real_keys) is True

    # Same COUNT, but swap one real key for a bogus one the backup never held.
    tampered_keys = real_keys[:-1] + [(f"USER#{uuid4()}", "PROFILE")]
    assert len(tampered_keys) == len(real_keys)
    assert mod.validate_backup(backup_path, tampered_keys) is False


def test_verify_asserts_single(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T023: verify passes post-apply; an orphan projection makes verify FAIL."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, email, provider_sub = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    canonical_id = user_ids[0]
    result = mod.apply(dynamodb_table, sub, None)
    assert result.status == "completed"

    shared = {"cognito_sub": sub, "provider_sub": provider_sub, "email": email}
    assert mod.verify(dynamodb_table, canonical_id, shared) is True

    # Inject an orphan duplicate sharing the identity -> verify must fail.
    from tests.unit.scripts.conftest import put_profile

    orphan = str(uuid4())
    put_profile(
        dynamodb_table, orphan, "2026-07-25T00:00:00Z", sub, email, provider_sub
    )
    assert mod.verify(dynamodb_table, canonical_id, shared) is False


def test_canonical_never_in_destructive_set(
    dynamodb_table, confirmed, monkeypatch, tmp_path
):
    """T032: canonical poisoned into a destructive set -> HARD ABORT, zero writes."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    seed_group(dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"])

    real_select = mod.select_canonical

    def poisoned(group):
        canonical, non_canonical = real_select(group)
        # Inject the canonical itself into the non-canonical (destructive) set.
        return canonical, [canonical, *non_canonical]

    monkeypatch.setattr(mod, "select_canonical", poisoned)
    spy = SpyTable(dynamodb_table)
    result = mod.apply(spy, sub, None)
    assert result.status == "blocked"
    assert "FR-019" in (result.apply_blocked_reason or "")
    assert spy.writes == 0


def test_frozen_delete_set_straggler(dynamodb_table, confirmed, monkeypatch, tmp_path):
    """T033: a duplicate minted AFTER backup is untouched, reported, and verify fails."""
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    user_ids, email, provider_sub = seed_group(
        dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"]
    )
    canonical_id = user_ids[0]

    # Backup the current (2-record) group.
    before = list(dynamodb_table.scan().get("Items", []))
    backup_path = str(tmp_path / "backup.json")
    mod.backup_group(before, backup_path)

    # Concurrent login mints an 11th duplicate AFTER the backup.
    from tests.unit.scripts.conftest import put_profile

    straggler = str(uuid4())
    put_profile(
        dynamodb_table, straggler, "2026-07-24T22:00:00Z", sub, email, provider_sub
    )

    result = mod.apply(dynamodb_table, sub, backup_path)
    assert straggler in result.stragglers
    # Straggler PROFILE untouched.
    assert (
        dynamodb_table.get_item(Key={"PK": f"USER#{straggler}", "SK": "PROFILE"}).get(
            "Item"
        )
        is not None
    )
    # verify fails exactly-one (canonical + straggler both project).
    shared = {"cognito_sub": sub, "provider_sub": provider_sub, "email": email}
    assert mod.verify(dynamodb_table, canonical_id, shared) is False


def test_apply_gates_enforced_inside_apply(dynamodb_table, monkeypatch, tmp_path):
    """T034: direct apply() call with gates unsatisfied -> blocked, zero writes.

    No `confirmed` fixture here: COORDINATION_CONFIRMED stays False (the real default),
    proving a direct import+call cannot bypass the gate. (AR#5/A7)
    """
    monkeypatch.chdir(tmp_path)
    sub = f"google-cognito-{uuid4().hex}"
    seed_group(dynamodb_table, sub, ["2026-07-24T03:16:42Z", "2026-07-24T06:40:14Z"])
    spy = SpyTable(dynamodb_table)
    result = mod.apply(spy, sub, None)
    assert result.status == "blocked"
    assert spy.writes == 0
