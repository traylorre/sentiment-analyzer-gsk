#!/usr/bin/env python3
"""Consolidate duplicate OAuth USER records into one canonical record.

Feature 1397 (oauth-dup-cleanup). SKELETON — NON-EXECUTING.

This is the safe-by-default design skeleton authored alongside
specs/1397-oauth-dup-cleanup/{spec,plan,tasks}.md. The DESTRUCTIVE paths
raise NotImplementedError on purpose: this file ships the shape of the
migration, its gates, and its algorithm — NOT a runnable consolidation.
Implementation happens in tasks T003–T015; the live `--apply` run (T027)
is a SEPARATE owner-approved action after Feature 1395 deploys.

SAFETY MODEL (see spec.md FRs):
  * DRY-RUN IS THE DEFAULT. Destructive behavior requires `--apply`.
    NOTE: this DELIBERATELY INVERTS the repo convention used by
    scripts/migrate_status_field.py (which defaults to apply, opts into
    --dry-run). That migration is additive; this one DELETES USER records,
    so it must be safe-by-default. (FR-010)
  * `--apply` additionally requires `--i-understand-destructive`, a validated
    fresh backup, an unblocked coordination gate, and the env guard. (FR-011, FR-014)
  * Canonical = earliest created_at. (FR-002)
  * Reassign-then-delete; never delete-first. Backup + audit every action. (FR-005, FR-012)

Usage (once implemented):
    # dry-run report (no writes):
    python scripts/consolidate_oauth_duplicates.py \
        --table preprod-sentiment-users \
        --cognito-sub 34f814f8-c0c1-707e-f0a6-27147065f706

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
import sys
from dataclasses import dataclass, field
from typing import Any

# Selection rule constant — aligned with Feature 1395's survivor rule.
# CONFIRMED: 1395 spec (specs/1395-oauth-account-integrity/) FR-004 pins the SAME
# rule (earliest created_at, then user_id asc). No rule negotiation remains. The
# winner for the known group is dd0da3c8-769c-466c-ae1f-3495cc851921 — computed at
# runtime by select_canonical, NEVER hard-coded in executable logic. (FR-002/002a)
CANONICAL_RULE = "earliest_created_at"

# Coordination gate: the RULE is already confirmed (1395 FR-004). This flag gates on
# the residual OPERATIONAL question of Open Q1 — is Feature 1395 DEPLOYED? Flip to True
# only after the owner confirms 1395 is live. While False, --apply is BLOCKED regardless
# of other flags. (FR-002a)
COORDINATION_CONFIRMED = False


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


# --------------------------------------------------------------------------
# Phase 1 — enumerate & select (non-destructive; to implement in T003–T007)
# --------------------------------------------------------------------------


def enumerate_group(table: Any, cognito_sub: str) -> list[GroupRecord]:
    """Paginate by_cognito_sub, GetItem each PROFILE, cross-check email/provider_sub.

    Must NOT trust GSI Limit=1. (FR-001, FR-003, EC-3, EC-5)
    """
    raise NotImplementedError("T003: implement full paginated enumeration")


def select_canonical(group: list[GroupRecord]) -> tuple[GroupRecord, list[GroupRecord]]:
    """Sort by (created_at asc, user_id asc); null created_at sorts LAST and is
    never canonical. Returns (canonical, non_canonical). (FR-002, A6)
    """
    raise NotImplementedError("T004: implement deterministic canonical selection")


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
    raise NotImplementedError("T006: implement owned-item inventory")


def render_report(canonical: GroupRecord, non_canonical: list[GroupRecord]) -> str:
    """Human-readable dry-run report. Dry-run ends here — ZERO writes. (US1, FR-010)"""
    raise NotImplementedError("T007: implement report rendering")


# --------------------------------------------------------------------------
# Phase 2 — backup & rollback (to implement in T008–T009)
# --------------------------------------------------------------------------


def backup_group(items: list[dict], path: str) -> None:
    """Full-fidelity local JSON export. NO S3 / no new AWS resource. (FR-011)"""
    raise NotImplementedError("T008: implement local JSON backup")


def validate_backup(path: str, expected_count: int) -> bool:
    """Re-open, parse, assert count == expected before any write. (FR-011, A5)"""
    raise NotImplementedError("T008: implement backup re-read validation")


def rollback(table: Any, backup_file: str) -> RunResult:
    """put_item every exported item verbatim; idempotent; runs from file alone. (FR-015)"""
    raise NotImplementedError("T009: implement rollback from backup")


# --------------------------------------------------------------------------
# Phase 3 — apply (DESTRUCTIVE CORE — gated; implement T010–T013)
# --------------------------------------------------------------------------


def reassign_item(table: Any, item: dict, canonical_id: str) -> str:
    """Reassign-then-delete. Collision → loser under {SK}#dup-{src} with
    merged_from+collision=true; never overwrite canonical; never delete an
    unresolved source. Skip items already carrying merged_from.
    (FR-005, FR-006, FR-012, FR-013, A1, A4)
    """
    raise NotImplementedError("T010: implement reassign_item (DESTRUCTIVE)")


def discard_sessions(table: Any, user_id: str) -> int:
    """Delete SESSION# items (do not re-home stale auth). (FR-007)"""
    raise NotImplementedError("T011: implement session discard (DESTRUCTIVE)")


def delete_noncanonical_profile(table: Any, user_id: str) -> None:
    """Delete only after ALL children resolved; else retain + partial. (FR-008, A4)"""
    raise NotImplementedError("T012: implement profile deletion (DESTRUCTIVE)")


def apply(table: Any, cognito_sub: str, backup_file: str | None) -> RunResult:
    """Orchestrate the destructive consolidation. Enforces every gate before acting.

    Gates (all must pass): --apply + --i-understand-destructive present,
    coordination_gate() clear, validated backup present, env guard clear. (FR-010/011/013/014/017)
    """
    raise NotImplementedError("T013: implement apply orchestration (DESTRUCTIVE)")


# --------------------------------------------------------------------------
# Phase 4 — verify (to implement in T014)
# --------------------------------------------------------------------------


def verify(table: Any, canonical_id: str, shared: dict[str, str]) -> bool:
    """Assert each GSI (by_cognito_sub/by_provider_sub/by_email) resolves to exactly
    one USER item == canonical; FAIL loudly otherwise. (FR-009, US5)
    """
    raise NotImplementedError("T014: implement post-run verification")


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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Consolidate duplicate OAuth USER records (Feature 1397). "
        "DRY-RUN by default; destructive --apply is owner-gated and NON-EXECUTING in this skeleton."
    )
    p.add_argument(
        "--table", required=True, help="DynamoDB table (no default — explicit only)"
    )
    p.add_argument("--cognito-sub", help="Cognito sub identifying the duplicate group")
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

    # Skeleton guard: this file intentionally does not execute a migration.
    if args.apply or args.rollback or args.verify:
        block = coordination_gate()
        print(
            "[1397] NON-EXECUTING SKELETON. Destructive/verify/rollback paths are not "
            "implemented here (raise NotImplementedError by design).\n"
            f"[1397] Canonical rule: {CANONICAL_RULE}. Coordination gate: "
            f"{'CLEAR' if block is None else 'BLOCKED — ' + block}",
            file=sys.stderr,
        )
        return 2

    print(
        "[1397] Dry-run entrypoint. Implement T003–T007 to enumerate the group, "
        "select the earliest-created canonical, inventory owned data, and print the "
        "report. No writes occur in dry-run.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
