# Validator Inventory, sentiment-analyzer-gsk

Sourced from the validators domain (reconciled findings, all CONFIRMED). "Runs today?" = server-side (GitHub Actions) enforcement reality, since no workflow ever runs `pre-commit run` or `make` (`grep -rn 'pre-commit' .github/workflows/` → none; only `make` ref is a comment at pr-checks.yml:13).

## Enforced in CI (gates a merge)

| Validator | Declared | Wired into | Runs today? | Activation cost |
|---|---|---|---|---|
| ruff-format | Makefile:56-61; pre-commit:53-58 | pr-checks.yml:57-59 lint job | Yes, blocking | None (live). Drift to fix: CI installs ruff==0.8.4, dev/CI reqs pin 0.15.7 |
| ruff-check (lint incl. flake8-bandit `S`) | Makefile:63-66; pre-commit:56-57; pyproject:74-91 | pr-checks.yml:61-65 | Yes, blocking | None |
| gitleaks | pre-commit:88-92; .gitleaks.toml | pr-checks.yml:218-235 secrets-scan job | Yes, blocking (the sole CI-enforced secret scanner) | None |
| pytest unit + 80% coverage gate | Makefile:108-109; pre-commit:126-133; pyproject:216-218 | pr-checks.yml:95-112; deploy.yml:451 | Yes, blocking (`coverage report --fail-under=80`) | None |
| Hypothesis property tests | tests/property/; requirements-ci.txt:69 | pr-checks.yml:96-105 (tests/property NOT in --ignore) | Yes, runs transitively via pytest collection | None |
| Playwright E2E | pr-checks.yml:285-346; deploy.yml:1556-1606; nightly-e2e.yml:60-68 | 3 workflows (PR tier / preprod sanity / nightly external-api) | Yes, PR tier blocking (deploy sanity non-blocking, nightly cron) | None. Nightly cron self-disables after 60d inactivity (runtime state) |

## Runs in CI but advisory (cannot gate a merge)

| Validator | Declared | Wired into | Runs today? | Activation cost |
|---|---|---|---|---|
| pip-audit | Makefile:68-69 | pr-checks.yml:136-177 security job | Yes, non-blocking (`\|\| true` + `continue-on-error: true`) | Low: remove `\|\| true` and `continue-on-error` to gate |

## Wired only locally, DARK in CI (never runs server-side)

| Validator | Declared | Wired into | Runs today? | Activation cost |
|---|---|---|---|---|
| bandit | pre-commit:96-101; Makefile:73-93; pyproject:208-214 | pre-commit + `make sast` only | Local commits only (pinned 1.9.4 in reqs; pre-commit rev 1.7.10, version drift) | Low: add `pre-commit run --all-files` CI job |
| detect-secrets | pre-commit:76-86; wrapper scripts/detect-secrets-autostage.sh; .secrets.baseline | local pre-commit wrapper only | Local commits only (gitleaks gives overlapping CI coverage) | Low: add pre-commit CI job |
| mypy | pre-commit:136-143 (`stages: [manual]`); pyproject:129-137; reqs pin 1.19.1 | pre-commit manual stage only | No, manual stage never auto-fires (install types = pre-commit,pre-push) | Low-med: drop `manual` stage or add CI step |
| trivy (IaC, replaced tfsec) | pre-commit:104-112 | local pre-commit only | Local only, and non-blocking there (`--exit-code 0`) | Med: add CI job + set `--exit-code 1` |
| checkov (IaC, baselined) | pre-commit:116-121; .checkov.baseline | local pre-commit only | Local commits only | Low: add pre-commit CI job |

## Orphaned, cannot run anywhere today

| Validator | Declared | Wired into | Runs today? | Activation cost |
|---|---|---|---|---|
| semgrep | pyproject:55 (dev extra only) | `make sast` (command-guarded) | No, not installed, absent from CI, `make sast` silently skips it | High: pin + install + wire CI |
| tfsec | Makefile:68-71 (removed from pre-commit:67-69) | `make security` only, soft-fail | No, no workflow runs `make security` | Deprecated (no TF1.5 check-block support); superseded by trivy, likely delete |
| LocalStack integration tests | Makefile:111-113; tests/integration/conftest.py:39-58 | `make test-integration` only | No, deploy.yml integration job runs preprod against REAL AWS, not LocalStack; no `localstack` ref in any workflow | Med-high: stand up LocalStack service in a CI job |
| mutmut (mutation testing) | Makefile:135-141 | command-guarded make target | No, no config, no reqs pin, no CI/pre-commit wiring | High: add config + pin + CI job |

## Highest-leverage activation

One CI job, `pre-commit run --all-files` (the commented-out block at .pre-commit-config.yaml:179-184), pulls bandit, detect-secrets, trivy, checkov, and staged mypy under server-side enforcement in a single step. Today CI enforcement is limited to jobs that invoke tools directly: ruff, gitleaks, pytest+coverage, Playwright, and non-blocking pip-audit.
