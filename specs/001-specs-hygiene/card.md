# Card: specs tree hygiene (two operator-commissioned housekeeping items)

Status: CARDED, not started. Commissioned 2026-08-06 so it does not get lost on
the kanban board. Linked from specs/001-signed-fanout/card.md while that card
lives; this card is the durable record.

## Item 1: strays under .specify/specs/

.specify/ is speckit infrastructure (templates, scripts, memory). specs/ is the
created specs. Yet .specify/specs/ holds real feature material:
ohlc-cache-remediation.md with its -tests and -clarifications siblings,
1276-e2e-cached-data-mock/, and future/. Adjudicate each one: move to specs/ if
still live, delete if superseded (item 2 standard applies). The
.specify/specs/ directory itself goes away at the end.

## Item 2: wholesale deletion of stale specs/

specs/ holds roughly 380 entries and the vast majority are superseded,
contradictory, or stale (loose SESSION-SUMMARY*.md files, an archive/ dir,
near-duplicate dirs like 1243-first-chaos-gameday vs 1243-first-gameday,
terraform-cycle-fix with and without a number). Operator intent, recorded so a
future agent does not relitigate it: this repo is not an archaeological dig; it
captures the latest state. Stale specs confuse agents grepping for insights and
read poorly to any engineer reviewing the repository. A lot of trial and error
went into learning how to write md and spec-driven files; the repo should show
the latest iteration only.

Mechanism (operator proposal; orchestrator reviewed and concurs, no retired
branch):

- Delete stale specs from main outright. Git history is the archive; every
  deleted directory stays recoverable by commit, so a retired branch would
  store nothing new while creating a second place for agents to absorb dead
  designs, and it would rot unmaintained.
- Version stops are annotated tags off main (v1.0.0 when version 1 retires
  during version 2 work), never branches. Tags are immutable, maintenance-free,
  and not accidentally grepped.
- The sweep is audited, not blind: every directory gets a keep/delete verdict
  with a one-line reason, batched into reviewable PRs. Anything documenting a
  still-live decision gets folded into docs/ before its spec dies.
- Protected floor at sweep time (re-verify then, do not trust this list
  blindly): active cards per the cards lifecycle (001-signed-fanout,
  001-live-hero-widget, 001-model-refresh-eval, 001-chart-stale-series,
  001-digest-never-worked, 001-source-attribution-dead), the quarrysome
  closeout (deliberately open until its work items land), in-flight feature
  dirs, and this card.

## Exit criteria

.specify/specs/ no longer exists; specs/ contains only active cards and
in-flight feature dirs; the tag policy (version stops as annotated tags, no
retired branches) is written down once in CLAUDE.md or docs/ so future sessions
inherit it.
