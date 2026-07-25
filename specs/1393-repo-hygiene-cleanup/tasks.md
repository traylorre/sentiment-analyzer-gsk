# Tasks: Repo Hygiene — Reconcile Dangling Worktrees & Branches

**Feature**: `1393-repo-hygiene-cleanup` | **Date**: 2026-07-24
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> Hand-authored (speckit skills are branch-creating/interactive; planning-only). Structure follows
> `.specify/templates/tasks-template.md`. `[P]` = parallelizable (independent, no ordering dep).
> EVERY destructive task (remove/delete/apply) is OWNER-GATED (FR-015) — do not execute without
> approval. All git ops run from the main repo root (`/home/zeebo/projects/sentiment-analyzer-gsk`).

## Conventions

- IDs: `T0xx`. Thread A (four agent worktrees) and Thread B (sa-cfdel/1378) are largely independent.
- Every task lists the FR(s) it satisfies and an acceptance check.
- Re-run containment verification at EXECUTION time (FR-001/006) — never trust the 2026-07-24
  snapshot alone (AR2-F2).

---

## Phase 0 — Re-verify (non-destructive; do first)

### T001 [P] — Re-verify containment for all six HEADs (patch-id, not `log A..B`)
- **Do**: `git fetch origin main`; then for `c2ff2f4 9dfff76 d3f20b7 dc3076a ac2bf32`:
  `git cherry origin/main <HEAD>` (expect leading `-` = patch-equiv upstream) and, for `c2ff2f4`,
  `git branch -r --contains c2ff2f4 | grep origin/main` (literal ancestor). Record each output as
  deletion evidence. Do NOT use `git log origin/main..HEAD` as the containment test (squash-merge
  false positives, AR1-F1).
