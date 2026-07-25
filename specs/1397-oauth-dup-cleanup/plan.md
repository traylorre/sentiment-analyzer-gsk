# Plan — Feature 1397: oauth-dup-cleanup

**Artifact type:** Migration design + non-executing script skeleton. No destructive action in this feature.
**Script home:** `scripts/consolidate_oauth_duplicates.py` (alongside existing `scripts/migrate_status_field.py`, `scripts/audit_duplicate_provider_subs.py`, `scripts/cleanup_orphaned_sessions.py`).
**Tests:** `tests/unit/scripts/test_consolidate_oauth_duplicates.py` (moto, `-m "not preprod"`). NOTE: `tests/unit/scripts/` does NOT exist yet — T002 creates the directory + `__init__.py` (matching the package convention used by `tests/unit/dashboard/`).

---

## 1. Migration algorithm

```
INPUT: --table <name>  --cognito-sub <sub>  [--apply]  [--backup-file <path>]
       [--allow-prod]  [--i-understand-destructive]  [--verify]

0. GUARD (FR-014)
   - require --table (no default)
   - resolve + PRINT: table name, aws account id, caller ARN (sts get-caller-identity)
   - if "prod" in table name and not --allow-prod: HARD STOP
   - default mode = DRY-RUN unless --apply (FR-010)

1. ENUMERATE GROUP (FR-001, FR-003, EC-3)
   - query by_cognito_sub GSI for the sub → collect ALL user_ids (paginate; do NOT trust Limit=1)
   - for each user_id: strongly-consistent GetItem PK=USER#{id}, SK=PROFILE
   - assert group shares email + provider_sub; divergence → report + block --apply for group (FR-001, EC-5)

2. SELECT CANONICAL (FR-002, FR-002a, A6)
   - sort group by (created_at asc, user_id asc); null/malformed created_at sorts LAST
   - canonical = first; if canonical lacks created_at → block --apply, flag
   - COORDINATION GATE (FR-002a): assert selection rule == Feature 1395 login tie-break.
     Until confirmed (Open Q1), --apply is BLOCKED even with all other flags.

3. INVENTORY OWNED DATA (FR-004)
   - for each NON-canonical user_id: query PK=USER#{id} (paginate)
   - classify by SK prefix: PROFILE / CONFIG# / ALERT# / NOTIF# / PREF# / SESSION# / <unknown>
   - <unknown> prefixes reported, never dropped

4. REPORT (US1, FR-018)
   - print the RUNTIME-COMPUTED canonical (user_id + created_at + rule applied),
     the non-canonical ids, per-record inventory, planned action per item —
     the FULL reassignment plan, printed at execution time
   - the owner compares this printout to their own independently-queried
     expectation BEFORE approving --apply (FR-018); no artifact names the winner
   - DRY-RUN ENDS HERE — zero writes

--- everything below only under --apply, after gates pass ---
--- ALL gates are enforced INSIDE apply(), not only in main() (AR#5/A7) ---

5. BACKUP (FR-011, A5, A9)
   - export EVERY affected item (all group PROFILEs + all owned items), full attribute fidelity, to local JSON
   - re-open + parse the file; assert parsed_count == enumerated_count AND
     exact (PK, SK) key-set equality vs the fresh enumeration; else ABORT
   - record SHA-256 of the serialized backup in the audit log
   - a --backup-file whose key set mismatches the current group is REFUSED
   - NO S3 / new AWS resource (Open Q2 if S3 desired)

5b. FREEZE + ASSERT (FR-019, FR-020)
   - re-enumerate the group immediately before the destructive phase
   - any user_id/item NOT in the validated backup → straggler: never touched,
     reported (fail-closed; a concurrent-login dup created mid-run lands here)
   - HARD-ASSERT the canonical id is absent from every delete/discard/
     reassign-source set; abort with zero writes if it appears

6. APPLY per non-canonical user_id (FR-005..FR-008, FR-012, FR-013)
   for each owned item (excluding PROFILE):
     - CONFIG#/ALERT#/NOTIF#/PREF#:
         target = PK=USER#{canonical}, SK=same
         if target exists (collision, FR-006):
             write loser under SK={SK}#dup-{src_short}, set merged_from + collision=true
         else:
             put target with new item (user_id=canonical, merged_from=src), ConditionExpression attribute_not_exists(PK+SK)
         CONFIRM write succeeded → then delete source item
         if write NOT confirmed → do NOT delete source; mark run partial (FR-012, A4)
     - SESSION#: delete (discard, FR-007), log
     - idempotency: item already carrying merged_from (incl. collision-diverted) → skip (FR-013, A1)
   AFTER all children resolved for this user_id:
     - append non-canonical PROFILE to backup+audit, then DELETE it (FR-008)
     - if ANY child unresolved → retain PROFILE, run=partial (A4)

7. VERIFY (FR-009, US5, --verify)
   - query by_cognito_sub / by_provider_sub / by_email for shared values
   - assert exactly ONE USER item each, == canonical; else FAIL loudly

8. AUDIT (FR-012)
   - every reassign/divert/delete → append-only JSONL: {ts, action, source_key, target_key, outcome}
```

