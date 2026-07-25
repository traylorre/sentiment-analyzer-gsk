# Tasks: 1400-validator-gating

**Spec**: spec.md | **Plan**: plan.md
Dependency-ordered. No task starts implementation before Phase 3 approval.

## Phase A — Baseline (must be green before any gate exists)

- [ ] **T001** — Pre-clean main. Run the exact CI-shaped suite locally against a
  fresh main checkout: `SKIP=detect-secrets,gitleaks pre-commit run --all-files
  --show-diff-on-failure` with bandit rev ALREADY bumped to 1.9.4 and trivy
  `--exit-code 1` applied (test the future config, not the current one). Remediate
  every finding: code fixes preferred; `# nosec`/baseline entries only with
  documented justification per SAST policy. Regenerate `.checkov.baseline` at the
  CI-pinned checkov version if drift appears. **Exit: suite exits 0 on main.**
  [BLOCKS: everything]

- [ ] **T002** — Seed the pip-audit ignore file. Run `pip-audit -r
  requirements.txt` and `-r requirements-dev.txt` against main; for each current
  advisory decide: upgrade the pin (preferred) or seed `.pip-audit-ignore` with
  ID + expiry (≤90d) + justification. **Exit: pip-audit with seeded ignores exits
  0 on main.** [DEPENDS: none; parallel with T001]

- [ ] **T003** — Verify the two empirical unknowns (AR2-F1, AR2-F3):
  (a) `detect-secrets-hook --baseline .secrets.baseline` against `git ls-files` on
  a clean tree exits 0 (no line-number false-fails), and exits 1 when a synthetic
  secret file is added; (b) determine what `check-false-pass-patterns.sh
  --staged-only` does with an empty staged set in CI — if no-op, record the
  honest "local-only" comment in the workflow. **Exit: both behaviors documented
  with command output.** [DEPENDS: none; parallel]

## Phase B — Build the gate

- [ ] **T004** — Version pins commit: `.pre-commit-config.yaml` bandit rev →
  1.9.4; pyproject dev extra tightened; trivy `--exit-code 0` → `1`; update the
  stale comment block at .pre-commit-config.yaml:179-184 to point at the real job.
  [DEPENDS: T001 (findings from the bumped rev already remediated)]

- [ ] **T005** — Add the `pre-commit` job to pr-checks.yml per plan §1 (setup-python,
  system-tool installs at exact pins, pre-commit cache, SKIP list with per-hook
  justification comments, `--show-diff-on-failure`, blocking detect-secrets-hook
  step). Add `scripts/pip-audit-gate.sh` + `.pip-audit-ignore`; rewrite the
  `security` job: remove `|| true` (:159,:165) and `continue-on-error` (:161,:167),
  call the wrapper, keep artifact upload. [DEPENDS: T002, T003, T004]

## Phase C — Prove it gates (fails-red / passes-green)

- [ ] **T006** — Red-team the gate on a throwaway branch (NEVER merged;
  branch deleted after): plant, in three separate commits,
  (a) a bandit HIGH in `src/` (shell-injection pattern — deliberately unsafe
  fixture code whose only purpose is to trip the scanner),
  (b) a synthetic AWS-format key in a tracked file,
  (c) a requirements pin with a known advisory not in the ignore file, plus
  (d) an ignore-file entry dated yesterday.
  **Exit: CI runs show FOUR distinct red results (SC-001..SC-004), captured as
  run URLs in the PR description. Then revert commits, confirm green, close
  unmerged, delete branch.** [DEPENDS: T005] **← HIGHEST-RISK TASK (see AR#3)**

- [ ] **T007** — Timing check (SC-005): from T006's green run, record pre-commit
  job duration cold and cached; confirm ≤5 min and not the critical path.
  [DEPENDS: T006]

## Phase D — Enforce

- [ ] **T008** — Audit in-flight PRs (list open PRs, note which predate the job),
  observe ≥2 green runs on main, then request OWNER ACTION: mark `Pre-commit
  Hooks` and `Dependency Vulnerability Scan` as required status checks in branch
  protection. Record the flip date in the PR/board. [DEPENDS: T006, T007]

- [ ] **T009** — Close the honesty loop: update
  docs/cleanup-pristine/validator-inventory.md (bandit/detect-secrets/trivy/
  checkov move from "DARK in CI" to "Enforced"; pip-audit moves from "advisory"
  to "Enforced"; mypy stays dark, noted). Update RESUME-PRIORITY-BRIEF P3 status.
  [DEPENDS: T008]

---

## Adversarial Review #3 (execution-readiness attack)

**AR3-F1 (elevated AR2-F1 — detect-secrets-hook behavior): RESOLVED BY ORDERING.**
T003 verifies empirically before T005 wires it. If the hook false-fails, the
fallback (scan + hash-only diff) is specified in plan §AR2-F1. No task proceeds on
an assumption.

**AR3-F2 (elevated AR2-F2 — trivy DB drift): ACCEPTED RESIDUAL.** A trivy red
without a repo diff is the tool doing its job on a new CVE. Runbook line goes in
the workflow comment (T005). If drift-noise proves chronic post-flip, the escape
hatch is a trivyignore file with the SAME expiry discipline as pip-audit — NOT
`--exit-code 0`. Never regress to decorative.

**AR3-F3 (T006 is the highest-risk task): planted-bad fixtures touching `src/` and
requirements on a shared repo.** Attack vectors: (a) the throwaway branch gets
merged by mistake — mitigated: PR opened as DRAFT, title-prefixed `DO NOT MERGE
[gate red-team]`, closed not merged, branch deleted, and the planted secret is
SYNTHETIC (fake key format, never a real credential); (b) gitleaks/secrets-scan
history scan (fetch-depth: 0) later flags the deleted branch's commits — mitigated:
synthetic key uses a documented-fake pattern and gets a `.gitleaks.toml`/baseline
allowlist entry ONLY if it ever resurfaces, with a comment linking this spec;
(c) the vulnerable pin lands in the pip cache or a lockfile — no lockfile in this
path, and the branch never merges. Residual risk LOW.

**AR3-F4 (sequencing hole probe): can T005 land while main is dirty?** No — T001
gates Phase B by construction, and T005's PR itself runs the new job (a
self-proving PR: if the gate job is red on its own PR, it cannot merge once
required; before required-flip, reviewer checks it manually — noted in T005).

**AR3-F5 (owner-action dependency): T008's branch-protection flip is outside repo
control.** If the owner defers, the job still runs and reports on every PR
(non-required) — partial win, honestly reportable as "runs on every PR" but NOT
yet as "gates every deploy." The resume claim stays unfixed until T008 completes.
This is the feature's definition-of-done, not a nice-to-have.

### Gate

- Highest-risk task: **T006** (planted-bad red-team) — mitigations in AR3-F3,
  residual LOW.
- Blocking unknowns: none (both AR#2 elevations resolved by T003 ordering or
  accepted with escape hatch).
- Owner actions required: T008 branch-protection flip (flagged, not a spec
  blocker).

**AR#3 GATE: READY for Phase 3 implementation — with two hard conditions:
(1) T001 must exit 0 on main before T005 lands; (2) T006's branch is draft-only,
synthetic-secret-only, closed-unmerged.**
