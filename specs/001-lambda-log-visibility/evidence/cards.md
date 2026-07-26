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