**Idempotency invariant:** an item is "done" iff (target exists carrying `merged_from`) OR (source no longer exists). A re-run recomputes the group, sees markers, and performs zero new destructive writes → `already-consolidated`.

---

## 2. Canonical-selection decision (and coordination with 1395)

**Decision: canonical = earliest `created_at`** (the record created `2026-07-24T03:16:42Z` — the true earliest, re-queried live by an independent refuter), `user_id` asc as secondary tie-break. Per FR-018 the winner's id is NOT recorded in any artifact; `select_canonical` computes it at runtime and the dry-run prints it for owner comparison.

**Why earliest-created (not most-data, not GSI-first):**
- **Deterministic & reproducible.** `created_at` is immutable; re-runs and independent operators pick the same record. "Most owned data" changes as data moves and is undefined when all records own nothing (our exact case — all 10 own only PROFILE).
- **GSI-first is non-deterministic.** `get_user_by_email_gsi`, `get_user_by_provider_sub`, `get_user_by_cognito_sub` (all in `src/lambdas/dashboard/auth.py`) issue hash-only `Limit=1` queries. DynamoDB returns an arbitrary member of the group. Picking "whatever the GSI returns first" is not stable and must not be the canonical rule (FR-003).
- **Owned data is decoupled from the choice.** FR-005 moves any owned data ONTO the canonical regardless of which record accumulated it, so choosing the oldest record never loses data (EC-6).

**Coordination with Feature 1395 — RULE CONFIRMED (deploy status is the residual gate — FR-002a, Open Q1):**
1395 fixes the fragmentation by making login resolve an existing user instead of minting a new `user_id`. Its spec exists (`specs/1395-oauth-account-integrity/`) and **FR-004 pins the SAME survivor rule this feature uses: earliest `created_at`, then `user_id` ascending.** The rule alignment is therefore confirmed, not assumed — both features crown the same runtime-computed winner (id not recorded per FR-018). For a table that *already* contains duplicates, 1395's resolver still hits a `Limit=1` hash query until cleanup collapses the group to one record; after cleanup there is exactly one record so `Limit=1` is deterministic. If a future revision of 1395 instead:
- adds a dedup on write (so no NEW dups) but leaves reads as `Limit=1` → reads stay non-deterministic among the existing 10 until cleanup runs; cleanup collapsing to earliest is fine, and afterward there is exactly one record so `Limit=1` is deterministic. **This is the most likely reality** (1395 is a write-path fragmentation fix).
- picks a DIFFERENT surviving record (e.g. most-recent) → cleanup MUST change FR-002 to match, else the login lands on a deleted PK.

Because 1395's spec exists and its FR-004 confirms the identical earliest-`created_at` rule, the tie-break alignment is **settled**. What remains gating the destructive step is purely operational: **confirm 1395 is DEPLOYED** (so it is actively preventing new fragmentation) before `--apply`. Dry-run + backup + everything non-destructive proceed now; `--apply` waits on that Open Q1 deploy-status confirmation.

