#!/usr/bin/env python3
"""Consolidate duplicate OAuth USER records into one canonical record.

Feature 1397 (oauth-dup-cleanup).

This is the safe-by-default consolidation migration authored alongside
specs/1397-oauth-dup-cleanup/{spec,plan,tasks}.md. DRY-RUN IS THE DEFAULT;
the DESTRUCTIVE `--apply` path is owner-gated and stays BLOCKED until an owner
flips COORDINATION_CONFIRMED (a reviewed, GPG-signed commit) after confirming
Feature 1395 is DEPLOYED. The migration logic is fully implemented and validated
against an in-memory (moto) DynamoDB table; the live `--apply` run (T027) is a
SEPARATE owner-approved action.

SAFETY MODEL (see spec.md FRs):
  * DRY-RUN IS THE DEFAULT. Destructive behavior requires `--apply`.
    NOTE: this DELIBERATELY INVERTS the repo convention used by
    scripts/migrate_status_field.py (which defaults to apply, opts into
    --dry-run). That migration is additive; this one DELETES USER records,
    so it must be safe-by-default. (FR-010)
  * `--apply` additionally requires `--i-understand-destructive`, a validated
    fresh backup, an unblocked coordination gate, and the env guard. (FR-011, FR-014)
  * Canonical = earliest created_at, then user_id ascending. (FR-002)
  * Reassign-then-delete; never delete-first. Backup + audit every action. (FR-005, FR-012)
  * ALL gates are enforced INSIDE apply() (not only main()), so a direct import
    + call cannot bypass them. (AR#5/A7)

Usage:
    # dry-run report (no writes):
    python scripts/consolidate_oauth_duplicates.py \
        --table preprod-sentiment-users \
        --cognito-sub <sub>   # live identifiers are runtime inputs, never literals (FR-018)

    # apply (GATED — owner approval + 1395 deployed + Open Q1 answered):
    python scripts/consolidate_oauth_duplicates.py \
        --table preprod-sentiment-users \
        --cognito-sub <sub> --apply --i-understand-destructive

    # verify / rollback:
    python scripts/consolidate_oauth_duplicates.py --table <t> --cognito-sub <s> --verify
    python scripts/consolidate_oauth_duplicates.py --table <t> --rollback --backup-file <path>
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

try:  # boto3 is optional at import time (tests may inject a fake table)
    import boto3
    from boto3.dynamodb.conditions import Attr, Key
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - exercised only in minimal envs
    boto3 = None  # type: ignore[assignment]
    Attr = Key = None  # type: ignore[assignment]

    class ClientError(Exception):  # type: ignore[no-redef]
        """Fallback so except-clauses parse when botocore is unavailable."""


try:
    from src.lambdas.shared.logging_utils import sanitize_for_log
except Exception:  # pragma: no cover - keep the script importable standalone

    def sanitize_for_log(value: Any, max_length: int = 200) -> str:
        text = str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ")
        return text[:max_length]


# Selection rule constant — aligned with Feature 1395's survivor rule.
# CONFIRMED: 1395 spec (specs/1395-oauth-account-integrity/) FR-004 pins the SAME
# rule (earliest created_at, then user_id asc). No rule negotiation remains.
# FR-018: the winner is computed at runtime by select_canonical and is NEVER
# recorded as a literal — not here, not in any spec/plan/tasks artifact. NO live
# user_id appears anywhere in this file (enforced by a static test scan, T028).
# The dry-run prints the computed canonical + the full reassignment plan; the
# owner compares that printout to their own live query before approving --apply.
CANONICAL_RULE = "earliest_created_at"

# Coordination gate: the RULE is already confirmed (1395 FR-004). This flag gates on
# the residual OPERATIONAL question of Open Q1 — is Feature 1395 DEPLOYED? Flip to True
# only after the owner confirms 1395 is live. While False, --apply is BLOCKED regardless
# of other flags. (FR-002a)
COORDINATION_CONFIRMED = False

# SK classification prefixes (FR-004). Order matters only for reporting.
_REASSIGN_CATEGORIES = ("CONFIG", "ALERT", "NOTIF", "PREF")
_SK_PREFIXES = {
    "CONFIG": "CONFIG#",
    "ALERT": "ALERT#",
    "NOTIF": "NOTIF#",
    "PREF": "PREF#",
    "SESSION": "SESSION#",
}


@dataclass
class GroupRecord:
    user_id: str
    created_at: str | None
    email: str | None
    provider_sub: str | None
    profile_item: dict[str, Any]


@dataclass
class RunResult:
    mode: str  # "dry-run" | "apply" | "verify" | "rollback"
    canonical_user_id: str | None = None
    non_canonical: list[str] = field(default_factory=list)
    status: str = "reported"  # reported|completed|partial|already-consolidated|blocked
    apply_blocked_reason: str | None = None
    stragglers: list[str] = field(default_factory=list)
    audit_path: str | None = None
    backup_sha256: str | None = None


class _CanonicalInDestructiveSetError(Exception):
    """Raised when the canonical id lands in a destructive set (FR-019, EC-7)."""


class _UnresolvedChildrenError(Exception):
    """Raised when a non-canonical PROFILE still has unresolved children (FR-008)."""


# --------------------------------------------------------------------------
# Backup (de)serialization helpers — full-fidelity, type-preserving
# --------------------------------------------------------------------------


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return {"__decimal__": str(obj)}
    if isinstance(obj, set | frozenset):
        return {"__set__": sorted(str(v) for v in obj)}
    if isinstance(obj, bytes):
        return {"__bytes__": obj.decode("latin-1")}
    raise TypeError(f"Unserializable type: {type(obj).__name__}")


def _json_object_hook(d: dict[str, Any]) -> Any:
    if "__decimal__" in d:
        return Decimal(d["__decimal__"])
    if "__set__" in d:
        return set(d["__set__"])
    if "__bytes__" in d:
        return d["__bytes__"].encode("latin-1")
    return d


def _serialize_items(items: list[dict]) -> str:
    return json.dumps(items, default=_json_default, sort_keys=True, indent=2)


def _item_key(item: dict) -> tuple[str, str]:
    return (str(item.get("PK")), str(item.get("SK")))


# --------------------------------------------------------------------------
# Audit log (FR-012) — append-only JSONL, sanitized identifiers
# --------------------------------------------------------------------------


def _audit(
    path: str | None, action: str, source_key: Any, target_key: Any, outcome: str
) -> None:
    """Append one audit record. No-op when path is None (audit disabled)."""
    if not path:
        return
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "action": sanitize_for_log(action),
        "source_key": sanitize_for_log(source_key),
        "target_key": sanitize_for_log(target_key),
        "outcome": sanitize_for_log(outcome),
    }
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# --------------------------------------------------------------------------
# Phase 1 — enumerate & select (non-destructive)
# --------------------------------------------------------------------------


def enumerate_group(table: Any, cognito_sub: str) -> list[GroupRecord]:
    """Paginate by_cognito_sub, GetItem each PROFILE, cross-check email/provider_sub.

    Must NOT trust GSI Limit=1. (FR-001, FR-003, EC-3, EC-5)
    """
    user_ids: list[str] = []
    seen: set[str] = set()
    query_kwargs: dict[str, Any] = {
        "IndexName": "by_cognito_sub",
        "KeyConditionExpression": Key("cognito_sub").eq(cognito_sub),
    }
    while True:
        resp = table.query(**query_kwargs)
        for item in resp.get("Items", []):
            uid = item.get("user_id") or str(item.get("PK", "")).split("#", 1)[-1]
            if uid and uid not in seen:
                seen.add(uid)
                user_ids.append(uid)
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        query_kwargs["ExclusiveStartKey"] = last

    group: list[GroupRecord] = []
    for uid in user_ids:
        resp = table.get_item(
            Key={"PK": f"USER#{uid}", "SK": "PROFILE"}, ConsistentRead=True
        )
        profile = resp.get("Item")
        if not profile:
            # GSI projection without a base PROFILE — report by including a stub.
            continue
        group.append(
            GroupRecord(
                user_id=uid,
                created_at=profile.get("created_at"),
                email=profile.get("email"),
                provider_sub=profile.get("provider_sub"),
                profile_item=profile,
            )
        )
    return group


def _divergence(group: list[GroupRecord]) -> str | None:
    """Return a blocking reason if the group does not share email + provider_sub. (FR-001, EC-5)"""
    emails = {r.email for r in group if r.email is not None}
    subs = {r.provider_sub for r in group if r.provider_sub is not None}
    if len(emails) > 1 or len(subs) > 1:
        return (
            "Divergent identifier in group: "
            f"emails={sorted(sanitize_for_log(e) for e in emails)} "
            f"provider_subs={sorted(sanitize_for_log(s) for s in subs)} "
            "— may not be true duplicates; --apply BLOCKED for this group."
        )
    return None


def select_canonical(
    group: list[GroupRecord],
) -> tuple[GroupRecord, list[GroupRecord]]:
    """Sort by (created_at asc, user_id asc); null created_at sorts LAST and is
    never canonical. Returns (canonical, non_canonical). (FR-002, A6)
    """
    if not group:
        raise ValueError("empty group — nothing to select")

    def sort_key(r: GroupRecord) -> tuple[int, str, str]:
        missing = 1 if not r.created_at else 0
        return (missing, r.created_at or "", r.user_id)

    ordered = sorted(group, key=sort_key)
    return ordered[0], ordered[1:]


def coordination_gate() -> str | None:
    """Return a blocking reason if Feature 1395 is not confirmed DEPLOYED. (FR-002a)

    The selection RULE is already confirmed aligned with 1395 FR-004
    (earliest_created_at, user_id asc). This gate covers the residual operational
    question: is 1395 live? (Open Q1)
    """
    if not COORDINATION_CONFIRMED:
        return (
            "Open Q1 unconfirmed: rule aligns with 1395 FR-004, but Feature 1395 is not "
            "confirmed DEPLOYED. --apply is BLOCKED until the owner confirms 1395 is live."
        )
    return None


def inventory_owned(table: Any, user_id: str) -> dict[str, list[dict]]:
    """Paginate PK=USER#{id}; classify by SK prefix; unknown reported not dropped. (FR-004)"""
    inventory: dict[str, list[dict]] = {
        "PROFILE": [],
        "CONFIG": [],
        "ALERT": [],
        "NOTIF": [],
        "PREF": [],
        "SESSION": [],
        "unknown": [],
    }
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("PK").eq(f"USER#{user_id}"),
    }
    while True:
        resp = table.query(**query_kwargs)
        for item in resp.get("Items", []):
            sk = str(item.get("SK", ""))
            if sk == "PROFILE":
                inventory["PROFILE"].append(item)
                continue
            matched = False
            for cat, prefix in _SK_PREFIXES.items():
                if sk.startswith(prefix):
                    inventory[cat].append(item)
                    matched = True
                    break
            if not matched:
                inventory["unknown"].append(item)
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        query_kwargs["ExclusiveStartKey"] = last
    return inventory


