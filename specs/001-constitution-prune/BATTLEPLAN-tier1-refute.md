# Battleplan: refute the verified-once Tier 1 docs

Opened 2026-08-01. Owner directive: *"verified once: let's refute them so they're actually
useful."*

Scope is the five Tier 1 pointer-closure files that passed `injected-docs-check.sh`
mechanically but never faced an adversarial pass. Mechanical cleanliness proves cited paths
exist and cited lines exist. It cannot prove a cited line still *says* what the doc claims,
and it cannot see an omission at all. That gap is what this battleplan closes.

Governing doctrine: `docs/cleanup-pristine/battleplan-refuter-doctrine.md`.
Scoreboard card: `CLEANUP-BOARD.html`, "MASTER: markdown audit scoreboard".

## Standard

A doc graduates to REFUTER-AUDITED when every load-bearing claim in it has a verdict backed by
a reproduced command against a **primary source**, and the parent has personally re-verified
every survivor. Refuter agreement is a lead, not a verdict; two agents can be wrong the same
way, and in this campaign they have been.

Primary sources are `src/`, `frontend/src/`, `tests/`, `infrastructure/terraform/`, `Makefile`,
`.github/workflows/`, the manifests, Dockerfiles, and `git log`. **No `.md` file is evidence.**
A claim supported only by another document is UNVERIFIABLE, not CONFIRMED.

## Targets

| # | File | Words | Refuters | Lens |
|---|------|-------|----------|------|
| F1 | `docs/ci-gotchas.md` | 530 | 2 | A: claim-by-claim. B: consequence + `git log`/`blame` archaeology |
| F2 | `docs/SERVICE-SHAPE.md` | 925 | 1 | bidirectional completeness, as-built vs as-intended, dead symbols |
| F3 | `docs/OBSERVABILITY.md` | 537 | 1 | three-way inventory: emitted / alarmed / granted |
| F4 | `docs/ACTIVE-TECHNOLOGIES.md` | 328 | 1 | manifests are authoritative; wired vs dead; retired vs present |
| F5 | `docs/runbooks/terraform-state.md` | 301 | 1 | every command is a claim; destructive-step guards |

F1 gets the pair because it is the highest-risk of the group: extended but never rebuilt, acted
on under time pressure, and the prior session's work on it was never independently checked.

All five files are disjoint, so the refuters run concurrently. Doctrine rule 3 permits this
precisely because no mutation-probing is involved here; nothing writes to the tree.

Agents are spawned as read-only types. Enforcement at the tool layer, not by instruction,
because a killed refuter has left a mutation behind before.

## Sequencing

1. **Refute** (parallel, 6 agents). Running.
2. **Parent re-verification.** Every surviving claim re-checked by the parent against source.
   Not delegated. This is where refuter agreement stops counting.
3. **Adjudicate.** Per the owner's standing rule: where doc and code disagree, code wins and the
   doc is amended. Where a technology is wired in code but absent from the doc, that is an
   amendment, not a code change. **Every amendment is presented to the owner before it is
   applied.** No doc edit lands unreviewed.
4. **Apply**, in one commit per file, with the refutation record committed alongside.
5. **Update the scoreboard card**, moving each file from `[~]` to `[x]` only after step 2.

## Adjudication rule (owner-stated)

> If we find a tech that is not mentioned but it is wired up in code, that calls for an
> amendment to the md file. All md amendments need to be validated with me.

Two directions, both are findings of equal weight:

- **Doc claims X, code says not-X** -> the doc is wrong. Amend the doc.
- **Code does X, doc is silent** -> the doc is incomplete. Amend the doc.

Neither direction authorises changing code to match a document. Code is the primary source;
that is the whole premise.

## Out of scope, explicitly

- **Tier 2.** 1777 files. Not scheduled, and expanding into it needs an explicit decision.
  The closure is what agents actually read.
- **Creating alarms or alerts.** Owner decision 2026-08-01: alarms are unwanted, they cost
  money, and squashing all alerting is acceptable. A missing alarm is therefore NOT a defect
  in this campaign. F3 establishes only whether the *document* tells the truth about what
  exists. See the standing decision recorded on the board.
- **The Next.js CVE work.** Tracked separately, runs in parallel, shares no files with this.

## Deferred to after this battleplan

The scoreboard card's remaining Tier 1 items, in its own recommended order:

- `SECURITY.md` (489w) — different in kind. Public-facing policy with an audience outside the
  repo. Correct lens is claimed controls vs actual controls, not drift.
- `docs/diagrams/TEMPLATE.md` (525w) — the constitution tells agents to build diagrams from it
  and it has never been read.
- `infrastructure/terraform/bootstrap/README.md` — rewritten 2026-08-01, no refuter pass.
- Policy call: does `injected-docs-check.sh` get wired into `make validate` as a hard gate, a
  non-gating CI annotation, or stay manual. It is written and its proof harness demonstrates
  all six rules firing, and nothing runs it.

Then the testing audit off the kanban cards.
