#!/usr/bin/env bash
# Drift detector for the core injected documents.
#
# Usage: injected-docs-check.sh [FILE...]     (default: the core set below)
# Exit 0 = clean, 1 = drift found.
#
# Why this exists. The old versions of these documents were defended by nobody
# believing them. The rebuilt ones are short and curated, so they get trusted,
# which makes a surviving error cost more rather than less. Nothing else in the
# repo checks them.
#
# The rules are chosen from observed failures, not from a general idea of what a
# linter should do. Every one of these has already produced a wrong answer in
# this repository:
#
#   R1  a doc cites a path that does not exist  (docs/CLOUD_PROVIDER_PORTABILITY_AUDIT.md,
#       docs/SERVICE-SHAPE.md)
#   R2  a doc cites file:NN past the end of the file  (five stale sibling
#       citations in 001-oauth-provider-taint, three of them off by one line)
#   R3  a doc's Lambda list drifts from src/lambdas/
#   R4  a doc's CloudWatch namespace table drifts from the code and Terraform
#       (this rule was written because the author of OBSERVABILITY.md missed
#       three of eight namespaces inside a single session, by grepping for
#       inline Namespace= and not for namespaces bound to a module constant)
#   R5  a doc cites a make target that does not exist
#
# R1 needs an escape hatch, because these docs deliberately name things that do
# NOT exist so an agent stops hunting for them. That list lives in
# no-such-path.txt next to this script rather than as markers in the prose: the
# documents stay clean and the exceptions stay auditable.

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(git -C "$here" rev-parse --show-toplevel)
cd "$repo" || exit 2

allow="$here/no-such-path.txt"
status=0

CORE=(
  .specify/memory/constitution.md
  CLAUDE.md
  docs/SERVICE-SHAPE.md
  docs/MODELING.md
  docs/OBSERVABILITY.md
  docs/ci-gotchas.md
  docs/ACTIVE-TECHNOLOGIES.md
  docs/E2E-SYNTHETIC-DATA.md
  docs/runbooks/terraform-state.md
)

fail() { printf '%s\n' "$*"; status=1; }

is_allowed() {
  [ -f "$allow" ] || return 1
  grep -qxF "$1" "$allow"
}

# Backticked tokens that are unambiguously repo-root-relative: they begin with a
# real top-level directory, or they are a known root file.
#
# Deliberately narrow. An earlier version accepted any backticked token holding a
# slash, which flagged URL routes (`/api/v2/metrics`), CloudWatch namespaces
# (`SentimentAnalyzer/SSE`), shell fragments (`source .venv/bin/activate`) and
# path fragments written relative to a directory named in the surrounding prose
# (`roles.py`, `modules/lambda/main.tf`). None of those are checkable without
# guessing at the prose, and the guess is where a false positive would come from.
# Root-relative paths need no guessing, and they are the class that actually
# broke: docs/CLOUD_PROVIDER_PORTABILITY_AUDIT.md.
#
# KNOWN LIMIT: ROOTFILES is a whitelist, not a rule. A bare filename with no
# directory component is only checked if it is named there. `mermaid-config.json`
# is in the list because the constitution cites it and a reader would otherwise
# look in docs/diagrams/; a bare filename this list does not know is invisible to
# R1. Distinguishing a real root file from a prose fragment like `handler.py`
# without a directory is the part that cannot be done generically, so extend the
# list when a core doc starts citing a new root file.
ROOTS='src|docs|tests|specs|infrastructure|frontend|scripts|\.github|\.specify'
ROOTFILES='Makefile|CLAUDE\.md|CLEANUP-BOARD\.html|pyproject\.toml|requirements(-dev)?\.txt|SECURITY\.md|docker-compose\.yml|SPEC\.md|mermaid-config\.json|CHANGELOG\.md|README\.md'
extract_paths() {
  grep -oE '`[^`]+`' "$1" 2>/dev/null \
    | tr -d '`' \
    | sed 's/[.,;:)]*$//; s/:[0-9-]*$//' \
    | grep -vE '[*<>${}|]| ' \
    | grep -E "^($ROOTS)/|^($ROOTFILES)$" \
    | sort -u
}

