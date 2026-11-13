# Feature Specification: Signed, Aggregating Sentiment Timeseries Fanout

**Feature Branch**: `001-signed-fanout`
**Created**: 2026-08-05
**Status**: Draft
**Input**: User description: "Signed, aggregating sentiment timeseries fanout: buckets carry signed sentiment (-1..1) and accumulate per-article instead of overwriting; 30-day backfill from sentiment-items; CANON doc amendments; tests at the handler-to-fanout hop"

## Context

Verified state (research + refuters, this run): the analysis pipeline stores each
article's unsigned model confidence (0.5..1.0) as the bucket value and each new
article's write replaces the bucket wholesale. Full preprod scan 2026-08-05 (7,843
items, paginated scan of the timeseries table): zero buckets with count other than
1, zero with a negative average; re-run that scan to re-establish the premise rather
than trusting this sentence. The bucket-reading consumers (dashboard thresholds at
plus/minus 0.33, chart axes fixed to -1..1, color ramps red-to-green, the dormant
alert evaluator) were built for signed aggregated values, and their negative and
neutral display branches are unreachable from real data. Two consumers this feature
does NOT fix, named so nobody reads them into scope: digest labeling is broken
independently of signedness (its query uses PK/SK key names against a table keyed
source_id/timestamp, so every call raises and falls to a hardcoded 0.0/neutral
fallback; it also reads a field no live writer stores) and needs its own fix; SSE
`sentiment_update` events average per-article scores, which stay unsigned under
FR-008, alongside signed `partial_bucket` events on the same stream; no shipping UI
currently renders `sentiment_update` scores. Bucket writers today are the analysis
role plus a dormant ingestion-role grant (ingestion contains no timeseries code).
The version guard this feature adds binds only writers that opt into its
condition, so an unconditional write through that dormant grant bypasses the
guard and strips the version attribute; dropping the grant is therefore the
enforcement half of the version mechanism, not optional adjacent hardening.
Still the owner's call, separate change.
CANON docs (MODELING.md, SERVICE-SHAPE.md) document the current unsigned behavior as
intended, so this change deliberately amends canon with owner sign-off, not silently.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sentiment direction is visible (Priority: P1)

A dashboard viewer looks at a ticker's sentiment line and can tell good news from
bad: negative-news days plot below zero, positive above, and the line uses the full
range the chart was built for. Sentiment/price correlation becomes visually
assessable, which is the product's core promise.

**Why this priority**: Today the line answers "how confident was the model," which no
user asked. Direction is the product.

**Independent Test**: Ingest one high-confidence negative article for a ticker; the
bucket value and the plotted point are negative; the dashboard labels the day
negative and colors it in the red band.

**Acceptance Scenarios**:

1. **Given** a scored article with a negative label and confidence 0.9, **When** it
   fans out, **Then** every touched bucket's contribution is -0.9.
2. **Given** a neutral-label article, **When** it fans out, **Then** its contribution
   is 0.0.
3. **Given** buckets holding signed values, **When** the dashboard queries them,
   **Then** days at or below -0.33 label negative and days between -0.33 and 0.33
   label neutral (both branches now reachable).

---

### User Story 2 - Days aggregate instead of forgetting (Priority: P2)

On a day with many articles about a ticker, the daily value reflects all of them,
not whichever arrived last. Bucket statistics (count, average, open/high/low/close)
describe the day's articles as a population.

**Why this priority**: Without accumulation, signed values still misrepresent any
multi-article day; the two defects only make sense fixed together.

**Independent Test**: Score three articles (labels positive 0.8, negative 0.9,
positive 0.6) into one bucket window; the bucket ends with count 3, sum 0.5,
average ~0.167, high 0.8, low -0.9, label_counts {positive: 2, negative: 1}.

**Acceptance Scenarios**:

1. **Given** an existing bucket with count N, **When** another article in the same
   window fans out, **Then** count becomes N+1 and sum/avg/extremes update; nothing
   is overwritten.
