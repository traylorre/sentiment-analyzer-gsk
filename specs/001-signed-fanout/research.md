# Research: Signed, Aggregating Sentiment Timeseries Fanout

Decisions for every open technical question in plan.md. Evidence base: this run's
verified research and refuter records (reviews/ar1.json and the handoff journals),
plus the cited code.

## D1. Accumulation mechanism: optimistic concurrency, one atomic write per bucket

**Decision**: Read the bucket, compute the complete next state locally (count, sum,
avg, open/high/low/close by article-timestamp order, label_counts, sources), write
it with a single conditional PutItem guarded on a `version` attribute. The guard
has two branches, chosen by what the read returned: `ConditionExpression:
version = :expected` when the read returned a version, and `ConditionExpression:
attribute_not_exists(version)` when it did not. The second branch covers both
absent buckets and existing pre-cutover buckets, which predate the attribute;
DynamoDB evaluates attribute_not_exists as true for a missing item as well, so
no separate attribute_not_exists(PK) creation branch exists. Race safety: two
writers that both read a version-less bucket cannot both succeed, because the
first successful put creates `version` and the second writer's
attribute_not_exists(version) then fails. On ConditionalCheckFailedException,
re-read and retry (bounded, with jitter). One write per article per bucket; the bucket is always internally
consistent because every write is a complete state at a single version.

**Rationale**: FR-002 requires every statistic correct after every accepted write,
including avg and timestamp-ordered open/close. DynamoDB UpdateExpressions cannot
compute max/min/avg server-side, so any expression-based approach either splits one
logical update across multiple non-atomic calls (the rejected
`write_fanout_with_update` shape: crash leaves count updated, extremes not, avg
never) or cannot maintain the derived fields at all. Optimistic concurrency makes
crash-consistency structural: a crash before the write changes nothing; after,
everything. Contention is negligible at this volume (thousands of articles/day
across ~1,500 tickers); retries are rare and bounded. Read-before-write doubles
request count but on-demand billing at this scale is cents. The version guard is
cooperative, not enforced: it binds only writers that use the condition. The
dormant ingestion-role grant (spec Context) can write unconditionally past it and
would strip the version attribute, so dropping that grant is the enforcement half
of this mechanism, still the owner's call.

**Alternatives considered**:
- Single UpdateItem with ADD count/sum + document-path ADD label_counts: atomic for
  those fields, but open/high/low/close/avg unmaintainable server-side; readers
  deriving avg=sum/count would fix avg alone, leaving OHLC broken. Rejected.
- Repair `write_fanout_with_update` (4 sequential UpdateItems): still non-atomic
  across statistics; crash windows remain; AR#1 adjudication bars it as-is. Rejected.
- DynamoDB transactions (TransactWriteItems around per-statistic updates): atomic
  but still cannot compute max/min/avg server-side, so it degenerates to
  read-modify-write anyway, at 2x write cost. Rejected.
- Per-article ledger items + on-read aggregation: unbounded item growth per bucket
  window and a read-path rewrite in every consumer. Rejected as blast-radius
  expansion.

## D2. Signed mapping: one shared function, used by handler and backfill

**Decision**: Extract the existing `_label_to_score` logic (positive -> +confidence,
negative -> -confidence, neutral -> 0.0) into `src/lib/timeseries/signed.py` as
`label_to_signed(label, confidence)`. `analysis/sentiment.py` keeps `_label_to_score`
as a thin delegate (its test-only aggregation callers keep working); the handler
calls the lib function at the fanout hop; the backfill imports the same function.

