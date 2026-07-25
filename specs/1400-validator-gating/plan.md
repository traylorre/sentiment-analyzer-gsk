# Implementation Plan: 1400-validator-gating

**Spec**: specs/1400-validator-gating/spec.md
**Phase**: authoring only — no workflow YAML edits until Phase 3.

## Design Overview

Three edits, one new script, one new tracked ignore file:

1. New `pre-commit` job in `.github/workflows/pr-checks.yml`.
2. `security` job (pip-audit) made blocking via a wrapper script + curated ignore file.
3. Version/config pin fixes: bandit rev, trivy exit code.

## 1. The pre-commit CI job

```yaml
# JOB: Pre-commit (validator gate — Feature 1400)
pre-commit:
  name: Pre-commit Hooks
  runs-on: ubuntu-latest
  permissions:
    contents: read
  steps:
    - uses: actions/checkout@v7
    - uses: actions/setup-python@v7
      with:
        python-version: '3.13'
        cache: 'pip'
    - name: Install system-hook dependencies
      run: |
        pip install pre-commit==4.6.0 checkov==<pin>   # checkov is language: system
        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
          | sh -s -- -b /usr/local/bin v<pin>          # trivy is language: system
    - name: Cache pre-commit environments
      uses: actions/cache@v4
      with:
        path: ~/.cache/pre-commit
        key: pre-commit-${{ hashFiles('.pre-commit-config.yaml') }}
    - name: Run pre-commit (blocking)
      env:
        # detect-secrets: autostage wrapper mutates+git-adds baseline — local-only
        #   workflow (see CLAUDE.md pre-commit ordering). CI runs the non-mutating
        #   detect-secrets-hook below instead.
        # gitleaks: dedicated blocking CI job already exists (secrets-scan).
        SKIP: detect-secrets,gitleaks
      run: pre-commit run --all-files --show-diff-on-failure
    - name: Detect secrets (non-mutating, blocking)
      run: |
        pip install detect-secrets==<pin from requirements-dev.txt>
        git ls-files -z | xargs -0 detect-secrets-hook --baseline .secrets.baseline
```

Manual job over `pre-commit/action`: that action is in maintenance mode and adds
nothing over the four lines above; manual keeps the SKIP list and system-tool
installs explicit.

### Hook triage — CI-blocking vs local-only

| Hook | In CI gate? | Why |
|---|---|---|
| trailing-whitespace, end-of-file-fixer, check-* | YES | File-modifying ones fail-with-diff in CI (runner never pushes → no loop possible) |
| ruff, ruff-format | YES | Redundant with lint job but free; keeps "CI runs exactly what local runs" true |
| terraform_fmt | YES | Same |
| detect-secrets (autostage wrapper) | NO — SKIP | Wrapper does `git add` + retry-until-stable; a mutating retry loop is a local-workflow tool. CI substitute: `detect-secrets-hook` (read-only, exits 1 on new secrets, ignores line-number churn) |
| gitleaks | NO — SKIP | Already a dedicated blocking job (pr-checks.yml:218) |
| bandit | YES | The headline dark validator; rev pinned per §3 |
| trivy-terraform | YES | After FR-006 flips `--exit-code 0` → `1`; needs trivy on runner |
| checkov-terraform | YES | Baseline-aware already (`.checkov.baseline` at repo root); needs checkov on runner. NOTE: local venv/pyenv hcl2 gotcha does not apply in CI (clean python 3.13) |
| pytest, check-branch-collision, check-error-log-assertions | AUTO-EXCLUDED | `stages: [push]` + `default_stages: [commit]` → `run --all-files` never invokes them; pytest already has its own CI job |
| check-false-pass-patterns | YES | commit-stage script hook, read-only. CAVEAT: entry uses `--staged-only`; in CI nothing is staged. Verify script behavior on empty staged set (T003); if it no-ops, acceptable (it still gates local commits) — do NOT silently believe it scanned |
| mypy | NO | `stages: [manual]` — stays manual. Blocking mypy is a separate feature after typing debt is measured |

## 2. pip-audit: blocking with curated ignores (the crux)

Why it got `|| true` in the first place: pip-audit surfaces advisories in pinned
transitive deps with no upstream fix. Blocking on those = permared = someone
re-adds `|| true` within a week. A gate that's too noisy gets disabled — so the
design goal is *sustainable* blocking, not maximal blocking.

Mechanism — `scripts/pip-audit-gate.sh` + tracked `.pip-audit-ignore`:

```
# .pip-audit-ignore — every line: VULN_ID  EXPIRY(YYYY-MM-DD)  justification
# Max lifetime 90 days. Expired entry = CI failure. Renewal = new commit = PR-reviewable diff.
# Example:
# GHSA-xxxx-yyyy-zzzz  2026-10-01  transitive via botocore; no fixed release; not reachable (we never call X)
```

Script behavior:
1. Parse file; **fail immediately** if any entry's expiry < today (SC-004) or is
   malformed / missing justification.
2. Build `--ignore-vuln ID` flags; run
   `pip-audit -r requirements.txt --strict` and `-r requirements-dev.txt`
   with them. No `|| true`. Job drops `continue-on-error`.
