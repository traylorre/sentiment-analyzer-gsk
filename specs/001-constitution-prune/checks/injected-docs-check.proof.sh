#!/usr/bin/env bash
# Proof harness for injected-docs-check.sh.
#
# A checker that reports "clean" is worthless until each rule is shown firing on
# a defect it is supposed to catch. This induces one perturbation per rule,
# asserts the rule fires, restores the file, and verifies the restore by hash.
#
# Usage: injected-docs-check.proof.sh    Exit 0 = every rule proved.

set -uo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
cd "$repo" || exit 2

check="$here/injected-docs-check.sh"
backup=$(mktemp -d)
trap 'restore_all; rm -rf "$backup"' EXIT

declare -a touched=()
save()    { mkdir -p "$backup/$(dirname "$1")"; cp "$1" "$backup/$1"; touched+=("$1"); }
restore_all() { for f in "${touched[@]:-}"; do [ -n "$f" ] && cp "$backup/$f" "$f"; done; }

pass=0; fail=0
prove() { # prove <label> <expected-tag> <file> <perturbation-command>
  local label=$1 tag=$2 file=$3 cmd=$4
  save "$file"
  eval "$cmd"
  local out; out=$("$check" 2>&1)
  cp "$backup/$file" "$file"
  if grep -q "$tag" <<<"$out"; then
    printf 'PROVED  %-28s %s\n' "$label" "$(grep -m1 "$tag" <<<"$out")"
    pass=$((pass+1))
  else
    printf 'NOT PROVED  %-24s (rule did not fire)\n' "$label"
    fail=$((fail+1))
  fi
}

echo "baseline:"
"$check" || { echo "baseline is not clean; fix that before trusting this harness"; exit 2; }
echo

prove "R1 cited-path-missing" "R1" "docs/OBSERVABILITY.md" \
  "printf '\nSee \`docs/DOES-NOT-EXIST.md\` for detail.\n' >> docs/OBSERVABILITY.md"

prove "R2 citation-past-eof" "R2" "docs/OBSERVABILITY.md" \
  "printf '\nSee \`CLAUDE.md:999999\` for detail.\n' >> docs/OBSERVABILITY.md"

# Two directions. Deleting the row proves the forward check, and it must be the
# TABLE ROW: the bare word "canary" appears in prose elsewhere in the document,
# so a prose-grep implementation reports clean here. That is the bug this
# perturbation was rewritten to catch.
prove "R3 drift, row deleted" "R3" "docs/SERVICE-SHAPE.md" \
  "sed -i '/^| \`canary\` |/d' docs/SERVICE-SHAPE.md"

prove "R3 drift, stale row" "R3" "docs/SERVICE-SHAPE.md" \
  "sed -i 's#^| \`canary\` #| \`canaria\` #' docs/SERVICE-SHAPE.md"

prove "R4 namespace-drift" "R4" "docs/OBSERVABILITY.md" \
  "sed -i 's|\`SentimentAnalyzer/Reliability\`||g' docs/OBSERVABILITY.md"

prove "R5 make-target-missing" "R5" "docs/OBSERVABILITY.md" \
  "printf '\nRun \`make nonexistent-target\` first.\n' >> docs/OBSERVABILITY.md"

# Insert a line above every anchored Makefile citation. Each stays in range, so
# R2 sees nothing; only R6 catches the shift. This is the off-by-one that made
# five sibling citations in 001-oauth-provider-taint stale, three by one line.
prove "R6 anchor-drift" "R6" "Makefile" \
  "sed -i '40i\\# induced line shift' Makefile"

restore_all
echo
echo "restore verification:"
final=$("$check" 2>&1)
if [ "$final" = "injected-docs-check: clean" ]; then
  echo "  files restored, checker clean"
else
  echo "  RESTORE FAILED:"; echo "$final"; fail=$((fail+1))
fi

echo
echo "proved $pass, unproved $fail"
[ "$fail" -eq 0 ]