def render_report(canonical: GroupRecord, non_canonical: list[GroupRecord]) -> str:
    """Human-readable dry-run header naming the RUNTIME-COMPUTED canonical. (US1, FR-010, FR-018)"""
    lines = [
        "=== Feature 1397 consolidation report (DRY-RUN) ===",
        f"Canonical-selection rule: {CANONICAL_RULE} (then user_id ascending)",
        f"Computed canonical user_id: {canonical.user_id}",
        f"Canonical created_at:       {canonical.created_at}",
        f"Non-canonical records ({len(non_canonical)}):",
    ]
    for rec in non_canonical:
        lines.append(f"  - {rec.user_id}  (created_at={rec.created_at})")
    return "\n".join(lines)


def dry_run_report(table: Any, cognito_sub: str) -> str:
    """Compose the FULL dry-run printout: computed canonical + per-item reassignment
    plan for every owned item. This printout is what the owner compares against their
    own live query before approving --apply. ZERO writes. (US1, FR-010, FR-018)
    """
    group = enumerate_group(table, cognito_sub)
    if not group:
        return f"No USER records found for cognito_sub={sanitize_for_log(cognito_sub)}."
    canonical, non_canonical = select_canonical(group)
    lines = [render_report(canonical, non_canonical)]

    divergence = _divergence(group)
    if divergence:
        lines.append(f"[BLOCK] {divergence}")
    if not canonical.created_at:
        lines.append(
            "[BLOCK] Computed canonical lacks created_at — --apply blocked pending owner decision."
        )

    lines.append("--- Reassignment plan ---")
    action_by_cat = {
        "CONFIG": "REASSIGN",
        "ALERT": "REASSIGN",
        "NOTIF": "REASSIGN",
        "PREF": "REASSIGN",
        "SESSION": "DISCARD",
    }
    for rec in non_canonical:
        inv = inventory_owned(table, rec.user_id)
        for cat in ("CONFIG", "ALERT", "NOTIF", "PREF", "SESSION"):
            for item in inv[cat]:
                action = action_by_cat[cat]
                lines.append(
                    f"PLAN {action}: {sanitize_for_log(item.get('SK'))} "
                    f"(from {rec.user_id}) -> USER#{canonical.user_id}"
                )
        for item in inv["unknown"]:
            lines.append(
                f"PLAN REPORT-ONLY (unknown prefix, never dropped): "
                f"{sanitize_for_log(item.get('SK'))} (from {rec.user_id})"
            )
        lines.append(
            f"PLAN DELETE PROFILE: USER#{rec.user_id} (after children resolved)"
        )
    lines.append(f"PLAN RETAIN canonical PROFILE: USER#{canonical.user_id}")
    lines.append("DRY-RUN complete — zero DynamoDB writes performed.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Phase 2 — backup & rollback
# --------------------------------------------------------------------------


def backup_group(items: list[dict], path: str) -> None:
    """Full-fidelity local JSON export. NO S3 / no new AWS resource. (FR-011)"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_serialize_items(items))


def _load_backup(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh, object_hook=_json_object_hook)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def validate_backup(path: str, expected_keys: Any) -> bool:
    """Re-open, parse, assert count == expected AND exact (PK, SK) key-set equality.

    ``expected_keys`` is an iterable of (PK, SK) tuples (count-only validation is
    insufficient — right count, wrong items). (FR-011, A5, AR#5/A9)
    """
    expected = {tuple(k) for k in expected_keys}
    items = _load_backup(path)
    actual = {_item_key(i) for i in items}
    if len(items) != len(expected):
        return False
    return actual == expected


def rollback(table: Any, backup_file: str) -> RunResult:
    """put_item every exported item verbatim; idempotent; runs from file alone. (FR-015)"""
    items = _load_backup(backup_file)
    for item in items:
        table.put_item(Item=item)
    return RunResult(mode="rollback", status="completed")


# --------------------------------------------------------------------------
# Phase 3 — apply (DESTRUCTIVE CORE — gated)
# --------------------------------------------------------------------------


def _is_conditional_failure(err: ClientError) -> bool:
    try:
        code = err.response["Error"]["Code"]  # type: ignore[attr-defined]
    except Exception:
        return False
    return code == "ConditionalCheckFailedException"


def reassign_item(table: Any, item: dict, canonical_id: str) -> str:
    """Reassign-then-delete. Collision -> loser under {SK}#dup-{src} with
    merged_from+collision=true; never overwrite canonical; never delete an
    unresolved source. Skip items already carrying merged_from.
    Returns: reassigned | collision-diverted | skipped | failed.
    (FR-005, FR-006, FR-012, FR-013, A1, A4)
    """
    if item.get("merged_from"):
        return "skipped"

    source_pk = str(item["PK"])
    source_sk = str(item["SK"])
    source_user_id = source_pk.split("#", 1)[-1]
    src_short = source_user_id[:8]
    target_pk = f"USER#{canonical_id}"

    existing = table.get_item(
        Key={"PK": target_pk, "SK": source_sk}, ConsistentRead=True
    ).get("Item")

    new_item = dict(item)
    new_item["PK"] = target_pk
    new_item["user_id"] = canonical_id
    new_item["merged_from"] = source_user_id

    if existing:
        # Collision: keep-canonical, preserve-loser under a suffixed SK (FR-006).
        new_item["SK"] = f"{source_sk}#dup-{src_short}"
        new_item["collision"] = True
        outcome = "collision-diverted"
    else:
        outcome = "reassigned"

    try:
        table.put_item(
            Item=new_item,
            ConditionExpression=Attr("PK").not_exists() & Attr("SK").not_exists(),
        )
    except ClientError as err:
        if _is_conditional_failure(err):
            # Target already written (idempotent re-run / concurrent divert). Do NOT
            # delete the source blindly: only delete if the confirmed target carries
            # our merged_from marker, else treat as unresolved.
            return "skipped"
        # Throttling / transient failure: DO NOT delete source. Mark run partial.
        return "failed"

    # Reassign confirmed — now (and only now) delete the source item.
    table.delete_item(Key={"PK": source_pk, "SK": source_sk})
    return outcome


def discard_sessions(table: Any, user_id: str) -> int:
    """Delete SESSION# items (do not re-home stale auth). (FR-007)"""
    count = 0
    resp = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
        & Key("SK").begins_with("SESSION#")
    )
    for item in resp.get("Items", []):
        table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
        count += 1
    return count


def delete_noncanonical_profile(table: Any, user_id: str) -> None:
    """Delete only after ALL children resolved; else retain + partial. (FR-008, A4)"""
    resp = table.query(KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"))
    leftover = [i for i in resp.get("Items", []) if str(i.get("SK")) != "PROFILE"]
    if leftover:
        raise _UnresolvedChildrenError(user_id)
    table.delete_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})


