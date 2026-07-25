# Battleplan & Refuter Doctrine

*Written 2026-07-24 (BP4 kickoff). This is the artifact the crashed session was asked for
and never delivered. It captures the operating discipline that the last several sessions
learned the hard way — from OOM crashes, a wrong root-cause, a refuter mutation left in the
tree, and four consecutive "this is THE root cause" calls that were each overturned by the
owner's browser rather than by any document review.*

---

## 1. Re-derive from live state. Documents are suspects, not evidence.

The single most expensive failure pattern in this campaign is **asserting a fact about
state that was never checked against state.** Every overturned theory — the 3rd-party-cookie
root cause, "1384 is the fix" (twice), the canonical dup record, "GAP-1 carded separately,"
"WAF test auto-reactivates," "1393 = 4 worktrees" — was overturned by re-querying the live
system, never by the plan's own adversarial appendices.

Rules:
- A spec, README, comment, diagram, or prior battleplan note is a **claim to verify**, never
  a fact to build on. The board (`CLEANUP-BOARD.html`) is ground-truth-ish but drifts; it was
  19 commits stale when BP4 opened.
- Before scheduling work on any card, **re-run the check.** `grep` the claimed line, run the
  repro, query the table. Cards move to `done` only with a commit SHA in evidence.
- Every feature carries a **ship-time state check** — an executed assertion, not a reviewed
  paragraph. "The test passes now" beats "the review concluded it would pass."

## 2. Anti-sunk-cost. Prior momentum is not a reason.

LLMs continue down a path after the path is known-bad. Guard against it explicitly:
- When switching models or resuming, **re-open the load-bearing decision** rather than
  inheriting it. "Fable eyes" = evaluate the current state cold; keep what survives scrutiny,
  drop what only survives by inertia.
- A rationale that closes a threat class you never enumerated will close the next one too.
  (The torch deferral's "needs pre-existing S3 write" silently exempted `tar.extractall`
  under the identical model.) State the threat model; don't pattern-match a dismissal.
- Right-answer-wrong-method still counts as a miss to re-examine. Merging #945 on a correct
  flake call via a method (reason-about-E2E-from-diff) that was proven unreliable 45 minutes
  later is a process bug even though the merge was fine.

## 3. Memory / OOM discipline (this box: ~10GB WSL cap).

Two sessions died at 6.6–8.6GB RSS. Cause: a mutation-probing refuter rewrites the real
working tree (apply mutation → run tests → restore); anything else reading that file at the
same time can hit a mutated `while True` and balloon RAM until the session is killed.
- **Serialize the mutation-refuter.** It runs alone. Nothing else runs tests during it.
- **Parallelize refuters only across DISJOINT files** — a standalone script, a different
  module. Never two agents on the file under mutation.
- **Chunk pytest** ~6 files per process, every time, regardless — it bounds any single
  process's memory.
- **`timeout` every pytest/python invocation** an agent runs. A defect that breaks loop
  termination turns an unrelated test run into an unbounded one; the timeout is the backstop.
- **Symptom recognition:** a test that hangs or balloons but passes instantly in isolation is
  reading a concurrently-mutated file — suspect that, not a real hang.
- **After any refuter dies, `git diff`.** A killed refuter leaves its mutation behind (it did,
  once — `existing_by_email or stable_user` was left flipped). Verify md5/`grep -c MUTATION`
  before trusting the tree.

## 4. Child-agent model awareness.

The parent cannot switch its own model mid-session; only spawned agents can be given a model.
So:
- When the owner wants a model changed, that takes effect through **child agents** (or a new
  session), and the parent should say so plainly rather than implying it switched itself.
- A/B a model on a **fresh, un-spoiled task.** Re-running a refuter on a feature whose answer
  key already exists in three files measures contamination, not capability. The 1395 Fable arm
  is unscorable for exactly this reason.
- Pre-register the rubric and answer key **before** the second arm runs, so scoring can't be
  rationalized post-hoc.

## 5. Refuter independence (the standing rule).

Every claim is verified by an **independent** refuter/validator — never the implementer
grading its own work. The implementer is blind to its own errors; self-run tests miss vacuous
tests, stranded flows, and enshrined bugs (1395's own new test asserts the K-3 defect as
correct).
- Refuter is prompted to **disprove**, defaults to skepticism, and must **reproduce
  independently** or the finding is a false positive, not a find.
- UI work → Playwright screenshot against the real Amplify site, never localhost.
- OAuth login can't be headless (Google bot-detects) → the owner does the interactive login;
  don't claim it works without their confirmation.
- Mutation hygiene is binary and disqualifying: every mutation applied AND restored, `git diff`
  clean at exit, or the run doesn't count regardless of findings.

## 6. Fail-closed, no silent fallbacks.

- `None`/"not found" is reserved for the genuine negative (full range scanned, zero results).
  An **error** must propagate, never be coerced to "not found" — coercing it is CWE-636
  (Failing Open) and, in auth, mints duplicate accounts (the 1395 bug).
- A resource bound may stop the work but must **surface incompleteness explicitly** (raise),
  never truncate silently. (DynamoDB's 1MB page returns `LastEvaluatedKey`; Elasticsearch's
  `max_result_window` errors; boto3 `MaxItems` returns a `NextToken`. None return a silent
  empty.)
- Every fallback needs an explicit justification and a log line, or it's a concealed bug.

## 7. Persist early. Artifacts are not durable until committed.

The plan writes as if writing were persisting. It is not: 9k lines of specs sat untracked, an
implementation had 0 commits, on a box whose own runbook documents a killed hook silently
discarding uncommitted tracked edits.
- Commit work-in-progress to its branch **before** starting adjacent work — label it
  `wip(...) — KNOWN DEFECTS, DO NOT MERGE` so committing-for-safety is not mistaken for
  ready-to-ship. Commit ≠ push; local durability first, PR when green.
- GPG-sign everything; never `--no-verify` / `--no-gpg-sign`. A signing failure is a config
  bug to fix, not to bypass.

## 8. Size the process to the change.

Not every change earns nine stages. A sub-~50-line production diff ships as a PR with a
paragraph and an independent refuter — not a full spec suite. Reserve the heavy pipeline for
features with real design surface. The pipeline's unit of work is a document, and a document
completes when it's internally consistent — which is why the artifact-to-code ratio ran 22:1.
Measure what ships, not what's authorable.

---

*Linked memory: `refuter-mutation-concurrency`, `verification-refuter-standard`,
`sse-defer-not-delete`, `no-new-aws-resources`, `prefer-battleplan-discipline`.*
