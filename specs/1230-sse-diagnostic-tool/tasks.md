# Tasks: SSE Diagnostic Tool

**Input**: Design documents from `/specs/1230-sse-diagnostic-tool/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included per constitution requirement.

**Organization**: Single script with incremental feature additions per user story.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — SSE Parser + CLI Skeleton

**Purpose**: Core SSE protocol parser and CLI argument handling. Everything else builds on this.

- [x] T001 Create `scripts/sse_diagnostic.py` with CLI skeleton: argparse with positional `url` argument, optional `--token`, `--user-id`, `--event-type`, `--ticker`, `--json`, `--timeout` (default 0 = unlimited) options; `main()` entry point; shebang line `#!/usr/bin/env python3`
- [x] T002 Implement SSE protocol parser function `parse_sse_stream(response)` in `scripts/sse_diagnostic.py` — read lines from HTTP response, parse `event:`, `data:`, `id:`, `retry:` prefixes, yield `(event_type, data_dict, event_id)` tuples on empty line dispatch; handle multi-line `data:` fields; skip comment lines (`:` prefix)
- [x] T003 Implement HTTP connection function `connect(url, token, user_id, last_event_id)` in `scripts/sse_diagnostic.py` — use `urllib.request.urlopen` with `Accept: text/event-stream` header; add `Authorization: Bearer {token}` if token provided; add `X-User-ID: {user_id}` if user_id provided; add `Last-Event-ID: {id}` if resuming; return streaming response; handle connection errors (401→"Authentication required", 503→parse Retry-After, other→connection error message)

**Checkpoint**: Script connects to SSE endpoint and parses events into structured tuples.

---

## Phase 2: User Story 1 — Connect and Display Live Events (Priority: P1) 🎯 MVP

**Goal**: Run the tool, see formatted events in real time.

**Independent Test**: `python scripts/sse_diagnostic.py http://localhost:8000/api/v2/stream` shows heartbeat events within 30s.

- [x] T004 [US1] Implement event formatters in `scripts/sse_diagnostic.py` — one function per event type: `format_heartbeat(data)` shows connections + uptime; `format_metrics(data)` shows totals + rates; `format_sentiment_update(data)` shows ticker + score + label + source; `format_partial_bucket(data)` shows ticker + resolution + progress + OHLC; `format_deadline(data)` shows reason. Each prefixed with `[HH:MM:SS]` timestamp and event type label
- [x] T005 [US1] Implement main event loop in `scripts/sse_diagnostic.py` — connect to URL, iterate `parse_sse_stream()`, call appropriate formatter, print to stdout; handle `KeyboardInterrupt` (Ctrl+C) for clean shutdown
- [x] T006 [US1] Write unit tests in `tests/unit/test_sse_diagnostic.py` — test cases: (1) parse_sse_stream correctly parses heartbeat event from raw SSE text, (2) parse_sse_stream handles multi-line data, (3) format_heartbeat produces expected output string, (4) format_sentiment_update produces expected output with ticker/score/label, (5) connect raises clear error on 401 response. Mock urllib responses, use fixed timestamps

**Checkpoint**: `python scripts/sse_diagnostic.py URL` shows live events. `make test-local` passes.

---

## Phase 3: User Story 2 — Filter Events (Priority: P2)

**Goal**: `--event-type` and `--ticker` flags reduce output to matching events only.

- [x] T007 [US2] Implement `should_display(event_type, data, args)` filter function in `scripts/sse_diagnostic.py` — if `args.event_type` set, skip events not matching; if `args.ticker` set, skip events whose data doesn't contain that ticker (check `data.get("ticker")` and `data.get("by_tag", {})` keys); return True/False
- [x] T008 [US2] Wire filter into main event loop — call `should_display()` before formatting; only print matching events
- [x] T009 [US2] Add filter tests to `tests/unit/test_sse_diagnostic.py` — test cases: (1) event_type filter passes matching events, blocks non-matching, (2) ticker filter passes events with matching ticker, blocks others, (3) combined filter requires both match, (4) no filter passes all events

**Checkpoint**: `--event-type sentiment_update --ticker AAPL` shows only AAPL sentiment updates.

---

## Phase 4: User Story 3 — Session Summary (Priority: P3)

**Goal**: Ctrl+C prints event counts, duration, and health warnings.

- [x] T010 [US3] Implement `SessionStats` class in `scripts/sse_diagnostic.py` — tracks: start_time, event_counts (dict by type), last_heartbeat_time, reconnect_count, total_events; method `record_event(event_type)` increments counters; method `summary()` returns formatted string with duration, per-type counts, total, and heartbeat health check (warn if gap > 60s)
- [x] T011 [US3] Wire `SessionStats` into main loop and signal handler — create stats at start, call `record_event()` for each event, register `signal.SIGINT` handler that prints `stats.summary()` then exits cleanly
- [x] T012 [US3] Implement reconnection logic in `scripts/sse_diagnostic.py` — on connection drop, retry up to 3 times with exponential backoff (1s, 2s, 4s); send `Last-Event-ID` header on reconnect; increment `reconnect_count` in stats; after 3 failures, print summary and exit with error
- [x] T013 [US3] Add summary + reconnection tests to `tests/unit/test_sse_diagnostic.py` — test cases: (1) SessionStats correctly counts events by type, (2) summary includes duration and per-type breakdown, (3) heartbeat gap warning triggers when gap > 60s, (4) reconnection sends Last-Event-ID header

**Checkpoint**: Ctrl+C prints health summary. Reconnection works on connection drop.

---

## Phase 5: Polish

- [x] T014 Implement `--json` output mode in `scripts/sse_diagnostic.py` — when `--json` flag set, print each event as a single JSON line (JSONL) instead of formatted output; include event_type, event_id, timestamp, and data fields
- [x] T015 Run `make validate` — verify linting, formatting pass for new files
- [x] T016 Run `make test-local` — verify all tests pass
- [x] T017 Manual verification: run tool against local dev server (`python scripts/sse_diagnostic.py http://localhost:8000/api/v2/stream`) and confirm events display correctly

---

## Dependencies & Execution Order

```
Phase 1: Foundational (T001-T003)
    ↓ (BLOCKS ALL)
Phase 2: US1 — Display Events (T004-T006)
    ↓
Phase 3: US2 — Filtering (T007-T009)
    ↓
Phase 4: US3 — Summary + Reconnection (T010-T013)
    ↓
Phase 5: Polish (T014-T017)
```

All phases are sequential (single file, each builds on previous).

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1: Parser + CLI skeleton (T001-T003)
2. Phase 2: Event display (T004-T006)
3. **STOP**: Tool connects and shows events — immediately useful

### Full Delivery

- 17 tasks total
- Single file: `scripts/sse_diagnostic.py` (~300 lines estimated)
- Single test file: `tests/unit/test_sse_diagnostic.py`