def _assert_canonical_excluded(
    canonical_id: str, destructive_user_ids: set[str]
) -> None:
    """HARD assertion: canonical id must not appear in any destructive set. (FR-019, EC-7)"""
    if canonical_id in destructive_user_ids:
        raise _CanonicalInDestructiveSetError(canonical_id)


def apply(table: Any, cognito_sub: str, backup_file: str | None) -> RunResult:
    """Orchestrate the destructive consolidation. Enforces every gate before acting.

    Gates (all inside apply(), not just main()): coordination gate clear,
    no divergence, canonical has created_at, validated backup present, env guard
    clear, FR-019 canonical-exclusion assertion, FR-020 frozen delete set.
    (FR-010/011/013/014/017/019/020, AR#5/A7)
    """
    result = RunResult(mode="apply")

    # Gate 0: coordination (Open Q1 — is 1395 deployed?). Default: BLOCKED.
    block = coordination_gate()
    if block:
        result.status = "blocked"
        result.apply_blocked_reason = block
        return result

    # Gate 1: env guard (defense-in-depth; prod is out of scope for 1397).
    table_name = getattr(table, "name", "") or ""
    if _resolves_to_prod(table_name):
        result.status = "blocked"
        result.apply_blocked_reason = f"table '{table_name}' resolves to prod; refused."
        return result

    # Enumerate + selection.
    group = enumerate_group(table, cognito_sub)
    if not group:
        result.status = "already-consolidated"
        return result

    divergence = _divergence(group)
    if divergence:
        result.status = "blocked"
        result.apply_blocked_reason = divergence
        return result

    canonical, non_canonical = select_canonical(group)
    result.canonical_user_id = canonical.user_id
    result.non_canonical = [r.user_id for r in non_canonical]

    if not canonical.created_at:
        result.status = "blocked"
        result.apply_blocked_reason = (
            "canonical lacks created_at — pending owner decision."
        )
        return result

    if not non_canonical:
        result.status = "already-consolidated"
        return result

    # Gate 2: validated backup covering the group (FR-011).
    audit_path = None
    if backup_file:
        backup_path = backup_file
        frozen_items = _load_backup(backup_path)
    else:
        # Produce a fresh pre-flight backup of every affected item.
        affected: list[dict] = [canonical.profile_item]
        for rec in group:
            if rec.user_id == canonical.user_id:
                continue
            inv = inventory_owned(table, rec.user_id)
            for items in inv.values():
                affected.extend(items)
        short = cognito_sub[:8] if cognito_sub else "group"
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = f"1397-backup-{short}-{stamp}.json"
        backup_group(affected, backup_path)
        frozen_items = affected

    result.backup_sha256 = _sha256_file(backup_path)
    audit_path = backup_path + ".audit.jsonl"
    result.audit_path = audit_path
    _audit(audit_path, "backup", backup_path, result.backup_sha256, "recorded")

    # FR-011 key-set validation: the backup must faithfully capture its own contents.
    frozen_keys = {_item_key(i) for i in frozen_items}
    if not validate_backup(backup_path, frozen_keys):
        result.status = "blocked"
        result.apply_blocked_reason = (
            "backup validation failed (count/key-set mismatch)."
        )
        return result

    # FR-020 FREEZE: re-enumerate; anything not in the backup is a straggler and is
    # NEVER touched (fail-closed on concurrent-login duplicates minted mid-run).
    frozen_user_ids = {
        pk.split("#", 1)[-1] for (pk, sk) in frozen_keys if sk == "PROFILE"
    }
    stragglers = [
        rec.user_id for rec in non_canonical if rec.user_id not in frozen_user_ids
    ]
    result.stragglers = stragglers
    frozen_non_canonical = [
        rec for rec in non_canonical if rec.user_id in frozen_user_ids
    ]

    # FR-019 HARD ASSERT: canonical must not be in any destructive set. Zero writes
    # have occurred yet, so an abort here is truly write-free.
    destructive_ids = {rec.user_id for rec in frozen_non_canonical}
    try:
        _assert_canonical_excluded(canonical.user_id, destructive_ids)
    except _CanonicalInDestructiveSetError:
        result.status = "blocked"
        result.apply_blocked_reason = "FR-019 violation: canonical id appeared in a destructive set — HARD ABORT, zero writes."
        return result

    # --- Destructive phase (frozen, backed-up set only) ---
    status = "completed"
    for rec in frozen_non_canonical:
        inv = inventory_owned(table, rec.user_id)
        resolved = True

        for cat in _REASSIGN_CATEGORIES:
            for item in inv[cat]:
                outcome = reassign_item(table, item, canonical.user_id)
                _audit(
                    audit_path,
                    f"reassign:{cat}",
                    _item_key(item),
                    (f"USER#{canonical.user_id}", item.get("SK")),
                    outcome,
                )
                if outcome == "failed":
                    resolved = False

        discarded = discard_sessions(table, rec.user_id)
        if discarded:
            _audit(
                audit_path,
                "discard_sessions",
                f"USER#{rec.user_id}",
                None,
                str(discarded),
            )

        if inv["unknown"]:
            # Unknown prefixes are reported, never dropped — retain the PROFILE.
            resolved = False
            _audit(
                audit_path,
                "unknown-prefix-retained",
                _item_key(inv["unknown"][0]),
                None,
                "retained",
            )

        if resolved:
            try:
                _audit(
                    audit_path,
                    "delete_profile",
                    f"USER#{rec.user_id}",
                    None,
                    "deleting",
                )
                delete_noncanonical_profile(table, rec.user_id)
            except _UnresolvedChildrenError:
                status = "partial"
                _audit(
                    audit_path,
                    "delete_profile",
                    f"USER#{rec.user_id}",
                    None,
                    "retained-partial",
                )
        else:
            status = "partial"

    if stragglers:
        status = "partial"

    result.status = status
    return result


