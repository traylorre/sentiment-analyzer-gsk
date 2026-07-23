# Validator Inventory

Sign-post for every declared validator on branch `Q-pin-hcl2`: where it's declared, where (if anywhere) it's wired, whether it fires today, and what activation would cost. Terrain map only, no fixes recommended.

## Validators

| Validator | Declared (file:line) | Wired into (make/pre-commit/CI file:line) | Runs today? | Activation cost |
|---|---|---|---|---|
| ruff format | `pyproject.toml:70` `[tool.ruff]` | pre-commit `.pre-commit-config.yaml:58` (`ruff-format`, rev v0.8.4 `:53-54`, default_stages=[commit] `:31`); CI `pr-checks.yml:57,59` (`ruff format --check --diff src/ tests/`, ruff==0.8.4 `:55`); Makefile `:57` fmt, `:60-61` fmt-check, validate→fmt `:42` | **LIVE** (pre-commit + CI) | Already active |
| ruff lint (incl. `--select S`) | `pyproject.toml:74` `[tool.ruff.lint]`; select `S` at `:83` | pre-commit `.pre-commit-config.yaml:56-57` (`ruff --fix`, rev v0.8.4); CI `pr-checks.yml:62` (`ruff check src/ tests/`), `:65` (`ruff check src/ --select S --output-format=github`); Makefile `:64` | **LIVE** (pre-commit + CI) | Already active |
| bandit | `pyproject.toml:208` `[tool.bandit]`; `pyproject.toml:54` `bandit>=1.7.0` | pre-commit `.pre-commit-config.yaml:99` (`-c pyproject.toml -ll -r src/`, rev 1.7.10 `:96-97`); Makefile `:75` sast, `:91` audit-pragma. **No CI step** (`grep bandit .github/workflows/` → none). Binary present in CI via `requirements-ci.txt:59` (bandit==1.9.4) but never invoked | **LIVE** (pre-commit) / **ORPHANED** (CI) | Add CI step `bandit -c pyproject.toml -r src/ -ll`, binary already installed, zero new deps |
| semgrep | `pyproject.toml:55` `semgrep>=1.50.0` (`[dev]` only) | Makefile `:73-84` sast, guarded by `command -v semgrep` `:78`, else skip msg `:82`. **No pre-commit, no CI, not in requirements-ci/dev** (`grep` → none). `pr-checks.yml:13` is a comment only. CI installs `requirements-ci.txt`+`pip install -e .` (no `[dev]`) → binary absent | **ORPHANED** (CI-dark + commit-dark) | Add semgrep to `requirements-ci.txt` + CI step (`semgrep scan --config auto --error src/`) or `make sast`. Fires today only if a human runs `make sast` with semgrep hand-installed |
| mypy | `pyproject.toml:129` `[tool.mypy]` | pre-commit `.pre-commit-config.yaml:136` local hook, **`stages: [manual]`** `:143` (excluded from commit/push). **No CI** (`grep mypy .github/workflows/` → none). Installed via `requirements-ci.txt:62` / `requirements-dev.txt:41` (mypy==1.19.1) | **ORPHANED** (manual-only) | Change `stages:[manual]`→`[push]` at `.pre-commit-config.yaml:143` and/or add CI `python -m mypy src/ --ignore-missing-imports`, binary already installed |
| gitleaks | pre-commit repo `gitleaks/gitleaks-action` rev v8.18.0 `.pre-commit-config.yaml:89-90` | pre-commit `:92` (default_stages=[commit] `:31`); CI secrets-scan job `pr-checks.yml:218`, fetch-depth:0 `:230`, `gitleaks/gitleaks-action@v2` `:233`; triggers push/PR/schedule `:18-26` | **LIVE** (pre-commit + CI) | Already active |
| detect-secrets | local wrapper `.pre-commit-config.yaml:78-86` (`./scripts/detect-secrets-autostage.sh`, excludes tests/ + baseline) | pre-commit only (default_stages=[commit]). **No CI** (`grep detect-secrets .github/workflows/` → none); not pinned in any `requirements*.txt` | **LIVE** (pre-commit) / **ORPHANED** (CI) | Add CI step `pip install detect-secrets && detect-secrets scan --baseline .secrets.baseline` |
| trivy (IaC) | local hook `.pre-commit-config.yaml:107-112` (`trivy config --exit-code 0 --severity HIGH,CRITICAL ... infrastructure/terraform/`, language:system, files `\.tf$`) | pre-commit only, **`--exit-code 0` = report-only, never blocks**. **No CI** (`grep trivy .github/workflows/` → none). System binary, no auto-install | **LIVE-but-nonblocking** (pre-commit) / **ORPHANED** (CI) | Runs only if trivy on committer machine. Real gate: add `aquasecurity/trivy-action` with `--exit-code 1` to CI |
| checkov (IaC) | local hook `.pre-commit-config.yaml:116-121` (`checkov --quiet --compact --framework terraform --baseline .checkov.baseline -d infrastructure/terraform/`, language:system, files `\.tf$`) | pre-commit only. **No CI** (`grep checkov .github/workflows/` → none). System binary, not a pip dep; requires `.checkov.baseline` at repo root | **LIVE** (pre-commit) / **ORPHANED** (CI) | Runs only if checkov on committer machine. CI gate: add checkov-action or `pip install` + run step |
| pytest unit (80% cov gate) | `pyproject.toml:141` testpaths=["tests"]; `:218` fail_under=80 | pre-commit `.pre-commit-config.yaml:126,128` (`pytest tests/unit -x --tb=short -q`, **stages:[push]** `:133`); CI test job `pr-checks.yml:92-93` install, `:97-104` pytest w/ --ignore list, `:112` `coverage report --fail-under=80`; Makefile `:108-109` | **LIVE** (pre-commit push + CI) | Already active |
| LocalStack integration suite | `tests/integration/conftest.py:39` LOCALSTACK_ENDPOINT (http://localhost:4566); Makefile `:111-112` test-integration→localstack-up, `:149-168` up/wait | Makefile target only. **Not in any CI** (`grep -i localstack .github/workflows/` → none). CI test job collects non-preprod `tests/integration/*.py` with **no LocalStack running** (`pr-checks.yml:97-104`). `deploy.yml` runs preprod integration vs REAL AWS (`~:1499`, `-m preprod`) | **ORPHANED** (CI, LocalStack path) | Add a localstack service container + `make test-integration` to a workflow. *(OPEN: exact count of the 22 integration files that bind LocalStack fixtures vs pure-moto, needs per-file read)* |
| Playwright E2E (customer frontend) | `frontend/playwright.config.ts` (exists); 36 `*.spec.ts` files under `frontend/tests/e2e` | CI on-PR `pr-checks.yml:285` playwright-e2e (npm ci `:313`, install chromium `:316`, run `:323-328` with `--grep-invert "@external-api"`); nightly `nightly-e2e.yml:29` external-api-e2e, cron `:19`, `--grep "@external-api"` `:64`, API-key secrets `:71-72` | **LIVE** (on-PR job source-provably active) | Already active. *(OPEN: nightly schedule status, GitHub auto-disables scheduled workflows after 60d inactivity per `nightly-e2e.yml:10-13`; not source-provable, needs `gh api .../actions/workflows` run history)* |
| **mutmut (mutation)** | Makefile `:135-141` test-mutation (guarded stub only) | Guarded by `command -v mutmut` `:137`, else install hint `:140`. See KNOWN-DARK below | **DELETE-CANDIDATE** (never executed) | See below, 3 missing pieces |
| **hypothesis / tests/property** | `requirements-ci.txt:69` hypothesis==6.151.9; `requirements-dev.txt:47` >=6.0.0; `tests/property/*.py` import `@given/@settings` | Swept into CI test job via testpaths (see KNOWN-DARK below) | **LIVE** (incidental, via `testpaths`), the "never runs" conclusion is **REFUTED** for CI | Already runs in CI; see below for the nuance |

## KNOWN-DARK callouts

### mutmut: genuinely never executed (DELETE-CANDIDATE)

**Proof of absence** (all re-verified this run):
- Only reference in the repo is the guarded Makefile stub: `Makefile:135` (`test-mutation`), `:137` (`if command -v mutmut`), `:138`, `:140` (install hint). Runs nothing unless mutmut is already on PATH.
- `grep -rn mutmut requirements*.txt pyproject.toml setup.cfg .pre-commit-config.yaml Makefile .github/workflows/` → **only** Makefile lines 135/137/138/140.
- `ls .mutmut setup.cfg .mutmut.ini` → none exist (no config).
- `grep mutmut .github/workflows/` → none (no CI reference).

**Activation cost, three absent pieces, all required:**
1. Pin `mutmut` in `requirements-dev.txt`.
2. Add `[tool.mutmut]` / `setup.cfg` config.
3. Add a CI/nightly `mutmut run` job.

All three are missing, so the target is inert. (spec refs specs/058, specs/084 are non-evidence and were not relied on.)

### hypothesis / tests/property: "never runs" is REFUTED for CI

The claim splits: the *no-explicit-reference* half is **true**, but the *never-runs conclusion* is **FALSE**, the property tests are collected and executed by the CI test job.

**Absence half (true):**
- `grep property Makefile .github/workflows/` → none. No dedicated make/CI target.
- `grep collect_ignore | norecursedirs` → none. No skip config.
- `grep pytest.mark.skip tests/property/` → none (only `@given/@settings`).

**Why it nonetheless RUNS in CI:**
- `pyproject.toml:141` testpaths=["tests"].
- CI test job (`pr-checks.yml:97-104`) ignores **only** preprod files + `tests/integration/timeseries` + `tests/e2e`, `tests/property` is **not** ignored.
- CI runs bare `pytest` with no `-m` deselect → `tests/property/*.py` (e.g. `test_api_contracts.py:9`, `test_infrastructure.py:9`, `test_lambda_handlers.py`) is swept into the unit run and executes.

**Where it genuinely does NOT run:** the pre-commit push hook, scoped to `tests/unit` (`.pre-commit-config.yaml:128`). No dedicated property target exists.

**Activation cost (for a hardened isolated run, not basic execution):** add a dedicated `pytest tests/property` step/target with higher example counts + separate reporting. Basic execution already happens in CI.