2. **Given** the same article delivered twice by the messaging layer, **When** the
   second delivery is processed, **Then** the bucket does not double-count (the
   existing already-analyzed guard prevents re-fanout).

---

### User Story 3 - Recent history is repaired (Priority: P3)

After the change ships, a viewer sees a signed, aggregated trailing month, not a flat
line that only starts moving today. History older than the repairable window behaves
predictably and ages out on its own.

**Why this priority**: The chart is the repo's public face (README hero re-shoot
waits on this); an empty month of signed data delays that by weeks.

**Independent Test**: Run the backfill against an environment; trailing-30-day
buckets show signed averages and counts greater than 1 on multi-article days;
re-running the backfill produces identical buckets (idempotent).

**Acceptance Scenarios**:

1. **Given** retained per-article records for the trailing 30 days, **When** the
   backfill runs, **Then** every resolution bucket whose window falls inside those
   30 days is recomputed from scratch with signed contributions.
2. **Given** buckets older than the repairable window, **When** the backfill runs,
   **Then** they are left untouched and expire via their existing TTLs.
3. **Given** a completed backfill, **When** it is run again, **Then** bucket contents
   are unchanged (recompute-from-source, not increment).

---

### Edge Cases

- Re-delivered message after a crash between item-update and fanout: the guard that
  makes fanout once-per-article also means a crash in that gap loses the fanout
  contribution permanently (pre-existing behavior; unchanged by this feature but now
  it skews an aggregate rather than a single-article bucket).
- All-negative day: open/high/low/close must order correctly with negative values
  (high is the least negative).
- Neutral articles pull averages toward zero by design; a day of one positive and
  one neutral article halves the average. Documented, intended.
- Backfill racing live ingestion: recompute-from-source alone does not close the
  race. A live fanout landing between the backfill's read and write is clobbered
  (unrecoverable through the normal path, because the analyzed gate forecloses
  re-fanout), and one landing after the backfill's write double-counts. Because
  bucket windows key off publisher-controlled article timestamps (live data holds
  buckets dated 2017 and tomorrow), no settle horizon makes any window quiescent.
  The protocol is therefore quiescence: the analysis path is stopped and drained for
  the backfill's duration (FR-004). Conditional writes could close the first
  interleaving but not the second, which is why quiescence is the mechanism.
- Partial accumulation failures: accumulation cannot use wholesale batch puts, so
  the failure mode is a multi-step per-bucket update crashing partway (some
  statistics updated, others not) or throttling mid-resolution-set. Failures must
  surface loudly, and the plan must produce a crash-consistent accumulation design;
  the existing unwired candidate updates count and sum but never the average that
  every consumer reads, and is not acceptable as-is (FR-002, FR-009).
- Mixed epoch on screen: for up to 60 days, daily buckets older than the backfill
  window still carry unsigned values next to newer signed ones. Disposition:
  untouched (Assumption A3), self-healing via TTL.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every bucket contribution MUST be the signed sentiment of its article:
  positive label contributes +confidence, negative contributes -confidence, neutral
  contributes 0.0.
- **FR-002**: Concurrent and successive articles in the same bucket window MUST
  accumulate: count increments, sum adds, extremes widen, label counts merge, and
  open/close follow article-timestamp order (one ordering basis for live writes and
  backfill alike). No fanout write may replace a bucket wholesale. The bucket's
  average MUST be correct after every accepted write: maintained on write or
  derived from sum and count by readers, decided at plan time with a
  crash-consistent design.
- **FR-003**: Each analyzed article MUST contribute to each bucket at most once,
  surviving message re-delivery (the existing analyzed-status gate is the mechanism;
  it MUST remain on the path guarding fanout).
- **FR-004**: A one-off, re-runnable backfill MUST recompute, from retained
  per-article records, every bucket whose full window lies inside the retention
  horizon (trailing ~30 days) AND whose computed TTL is still in the future;
  fine resolutions whose windows have already expired are not recreated. The
  backfill MUST run with the analysis path quiesced (consumer stopped, in-flight
  invocations drained) for its duration; SC-004's identical-on-repeat property is
  claimed under quiesced conditions only. The backfill MUST run under a named role
  scoped to reading the items table, reading and writing the timeseries table, and
  operating the quiescence controls (ingestion rule disable/enable, CloudWatch
  metric reads; research.md D6 is the authoritative grant list), and MUST emit
  a run manifest (start/end, windows covered, per-resolution bucket counts,
  failures) that the operator keeps; enabling CloudTrail data events is offered to
  the owner as an explicit accept/decline.