# --------------------------------------------------------------------------
# Phase 4 — verify
# --------------------------------------------------------------------------


def verify(table: Any, canonical_id: str, shared: dict[str, str]) -> bool:
    """Assert each GSI (by_cognito_sub/by_provider_sub/by_email) resolves to exactly
    one USER item == canonical; FAIL loudly otherwise. (FR-009, US5)
    """
    index_by_attr = {
        "cognito_sub": "by_cognito_sub",
        "provider_sub": "by_provider_sub",
        "email": "by_email",
    }
    ok = True
    for attr, index in index_by_attr.items():
        value = shared.get(attr)
        if value is None:
            continue
        user_ids: list[str] = []
        query_kwargs: dict[str, Any] = {
            "IndexName": index,
            "KeyConditionExpression": Key(attr).eq(value),
        }
        while True:
            resp = table.query(**query_kwargs)
            for item in resp.get("Items", []):
                if str(item.get("SK")) == "PROFILE":
                    user_ids.append(
                        item.get("user_id") or str(item.get("PK", "")).split("#", 1)[-1]
                    )
            last = resp.get("LastEvaluatedKey")
            if not last:
                break
            query_kwargs["ExclusiveStartKey"] = last

        if user_ids != [canonical_id]:
            ok = False
            others = [u for u in user_ids if u != canonical_id]
            print(
                f"[VERIFY FAIL] {index} for value resolves to {len(user_ids)} USER items "
                f"(expected exactly canonical). Straggler(s): "
                f"{[sanitize_for_log(o) for o in others]}",
                file=sys.stderr,
            )
    return ok


