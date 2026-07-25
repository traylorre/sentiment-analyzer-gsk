# Feature 1397: oauth-dup-cleanup — Consolidate Duplicate OAuth User Records

**Status:** DRAFT (owner-gated data migration — plan + non-executing script only)
**Environment:** preprod (the 10 known duplicates are preprod-only). Prod applicability noted, not executed.
**Depends on:** Feature 1395 (OAuth login fragmentation fix) MUST be deployed before any `--apply` run, so new logins stop minting fresh `user_id`s during/after cleanup.
**Type:** Owner-approved, backup-gated, dry-run-by-default DATA MIGRATION. This feature ships a PLAN and a SAFE-BY-DEFAULT SCRIPT. It performs NO destructive action during the battleplan.

---

## Context (verified live this session — ground truth)

The live `preprod-sentiment-users` DynamoDB table (single-table design) holds **10 duplicate `USER` records** for one Cognito `sub` (`34f814f8-c0c1-707e-f0a6-27147065f706`), all `auth_type=google`, email `scotthazlett@gmail.com`, created across 2026-07-24. Each Google login minted a new `user_id` (the fragmentation bug, fixed separately by Feature 1395).

Verified facts used by this spec:

| Fact | Value | How verified |
|---|---|---|
| Duplicate USER records | 10 | `query by_cognito_sub` → 10 items |
| Shared cognito_sub | `34f814f8-c0c1-707e-f0a6-27147065f706` | same on all 10 |
| Shared email / provider | `scotthazlett@gmail.com` / google | same on all 10 |
| Earliest `created_at` | `2026-07-24T03:16:42.164498Z` — **winner's `user_id` deliberately NOT recorded here (FR-018)**; it is computed at runtime by `select_canonical` and printed by the dry-run for owner comparison | min over the 10 (re-queried live by independent refuter) |
| Latest `created_at` | `2026-07-24T21:18:06.865682Z` (id not recorded — FR-018) | max over the 10 |
| Owned data per duplicate | **PROFILE only** — zero CONFIG#/ALERT#/NOTIF#/SESSION# | `query PK=USER#{id}` for all 10 returned only `SK=PROFILE` |
| GSI resolution today | non-deterministic | `by_email`, `by_provider_sub`, `by_cognito_sub` all use hash-only `Limit=1` queries (`auth.py`) |

**Consequence of the last two rows:**
1. Consolidation of the current 10 is data-preserving even if we discarded owned data, because none exists beyond PROFILE. The script must still handle owned data generically (for prod / future runs).
2. Login resolution today returns an *arbitrary* one of the 10. Feature 1395 must introduce a deterministic tie-break. **Cleanup's canonical choice MUST equal 1395's tie-break, or cleanup will delete the record the code keeps reusing.** This is the central coordination risk (see FR-002, Open Questions).

---

## User Stories

### US1 — Operator consolidates duplicates into one canonical account (P1)
As the on-call operator, I run a dry-run that enumerates all USER records sharing a `cognito_sub`, names the canonical record, lists every owned item that would move or be discarded, and writes a human-readable report — **without changing any data** — so I can review before approving.

**Acceptance:**
- Given the 10 duplicates, when I run the script with no flags, then it prints/records the canonical `user_id`, the 9 non-canonical `user_id`s, an owned-item inventory per record, and exits WITHOUT any DynamoDB write.
- The report states the canonical-selection rule applied and the value it keyed on (earliest `created_at`).

### US2 — Operator preserves owned data during consolidation (P1)
As the operator, when a non-canonical duplicate owns configs/alerts/notifications, the migration reassigns those items to the canonical `user_id` (not the discard path) so no user-created data is lost.

**Acceptance:**
- Given a non-canonical record owning N configs, when `--apply` runs (post-approval, post-backup), then those N configs exist under the canonical `user_id` and are reachable by the canonical account's normal queries.
- Given a config that collides (same logical config under two records), the migration does NOT silently drop either — it applies the documented collision rule (FR-004) and logs the decision.

### US3 — Operator runs safely and reversibly (P1)
As the operator, before any destructive write I must produce a real backup of every affected item, and I can restore from that backup if the migration goes wrong.

**Acceptance:**
- `--apply` refuses to run unless a backup file was produced in this invocation (or `--backup-file` points at a valid prior export) AND `--i-understand-destructive` (or equivalent explicit token) is present.
- Every delete/reassign is written to an append-only audit log with before/after keys.
- A documented rollback restores the pre-migration state from the backup file.

### US4 — Operator cannot run against the wrong environment by accident (P1)
As the operator, the script must confirm it is pointed at the intended table/account and refuse prod unless prod is explicitly named and separately approved.

