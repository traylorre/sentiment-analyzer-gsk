# Feature Specification: Repo Hygiene — Reconcile Dangling Worktrees & Branches

**Feature Branch**: `1393-repo-hygiene-cleanup`
**Created**: 2026-07-24
**Status**: Draft
**Input**: User description: "Resolve two dangling-work threads so nothing is orphaned: (A) four uncleaned agent worktrees under `.claude/worktrees/agent-*` left over from the 1380–1383 battleplan, and (B) the orphaned CloudFront/WAF teardown thread — a separate worktree at `/home/zeebo/projects/sa-cfdel` on branch `1378b-cloudfront-waf-moved-block`. For each worktree+branch, produce a documented finish-vs-abandon decision backed by git evidence, verify no unmerged work is lost, and ensure no orphaned branches remain per CLAUDE.md's Orphan Branch Prevention rule."

> Authoring note: The `/speckit.*` skills in this repo run interactive, branch-creating
> workflows. This feature was authored by hand following `.specify/templates/*` structure. This is
> a planning-only artifact — it recommends removals/deletions with evidence; it performs none of
> them. Every destructive step is owner-gated (see FR-015).

## Context & Problem

Two independent threads of dangling git state exist in the working environment. Neither is
tracked by a spec, and both risk either (a) permanently losing unmerged work if removed carelessly,
or (b) leaving orphaned branches on the remote if removed incorrectly (the exact failure the
CLAUDE.md "Orphan Branch Prevention (143)" rule exists to prevent).

### Thread A — four leftover agent worktrees (from the 1380–1383 battleplan)

`git worktree list` shows four worktrees under `.claude/worktrees/agent-*`, each on its own local
branch:

| Worktree dir | Local branch | HEAD | Related merged PR |
|---|---|---|---|
| `.claude/worktrees/agent-a7bc7836fc7e73b90` | `worktree-agent-a7bc7836fc7e73b90` | `c2ff2f4` | #938 (M1 WI-6 OAuth sign-in fix) |
| `.claude/worktrees/agent-a8e8e02a5cda3ab4c` | `1382-apigw-cors-patch` | `9dfff76` | #940 (1382 CORS) |
| `.claude/worktrees/agent-a9be816c9de30681b` | `1381-oauth-session-persistence` | `d3f20b7` | #942 (1381 session) |
| `.claude/worktrees/agent-af6490ffbc33d1c2c` | `1383-oauth-env-durability` | `dc3076a` | #941 (1383 env durability) |

Features 1381/1382/1383 are already merged to `main` via squash-merge (PRs #942/#940/#941). The
squash created NEW commit SHAs on `main`, so a naive `git log origin/main..HEAD` shows the branch
commits as "unique" even though their content is upstream. Patch-id comparison (`git cherry`) is
the correct containment test here.

### Thread B — the orphaned CloudFront/WAF teardown (1378)

A separate worktree at `/home/zeebo/projects/sa-cfdel` sits on branch
`1378b-cloudfront-waf-moved-block` (HEAD `ac2bf32` "fix(1378): add moved block for waf_cloudfront
count migration"). The cleanup board carries a card: "CloudFront WAF teardown (1378) not
reconciled." The 1378 teardown is a deliberate **two-phase** operation (documented in
`variables.tf` on main):

- **Phase 1** — `enable_waf=false` (disassociate the ACL from CloudFront) + `enable_cloudfront_waf=true`
  (keep the ACL). A CloudFront WAF cannot be deleted while still associated (AWS returns
  `WAFAssociatedItemException`), so disassociation must land and finish a global redeploy first.
- **Phase 2** — `enable_cloudfront_waf=false` (delete the now-orphaned, disassociated ACL).

The open question the card raises: did Phase 2 ship, or is a disassociated-but-undeleted WebACL
still sitting in the account, and is the `sa-cfdel` branch holding unmerged Phase-2 work?

### Thread B coupling with Feature 1392 (CRITICAL — new in this re-scope)

Phase 2 (`enable_cloudfront_waf=false`) does NOT run in isolation. It is executed in the same
battleplan as Feature 1392, which ENABLES the regional API-Gateway WAF (`enable_waf=false→true`).
Both toggles live in the SAME file (`preprod.tfvars`) but govern DIFFERENT resources at DIFFERENT
scopes:

| Toggle | tfvars line | Module | Scope | count line | Feature |
|---|---|---|---|---|---|
| `enable_waf` | `preprod.tfvars:59` | `module.waf` | REGIONAL (API GW) | `main.tf:925` | 1392 (create) |
| `enable_cloudfront_waf` | `preprod.tfvars:72` | `module.waf_cloudfront` | CLOUDFRONT | `main.tf:996` | 1393 (delete) |

They are structurally independent EXCEPT for one line that couples them:

```hcl
# main.tf:969  — waf_web_acl_arn passed to module.cloudfront_sse
waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""
```

This guard is on **`enable_waf`** but indexes **`module.waf_cloudfront[0]`** (governed by
`enable_cloudfront_waf`). At the battleplan's target end-state (`enable_waf=true` +
`enable_cloudfront_waf=false`) the guard's true-branch indexes a `count=0` module → **terraform
"Invalid index / empty tuple" error.** The teardown's `enable_cloudfront_waf=false` flip therefore
cannot coexist with 1392's `enable_waf=true` while line 969 reads `var.enable_waf`. This teardown
MUST also change the line-969 guard to `var.enable_cloudfront_waf` (resource-neutral: yields `""`
when the CloudFront WAF is off, exactly what the distribution already receives). See FR-016 and
Adversarial Review #1 AR1-F8.