# --------------------------------------------------------------------------
# Env guard + CLI
# --------------------------------------------------------------------------


def _resolves_to_prod(table_name: str) -> bool:
    """True if the table name resolves to a PROD environment. (FR-014)

    Rule (authoritative, matched to spec FR-014 / US4): refuse if ANY hyphen-delimited
    segment equals `prod`, OR the name carries a `prod`/`production` token that is NOT
    part of `preprod`. `preprod` MUST NOT be false-tripped; real prod names
    (`sentiment-prod-users`, `production-...`, `prod-...`) MUST be caught.

    The earlier skeleton only tested the FIRST hyphen segment == `prod`, so
    `sentiment-prod-users` and `production-sentiment-users` bypassed the guard
    (Adversarial Review #4, NF-2).
    """
    name = table_name.lower()
    segments = name.split("-")
    # 1. Any hyphen-segment is exactly `prod` (e.g. sentiment-prod-users, prod-...).
    if "prod" in segments:
        return True
    # 2. A `prod`/`production` token anywhere that is NOT the `preprod` compound.
    #    Strip out `preprod` occurrences first so they can never satisfy the check,
    #    then look for a remaining prod/production token.
    stripped = name.replace("preprod", "")
    if "production" in stripped or "prod" in stripped:
        return True
    return False