- **FR-005**: Buckets not covered by FR-004 MUST be left untouched and age out via
  existing TTLs. No destructive deletion without separate operator approval.
- **FR-006**: Every CANON statement falsified by this change MUST be amended in the
  same change set. Known-falsified floor (the sweep at review time, not the
  definition of done): MODELING.md's score-is-a-probability section (amended to
  split item claims, which stay unsigned, from bucket claims, which become signed);
  the single MODELING.md sentence "There is no replay, rescore or backfill path in
  src/" (the surrounding re-running-inference claims stay true because the backfill
  recomputes aggregates from stored labels without re-running inference, and the
  amendment says so); SERVICE-SHAPE.md's output-schema warning; README.md's
  confidence wording; the two handler docstrings asserting 0.0-1.0; the fanout
  module and write_fanout docstrings (the latter already falsely promises an
  UpdateItem fallback); the timeseries models' field descriptions including the
  sources description. Riding the change set as labeled pre-existing drift repair,
  not feature fallout: the api_v2.py module docstring's claim of a historical
  backfill endpoint that has never existed. Owner sign-off gates the doc
  amendments.
- **FR-007**: Tests MUST pin the new semantics at the previously untested
  handler-to-fanout hop, the accumulation behavior, sign mapping for all three
  labels, backfill idempotency, and at least one fanout failure path (partial
  accumulation failure surfaces loudly and is repairable per FR-009).
- **FR-008**: The change MUST NOT alter the per-article stored record's score field
  (it remains unsigned confidence with a separate label; only the timeseries
  contribution is signed). Consumers of per-article records are out of scope.
- **FR-009**: Fanout failures MUST be observable AND recoverable: a failed
  contribution is recorded (ticker + window) so a targeted backfill run for that
  window repairs it; recompute-from-source already heals this class. Each targeted
  repair inherits FR-004's quiescence, so a repair implies a brief analysis outage,
  an accepted cost. Today's behavior (warning plus a metric, contribution lost
  forever behind the analyzed gate) stops being acceptable once buckets are
  population aggregates.
- **FR-010**: Article timestamps MUST be bounded before they key a bucket write:
  timestamps in the future or older than the items retention horizon are rejected
  or clamped, loudly. Live data proves mis-dated arrivals occur (buckets dated
  2017 and tomorrow exist); under accumulation a mis-dated article would skew a
  population aggregate with no removal path. Residual risk accepted: within the
  valid window, publisher-controlled dates still choose the bucket, which is
  inherent to publishing time-bucketed sentiment.

### Key Entities

- **Timeseries bucket**: per ticker+resolution+window aggregate; count, sum, avg,
  open/high/low/close, label_counts, sources, TTL. Value semantics change from
  "last article's confidence" to "signed population statistics". Under accumulation
  `sources` becomes a bounded, deduplicated set of provider names (today it grows
  one per-article dedup id per write, which the source filter can never match); its
  model description is amended in the FR-006 sweep.
- **Sentiment item**: per-article record; label + unsigned confidence; retained ~30
  days; the backfill's source of truth. Unchanged by this feature (FR-008).
- **Signed sentiment**: derived value in [-1, 1]; sign from label, magnitude from
  confidence; neutral is exactly 0.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A negative-label article produces a negative plotted point; the
  dashboard's negative and neutral display branches are exercised by real data,
  with a synthetic article as fallback if the news cycle provides none at
  verification time (observable on the chart and in API responses).
- **SC-002**: On a day with N>1 articles for a ticker, the daily bucket reports
  count N and an average equal to the mean of the signed contributions (spot-checked
  against source records).