### Confirmed git evidence (gathered 2026-07-24, after `git fetch origin main`)

- **origin/main HEAD**: `46a4975` "fix(1381): persist OAuth session across reload … (#942)".
- **Thread-A containment (`git cherry origin/main <HEAD>`, patch-id)**:
  - `c2ff2f4` — `git branch -r --contains c2ff2f4` lists `origin/main` (literal ancestor; it is the
    merge base commit of #938). `git log origin/main..HEAD` = **empty** (0 unique commits).
  - `9dfff76` — `git cherry` → `- 9dfff76…` (leading `-` = patch-equivalent already upstream, #940).
  - `d3f20b7` — `git cherry` → `- d3f20b7…` (patch-equivalent upstream, #942).
  - `dc3076a` — `git cherry` → `- dc3076a…` (patch-equivalent upstream, #941).
- **Thread-B containment**: `ac2bf32` — `git cherry origin/main ac2bf32` → `- ac2bf32…`
  (patch-equivalent upstream). Confirmed present on main as **#911** (`78f1037` "fix(1378): add
  moved block for waf_cloudfront count migration (#911)"). The `moved { from =
  module.waf_cloudfront to = module.waf_cloudfront[0] }` block IS on `origin/main:main.tf:1029-1030`.
- **Phase-2 status on main**: `origin/main:preprod.tfvars:72` = `enable_cloudfront_waf = true`.
  `git log origin/main -S "enable_cloudfront_waf = false" -- infrastructure/terraform/` returns
  **no commits**. Phase 2 (the flip to `false` that deletes the orphaned ACL) has **NOT** shipped —
  and the `sa-cfdel` branch does NOT contain it either (its only commit is the merged moved block).
- **Working-tree state per worktree** (`git -C <wt> status --porcelain`):
  - `agent-a7bc7836fc7e73b90`: **untracked** `specs/1380-oauth-avatar-picture/` (plan.md, spec.md,
    tasks.md — a full hand-authored spec suite, ~55 KB, NOT present on origin/main). **This is the
    only unmerged work in any of the six worktrees.**
  - `agent-a8e8e02a5cda3ab4c`, `agent-a9be816c9de30681b`, `agent-af6490ffbc33d1c2c`: clean.
  - `sa-cfdel`: only untracked `.venv` (a virtualenv, not work; ignorable).
- **Remote branch existence** (`git ls-remote --heads origin <name>`, live query): ALL five
  candidate branch names (`worktree-agent-a7bc7836fc7e73b90`, `1381-oauth-session-persistence`,
  `1382-apigw-cors-patch`, `1383-oauth-env-durability`, `1378b-cloudfront-waf-moved-block`) are
  **ABSENT on origin**. `git branch -vv` shows stale upstream labels (e.g.
  `[origin/1378b-cloudfront-waf-moved-block]`) but those are **cached local remote-tracking refs**;
  the live remote has none of them. **No `git push origin --delete` is required for any branch** —
  removing these worktrees strands nothing on the remote.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — No dangling worktree/branch is removed until its contents are proven merged (Priority: P1)

As the repo owner, before any worktree is removed or any branch deleted, I need documented proof
(patch-id containment + working-tree cleanliness) that the removal loses no unmerged work, so a
cleanup can never destroy the only copy of something.

**Why this priority**: This is the whole point of the feature. The risk being managed is
irreversible data loss (deleting a branch whose work is not upstream) and orphaned remote branches.

**Independent Test**: For each of the six worktrees, produce the `git cherry` / `git branch -r
--contains` result and the `git status --porcelain` output, and show a per-item finish/abandon
decision that cites that evidence.

**Acceptance Scenarios**:

1. **Given** a branch whose HEAD is patch-equivalent to `origin/main` and whose worktree is clean,
   **When** the reconciliation runs, **Then** it is classified ABANDON-safe with the `git cherry`
   `-` line recorded as evidence.
2. **Given** a worktree with untracked work not present on `origin/main` (the 1380 specs),
   **When** the reconciliation runs, **Then** that work is PRESERVED (copied out) before the
   worktree is removed, and the removal is blocked until preservation is confirmed.
3. **Given** a branch, **When** its remote existence is checked, **Then** the live `ls-remote`
   result determines whether any `git push origin --delete` is needed (none are, per evidence).

---

### User Story 2 — The four battleplan agent worktrees are cleaned up (Priority: P1)

As the repo owner, I want the four `.claude/worktrees/agent-*` worktrees and their local branches
removed so `git worktree list` no longer shows stale battleplan scaffolding, without losing the
untracked 1380 spec suite.

**Why this priority**: These four are confirmed fully-merged (1381/1382/1383 shipped; the
`worktree-agent-a7bc…` HEAD is a literal ancestor of main). They are pure scaffolding debt.

**Independent Test**: After the tasks run, `git worktree list` shows only the two real checkouts;
`git branch` shows none of the four local branches; `specs/1380-oauth-avatar-picture/` is preserved
in the main repo (committed or explicitly dispositioned).

**Acceptance Scenarios**:

1. **Given** the 1380 specs are preserved, **When** `agent-a7bc7836fc7e73b90` is removed and
   `worktree-agent-a7bc7836fc7e73b90` deleted, **Then** no untracked work is lost.
2. **Given** `1381/1382/1383` branches are patch-equivalent to main, **When** their worktrees are
   removed and local branches deleted, **Then** `git worktree list` and `git branch` no longer
   list them, and no remote branch deletion is attempted (none exist).

---

### User Story 3 — The 1378 CloudFront/WAF thread gets a documented finish-vs-abandon decision (Priority: P2)

As the repo owner, I need a clear, evidence-backed recommendation on the `sa-cfdel` worktree/branch
AND on the separate question of whether Phase-2 teardown should be completed, so the cleanup board
card can be closed with a real decision rather than left ambiguous.

**Why this priority**: The branch itself is trivially abandon-safe (its work is merged), but the
*teardown thread* it belongs to is genuinely unfinished (Phase 2 never shipped). Conflating "the
branch" with "the teardown" is the trap; this story separates them.

**Independent Test**: The plan states (a) ABANDON for the `sa-cfdel` worktree+branch with the
`git cherry -` evidence, and (b) a separate, owner-gated recommendation on Phase 2 with the
`preprod.tfvars:72 = true` + "no flip commit on main" evidence.

**Acceptance Scenarios**:

1. **Given** `ac2bf32` is patch-equivalent to `origin/main` (#911) and the worktree holds no
   unmerged work, **When** the decision is recorded, **Then** the `sa-cfdel` worktree+branch is
   recommended ABANDON with citations, gated on owner approval.
2. **Given** Phase 2 (`enable_cloudfront_waf=false`) is not on main and not on the branch, **When**
   the decision is recorded, **Then** it is surfaced as a SEPARATE open item (finish Phase 2 vs
   consciously accept the disassociated ACL) routed to the owner — never silently closed by
   deleting the branch.

### Edge Cases

- **Squash-merge false "unique" commits**: `git log origin/main..HEAD` shows 1381/1382/1383/1378b
  commits as unique by SHA reachability even though their patches are upstream. Containment MUST be
  judged by `git cherry` (patch-id) / `git branch --contains`, NOT by `log A..B`. (See Adversarial
  Review #1, AR1-F1.)
- **Untracked-work loss on `git worktree remove`**: `git worktree remove` refuses when a worktree
  has untracked/modified files unless `--force`. The 1380 specs are untracked in
  `agent-a7bc7836fc7e73b90`; forcing removal without preserving them first would delete the only
  copy. Preservation is a hard precondition (FR-002, AR1-F2).
- **Stale remote-tracking refs vs. live remote**: `git branch -vv` upstream labels are cached and
  can name remote branches that no longer exist. The authoritative check is `git ls-remote --heads
  origin <name>` (live). All five are absent live; the cached ref
  `refs/remotes/origin/1378b-cloudfront-waf-moved-block` is stale and should be pruned. (AR1-F3.)
- **Orphan Branch Prevention rule**: Per CLAUDE.md "Orphan Branch Prevention (143)", a remote
  branch must be verified safe (has an associated merged PR, or is absent) before any
  `push origin --delete`. Here no remote deletion is needed; the rule is satisfied by the
  ls-remote-absent evidence, not by a deletion. (AR1-F4.)
- **`.venv` in sa-cfdel**: untracked but not work — it is a rebuildable virtualenv. Safe to discard
  with the worktree (do not attempt to "preserve" it).
- **Append-only discipline**: No history rewrite, no force-push, no rebase of merged work is
  performed. Branch/worktree deletion is ref/working-tree cleanup, not history mutation. (FR-013.)

## Requirements *(mandatory)*

### Functional Requirements

**Thread A — four agent worktrees**

- **FR-001**: For each of the four agent-worktree branch HEADs (`c2ff2f4`, `9dfff76`, `d3f20b7`,
  `dc3076a`), containment in `origin/main` MUST be re-verified at execution time via `git cherry
  origin/main <HEAD>` (patch-id) and/or `git branch -r --contains <HEAD>`, and the exact output
  recorded as deletion evidence, BEFORE any removal. `git log A..B` MUST NOT be used as the
  containment test (squash-merge false positives).
- **FR-002**: The untracked spec suite `specs/1380-oauth-avatar-picture/{spec,plan,tasks}.md` in
  `agent-a7bc7836fc7e73b90` MUST be preserved (copied into the main repo's
  `specs/1380-oauth-avatar-picture/` and committed, OR explicitly dispositioned by the owner as
  disposable) BEFORE that worktree is removed. Removal of that worktree is BLOCKED until
  preservation is confirmed.
- **FR-003**: After FR-001 (and FR-002 for the a7bc worktree) pass, each of the four agent
  worktrees MUST be removed via `git worktree remove` (using `--force` only after untracked work is
  preserved/dispositioned).
- **FR-004**: After their worktrees are removed and containment verified, the four local branches
  (`worktree-agent-a7bc7836fc7e73b90`, `1382-apigw-cors-patch`, `1381-oauth-session-persistence`,
  `1383-oauth-env-durability`) MUST be deleted locally (`git branch -d`, preferring `-d` over `-D`
  so git's own merged-check acts as a second gate; `-D` only with recorded `git cherry` evidence
  since squash-merge defeats `-d`).
- **FR-005**: No remote branch deletion MUST be performed for the four Thread-A branches unless a
  live `git ls-remote --heads origin <name>` shows the branch present; current evidence shows all
  four ABSENT, so remote deletion is a no-op and MUST NOT be invented.

**Thread B — 1378 / sa-cfdel**

- **FR-006**: Containment of `ac2bf32` in `origin/main` MUST be re-verified (`git cherry` +
  identification of the merged PR #911 / `78f1037`) and recorded before any removal.
- **FR-007**: The Phase-2 state MUST be reported from primary evidence: `origin/main:preprod.tfvars`
  `enable_cloudfront_waf` value, and the absence of any commit flipping it to `false`. The report
  MUST state explicitly whether a disassociated-but-undeleted CloudFront WebACL likely still exists
  in the account.
- **FR-008**: The `sa-cfdel` worktree + `1378b-cloudfront-waf-moved-block` local branch MUST
  receive a documented ABANDON recommendation (its only commit is merged; no unmerged work), gated
  on owner approval, with citations.
- **FR-009**: The question "should Phase 2 be completed?" MUST be surfaced as a SEPARATE
  owner-gated open item, distinct from the branch-abandon decision. Deleting the branch MUST NOT be
  treated as closing the teardown. The recommendation MUST present both options with consequences:
  (a) FINISH Phase 2 — flip `enable_cloudfront_waf=false` in `preprod.tfvars` (+ the FR-016 line-969
  decoupling) + apply, which deletes the orphaned CloudFront WAF (no new AWS resource created); or
  (b) ACCEPT — deliberately keep the ACL (documented cost/decision).
- **FR-016**: Phase-2 FINISH MUST also change the `main.tf:969` guard from `var.enable_waf` to
  `var.enable_cloudfront_waf` (or an equivalent `length(module.waf_cloudfront) > 0` guard), applied
  IN THE SAME commit/apply as the `enable_cloudfront_waf=false` flip. Rationale: Feature 1392 sets
  `enable_waf=true`; with the current guard, the combined end-state (`enable_waf=true` +
  `enable_cloudfront_waf=false`) makes `main.tf:969` index an empty `module.waf_cloudfront[0]` and
  the plan errors. This change is RESOURCE-NEUTRAL (with `enable_cloudfront_waf=false` it evaluates
  to `""`, unchanged from what `module.cloudfront_sse` already receives) — it is not a new resource
  delta; it only makes the two toggles independent. It MUST NOT be applied standalone while
  `enable_cloudfront_waf` is still `true` (doing so would re-associate the CloudFront WAF); it lands
  together with the `false` flip.
- **FR-017**: The Phase-2 `terraform plan` MUST show destroys confined to `module.waf_cloudfront[0].*`
  ONLY — i.e. `aws_wafv2_web_acl.main` AND its module-scoped `aws_cloudwatch_metric_alarm.waf_blocked[0]`
  (two resources; the WebACL's rules are inline blocks, not separate resources; the CLOUDFRONT-scope
  association resource has `count=0` and is absent). NOTHING outside that module may change: no
  destroy of `module.waf` (Feature 1392's API-GW WAF), no change to `module.cloudfront_sse`, no other
  collateral. The `moved` block (`main.tf:1028-1031`) becomes a no-op at `count=0`. Any delta outside
  `module.waf_cloudfront[0]` BLOCKS and routes to the owner.
- **FR-010**: If the owner approves ABANDON (FR-008), the `sa-cfdel` worktree MUST be removed and
  the local branch deleted; the untracked `.venv` is discarded with it (not preserved).

**Cross-cutting**

- **FR-011**: After all removals, `git worktree list` MUST show only the two real checkouts
  (`/home/zeebo/projects/sentiment-analyzer-gsk` and — unless FR-010 executed — no others under
  `.claude/worktrees/`), and no orphaned branch (local or remote) MUST remain for any reconciled
  item (CLAUDE.md Orphan Branch Prevention satisfied).
- **FR-012**: Stale local remote-tracking refs for deleted/absent branches (e.g.
  `refs/remotes/origin/1378b-cloudfront-waf-moved-block`) MUST be pruned (`git remote prune origin`
  or `git branch -dr`) so `git branch -vv` no longer shows phantom upstreams.
- **FR-013**: The reconciliation MUST use append-only discipline: NO history rewrite, NO force-push,
  NO rebase of already-merged commits. Only worktree removal, local branch deletion, and (if
  approved) the Phase-2 one-line tfvars change are permitted mutations.
- **FR-014**: NO new AWS resources are created. The only possible AWS effect is Phase-2 DELETING an
  already-orphaned WebACL, and only if the owner approves FINISH (FR-009). This feature never
  provisions.
- **FR-015**: Every destructive action (worktree removal, branch deletion, remote-branch deletion,
  Phase-2 apply) is OWNER-GATED. This spec recommends with evidence; it MUST NOT pre-decide or
  perform destructive operations without owner approval.

### Key Entities *(include if feature involves data)*

- **Worktree**: a linked working directory bound to a branch (`git worktree list`). Removing it
  detaches the directory; the branch survives until separately deleted.
- **Branch (local / remote-tracking / remote)**: local branch (`refs/heads/*`), cached
  remote-tracking ref (`refs/remotes/origin/*`), and the live remote branch (`git ls-remote`). These
  three can disagree; the live remote is authoritative for orphan-prevention.
- **CloudFront WebACL (WAF)**: the `module.waf_cloudfront[0]` resource gated by
  `enable_cloudfront_waf`. Phase-1 disassociated it; Phase-2 (unshipped) would delete it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For all six worktrees, a recorded `git cherry` / `git branch --contains` result plus
  `git status --porcelain` output exists, and each has a written finish/abandon decision citing it.
- **SC-002**: The 1380 spec suite exists in the main repo (or a written owner disposition marks it
  disposable) BEFORE any worktree removal — zero unmerged work lost.
- **SC-003**: After execution, `git worktree list` shows no `.claude/worktrees/agent-*` entries and
  `git branch` lists none of the four Thread-A branches.
- **SC-004**: `git ls-remote --heads origin` shows no orphaned branch for any reconciled item, and
  no `push origin --delete` was run against a branch lacking a merged PR (Orphan Prevention held).
- **SC-005**: The 1378 report states the Phase-2 fact (`enable_cloudfront_waf=true` on main, no flip
  commit) and gives a clear ABANDON-branch + separate Phase-2 owner decision.
- **SC-006**: `git branch -vv` shows no phantom upstream for the pruned refs.
- **SC-007**: No history was rewritten (reflog/`git log` on main unchanged); no new AWS resource
  created.

## Assumptions

- The four 1381/1382/1383/#938 PRs are truly merged (confirmed by PR numbers in `main` commit
  subjects and by `git cherry` patch-equivalence).
- The 1380 feature (oauth-avatar-picture) was specced in the a7bc worktree but never merged; its
  specs are the only copy. (Confirmed: `git ls-tree -r origin/main | grep 1380` is empty.)
- `sa-cfdel`'s `.venv` is a rebuildable virtualenv, not deliverable work.
- Owner approval will be obtained before any destructive step (FR-015).

## Out of Scope

- Actually implementing Feature 1380 (avatar/picture) — this feature only PRESERVES its specs.
- The full CloudFront/WAF architecture decision (the standing "no new AWS resources" memory already
  covers provisioning; Phase-2 here is a teardown, not a build).
- Deleting any branch that has an unmerged commit (none found; if one appeared, it would BLOCK).
- Cleaning up the many other stale local branches shown in `git branch -vv` (e.g. `A-*`…`J-*`) —
  those are out of this feature's charter (only the six named worktrees).

---

## Adversarial Review #1

**Reviewer stance**: Assume the recommendation is wrong. Attacks named by the charter: could a
deletion lose unmerged work? Is any branch NOT actually in main? Does removing a worktree strand a
branch on the remote? Does the CLAUDE.md orphan rule get violated?

### Findings

**AR1-F1 (HIGH → resolved): "Unique commit" false positive from squash-merge.** `git log
origin/main..HEAD` reports `9dfff76`/`d3f20b7`/`dc3076a`/`ac2bf32` as unique commits — which, read
naively, says "this branch has unmerged work, do NOT delete." That reading is WRONG: 1381/1382/1383
were **squash-merged**, minting new SHAs on main, so the original branch commit is unreachable from
main by SHA but its *patch* is upstream. *Resolution*: The containment test is `git cherry
origin/main <HEAD>` (patch-id); all four show a leading `-` (equivalent upstream). FR-001/FR-006
mandate `git cherry` and explicitly forbid `log A..B` as the test. **Gate impact: this is the
single most dangerous misread; without it a reviewer might either (a) refuse a safe cleanup forever,
or (b) `git branch -D` while wrongly believing the `-d` refusal was a bug. Codified.**

**AR1-F2 (CRITICAL → resolved in spec): Untracked 1380 specs would be destroyed.**
`agent-a7bc7836fc7e73b90` holds an untracked `specs/1380-oauth-avatar-picture/` suite (~55 KB,
three files) that is NOT on `origin/main` (`git ls-tree -r origin/main | grep 1380` = empty). A
routine `git worktree remove --force` would delete the ONLY copy of a full feature spec. This is
genuine unmerged work, mis-hiding as "just an agent worktree." *Resolution*: FR-002 makes
preservation a hard, blocking precondition (copy into main repo + commit, or explicit owner
disposition) before that worktree is touched. Task T002 gates T005 on it. **Gate impact: this is
the one place the cleanup could actually lose work; converted from a latent CRITICAL to a
sequenced precondition. This is the highest-value finding in the feature.**

**AR1-F3 (MEDIUM → resolved): Stale upstream labels imply remote branches that don't exist.**
`git branch -vv` prints `[origin/1381-oauth-session-persistence]` etc., which could lead someone to
run `git push origin --delete 1381-oauth-session-persistence` — a confusing no-op at best, or (if a
same-named branch were later recreated) a wrong deletion. *Investigation*: live `git ls-remote
--heads origin <name>` returns nothing for all five names; the labels are cached
`refs/remotes/origin/*` refs. *Resolution*: FR-005 (deletion only if live-present), FR-012 (prune
stale refs). **Gate impact: prevents an orphan-rule misfire in the wrong direction.**

**AR1-F4 (MEDIUM → resolved): Does removing a worktree strand its branch on the remote?** The
charter's explicit worry. *Investigation*: Removing a worktree only detaches the working directory;
it does not touch remote refs. And the live remote has none of these branches, so nothing can be
stranded. The branches are LOCAL-only. *Resolution*: FR-011 asserts the post-state (no orphaned
local or remote branch); FR-004 deletes the now-detached local branches. **Gate impact: the feared
failure mode is structurally impossible here (nothing on remote to strand).**

**AR1-F5 (MEDIUM → resolved): Abandoning `sa-cfdel` silently closes an unfinished teardown.** The
branch is abandon-safe, but the teardown it belongs to is NOT finished (Phase 2 unshipped). If the
board card is closed merely by deleting the branch, an orphaned CloudFront WebACL persists in the
account, undocumented. *Resolution*: FR-008 (abandon the branch) and FR-009 (surface Phase-2 as a
SEPARATE owner decision) are deliberately split. **Gate impact: prevents "cleaned the branch,
forgot the ACL" — the exact reason the card says 'not reconciled.'**

**AR1-F6 (LOW): `worktree-agent-a7bc7836fc7e73b90` HEAD is a literal ancestor, not a squash.**
Unlike the other three, `c2ff2f4` is an actual ancestor of `origin/main` (it is #938's merge-base
commit; `git branch -r --contains c2ff2f4` lists `origin/main`, and `log origin/main..HEAD` is
empty). So `git branch -d worktree-agent-a7bc7836fc7e73b90` will succeed without `-D`. Documented so
the implementer isn't surprised by the asymmetry. **Gate impact: documentation only.**

**AR1-F7 (LOW): `.venv` under sa-cfdel is untracked too.** Unlike the 1380 specs, it is a
rebuildable virtualenv, not work. FR-010 explicitly discards it; it must NOT trigger the FR-002
preservation path. **Gate impact: prevents a spurious "preserve untracked files" over-correction.**

**AR1-F8 (CRITICAL → resolved in spec): Phase-2 `enable_cloudfront_waf=false` is NOT independent of
Feature 1392's `enable_waf=true` — the combined plan ERRORS.** The two toggles look independent
(different modules, different scopes, different tfvars keys) but `main.tf:969`
(`waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""`) couples them: it
guards on `enable_waf` yet indexes `module.waf_cloudfront[0]`, which exists only when
`enable_cloudfront_waf` is true. At the battleplan end-state (`enable_waf=true` +
`enable_cloudfront_waf=false`) the true-branch indexes a `count=0` module → terraform
"Invalid index" error. This is unreachable in EITHER apply order without a code change: enabling the
API-GW WAF (1392) after deleting the CloudFront WAF (1393) errors, and doing 1392 first re-associates
the CloudFront WAF (undoing Phase 1) then errors on the 1393 flip. *Resolution*: FR-016 folds a
resource-neutral line-969 guard fix (`var.enable_waf` → `var.enable_cloudfront_waf`) into the same
apply as the `false` flip, decoupling them; FR-017 constrains the plan to `module.waf_cloudfront[0]`
destroys only. Sequencing: this teardown (with the FR-016 fix) lands BEFORE 1392's `enable_waf`
flip. **Gate impact: without this, the two owner-approved changes are mutually incompatible and
neither the teardown-then-enable nor enable-then-teardown path plans cleanly. Highest-value new
finding in the re-scope.**

### Edits applied to spec

- Elevated 1380-spec preservation to a hard blocking precondition (FR-002) with AR1-F2 as CRITICAL.
- Mandated `git cherry`/`branch --contains` and forbade `log A..B` in FR-001/FR-006 (AR1-F1).
- Split branch-abandon (FR-008) from Phase-2 decision (FR-009) (AR1-F5).
- Added FR-005/FR-012 for stale-ref handling (AR1-F3), FR-011 post-state (AR1-F4).

### Gate

- CRITICAL: 0 open (AR1-F2 resolved by FR-002 blocking precondition; AR1-F8 resolved by FR-016 line-969 decoupling + FR-017 plan constraint)
- HIGH: 0 open (AR1-F1 resolved by containment-test mandate)
- MEDIUM: 0 open (AR1-F3/F4/F5 resolved)
- LOW: 2 documented (AR1-F6 ancestor asymmetry, AR1-F7 .venv)

**AR#1 GATE: PASS (0 CRITICAL / 0 HIGH open).**

---

## Clarifications

Session 2026-07-24 (self-answered from live git evidence; unanswerable items deferred to owner).

### C1 — Are the 1381/1382/1383 branches actually merged, given `git log A..B` shows unique commits?

**Answer: YES, merged (patch-equivalent).** `git cherry origin/main <HEAD>` returns a leading `-`
for `9dfff76`, `d3f20b7`, `dc3076a` (and `ac2bf32`), meaning an equivalent patch is already
upstream (squash-merged as #940/#942/#941/#911). The `log A..B` "unique" lines are SHA-reachability
artifacts of squash-merge, not unmerged work. Containment is judged by patch-id, per FR-001.

### C2 — Is there any unmerged work in any of the six worktrees?

**Answer: EXACTLY ONE item — the untracked `specs/1380-oauth-avatar-picture/` suite in the a7bc
worktree.** All committed HEADs are patch-upstream; all working trees are clean EXCEPT (a) a7bc's
untracked 1380 specs (genuine, must preserve — FR-002) and (b) sa-cfdel's untracked `.venv`
(rebuildable, discard — FR-010). Evidence: `git -C <wt> status --porcelain` for each.

### C3 — Do any of these branches exist on the remote (does deletion risk orphaning)?

**Answer: NO — all five are absent on origin (live `ls-remote`).** No `push origin --delete` is
needed or appropriate. Removing the worktrees strands nothing. The `git branch -vv` upstream labels
are stale cached refs (prune per FR-012).

### C4 — Did Phase-2 of the 1378 teardown ship, and should the sa-cfdel branch finish it?

**Answer: NO, Phase-2 did not ship, and NO, the branch cannot finish it.** `origin/main:preprod.tfvars:72`
is `enable_cloudfront_waf = true`; no commit flips it to `false` (`git log -S`). The `sa-cfdel`
branch's only commit (the moved block) is already merged as #911 and does not contain Phase-2
either. So the branch is ABANDON-safe (FR-008), and Phase-2 is a SEPARATE, still-open owner decision
(FR-009) — not something the branch can be "rebased to finish."

### C5 — Should the 1380 specs be committed to main, or is preserving them elsewhere enough?

**Answer: Commit them into the main repo's `specs/1380-oauth-avatar-picture/` (recommended), OR
obtain an explicit owner disposition that they are disposable.** They are the only copy of a full
feature spec suite; the safest, append-only-compatible action is to add + commit them so they live
in tracked history before the worktree is removed. Final call is owner-gated (FR-015, O2).

### C6 — Are `enable_waf` (1392) and `enable_cloudfront_waf` (1393) independent toggles?

**Answer: NOT fully — they are coupled by one line, `main.tf:969`, and that coupling breaks the
combined end-state until fixed.** Structurally they gate different modules at different scopes
(`module.waf` REGIONAL `main.tf:925` vs `module.waf_cloudfront` CLOUDFRONT `main.tf:996`), share only
the `preprod.tfvars` file, and the `moved` block (`main.tf:1028-1031`) touches only
`module.waf_cloudfront`. The ONE coupling is `main.tf:969`
(`var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""`): it guards on `enable_waf` but indexes
`module.waf_cloudfront[0]`. With 1392 setting `enable_waf=true` and this teardown setting
`enable_cloudfront_waf=false`, that line indexes a `count=0` module → terraform "Invalid index"
error. Evidence: `main.tf:969` vs `main.tf:996`. Resolution: FR-016 re-guards line 969 on
`enable_cloudfront_waf` (resource-neutral), applied with the `false` flip — AFTER which the two
toggles ARE independent and each flip touches only its own module. A combined plan then shows exactly
`+module.waf[0].*` (1392) and `−module.waf_cloudfront[0].*` (1393), nothing shared.

### Deferred to owner (cannot self-answer)

- **O1 (Phase-2 teardown intent):** Should the orphaned CloudFront WebACL be DELETED now (flip
  `enable_cloudfront_waf=false` + the FR-016 line-969 fix, apply — completes the teardown, no new
  resource) or deliberately KEPT? This is the real "not reconciled" question; the branch abandon
  does not answer it. **The battleplan's owner-approval to enable 1392 implies FINISH** (the two are
  interlocked via `main.tf:969`), but confirm.
- **O3 (is the CloudFront WebACL actually still present/billing?):** Primary evidence says Phase 2
  never shipped (`enable_cloudfront_waf=true` on main, no flip commit), so a disassociated ACL very
  likely persists — but confirm with a live `aws wafv2 list-web-acls --scope CLOUDFRONT --region
  us-east-1` before asserting it is billing. If already absent (deleted out-of-band), Phase-2 FINISH
  is a no-op and only the FR-016 line-969 fix is needed for 1392 to plan.
- **O2 (1380 specs disposition):** Commit the preserved 1380 spec suite to main, or discard it as
  abandoned planning? Default recommendation: commit (C5). Owner decides.
