# Implementation Plan: Repo Hygiene — Reconcile Dangling Worktrees & Branches

**Branch**: `1393-repo-hygiene-cleanup` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/1393-repo-hygiene-cleanup/spec.md`

> Authored by hand (speckit skills are branch-creating/interactive; planning-only). Structure
> follows `.specify/templates/plan-template.md`. This plan RECOMMENDS; every destructive step is
> owner-gated (FR-015).

## Summary

Reconcile six dangling worktrees/branches into a clean, orphan-free state, losing zero unmerged
work. Five of the six are confirmed patch-equivalent to `origin/main` and abandon-safe; the sixth
worktree (`agent-a7bc7836fc7e73b90`) additionally holds the ONLY copy of an untracked 1380 spec
suite that must be preserved first. Two threads:

- **A) Four battleplan agent worktrees** — verify patch-containment, PRESERVE the 1380 specs, remove
  worktrees, delete local branches. No remote deletion (all absent on origin).
- **B) 1378 / sa-cfdel** — the branch (`ac2bf32`, moved block) is already merged as #911, so ABANDON
  it. But Phase-2 of the teardown (`enable_cloudfront_waf=false`, delete the orphaned CloudFront
  WebACL) never shipped and the branch does not contain it — so Phase-2 is surfaced as a SEPARATE
  owner decision, not closed by the branch abandon.

## Technical Context

**Language/Version**: N/A (git operations + Terraform HCL config for the optional Phase-2 flip)
**Primary Dependencies**: `git` (worktree/branch/cherry/ls-remote), `gh` (PR confirmation),
Terraform 1.5+ / AWS Provider ~> 5.0 (only if owner approves Phase-2)
**Storage**: N/A (no application data). CloudFront WebACL is the only AWS object touched, and only
under Phase-2 FINISH (a deletion, not a creation).
**Testing**: git-state assertions (`git worktree list`, `git branch`, `git ls-remote`,
`git cherry`); for optional Phase-2, `terraform plan` shows a single WebACL destroy and no other
change. No unit tests (no code).
**Target Platform**: local git working environment; AWS preprod (Phase-2 only).
**Project Type**: repo maintenance / infra reconciliation.
**Performance Goals**: N/A.
**Constraints**: Append-only history (no rewrite/force-push, FR-013). No new AWS resources (FR-014).
Every destructive op owner-gated (FR-015). CLAUDE.md Orphan Branch Prevention (143) governs any
remote-branch deletion.
**Scale/Scope**: 6 worktrees, 4 local branches (+1 under Thread B), 1 untracked spec suite to
preserve, 1 optional one-line tfvars flip. Small blast radius; the only irreversible risk is
losing the 1380 specs (mitigated by FR-002).

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after design.*

| Requirement | Status | Notes |
|---|---|---|
| No history rewrite / append-only | PASS | Only worktree/branch cleanup + optional tfvars edit; no rebase of merged work, no force-push (FR-013). |
| Least privilege / no new resources | PASS | FR-014: zero new AWS resources; Phase-2 (optional) only DELETES an orphaned ACL. |
| Secrets never in source/logs | PASS | No secret touched; git refs and tfvars booleans only. |
| IaC via Terraform, pinned providers | PASS | Optional Phase-2 is a `var` flip in `preprod.tfvars`; no module/provider change. |
| Owner-gated destructive actions | PASS | FR-015: recommend-only; owner approves each removal/deletion/apply. |
| Orphan Branch Prevention (CLAUDE.md 143) | PASS | Remote deletion only if live-present (none are); post-state asserts no orphan (FR-005/011/012). |
| Data-loss avoidance | PASS | FR-002 preserves the only-copy 1380 specs before any removal. |

**Constitution gate: PASS.** No violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/1393-repo-hygiene-cleanup/
├── spec.md      # Complete (+ Adversarial Review #1)
├── plan.md      # This file (+ Adversarial Review #2)
└── tasks.md     # (+ Adversarial Review #3)
```

No `data-model.md` / `contracts/` (no data model, no API surface).

### Affected paths (repository / environment)

