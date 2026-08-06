# Card: signed, aggregating sentiment timeseries fanout

Status: PLANNING COMPLETE, READY FOR IMPLEMENTATION, paused for operator quota
reset. Implementation starts only on explicit operator go (First-Feature Gate
passed 2026-08-06). Branch `001-signed-fanout` carries every artifact.

Supersedes specs/001-signed-sentiment-fanout/card.md (folded in below, dir
deleted at consolidation).

## Symptom

The dashboard's sentiment line pins near +1.0 for every ticker, range, and source
mode, so price/sentiment correlation is invisible even where it exists. The chart's
right axis spans -1..1 but the plotted data can never go negative.

## Root cause (verified, refuter-confirmed)

The analysis handler builds the fanout `SentimentScore` with the raw unsigned
model confidence (src/lambdas/analysis/handler.py:480 hop; ~0.9+ regardless of
label), and `write_fanout` overwrites the bucket wholesale on every article
(count==1 in 7,843/7,843 live items, full preprod scan 2026-08-05). The signed
mapping already exists (`_label_to_score`, src/lambdas/analysis/sentiment.py:628)
and the read side is already signed (thresholds +/-0.33, axes -1..1); only the
write path is wrong. CANON docs document the unsigned behavior as intended, so
this feature deliberately amends canon with owner sign-off.

## What exists (all in specs/001-signed-fanout/, uncommitted until this card ships)

spec.md (FR-001..FR-010, SC-001..SC-006, 5 clarifications), research.md (D1-D9),
plan.md, data-model.md, contracts/{bucket-schema,backfill-manifest}.md,
quickstart.md, tasks.md (22 tasks, 100% FR coverage), reviews/{ar1,ar2,ar3}.json.
Three adversarial reviews closed 0 CRITICAL / 0 HIGH; every finding fixed in the
artifacts and graded. tasks.md ends with the AR#3 record and the gate verdict.

## Remaining work

1. On operator go: execute tasks.md T001-T022 in order (TDD inside each story;
   T010/T011/T012 land as ONE change or SSE cold start breaks; the highest-risk
   task is T011, see the AR#3 section of tasks.md).
2. Gates before push: `make validate` and `make test-local` green, GPG commit,
   push feature branch and open the PR in one step, auto-merge --squash only per
   the standing operator authorization. Sub-agents never push.
3. FR-006 CANON doc amendments require owner sign-off before merge (SC-005).
4. Backfill runs per environment ONLY on separate explicit operator go (spec A5);
   the runbook and three-part drain criterion are in quickstart.md and spec
   Clarifications Q3.
5. Open questions for the operator at ship, recorded in tasks.md Gate verdict:
   admin bootstrap apply for the ci-user-policy extension before US3 terraform
   deploys (ar3-002); CloudTrail data events accept/decline; legacy-bucket
   deletion for chart honesty (A3); dormant ingestion-grant drop (enforcement
   half of the version guard, ar2-010); live-path double-count residual
   (candidate future card).
6. After ship: delete this card (cards lifecycle); fold the CLAUDE.md Active
   Technologies entry into docs/ACTIVE-TECHNOLOGIES.md (T020); then the queued
   live-hero-widget battleplan (specs/001-live-hero-widget/card.md), whose hero
   re-shoot waits on this feature's backfilled data.

## Why it matters beyond aesthetics

Alerts and any threshold logic reading these buckets see confidence, not
sentiment: a strongly negative news day looks identical to a strongly positive
one. The README hero re-shoot (specs/001-readme-landing/) and the live hero
widget both want this fixed first.