3. Keep the JSON artifact upload (audit trail unchanged).

Why not `--fix`/Dependabot-only: Dependabot already exists; this gate catches the
window between advisory publication and Dependabot PR merge, and catches manual
pin edits Dependabot never sees.

Why expiry beats a standing allowlist: today's `|| true` IS an allowlist of
everything, forever, with no justification. Every property of the ignore file
(named IDs, dated, justified, reviewed, auto-expiring) is a strict improvement.
The expiry check makes forgetting structurally impossible — the list cannot rot
silently, it goes red.

Seeding: T002 runs pip-audit against current requirements to enumerate today's
advisories; each becomes either (a) an upgrade in this feature's implementation,
or (b) a seeded ignore entry with justification. The gate lands with a clean run.

## 3. Version pins

- `.pre-commit-config.yaml` bandit rev: `1.7.10` → `1.9.4` (match
  requirements-{dev,ci}.txt). Contingency: if 1.9.4 fires new findings on current
  `src/`, fix them (preferred) or `# nosec` with justification per SAST policy —
  never downgrade the pin to dodge findings.
- `pyproject.toml:54` dev extra: `bandit>=1.7.0` → `bandit==1.9.4` (or `>=1.9.4,<2`).
- Local venv drift (1.9.2 installed vs 1.9.4 pinned) self-heals via
  `pip install -r requirements-dev.txt`; note in PR description, no code change.
- trivy hook: `--exit-code 0` → `--exit-code 1` (severity HIGH,CRITICAL unchanged).
- New pins introduced by this feature (trivy binary, checkov in CI step) are exact
  versions, recorded in the workflow file.

## 4. Rollout / migration (avoids permared + open-PR breakage)

1. **Pre-clean main** (T001): run the full CI-shaped suite locally against main;
   remediate or baseline every finding. The job must be born green.
2. **Land the job non-required**: it runs and reports on all PRs immediately.
3. **Red-team proof** (T006): throwaway branch plants bandit HIGH + synthetic
   secret + vulnerable pin; confirm all three FAIL; close unmerged.
4. **Observe** N green runs on main + in-flight PRs rebased/merged.
5. **Flip to required status check** (owner action, branch-protection UI) — the
   only step outside the repo.

## Constitution / standing-constraint check

- No new AWS resources: compliant (CI config + scripts only).
- No production code paths touched.
- GPG-signed commits throughout.

---

## Adversarial Review #2 (plan attack, spec↔plan drift)

**AR2-F1 (HIGH → resolved): `detect-secrets-hook` false-fails on baseline
line-number drift?** The known churn problem is `detect-secrets scan` *updating*
line numbers in the baseline; the `detect-secrets-hook` entrypoint compares
secrets (hash-based) against the baseline and does not fail on line drift — this
is precisely why it's the upstream-recommended CI form. Risk if wrong: permared.
*Mitigation*: T003 empirically verifies hook behavior against the current baseline
before the job lands; if it proves noisy, fallback is `detect-secrets scan
--baseline` + `git diff --exit-code` on secret-hash lines only. Elevated to AR#3.

**AR2-F2 (HIGH → resolved): checkov/trivy in CI may disagree with local runs.**
The `.checkov.baseline` was generated by some local checkov version; CI's pinned
checkov could report baseline-format or new-check drift, and trivy's DB updates
daily (a scan green Monday can be red Wednesday with zero repo changes — a
"spurious" failure mode distinct from flaky). *Resolution*: pin checkov to the
version that generated the baseline (or regen baseline at the pinned version in
T001); accept trivy DB-drift as a FEATURE (new CVEs should surface) but scope it
via existing severity filter HIGH,CRITICAL; document the "red without a diff"
runbook line in the workflow comment. Elevated to AR#3 as residual.

**AR2-F3 (MEDIUM → resolved): `--staged-only` hook silently no-ops in CI**
(nothing staged). Honest accounting: check-false-pass-patterns may contribute zero
CI coverage. T003 verifies; if no-op, add a comment in the workflow admitting it
gates locally only — do not claim coverage that doesn't exist (this feature IS the
honesty fix; lying inside it would be poetic failure).

**AR2-F4 (MEDIUM → resolved): pip-audit `--strict` semantics.** `--strict` makes
dependency-resolution errors fatal too, which can fail on packages without wheels
for the runner platform. If that bites, drop `--strict` and rely on default
exit-1-on-vuln behavior — the gate property (SC-003) survives without it.

**AR2-F5 (LOW): ignore-file parser is new bash.** Keep it <40 lines, no cleverness,
covered by a trivial planted-expiry test in T006 (SC-004 proof doubles as the
parser test).

**Spec↔plan drift**: none found — every FR maps to a plan section (FR-001→§1,
FR-002→triage table, FR-003→job deps step, FR-004→§2, FR-005/006→§3,
FR-007→§4, FR-008→cache step).

**AR#2 GATE: PASS. Drift: none. Elevated to AR#3: (AR2-F1) detect-secrets-hook
behavior unverified, (AR2-F2) trivy DB-drift red-without-a-diff.**
