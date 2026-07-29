# T018: Out-of-scope defects carded (feature 001-lambda-log-visibility)

Both defects are ALREADY VISIBLE today (not caused by this feature) and are
deliberately NOT fixed here (AR#1 F2 / AR#3 over-masking guardrail). They go
to the owner board follow-up queue alongside the existing cards from the
2026-07-25 incident close.

## Card A — notification entrypoint logs raw event incl. live magic-link token

- `src/lambdas/notification/handler.py:56` — `logger.info(f"Notification
  Lambda invoked: {json.dumps(event)[:500]}")`; magic-link events carry
  recipient email AND the live sign-in token (a bearer credential:
  handler.py:204 builds the link from it). Pre-existing CWE-312.
- Same class, same module logger (INFO since :33, visible today):
  handler.py:170 "Alert email sent to {email}…", :220 "Magic link email sent
  to {email}", error-path lines :173/:197-199/:224 with full email.
- Fix shape (one card): mask emails via the `_mask_email` helper landed by
  feature 001; replace the raw-event dump with a redacted summary
  (notification_type + keys present, never values).

## Card B — Finnhub adapter passes API key as URL query parameter

- `src/lambdas/shared/adapters/finnhub.py:127` — `params={"token":
  self.api_key}`. Key lands in any URL-logging path (httpx INFO — pinned to
  WARNING by feature 001, which closes the ACTIVE path — plus proxies,
  traces, error messages that echo URLs). Tiingo already uses headers
  (tiingo.py:121-122) — same change here.
- Feature 001's httpx pin is a mitigation, not a fix; the key-in-URL pattern
  itself is the defect.

Status: recorded here per T018; to be added to CLEANUP-BOARD.html riders at
the next board update (board edits batch with the next board PR per session
convention).

## Card C — dashboard_import_errors metric filter is dead-on-arrival (found by T005)

- Filter pattern (modules/monitoring/main.tf:30-41) assumes field order
  `[time, request_id, level=ERROR*, ...]`; real runtime lines lead with
  `[LEVEL]`. Metric namespace `SentimentAnalyzer/Packaging` has been EMPTY
  since the filter's creation (2025-12-06) — it has never matched anything.
- Proven consequence: the metrics Lambda crash-looped with
  Runtime.ImportModuleError for 7+ days (26,036 errors/24h) and the CRITICAL
  alarm built for exactly that failure never fired.
- Fix shape: correct the filter pattern to match real line shapes (both
  `[ERROR]`-prefixed app lines AND bare `Runtime.ImportModuleError` platform
  lines), then a positive control proving the metric increments.
- NOTE: the metrics-Lambda crash-loop ITSELF (missing aws-lambda-powertools
  in the ZIP) is fixed IN feature 001's PR (deploy.yml one-line pin, same as
  Feature 1227's ingestion fix) because FR-008/SC-002 are unachievable while
  the function cannot import its handler. The filter fix remains carded.

## Card D — notification hourly digest schedule never fires (found by T023)

- /aws/lambda/preprod-sentiment-notification: zero invocations in 7+ days
  despite modules/eventbridge hourly digest rule. This silence is what hid
  the notification ZIP's missing-powertools ImportModuleError (fixed in the
  001 follow-up PR).
- Fix shape: verify the EventBridge rule state/target/permissions; add an
  invocation-count alarm (metric-based) so a silent scheduled function is
  loud.

## Card E — digest user query fails on preprod (surfaced BY feature 001)

- Every digest run logs `[ERROR] Failed to query digest users` +
  `Failed to get users for digest` (digest_service error path;
  DigestServiceError early-return) — observed on the first successful
  notification invoke after the packaging fixes (2026-07-26 07:12 UTC,
  request 194a506e). Response stays 200 with processed:0 — silent failure.
- Consequence: digest emails can NEVER send on preprod even now that the
  function imports; also blocks the digest_service dark-INFO lines from
  serving as notification's FR-008 evidence (E2E uses C-8 instead until
  this is fixed).
- Fix shape: diagnose the DynamoDB query (likely GSI name/permissions on
  the users table digest index); newly-visible ERROR lines now make this
  loud in CloudWatch.

## Card F — metrics crash-loop round 2 + the verification gap it exposed

- The #965 powertools pin peeled ONE onion layer: 43s later the metrics
  Lambda began failing on `No module named 'aws_xray_sdk'` (powertools
  Tracer lazy-loads it at construction, tracer.py:29) — ~14,600 errors over
  3 days, zero healthy invocations, caught only by the T024 measurement
  sweep. Fixed: aws-xray-sdk==2.14.0 pinned + isolated import simulation
  now part of the fix discipline.
- Verification gap (recorded honestly): the E2E's C-8 assertion PASSED
  throughout — C-8 emits at handler import before Tracer() fails, so it
  proves logging visibility, not function health. E2E now adds a synthetic
  invoke asserting no FunctionError for metrics (and notification already
  has one).
- Standing gap for the board: NO deploy smoke step exercises ZIP-Lambda
  imports (dashboard has one; metrics/notification/canary/ingestion don't),
  and the dead import-error metric filter (Card C) means ImportModuleError
  storms are silent. An import smoke per ZIP Lambda in the deploy pipeline
  would have caught all three onion layers pre-merge.