---

## 3. Dry-run / apply / backup / rollback mechanics

- **Dry-run (default, FR-010):** steps 0–4 only. Deliberately inverts the repo convention (`migrate_status_field.py` defaults to APPLY, opts into `--dry-run`). Justification: that migration is additive (backfills a field); this one DELETES USER records. Safe-by-default beats convention here; the inversion is called out in the script docstring and in tasks.md.
- **Apply (FR-010, FR-011):** requires `--apply` AND `--i-understand-destructive` AND a validated backup (fresh or `--backup-file`). Refuses without all three. Prints a final "about to delete N records" summary.
- **Backup (FR-011):** local JSON, full-fidelity export of all affected items. Re-read + count-checked before any write (A5). No S3 bucket / no new AWS resource without owner approval (Open Q2).
- **Rollback (FR-015):** `--rollback --backup-file <path>` re-`put_item`s every exported item verbatim; idempotent; runnable from the file alone with no recomputation. Restores the 10 PROFILEs (and any moved children) to pre-migration state.

---

## 4. Reuse assessment — `merge_anonymous_data` (FR-016)

Read `src/lambdas/shared/auth/merge.py`. **Not reused directly.** Borrow the pattern, not the function:

| Aspect | merge_anonymous_data | 1397 needs |
|---|---|---|
| Entity coverage | CONFIGURATION, ALERT_RULE, PREFERENCE only (`entity_type` filter) | + NOTIF#, + SESSION# handling, + unknown-prefix reporting |
| Collision path | `put ConditionExpression=attribute_not_exists(PK)`; **still tombstones source on ConditionalCheckFailed** → source can be marked merged while target write was skipped (data-loss risk) | keep-canonical, preserve-loser under suffixed SK; never delete an unresolved source (FR-006, FR-012) |
| Deletion | tombstone (mark, keep) — never deletes source | actually DELETE non-canonical records (that's the point) — but only after backup + child resolution |
| Safety rails | none (no dry-run, no backup, no env guard) | dry-run default, backup gate, prod guard |
| Idempotency markers | `merged_from` / `merged_to` — good | reuse this exact marker convention |

Borrowed: reassign-then-mark ordering, `merged_from`/`merged_to` markers, conditional writes for concurrency. A dedicated script is safer than calling the helper (its collision/tombstone semantics conflict with FR-006/FR-012).

---

## 5. Constitution check

| Constitution requirement | Compliance |
|---|---|
| No unauthenticated management access | Script runs under the operator's IAM (`sts` identity printed); acts on server-authoritative `cognito_sub`, never client input. PASS |
| Least-privilege DB credentials | Runs with the operator's existing preprod deployer creds; no privilege escalation; recommend read-only dry-run runs. PASS |
| No secrets in source | Script takes table/sub as args; no credentials embedded. PASS |
| Parameterized / safe DB access | boto3 expression-attribute-values (parameter binding), never string-concatenated queries. PASS |
| Protect logs from injection | Reuse `sanitize_for_log` for any logged identifiers; user_ids/subs truncated + sanitized. PASS |
| No new AWS resources without approval (project standing constraint) | Backup is a LOCAL file; S3 destination is an Open Question, not a default. PASS |

**Constitution gate: PASS.** No new infra, no new external surface, acts within existing IAM, safe query construction.

---

## Adversarial Review #2 — Drift & Consistency

Checking plan.md against the (AR#1-amended) spec.md for contradictions, gaps, and untraceable steps.

| # | Check | Finding | Resolution |
|---|---|---|---|
| D1 | Every FR maps to a plan step? | FR-001→step1, FR-002/002a→step2, FR-003→step1, FR-004→step3, FR-005/006/007/008→step6, FR-009→step7, FR-010→step0, FR-011→step5, FR-012→step6+8, FR-013→idempotency invariant, FR-014→step0, FR-015→§3 rollback, FR-016→§4, FR-017→ (missing from plan). | **GAP:** FR-017 (low-traffic window / stale-client self-heal, added in AR#1) not reflected in plan. Add to step 0 guard: `--apply` prints a low-traffic-window advisory and, for interactive runs, requires operator to confirm no active session expected. Non-blocking, advisory. FIXED below. |
| D2 | AR#1 spec edits reflected in plan? | A1 (collision items carry `merged_from`) → plan step6 says "item already carrying merged_from (incl. collision-diverted) → skip" ✓. A4 (PROFILE deleted only after all children) → plan step6 "AFTER all children resolved" ✓. A5 (backup re-read) → step5 ✓. A6 (null created_at sorts last) → step2 ✓. | Consistent. No drift. |
| D3 | Canonical value consistent across artifacts? | spec FR-002 + C2 + plan §2 all state the RULE (earliest `created_at`, `user_id` asc) with NO literal winner — FR-018 bans literal ids after the AR#4/NF-1 near-miss (a prior draft named a wrong record; exactly the error class FR-018 now prevents mechanically). ✓ | Consistent. |
| D4 | Convention inversion documented in both? | plan §3 + spec FR-010 both state the dry-run-default inversion vs `migrate_status_field.py`. ✓ | Consistent. |
| D5 | Does plan invent scope not in spec? | Plan adds `--rollback` subcommand — traces to FR-015. Adds `--verify` — traces to FR-009/US5. No orphan scope. | OK. |
| D6 | Coordination gate consistent? | spec FR-002a + Open Q1 + plan §2 all block `--apply` on 1395 tie-break confirmation. ✓ | Consistent. |
| D7 | Constitution check complete? | §5 covers auth, least-priv, secrets, safe queries, log injection, no-new-infra. Maps to constitution security section. ✓ | OK. |
| D8 | Idempotency definition stable? | spec FR-013 (target exists + merged_from, or source gone) == plan idempotency invariant. ✓ | Consistent. |

### Edit applied (D1)
Step 0 guard amended to satisfy FR-017: under `--apply`, the script prints a low-traffic-window advisory and (interactive) requires an explicit confirmation that no active session is expected. Advisory, non-blocking; the real safety comes from running post-1395 + SESSION# discard.

### Gate — Adversarial Review #2
**PROCEED to tasks.md.** One gap found (FR-017 not carried into the plan) and fixed. No contradictions between spec and plan. Canonical selection, safety rails, idempotency, and the 1395 coordination gate are consistent across both artifacts. The destructive `--apply` remains blocked on Open Q1 — correct.

---

## Adversarial Review #6 — Finalization drift check (post-AR#5)

Re-checking plan against the AR#5-amended spec (new FR-018/019/020, amended FR-011, gate-inside-apply).

| # | Check | Finding | Resolution |
|---|---|---|---|
| E1 | FR-018 mapped? | Step 4 amended: dry-run prints runtime-computed canonical + full reassignment plan; no artifact names the winner; plan §2 and D3 scrubbed of literal ids. ✓ | Consistent. |
| E2 | FR-019 mapped? | New step 5b: pre-destructive hard assertion that the canonical is absent from every destructive set. ✓ | Consistent. |
| E3 | FR-020 mapped? | New step 5b: frozen delete set — re-enumerate before apply, stragglers (concurrent-login dups) untouched + reported. ✓ | Consistent. |
| E4 | FR-011 amendment mapped? | Step 5 now validates key-set equality (not count-only), records SHA-256, refuses mismatched `--backup-file`. ✓ | Consistent. |
| E5 | A7 gate placement mapped? | Banner above step 5: all gates enforced INSIDE `apply()`; `main()` only collects flags. Carried to T013/T034. ✓ | Consistent. |
| E6 | Any remaining literal live-data id in plan.md? | Grep for the known ids returns zero after this round (only the rule and timestamps remain). ✓ | Clean. |
| E7 | Does the plan still avoid inventing scope? | Step 5b traces to FR-019/FR-020; nothing else added. No orphan scope. ✓ | OK. |

### Gate — Adversarial Review #6
**PROCEED to tasks finalization.** All AR#5 spec changes are reflected in the plan; no drift, no literal ids, no orphan scope.