# ---------------------------------------------------------------- R1 + R2
for f in "$@"; do :; done
files=("$@"); [ ${#files[@]} -eq 0 ] && files=("${CORE[@]}")

for f in "${files[@]}"; do
  [ -f "$f" ] || { fail "$f [missing-core-doc]"; continue; }

  while IFS= read -r p; do
    [ -z "$p" ] && continue
    [ -e "$p" ] && continue
    is_allowed "$p" && continue
    fail "$f: $p [R1 cited-path-missing]"
  done < <(extract_paths "$f")

  # R2: `path:NN` and `path:NN-MM` citations must land inside the file.
  while IFS= read -r cite; do
    path=${cite%%:*}; rest=${cite#*:}; line=${rest%%-*}
    [ -f "$path" ] || continue          # R1 already reported it
    total=$(wc -l <"$path")
    [ "$line" -le "$total" ] 2>/dev/null && continue
    fail "$f: $cite [R2 citation-past-eof, $path has $total lines]"
  done < <(grep -oE '`[A-Za-z0-9_./-]+\.(md|py|ts|tsx|js|json|toml|tf|hcl|sh|yml|yaml|html):[0-9]+(-[0-9]+)?`' "$f" \
             | tr -d '`' | sort -u)
done

# ---------------------------------------------------------------- R3
if [ -f docs/SERVICE-SHAPE.md ]; then
  # A Lambda is a src/lambdas/ subdirectory holding a handler.py. That excludes
  # shared/ (library code, no handler) and __pycache__ without naming either.
  real=$(find src/lambdas -mindepth 2 -maxdepth 2 -name handler.py -printf '%h\n' \
           | xargs -rn1 basename | sort -u)
  # The doc's list is the first column of the Compute table. Keying on the table
  # rather than on prose mentions matters in both directions: a bare name like
  # "metrics" or "analysis" appears in prose all over the document, so a prose
  # grep reports no drift even after the row is deleted.
  documented=$(sed -n '/^## Compute/,/^## /p' docs/SERVICE-SHAPE.md \
                 | grep -oE '^\| *`[a-z_]+` *\|' | tr -d '`| ' | sort -u)
  if [ -z "$documented" ]; then
    fail "docs/SERVICE-SHAPE.md: Compute table has no parsable Lambda rows [R3 lambda-list-drift]"
  fi
  while IFS= read -r l; do
    [ -z "$l" ] && continue
    grep -qxF "$l" <<<"$documented" \
      || fail "docs/SERVICE-SHAPE.md: Lambda '$l' exists in src/lambdas/ but is not in the Compute table [R3 lambda-list-drift]"
  done <<<"$real"
  while IFS= read -r l; do
    [ -z "$l" ] && continue
    grep -qxF "$l" <<<"$real" \
      || fail "docs/SERVICE-SHAPE.md: Compute table names '$l' but src/lambdas/$l/handler.py does not exist [R3 lambda-list-drift]"
  done <<<"$documented"
fi

# ---------------------------------------------------------------- R4
if [ -f docs/OBSERVABILITY.md ]; then
  actual=$( { grep -rhoE '"SentimentAnalyzer[^"]*"' src/ 2>/dev/null | tr -d '"'
              grep -rhoE 'namespace *= *"SentimentAnalyzer[^"]*"' infrastructure/terraform/ 2>/dev/null \
                | sed 's/.*"\(.*\)"/\1/'; } | sort -u )
  documented=$(grep -oE '`SentimentAnalyzer[^`]*`' docs/OBSERVABILITY.md | tr -d '`' | sort -u)
  while IFS= read -r ns; do
    [ -z "$ns" ] && continue
    grep -qxF "$ns" <<<"$documented" || fail "docs/OBSERVABILITY.md: namespace '$ns' is live but undocumented [R4 namespace-drift]"
  done <<<"$actual"
  while IFS= read -r ns; do
    [ -z "$ns" ] && continue
    grep -qxF "$ns" <<<"$actual" || fail "docs/OBSERVABILITY.md: namespace '$ns' is documented but exists nowhere [R4 namespace-drift]"
  done <<<"$documented"
fi

# ---------------------------------------------------------------- R5
if [ -f Makefile ]; then
  targets=$(grep -oE '^[a-zA-Z0-9_-]+:' Makefile | tr -d ':' | sort -u)
  for f in "${files[@]}"; do
    [ -f "$f" ] || continue
    while IFS= read -r t; do
      [ -z "$t" ] && continue
      grep -qxF "$t" <<<"$targets" || fail "$f: 'make $t' is cited but is not a Makefile target [R5 make-target-missing]"
    done < <(grep -oE '`make [a-z][a-z0-9-]*`' "$f" | sed 's/`make //; s/`//' | sort -u)
  done
fi

# ---------------------------------------------------------------- R6
# R2 proves a cited line exists. It cannot prove the line still says what the
# citing document says it says, and that is the failure that actually hurts: an
# insertion above shifts every citation below it by one, and the line is still
# in range. anchors.tsv pins the claims worth checking.
anchors="$here/anchors.tsv"
if [ -f "$anchors" ]; then
  while IFS=$'\t' read -r path line pattern claimant; do
    case "$path" in ''|'#'*) continue ;; esac
    if [ ! -f "$path" ]; then
      fail "$claimant: anchor target $path does not exist [R6 anchor-broken]"; continue
    fi
    actual=$(sed -n "${line}p" "$path")
    grep -qE "$pattern" <<<"$actual" \
      || fail "$claimant: $path:$line no longer matches /$pattern/ [R6 anchor-drift]"
  done < "$anchors"
fi

[ "$status" -eq 0 ] && echo "injected-docs-check: clean"
exit "$status"
