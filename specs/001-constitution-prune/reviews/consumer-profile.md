# Who reads the constitution, and to do what

The prune target is driven by consumers, not by taste. This file is the standard the
necessity refuter tests each section against. A section earns its place only if omitting it
would make a named consumer below produce a *wrong* result, not merely a less-informed one.

## Two consumers, very different needs

**MT (main thread).** Long-lived, does the work the repo is graded on: branches, commits,
pushes, PRs, pipeline monitoring, board cards, releases. Reads the constitution once at
session start and keeps it.

**SA (sub-agent).** Short-lived, single-purpose, spawned with a narrow task and no history.
Never opens a PR, never pushes, never touches the pipeline. Gets the constitution injected as
fixed overhead on *every* spawn, which is why bloat here is multiplied by agent count.

## SA task catalogue (the ones that actually happen)

| # | Task | What it needs to get right |
|---|------|----------------------------|
| SA-1 | Root-cause a failing unit test | Which mocks are legal, that fixture-editing to green a test is prohibited, that "flaky" is not an accepted outcome |
| SA-2 | Root-cause a failing integration/E2E test | That integration tests hit real dev AWS, that the failure means dev or code is wrong, never test config; that external publishers stay mocked |
| SA-3 | Find references/usages of a tech, term, or symbol | Almost nothing. Needs the repo, not the constitution |
| SA-4 | Verify or refute a claim (refuter/validator) | The rule being claimed, if the claim is about a rule |
| SA-5 | Write or extend tests for new code | Coverage floor, happy+error path requirement, deterministic time, which layer mocks what |
| SA-6 | Implement a spec task (speckit) | What the service does, acceptance criteria for the change, testing obligations |
| SA-7 | Map architecture / hunt doc drift | What the service is supposed to be, so drift is measurable against it |
| SA-8 | Audit config vs documented policy | The documented policy, precisely, for the tool in question |
| SA-9 | Review a diff for defects | Security rules that a diff can violate: injection, secrets, logging raw input |

## Failure-mode test (what the refuter must demonstrate)

For a section to be KEEP, the refuter must name at least one row above and describe a
**concrete wrong output** the agent produces without that section in context. Examples of a
passing argument:

- "Without *Failing Tests*, SA-1 edits the fixture to match the broken code and reports the
  test fixed. This has a known-bad outcome and no other source in-context prohibits it."

Examples of a **failing** argument, all of which must be graded CUT or PARTITION:

- "It provides useful background on the service." Background is not necessity.
- "A future task might need it." Speculative.
- "It documents an important requirement." Importance is not the test; *in-context necessity
  for a listed task* is.
- "It is referenced elsewhere in the document." Internal cross-reference is not consumer need.

## Verdicts the refuter may return

- **KEEP** — proven necessary in-context for a named SA row or for MT.
- **PARTITION** — real content, but needed only by a task that can load it on demand. Moves to
  a `docs/` file; the constitution keeps at most a one-line pointer.
- **SUMMARIZE** — needed, but the operative rule survives in one or two lines; the rest goes.
- **CUT** — no consumer, or fully duplicated elsewhere. Deleted, not partitioned.

## Standing constraints

- Budget: the whole document under 2000 words, ideally lower. Currently 4046.
- Partition targets are `docs/*.md`, one hop from the constitution. Three already exist:
  `docs/MODELING.md`, `docs/OBSERVABILITY.md`, `docs/E2E-SYNTHETIC-DATA.md`.
- Rules carry no rationale. Explaining *why* a rule exists hands an agent a premise it can
  evaluate and then decide is inapplicable.
- No dates, no version footers, no amendment history, no em-dashes or en-dashes.
