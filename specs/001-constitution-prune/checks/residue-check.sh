#!/usr/bin/env bash
# Historical-residue detector. Replaces the criterion 3 word list, which scores
# zero on both precision and recall against this document.
#
# Usage: residue-check.sh FILE...
# Exit 0 = clean, 1 = residue found.
#
# The word list in the definition of done (`was `, `previously`, `superseded`,
# `updated to`, `no longer`, `formerly`) returns exactly one match on
# constitution.md, and that match is a template field name. It sees none of the
# six amendment entries and not the version footer, which together are the
# largest residue block in the file. Residue here is structural, not lexical:
# it takes the shape of dated change entries, version identifiers, supersession
# markers in headings, and past-tense verbs narrating edits to the document.

set -uo pipefail

status=0

# Rule 1: dated change-log entries. "Amendment 1.4 (2025-11-28): Added ..."
R1='^[[:space:]]*(Amendment|Revision|Change|Update)[[:space:]]*[0-9]+\.[0-9]+'
# Rule 2: version / ratification identifiers.
R2='\*\*(Version|Ratified|Last Amended)\*\*|^[[:space:]]*(Version|Ratified|Last Amended):'
# Rule 3: supersession markers in headings. Matched case-insensitively: headings
# title-case them ("(Updated)"), so a case-sensitive match misses every real one.
R3='^[^`]*(\(updated\)|\(revised\)|\(new\)|\(deprecated\)|\(old\)|\(legacy\))[[:space:]]*$'
# Rule 4: past-tense verbs narrating an edit to this document.
R4='^[[:space:]]*(Added|Removed|Renamed|Strengthened|Clarified|Migrated|Replaced|Moved|Introduced)[[:space:]]'
R4b='):[[:space:]]*(Added|Removed|Renamed|Strengthened|Clarified|Migrated|Replaced|Moved|Introduced)[[:space:]]'
# Rule 5: the original word list, kept as a subset. Not sufficient alone.
R5='\bwas \b|\bpreviously\b|\bsuperseded\b|\bupdated to\b|\bno longer\b|\bformerly\b'
# Rule 6: parenthetical tool alternatives left behind by a migration, e.g. "(or black)".
# Scoped to a tool vocabulary. An unscoped "\(or [a-z]+\)" also matches prose
# like "(or config)", which is not residue.
R6='\((or|formerly|previously) (black|flake8|isort|bandit|tfsec|pylint|nose|unittest|npm|yarn|pip)\b'

report() {
  local file=$1 rule=$2 label=$3 fold=${4:-}
  local out
  out=$(grep -nE ${fold:+-i} "$rule" "$file" 2>/dev/null) || return 0
  [ -z "$out" ] && return 0
  while IFS= read -r line; do
    printf '%s:%s [%s]\n' "$file" "$line" "$label"
  done <<<"$out"
  status=1
}

for f in "$@"; do
  [ -f "$f" ] || { echo "residue-check: no such file: $f" >&2; status=1; continue; }
  report "$f" "$R1"  "dated-change-entry"
  report "$f" "$R2"  "version-identifier"
  report "$f" "$R3"  "supersession-marker" fold
  report "$f" "$R4"  "edit-narration"
  report "$f" "$R4b" "edit-narration"
  report "$f" "$R5"  "residue-phrase"
  report "$f" "$R6"  "migration-leftover"
done

if [ "$status" -eq 0 ]; then
  echo "residue-check: clean"
fi
exit "$status"
