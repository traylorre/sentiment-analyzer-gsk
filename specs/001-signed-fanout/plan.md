# Implementation Plan: Signed, Aggregating Sentiment Timeseries Fanout

**Branch**: `001-signed-fanout` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-signed-fanout/spec.md`

## Summary

Route the already-existing signed mapping into the timeseries fanout, replace
wholesale bucket overwrites with crash-consistent accumulation (optimistic
concurrency, single atomic write per bucket per article), bound publisher-controlled
timestamps before they key a write, make fanout failures repairable by a targeted
backfill, run a quiesced 30-day backfill under a scoped role with a run manifest,
and amend every CANON statement the change falsifies. Full decision record in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.13 (repo venv; system Python differs, always activate)
**Primary Dependencies**: boto3 (present), no new runtime dependencies; moto for unit
tests, LocalStack for `tests/integration/timeseries/` (both present)
**Storage**: DynamoDB `sentiment_timeseries` (PK `{ticker}#{resolution}`, SK ISO
window start, TTL attr `ttl`); reads from `sentiment_items` (source for backfill)
**Testing**: pytest; tiering per constitution section 3 (unit=moto,
integration/timeseries=LocalStack, e2e=preprod marker)
**Target Platform**: AWS Lambda (analysis, container image); backfill runs as an
operator-invoked script against AWS, not a Lambda
**Project Type**: single project (src/lambdas/analysis, src/lib/timeseries, scripts)
**Performance Goals**: article volume is small (thousands/day); 6 bucket
updates/article/ticker with a read before each write is well inside DynamoDB
on-demand capacity; no latency SLO on the analysis path
**Constraints**: crash-consistent bucket updates (FR-002); quiescence during
backfill (FR-004); no new dependencies; S2 tier, basic rigour
**Scale/Scope**: ~1,500 tickers live, 6 resolutions, trailing-30-day backfill ~10^4
buckets per environment

## Constitution Check

*GATE: pass before Phase 0; re-checked after Phase 1 design.*

- Dedup/idempotency (sec 1): preserved; the analyzed-status gate remains the
  fanout idempotency mechanism (spec A2). PASS
- `model_version` on stored inferences (sec 1): untouched (FR-008). PASS
- Security (sec 2): no secrets introduced; DynamoDB expressions use
  ExpressionAttributeNames/Values throughout (existing pattern kept); no raw text
  logged (fanout logs carry ticker/window/counts only). Backfill role is
  least-privilege per FR-004. PASS
- Testing tiers (sec 3): unit via moto, accumulation race tests in
  `tests/integration/timeseries/` (LocalStack), no repointing mocks at real AWS;
  fixed dates/freezegun only. Coverage floor 80% honored; new module carries unit
  tests with happy + error paths. PASS
- Push rules (sec 4): feature branch `001-signed-fanout` (already on it), GPG
  commits, `make validate` + `make test-local` before push, sub-agents never push.
  PASS
- Post-Phase-1 re-check: no new projects, no new dependencies, no scanner
  exclusions introduced. PASS. Complexity Tracking left empty (no violations).

## Project Structure

### Documentation (this feature)

```text
specs/001-signed-fanout/
├── plan.md              # This file
├── research.md          # Phase 0: decisions with alternatives
├── data-model.md        # Phase 1: bucket schema before/after, item schema
├── quickstart.md        # Phase 1: verify-locally walkthrough
├── contracts/
│   ├── bucket-schema.md         # timeseries bucket contract post-change
│   └── backfill-manifest.md     # run manifest contract (FR-004)
├── checklists/requirements.md
├── reviews/ar1.json
└── tasks.md             # Phase 2 (/speckit.tasks, not this command)
```

### Source Code (repository root)

```text
src/lib/timeseries/
├── __init__.py          # exports rewritten: deleted write_fanout* symbols dropped,
│                        # accumulate_fanout and label_to_signed exported. Mandatory:
│                        # SSE imports this package at every cold start, so a stale
│                        # export of a deleted symbol is an ImportError in SSE
├── fanout.py            # accumulate_fanout() replaces write_fanout on live path;
│                        # write_fanout_with_update deleted (unacceptable per AR#1)
├── models.py            # SentimentScore.value docs corrected; sources semantics
└── signed.py            # NEW: label_to_signed() moved/exported from analysis so
                         # backfill and handler share one mapping

src/lambdas/analysis/
├── handler.py           # signed value at the hop; FR-010 bounds; FR-009 recording
└── sentiment.py         # _label_to_score delegates to lib (single source of truth)

scripts/backfill_timeseries.py   # NEW: quiesced backfill, manifest emission
infrastructure/terraform/modules/iam/main.tf  # NEW scoped backfill role
docs/MODELING.md, docs/SERVICE-SHAPE.md, README.md  # FR-006 amendments

tests/unit/test_timeseries_fanout.py          # rewritten for accumulate semantics
tests/unit/test_analysis_handler.py           # hop test (signed value reaches fanout)
tests/unit/test_backfill_timeseries.py        # NEW: recompute + idempotency + manifest
tests/integration/timeseries/                 # LocalStack: concurrent accumulation,
                                              # crash-consistency, race behavior
```