**Rationale**: The mapping must be bit-identical between live fanout and backfill or
SC-004's recompute-equality breaks. Two copies of a three-branch function is how the
current split-brain happened. Placement constraint, stated as the invariant the
build actually enforces: SSE transitively imports this package at every cold start
(sse_streaming/handler.py:42, stream.py:42 and polling.py:231 import
src.lib.timeseries, whose __init__ imports fanout), and that survives because the
SSE Dockerfile copies lib/timeseries as a whole directory while copying top-level
lib files individually (docs/ci-gotchas.md). signed.py therefore ships to SSE
automatically, and fanout.py/signed.py MUST NOT import any top-level src/lib
module other than metrics.py, the only top-level lib file the SSE image copies
(fanout.py:21 imports src.lib.metrics today). Any other top-level lib import
breaks SSE at cold start.

## D3. FR-010 bounds: reject, don't clamp, at the handler before fanout

**Decision**: In the analysis handler, before fanout: reject timestamps > now + 5
minutes (clock skew allowance) or older than the items retention horizon (30 days).
Rejection skips fanout only (the per-article record still stores, FR-008), logs a
structured warning with ticker and offending timestamp age (no raw text, constitution
sec 2), and increments a `TimeseriesFanoutRejectedTimestamp` metric.

**Rationale**: Clamping fabricates a time the publisher never claimed and silently
relocates sentiment to the wrong bucket, which is worse than absence under
population statistics. Rejects are loud (basic rigour) and bounded article loss is
acceptable: mis-dated articles are rare (live evidence: single-digit occurrences in
a 7,843-item table) and were already producing wrong buckets. The 30-day floor
matches the backfill horizon so no rejected article was repairable anyway.

## D4. FR-009 recording: structured log + metric, repair via targeted backfill

**Decision**: On fanout failure after retries, emit one structured log record
(ticker, resolution, window, error class) and increment the existing
`TimeseriesFanoutErrors` metric unchanged, with no added dimension: dimensions are
part of a CloudWatch metric's identity, so a dimensioned emission would create new
series that anything watching the existing metric never sees, and per-window
dimension values are unbounded billed cardinality. The structured log record
carries the window. The runbook section
in quickstart.md documents the repair: run the backfill for that ticker/window.
No new persistence.

**Rationale**: A failure table is more machinery than the failure rate justifies
(basic rigour, not full). Logs Insights over the analysis log group answers "which
windows need repair" directly; the backfill is idempotent per-window so
over-repairing is harmless. Owner's no-alarms stance (memory) means no alarm is
wired; the metric exists for dashboards and manual checks.

## D5. Quiescence: disable the ingestion schedule, drain, backfill, re-enable

**Decision**: The backfill script's runbook (and its preflight check) requires:
disable the EventBridge ingestion schedule rule, wait for drain per the
three-part criterion in spec Clarifications Q3 (240 seconds of zero Invocations
after disable, zero Throttles over the trailing 6 hours, zero Errors over the
trailing 30 minutes, all via CloudWatch GetMetricData), run, re-enable. The script refuses to start if the rule is still enabled
unless `--force` (logged in the manifest).

**Rationale**: Stopping the source (ingestion schedule) quiesces the entire
downstream path with one reversible switch and loses nothing: news accumulates at
the publishers and the next scheduled ingestion pull catches up (the ingestion
window queries by published-time range). Alternatives: reserved concurrency 0 on the
analysis Lambda leaves SNS retrying/DLQing deliveries (lossy, messy to replay);
disabling the SNS subscription drops messages outright. Rejected both.

