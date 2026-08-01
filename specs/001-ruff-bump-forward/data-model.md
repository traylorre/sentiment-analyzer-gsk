# Data Model: Ruff Bump-Forward

**Date**: 2026-07-29 | **Feature**: [spec.md](spec.md)

No runtime data stores are touched. The feature's "entities" are configuration surfaces and their invariants. Line numbers are as of 2026-07-29 (branch base 01d13d5) and re-verified at implementation time.

## Entity: Pin Surface

Invariant: all rows agree on 0.15.14 after this feature; `required-version` enforces at runtime.

| # | Surface | Before | After | Verification |
|---|---------|--------|-------|--------------|
| 1 | `requirements-dev.txt:36` | `ruff==0.15.14` | unchanged (verify) | grep |
| 2 | `pyproject.toml:46` dev extra | `"ruff>=0.8.0",` | `"ruff==0.15.14",` | grep |
| 3 | `.github/workflows/pr-checks.yml:55` | `pip install ruff==0.8.4` | `pip install ruff==0.15.14` | grep + CI lint job green |
| 4 | `.pre-commit-config.yaml:54` | `rev: v0.8.4` | `rev: v0.15.14` | `pre-commit run --all-files` |
| 5 | `requirements-ci.txt:57` | `ruff==0.15.14` | unchanged (verify) | grep |
| — | `pyproject.toml [tool.ruff]` | (absent) | `required-version = "==0.15.14"` | wrong-version binary exits 2 |

## Entity: Drift Channel

Invariant: no automated mechanism can move any pin surface independently.

| Channel | Location | Closure | Verification |
|---------|----------|---------|--------------|
| Dependabot code-quality group | `.github/dependabot.yml:32` (pip), group at :71 | `ignore` entry for `ruff`, all update types, rationale comment | YAML review; next dependabot cycle opens no ruff PR |
| autoupdate runbook | `.pre-commit-config.yaml:17-19` header | Rewritten: points to multi-surface pinned-upgrade procedure, no bare `pre-commit autoupdate` | text review |
| Legacy script hook | `scripts/pre-commit` (self-installs, unpinned ruff + auto-black) | File deleted; ALL README.md black references rewritten (lines 7 badge, 616, 694, 726, 768, 984) | file absent; `grep -n black README.md` shows no workflow instruction or badge |
| In-flight dependabot PR | #971 (ruff 0.16.0 + pre-commit 4.6.1; successor of #902, closed unmerged 2026-07-27; automerge-eligible) | Closed with comment citing this feature, FIRST implementation action | `gh pr view 971` state CLOSED; surfaces 1/5 still read 0.15.14 |

## Entity: Hook Definition

| Field | Before | After |
|-------|--------|-------|
| repo | astral-sh/ruff-pre-commit | unchanged |
| rev | `v0.8.4` | `v0.15.14` (verified tag, sha `0c7b6c98`) |
| hook 1 id | `ruff` (legacy alias at new rev) | `ruff-check` |
| hook 1 args | `[--fix]` | unchanged |
| hook 2 id | `ruff-format` | unchanged |

## Entity: Reformat Set

- Scope: `src/`, `tests/` (69 files measured 2026-07-29; regenerate at implementation time under pinned binary).
- The 15 tracked `.py` files outside src/tests (scripts/, interview/) verified already conformant under 0.15.14; re-verify, include if shifted (CI pre-commit job reaches them).
- Property: `git diff` post-format contains formatting-only hunks; unit suite green before == after.

## Entity: Triage Ledger (UP042 suppressions)

Disposition for all 7: `# noqa: UP042` rider + one-line justification; NO StrEnum conversion (unsafe autofix: changes `str()` semantics of DynamoDB/JSON-serialized members).

| Enum | Location |
|------|----------|
| `Resolution` | `src/lib/timeseries/models.py:17` |
| `SentimentSource` | `src/lambdas/analysis/sentiment.py:353` |
| `SentimentLabel` | `src/lambdas/analysis/sentiment.py:361` |
| `AuthErrorCode` | `src/lambdas/shared/errors/auth_errors.py:20` |
| `AuthType` | `src/lambdas/shared/middleware/auth_middleware.py:27` |
| `TimeRange` | `src/lambdas/shared/models/ohlc.py:16` |
| `OHLCResolution` | `src/lambdas/shared/models/ohlc.py:36` |

Companion artifacts: a `CLEANUP-BOARD.html` kanban card recording root cause "unsafe autofix vs behavior-neutrality" and proposed fix "StrEnum migration feature with serialization test sweep". Plus FR-014 lock-test module in `tests/unit/` asserting `str(member)` == `"ClassName.MEMBER"` and `.value` == wire string for all 7 (verified semantics on repo Python 3.13.0; none of the 7 defines `__str__`/`__format__`).

## Entity: Makefile Target (audit-pragma)

| Field | Before | After |
|-------|--------|-------|
| RUF100 line | `ruff check --select RUF100 src/ tests/` | `ruff check --extend-select RUF100 src/ tests/` |
| Failure mode fixed | `--select` replaces config select → 14 false "unused noqa" | RUF100 evaluated against full configured rule set |
| Bandit half | `bandit -r src/ --ignore-nosec ...` | byte-identical |

## State Transitions

Single atomic commit; no intermediate states permitted (required-version bricks stale binaries the moment it lands):

```text
[base 01d13d5-equivalent] → (venv upgrade, uncommitted) → [one commit: pins + enforcement +
reformat + noqas + channel closures + Makefile/README/dependabot + hook deletion] → gates green
```