**Structure Decision**: single project; the only new module is the shared signed
mapping and the backfill script. The dead `write_fanout_with_update` is removed
rather than repaired so exactly one accumulation implementation exists.

## Adversarial Review #2

Reviewer subagent over the full Phase 0/1 artifact set (spec, plan, research,
data-model, both contracts, quickstart, ar1.json, constitution section 3), seven
activities: artifact read, clarification drift, cross-artifact consistency, code
verification, S2 angles, operational rigour, constitution compliance. Verdict:
0 CRITICAL, 1 HIGH, 5 MEDIUM, 7 LOW. Per-item record with evidence in
reviews/ar2.json; reviewer, refuter, and grader raw trails in the run's handoff
directories.

| ID | Sev | Finding | Adjudication | Disposition |
|---|---|---|---|---|
| ar2-001 | HIGH | D1 protocol has no branch for existing unversioned (pre-cutover) buckets; backfill cannot rewrite its primary targets | Refuter CONFIRMED; refined fix: two-branch guard keyed on what the read returned, no separate attribute_not_exists(PK) branch | fixed: research D1, data-model validation rules and state machine (legacy-unversioned first-class), bucket-schema, spec Q4 |
| ar2-002 | MEDIUM | D2 rationale "SSE does not import timeseries fanout" is false (transitive import via package __init__ at cold start) | recorded | fixed: D2 restated as the whole-directory-copy invariant plus the metrics.py-only import bound |
| ar2-003 | MEDIUM | Plan change set omitted src/lib/timeseries/__init__.py, mandatory once D7 deletes both exported symbols | recorded | fixed: plan source tree, SSE cold-start blast radius named |
| ar2-004 | MEDIUM | Manifest records no scope for targeted repairs; cross-run count comparisons meaningless | recorded | fixed: scope field {ticker_filter, window_filter, argv} in backfill-manifest |
| ar2-005 | MEDIUM | Clarified is_partial contract absent from bucket-schema, the artifact consumers read | recorded | fixed: is_partial bullet in bucket-schema |
| ar2-006 | MEDIUM | 240s Invocations silence does not bound Lambda's async retry queue; silent double-count direction | Refuter CONFIRMED; chose the amendment (async-queue metrics cannot prove emptiness; trailing Throttles 6h and Errors 30m can) | fixed: three-part drain criterion in spec Q3, research D5, quickstart; escalation path and residuals documented |
| ar2-007 | LOW | FR-004 role-scope sentence drifted behind Q4 protocol and D6 grants | recorded | fixed: FR-004 wording, D6 named authoritative |
| ar2-008 | LOW | Least-privilege claim silent on GetMetricData being necessarily account-wide | recorded | fixed: D6 rationale states the residual |
| ar2-009 | LOW | Window dimension on TimeseriesFanoutErrors changes metric identity, unbounded cardinality | recorded | fixed: D4 keeps the metric undimensioned; log carries the window |
| ar2-010 | LOW | Version guard binds cooperating writers only; dormant ingestion grant is a bypass that strips version | recorded | fixed: spec Context and Q4, research D1; grant drop reframed as the enforcement half, still owner's call |
| ar2-011 | LOW | Q2 cites the failure tracker, not the SNS body construction | recorded | fixed: cite moved to handler.py:1043 and source_type origin |
| ar2-012 | LOW | Smoke query returns oldest buckets; reads as cutover failure for a week | recorded | fixed: --no-scan-index-forward plus explanation |
| ar2-013 | LOW | Manifest idempotency sentence internally inconsistent (counts co-vary by conservation) | recorded | fixed: written plus skipped_ttl stable; split may shift |

The HIGH was adjudicated by an independent refuter briefed with numbered actions;
the same refuter adjudicated ar2-006's amendment choice because the fix shape
needed a decision against Lambda async invocation semantics (both CONFIRMED,
binding edit lists applied verbatim). The applied edit set, 21 edits across all
seven artifacts, was graded by a fresh agent that proposed none of it: 13/13
faithful, contradiction sweep found no surviving old claims, cross-references
agree (spec Q3 / research D5 / quickstart on the drain criterion; data-model
state machine / research D1 on the two-branch guard; plan tree / D7 deletions /
D2 placement), dash scan clean.

Reviewer-verified clean, no finding: D5 catch-up via the 7-day published-time
ingestion window (ingestion/handler.py:902-903), D8 SNS sources ground truth,
reader attribute-wise tolerance of new attributes, constitution section 3
compliance, quickstart table and target names.

Gate statement: 0 CRITICAL, 0 HIGH open. Stage 5 gate: OPEN.

## Stage 6: canon drift second pass

[Feature 0001] Stage 6: plan second pass. Drift was found in both directions
during AR#2 (artifact claims vs code: the D2 rationale was false against the SSE
import graph, the plan change set was incomplete against D7, and the drain
criterion was insufficient against Lambda async semantics). The applied AR#2
corrections above are the realignment; no further plan changes required beyond
them.