The trailing-window conditions exist because disabling the rule stops new work
but not Lambda's internal async retry queue: SNS delivery to analysis is
asynchronous, the function has no aws_lambda_function_event_invoke_config, and a
throttled event can redeliver up to 6 hours later (the AWS default maximum event
age), mid-backfill. The version condition makes the clobber direction loud
(ConditionalCheckFailed into the manifest); the silent direction is a
redelivered event whose first attempt had already stored the item and
accumulated the fanout before failing, which the backfill then recomputes into
the bucket and the redelivery re-accumulates, a double count nothing detects.
Zero Throttles and zero Errors over the trailing windows prove no retry is
pending, read-only, using metrics Lambda always emits; the newer async-queue
metrics cannot serve here because AsyncEventsReceived is not emitted for retries
and AsyncEventAge only emits when a delivery attempt occurs, so both stay silent
about an event backing off in the queue. Escalation when the operator cannot
wait out a dirty trailing window: temporarily set maximum event age to 60
seconds on the analysis function (PutFunctionEventInvokeConfig, run under the
operator principal, not the backfill role), wait out the 240 second silence,
run, then delete the config. This drops still-pending events to the existing
SQS DLQ permanently; their articles were never analyzed and ingestion dedup will
not re-pull them, which is why it is escalation and not the default. Accepted
residuals: Lambda-internal system errors can requeue an event without
incrementing Errors or Throttles (rare, still bounded by the 6 hour event age),
and a partially completed retry double counts on the live path at any time
regardless of quiescence, because accumulation has no per-article idempotency
key; SC-003 style spot recompute is the detection for both.

## D6. Backfill identity: new scoped IAM role, assumed by the operator

**Decision**: Terraform adds the `${environment}-backfill-timeseries-role` role
(env-prefixed per iam-module convention; both environments deploy from one
account): Query/Scan on
`sentiment_items`, PutItem/GetItem on `sentiment_timeseries`, DescribeRule/
DisableRule/EnableRule on the ingestion schedule rule, CloudWatch GetMetricData for
the drain check. Trust policy: the account's operator principal. The script runs
under `aws sts assume-role` into it; the manifest records the assumed-role ARN and
session name.

**Rationale**: FR-004 requires a named scoped identity; this is the least-privilege
set the script's actions need. One grant is necessarily account-wide:
cloudwatch:GetMetricData supports no resource-level scoping, so the drain check is
granted on Resource '*', an accepted cost of the metric-based preflight; every
other grant stays resource-scoped (the rule ARN and the two table ARNs). CloudTrail data events are offered to the owner as
an explicit accept/decline at ship (cost of data events on two tables is nontrivial
relative to this project's bill; management-plane events already cover the
rule disable/enable).

## D7. Legacy `write_fanout` / `write_fanout_with_update`: delete both from the live path

**Decision**: `accumulate_fanout()` (new, D1 semantics) becomes the only fanout
writer. `write_fanout` is deleted rather than kept for "new bucket" fast-pathing;
`write_fanout_with_update` is deleted rather than repaired. Their tests are
rewritten against `accumulate_fanout`, not migrated.

**Rationale**: One implementation, one semantics (senior-audience standard: correct
abstraction over preserved code). The conditional-create branch of D1 covers the
new-bucket case the batch writer served. Keeping dead variants invites the next
agent to wire the wrong one, which is the exact failure mode that produced this
feature.

## D8. `sources` under accumulation: deduplicated provider names, bounded

**Decision**: The bucket's `sources` becomes a string set of provider names
(`tiingo`, `finnhub`), deduplicated by the set type itself, populated from the
article's provider (already carried in the SNS message `sources` field, verified:
ingestion includes it; the analysis handler currently ignores it and passes the
`dedup:` source_id instead). The `dedup:` id stops being written to buckets.

**Rationale**: Fixes ar1-012's unbounded growth and gives the dashboard source
filter (`001-source-attribution-dead` card) real data to match against without
expanding this feature's scope into the filter itself: writing correct provider
names is this feature's side of the boundary (it owns the bucket write path);
fixing the filter/UI stays carded. String set gives free dedup and bounded size
(2 providers).

## D9. Mixed-epoch history: leave in place (spec A3 confirmed)

**Decision**: No deletion of legacy unsigned buckets; TTL ages them out within 90
days. The dashboard renders a visually coherent but semantically mixed line for up
to 60 days beyond the backfill window.

**Rationale**: Deletion is destructive and gated on separate operator approval the
spec already records. The affected range is the oldest third of the daily chart,
shrinking daily. Documented in MODELING.md's amendment so the mixed window is
canon-visible with its end date.
