# Feature Specification: Validator Gating — Make the Dark Validators Actually Gate

**Feature ID**: 1400-validator-gating
**Status**: Spec (Stages 1-8, no implementation)
**Source**: RESUME-PRIORITY-BRIEF P3 (honesty fix); docs/cleanup-pristine/validator-inventory.md (refuter-confirmed)
**Branch (future)**: `1400-validator-gating`

## The Honesty Gap

The resume claim is "machine review gates every deploy." The reality, refuter-verified:

1. **No CI job runs pre-commit.** `grep -rln pre-commit .github/workflows/` returns
   nothing. bandit, detect-secrets, trivy, checkov, and mypy exist only as local
   pre-commit hooks. A contributor who never runs `pre-commit install` — or who
   commits with `--no-verify`, or pushes from a machine without trivy/checkov on
   PATH — bypasses every one of them, and the PR merges green.
2. **pip-audit is advisory-only.** `.github/workflows/pr-checks.yml` lines 159 and
   165 end in `|| true`; lines 161 and 167 set `continue-on-error: true`. Belt AND
   suspenders on never failing. It runs on every PR and can never block one.
3. **Bandit version drift is three-way**, worse than the brief's two-way claim:
   - `.pre-commit-config.yaml:97` — rev `1.7.10` (what local commits actually run,
     in pre-commit's isolated env)
   - `requirements-dev.txt:38` / `requirements-ci.txt:59` — `bandit==1.9.4`
   - installed in `.venv` — `bandit 1.9.2` (venv is stale vs its own pin)
   - `pyproject.toml:54` dev extra — `bandit>=1.7.0` (floats)

   Three surfaces, three different versions. A finding introduced between 1.7.10
   and 1.9.4 is invisible to the hook that's supposed to catch it at commit time.
4. **Bonus finding (this spec's audit)**: even locally, the trivy hook cannot fail —
   `.pre-commit-config.yaml:109` hardcodes `--exit-code 0`. It is decorative on
   every machine it runs on.

The irony: `.pre-commit-config.yaml:179-184` contains a comment block describing
exactly the CI integration that was never built ("In GitHub Actions, add:
`pre-commit run --all-files`. This ensures CI and local hooks are always in sync.").

What IS enforced server-side today (per validator-inventory.md): ruff format/check,
gitleaks, pytest+80% coverage, Playwright PR tier, CodeQL. Everything else is local
theater or advisory.

## Functional Requirements

- **FR-001**: A CI job in pr-checks.yml runs `pre-commit run --all-files
  --show-diff-on-failure` on every PR to main and on pushes to main, and FAILS the
  build on any hook failure. No `|| true`, no `continue-on-error`.
- **FR-002**: Hooks that are local-workflow-only are explicitly excluded from the CI
  invocation via the `SKIP` env var, with each exclusion justified in a comment:
  - `detect-secrets` (the autostage wrapper mutates and `git add`s the baseline — a
    file-modifying retry loop has no place in a blocking gate). CI gets equivalent
    coverage via a dedicated blocking `detect-secrets-hook --baseline
    .secrets.baseline` step (plus the existing gitleaks job).
  - `gitleaks` (already a dedicated blocking CI job at pr-checks.yml:218-235;
    running it twice buys nothing).
  - Push-stage hooks (pytest, check-branch-collision, check-error-log-assertions)
    are automatically out of scope: `default_stages: [commit]` means
    `run --all-files` never invokes them, and CI runs pytest in its own job.
  - `mypy` stays `stages: [manual]` — out of scope for this feature (typing debt is
    unquantified; making it blocking risks permared; see Non-Goals).
- **FR-003**: The CI runner installs the `language: system` hook dependencies
  (trivy, checkov) before invoking pre-commit, at pinned versions.
- **FR-004**: pip-audit becomes blocking: remove `|| true` (pr-checks.yml:159,165)
  and `continue-on-error: true` (:161,:167). Blocking is made *sustainable* via a
  curated ignore list, NOT a blanket pass:
  - Ignored vuln IDs live in a tracked file (`.pip-audit-ignore` or equivalent),
    one entry per line with vuln ID, expiry date, and one-line justification.
  - A wrapper script translates entries into `--ignore-vuln` flags and FAILS CI if
    any entry is past its expiry date. Ignores are loans, not write-offs.
  - Maximum ignore lifetime 90 days per entry; renewal requires a fresh commit with
    updated justification (visible in PR diff, reviewable).
- **FR-005**: Bandit is pinned to ONE version everywhere: `.pre-commit-config.yaml`
  rev, `requirements-dev.txt`, and `requirements-ci.txt` all agree (target: the
  current reqs pin, 1.9.4, unless the hook run against the current tree surfaces a
  1.9.x-only false-positive wave — see plan). `pyproject.toml` dev extra tightened
  from `>=1.7.0` to match. Developer venvs re-sync via existing bootstrap docs.
- **FR-006**: The trivy hook's `--exit-code 0` becomes `--exit-code 1` so it can
  actually fail, both locally and in CI (HIGH,CRITICAL severities, as today).
- **FR-007**: The gate lands in two steps: (a) job added and observed green on main
  (baseline must be clean BEFORE the job exists — pre-cleaned in this feature's
  implementation), then (b) job marked as a required status check. Open PRs are
  handled per the migration note in plan.md.
- **FR-008**: pre-commit environments are cached in CI (keyed on
  `.pre-commit-config.yaml`) so the added job does not dominate PR wall-clock time.

## Success Criteria

Each is a fails-red proof, not a "job exists" proof:

- **SC-001**: A test PR containing a planted bandit HIGH (e.g.
  `subprocess.call(user_input, shell=True)` in `src/`) FAILS the pre-commit CI job.
- **SC-002**: A test PR containing a planted secret that gitleaks/detect-secrets
  patterns match (synthetic AWS key format) FAILS CI.
- **SC-003**: A test PR pinning a dependency with a known unignored vulnerability
  (or a temporarily emptied ignore list against a currently-vulnerable pin) FAILS
  the security job.
- **SC-004**: An expired entry in the pip-audit ignore file FAILS CI on its own.
- **SC-005**: `pre-commit run --all-files` on a clean main passes in CI (no
  permared), and the job completes within budget (see plan; target ≤ 5 min,
  parallel to existing jobs so marginal wall-clock ≈ 0).
- **SC-006**: `grep bandit` across `.pre-commit-config.yaml`, `requirements-dev.txt`,
  `requirements-ci.txt` yields one version.

## Non-Goals

- Making mypy blocking (typing debt unquantified; separate feature once measured).
- Reviving semgrep, tfsec, LocalStack, mutmut (orphaned per validator-inventory.md;
  separate decisions).
- Any change to deploy.yml or branch-protection settings themselves in Phase 1
  authoring (branch protection flip is an implementation-phase owner action, FR-007b).
- Touching the local developer workflow beyond the bandit rev bump and trivy
  exit-code fix — the autostage wrapper stays for local use.

## Constraints

- No new AWS resources (standing constraint — this is pure CI/config, compliant).
- GPG-signed commits.
- This feature authors specs only; workflow YAML edits happen in Phase 3.

---

## Adversarial Review #1 (spec attack)

**AR1-F1 (CRITICAL → resolved): The gate could be born permared.** If
`pre-commit run --all-files` fails on current main (likely candidates: bandit 1.9.4
new checks vs code written under 1.7.10, checkov baseline drift, trivy findings
newly able to fail after FR-006), the required check blocks ALL PRs including the
fix PR. *Resolution*: FR-007 mandates baseline-clean-first sequencing; tasks.md
T001 runs the full suite against main and remediates/baselines BEFORE the job is
added; the required-check flip is a separate, later step. **Gate impact: prevents
the exact failure mode that historically produces `|| true`.**

**AR1-F2 (HIGH → resolved): Open PRs break when the check becomes required.** Any
PR branched before the gate will not have run the job; marking it required blocks
merges until rebase. *Resolution*: FR-007's two-step landing — the job runs on all
PRs immediately (pull_request trigger evaluates merge result against the new
workflow on base), but "required" status is flipped only after in-flight PRs are
audited (plan.md Migration). With this repo's PR velocity (squash-merge, short-lived
branches) the exposure window is days, not weeks.

**AR1-F3 (HIGH → resolved): The ignore list is a security-theater loophole.**
Someone ignores a real, actionable CVE to unblock a Friday deploy and it never gets
revisited. *Resolution*: FR-004's expiry enforcement makes every ignore a ticking
failure — CI goes red when it lapses, so forgetting is impossible; justification
lives in a tracked file so every addition is a visible PR diff line subject to
normal review; 90-day cap bounds exposure. Residual risk: a reviewer rubber-stamps
a bad justification — that is a people problem no YAML fixes, and it is still
strictly better than today's blanket `|| true` (which is an ignore-everything list
with no expiry and no justification).

**AR1-F4 (MEDIUM → resolved): File-modifying hooks in a blocking CI gate.**
trailing-whitespace, end-of-file-fixer, ruff --fix, ruff-format, terraform_fmt all
mutate files. In CI this is safe: the runner never pushes, so no loop is possible;
a mutation simply exits nonzero and `--show-diff-on-failure` (FR-001) shows the
contributor exactly what to fix. The ONLY dangerous one is the detect-secrets
autostage wrapper (it runs `git add` and retries until stable — in CI that could
mask churn or behave unpredictably on a detached HEAD), and FR-002 skips it in
favor of the non-mutating `detect-secrets-hook` entrypoint.

**AR1-F5 (MEDIUM → resolved): Does the job slow every PR unacceptably?** The suite
adds ruff (~s), bandit (~10s), checkov (~30-60s), trivy (~20s incl. install),
detect-secrets (~10s) plus env setup. With FR-008's cache, steady-state ≈ 2-4 min.
It runs PARALLEL to the test job (pytest+coverage, historically the long pole) and
playwright-e2e (20-min timeout), so marginal wall-clock is ~zero. Unacceptable
slowdown would require this job to exceed the current slowest job; it will not.

**AR1-F6 (LOW): Redundant scanning.** ruff `--select S` (flake8-bandit) already
gates in CI and overlaps bandit; gitleaks overlaps detect-secrets. Accepted:
overlap is cheap, the tools' rule sets are not identical, and FR-002 already trims
the literal duplicate (gitleaks-in-pre-commit).

**AR1-F7 (LOW): pre-commit 4.x deprecates the `commit` stage name.** The config
uses legacy `default_stages: [commit]` / `stages: [commit]`; pre-commit 4.6.0 maps
them with a warning. Cosmetic; may be modernized opportunistically during
implementation, not a gate condition.

### Gate

- CRITICAL: 0 open (F1 resolved by FR-007 sequencing + T001)
- HIGH: 0 open (F2 two-step landing; F3 expiry-enforced ignores)
- MEDIUM: 0 open (F4 skip-wrapper; F5 cache + parallelism)
- LOW: 2 documented (F6 overlap, F7 stage naming)

**AR#1 GATE: PASS (0 CRITICAL / 0 HIGH open).**
