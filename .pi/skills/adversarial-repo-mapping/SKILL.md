---
name: adversarial-repo-mapping
description: Cold, no-priors mapping of a repo's real architecture and drift. Optimizes for finding mistakes, not coverage. Fans out per-domain finder agents, refutes each finding with an independent skeptic, sweeps for cross-domain contradictions, and emits citation-backed maps. Use for cleanup campaigns, architecture audits, doc/diagram drift hunts, and dead-code discovery. Comments, READMEs, specs, and diagrams are SUSPECTS, never evidence.
---

# Adversarial Repo Mapping

## Prime directive

Optimize for **finding mistakes**, not for coverage. A 99% map that misses the one subtle,
chronic bug is a failure. The value produced is the caught error, not the closed ticket.

The enemy is **misleading structure**: comments, READMEs, specs, and diagrams that describe
code that no longer exists, or never did. These files steer every reader (human and agent)
toward the wrong mental model, so bugs persist because everyone is looking where the map
points instead of where the code is. This skill exists to find where the map lies.

## The contamination rule (why PRISTINE mode is the default)

Seeded priors contaminate. If you feed agents a list of known findings, they verify that
list and stop looking. They inherit the blind spots of whoever wrote the list. Run this
skill **PRISTINE**: agents receive **category directives only** ("enumerate every URL surface
and classify it", "verify every diagram against source"), never the answers. Nothing from a
prior run, a carryover, or an existing `docs/cleanup/` reaches a finder agent.

Two modes:
- **PRISTINE (trust this one):** cold discovery, zero priors. The only trustworthy map.
- **SEEDED (measure, do not trust):** primed with priors. Useful only to measure contamination
  by diffing its output against a PRISTINE run. Never ship a seeded map as ground truth.

## Hard rules (enforce at every stage, including refute)

1. **Canonical sourcing.** Every claim cites a real `file:line` opened this run: a Terraform
   resource block (`infrastructure/terraform/**/*.tf`), real source (`src/**`, `frontend/src/**`),
   a config/manifest (`Makefile`, `.pre-commit-config.yaml`, `requirements*.txt`, `pyproject.toml`,
   `.github/workflows/**`), OR a grep-proven absence (state the exact command and that it returned nothing).
2. **Suspects are never evidence.** A comment, README, SPEC, ADR, CHANGELOG, or diagram is a
   SUSPECT to reconcile against real source. It is the thing being checked, not the proof.
3. **No optimism.** If a citation does not precisely support the claim, the verdict is UNKNOWN
   with the exact evidence still needed. "Probably" and "looks like" are not verdicts.
4. **Tool output is also a suspect.** An import graph, a linter, a count script can be wrong.
   Refute their output too (see the import-graph caveat).
5. **Read-only.** Touch nothing but the output maps folder.

## The pipeline

```
enumerate  ->  verify (per domain)  ->  refute (independent skeptic)  ->  contradiction sweep  ->  synthesize maps
```

Run verify and refute as a `pipeline(domains, verify, refute)` so each domain refutes as soon
as it finishes (no barrier). Synthesis is a barrier: it needs all reconciled findings at once.

### Stage 1: enumerate (deterministic, no LLM)
Ground-truth counts the finders will be checked against. Run and cache:
- DynamoDB tables: `grep -rn 'resource "aws_dynamodb_table"' infrastructure/terraform/`
- Lambda modules: `grep -n 'module "' infrastructure/terraform/main.tf`
- Container images: `find src -name Dockerfile` and `deploy.yml` `build-*-image` jobs
- Every diagram file: `grep -rln '```mermaid' --include='*.md' .` (exclude `test-results`, `node_modules`)
- Import graph for dead code (see caveat below)

### Stage 2: verify (fan out, one finder per domain)
Domains (each finder gets a category directive, cold):
- **urls** — every URL/endpoint surface, classify LIVE / DISABLED / ORPHANED, prove emitter to consumer wiring.
- **comments** — every comment/docstring that asserts a fact; reconcile against the code it describes. Include docstrings (e.g. "8 resolutions" vs a 6-member enum).
- **deadcode** — unreferenced modules/functions via the import graph, each confirmed by grep across `src/` and `tests/`.
- **validators** — for each (ruff, bandit, semgrep, mypy, gitleaks, detect-secrets, trivy, checkov, pytest, integration, e2e, mutmut, hypothesis): declared? wired into make/pre-commit/CI? actually runs today? activation cost?
- **charts** — FIRST CLASS. One finder per diagram file. Extract every count, node name, edge, label, resource name, URL, threshold; check each against live source. Diagrams drift hardest and mislead most.
- **manifest** — full `git ls-files` categorized; processing order; the ledger schema.

Each finder returns structured findings: `{claim, cited_locus, actual_at_locus, state, verdict, evidence_still_needed}`.

### Stage 3: refute (independent skeptic per domain)
A separate agent re-opens every cited locus and re-runs every grep/count. Its job is to REFUTE.
- If a `file:line` does not precisely say what the finder claimed, flip to UNKNOWN or REFUTED.
- If a "grep-proven absence" was claimed, re-run the grep; if it returns anything, flip.
- Re-count every count. Default to UNKNOWN on thin or line-drifted evidence.
Only claims that survive a personal re-check keep a CONFIRMED / LIVE / DISABLED / ORPHANED verdict.
This stage is non-negotiable. In practice it corrects real errors every run, including the tool's own.

### Stage 4: contradiction sweep (barrier, then one pass)
Collect all reconciled findings. Run one agent whose only job is to find claims from different
domains that describe the same fact differently (the classic: domain A refutes "X is always
true" while domain B confirms "X is true in dev"). Reconcile or flag. This catches the errors
that per-domain refutation structurally cannot, because no single finder sees another's work.

### Stage 5: synthesize
Emit the maps from reconciled findings only. Never assert an UNKNOWN as fact; render it as an
OPEN QUESTION with its evidence-to-resolve. Maps are citation-backed, em-dash-free, AI-tell-free.

## Execution-phase retrospective (learned by running the whole campaign)

The maps this skill produced were executed against (fix, delete, signpost). Execution exposed
gaps in the mapping phase itself. Fold these into every future run:

1. **Report drift by CLASS, not by citation.** Every drift class the map spot-checked
   undercounted its real blast radius by about 2x ("8 resolutions": 3 cited loci, 13 real;
   "/opt/model": 3 cited, 8 real). Once a false claim is confirmed, grep it repo-wide and
   report the full extent. A cited-loci list reads as complete when it is not.
2. **Do git archaeology at mapping time.** A test-only orphan cannot be adjudicated without
   its history: added-in commit, ever production-imported (and the unwiring sha if so),
   superseded-by. Execution needed a full second archaeology pass before any deletion was
   safe. Capture (added_in, ever_wired, unwired_at, superseded_by) when the orphan is first
   found. The split that matters: SUPERSEDED (live replacement exists, safe delete) vs
   UNWIRED-LATENT (specced behavior whose wiring never shipped, deleting erases intent).
3. **Chain reachability is a first-class domain.** The map found dead modules but missed that
   an entire Lambda was reachable only by one daily EventBridge timer, which silently killed
   THREE user-facing features (alert emails, magic-link emails, a notification queue with no
   consumer). Map who invokes every entrypoint: SNS subscriptions, EventBridge targets,
   lambda:Invoke callers, Function URLs, API routes. Then follow each dead module to its live
   ends; a dead middle link means the live ends are dead too, and that is a product bug, not
   a code smell.
4. **Mine commit messages and in-tree TODOs as a finder domain.** Deferred-work promises
   buried in git log are exactly the class owners fear losing. A dedicated mining pass
   (grep log for deferred/follow-up/for now/phase 2/known issue, then adversarially verify
   each promise against the current tree) carded 17 still-outstanding items, including a
   session-restore bug both full mapping runs missed.
5. **Map the execution environment, not just the repo.** Two blockers during execution were
   environment facts the validator inventory could have caught: the checkov hook resolves to
   a different (broken) interpreter without the project venv active, and a stale security
   baseline made an unrelated pre-existing finding block every .tf commit. For each validator
   record: which interpreter/binary it resolves to, and whether its baseline is current.
6. **Fix comments against the wired fork, not the plausible one.** A comment describing
   mechanism A is not wrong just because code implements mechanism B somewhere; both can
   exist (a config fork, an env fallback, an orphaned build script). Before correcting,
   prove which side is actually wired (env vars set, resources attached, callers present).
   Executing a "fix" against the unwired half injects fresh drift with a confident tone.
7. **Signpost what you keep.** UNWIRED-LATENT code left in tree must carry an in-file marker
   pointing at a tracked open question, or the next mapper re-discovers it from scratch and
   the next reader mistakes it for live code. Resolved questions stay on the map as resolved,
   never deleted; the trail is the deliverable.

## Import-graph caveat (learned the hard way)

A dotted-path AST import graph produces **false positives** in Docker-flattened Lambda layouts,
where modules import each other by **bare name** (`from cache_logger import ...`) because the
Dockerfile copies them into the task root. Before asserting a module is dead, resolve bare
imports and check: static imports (dotted AND bare), `importlib`/`__import__`/string paths,
`getattr`, decorator/registry auto-discovery, `Dockerfile COPY` lines, pytest collection, `__all__`,
and Lambda handler config. The import graph is a lead, not a verdict. Refute it.

## Output maps

Write to the target folder (PRISTINE runs use a fresh folder, never overwriting a prior run):
- `url-inventory.md` — every URL surface, LIVE/DISABLED/ORPHANED, emitter to consumer.
- `dependency-map.md` — workstream DAG, parallel-safe set, CI-cost ordering.
- `open-questions.md` — decision nodes, each with exact evidence-to-resolve. Flagship question first.
- `whitelist-ledger.md` — file manifest, processing order, ledger schema, seeded rows (citation-backed only).
- `validator-inventory.md` — every validator's true run-state and activation cost.
- `diagram-drift.md` — every confirmed diagram drift with both loci.
- `README.md` — index tying them together, plus the refutation deltas (what priors were wrong).

## Workflow skeleton

```js
const reconciled = await pipeline(DOMAINS,
  d => agent(d.verifyPrompt, {label:`verify:${d.key}`, phase:'Verify', schema:FINDINGS}),
  (v,d) => agent(refutePrompt(d.key, JSON.stringify(v)), {label:`refute:${d.key}`, phase:'Refute', schema:FINDINGS}));
// barrier
const contradictions = await agent(sweepPrompt(JSON.stringify(byDomain)), {schema:SWEEP});
const maps = await parallel(DOCS.map(doc => () =>
  agent(synthPrompt(doc, allFindings), {label:`write:${doc.filename}`, phase:'Synthesize', schema:DOC})));
// main loop writes files (agents never edit source)
```

Scale the finder pool and vote count to the ask. "find any drift" is a few finders, single refute.
"be exhaustive" is a finder per file, 3-vote refute, plus the contradiction sweep and a completeness
critic that asks "what modality did we not run, what claim is unverified, what source is unread?"