- **SC-003**: After backfill, the trailing 30 days of a high-volume ticker show at
  least one day with count > 1, and daily averages equal signed recomputation from
  source records (guaranteed properties; baseline is the dated full scan in
  Context, re-run at verification time). Label mix (a negative or neutral day
  appearing) is a spot-check with a synthetic-article fallback, because a genuinely
  positive news month is not a defect.
- **SC-004**: Under quiesced conditions and an unchanged item set, re-running the
  backfill changes zero bucket values (backfill-vs-backfill comparison).
- **SC-005**: No CANON document contains a statement the shipped behavior falsifies;
  the FR-006 list is the verified floor, not the definition, and the amended docs
  carry owner sign-off.
- **SC-006**: Bucket-derived consumer endpoints (streaming partial buckets,
  dashboard timeseries, sentiment history) return signed values in [-1, 1]
  consistent with recomputation from source records, in the full test suite and a
  live smoke check. Digest and streaming `sentiment_update` events are exempt per
  FR-008 (out of scope, defects independently recorded).

## Assumptions

- **A1**: The existing signed mapping (positive +confidence / negative -confidence /
  neutral 0.0) is the correct semantics; it already exists in the codebase and
  matches every consumer's expectations. No new scale is invented.
- **A2**: The analyzed-status conditional write remains the idempotency mechanism
  for fanout; no new dedup layer is introduced.
- **A3**: Legacy unsigned buckets outside the backfill window are left in place.
  Deleting them is destructive and reversible only by losing data; TTL removes them
  within 90 days of the cutover. If the operator prefers deletion for chart honesty,
  that is a separate approval at ship time.
- **A4**: Backfill covers all resolutions whose windows fit inside item retention;
  in practice the finest resolutions have short TTLs and mostly age out before
  backfill matters. Daily (24h) buckets are the ones that matter for the chart.
- **A5**: The change deploys through the existing pipeline to both environments;
  the backfill is run per environment by the operator's explicit go.

## Adversarial Review #1

Reviewer subagent, 7 numbered actions (spec read, code cross-check, live
re-measurement, contradiction attack, S2 angles, basic rigour, CANON completeness).
Verdict: 0 CRITICAL, 3 HIGH, 5 MEDIUM, 4 LOW. Per-item record with evidence in
reviews/ar1.json; reviewer and refuter raw trails in their handoff journals.

| ID | Sev | Finding | Adjudication | Disposition |
|---|---|---|---|---|
| ar1-001 | HIGH | Backfill/live race unsolved; SC-004 self-contradictory | Refuted-and-confirmed; settle horizon rejected (publisher-controlled timestamps) | fixed: quiescence protocol in FR-004, edge case, SC-004 |
| ar1-002 | HIGH | FR-006 CANON list incomplete; SC-005 self-certifying | PARTIAL: only the single no-backfill sentence falsified; two fanout docstrings added | fixed: FR-006 expanded precisely, SC-005 floor wording |
| ar1-003 | HIGH | Context promises fixes to consumers that never read buckets | PARTIAL: digest broken worse than reviewed (wrong keys, then absent field); keep out of scope | fixed: Context corrected, SC-006 strengthened; digest carded separately |
| ar1-004 | MEDIUM | Accumulation mechanism unspecified; candidate never updates avg | recorded | fixed: FR-002 avg clause, edge case rewritten |
| ar1-005 | MEDIUM | Fanout failure observable but unrecoverable | recorded | fixed: FR-009 added, FR-007 failure test |
| ar1-006 | MEDIUM | FR-004 obligated writing dead expired buckets | recorded | fixed: TTL-future scope |
| ar1-007 | MEDIUM | Unvalidated publisher timestamps key buckets | recorded | fixed: FR-010 added |
| ar1-008 | MEDIUM | Backfill identity/audit unspecified | recorded | fixed: scoped role + run manifest in FR-004 |
| ar1-009 | LOW | Writer set unstated; dormant ingestion grant | recorded | fixed: Context note; grant drop deferred to owner |
| ar1-010 | LOW | SC-003 news-cycle dependent; stale sample citation | recorded | fixed: SC-003 split, dated full-scan premise |
| ar1-011 | LOW | Mixed OHLC ordering semantics | recorded | fixed: single article-timestamp basis in FR-002 |
| ar1-012 | LOW | sources semantics undefined under accumulation | recorded | fixed: Key Entities + FR-006 sweep |

