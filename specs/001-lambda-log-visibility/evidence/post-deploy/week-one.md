# T026 Week-One Watch — secret/PII/DEBUG leak patterns

Window under watch: 2026-07-26T07:35Z (fix fully live) → end of week one
(~2026-08-02). Days 4–7 append below.

Patterns, per log group (`filter_log_events`, full pagination, window start
2026-07-26T07:35Z):

- `"token="` — expect 0 (secret leak; SC-001/SC-002 hygiene)
- email heuristic — union of `"@gmail.com"` hits and `"sent to"` hits; any FULL
  email in a line emitted by `sendgrid_service` = FAIL; masked `s***@` forms OK;
  full emails from the KNOWN pre-existing entrypoint lines `handler.py:170/220`
  recorded-not-endorsed
- `"[DEBUG]"` — expect 0 (SC-004)

## Day 3 — 2026-07-29T14:08Z (window 07-26T07:35Z → 07-29T14:08Z)

| group | `token=` | email: `@gmail.com` | email: `sent to` | full emails | masked | `[DEBUG]` |
|---|---|---|---|---|---|---|
| dashboard | 0 | 0 | 0 | 0 | 0 | 0 |
| ingestion | 0 | 0 | 0 | 0 | 0 | 0 |
| analysis | 0 | 0 | 0 | 0 | 0 | 0 |
| metrics | 0 | 0 | 0 | 0 | 0 | 0 |
| notification | 0 | 0 | 0 | 0 | 0 | 0 |
| canary | 0 | 0 | 0 | 0 | 0 | 0 |

**Verdict (day 3): PASS across all six groups, all three patterns.** Zero hits
everywhere, so nothing to redact and no full-vs-masked adjudication needed.

Notes:

- The notification group is now actually logging (it was silent pre-deploy), and its
  new lines in the window include digest-query errors but no email-bearing lines —
  the sendgrid_service send path and the handler.py:170/220 entrypoint lines did not
  fire in this window, so the email check is clean-by-absence there, not
  clean-by-masking. Re-check on a day a digest actually sends.
- The metrics group's high event volume in the window is its ongoing
  `aws_xray_sdk` ImportModuleError crash loop (see t024-consumer-comparison.md §2);
  none of the watch patterns appear in it.
- Collection identity `sentiment-analyzer-preprod-deployer`; no AWS denials during
  this day's collection.

<!-- Day 4–7 entries: append below this line, same table + verdict format. -->
