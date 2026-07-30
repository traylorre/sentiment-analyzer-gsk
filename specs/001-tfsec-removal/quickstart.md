# Quickstart: Verify tfsec Removal

**Feature**: 001-tfsec-removal

## Prerequisites

```bash
source .venv/bin/activate   # standing repo requirement
git checkout 001-tfsec-removal
```

## Verify SC-002: output identical with/without tfsec

```bash
S=$(mktemp -d)
make security > "$S"/sec-with-tfsec.out 2>&1; echo "exit=$?"
PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "$HOME/.local/bin" | paste -sd:) \
  make security > "$S"/sec-without-tfsec.out 2>&1; echo "exit=$?"
diff "$S"/sec-with-tfsec.out "$S"/sec-without-tfsec.out && echo "SC-002 PASS"
```

## Verify SC-003: validate outcome unchanged

```bash
make validate; echo "exit=$?"   # compare against pre-change run from same base state
```

## Verify SC-001: reference sweep

```bash
grep -rn tfsec \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=archived-specs --exclude-dir=reviews --exclude-dir=cleanup-pristine .
# Every remaining hit must be: pre-commit historical comment, another spec's
# scope note, this spec's own artifacts, constitution (follow-up recorded),
# dated board-card audit text, project CLAUDE.md auto-generated tech entries,
# or untracked session files (CONTEXT-CARRYOVER*).
```

## Verify FR-003 / SC-004: corrected docs are positively accurate

```bash
grep -n "Checkov" CONTRIBUTING.md
# The automated-checks entry must show gating-status qualifiers:
# Checkov marked gating, Trivy marked report-only (pending validator-gating flip).
grep -n "Trivy/Checkov" SPEC.md   # line ~479, tfsec clause replaced
```

## Verify FR-007: board cards updated

```bash
python3 - << 'EOF'
import json
html = open('CLEANUP-BOARD.html').read()
start = html.index('const CARDS = [') + len('const CARDS = ')
cards, _ = json.JSONDecoder().raw_decode(html[start:])
t = [c for c in cards if c['title'].startswith('tfsec orphaned')][0]
assert t['lane'] == 'done', t['lane']
assert '2026-' in t['evidence'].split('||')[-1], 'no dated completion clause'
b = [c for c in cards if c['title'].startswith('No Terraform semantic validation')][0]
assert '2026-07-29 001-tfsec-removal' in b['evidence'], 'card (b) missing dated correction'
m = [c for c in cards if c['title'].startswith('MASTER: Terraform')][0]
assert '2026-07-29 001-tfsec-removal' in m['evidence'], 'card (c) missing dated append'
print('FR-007 PASS (all three cards)')
EOF
```

Note (SC-002): pip-audit queries a live vulnerability DB; on an unexpected diff
between the two captures, rerun both before declaring failure.

## Verify FR-005: freeze intact

```bash
git diff --stat main -- docs/archived-specs docs/reviews docs/cleanup-pristine .specify/memory
# must be empty
```
