# Quickstart: Verification Runbook — Semgrep Gating

**Feature**: 001-semgrep-gating | **Date**: 2026-07-29

Run from repo root with `.venv` activated. Order matters (clean-tree checks before plant tests).

## 1. Fresh-provision check (SC-005)

```bash
python3.13 -m venv /tmp/fresh-provision-check
/tmp/fresh-provision-check/bin/pip install -r requirements-dev.txt -q
/tmp/fresh-provision-check/bin/semgrep --version   # expect: 1.172.0
rm -rf /tmp/fresh-provision-check
```

Both surfaces agree: `grep semgrep requirements-dev.txt pyproject.toml` → `==1.172.0` in both, no floating spec remains.

## 2. Clean-tree pass (SC-001, FR-006)

```bash
make sast; echo "exit: $?"
```

Expect: exit 0; bandit section unchanged; semgrep section shows rule/file counts (e.g., "Ran N rules on M files"); no `✗` lines. Runtime well under the constitution's 60s ceiling (~15-20s; registry fetch dominates).

## 3. Plant test (SC-002)

```bash
cat > src/_sast_plant_test.py <<'EOF'
import subprocess
def run(cmd):
    subprocess.call(cmd, shell=True)  # gate-severity pattern (subprocess-shell-true family)
EOF
make sast; echo "exit: $?"    # expect nonzero, rule id named in output
rm src/_sast_plant_test.py
make sast; echo "exit: $?"    # expect 0 again
```

If the registry's rule set that day doesn't flag this pattern at gate severity, substitute any current ERROR-severity pattern — the criterion is "a planted gate-severity finding fails the target", not one specific rule.

## 4. Missing-binary fail-fast (SC-003)

```bash
SHADOW=$(mktemp -d)
for tool in git make bash sh grep sed python3 bandit pip-audit ruff terraform; do
  p=$(command -v $tool) && ln -s "$p" "$SHADOW/"; done
time PATH="$SHADOW" make sast; echo "exit: $?"
rm -rf "$SHADOW"
```

Expect: nonzero exit in ~10s total — the frozen bandit step runs first and consumes ~4-5s of that (AR#2 F4); the missing-scanner detection itself is instant (<5s per SC-003). Output contains "Semgrep not installed. Install: pip install -r requirements-dev.txt"; NOT a silent skip, NOT "✓ SAST scan complete".

## 5. No-swallow sweep (SC-004, FR-007)

```bash
sed -n '/Running Semgrep/,/SAST scan complete/p' Makefile
```

Expect in the semgrep lines: zero `|| true`, zero `|| echo`, zero `2>/dev/null` on the scan invocation, no if/else skip shape. The `command -v` guard present must end in `exit 1`, not a skip.

```bash
git diff main -- Makefile
```

Expect: hunks touch only the semgrep block; bandit lines byte-identical.

## 6. Suppression justification (SC-006)

```bash
grep -rn nosemgrep --include=Dockerfile --include='*.py' --include=Makefile .
git diff main -- src/lambdas/analysis/Dockerfile src/lambdas/dashboard/Dockerfile
```

Expect: exactly 3 grep hits on code surfaces — analysis + dashboard Dockerfiles (markers on own lines immediately ABOVE the CMDs; same-line comments corrupt CMD — AR#2 F1) plus sentiment.py (marker ABOVE the `with tarfile.open` line; the rule ignores `filter="data"` — AR#3 F2). An unconstrained repo-wide grep also hits this feature's own spec artifacts and archived 070 docs (13 pre-existing hits), which is why the check is constrained (AR#2 F3). Each hit has adjacent justification. The Dockerfile diff shows ONLY added comment lines; CMD lines byte-identical. (Command must behave under both GNU grep and the owner's ugrep wrapper.)

## 7. Extraction fix + unit test (R5b, constitution accompaniment)

```bash
grep -n 'filter="data"' src/lambdas/analysis/sentiment.py   # expect: line ~118
pytest tests/unit/test_sentiment.py -v                       # all green incl. new extraction test(s)
pytest tests/unit/ -q                                        # full suite green
```

Re-scan check: `make sast` (step 2) passing on the post-fix tree confirms the R5b fix + suppression rider landed correctly (the rule ignores `filter="data"`, so the ABOVE-the-with-line nosemgrep is required — AR#3 F2; step 6's expected count of 3 already includes it).

## 8. Board card (FR-009)

```bash
python3 - <<'EOF'
import json, re
html = open('CLEANUP-BOARD.html').read()
i = html.index('const CARDS')
start = html.index('[', i)
cards, _ = json.JSONDecoder().raw_decode(html[start:])
card = next(c for c in cards if 'Orphaned validators' in c['title'])
print('lane:', card['lane'])
print('evidence has dated semgrep close:', '2026-' in card['evidence'] and 'semgrep' in card['evidence'].lower())
print('next_action:', card['next_action'])
EOF
```

Expect: lane unchanged; evidence contains the dated semgrep-portion close; next_action shows the venv-done/CI-deferred split with LocalStack/mutmut still open.

## Ruff churn reminder

After any `make validate` run during verification: `git checkout -- src tests` to discard the ~68-file reflow from the venv/CI ruff skew. Never `git add -A`. (Standing landmine until the ruff bump-forward feature lands.)