```text
.claude/worktrees/agent-a7bc7836fc7e73b90/   # remove (after preserving 1380 specs)
.claude/worktrees/agent-a8e8e02a5cda3ab4c/   # remove
.claude/worktrees/agent-a9be816c9de30681b/   # remove
.claude/worktrees/agent-af6490ffbc33d1c2c/   # remove
/home/zeebo/projects/sa-cfdel/               # remove (Thread B, owner-approved)
specs/1380-oauth-avatar-picture/             # CREATE in main repo (preserve untracked specs)
infrastructure/terraform/preprod.tfvars      # Phase-2: enable_cloudfront_waf true→false (line 72)
infrastructure/terraform/main.tf             # Phase-2: line 969 guard enable_waf → enable_cloudfront_waf (FR-016 decouple)
```

## Per-Worktree / Branch State Table (git evidence, gathered 2026-07-24 post-`fetch`)

| # | Worktree | Local branch | HEAD | Containment test | Result | Working tree | Remote (live ls-remote) | Decision |
|---|---|---|---|---|---|---|---|---|
| A1 | `.claude/worktrees/agent-a7bc7836fc7e73b90` | `worktree-agent-a7bc7836fc7e73b90` | `c2ff2f4` | `branch -r --contains` → lists `origin/main`; `log origin/main..HEAD` empty | **IN main** (literal ancestor, #938) | **untracked `specs/1380-oauth-avatar-picture/`** (only-copy) | ABSENT | **ABANDON worktree+branch — but PRESERVE 1380 specs first** |
| A2 | `.claude/worktrees/agent-a8e8e02a5cda3ab4c` | `1382-apigw-cors-patch` | `9dfff76` | `git cherry origin/main 9dfff76` | `- 9dfff76…` (patch-equiv, #940) | clean | ABSENT | **ABANDON** (remove + delete local) |
| A3 | `.claude/worktrees/agent-a9be816c9de30681b` | `1381-oauth-session-persistence` | `d3f20b7` | `git cherry origin/main d3f20b7` | `- d3f20b7…` (patch-equiv, #942) | clean | ABSENT | **ABANDON** |
| A4 | `.claude/worktrees/agent-af6490ffbc33d1c2c` | `1383-oauth-env-durability` | `dc3076a` | `git cherry origin/main dc3076a` | `- dc3076a…` (patch-equiv, #941) | clean | ABSENT | **ABANDON** |
| B1 | `/home/zeebo/projects/sa-cfdel` | `1378b-cloudfront-waf-moved-block` | `ac2bf32` | `git cherry origin/main ac2bf32` | `- ac2bf32…` (patch-equiv, #911=`78f1037`) | untracked `.venv` only | ABSENT (stale cached ref exists) | **ABANDON branch+worktree; Phase-2 = SEPARATE owner decision** |

**Containment note (why `git cherry`, not `log`)**: 1381/1382/1383/1378b were squash-merged, so
`git log origin/main..HEAD` lists their original commits as "unique" by SHA reachability. That is a
false positive (AR1-F1). The authoritative test is patch-id: `git cherry origin/main <HEAD>` — a
leading `-` means "equivalent already upstream." All five show `-`. `c2ff2f4` is additionally a
literal ancestor (`branch --contains` lists `origin/main`).

## Finish-vs-Abandon Recommendation (per item)

### A1–A4 (four agent worktrees): **ABANDON** (owner-gated, low risk)

Evidence: all HEADs patch-equivalent to `origin/main` (features shipped as #938/#940/#941/#942);
no remote branches to strand; three working trees clean. The ONLY caveat is A1's untracked 1380
specs — **preserve before removal** (FR-002). Action: preserve → `git worktree remove` ×4 →
`git branch -d/-D` ×4 → `git remote prune origin`.

### B1 (sa-cfdel / 1378b branch): **ABANDON the branch+worktree** (owner-gated)

Evidence: `ac2bf32` is merged as #911 (`78f1037`); the moved block is on
`origin/main:main.tf:1029-1030`; no unmerged commits; only `.venv` untracked (discard). There is
nothing to "rebase and finish" on this branch — its work is done and upstream.

### B1-Phase-2 (the teardown thread): **SEPARATE owner decision — recommend FINISH**

This is the real content of the "not reconciled" board card, and it is NOT the branch. Evidence:

- `origin/main:preprod.tfvars:72` → `enable_cloudfront_waf = true` (ACL still declared/kept).
- No commit flips it to `false`: `git log origin/main -S "enable_cloudfront_waf = false" --
  infrastructure/terraform/` → empty.
- `variables.tf` on main documents the two-phase intent explicitly: "Phase 2: enable_cloudfront_waf=false
  (delete the now-orphaned ACL)."
- Phase-1 (#909, `1648a56`) disassociated the ACL (`enable_waf=false`) but kept it. So a
  disassociated, unused CloudFront WebACL very likely still exists in the account, costing a small
  monthly amount and adding drift.

**Recommendation: FINISH Phase-2** — in ONE commit/apply, flip `enable_cloudfront_waf=false` in
`preprod.tfvars:72` AND change the `main.tf:969` guard from `var.enable_waf` to
`var.enable_cloudfront_waf` (FR-016 decoupling). Run `terraform plan` and expect destroys confined
to `module.waf_cloudfront[0]` ONLY — the `aws_wafv2_web_acl.main` AND its module-scoped
`aws_cloudwatch_metric_alarm.waf_blocked[0]` (two resources; the WebACL's rules are inline blocks,
not separate resources; the CLOUDFRONT-scope association has `count=0` and is absent) — plus the
`moved` block (`main.tf:1028-1031`) becoming a no-op. NO other change. This is a DELETION, not a
creation, so it satisfies "no new AWS resources" (FR-014) and reduces cost/drift. It is a fresh,
small change on `main` (a new short-lived branch → PR), NOT a resurrection of `sa-cfdel`.

**Why the line-969 fix rides along (FR-016, AR1-F8):** Feature 1392 sets `enable_waf=true`. With the
current guard, the combined end-state (`enable_waf=true` + `enable_cloudfront_waf=false`) makes
`main.tf:969` index an empty `module.waf_cloudfront[0]` → terraform "Invalid index" error, in EITHER
apply order. The guard change is resource-neutral (with `enable_cloudfront_waf=false` it yields `""`,
unchanged for `module.cloudfront_sse`), so it adds no resource delta — it only decouples the two
toggles so 1392 can plan. It MUST NOT be applied alone while `enable_cloudfront_waf` is still `true`
(that would re-associate the CloudFront WAF, undoing Phase 1); it lands with the `false` flip.
**Sequencing: this teardown (with the FR-016 fix) lands BEFORE 1392's `enable_waf` flip.**

**"Exactly one destroy" — precision:** the earlier phrasing was imprecise. The teardown destroys TWO
resources, both inside `module.waf_cloudfront[0]` (WebACL + its alarm); the correct acceptance
criterion is "all destroys confined to `module.waf_cloudfront[0]`, nothing outside it" (FR-017) —
in particular no destroy of `module.waf` (1392's API-GW WAF) and no change to `module.cloudfront_sse`.

**Alternative: ACCEPT** — deliberately keep the disassociated ACL (e.g. if re-enabling WAF soon).
If chosen, document it on the board card so "not reconciled" is replaced with a real decision, and
close the card. Owner picks (O1).

**Why split**: abandoning the branch is safe and independent of the Phase-2 call. Bundling them
would either block a safe cleanup on an infra decision, or (worse) let deleting the branch masquerade
as finishing the teardown while an orphaned ACL lingers (AR1-F5).

## Phase 0 — Research (resolved)

All unknowns resolved from live git/Terraform state during spec authoring:

1. **Are the four agent branches merged?** YES — `git cherry` patch-equivalence to `origin/main`
   (#938/#940/#941/#942). `log A..B` false positives explained (squash-merge).
2. **Any unmerged work?** ONE item: untracked 1380 specs in A1 (preserve). All else clean or
   rebuildable (.venv).
3. **Do the branches exist on origin?** NO — live `ls-remote` empty for all five; only stale cached
   tracking refs remain.
4. **Is 1378b merged?** YES — #911 (`78f1037`); moved block on main.
5. **Did Phase-2 ship?** NO — `enable_cloudfront_waf=true` on main; no flip commit; branch doesn't
   contain it. Phase-2 is a separate, open owner decision.

## Phase 1 — Design (operational recipe, owner-gated at each destructive step)

### A) Preserve the 1380 specs (BLOCKING precondition for A1 removal)

```bash
# Copy the only-copy untracked spec suite into the main repo BEFORE removing the worktree.
mkdir -p specs/1380-oauth-avatar-picture
cp .claude/worktrees/agent-a7bc7836fc7e73b90/specs/1380-oauth-avatar-picture/*.md \
   specs/1380-oauth-avatar-picture/
git add specs/1380-oauth-avatar-picture/ && git commit -S -m "chore(1393): preserve 1380 spec suite before worktree cleanup"
# OR: owner explicitly dispositions the 1380 specs as disposable (record decision, skip commit).
```

### A) Re-verify containment, then remove worktrees + delete local branches

```bash
git fetch origin main
for h in c2ff2f4 9dfff76 d3f20b7 dc3076a; do echo "== $h =="; git cherry origin/main "$h" | head; done
git branch -r --contains c2ff2f4 | grep origin/main   # A1 literal ancestor

# after preservation confirmed:
git worktree remove .claude/worktrees/agent-a7bc7836fc7e73b90        # add --force only if untracked already preserved
git worktree remove .claude/worktrees/agent-a8e8e02a5cda3ab4c
git worktree remove .claude/worktrees/agent-a9be816c9de30681b
git worktree remove .claude/worktrees/agent-af6490ffbc33d1c2c

git branch -d worktree-agent-a7bc7836fc7e73b90    # -d succeeds (literal ancestor)
# squash-merged branches fail -d; use -D ONLY with the recorded `git cherry -` evidence:
git branch -D 1382-apigw-cors-patch 1381-oauth-session-persistence 1383-oauth-env-durability
```

### A) No remote deletion; prune stale refs

```bash
git ls-remote --heads origin worktree-agent-a7bc7836fc7e73b90 1381-oauth-session-persistence \
  1382-apigw-cors-patch 1383-oauth-env-durability   # expect empty → NO push --delete
git remote prune origin                              # clears stale cached tracking refs
```

### B) sa-cfdel abandon (owner-approved)

```bash
git cherry origin/main ac2bf32                       # expect: - ac2bf32… (merged #911)
git worktree remove /home/zeebo/projects/sa-cfdel    # --force to discard the untracked .venv
git branch -D 1378b-cloudfront-waf-moved-block
git branch -dr origin/1378b-cloudfront-waf-moved-block  # drop stale cached tracking ref (or remote prune)
```

### B) Phase-2 (only if owner approves FINISH — separate fresh branch/PR; interlocked with 1392)

Two edits in ONE commit (FR-016 — do not split):

```hcl
# infrastructure/terraform/preprod.tfvars:72  (Feature 1378 Phase 2)
enable_cloudfront_waf = false   # was true; deletes the now-orphaned, disassociated CloudFront WebACL
```
```hcl
# infrastructure/terraform/main.tf:969  (decouple from enable_waf so 1392 can enable the API-GW WAF)
# BEFORE: waf_web_acl_arn = var.enable_waf ? module.waf_cloudfront[0].web_acl_arn : ""
# AFTER:  waf_web_acl_arn = var.enable_cloudfront_waf ? module.waf_cloudfront[0].web_acl_arn : ""
```
`terraform plan -var-file=preprod.tfvars` MUST show destroys confined to `module.waf_cloudfront[0]`
ONLY (WebACL + its `aws_cloudwatch_metric_alarm.waf_blocked[0]`; association is `count=0`), the
`moved` block as a no-op, and NO change to `module.waf` or `module.cloudfront_sse` (FR-017). checkov
must pass with venv ACTIVE (the hcl2 gotcha — otherwise the checkov pre-commit hook crashes on the
`.tf` edit); GPG-signed commit. Apply via the normal CI/PR path — respect state-lock (CI owns
applies; do not run local `apply`/`plan` against locked state while CI deploys). This teardown MUST
land BEFORE Feature 1392's `enable_waf` flip.

## Phase 2 — Verification approach

1. `git worktree list` → only real checkouts remain (SC-003).
2. `git branch` → none of the four Thread-A branches (and, if B approved, no 1378b) (SC-003).
3. `git ls-remote --heads origin` → no orphaned reconciled branch (SC-004).
4. `specs/1380-oauth-avatar-picture/` present in main repo (or owner disposition recorded) (SC-002).
5. `git branch -vv` → no phantom upstreams (SC-006).
6. If Phase-2 applied: `terraform plan` clean; AWS shows the CloudFront WebACL gone; no new resource
   (SC-007, FR-014).

## Complexity Tracking

No constitution violations → table intentionally empty.

## Progress Tracking

- [x] Phase 0 research complete (resolved during spec)
- [x] Phase 1 design complete
- [x] Constitution check (initial) PASS
- [ ] Constitution re-check after AR#2
- [ ] tasks.md generated

---

## Adversarial Review #2

**Stance**: Hunt for spec↔plan drift, cross-artifact contradictions, and design flaws now that the
operational recipe is concrete.

### Drift checks (spec ↔ plan)

| Spec item | Plan coverage | Drift? |
|---|---|---|
| FR-001 (git cherry containment, not log A..B) | State table + Phase 1 re-verify loop | none |
| FR-002 (preserve 1380 specs, blocking) | Phase 1 "Preserve the 1380 specs" precedes removals | none |
| FR-003 (remove worktrees) | Phase 1 `git worktree remove` ×4 | none |
| FR-004 (delete local branches, prefer -d) | Phase 1 `-d` for A1, `-D`+evidence for squash-merged | none |
| FR-005 (no remote deletion unless present) | Phase 1 `ls-remote` check → no `push --delete` | none |
| FR-006 (verify ac2bf32, #911) | State table B1 + Phase 1 B `git cherry` | none |
| FR-007 (report Phase-2 state) | "B1-Phase-2" recommendation w/ tfvars + `log -S` evidence | none |
| FR-008 (abandon sa-cfdel branch) | "B1: ABANDON" | none |
| FR-009 (Phase-2 separate owner item) | "B1-Phase-2 SEPARATE decision" + O1 | none |
| FR-010 (remove sa-cfdel, discard .venv) | Phase 1 B `worktree remove --force` | none |
| FR-011 (post-state no orphan) | Phase 2 verification 1–3 | none |
| FR-012 (prune stale refs) | Phase 1 `git remote prune origin` / `branch -dr` | none |
| FR-013 (append-only) | Constitution check; no rebase/force-push anywhere | none |
| FR-014 (no new AWS resources) | Phase-2 is a DESTROY-only plan; Constitution check | none |
| FR-015 (owner-gated) | "owner-gated" on every destructive step; O1/O2 | none |
| FR-016 (line-969 decouple with the flip) | Phase-1 B recipe (two edits, one commit) + B1-Phase-2 rationale | none |
| FR-017 (destroys confined to `module.waf_cloudfront[0]`) | B1-Phase-2 precision + Phase-2 verification | none |

No drift. Every FR maps to a concrete plan element.

### New findings at design granularity

**AR2-F1 (MEDIUM → resolved): `git worktree remove --force` bypasses git's own untracked-work
guard.** The Phase-1 recipe uses `--force` for A1 and sa-cfdel. `git worktree remove` WITHOUT
`--force` refuses when untracked/modified files exist — that refusal is a useful safety net that
would catch a forgotten 1380 preservation. Using `--force` blindly defeats it. *Resolution*: Tasks
sequence the preservation commit (T002) as a hard predecessor of the A1 removal (T005), and reserve
`--force` for AFTER preservation is confirmed. For A2–A4 (clean trees) plain `git worktree remove`
suffices (no `--force`). Documented as an ordering acceptance criterion. **This is the highest-risk
implementation detail** — flagged for AR#3.

**AR2-F2 (MEDIUM → resolved): `git branch -D` defeats git's merged-check.** `-D` deletes regardless
of merge status; if the recorded `git cherry` evidence were stale (e.g. someone amended a branch
after the last fetch), `-D` would silently drop real work. *Resolution*: FR-001 mandates re-running
`git cherry` at execution time (not trusting the 2026-07-24 snapshot), and `-D` is permitted ONLY
with a fresh `-` result recorded. A1 uses `-d` (safe) because it's a literal ancestor. Tasks pin the
re-verify immediately before each `-D`.

**AR2-F3 (HIGH → resolved): Phase-2 `terraform plan` showing MORE than the CloudFront-WAF destroy —
two concrete causes.** (1) **The line-969 coupling (AR1-F8).** If the guard is left as
`var.enable_waf` and 1392 has set `enable_waf=true`, the plan does not merely show extra changes — it
ERRORS on an empty `module.waf_cloudfront[0]` index. FR-016 fixes the guard in the same commit so the
plan is valid and the destroys stay confined to `module.waf_cloudfront[0]`. (2) **Generic preprod
drift** bundling unrelated changes. *Resolution*: FR-017 + the Phase-2 task require READING the plan
and confirming destroys are confined to `module.waf_cloudfront[0].*` (WebACL + its alarm; two
resources, rules inline) with the `moved` block a no-op and NO change to `module.waf` or
`module.cloudfront_sse`; ANY delta outside that module BLOCKS and routes to the owner. The precise
acceptance is "confined to `module.waf_cloudfront[0]`", not the earlier imprecise "exactly one
destroy" (the alarm is a legitimate second destroy within the module). **Elevated to HIGH because the
coupling turns a vague 'extra changes' worry into a hard plan failure for the combined battleplan.**

**AR2-F4 (LOW → resolved): Order of worktree-remove vs branch-delete.** A branch checked out in a
worktree cannot be deleted while the worktree exists (git refuses). *Resolution*: Phase-1 removes
worktrees BEFORE deleting the corresponding local branches — already the recipe order. Documented.

**AR2-F5 (LOW): sa-cfdel is OUTSIDE the main repo tree.** It lives at `/home/zeebo/projects/sa-cfdel`,
not under `.claude/worktrees/`. `git worktree remove` still works by path, but the operator must run
it from the main repo (or with `-C`), not from inside `sa-cfdel`. *Resolution*: Task specifies
running removals from the main repo root. **Documentation only.**

### Cross-artifact consistency

- Clarifications C1–C5 and owner questions O1/O2 are consistent with the plan's recommendations
  (patch-id containment; preserve 1380; no remote deletion; abandon branch + separate Phase-2;
  commit-or-disposition the specs). No contradiction.
- The finish-vs-abandon table matches the spec's per-item decisions exactly.

### Constitution re-check (post-design)

Re-ran the gate with the concrete recipe: still PASS. Append-only holds (no rebase/force-push);
Phase-2 is destroy-only (no new resource); every destructive step owner-gated; orphan-prevention
satisfied by ls-remote-absent + prune. No new violations.

### Gate

- CRITICAL: 0 open (AR1-F8 coupling resolved by FR-016 decouple applied with the flip)
- HIGH: 0 open (AR2-F3 coupling/multi-destroy resolved by FR-016 + FR-017 plan-confinement gate)
- MEDIUM: 0 open (AR2-F1, AR2-F2 resolved via task ordering + re-verify criteria)
- LOW: 2 (AR2-F4/F5 resolved/documented)

**AR#2 GATE: PASS. Drift: none. Two highest-risk details elevated to AR#3: (AR2-F1)
preserve-before-force-remove, and (AR2-F3/FR-016) the line-969 decouple that must ride with the
Phase-2 flip so the combined battleplan plans cleanly.**

---

## Plan 2nd Pass (Stage 6)

**Outcome: SKIPPED (no structural drift).** AR#2 found zero spec↔plan drift. The two elevated
concerns (AR2-F1 preserve-before-force, AR2-F2 re-verify-before-`-D`) are task-ordering acceptance
criteria, not plan-structure changes. No re-plan required.