Each HIGH was adjudicated by an independent refuter briefed with numbered actions
(verdicts: CONFIRMED, PARTIAL, PARTIAL; fixes SUFFICIENT-WITH-AMENDMENT, amendments
binding and applied). The full applied edit set was graded by a fourth agent that
proposed none of it: 12/12 faithful, ar1-002 precision check PASS, zero
contradictions, dash scan clean after 7 mechanical rewordings.

Gate statement: 0 CRITICAL, 0 HIGH open. Per-item record in reviews/ar1.json;
adjudication and grading artifacts in the run's handoff directories. Stage 2 gate:
OPEN.

## Clarifications

### Session 2026-08-05

- Q: What is `is_partial`'s contract under accumulation? -> A: Unchanged: every
  fanout write sets it True and readers compute completeness at query time.
  Evidence: the dashboard explicitly distrusts the stored flag because "the fanout
  writer always sets is_partial=True" (src/lambdas/dashboard/timeseries.py:131-132,
  366-368); stored False means explicitly complete. Accumulation keeps writing
  True; no clearing pass exists or is added.
- Q: Are the SNS message's provider names reliable ground truth for the bucket
  `sources` set? -> A: Yes. Ingestion includes the provider in the SNS body as
  `"sources": [source]` (src/lambdas/ingestion/handler.py:1043), where `source` is
  the per-provider fetch's source_type carrying exactly "tiingo" or "finnhub"; the
  module docstring (handler.py:11) documents the format. The analysis handler
  currently ignores that field; D8 starts reading it.
- Q: What is the concrete drain criterion for backfill quiescence? -> A: Three
  conditions on the analysis Lambda, all read by the preflight via CloudWatch
  GetMetricData: (1) zero Invocations for 240 seconds after the ingestion rule is
  disabled (2x the Lambda's 120s timeout, infrastructure/terraform/main.tf:382);
  (2) zero Throttles over the trailing 6 hours, the default async maximum event
  age, which nothing bounds here because the function has no
  aws_lambda_function_event_invoke_config; (3) zero Errors over the trailing 30
  minutes. Invocation silence alone does not prove drain: SNS invokes analysis
  asynchronously, and a throttled or errored delivery waits in Lambda's internal
  retry queue, invisible to the Invocations metric, for up to the maximum event
  age before redelivery. A pending retry can exist only if an earlier attempt
  throttled or errored, so clean trailing windows on those two metrics prove the
  queue empty; error retries resolve within minutes while throttle retries can
  back off for hours, hence the two window lengths. The trailing windows are
  evaluated after the 240 second wait completes, because CloudWatch metric
  delivery lags by about a minute. If a trailing check fails, wait until the
  newest offending datapoint ages out of its window before starting.
- Q: How does the backfill interact with the `version` attribute? -> A: Read each
  bucket, write the recomputed complete state conditionally on the version read
  (or attribute_not_exists(version) when the read found no version, which covers
  new buckets and existing pre-cutover buckets that predate the attribute),
  incrementing it. Quiescence makes contention impossible, so the condition costs
  nothing; it exists as defense in depth so a quiescence violation fails loudly
  (ConditionalCheckFailed in the manifest's failures list) instead of silently
  clobbering a live write. The condition binds cooperating writers only;
  enforcement against a non-cooperating writer is the dormant-grant drop (Context).
- Q: Do neutral (0.0) contributions participate in OHLC extremes? -> A: Yes.
  Neutral articles are full population members: count, label_counts, sum, avg,
  and open/high/low/close all include the 0.0 contribution. Excluding them from
  extremes while counting them in avg would make bucket statistics mutually
  incoherent; the spec already treats neutral's pull toward zero as intended
  (Edge Cases).