**Acceptance:**
- The script prints the resolved table name + AWS account id + caller ARN and requires `--table` to be passed explicitly (no default that silently hits prod).
- If the resolved table name resolves to a prod environment, the script hard-stops unless `--allow-prod` is also passed (and prod is out of scope for this feature's execution). The prod-detection rule (shared by spec and code, FR-014) is: hard-stop if ANY hyphen-delimited segment equals `prod`, OR the name contains a `prod`/`production` token that is NOT part of `preprod` — while never false-tripping on `preprod`. This catches `sentiment-prod-users`, `production-sentiment-users`, and `prod-sentiment-users`, and lets `preprod-sentiment-users` through.

### US5 — GSI projections resolve to exactly one record afterward (P2)
As the operator, after consolidation every identity index (`by_cognito_sub`, `by_provider_sub`, `by_email`) resolves to exactly the canonical record, with no orphan projections pointing at deleted duplicates.

**Acceptance:**
- After `--apply`, a `--verify` pass queries each GSI for the shared identifiers and asserts exactly one USER item returned, and that it is the canonical `user_id`.

---

## Functional Requirements

### Canonical selection
- **FR-001** The script MUST group candidate USER records by `cognito_sub` (server-authoritative identifier), scoped to a single group per invocation (the target `cognito_sub` is an explicit argument). It MUST also cross-check that the group shares the same `email` and `provider_sub`; any divergence is reported and blocks `--apply` for that group (a divergent identifier means it may not be a true duplicate).
- **FR-002** The canonical record MUST be selected by **earliest `created_at`** (oldest wins), with `user_id` lexicographic order as a deterministic secondary tie-break if two `created_at` values are identical. The rule MUST be deterministic and reproducible across runs. Per FR-018, the winner is NEVER named in this spec or any artifact: it is computed at runtime by `select_canonical` and surfaced by the dry-run printout for owner comparison. (For traceability: the true earliest record was created `2026-07-24T03:16:42Z` and is a normal non-tombstoned Google USER — verified live by an independent refuter.)
  - **FR-002a (coordination gate)** The canonical-selection rule MUST match Feature 1395's post-fix login-resolution tie-break. **This is confirmed:** Feature 1395's spec (`specs/1395-oauth-account-integrity/`) FR-004 pins the SAME rule — earliest `created_at`, then `user_id` ascending — so the rule is aligned by construction. The residual gate is operational, not a rule dispute: `--apply` remains BLOCKED until the owner confirms **1395 is DEPLOYED** (see Open Questions Q1). Rationale: running cleanup before 1395 is live lets new logins keep minting fresh `user_id`s during/after consolidation.
- **FR-003** The script MUST NOT assume the GSI `Limit=1` query returns the canonical record; it MUST enumerate the FULL group (paginated) and compute the canonical itself. Relying on the arbitrary GSI-first item is prohibited.

### Owned-data reassignment
- **FR-004** For each non-canonical `user_id`, the script MUST enumerate ALL owned items via `query PK=USER#{user_id}` (paginated), classifying by `SK` prefix: `PROFILE`, `CONFIG#`, `ALERT#`, `NOTIF#`, `SESSION#`, `PREF#`, and any unrecognized prefix (reported, never silently dropped).
- **FR-005** Owned CONFIG#/ALERT#/NOTIF#/PREF# items MUST be reassigned to the canonical record by writing a new item under `PK=USER#{canonical_id}` (preserving `SK`, rewriting `user_id` and any embedded owner reference) BEFORE the source item is deleted. Reassignment MUST use a conditional write; the source delete MUST occur only after the reassigned write is confirmed (reassign-then-delete, never delete-first).
- **FR-006 (collision rule)** If a reassignment target key (`PK=USER#{canonical}`, same `SK`) already exists, the item is a collision. The default rule is **keep-canonical, preserve-loser**: do NOT overwrite the canonical item; write the losing item under a collision-suffixed `SK` (`{SK}#dup-{source_user_id_short}`) so no data is destroyed, and record the collision in the audit log for owner review. The script MUST NOT tombstone/delete a source item whose reassignment was skipped or diverted (this closes the merge-helper data-loss gap — see FR-012).
- **FR-007** SESSION# items on non-canonical records MUST be discarded (deleted), not reassigned. Sessions are short-lived credentials bound to a specific login; re-homing them onto the canonical record would resurrect stale auth material. Their deletion MUST be logged.
- **FR-008** The canonical PROFILE MUST be retained as-is. Non-canonical PROFILE records MUST be deleted (after their owned data is reassigned per FR-005/006), which is what collapses the group to one. Before deletion, each non-canonical PROFILE MUST be written to the backup and audit log.

### GSI hygiene
- **FR-009** After deletion of the 9 non-canonical PROFILE records, the shared `by_cognito_sub`, `by_provider_sub`, and `by_email` values MUST project exactly one USER item (the canonical). The `--verify` pass MUST assert this and FAIL loudly otherwise. Because these GSIs project from the base item, deleting the base PROFILE removes its projection automatically; `--verify` guards against partial-failure leftovers.

### Safety, audit, rollback
- **FR-010 (dry-run default)** The script MUST default to dry-run. Destructive behavior requires an explicit `--apply` flag. (This deliberately INVERTS the repo's existing `--dry-run`-opt-in convention used by `scripts/migrate_status_field.py`, because this migration is destructive; the inversion is documented in plan.md.)
- **FR-011 (backup gate)** `--apply` MUST refuse to proceed without a fresh pre-flight backup produced in the same invocation (default), or a `--backup-file` pointing at a validated prior export of the same group. The backup is a **local JSON export** of every affected item (all group PROFILEs + all their owned items, full attribute fidelity). Validation (AR#1/A5 + AR#5/A9): after writing, the script MUST re-open and parse the file and assert (a) item count == enumerated count AND (b) the exact (PK, SK) key set matches the enumerated key set — count-only validation is insufficient (right count, wrong items). A SHA-256 of the serialized backup MUST be recorded in the audit log so post-hoc integrity of the rollback source is checkable. No new AWS resource (e.g. S3 bucket) may be created without separate owner approval; if an S3 destination is desired, it is an Open Question, not a default.
- **FR-012 (no silent failure / no data loss)** Every reassign, collision-divert, and delete MUST be logged to an append-only audit log (JSONL) with: timestamp, action, source key, target key (if any), and outcome. A reassignment failure MUST abort the source delete for that item and mark the run `partial`; the script MUST NOT continue deleting other items in a way that could strand references. The known merge-helper gap — tombstoning a source even when its target write hit a ConditionalCheckFailed — MUST NOT be reproduced here.
- **FR-013 (idempotency)** Re-running `--apply` after a completed or partial run MUST be safe: already-reassigned items are detected (target exists + carries `merged_from`) and skipped; already-deleted records are no-ops. A second full run MUST make zero additional destructive writes and report `already-consolidated`.
- **FR-014 (environment guard)** Per US4: explicit `--table` (no default), printed account/ARN, prod hard-stop behind `--allow-prod`. **Prod-detection rule (authoritative, matched by `_env_guard` in the script):** refuse if ANY hyphen-delimited segment of the table name equals `prod`, OR the name matches a `prod`/`production` pattern that is NOT `preprod`. `preprod` MUST NOT be false-tripped; real prod names (`sentiment-prod-users`, `production-...`, `prod-...`) MUST be caught. (Earlier drafts only tested the FIRST hyphen segment == `prod`, which let `sentiment-prod-users` and `production-...` bypass the guard — corrected in Adversarial Review #4.)
- **FR-015 (rollback)** A documented rollback procedure MUST restore every backed-up item verbatim (`put_item` of the exact exported attributes) and MUST be runnable from the backup file alone, without recomputation. Rollback MUST be idempotent.
- **FR-016 (merge-helper assessment)** The design MUST record whether `src/lambdas/shared/auth/merge.py:merge_anonymous_data` is reused. Assessment (this spec): it is NOT reused as-is because (a) it only handles `entity_type` in {CONFIGURATION, ALERT_RULE, PREFERENCE} and ignores NOTIF#/SESSION#, (b) its collision path tombstones the source even when the target write is skipped (potential data loss, contradicts FR-006/FR-012), and (c) it has no backup/dry-run/environment gate. Its **reassign-then-tombstone, conditional-write, `merged_from`/`merged_to` idempotency markers** are a good pattern to borrow; a dedicated migration is safer than calling it directly.
- **FR-017 (low-traffic window, from AR#1/A2)** `--apply` SHOULD run during a low-traffic window; under `--apply` the script prints a low-traffic advisory and (interactive) asks the operator to confirm no active session is expected. Advisory, non-blocking; real safety comes from running post-1395 + SESSION# discard.
- **FR-018 (no literal live-data identifiers — the near-miss constraint)** NO live-data identifier (any of the 10 `user_id`s, and specifically the canonical winner) may appear as a literal in ANY artifact of this feature (spec/plan/tasks/script/tests) or in executable logic. Rationale: a prior draft hard-coded the WRONG canonical (a mid-day record, `06:40` UTC) instead of the true earliest (`03:16` UTC), and the error propagated into 5 artifacts before an independent refuter re-queried live DynamoDB and caught it. The winner is computed at runtime by `select_canonical` ONLY. The dry-run MUST print, at execution time: (a) the computed canonical `user_id` + its `created_at` + the rule applied, and (b) the FULL reassignment plan (every non-canonical id, every owned item, the planned action per item). The owner compares that printout to their own independently-queried expectation BEFORE approving `--apply`. Enforcement: a test statically scans the script source and fails if any UUID-shaped literal is present (synthetic ids live only in test fixtures).
- **FR-019 (canonical-never-destroyed guard)** The canonical `user_id` MUST be structurally excluded from every destructive set (reassign-source, session-discard, profile-delete). Immediately before any destructive phase, the script MUST assert the canonical id is absent from all pending delete/discard/reassign-source lists and HARD-ABORT (no writes) if it appears. This guards the case where a selection bug (or a rule change in 1395) would otherwise delete the record 1395's live code resolves to. Because 1395 FR-004 pins the same rule, the record 1395 reuses IS the canonical — this guard makes that invariant enforced, not assumed.
- **FR-020 (frozen delete set / fail-closed on stragglers)** Only items present in the validated backup may be deleted or mutated. Immediately before the destructive phase, the script MUST re-enumerate the group; any `user_id` or item discovered that is NOT in the backup (e.g., a new duplicate minted by a concurrent login mid-run) MUST NOT be touched — it is reported as a straggler for a future run, and the run proceeds only against the frozen, backed-up set. `--verify` will then fail exactly-one and name the straggler, prompting a fresh dry-run→backup→apply cycle rather than an unbacked-up delete.

---

## Success Criteria

- **SC-1** Dry-run on the known group prints the runtime-computed canonical (the record with earliest `created_at`, `2026-07-24T03:16:42Z`), the 9 non-canonical ids, the full reassignment plan, and "owned items: PROFILE only" for each — with zero DynamoDB writes (verifiable via CloudTrail / no mutation). The owner compares the printed canonical against their own live query before any approval (FR-018).
- **SC-2** (post-approval, post-1395, post-backup) `--apply` collapses the group to exactly 1 USER record; `--verify` confirms each GSI resolves to canonical only.
- **SC-3** No user-created data (configs/alerts/notifications) is lost; for the known group this is trivially true (none exists), and the moto test suite proves the reassignment path preserves data on synthetic groups that DO own data.
- **SC-4** A second `--apply` is a no-op (`already-consolidated`).
- **SC-5** Rollback from the backup restores all 10 records byte-for-byte on a moto fixture.
- **SC-6** The script cannot run against a `prod`-named table without `--allow-prod`; default invocation is dry-run.

---

## Edge Cases

- **EC-1 (collision):** A duplicate owns a CONFIG whose `SK` equals a CONFIG already under the canonical. → FR-006 keep-canonical, preserve-loser under suffixed SK; logged for owner review. Never a silent overwrite or drop.
- **EC-2 (mid-session duplicate):** A duplicate is actively logged in (has a live SESSION# / an in-flight request) when cleanup runs. → SESSION# discarded (FR-007); the live client's next call resolves via the (post-1395 deterministic) identity path to the canonical record, so it lands on the surviving account rather than a deleted one. Running AFTER 1395 is deployed is what makes this safe (Depends-on).
- **EC-3 (eventual consistency):** A just-created duplicate has not yet propagated to the `by_cognito_sub` GSI when the group is enumerated. → Enumeration MUST use a **strongly-consistent base-table read where possible** and re-enumerate immediately before `--apply`; the `--verify` pass catches a straggler by asserting exactly-one post-run and failing if a late projection appears. A straggler duplicate created after backup is out of scope for that run and reported.
- **EC-4 (partial failure mid-migration):** The process dies after reassigning 3 of 5 items. → Reassign-then-delete ordering (FR-005) + `merged_from` markers (FR-013) mean re-running resumes safely; no source is deleted whose target write did not confirm.
- **EC-5 (divergent identifier):** One of the "duplicates" has a different `email` or `provider_sub`. → FR-001 reports and BLOCKS `--apply` for the group; a human decides whether it is truly the same person.
- **EC-6 (canonical owns nothing, a duplicate owns everything):** Canonical is earliest-created but a later duplicate accumulated all the configs. → Still consolidate onto earliest (to match 1395's login target); FR-005 moves the later duplicate's data ONTO the canonical. Owned data follows the person, not the record age.
- **EC-7 (canonical lands in a destructive set):** A selection or bookkeeping bug puts the canonical `user_id` into the delete/discard/reassign-source lists. → FR-019 pre-destructive assertion HARD-ABORTS with zero writes. The record 1395's live code resolves to is never deletable, even under a bug.
- **EC-8 (new duplicate minted mid-run):** A concurrent Google login creates an 11th duplicate between backup and apply. → FR-020: the delete set is frozen to the backed-up items; the straggler is untouched and reported. `--verify` fails exactly-one and names it; the operator runs a fresh dry-run→backup→apply cycle. Nothing is ever deleted that is not in a validated backup.

---

## Threat Model

| Threat | Vector | Mitigation |
|---|---|---|
| Accidental data loss | Delete before reassign; collision silently overwrites; merge-helper tombstone gap | Reassign-then-delete (FR-005); keep-canonical-preserve-loser collision (FR-006); mandatory backup (FR-011); audit log (FR-012); dedicated migration, not the leaky helper (FR-016) |
| Running against prod by mistake | Default table hitting prod; muscle-memory `--apply` | No default `--table` (FR-014); printed account/ARN; prod hard-stop behind `--allow-prod`; dry-run default (FR-010) |
| Partial failure mid-migration | Process crash between reassign and delete | Reassign-then-delete ordering + `merged_from` idempotency markers (FR-013/EC-4); run marked `partial`, resumable |
| Canonical mismatch with code | Cleanup keeps a record 1395 won't reuse | FR-002a coordination gate blocks `--apply` until 1395's tie-break is confirmed to equal earliest-`created_at` |
| Double-run destruction | Operator re-runs `--apply` | Idempotency (FR-013); already-consolidated no-op |
| Login during migration | New/refreshing session lands on a deleting record | Run only after 1395 deployed (Depends-on); SESSION# discard (FR-007); EC-2 |
| Silent GSI orphan | Partial delete leaves a projection | `--verify` asserts exactly-one per GSI (FR-009) |
| Backup unusable | Export missing attributes / not validated | Full-fidelity JSON export; `--apply` validates backup covers the group before proceeding (FR-011); rollback runs from file alone (FR-015) |

---

## Adversarial Review #1

Attacking the spec as written, assuming a hostile/careless operator and an unlucky runtime.

| # | Attack | Finding | Severity | Resolution |
|---|---|---|---|---|
| A1 | **Run the script twice** (operator forgets it already applied). | Idempotency was asserted (FR-013) but the collision rule (FR-006) writes a suffixed `{SK}#dup-…` item — on a second run the suffixed item itself has no `merged_from` guard described, risking a `#dup-#dup-…` chain. | HIGH | Edit FR-006/FR-013: collision-diverted items MUST also carry `merged_from` + a `collision=true` marker, and the skip-logic MUST treat any item already carrying `merged_from` (including diverted ones) as done. Second run re-scans, sees markers, no new writes. |
| A2 | **A login happens DURING migration** (between enumerate and delete). | EC-2 relies on 1395 being deployed. But 1395 makes NEW logins resolve deterministically; it does NOT stop an already-issued token whose `user_id` points at a soon-to-be-deleted duplicate. That client keeps sending the stale `user_id` until its token refreshes. | MEDIUM | Add FR-017: `--apply` SHOULD run during a low-traffic window and, for preprod, the owner confirms no active session. Post-1395, a stale-`user_id` request will 404/re-auth rather than corrupt data (no writes land on a deleted PK create data; they fail). Document that a stale client self-heals on next login. Not a data-integrity risk, a UX blip. Recorded, not blocking. |
| A3 | **Canonical selection disagrees with what 1395's code will reuse.** | FR-002a names the risk and blocks `--apply`. Feature 1395's spec DOES exist (`specs/1395-oauth-account-integrity/`) and its FR-004 confirms the SAME rule (earliest `created_at`, then `user_id` asc) — so the RULE is aligned. The only remaining gate is confirming 1395 is DEPLOYED before any `--apply`. | HIGH (correctly gated) | Keep FR-002a as a hard `--apply` block. Rule alignment is confirmed via 1395 FR-004; Open Q1 narrows to "is 1395 deployed?" — an owner deploy-status confirmation, not a rule negotiation. Dry-run and all non-destructive work proceed; destructive step waits on the deploy confirmation. This is the correct gate, not a defect. |
| A4 | **An owned item fails to reassign halfway** (throttling, conditional-check race). | FR-005/FR-012 handle abort-source-delete, but did not specify what happens to the PARENT non-canonical PROFILE when one of its children failed. If PROFILE is deleted while a child reassignment is pending, the child is orphaned. | HIGH | Edit FR-008: a non-canonical PROFILE MUST NOT be deleted until ALL its owned items are confirmed reassigned-or-diverted-or-discarded. If any child is unresolved, the PROFILE is retained and the run is `partial`; re-run resumes. |
| A5 | **Backup written but to a full disk / truncated.** | FR-011 requires a backup exists; did not require it be re-readable. | MEDIUM | Edit FR-011: after writing the backup, the script MUST re-open and parse it and assert item count == enumerated count before permitting `--apply`. |
| A6 | **`created_at` missing or malformed** on one record. | FR-002 sorts by `created_at`; a null would sort unpredictably and could crown the wrong canonical. | MEDIUM | Edit FR-002: records with missing/unparseable `created_at` sort LAST (never auto-canonical) and are flagged; if the intended canonical lacks `created_at`, `--apply` blocks pending owner decision. |

### Edits applied to spec (from AR#1)
- FR-006 / FR-013 amended: collision-diverted items carry `merged_from` + `collision=true`; skip-logic treats any `merged_from`-bearing item as done (A1).
- FR-008 amended: non-canonical PROFILE deleted only after ALL its children are resolved; otherwise retain + `partial` (A4).
- FR-011 amended: backup re-read and count-validated before `--apply` (A5).
- FR-002 amended: null/malformed `created_at` sorts last, never auto-canonical, flags + can block (A6).
- New FR-017 (A2): prefer low-traffic window; stale-client self-heals post-1395; non-blocking, documented.

### Gate — Adversarial Review #1
**PROCEED to plan.md.** No blocker introduced by the spec itself. The one hard gate (FR-002a / A3, canonical must match 1395) is correctly deferred to an owner/author coordination item and blocks only the destructive `--apply`, not the plan or the dry-run script.

---

## Clarifications

Self-answered where the spec + verified facts + code determine the answer; deferred where only the owner can decide.

**C1 — Do any of the 10 duplicates own configs/alerts/notifications that must be preserved?**
Answered (verified live): **No.** Each of the 10 owns only its `PROFILE` item (`query PK=USER#{id}` returned `SK=PROFILE` for all 10; no CONFIG#/ALERT#/NOTIF#/SESSION#/PREF#). Consolidation of the known group is data-preserving by construction. The reassignment path (FR-005/006) still ships and is tested against synthetic data-owning groups for prod/future safety.

**C2 — Which record is canonical?**
Answered: **earliest `created_at`** (the record created `2026-07-24T03:16:42Z`), secondary tie-break `user_id` ascending. Deterministic, immutable key, decoupled from owned-data movement (FR-002, plan §2). This matches Feature 1395's FR-004 survivor rule (earliest `created_at`, then `user_id` asc) — the two features crown the same runtime-computed winner. Per FR-018 the winner's `user_id` is not recorded here; the dry-run prints it for owner comparison.

**C3 — Reuse `merge_anonymous_data` or write a dedicated migration?**
Answered: **dedicated migration.** The helper only covers 3 entity types, has a collision path that can tombstone a source whose target write was skipped (data-loss risk), and no dry-run/backup/env guard. Borrow its `merged_from`/`merged_to` idempotency markers and reassign-then-mark ordering; do not call it (FR-016, plan §4).

**C4 — Where does the backup live?**
Answered: **local JSON file**, re-read and count-validated before `--apply`. No S3 bucket or other new AWS resource by default (project standing constraint). S3 destination is deferred to the owner (Open Q2).

**C5 — Is this run against prod?**
Answered: **preprod only** for this feature. Prod is out of scope for execution; the script hard-stops on a `prod`-named table unless `--allow-prod` is explicitly passed, and prod execution would be a separate owner-approved run after prod deploys.

### Open Questions (owner decision required — cannot self-answer)

- **Q1 (BLOCKS `--apply`, deploy-status confirmation):** ~~What deterministic record does 1395 reuse?~~ **RESOLVED for the RULE:** Feature 1395's spec exists (`specs/1395-oauth-account-integrity/`) and its **FR-004 confirms the identical survivor rule** — earliest `created_at`, then `user_id` ascending. 1397's FR-002 and 1395's FR-004 therefore crown the same runtime-computed winner (id not recorded — FR-018). No rule negotiation remains. The **only** remaining owner gate is confirming **1395 is DEPLOYED** (not merely specced) before any `--apply`, so new logins stop minting fresh `user_id`s during/after cleanup. **Owner must confirm 1395 deploy status before the destructive step.**
- **Q2 (backup destination):** Local JSON file is the default (no new AWS resource). Is a versioned S3 export desired instead/additionally? If yes, approve the bucket (or name an existing one) — otherwise local file stands.
- **Q3 (owned-config collision policy, only bites if prod data collides):** Default is keep-canonical, preserve-loser under a suffixed SK (FR-006) so nothing is destroyed. For the known preprod group this never triggers (no owned data). Confirm the default is acceptable, or specify overwrite/merge semantics, before any run against data-owning duplicates.
- **Q4 (destructive execution approval):** Explicit go/no-go for the `--apply` step itself, AFTER 1395 is deployed and Q1 is answered. This feature does not execute it.

---

## Adversarial Review #4 (Independent Refuter Resolution)

An independent refuter re-queried live `preprod-sentiment-users` and confirmed three findings. Each is resolved below with the exact locations changed. The live re-query was reproduced this session (`query by_cognito_sub` for `34f814f8-c0c1-707e-f0a6-27147065f706`, projected `user_id, created_at`, sorted ascending).

| # | Sev | Finding | Resolution | Locations changed |
|---|---|---|---|---|
| **NF-1** | CRITICAL | **Wrong canonical.** Artifacts named a survivor created `2026-07-24T06:40:14Z`. That record is NOT the earliest. The TRUE earliest-`created_at` in the live group was created **`2026-07-24T03:16:42.164498Z`** — 3.5 h older, a normal non-tombstoned Google USER. The wrong literal had propagated into 5 artifacts before an independent refuter re-queried live DynamoDB. | Initially the wrong example was replaced with the correct id; AR#5 then went further and BANNED literal winners entirely (FR-018): all `user_id` literals are scrubbed from every artifact, the winner is computed at runtime by `select_canonical`, and the dry-run prints it for owner comparison. The SELECTION RULE (earliest `created_at`, `user_id` asc tiebreak) was already correct and is UNCHANGED. Confirmed the rule matches Feature 1395 FR-004 — both crown the same runtime-computed record. | spec.md: verified-facts table (Earliest row), FR-002, SC-1, C2, AR#1/A3, new FR-018. plan.md: §2 decision, §2 coordination paragraph, AR#2/D3. tasks.md: AR#3 risk table, T026, ship-gate item 2. script: `CANONICAL_RULE` comment block (no id literal). |
| **NF-2** | LOW | **Env-guard drift.** US4/FR-014 said hard-stop "if the table name CONTAINS `prod`," but `_env_guard` only stopped when the FIRST hyphen-segment == `prod`. `sentiment-prod-users` and `production-…` would bypass the guard. | Reconciled spec and code to ONE rule: refuse if ANY hyphen-segment == `prod`, OR the name carries a `prod`/`production` token that is NOT part of `preprod`. `preprod` is never false-tripped; real prod names are caught. Extracted `_resolves_to_prod()` helper; verified against 9 cases (incl. `preprod-sentiment-users`→allow, `sentiment-prod-users`/`production-…`→block). | spec.md: US4 acceptance bullet, FR-014. script: new `_resolves_to_prod()` + `_env_guard()` rewrite. |
| **NF-3** | LOW | **Stale claim.** Artifacts repeatedly asserted "Feature 1395's spec does not yet exist." It DOES exist (`specs/1395-oauth-account-integrity/`) and its FR-004 confirms the earliest-`created_at` rule. | Removed the "does not exist" claims. Updated Q1: the RULE is confirmed aligned via 1395 FR-004; the only residual owner gate is confirming **1395 is DEPLOYED** before any `--apply`. FR-002a, plan §2, tasks T026, and the script's `coordination_gate()`/`COORDINATION_CONFIRMED` comments now frame the gate as deploy-status, not rule negotiation. | spec.md: FR-002a, AR#1/A3, Open Q1. plan.md: §2 coordination paragraph + trailing assumption note. tasks.md: AR#3 risk table, T026, ship-gate item 2. script: `coordination_gate()` docstring + gate comments. |

**Gate after AR#4 (honest, unchanged in spirit):**
- **Non-destructive phases (Phase 0–5: script skeleton + full moto test suite) are READY** now that the canonical example, env guard, and 1395 references are corrected. The script remains NON-EXECUTING — every destructive function (`reassign_item`, `discard_sessions`, `delete_noncanonical_profile`, `apply`, `rollback`, `verify`) still raises `NotImplementedError` by design. This review did NOT implement the migration.
- **Live `--apply` (T026/T027) remains BLOCKED** on: (1) explicit owner approval (Q4), and (2) Feature 1395 confirmed **DEPLOYED** (Q1 — rule alignment already settled via 1395 FR-004). `COORDINATION_CONFIRMED` stays `False`; `--apply` is refused regardless of flags until an owner flips it after confirming 1395 is live.

---

## Adversarial Review #5 (Finalization — destructive-safety attack round)

Fresh attack pass before implementation of the skeleton + test suite. Vectors: destructive-migration safety, partial failure, concurrent login mid-run, backup integrity, `--apply` gate bypass, literal-id contamination.

| # | Attack | Finding | Severity | Resolution |
|---|---|---|---|---|
| A7 | **Bypass the `--apply` gate by importing the module** and calling `apply()` / `reassign_item()` directly from a REPL, skipping argparse entirely. | The CLI gates (flags, env guard) lived in `main()`; a direct call would reach destructive code with zero gates. | HIGH | RESOLVED: gates MUST be enforced INSIDE `apply()` itself (coordination gate, validated backup, acknowledgement token, env guard, FR-019 canonical assertion) — `main()` merely collects flags. A direct `apply()` call with unsatisfied gates returns `blocked` with zero writes. Test T034 calls `apply()` directly and asserts no destructive write. Tasks T013 amended. |
| A8 | **Bypass by editing `COORDINATION_CONFIRMED = True`** in a working copy and running. | An operator with repo write + AWS creds can always self-authorize; no script can fully prevent its own modification. | MEDIUM | ACCEPTED-WITH-MITIGATION: the constant flip is designed to be a reviewed, GPG-signed commit (documented in the script comment); the remaining rails (dry-run printout comparison by the owner, `--i-understand-destructive`, validated backup, audit log with backup hash) still apply and leave evidence. Defense is layered gates + audit trail, not tamper-proofing. Non-blocking. |
| A9 | **Backup passes count-validation but contains the wrong items** (stale file reused via `--backup-file`, or a serialization bug exporting the right number of wrong records). | FR-011 (pre-AR#5) validated COUNT only. Rollback from a wrong-but-right-sized backup would be silent corruption. | HIGH | RESOLVED: FR-011 amended — validation asserts exact (PK, SK) key-set equality against the fresh enumeration, and a SHA-256 of the backup is recorded in the audit log. A `--backup-file` whose key set does not match the current group is refused. |
| A10 | **Concurrent Google login mints an 11th duplicate between backup and apply.** | The new record is not in the backup; deleting it would be an unbacked-up destructive write; ignoring it silently leaves the group unconsolidated with no signal. | HIGH | RESOLVED: new FR-020 (frozen delete set): re-enumerate immediately before the destructive phase; anything not in the validated backup is untouched and reported as a straggler; `--verify` fails exactly-one and names it. Fail-closed: no item is ever deleted that is not in a validated backup. Test T033. |
| A11 | **A selection/bookkeeping bug puts the canonical itself into a destructive set** — deleting the exact record 1395's live code resolves to. | Nothing previously ASSERTED the canonical's exclusion; it was implied by construction only. | CRITICAL | RESOLVED: new FR-019 — pre-destructive hard assertion that the canonical id is absent from every delete/discard/reassign-source list; HARD-ABORT with zero writes otherwise (EC-7). Test T032 injects a poisoned set and asserts abort. |
| A12 | **Literal-id contamination recurs** (the NF-1 near-miss class): a future edit re-embeds a live `user_id` as "the" canonical and drifts from live data again. | The near-miss propagated a wrong id into 5 artifacts before a refuter caught it. Only convention prevented recurrence. | CRITICAL (historical) | RESOLVED: new FR-018 bans live-data ids as literals in ALL artifacts and executable logic; this round scrubbed every remaining occurrence (verified-facts table, FR-002, SC-1, C2, Q1, NF-1, plan §2/D3, tasks T026/AR#3, script comment). Enforcement is mechanical: T028's static scan fails the suite if any UUID-shaped literal appears in the script; dry-run prints the computed canonical + full reassignment plan for owner comparison at execution time. |
| A13 | **Interrupted mid-apply** (SIGKILL between reassign and delete, or mid-delete of the 9 PROFILEs). | Already covered: reassign-then-delete ordering (FR-005), `merged_from` markers (FR-013), PROFILE deleted only after all children resolved (FR-008/A4), run marked `partial`, resumable; rollback restores from backup (FR-015). Re-verified against the new FR-019/FR-020 — no interaction: a resumed run recomputes the group, re-asserts the canonical exclusion, and only touches backed-up items. | — | No change needed. Confirmed covered. |
| A14 | **Double-reassignment of the same item** (re-run, or retry after throttling). | Already covered: idempotency invariant (FR-013 + A1) — any item carrying `merged_from` (including collision-diverted) is skipped; second full run is `already-consolidated` with zero writes. Tie on `created_at` also re-verified: FR-002's `user_id` asc tie-break is deterministic and now has a dedicated test (T029). | — | No change needed. Test coverage added (T029). |

### Edits applied to spec (from AR#5)
- New FR-018 (no literal live-data ids; dry-run prints computed canonical + full plan; static-scan enforcement) — A12.
- New FR-019 (canonical-never-destroyed hard assertion) + EC-7 — A11.
- New FR-020 (frozen delete set, fail-closed on stragglers) + EC-8 — A10.
- FR-011 amended (key-set equality + SHA-256, not count-only) — A9.
- FR-017 promoted from AR#1 edit-note into the FR list proper (was previously only described in the AR#1 edits).
- Gate placement: gates enforced inside `apply()`, not only in `main()` — A7 (carried into plan step 6 and task T013).

### Gate — Adversarial Review #5
**PROCEED to implementation planning (plan/tasks finalization).** Two CRITICALs (A11, A12) and three HIGHs (A7, A9, A10) self-resolved via FR-018/019/020 and FR-011 amendment. A8 accepted with layered mitigation. The destructive `--apply` remains owner-gated — unchanged and correct.