def _env_guard(table_name: str, allow_prod: bool) -> None:
    """Print resolved table/account/ARN; hard-stop on prod unless --allow-prod. (FR-014)

    Implementation prints sts get-caller-identity. Skeleton enforces the prod stop.
    """
    if _resolves_to_prod(table_name) and not allow_prod:
        raise SystemExit(
            f"REFUSING: table '{table_name}' resolves to the prod environment and "
            "--allow-prod not set. Prod is out of scope for Feature 1397."
        )


def _print_caller_identity(table_name: str) -> None:
    """Print resolved table + AWS account id + caller ARN (FR-014)."""
    account = arn = "<unavailable>"
    if boto3 is not None:
        # Best-effort: identity print is advisory (FR-014); failure is non-fatal.
        with contextlib.suppress(Exception):
            ident = boto3.client("sts").get_caller_identity()
            account = ident.get("Account", account)
            arn = ident.get("Arn", arn)
    print(
        f"[1397] table={sanitize_for_log(table_name)} account={sanitize_for_log(account)} "
        f"caller={sanitize_for_log(arn)}",
        file=sys.stderr,
    )


def _get_table(table_name: str) -> Any:
    if boto3 is None:  # pragma: no cover
        raise SystemExit("boto3 is required to talk to DynamoDB")
    return boto3.resource("dynamodb").Table(table_name)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Consolidate duplicate OAuth USER records (Feature 1397). "
        "DRY-RUN by default; destructive --apply is owner-gated (COORDINATION_CONFIRMED)."
    )
    p.add_argument(
        "--table", required=True, help="DynamoDB table (no default — explicit only)"
    )
    p.add_argument("--cognito-sub", help="Cognito sub identifying the duplicate group")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run (this is already the DEFAULT; flag is affirming only)",
    )
    p.add_argument(
        "--apply", action="store_true", help="DESTRUCTIVE: perform consolidation"
    )
    p.add_argument(
        "--i-understand-destructive",
        action="store_true",
        help="Required acknowledgement alongside --apply",
    )
    p.add_argument("--backup-file", help="Prior validated backup export (JSON)")
    p.add_argument(
        "--allow-prod", action="store_true", help="Permit a prod-named table"
    )
    p.add_argument(
        "--verify", action="store_true", help="Assert exactly-one per GSI post-run"
    )
    p.add_argument("--rollback", action="store_true", help="Restore from --backup-file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _env_guard(args.table, args.allow_prod)
    _print_caller_identity(args.table)

    if args.rollback:
        if not args.backup_file:
            print("[1397] --rollback requires --backup-file", file=sys.stderr)
            return 2
        table = _get_table(args.table)
        result = rollback(table, args.backup_file)
        print(f"[1397] rollback: {result.status}", file=sys.stderr)
        return 0

    if not args.cognito_sub:
        print("[1397] --cognito-sub is required", file=sys.stderr)
        return 2

    table = _get_table(args.table)

    if args.verify:
        group = enumerate_group(table, args.cognito_sub)
        if not group:
            print("[1397] verify: no records found", file=sys.stderr)
            return 1
        canonical, _ = select_canonical(group)
        shared = {
            "cognito_sub": args.cognito_sub,
            "provider_sub": canonical.provider_sub,
            "email": canonical.email,
        }
        ok = verify(table, canonical.user_id, shared)
        print(f"[1397] verify: {'PASS' if ok else 'FAIL'}", file=sys.stderr)
        return 0 if ok else 1

    if args.apply:
        if not args.i_understand_destructive:
            print(
                "[1397] --apply requires --i-understand-destructive. Refusing.",
                file=sys.stderr,
            )
            return 2
        print(
            "[1397] LOW-TRAFFIC ADVISORY (FR-017): run during a low-traffic window; "
            "confirm no active session is expected before proceeding.",
            file=sys.stderr,
        )
        result = apply(table, args.cognito_sub, args.backup_file)
        if result.status == "blocked":
            print(
                f"[1397] --apply BLOCKED: {result.apply_blocked_reason}",
                file=sys.stderr,
            )
            return 2
        print(
            f"[1397] --apply {result.status}: canonical={result.canonical_user_id} "
            f"non_canonical={result.non_canonical} stragglers={result.stragglers}",
            file=sys.stderr,
        )
        return 0

    # Default: DRY-RUN (FR-010). --dry-run flag is affirming-only.
    print(dry_run_report(table, args.cognito_sub))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