- **FRs**: FR-001, FR-006
- **Accept**: all five show `-` under `git cherry` (or `c2ff2f4` shows as ancestor); outputs saved.
  If ANY shows `+` (unmerged) → STOP, that item is BLOCKED (see AR#3).

### T002 [P] — Snapshot working-tree state of all six worktrees
- **Do**: `git -C <wt> status --porcelain` for each. Confirm the only unmerged/untracked WORK is
  `agent-a7bc7836fc7e73b90/specs/1380-oauth-avatar-picture/` (and sa-cfdel's `.venv`, which is
  rebuildable, not work).
- **FRs**: FR-001 (evidence), FR-002 (identifies the preserve target)
- **Accept**: only A1 has real untracked work (1380 specs); A2/A3/A4 clean; B1 only `.venv`.

### T003 [P] — Confirm remote-branch absence (orphan-prevention)
- **Do**: `git ls-remote --heads origin worktree-agent-a7bc7836fc7e73b90 1381-oauth-session-persistence
  1382-apigw-cors-patch 1383-oauth-env-durability 1378b-cloudfront-waf-moved-block`.
- **FRs**: FR-005, FR-011 (CLAUDE.md Orphan Prevention)
- **Accept**: empty output → NO `git push origin --delete` is needed for any branch. If any name
  appears, that branch's remote deletion becomes owner-gated + PR-verified per CLAUDE.md 143.

---

## Phase 1 — Thread A: preserve, then clean the four agent worktrees

### T004 — Preserve the untracked 1380 spec suite (BLOCKING precondition for T005) [owner-gated]
- **Do**: Copy `.claude/worktrees/agent-a7bc7836fc7e73b90/specs/1380-oauth-avatar-picture/*.md`
  into `specs/1380-oauth-avatar-picture/` in the main repo; `git add` + GPG-signed commit — OR
  obtain an explicit owner disposition that the 1380 specs are disposable (record it). This MUST
  complete before T005 removes the a7bc worktree.
- **FRs**: FR-002 (and Clarification C5, owner O2)
- **Accept**: `specs/1380-oauth-avatar-picture/{spec,plan,tasks}.md` exist & are committed in the
  main repo, OR a written owner "discard" disposition is recorded. (AR1-F2 — the one place work
  could be lost.)

### T005 — Remove the four agent worktrees [owner-gated]
- **Depends on**: T001, T002, T003, **T004** (A1 only)
- **Do**: `git worktree remove .claude/worktrees/agent-a8e8e02a5cda3ab4c` (clean → no `--force`);
  same for `agent-a9be816c9de30681b`, `agent-af6490ffbc33d1c2c`. For
  `agent-a7bc7836fc7e73b90`, only AFTER T004: `git worktree remove --force` (— `--force` permitted
  because the untracked 1380 specs are now preserved, AR2-F1).
- **FRs**: FR-003
- **Accept**: `git worktree list` shows no `.claude/worktrees/agent-*` entries.
- **Guard (AR2-F1)**: `--force` on A1 is allowed ONLY after T004 confirms preservation. Never
  `--force` a7bc before T004.

### T006 — Delete the four Thread-A local branches [owner-gated]
- **Depends on**: T005 (a branch checked out in a worktree can't be deleted; remove worktree first —
  AR2-F4)
- **Do**: `git branch -d worktree-agent-a7bc7836fc7e73b90` (literal ancestor → `-d` succeeds,
  AR1-F6). For the squash-merged branches, re-confirm T001's `git cherry -` immediately, then
  `git branch -D 1382-apigw-cors-patch 1381-oauth-session-persistence 1383-oauth-env-durability`
  (`-D` needed because squash-merge defeats `-d`'s merged-check; permitted only with fresh evidence,
  AR2-F2).
- **FRs**: FR-004
- **Accept**: `git branch` lists none of the four; `-D` was used only with a fresh `git cherry -`
  result recorded.

---

## Phase 2 — Thread B: sa-cfdel abandon + Phase-2 decision

### T007 — Abandon the sa-cfdel worktree + 1378b branch [owner-gated]
- **Depends on**: T001 (ac2bf32 containment), T003 (remote absence)
- **Do**: Re-confirm `git cherry origin/main ac2bf32` → `-` (merged #911). From the main repo root
  (NOT from inside sa-cfdel, AR2-F5): `git worktree remove --force /home/zeebo/projects/sa-cfdel`
  (`--force` discards the untracked `.venv`, which is rebuildable — FR-010, AR1-F7). Then
  `git branch -D 1378b-cloudfront-waf-moved-block`.
- **FRs**: FR-006, FR-008, FR-010
- **Accept**: sa-cfdel gone from `git worktree list`; branch gone from `git branch`; no work lost
  (only `.venv` discarded).

### T008 — Prune stale remote-tracking refs [owner-gated]
- **Depends on**: T006, T007
- **Do**: `git remote prune origin` (and/or `git branch -dr origin/1378b-cloudfront-waf-moved-block`)
  to drop the cached tracking refs that make `git branch -vv` show phantom upstreams.
- **FRs**: FR-012
- **Accept**: `git branch -vv` shows no `[origin/…]` label for any reconciled branch.

### T009 — Report Phase-2 (1378 teardown) state + route the owner decision [owner-gated decision]
- **Do**: State from primary evidence: `origin/main:preprod.tfvars` `enable_cloudfront_waf = true`;
  `git log origin/main -S "enable_cloudfront_waf = false" -- infrastructure/terraform/` = empty;
  `variables.tf` documents "Phase 2: enable_cloudfront_waf=false (delete the now-orphaned ACL)."
  Conclude: a disassociated-but-undeleted CloudFront WebACL likely still exists. Present the two
  owner options (FINISH vs ACCEPT, O1). Update the cleanup-board card from "not reconciled" to the
  chosen decision. This is a SEPARATE item from T007 — deleting the branch does NOT close it (AR1-F5).
- **FRs**: FR-007, FR-009, FR-015
- **Accept**: report written with the three citations; board card carries an explicit FINISH/ACCEPT
  decision or a routed owner question O1.

### T010 — (CONDITIONAL) Complete Phase-2 teardown — ONLY if owner approves FINISH [owner-gated]
- **Depends on**: T009 (owner picks FINISH)
- **Do**: On a fresh short-lived branch (NOT sa-cfdel), make TWO edits in ONE GPG-signed commit
  (FR-016 — do not split, and do NOT apply the line-969 edit alone while `enable_cloudfront_waf` is
  still `true`, which would re-associate the CloudFront WAF):
  1. `infrastructure/terraform/preprod.tfvars:72` → `enable_cloudfront_waf = false`.
  2. `infrastructure/terraform/main.tf:969` guard → `var.enable_cloudfront_waf ? module.waf_cloudfront[0].web_acl_arn : ""` (was `var.enable_waf ?`), decoupling the toggle so Feature 1392's `enable_waf=true` can plan (otherwise the combined end-state indexes an empty `module.waf_cloudfront[0]` → terraform error, AR1-F8).

  Run `terraform plan -var-file=preprod.tfvars` and CONFIRM destroys are confined to
  `module.waf_cloudfront[0]` ONLY — `aws_wafv2_web_acl.main` + its
  `aws_cloudwatch_metric_alarm.waf_blocked[0]` (two resources; rules are inline; association is
  `count=0`) — the `moved` block a no-op, and NO change to `module.waf` (1392's API-GW WAF) or
  `module.cloudfront_sse` (FR-017). checkov MUST pass with venv ACTIVE (hcl2 gotcha on the `.tf`
  edit). Apply via the normal CI/PR path (respect state-lock; CI owns applies). **This teardown MUST
  land BEFORE 1392's `enable_waf` flip.**
- **FRs**: FR-013 (append-only: new commit, no rewrite), FR-014 (destroy-only, no new resource),
  FR-016 (decouple line 969), FR-017 (plan confined to `module.waf_cloudfront[0]`)
- **Accept**: plan shows destroys only within `module.waf_cloudfront[0]` (WebACL + alarm), `moved`
  no-op, nothing outside; apply succeeds; AWS shows the orphaned CloudFront ACL gone; no new resource
  created; `main.tf:969` now reads `var.enable_cloudfront_waf`. If plan shows anything outside
  `module.waf_cloudfront[0]` (or errors on an empty index) → BLOCK, route to owner.

---

## Phase 3 — Final verification

### T011 [P] — Assert clean end-state
- **Do**: `git worktree list` (only real checkouts); `git branch` (no reconciled branches);
  `git ls-remote --heads origin` (no orphaned reconciled branch); `git branch -vv` (no phantom
  upstreams); confirm `specs/1380-oauth-avatar-picture/` preserved (or dispositioned).
- **FRs**: FR-011, FR-012; **SCs**: SC-002, SC-003, SC-004, SC-006
- **Accept**: all five checks hold.

### T012 [P] — Assert no history rewrite / no new AWS resource
- **Do**: Confirm `main` history unchanged (no force-push, no rebase of merged commits); if T010
  ran, confirm the only AWS delta is the WebACL deletion.
- **FRs**: FR-013, FR-014; **SCs**: SC-007
- **Accept**: append-only held; zero new AWS resources.

---

## Requirement → Task coverage

| FR | Task(s) |
|---|---|
| FR-001 | T001, T002, T006 (re-verify before `-D`) |
| FR-002 | T004 |
| FR-003 | T005 |
| FR-004 | T006 |
| FR-005 | T003 |
| FR-006 | T001, T007 |
| FR-007 | T009 |
| FR-008 | T007 |
| FR-009 | T009 |
| FR-010 | T007 |
| FR-011 | T005, T007, T011 |
| FR-012 | T008, T011 |
| FR-013 | T010, T012 |
| FR-014 | T010, T012 |
| FR-015 | all destructive tasks (T004–T010) |
| FR-016 | T010 (line-969 decouple with the flip) |
| FR-017 | T010 (plan confined to `module.waf_cloudfront[0]`) |
| SC-001..007 | T001–T003 (evidence), T004/T009 (preserve/report), T011/T012 (assert) |

Every FR and SC maps to ≥1 task. No orphan requirements.

## Parallelization

- Phase 0 (T001, T002, T003) fully `[P]` — read-only verification.
- Thread A (T004→T005→T006) and Thread B (T007→T008→T009→T010) are independent after Phase 0.
- T011, T012 are `[P]` final assertions after all removals.
- T004 is a HARD predecessor of T005's a7bc removal (preserve-before-remove).

---

## Cross-Artifact Analysis (`/speckit.analyze` equivalent)

Non-destructive consistency scan across spec.md, plan.md, tasks.md.

### Coverage
- **Requirements → tasks**: all 17 FRs (incl. FR-016 line-969 decouple, FR-017 plan confinement) and
  all 7 SCs map to ≥1 task (table above). No orphans.
- **Tasks → requirements**: every task cites its FR(s). No task without an anchor.
- **User stories → tasks**: US1 (verify-before-remove) → T001–T004; US2 (four agent worktrees) →
  T004–T006; US3 (1378 decision) → T007–T010. All stories covered.

### Consistency
- **Terminology**: "patch-id / `git cherry`", "Phase 1/Phase 2", "abandon/finish", "owner-gated",
  worktree paths, and branch names used identically across all three artifacts.
- **Evidence anchors**: `git cherry` `-` lines, `origin/main:preprod.tfvars:72`, #909/#911/#938/
  #940/#941/#942, `main.tf:1029-1030` — consistent spec↔plan↔tasks.
- **Decisions**: Clarifications C1–C5 and owner O1/O2 reflected in tasks (T001 patch-id per C1; T002
  identifies the single unmerged item per C2; T003 remote-absence per C3; T009 Phase-2-separate per
  C4; T004 preserve/disposition per C5/O2; T009 Phase-2 finish/accept per O1).

### Gaps / risks surfaced
- **G1 (owner)**: O1 (Phase-2 FINISH vs ACCEPT) is the real content of the "not reconciled" card;
  T009 routes it, T010 is conditional on it. Non-blocking for the branch cleanup.
- **G2 (owner)**: O2 (commit vs discard the 1380 specs); T004 defaults to commit (recommended).
- **G3 (watch)**: `-D` on squash-merged branches (T006) requires FRESH `git cherry` evidence — a
  stale snapshot could hide a late amend. Re-verify is baked into T006/AR2-F2.

### Duplication / dead scope
- None. Out-of-scope items (implement 1380; full WAF architecture; other stale `A-*`…`J-*`
  branches) are not tasked.

**Analyze result: CONSISTENT. 0 blocking gaps. 2 owner decisions (O1, O2), 1 watch item (G3).**

---

## Adversarial Review #3

**Stance**: Final gate before execution. Identify the highest-risk task, the most likely rework,
and decide READY vs BLOCKED.

### Highest-risk task: **T005 (remove worktrees) coupled with T004 (preserve 1380 specs) and T006 `-D`**

The single irreversible-loss path in this entire feature is: `git worktree remove --force` on
`agent-a7bc7836fc7e73b90` BEFORE the untracked `specs/1380-oauth-avatar-picture/` suite is
preserved. That suite is the ONLY copy of a full feature spec (not on origin/main). Once
`--force`-removed, it is gone — no reflog, no recovery (untracked files aren't in git). Secondary
risk: `git branch -D` on a squash-merged branch trusting a STALE `git cherry` snapshot.

### Most likely rework
1. **Forgetting T004 before T005's a7bc `--force`** — highest-probability catastrophic error.
   Mitigation: T004 is a HARD predecessor; T005's guard forbids `--force` on a7bc until T004
   confirms preservation; git's own no-`--force` refusal (used for A2–A4) is the backstop, and A1
   must not bypass it until preservation is done (AR2-F1). Reviewer MUST verify T004 completed
   before any a7bc removal.
2. **`-D` on stale evidence (T006)** — re-run `git cherry` immediately before `-D` (AR2-F2). If it
   shows `+`, STOP.
3. **Phase-2 plan showing unexpected changes — or erroring outright (T010)** — the concrete danger
   is the `main.tf:969` coupling (AR1-F8): if the line-969 guard is not decoupled in the same commit
   as the `enable_cloudfront_waf=false` flip, the combined end-state with 1392's `enable_waf=true`
   indexes an empty `module.waf_cloudfront[0]` and the plan ERRORS (not just "extra changes"). T010
   folds the FR-016 guard fix into the same commit and BLOCKS on any destroy outside
   `module.waf_cloudfront[0]` (FR-017). A secondary trap: applying the line-969 edit alone while
   `enable_cloudfront_waf` is still `true` would re-associate the CloudFront WAF (undo Phase 1) — T010
   forbids splitting the two edits.

### Branch-vs-teardown masquerade (explicit)

Deleting `1378b-cloudfront-waf-moved-block` (T007) MUST NOT be mistaken for finishing the teardown.
The branch's only commit (the `moved` block) is already merged as #911; abandoning it changes NO AWS
state. The teardown — deleting the orphaned CloudFront WebACL — is T009 (decision) + T010 (execute),
a wholly separate task-set gated on its own owner approval (O1). Keeping them separate is why T007
and T009/T010 are distinct tasks in distinct threads: a board card that reads "not reconciled" is
closed by the ACL disposition, never by a branch deletion (AR1-F5).

### Security / safety re-confirmation
- **Data loss**: neutralized by T004 blocking-preserve + the reserve-`--force`-until-preserved rule.
- **Orphaned branches**: impossible for the reconciled set — live remote has none; no `push
  --delete` is run (T003, FR-005); stale refs pruned (T008).
- **History integrity**: append-only — no rebase, no force-push; only worktree/branch cleanup + (if
  approved) a new-commit tfvars flip (FR-013).
- **AWS**: no new resources; Phase-2 (optional) is a DESTROY of an already-orphaned ACL (FR-014).

### Gate
- CRITICAL: 0 (AR1-F2 loss path gated by T004→T005 ordering; AR1-F8 coupling gated by T010's FR-016 in-commit decouple)
- HIGH: 0 (AR2-F3 multi-destroy/coupling gated by FR-017 plan confinement)
- Blocking gaps: 0
- Owner decisions outstanding: 3 (O1 Phase-2 finish/accept; O2 1380-spec commit/discard; O3 confirm
  the CloudFront ACL is actually still present/billing) — none block the safe branch-cleanup portion.

**AR#3 GATE: READY for execution — with three hard conditions:** (1) T004 (preserve 1380 specs or
record a discard disposition) MUST complete before any `--force` removal of the a7bc worktree; (2)
`git cherry` MUST be re-run immediately before every `git branch -D`; (3) T010's Phase-2 commit MUST
bundle the `enable_cloudfront_waf=false` flip WITH the `main.tf:969` decouple (FR-016) and land
BEFORE Feature 1392's `enable_waf` flip, with the plan confined to `module.waf_cloudfront[0]`
(FR-017). T010 remains conditional on owner approval of Phase-2 FINISH (O1).
