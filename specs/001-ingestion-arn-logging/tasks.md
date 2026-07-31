# Tasks: Stop Ingestion Handler Logging Secret ARNs

**Input**: Design documents from `/specs/001-ingestion-arn-logging/`
**Prerequisites**: `spec.md` (with Adversarial Review #1 and Clarifications Q1 to Q4), `plan.md` (with Adversarial Review #2), `research.md` (D1 to D7), `codeql-logging-convention.md`, `checklists/requirements.md`

**Organization**: Tasks are grouped by user story. US1 (P1) is the defect fix and its regression guard. US2 (P2) is closure evidence, which is only evaluable after the change reaches the default branch. US3 (P3) is the reusable convention.

---

## Standing riders (apply to EVERY task)

1. **`make validate` is NOT a gate for this feature and no task may require it to be green.**
   `scripts/check-banned-terms.sh` exits 1 on 17 pre-existing matches from other features' files,
   measured by execution 2026-07-30: `specs/1157-auth-cache-headers/` **9** (research.md 5, plan.md 3,
   spec.md 1), `.secrets.baseline` **3**, `docs/cleanup/diagram-drift.md` **2**, `CLEANUP-BOARD.html`
   **2**, `specs/1268-cors-404-headers/plan.md` **1**. (Adversarial Review #3 finding R9 corrected this
   list: the three-file attribution carried here and in Cross-Artifact Analysis A2 accounts for only
   7 of the 17, and omits the largest contributor entirely. The count and the conclusion were right;
   the file list was not.) None of the 17 is under `specs/001-ingestion-arn-logging/`. T004 pins that
   measurement. Individual
   checks are invoked directly in T014. This also corrects `plan.md`'s local verification procedure,
   which names `make validate` as a pre-push step it cannot pass.
2. **Never key a task or a pass condition on a CodeQL alert NUMBER changing state.** Alert numbers
   are locating labels only. Every gate is keyed on `most_recent_instance.location.path` plus
   `rule.id`. The alerts API location object carries only `path`, `start_line`, `end_line`,
   `start_column`, `end_column` (verified 2026-07-30), so no finer key exists.
3. **Every `gh`, pipe, or log read needs an explicit exit-code check AND a non-empty proof-of-read
   assertion.** Empty output means "the read failed" until proven otherwise. Use `${PIPESTATUS[0]}`,
   never the exit code of the last stage of a pipe.
4. **Every `gh api` call against the alerts endpoint MUST pass `--paginate`.** Measured 2026-07-30:
   the repository holds 137 code scanning alerts across all states. One unpaginated page holds 100
   and covers alert numbers 59 to 180 only. Alerts 1 and 22 through 27, which SC-005 and FR-004 both
   depend on, are demonstrably off page 1. An unpaginated all-states query returns nothing for them
   and reads as clean. See Cross-Artifact Analysis finding A1.
5. **Do NOT pre-reserve a `TD-` identifier.** `docs/reference/TECH_DEBT_REGISTRY.md` holds `TD-001`
   through `TD-023`; identifiers allocate at merge time in merge order, and `TD-024` is contested by
   at least three sibling features. Nothing in this feature writes to that file (FR-013).
6. **Writable set (FR-013, as widened by Clarification Q4)**: `src/lambdas/ingestion/handler.py`,
   `tests/unit/lambdas/ingestion/test_handler_arn_logging.py`, and any file under
   `specs/001-ingestion-arn-logging/`. Nothing else. `src/lambdas/shared/secrets.py` is off limits
   (alerts 22 through 25 sit there with `fixed_at` null, live findings behind a dismissal). Scratch
   output goes to `/tmp`, never into the repository tree.
7. **Venv**: `source .venv/bin/activate` before any `python` or `pytest`. The system interpreter at
   `/usr/bin/python3` is 3.12.3; 3.13 is only inside the venv (or via a pyenv shim). If a subprocess
   is ever spawned from a test, use `sys.executable`.
8. **GPG-sign every commit** (`git commit -S`). Never `--no-verify`.

---

## Phase 1: Setup, baselines and probes (ALL before any file is edited)

**Purpose**: establish the "before" half of every before/after criterion, and probe capability
read-only. Every task here is read-only against the repository. T001 through T005 are mutually
independent.

- [ ] **T001** [P] **Interpreter precondition.**
  Command: `source .venv/bin/activate && python -c "import sys; print(sys.version)"`
  **PASS**: the printed version starts with `3.13.`. **FAIL**: anything starting `3.12.` means the
  venv is not active and every later `pytest` result is against the wrong interpreter.

- [ ] **T002** [P] **Capture the pre-change code scanning baseline (SC-005 "before" half, and the
  proof-of-read floor every later query reuses).** Output goes to `/tmp`, never into the repo.

  ```bash
  gh api --paginate \
    "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?per_page=100" \
    > /tmp/codeql-alerts-before.json
  rc=$?
  [ "$rc" -eq 0 ] || { echo "READ FAILED: gh exit $rc"; exit 1; }
  total=$(jq -s 'add | map(select(.rule.id=="py/clear-text-logging-sensitive-data")) | length' \
    /tmp/codeql-alerts-before.json)
  [ "$total" -ge 16 ] || { echo "READ FAILED / TRUNCATED: only $total alerts of this rule"; exit 1; }
  echo "rule alerts in corpus: $total"
  jq -s 'add' /tmp/codeql-alerts-before.json | jq -r '
    .[] | select(.rule.id=="py/clear-text-logging-sensitive-data")
    | "\(.number)\t\(.state)\tfixed_at=\(.fixed_at)\t\(.most_recent_instance.location.path):\(.most_recent_instance.location.start_line)"' \
    | sort -n
  ```

  **PASS**, all four conditions together:
  1. `rc` is 0.
  2. `total` is at least 16. Measured 2026-07-30: **22**. The floor exists because an unpaginated
     read returns exactly **9** alerts of this rule, so any value at or below 9 proves truncation
     rather than cleanliness (rider 4).
  3. The printed rows include, verbatim: `148 open fixed_at=null src/lambdas/ingestion/handler.py:264`,
     `149 ... :271`, `150 ... :276`, `144 open fixed_at=null src/lambdas/shared/auth/oauth_state.py:104`.
  4. Rows `22`, `23`, `24`, `25` all read `dismissed` with `fixed_at=null` at
     `src/lambdas/shared/secrets.py`. If these four rows are absent, the read was truncated. Do not
     proceed.

  **FAIL** on any of the four. Note the alert numbers here are locating labels for a human reading
  the diff later; no pass condition in this feature is keyed on them (rider 2).

  **Conditions 3 and 4 are this task's positive anchor** and must not be reduced to a count. They
  require named paths to print verbatim **through the same field path** the later gates filter on
  (`.most_recent_instance.location.path`), which is exactly what a corpus floor cannot do. See T016's
  R12 note: a mistyped path field returns `null` for every alert, exits `0`, and still satisfies a
  floor computed from `.rule.id`. If conditions 3 and 4 print, that field path is proven live for the
  whole run.

- [ ] **T003** [P] **Read-only dismissal capability probe (FR-008a).** Never establish this by
  attempting a dismissal: a dismissal that succeeds mutates alert state, cannot be cleanly reverted,
  and SC-005 treats unintended alert-state change as a breach.

  ```bash
  gh auth status 2>&1 | tee /tmp/gh-auth.txt; rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || { echo "PROBE FAILED: gh auth status exit $rc"; exit 1; }
  grep -q "Token scopes" /tmp/gh-auth.txt || { echo "PROBE FAILED: no scope line read"; exit 1; }
  gh api repos/traylorre/sentiment-analyzer-gsk --jq '{visibility, permissions}'; rc=$?
  [ "$rc" -eq 0 ] || { echo "PROBE FAILED: repo read exit $rc"; exit 1; }
  ```

  **PASS** (verdict `DISMISSAL-AVAILABLE`): both exit codes 0, the scope line is non-empty and
  contains `repo`, `visibility` is `public`, and `permissions.push` is `true`.
  **Verdict `DISMISSAL-ABSENT`** only if `visibility` is `public` and the scope list lacks `repo`
  (and lacks `public_repo`), or `permissions.push` is `false`.

  **A missing `security_events` scope is NOT by itself a block.** That scope is a private-repository
  requirement. This repository is public and `repo` includes `public_repo`. Measured 2026-07-30:
  scopes `gist, read:org, repo, workflow`; `visibility: public`; `permissions.admin true, push true`.
  Verdict on this environment is **`DISMISSAL-AVAILABLE`**, so `BLOCKED-ON-OWNER` is not the expected
  ending. Record the verdict verbatim; T019 and T022 both read it.

- [ ] **T004** [P] **Pin the pre-existing repository-wide gate failure (rider 1).**

  ```bash
  bash scripts/check-banned-terms.sh > /tmp/banned.out 2>&1; echo "exit=$?"
  grep -c '^  \./' /tmp/banned.out
  grep -c '^  \./specs/001-ingestion-arn-logging' /tmp/banned.out
  ```

  **PASS**: exit is `1`, the first count is `17`, and the second count is `0`. That is: the gate fails
  for reasons that pre-date this feature and none of the matches is ours. **FAIL** if the second count
  is anything but 0, which would mean this feature introduced a banned term. Re-run this exact task
  after T008 and T009 as part of T013.

- [ ] **T005** [P] **Baseline the ingestion unit suite (SC-004 "before" half).**
  Command: `source .venv/bin/activate && python -m pytest tests/unit/lambdas/ingestion/ -q; echo "exit=$?"`
  **PASS**: exit `0` and the summary line reads `43 passed`. Measured 2026-07-30: 43 collected in the
  directory, of which `test_handler.py` contributes 22. Record both numbers; T011 asserts against
  them.

**Checkpoint**: baselines captured, capability verdict recorded, no repository file modified.

---

## Phase 2: US1 regression guard, written RED first (Priority: P1)

**Goal**: a test that fails against the current unfixed handler and can only be made to pass by
removing the value. **This phase MUST complete before Phase 3.** Campaign experience: a test written
after the fix, or written against `caplog.text`, passes on unfixed code and proves nothing (FR-007,
spec edge case "A test asserts on rendered log text only", research D4).

**Independent test**: T007's RED gate is itself the proof the guard discriminates.

- [ ] **T006** [US1] **Create `tests/unit/lambdas/ingestion/test_handler_arn_logging.py`.** New file
  only. `tests/unit/lambdas/ingestion/test_handler.py` is not opened for editing at any point
  (SC-004 is then satisfied mechanically).

  **Fixture ARNs** (research D5, plan Test design):

  ```
  arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/tiingo-AbCdEf
  arn:aws:secretsmanager:eu-west-2:218795110243:secret:preprod/sentiment-analyzer/finnhub-GhIjKl
  ```

  **Fixture isolation (FR-007 as amended by Clarification Q3, plus plan Adversarial Review #2 M4).**
  The environment the fixture sets MUST keep every forbidden string unique to the two secret ARNs:
  - `SNS_TOPIC_ARN` keeps the unrelated account `123456789` and region `us-east-1`, exactly as the
    existing `env_vars` fixture has it. It must contain none of `218795110243`, `eu-west-2`,
    `preprod/sentiment-analyzer`.
  - `ALERT_TOPIC_ARN` is unset by the existing fixture and defaults to `""` in `_get_config()`. If the
    new fixture sets it, the same three constraints apply.
  - `AWS_REGION` stays `us-east-1`, **and `CLOUD_REGION` must be explicitly deleted or pinned to
    `us-east-1`**. `_get_config()` at `src/lambdas/ingestion/handler.py:589-590` reads `CLOUD_REGION`
    first and only falls back to `AWS_REGION`, so an inherited `CLOUD_REGION` silently defeats the
    region isolation. `spec.md` FR-007 names three variables; this is the fourth.
  - Teardown restores or pops every variable the fixture set, including `CLOUD_REGION`.

  **Forbidden strings, six, each asserted on its own** (research D5; `plan.md` calls this "five
  classes plus a sixth", `research.md` calls it six, FR-007 enumerates five plus the suffix in prose;
  they reconcile at six and six is what the test asserts):
  1. the full ARN value, each of the two, separately
  2. `arn:aws:secretsmanager`
  3. `218795110243`
  4. `eu-west-2`
  5. `preprod/sentiment-analyzer`
  6. `AbCdEf` and `GhIjKl`

  **Do NOT shorten string 5 to `sentiment-analyzer`.** The haystack includes `record.pathname`, which
  is an absolute path inside a checkout directory named `sentiment-analyzer-gsk`, so a shortened
  assertion fails on every record for a reason unrelated to the ARN. Keep the `preprod/` prefix.
  Equally, never assert on bare `arn:aws:`, which collides with `SNS_TOPIC_ARN`.

  **Assertion surface (FR-007, research D4).** One module-level helper builds the haystack per record:
  `record.getMessage()` joined with `str(v)` over **every** value in `record.__dict__`. The `str()`
  coercion is load-bearing: `record.__dict__` holds non-string values (`args`, `exc_info`, `levelno`)
  and a bare membership test raises `TypeError`. Scanning all of `__dict__` rather than named keys is
  deliberate; it survives a key rename and catches a leak that migrates to a new `extra` key.
  **`caplog.text` is not an acceptable surface anywhere in this module.**

  **A second helper is MANDATORY, not optional** (Adversarial Review #3 finding R11). The haystack
  helper joins values into one string and therefore **discards the key**, so pytest's assertion diff
  can show that a forbidden string is present but not *where*. T007's pass condition requires
  observing that the ARN arrives through a `record.__dict__` value rather than through the rendered
  message, and that observation is not derivable from the haystack alone. Add a `where(record, needle)`
  helper returning the list of locations (`"message"`, and `f"dict:{key}"` for each matching key) and
  put its result in every assertion message. Verified 2026-07-30 by running this design against the
  unfixed handler: the case-2 failure then reads
  `leak '<tiingo ARN>' at ['dict:tiingo_secret_arn'] on msg='Running in degraded mode: Tiingo adapter unavailable'`,
  which is exactly the evidence T007 asks for. Without the helper, T007's third condition is
  unobservable and an implementer will be tempted to wave it through.

  **Restrict the sweep to this module's own logger** (Adversarial Review #3 finding R8). `caplog`
  captures third-party records too. Measured 2026-07-30, `caplog.records[0]` for the case-1
  invocation is an INFO record from `botocore.credentials`, and records also arrive from
  `src.lambdas.ingestion.parallel_fetcher` and `src.lambdas.shared.failure_tracker`. Two consequences:
  the `record.pathname` collision described below is broader than the checkout directory (a
  dependency's `pathname` runs through `<checkout>/.venv/lib/python3.13/site-packages/...`, which also
  contains `sentiment-analyzer`), and an unrestricted sweep makes this suite hostage to whatever any
  dependency happens to log. Filter case 5 and the per-record loops to
  `r.name == "src.lambdas.ingestion.handler"`, or to `r.name.startswith("src.lambdas.")` if the wider
  net is wanted. The sweep still does its job: it catches a leak migrating to a fourth site in this
  module.

  **Capture**: `caplog.at_level(logging.WARNING, logger="src.lambdas.ingestion.handler")`. Verified:
  `handler.py:119` uses `logging.getLogger(__name__)`, `configure_lambda_logging()` sets levels only
  and never touches propagation or attaches handlers or formatters, so records propagate and `caplog`
  captures cleanly.

  **Mechanics**: `@mock_aws`, `_create_table_with_gsi` plus one active configuration so the handler
  reaches line 249, and `patch` on `src.lambdas.ingestion.handler.get_api_key`, `.TiingoAdapter`,
  `.FinnhubAdapter`, `._get_sns_client`, `.emit_metrics_batch`. **The `reset_caches` autouse fixture
  from `test_handler.py` MUST be duplicated in this module** (it is not shared), otherwise
  `_active_tickers_cache` leaks across modules.

  **The entrypoint is `lambda_handler`, not `handler`** (Adversarial Review #3 finding R7). No artifact
  in this feature named it until now; `plan.md` mentions it once in passing and `tasks.md` never did.
  `from src.lambdas.ingestion.handler import handler` raises
  `ImportError: cannot import name 'handler'`, observed 2026-07-30. Import
  `from src.lambdas.ingestion.handler import lambda_handler` and call it as
  `lambda_handler({"source": "test"}, mock_context)` with a `MagicMock` context carrying
  `aws_request_id`, matching `test_handler.py`'s existing integration tests. Note that this specific
  mistake makes **all five** cases fail, including case 4, so T007's shape check catches it: a run
  where case 4 also fails is an import or wiring error, not a RED gate.

  **Five cases**:
  1. Both credentials unavailable (`get_api_key` returns `None` for both). Assert an `ERROR` record
     exists; assert its rendered message contains the **case-sensitive** literals `Tiingo` and
     `Finnhub` (FR-002); assert it is clean against all six forbidden strings.
  2. Tiingo only unavailable (`get_api_key` `side_effect` keyed on the ARN argument). Assert the
     `WARNING` record still names Tiingo and is clean against all six, including structured
     attributes.
  3. Finnhub only unavailable. Mirror of case 2.
  4. Outer exception path (Acceptance Scenario 4, FR-005). With both credentials unavailable the
     `RuntimeError` reaches the `except` at `handler.py:572`, which logs via `get_safe_error_info(e)`.
     That helper returns `{"error_type": ...}` only (verified at
     `src/lambdas/shared/logging_utils.py:106-131`), so this record is clean **by construction even
     on unfixed code**. The case is a pin, not a discriminator; T007 states so explicitly so nobody
     reads its green as evidence.
  5. Sweep: assert **every** record captured across the whole case-1 invocation is clean, not just the
     targeted one. Catches a leak that migrates to a fourth site.

  **PASS**: the file exists, imports resolve, and `python -m pytest tests/unit/lambdas/ingestion/test_handler_arn_logging.py --collect-only -q`
  exits 0 and collects at least 5 tests.

- [ ] **T007** [US1] **RED gate. Run the new module against the UNFIXED handler.** This is the single
  most important gate in the feature and it can only be run before Phase 3.
  Command: `source .venv/bin/activate && python -m pytest tests/unit/lambdas/ingestion/test_handler_arn_logging.py -v; echo "exit=$?"`
  **PASS** requires the exact failure shape, not merely a non-zero exit:
  - exit is non-zero,
  - cases **1, 2, 3 and 5 FAIL**,
  - case **4 PASSES** (clean by construction, see T006 case 4),
  - at least one case-2 or case-3 failure message shows the ARN arriving through a
    `record.__dict__` value and **not** through the rendered message. That is the proof the assertion
    surface is the right one; a test that only fails on case 1 is a `caplog.text`-equivalent test in
    disguise and MUST be rewritten before proceeding.

  **FAIL**: any of cases 1, 2, 3, 5 passing against unfixed code. Do not continue to Phase 3. Record
  the observed failure list.

**Checkpoint**: the guard demonstrably discriminates fixed from unfixed code.

---

## Phase 3: US1 code change (Priority: P1)

**Goal**: remove every ARN-derived value from message, structured context and exception message at
the three sites in `src/lambdas/ingestion/handler.py:256-277`.

**Independent test**: T010 plus T011.

- [ ] **T008** [US1] **Site 1, `handler.py:259-265` (the definitely-rendered one).** `error_msg` is
  built by f-string from `config['tiingo_secret_arn']` and `config['finnhub_secret_arn']`, passed to
  `logger.error()`, then reused verbatim as the `RuntimeError` message. Both uses are sinks.
  Replace the f-string with a fixed literal naming both sources, for example
  `"CONFIGURATION ERROR: Both API keys missing (Tiingo and Finnhub)."` The literal MUST contain
  case-sensitive `Tiingo` and `Finnhub` (FR-002). The `logger.error(...)` call, the
  `raise RuntimeError(...)`, the log level, the branch condition and the exception type all stay
  exactly as they are (FR-006). The exception message is now clean, which is what makes FR-005 hold
  at the outer `except`. Add the FR-010 inline comment naming `py/clear-text-logging-sensitive-data`
  and the reason the value was removed.
  **PASS** (corrected by Adversarial Review #3 finding R1; the earlier "exactly two lines" wording was
  unsatisfiable). Run:

  ```bash
  grep -n "tiingo_secret_arn\|finnhub_secret_arn" src/lambdas/ingestion/handler.py > /tmp/arn-refs.txt
  echo "grep_exit=$?"; wc -l < /tmp/arn-refs.txt; cat /tmp/arn-refs.txt
  grep -cE "logger\.|f\"|f'|RuntimeError" /tmp/arn-refs.txt
  ```

  `grep_exit` is `0` and the line count is **exactly 4**. The four surviving references are the two
  `get_api_key(config[...])` reads inside `lambda_handler` and the two `os.environ[...]` reads inside
  `_get_config()`. Measured 2026-07-30 on the unfixed file the same grep returns **eight** lines
  (249, 250, 261, 262, 271, 276, 601, 602); T008 and T009 remove exactly the four in the 259-277
  region, and lines 601-602 in `_get_config()` are load-bearing configuration construction that MUST
  NOT be touched. The second grep count MUST be `0`: no surviving reference sits inside a logging
  call, an f-string or a `RuntimeError` construction. **FAIL** on a line count other than 4, or a
  second count other than 0.

- [ ] **T009** [US1] **Sites 2 and 3, `handler.py:268-277` (the structured-context ones).** Delete the
  `extra={...}` argument outright at both warnings. The messages already carry the literal source
  names, so nothing an on-call engineer uses is lost. **Do not** substitute a sanitized value: that is
  the `0e7a375` shape, it already failed in this repository, and FR-003 forbids it. Add the FR-010
  inline comment at each site.
  **PASS**: `sed -n '256,280p' src/lambdas/ingestion/handler.py` shows no `extra=` in either warning,
  both warnings retain their literal source name and `logger.warning` level, and both carry the
  FR-010 comment.

  *Impact note, keep it accurate (do not overstate):* nothing renders `extra` today. The root handler
  renders `getMessage()` and `configure_lambda_logging()` attaches no formatter; no Terraform in this
  repository sets a JSON log format for this function (verified: zero matches for `logging_config`,
  `log_format` or `LogFormat` under `infrastructure/terraform/`). These two sites are a latent leak
  armed by a future formatter plus an alert the engine raises regardless of rendering, not a live
  disclosure. Site 1 is the live one.

- [ ] **T010** [US1] **GREEN gate (SC-001, FR-007).**
  Command: `source .venv/bin/activate && python -m pytest tests/unit/lambdas/ingestion/test_handler_arn_logging.py -v; echo "exit=$?"`
  **PASS**: exit `0`, all 5 cases pass, zero skips, zero xfails. A skipped case is a failure of this
  task. Cross-check against T007's recorded failure list: cases 1, 2, 3 and 5 must have flipped from
  red to green, which is the only evidence that the fix, and not the test, changed.

- [ ] **T011** [US1] **SC-004 regression: nothing existing loosened or removed.**
  Command: `source .venv/bin/activate && python -m pytest tests/unit/lambdas/ingestion/ -q; echo "exit=$?"`
  **PASS**: exit `0`, and the summary reads `48 passed` (T005's 43 plus the 5 new cases); the count
  MUST be `43 + N` where N is the number of new cases, never fewer than 43 pre-existing.
  Additionally: `git status --porcelain tests/unit/lambdas/ingestion/test_handler.py` prints nothing,
  proving the existing module was not touched at all.

- [ ] **T012** [US1] **Static negative checks (FR-003, FR-012).**

  ```bash
  grep -n "_sanitize_secret_id_for_log" src/lambdas/ingestion/handler.py; echo "grep_exit=$?"
  grep -n "from src.lambdas.shared.secrets import" src/lambdas/ingestion/handler.py
  grep -nE "logging\.Filter|addFilter|setFormatter|logging\.Formatter|basicConfig" src/lambdas/ingestion/handler.py; echo "grep_exit=$?"
  ```

  **PASS**: the first grep exits `1` with no output (FR-003: the sanitizer is not called here). The
  second prints exactly one line, `from src.lambdas.shared.secrets import get_api_key`, unchanged. The
  third exits `1` with no output (FR-012: no new filter, formatter or logging-framework change).
  Here an exit of `1` from `grep` is the pass, and it is checked explicitly rather than inferred from
  silence.

- [ ] **T013** [US1] **Scope lock and comment presence (FR-013, FR-010).**

  ```bash
  git status --porcelain -- ':!specs/001-bad-tag-filter-dead-suppression' \
    ':!specs/001-codeql-coverage' ':!specs/001-oauth-provider-taint' > /tmp/scope.txt
  echo "status_exit=$?"; cat /tmp/scope.txt
  grep -cvE '(src/lambdas/ingestion/handler\.py|tests/unit/lambdas/ingestion/test_handler_arn_logging\.py|specs/001-ingestion-arn-logging)' /tmp/scope.txt
  grep -c "py/clear-text-logging-sensitive-data" src/lambdas/ingestion/handler.py
  bash scripts/check-banned-terms.sh > /tmp/banned-after.out 2>&1; echo "exit=$?"
  grep -c '^  \./' /tmp/banned-after.out
  grep -c '^  \./specs/001-ingestion-arn-logging' /tmp/banned-after.out
  git diff -U0 src/lambdas/ingestion/handler.py | grep -E '^@@'
  ```

  **PASS**, all five:
  1. `/tmp/scope.txt` is **non-empty** (an empty file means the read failed or nothing was changed at
     all, never that scope is clean), and the `grep -cv` count of lines outside the permitted set is
     **0**. Any other path, and in particular `src/lambdas/shared/secrets.py`, is a breach of FR-013
     and of SC-005.
     **The three sibling exclusions are load-bearing** (Adversarial Review #3 finding R2). This
     campaign runs four features in one shared worktree; measured 2026-07-30, a bare
     `git status --porcelain` already lists `specs/001-bad-tag-filter-dead-suppression/`,
     `specs/001-codeql-coverage/` and `specs/001-oauth-provider-taint/` as untracked. Without the
     pathspec exclusions this condition fails against a perfectly correct implementation. Never
     "resolve" a sibling directory appearing here by deleting it.
  2. The rule-id grep count is **3** (FR-010, one comment per site, unconditional).
  3. `check-banned-terms.sh` exit is still `1` and the feature-directory count (condition 4) is `0`.
     The total is expected to read **17**, unchanged from T004, but the total is **not** the gate:
     sibling features write into `specs/` in this same worktree concurrently and can move it. A total
     that moved while condition 4 stays `0` is attributable elsewhere and is not this feature's
     defect. Diff `/tmp/banned.out` against `/tmp/banned-after.out` to see which paths moved.
  4. The feature-directory match count is **`0`**. This is the actual gate.
  5. The `git diff -U0` hunk headers are all inside the `256-277` region of the pre-change file
     (`git diff --stat` was named here previously and cannot evaluate this: it emits insertion and
     deletion counts only, with no line regions. Adversarial Review #3 finding R5).

- [ ] **T014** [US1] **Targeted lint, format and SAST on the touched files only.** Do not invoke
  `make validate` (rider 1).

  ```bash
  source .venv/bin/activate
  ruff check src/lambdas/ingestion/handler.py tests/unit/lambdas/ingestion/test_handler_arn_logging.py; echo "ruff_check=$?"
  ruff format --check src/lambdas/ingestion/handler.py tests/unit/lambdas/ingestion/test_handler_arn_logging.py; echo "ruff_fmt=$?"
  bandit -c pyproject.toml -r src/lambdas/ingestion/handler.py -ll; echo "bandit=$?"
  semgrep scan --config auto --error --severity ERROR --severity WARNING src/lambdas/ingestion/handler.py; echo "semgrep=$?"
  ```

  **PASS**: all four exit codes are `0`. If `semgrep` is absent from the venv it must be installed
  (`pip install -r requirements-dev.txt`), never skipped: a skipped scanner reported as a pass is the
  defect class this campaign keeps finding.

**Checkpoint**: the code change is complete, locally verified, scope-locked, and independently
mergeable. Every criterion that does not need a default-branch analysis is now satisfied.

---

## Phase 4: US2 closure evidence (Priority: P2)

**Goal**: prove closure from branch state, not from a pull request check.

**These tasks are NOT runnable at the end of implementation.** SC-002 and SC-002a are keyed to a
default-branch CodeQL analysis on a commit that includes the change, which cannot exist while the
change sits on a feature branch. If T016 cannot run, the feature terminates at
`PENDING-BRANCH-ANALYSIS` via T022. That is a recorded outcome, not an abort.

- [ ] **T015** [US2] **Pull request run, as the informative inverse only.** Because this change edits
  the exact lines flagged today, the diff-informed pull request result is directly informative here.
  Command: `gh pr checks <PR> ; echo "exit=$?"`, then read the CodeQL result.
  **Use**: an alert surviving the pull request run is a **genuine survivor**, worth investigating
  immediately rather than waiting.
  **PASS/FAIL**: this task has no pass condition that closes anything. **A green pull request CodeQL
  check is explicitly NOT closure evidence** (SC-002; PR #990 was green with five alerts open). Record
  the observation and move on. Claiming closure from this task alone is a defect.

- [ ] **T016** [US2] **SC-002 gate: zero open alerts of this rule at this path.** Run only after a
  default-branch analysis on a commit that includes the change has completed.

  ```bash
  gh api --paginate \
    "repos/traylorre/sentiment-analyzer-gsk/code-scanning/alerts?per_page=100" \
    > /tmp/codeql-alerts-after.json
  rc=$?
  [ "$rc" -eq 0 ] || { echo "READ FAILED: gh exit $rc"; exit 1; }
  total=$(jq -s 'add | map(select(.rule.id=="py/clear-text-logging-sensitive-data")) | length' \
    /tmp/codeql-alerts-after.json)
  [ "$total" -ge 16 ] || { echo "READ FAILED / TRUNCATED: only $total"; exit 1; }

  # POSITIVE ANCHOR. The corpus floor above reads .rule.id and therefore says NOTHING about
  # whether the path field this gate depends on was read at all. Both clauses below must hold.
  null_paths=$(jq -s 'add | map(select(.most_recent_instance.location.path==null)) | length' \
    /tmp/codeql-alerts-after.json)
  [ "$null_paths" -eq 0 ] || { echo "BLIND READ: $null_paths alerts have a null path"; exit 1; }
  anchor=$(jq -s 'add | map(select(
      .most_recent_instance.location.path=="src/lambdas/shared/secrets.py")) | length' \
    /tmp/codeql-alerts-after.json)
  [ "$anchor" -ge 15 ] || { echo "BLIND READ: known-present path returned $anchor"; exit 1; }

  open_at_path=$(jq -s 'add | map(select(
      .rule.id=="py/clear-text-logging-sensitive-data"
      and .state=="open"
      and .most_recent_instance.location.path=="src/lambdas/ingestion/handler.py")) | length' \
    /tmp/codeql-alerts-after.json)
  echo "rule alerts: $total ; null_paths: $null_paths ; anchor: $anchor ; open at path: $open_at_path"
  ```

  **PASS**: `rc` is 0 **AND** `total` is at least 16 **AND** `null_paths` is exactly `0` **AND**
  `anchor` is at least 15 **AND** `open_at_path` is exactly `0`.

  **Why the two anchor clauses exist** (Adversarial Review #3 finding R12, added after the corpus-wide
  wave). **A corpus floor does not protect against a wrong field path.** Reproduced 2026-07-30 on the
  live corpus: mistyping `.most_recent_instance.location.path` as `.most_recent_instance.locatio.path`
  makes `jq` return `null` for every alert. It does **not** error and it exits `0`. The `total` floor
  still passes, because `total` is computed from `.rule.id`, a different field path that the typo does
  not touch. And `open_at_path` then evaluates to **`0`**, which is this task's PASS value. Measured:
  correct path gives `null_paths=0` and `anchor=16`; the mistyped path gives `null_paths=137` and
  `anchor=0`, with `jq_exit=0` in both cases. Every clause of the old pass condition was satisfiable by
  a completely blind read, and the blind read reported this feature's primary success criterion as met.
  Exit code plus corpus floor is necessary and **not** sufficient; an absence is only evidence once a
  known-present value has been shown present through the same field path.
  **FAIL**: `open_at_path` greater than 0. Any number returned, **including a number that did not
  exist before**, is a survivor under Acceptance Scenario 2 and goes to T019. It is never dismissed
  as an unrelated finding.
  **NOT-YET-EVALUABLE**: the latest completed default-branch analysis does not include the change.
  Verify with the shape below. **Do not combine `--paginate` with `--jq`** (Adversarial Review #3
  finding R4): gh applies `--jq` once per page, so `.[0]` prints the newest analysis of *every* page.
  Measured 2026-07-30, the `--paginate --jq` form printed **10 lines**, one per page, handing the
  reader ten commit shas and no rule for choosing among them. Only page one is wanted here:

  ```bash
  gh api "repos/traylorre/sentiment-analyzer-gsk/code-scanning/analyses?ref=refs/heads/main&per_page=1" \
    > /tmp/latest-analysis.json
  rc=$?
  [ "$rc" -eq 0 ] || { echo "READ FAILED: gh exit $rc"; exit 1; }
  [ "$(jq 'length' /tmp/latest-analysis.json)" -eq 1 ] || { echo "READ FAILED: no analysis row"; exit 1; }
  jq -r '.[0] | "\(.commit_sha)\t\(.created_at)"' /tmp/latest-analysis.json
  ```

  Compare that sha against the merge commit. In this case do not record a verdict; go to T022 and
  terminate at `PENDING-BRANCH-ANALYSIS`.

- [ ] **T017** [US2] **SC-002a: `fixed_at`, never `state`.** For each of alerts 148, 149 and 150 that
  is reported as repaired rather than dismissed, read `fixed_at` from the same
  `/tmp/codeql-alerts-after.json` (all states, already paginated):

  ```bash
  jq -s 'add' /tmp/codeql-alerts-after.json | jq -r '
    .[] | select(.number==148 or .number==149 or .number==150)
    | "\(.number)\t\(.state)\tfixed_at=\(.fixed_at)"' | sort -n
  rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] || { echo "READ FAILED"; exit 1; }
  ```

  **PASS**: `rc` is 0, **three rows print** (fewer than three means the read was truncated, not that
  the alerts vanished), and every row claimed as repaired has `fixed_at` non-null and dated at or
  after the change. **FAIL**: any row claimed repaired that reads `dismissed` or `closed` with
  `fixed_at=null`. Alerts 22 through 25 are the standing proof that this combination masks a site
  that was never repaired. The numbers here are locating labels for an anti-fraud cross-check only;
  SC-002 (T016) remains the criterion of record.

- [ ] **T018** [US2] **SC-005 blast radius: nothing outside the handler moved.**

  ```bash
  for f in src/lambdas/shared/secrets.py src/lambdas/shared/auth/oauth_state.py; do
    for snap in before after; do
      jq -s 'add' /tmp/codeql-alerts-$snap.json | jq -r --arg p "$f" '
        .[] | select(.rule.id=="py/clear-text-logging-sensitive-data")
        | select(.most_recent_instance.location.path==$p)
        | "\(.number)\t\(.state)\tfixed_at=\(.fixed_at)"' | sort -n > /tmp/sc005-$snap.txt
      [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "READ FAILED"; exit 1; }
      [ -s /tmp/sc005-$snap.txt ] || { echo "READ FAILED: empty for $f/$snap"; exit 1; }
    done
    diff /tmp/sc005-before.txt /tmp/sc005-after.txt; echo "$f diff_exit=$?"
  done
  ```

  **Then the whole-corpus check, which the per-file loop above cannot do** (Adversarial Review #3
  finding R3). SC-005 says alerts of this rule outside the handler are unchanged **in count**, and a
  two-file loop is blind to a path it does not name. Measured 2026-07-30 this rule sits on **four**
  paths: `handler.py` (3), `secrets.py` (16), `oauth_state.py` (2) and
  **`src/lambdas/shared/errors.py` (1, alert 1)**, which the loop above never reads. A regression that
  surfaced at a fifth path would be invisible.

  **Compare multiplicity, not membership** (Adversarial Review #3 finding R13). `rule@path` is **not**
  a unique key in this corpus, and the collapse is severe: measured 2026-07-30,
  `py/log-injection@src/lambdas/dashboard/auth.py` holds **24** alerts under one key, `ohlc.py` 17,
  and, inside this feature's own SC-005 scope,
  `py/clear-text-logging-sensitive-data@src/lambdas/shared/secrets.py` holds **16**. A set-diff keyed
  on `rule@path` reports membership only, so 15 of those 16 could vanish and it would print nothing.
  That is the highest-value file in this feature's blast radius. Build `{key: count}` on each side and
  diff the **counts**, reporting three buckets so a partial loss has somewhere to land.

  ```bash
  for snap in before after; do
    jq -s 'add' /tmp/codeql-alerts-$snap.json > /tmp/sc005-corpus-$snap.json
    [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "READ FAILED"; exit 1; }

    # POSITIVE ANCHOR, same reason as T016: the floor below reads .rule.id and cannot
    # detect a mistyped path field, which yields null everywhere and exits 0.
    np=$(jq '[.[] | select(.most_recent_instance.location.path==null)] | length' \
      /tmp/sc005-corpus-$snap.json)
    [ "$np" -eq 0 ] || { echo "BLIND READ: $np null paths in $snap"; exit 1; }
    anch=$(jq '[.[] | select(.most_recent_instance.location.path=="src/lambdas/shared/secrets.py")] | length' \
      /tmp/sc005-corpus-$snap.json)
    [ "$anch" -ge 15 ] || { echo "BLIND READ: anchor path returned $anch in $snap"; exit 1; }

    jq '[ .[] | select(.rule.id=="py/clear-text-logging-sensitive-data")
          | select(.most_recent_instance.location.path!="src/lambdas/ingestion/handler.py")
          | (.rule.id + "@" + .most_recent_instance.location.path) ]
        | group_by(.) | map({key:.[0], n:length}) | sort_by(.key)' \
      /tmp/sc005-corpus-$snap.json > /tmp/sc005-keys-$snap.json
    rows=$(jq '[.[].n] | add // 0' /tmp/sc005-keys-$snap.json)
    [ "$rows" -ge 15 ] || { echo "READ FAILED / TRUNCATED: only $rows rows outside the handler"; exit 1; }
    echo "$snap: keys=$(jq 'length' /tmp/sc005-keys-$snap.json) alerts=$rows null_paths=$np anchor=$anch"
  done

  jq -n --slurpfile b /tmp/sc005-keys-before.json --slurpfile a /tmp/sc005-keys-after.json '
    ($b[0] | INDEX(.key) | map_values(.n)) as $B |
    ($a[0] | INDEX(.key) | map_values(.n)) as $A |
    { disappeared: [ $B | keys_unsorted[] | select($A[.]==null) ],
      appeared:    [ $A | keys_unsorted[] | select($B[.]==null) ],
      changed:     [ $B | keys_unsorted[] | select($A[.]!=null and $A[.]!=$B[.])
                     | {key:., before:$B[.], after:$A[.]} ] }' > /tmp/sc005-buckets.json
  echo "buckets_exit=$?"; cat /tmp/sc005-buckets.json
  ```

  **PASS**, all of:
  1. Every per-file snapshot is **non-empty** (empty means the read failed, never that the file is
     clean) and every `diff_exit` is `0`.
  2. On both sides `null_paths` is `0` and `anchor` is at least 15. These are the positive anchors; a
     read that cannot see `secrets.py` cannot be trusted to report that nothing changed.
  3. Both `rows` counts are at least 15 (measured **19**; the floor is proof-of-read, not the
     criterion).
  4. **All three buckets are empty**: `disappeared` `[]`, `appeared` `[]`, `changed` `[]`.

  Specifically: alert 144 on `oauth_state.py` unchanged and still owned by sibling
  `001-oauth-provider-taint`; alerts 22 through 25 still `dismissed` with `fixed_at=null`; alert 1 on
  `errors.py` unchanged; **no new alert number and no changed count on any path outside
  `src/lambdas/ingestion/handler.py`**, which would breach both SC-005 and FR-013.

  **`changed` is the bucket that matters and the one a membership set-diff does not have.** Verified in
  both directions 2026-07-30 against fixtures built from the live corpus:
  - **Partial loss**, `secrets.py` cut from 16 alerts to 1 plus a fabricated new alert at
    `src/lambdas/ingestion/parallel_fetcher.py`: three-bucket output was
    `changed: [{key: ...secrets.py, before: 16, after: 1}]`, `appeared: [...parallel_fetcher.py]`,
    `disappeared: []`. Caught.
  - **The same fixture through a membership-only set-diff**: `disappeared: []`,
    `appeared: [...parallel_fetcher.py]`. The 16-to-1 loss on the single most sensitive file in this
    feature's scope was **invisible**. That is the defect, reproduced.
  - **No-change direction**, identical before and after: all three buckets `[]`. No false positive.

- [ ] **T019** [US2] **Survivor branch (FR-008, FR-008a, FR-009, SC-003).** Runs only if T016 returned
  `open_at_path` greater than 0. Read T003's recorded verdict; **do not re-probe by attempting a
  dismissal.**

  - **If `DISMISSAL-AVAILABLE`**: dismiss each surviving alert at this path as a false positive with a
    justification carrying all three FR-009 elements, drafted from the template in
    `codeql-logging-convention.md` section 2. All three elements are mandatory: what the value
    actually is (an AWS resource identifier, not a credential value), which convention shape was
    applied (value stripped from message, structured context and exception), and **why CodeQL still
    reports the flow**, stated concretely for the surviving site. Do not paste the template verbatim;
    element three and the re-evaluation trigger must be site-specific.
    **PASS (SC-003)**: re-read each dismissed alert and confirm `dismissed_comment` is non-empty and
    contains all three elements. Verify with a read, never by trusting the write's exit code.
  - **If `DISMISSAL-ABSENT`**: write `specs/001-ingestion-arn-logging/dismissal-handoff.md` carrying
    (a) the exact alert numbers observed at the path, (b) the exact justification text for each, and
    (c) the exact `gh api` call or UI steps to apply each. Terminate at `BLOCKED-ON-OWNER` via T022.
    **PASS**: the file exists and contains all three, and the code change is stated as independently
    complete and mergeable.

  Under neither branch is the feature reported as done or as failed while a dismissal is outstanding.

---

## Phase 5: US3 reusable convention (Priority: P3)

**Goal**: `001-oauth-provider-taint`, and any later feature working this rule, can cite one artifact
instead of re-deriving the convention. `codeql-logging-convention.md` already exists; these tasks
audit it against what this feature actually did. Both are read-only against everything except that
one file and are mutually independent.

- [ ] **T020** [P] [US3] **FR-011 and SC-006 conformance audit of `codeql-logging-convention.md`.**
  Confirm by reading that all five required elements are present and correct:
  1. the decision rule for rewrite versus dismiss (section 1, steps 1 to 4),
  2. the three-element dismissal wording pattern and its template (section 2),
  3. the `fixed_at` versus `state` caveat (section 3, trap 1),
  4. the alert-number-instability caveat and the path-plus-rule keying rule (section 3, trap 2),
  5. both terminal states, `PENDING-BRANCH-ANALYSIS` and `BLOCKED-ON-OWNER`, with the read-only
     capability probe and the explicit note that a missing `security_events` scope is not by itself a
     block (section 5a and 5b).

  **Then apply the one correction this feature discovered**: the query shape in section 3 lacks
  `--paginate` and has no proof-of-read assertion. Update it to the shape used in T016 (paginate,
  check the exit code, assert a non-zero corpus count, then count the filtered set). Leave a one-line
  note that an unpaginated read returns 100 of 137 alerts on this repository and silently omits alert
  numbers below 59, measured 2026-07-30.
  **The substantive defect is not the missing flag, it is the sentence under it.** Section 3 of the
  convention currently ends `Empty output is the pass condition.` with nothing proving the read
  worked. That is the campaign's canonical vacuous pass, sitting in the one document the sibling
  feature inherits by citation. Adding `--paginate` while leaving that sentence intact fixes nothing.
  Replace the block with the ordered shape T016 uses: exit code first, then a corpus-count floor, then
  read the absence. Say in the file that an absence is only evidence once the read is proven live.

  ```bash
  grep -c -- "--paginate" specs/001-ingestion-arn-logging/codeql-logging-convention.md
  grep -n "Empty output is the pass condition" specs/001-ingestion-arn-logging/codeql-logging-convention.md; echo "stale_exit=$?"
  grep -cE "exit|rc=|floor|proof" specs/001-ingestion-arn-logging/codeql-logging-convention.md
  ```

  **PASS**: all five elements verified present by reading; the first count is at least `1`;
  `stale_exit` is **`1`** with no output, meaning the unguarded sentence is gone (an exit of `2`
  means the file is missing and is a FAIL, not a pass, so the absence here is live-checked); and the
  third count is at least `1`. Measured 2026-07-30 before the edit: paginate count `0`, the stale
  sentence present at line 112. **FAIL**: any element missing, the query shape left unpaginated, or
  the unguarded pass sentence still present. (Adversarial Review #3 finding R6.)

- [ ] **T021** [P] [US3] **Sibling citation readiness (FR-011).**
  Command:
  `grep -nE "spec\.md:[0-9]+|plan\.md:[0-9]+|tasks\.md:[0-9]+|research\.md:[0-9]+" specs/001-ingestion-arn-logging/codeql-logging-convention.md; echo "grep_exit=$?"`
  **PASS**: `grep_exit` is `1` with no output. The convention must be citable by document and section,
  never by line number: sibling artifacts changed under review and will change again, and a
  line-number citation rots silently. References to this feature's own files inside the convention
  must name the file and the section only. **FAIL**: any hit.

**Checkpoint**: a reader who has never seen this feature can get the decision rule, the wording
pattern, the verification caveats and both terminal states from one file (SC-006).

---

## Phase 6: Terminal state, recorded explicitly

- [ ] **T022** **Determine and RECORD the terminal state.** Reaching a terminal state is an explicit,
  written outcome. An implementation that stops without filling in the record below has not completed
  this task, regardless of how much code it wrote.

  Decide in this order and stop at the first match:

  | Condition | State |
  |---|---|
  | T016 not runnable: no completed default-branch analysis on a commit containing the change | **`PENDING-BRANCH-ANALYSIS`** (FR-008b) |
  | T016 `open_at_path` is 0, T017 and T018 pass | **`DONE`** |
  | T016 `open_at_path` greater than 0, T003 verdict `DISMISSAL-AVAILABLE`, T019 dismissal applied and re-read | **`DONE (dismissed)`** |
  | T016 `open_at_path` greater than 0, T003 verdict `DISMISSAL-ABSENT`, `dismissal-handoff.md` written | **`BLOCKED-ON-OWNER`** (FR-008a) |

  Then fill in the **Terminal State Record** at the foot of this file. Writing it satisfies FR-008b's
  requirement that the verification query be on record: the record points at T016, which carries the
  query in full, and no separate artifact is created (this closes the ambiguity Adversarial Review #2
  logged as M5).

  **PASS**: the record below is filled in with a date, a state drawn from the four above, the T003
  verdict, and the T016 result or the reason it was not runnable.
  **`PENDING-BRANCH-ANALYSIS` and `BLOCKED-ON-OWNER` are reported as neither done nor failed.**
  `PENDING-BRANCH-ANALYSIS` is the **expected ending of implementation**, because SC-002 and SC-002a
  are only evaluable after the change reaches the default branch. Reporting either one as a failure,
  or silently as a success, is a defect.

---

## Terminal State Record

*Filled in by T022. Leave the placeholders until then.*

- **Date**: `<YYYY-MM-DD>`
- **Terminal state**: `<PENDING-BRANCH-ANALYSIS | DONE | DONE (dismissed) | BLOCKED-ON-OWNER>`
- **T003 capability verdict**: `<DISMISSAL-AVAILABLE | DISMISSAL-ABSENT>` (probed read-only; measured
  `DISMISSAL-AVAILABLE` on 2026-07-30)
- **T016 result**: `<open_at_path value, or "not runnable: reason">`
- **Verification query of record**: T016 in this file (paginated, exit-checked, floor-asserted)
- **Outstanding owner action**: `<none | apply dismissal-handoff.md | re-run T016 after the next
  default-branch analysis | add the next free TECH_DEBT_REGISTRY identifier if the dismissal branch
  fired>`

---

## Dependencies and execution order

```
T001..T005  [P, all independent, ALL before any edit]
     |
     +-- T002 -> T016, T017, T018   (the "before" snapshot; SC-005 needs both halves)
     +-- T003 -> T019, T022         (capability verdict; must precede any dismissal)
     +-- T004 -> T013               (banned-term count before/after)
     +-- T005 -> T011               (suite count before/after)
     |
T006 -> T007  (RED gate)
     |
T007 -> T008, T009   (HARD ORDER: the fix must not land before the guard has been seen to fail)
     |
T008, T009 -> T010 -> T011 -> T012 -> T013 -> T014
     |
     +-- (merge to default branch, outside this task list)
     |
T015 (informative only, never closure)
T016 -> T017, T018
T016 -> T019 (only when open_at_path > 0; also needs T003)
     |
T020, T021 [P with each other, independent of everything after T014]
     |
T016, T017, T018, T019 -> T022
```

**Parallelizable**: T001, T002, T003, T004, T005 (five, Phase 1), and T020, T021 (two, Phase 5).
Seven of twenty-two. Everything else is strictly ordered.

**Ordering hazards, stated so they are not rediscovered**:

- **T007 before T008/T009 is not a preference.** A test written after the fix cannot demonstrate it
  discriminates, and the specific failure mode here (`caplog.text` passing against two of three
  unfixed sites) is silent.
- **T002 before any edit.** SC-005 is a before/after diff. There is no way to reconstruct the "before"
  half afterwards.
- **T003 before T019, always.** The only alternative probe mutates alert state irreversibly.
- **T016 before T017 and T018**, because all three read the same paginated snapshot and T016 is the
  task that validates it was not truncated.

---

## Requirement coverage

Every FR and every SC in `spec.md` maps to at least one task. No gaps.

### Functional requirements

| Requirement | Tasks | How it is checked |
|---|---|---|
| **FR-001** no ARN or component in any log record, message or structured context | T006, T008, T009, T010 | Six forbidden strings asserted per record over `getMessage()` plus all of `record.__dict__` |
| **FR-002** each record still names its source in fixed literal text | T006 (case 1), T008, T009 | Case-sensitive `Tiingo` / `Finnhub` assertion on the rendered message |
| **FR-003** no new helper, existing sanitizer not called from these sites | T009, T012 | `grep -n "_sanitize_secret_id_for_log"` exits 1; import line unchanged |
| **FR-004** nothing ARN-derived in message, context or exception message | T006, T008, T009, T010 | Site 1 exception message rebuilt from a literal; T008 grep confines the two config reads to lines 249-250 |
| **FR-005** the raised failure cannot reintroduce the ARN downstream | T006 (case 4), T008 | Outer-except record pinned; `get_safe_error_info` returns type only |
| **FR-006** runtime behaviour otherwise unchanged (level, branch, exception type, response) | T008, T009, T011 | Level/branch/type preserved by construction; all 43 pre-existing tests still pass |
| **FR-007** tests assert over rendered message AND structured context, forbidden strings enumerated, fixture isolated | T006, T007, T010 | Haystack definition, six-string enumeration, `SNS_TOPIC_ARN` / `ALERT_TOPIC_ARN` / `AWS_REGION` / `CLOUD_REGION` isolation; T007 proves it fails on unfixed code |
| **FR-008** any surviving alert at this path is dismissed with a written justification | T016, T019 | Survivor detection keyed on path plus rule; dismissal comment re-read after writing |
| **FR-008a** `BLOCKED-ON-OWNER` terminal state, read-only capability probe, handoff artifact | T003, T019, T022 | Probe is scopes plus visibility plus permissions; `dismissal-handoff.md` contents specified; state recorded |
| **FR-008b** `PENDING-BRANCH-ANALYSIS` terminal state, verification query on record | T016, T022 | T016 carries the query; T022 records the state and points at it |
| **FR-009** three-element dismissal justification | T019, T020 | Element list enforced at write time and re-read; section 2 of the convention audited |
| **FR-010** inline rule-id comment at all three sites, unconditionally | T008, T009, T013 | `grep -c "py/clear-text-logging-sensitive-data" handler.py` equals 3 |
| **FR-011** convention recorded for the sibling feature to cite | T020, T021 | Five-element audit; no line-number citations |
| **FR-012** no new cloud resources, logging mechanism retained | T012 | grep for `logging.Filter`, `addFilter`, `setFormatter`, `Formatter`, `basicConfig` exits 1 |
| **FR-013** writable set locked | T002, T013 | Scratch to `/tmp`; `git status --porcelain` shows only the three permitted paths |

15 of 15 functional requirements covered.

### Success criteria

| Criterion | Tasks | How it is checked |
|---|---|---|
| **SC-001** zero records carry any enumerated forbidden string, message and structured context | T007, T010 | Red-then-green over all five cases |
| **SC-002** zero open alerts of this rule at this path, from the default-branch analysis | T016 | Paginated, exit-checked, floor-asserted, keyed on path plus rule |
| **SC-002a** `fixed_at` non-null and dated at or after the change for anything claimed repaired | T017 | Three rows must print; `dismissed`/`closed` with null `fixed_at` fails |
| **SC-003** every dismissed alert carries a non-empty three-element comment, or the handoff carries the exact text | T019 | Re-read after write, or `dismissal-handoff.md` content check |
| **SC-004** existing suite passes, additions only | T005, T011 | 43 before, 43 + N after; `test_handler.py` unmodified per `git status` |
| **SC-005** alerts elsewhere unchanged in count and `fixed_at` | T002, T018 | Non-empty before/after snapshots diffed per file; any new number on `secrets.py` fails |
| **SC-006** the convention is findable in one artifact under this feature's directory | T020 | Five-element audit of `codeql-logging-convention.md` |

7 of 7 success criteria covered.

---

## Cross-Artifact Analysis

Scope: `spec.md`, `plan.md`, `research.md`, `codeql-logging-convention.md`, `tasks.md` (this file).
Every claim below was checked against the repository or the live GitHub API on 2026-07-30, not
against another document. Adversarial Reviews #1 and #2 are treated as settled and are not re-run;
this pass looks for what survived them.

### Findings

| # | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| **A1** | **HIGH** | **The verification procedure is unpaginated and its all-states half is broken today.** `plan.md`'s Closure evidence block and `codeql-logging-convention.md` section 3 both use `gh api "…/code-scanning/alerts?state=open&per_page=100"` with no `--paginate`. `plan.md` then instructs, for SC-002a and SC-005, to "re-query without the `state` filter". Measured: the repository holds **137** alerts across all states; one page holds 100 and spans alert numbers **59 to 180**. Alerts **1 and 22 through 27 are off page 1**, and those are exactly the alerts SC-005 requires checking on `src/lambdas/shared/secrets.py` and FR-004 cites as its evidence base. The unpaginated all-states query returns **zero** rows for them, which reads as clean. This is campaign rule 2's exact failure shape, surviving in the one document the sibling feature inherits. The `state=open` half happens to be safe right now (5 open alerts total) but is silently fragile. | `gh api --paginate …` returns 137; `gh api …?per_page=100` returns 100; page-1 number range 59 to 180; `jq 'map(select(.number>=22 and .number<=27))\|length'` on page 1 is 0, on the paginated corpus is 6 | Closed in this file: rider 4 plus T002, T016, T017, T018 all use `--paginate` with an exit check and a corpus-count floor. T020 propagates the correction into `codeql-logging-convention.md` so the sibling inherits the fixed shape. `plan.md` is left as the reviewers wrote it; the correction lives here and in the convention |
| **A2** | **MEDIUM** | **`plan.md`'s local verification procedure names `make validate`, which cannot pass on this tree.** `plan.md` Verification procedure lists `make validate` as a pre-push step, and the Constitution Check §10 row asserts "`make validate` runs before push as usual". Measured: `scripts/check-banned-terms.sh` exits 1 on 17 pre-existing matches in `.secrets.baseline`, `docs/cleanup/diagram-drift.md` and `CLEANUP-BOARD.html`, none of them this feature's. Any task keyed on that command is unsatisfiable, and an implementer who treats the failure as their own will hunt a phantom | `bash scripts/check-banned-terms.sh` exits 1, 17 matches, 0 under `specs/001-ingestion-arn-logging/` | Closed in this file: rider 1, T004 pins the pre-existing count, T014 invokes ruff, bandit and semgrep directly, T013 re-checks the count is still 17 |
| **A3** | **MEDIUM** | **No artifact requires the regression test to be run against unfixed code.** `plan.md`'s Test design specifies the assertion surface correctly (research D4) but never orders test-before-fix. Adversarial Review #1 established that a rendered-text-only test passes against two of the three unfixed sites; nothing downstream forces anyone to observe that. Without a red gate, a test written after the fix that quietly regressed to `caplog.text` is indistinguishable from a correct one | `plan.md` Test design and `research.md` D4 both describe the surface; neither imposes an order. Phase ordering in `plan.md` is silent | Closed in this file: Phase 2 precedes Phase 3, and T007's pass condition is a specific failure shape (cases 1, 2, 3, 5 red; case 4 green by construction), not merely a non-zero exit |
| **A4** | **MEDIUM** | **Scanning all of `record.__dict__` collides with `record.pathname` if the path-segment forbidden string is shortened.** The haystack includes `pathname`, an absolute path inside a checkout named `sentiment-analyzer-gsk`. The forbidden string `preprod/sentiment-analyzer` is safe, but the near-miss `sentiment-analyzer` matches every record and fails for a reason unrelated to the ARN. No artifact mentions it. Q3 did this analysis for `SNS_TOPIC_ARN`, `ALERT_TOPIC_ARN` and `AWS_REGION` but stopped at environment values and never considered the record's own intrinsic attributes | `record.pathname` for the handler logger is the absolute path to `src/lambdas/ingestion/handler.py` under the checkout root | Closed in this file: T006 states the constraint and pairs it with the existing `arn:aws:` near-miss warning |
| **A5** | LOW | **Enumeration count stated three ways.** `spec.md` FR-007 enumerates five and mentions the suffix in prose; `plan.md` says "five classes plus a sixth for completeness"; `research.md` D5 says "Six explicit forbidden strings". Adversarial Review #2 logged this as L2 and left it. All three reconcile at six, but three phrasings invite an implementer to assert five | `spec.md` FR-007, `plan.md` Test design, `research.md` D5 | Closed in this file only: T006 pins the assertion count at six and says so. The three source documents are left as written |
| **A6** | LOW | **`research.md` D3 attributes a quotation to the wrong docstring.** D3 says `configure_lambda_logging()`'s "own docstring says it 'never attaches handlers or formatters'". That sentence is in the **module** docstring of `src/lambdas/shared/logging_config.py`, not the function's. The claim itself is correct and verified | `src/lambdas/shared/logging_config.py:6-7` (module docstring) versus `:30-37` (function docstring) | Recorded, not fixed. No behavioural consequence |
| **A7** | LOW | **`spec.md` Q1 undercounts the `TD-024` contention.** Q1 says "both features would claim `TD-024`"; Adversarial Review #2 L1 already noted three siblings contain it. The conclusion (do not pre-reserve) is strengthened, not weakened | `spec.md` Q1, `plan.md` Adversarial Review #2 L1 | Recorded, not fixed. Rider 5 in this file forbids pre-reservation outright |

**Requirement coverage gaps**: none. 15 of 15 FRs and 7 of 7 SCs map to at least one task; see the
coverage tables above.

**Tasks with no requirement behind them**: T001 (interpreter precondition) and T015 (pull request
run) trace to no FR or SC. Both are deliberate. T001 guards every later `pytest` result against
`plan.md`'s stated Python 3.13 requirement, which the system interpreter does not satisfy. T015
exists precisely to be **non-closing**, capturing SC-002's "useful inverse" while stating in its own
pass condition that it closes nothing. Neither inflates the coverage tables.

**Unfalsifiable pass conditions**: none remaining. Every task that reads from `gh`, a pipe or a log
carries an explicit exit-code check plus a proof-of-read assertion (T002 and T016 a corpus-count
floor, T017 a row count, T018 a non-empty file check). The three places where an empty result is the
pass, T012 and T021, check `grep`'s exit code explicitly rather than inferring cleanliness from
silence. T015 is deliberately verdict-free and says so.

**Contradictions between artifacts**: A1 and A2 are the two live ones, both between `plan.md` (and,
for A1, the convention) and the measured repository rather than between two documents. Adversarial
Review #2 already resolved the post-clarification drift set (C1, H1 to H6, M1 to M3) by edit, and
spot checks confirm those fixes landed: `codeql-logging-convention.md` section 5b now carries the
public-repository correction; `plan.md` Terminal States now lists four states with
`PENDING-BRANCH-ANALYSIS` marked expected; `plan.md` Constraints and Project Structure both carry the
Q4 directory carve-out; `research.md` D5's second fixture ARN carries the full path segment. Two
Adversarial Review #2 items were knowingly left open in `spec.md` (M4, `CLOUD_REGION` absent from
FR-007's variable list; M5, FR-008b not saying where the query is recorded). This file closes both
operationally: T006 requires `CLOUD_REGION` be cleared or pinned, and T022 makes the Terminal State
Record the place the query is recorded.

**Live state cross-check**, 2026-07-30: alerts 148 (line 264), 149 (271), 150 (276) open at
`src/lambdas/ingestion/handler.py` with `fixed_at` null; 144 open at
`src/lambdas/shared/auth/oauth_state.py:104`; 22 through 25 dismissed with `fixed_at` null; 26 and 27
dismissed with non-null `fixed_at`; alert 117 `fixed_at` `2026-01-20T22:34:56Z` and alert 144
`created_at` the identical timestamp. Every factual claim the artifacts make about alert state checks
out. Token scopes `gist, read:org, repo, workflow`; repository `public`; `push: true`.

### Verdict

**PASS with two actionable findings, neither blocking implementation.**

A1 (HIGH) and A2 (MEDIUM) are both defects in the recorded verification procedure rather than in the
code design, and both are closed inside this task list before any implementer can trip on them. A1
additionally requires the one-line propagation into `codeql-logging-convention.md` carried by T020,
because that document is inherited by citation and would otherwise hand the sibling feature a query
that reads truncation as cleanliness. The code change design, the assertion surface, the terminal
states and the scope lock are all internally consistent and match the live repository. No CRITICAL
finding. Tasks are dependency-ordered, each independently checkable, and no pass condition is
unfalsifiable.

---

## Adversarial Review #3

Final gate before implementation. The reviewer authored none of these artifacts. Method was
**execution, not reading**: every read-only command `tasks.md` prescribes was actually run, plus a
throwaway implementation of T006's test design in `/tmp` executed against the unfixed handler to
verify T007's required failure shape. Nothing was written outside
`specs/001-ingestion-arn-logging/`. Adversarial Reviews #1 and #2 and the Cross-Artifact Analysis are
treated as settled history and are not rewritten.

Findings are numbered R1 onward to avoid collision with A1 to A7 above.

### What was executed, and what it returned

| Ran | Result |
|---|---|
| T001 interpreter | `3.13.0 (main, Jan 15 2026)`. PASS |
| T002 alerts baseline, verbatim | `gh` exit 0; corpus **137**; rule total **22**; all four row conditions verified: `148 open null handler.py:264`, `149 ... :271`, `150 ... :276`, `144 open null oauth_state.py:104`, `22-25 dismissed fixed_at=null secrets.py`. PASS |
| T002 floor justification | Unpaginated `per_page=100` returns **9** of this rule, number range **59 to 180**. Unpaginated with **no** `per_page` returns 30 alerts and **0** of this rule. Both claims verified |
| T003 capability probe | `gh auth status` exit 0; scopes `gist, read:org, repo, workflow`; `{"visibility":"public","permissions":{"admin":true,"push":true,...}}`. Verdict **`DISMISSAL-AVAILABLE`**. PASS |
| T004 banned terms | exit `1`, total `17`, feature-directory `0`. PASS on the numbers, but the file attribution was wrong (R9) |
| T005 suite baseline | `43 passed in 2.42s`, exit 0. PASS |
| T008 pass-condition grep | Returns **8** lines today (249, 250, 261, 262, 271, 276, **601, 602**), not the two the task assumes. **R1** |
| T012 all three greps | grep1 exit `1` (no sanitizer call); grep2 one line, `115:from src.lambdas.shared.secrets import get_api_key`; grep3 exit `1`. All three behave as specified |
| T013 `git status --porcelain` | Lists four untracked spec directories, three of them siblings'. Condition 1 fails against a correct implementation. **R2** |
| T014 all four scanners | `ruff check` 0 ("All checks passed"), `ruff format --check` 0 ("1 file already formatted"), `bandit` 0 (0 issues at any severity), `semgrep scan --config auto` 0 (**281 rules actually ran**, 0 findings, no login required). T014 is executable as written and the scanners are not silently skipping |
| T016 NOT-YET-EVALUABLE probe, verbatim | Printed **10 lines**, one `.[0]` per page. **R4** |
| T017 jq pipeline | Three rows printed, `PIPESTATUS[0]` 0. Mechanically sound |
| T018 loop | Ran with a stand-in `after` snapshot: both `diff_exit` 0, `secrets.py` 16 rows, `oauth_state.py` 2 rows, non-empty checks fire correctly. Mechanically sound, but blind outside its two hardcoded paths. **R3** |
| T020 / T021 checks | T021 `grep_exit=1`, no output: PASS, and live (grep exits 2 on a missing file). T020's paginate count is `0` today, correctly reflecting the not-yet-fixed state, but the check is too weak. **R6** |
| **T006/T007 design, implemented and run against the unfixed handler** | **5 failed, 2 passed.** Cases 1, 2, 3, 5 **RED**; case 4 **GREEN**. Exactly T007's required shape |
| Case-2 leak location | `leak '<tiingo ARN>' at ['dict:tiingo_secret_arn'] on msg='Running in degraded mode: Tiingo adapter unavailable'`. T007's third condition is real and satisfiable |
| **`caplog.text` control** | **PASSED** on the unfixed tiingo-only case. The campaign's central claim, that a rendered-text-only test proves nothing at the two `extra=` sites, is confirmed by execution rather than inherited |
| `record.pathname` collision control | Failed at `['dict:pathname']` with pathname `<checkout>/.venv/lib/python3.13/site-packages/botocore/credentials.py`. Real, and broader than stated. **R8** |
| SC-005 path census | This rule sits on **four** paths: `handler.py` 3, `secrets.py` 16, `oauth_state.py` 2, **`errors.py` 1**. **R3** |
| `rule@path` multiplicity census | Not a unique key. Open set: this rule at `handler.py` count **3** (alerts 150, 149, 148). Whole corpus max group sizes: `py/log-injection@dashboard/auth.py` **24**, `@ohlc.py` **17**, this rule `@secrets.py` **16**. **R13** |
| Mistyped-field-path reproduction | `.locatio.path`: `null_paths=137`, anchor `0`, **`jq_exit=0`**. Correct path: `null_paths=0`, anchor `16`, `jq_exit=0`. Filtered for this rule at this path under the typo: **`0`**, which is T016's PASS value. **R12** |
| Three-bucket diff, partial-loss direction | Fixture cutting `secrets.py` 16 to 1 plus a new alert at `parallel_fetcher.py`: `changed:[{secrets.py, before:16, after:1}]`, `appeared:[parallel_fetcher.py]`, `disappeared:[]`. Caught |
| Membership-only control, same fixture | `disappeared: []`. The 16-to-1 loss was **invisible**. Defect reproduced |
| Three-bucket diff, no-change direction | Identical before and after: all three buckets `[]`. No false positive |

Read, not run: `plan.md`, `spec.md`, `research.md`, `codeql-logging-convention.md`,
`checklists/requirements.md`, and the handler and test sources.

### Findings

| # | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| **R1** | **HIGH** | **T008's pass condition was unsatisfiable by a correct implementation.** It required the ARN-key grep to return "exactly two lines, both at 249-250". Lines **601-602** are `_get_config()`'s `os.environ["TIINGO_SECRET_ARN"]` / `["FINNHUB_SECRET_ARN"]` dict construction. They are not logging, they are load-bearing, and they survive the fix. A correct implementation returns **four** lines. An implementer taking the condition literally either halts on a phantom failure or, worse, refactors `_get_config()` to satisfy it, breaking the handler. This is the "control check that fails a correct implementation" class the campaign has hit before | `grep -n "tiingo_secret_arn\|finnhub_secret_arn" src/lambdas/ingestion/handler.py` returns 8 lines today; 601-602 are inside `_get_config()` | **Fixed.** T008's pass condition rewritten: line count exactly 4, plus a second grep asserting **0** of the survivors sit in a logging call, an f-string or a `RuntimeError` construction. That second grep is the part that actually encodes the requirement |
| **R2** | **HIGH** | **T013 condition 1 fails today, before any implementation work, because of sibling features' untracked directories.** This campaign runs four features in one shared worktree. `git status --porcelain` already lists `specs/001-bad-tag-filter-dead-suppression/`, `specs/001-codeql-coverage/` and `specs/001-oauth-provider-taint/`. T013 declares any path outside three permitted patterns "a breach of FR-013 and of SC-005". The dangerous failure mode is not the false alarm, it is an implementer "resolving" the breach by deleting three sibling agents' work | `git status --porcelain` returns 4 untracked directories, measured 2026-07-30 | **Fixed.** T013 now uses `git status --porcelain` with explicit sibling pathspec exclusions, counts lines outside the permitted set with `grep -cv` (must be 0), asserts the status file is non-empty first so an empty read cannot pass as clean, and carries an explicit "never delete a sibling directory" instruction |
| **R3** | **MEDIUM** | **T018 cannot detect the SC-005 breach it exists to detect, outside two hardcoded paths.** SC-005 requires alerts of this rule outside the handler to be unchanged **in count**. T018 loops over `secrets.py` and `oauth_state.py` only. `src/lambdas/shared/errors.py` (alert 1) is never read, and a regression surfacing at a fifth path is structurally invisible. A per-file loop cannot answer a corpus-level question | Path census: 4 paths carry this rule; T018 reads 2 of the 3 non-handler paths | **Fixed.** A whole-corpus before/after diff added to T018, filtering only `path != handler.py`, with a row-count floor of 15 (measured 19) as its proof-of-read |
| **R4** | **MEDIUM** | **T016's NOT-YET-EVALUABLE probe combines `--paginate` with `--jq`, the exact per-page defect rider 4 exists to prevent.** Run verbatim it emits ten `{commit_sha, created_at}` objects, one per page of analyses, with no rule for choosing among them. The task then says "compare the sha against the merge commit", singular. Line one happens to be right, which is what makes it dangerous: it works by accident and teaches the wrong shape inside the file that establishes the convention | Executed: `stdout_lines=10`, first row `c01017888484bd5a0fdec9a32ded42378829f6dc` (matches `main` HEAD) | **Fixed.** Replaced with a `per_page=1`, no-`--paginate`, file-plus-standalone-`jq` shape carrying an exit check and a row-count assertion |
| **R5** | **MEDIUM** | **T013 condition 5 names a command that cannot evaluate its own condition.** `git diff --stat` emits insertion and deletion counts per file. It contains no line numbers, so "shows a net change confined to the `256-277` region" is not checkable from its output. An implementer either reports a pass having verified nothing, or silently substitutes a different command | `git diff --stat` output format | **Fixed.** Condition 5 now reads `git diff -U0 ... \| grep -E '^@@'` and checks the hunk headers |
| **R6** | **MEDIUM** | **T020's mechanical check does not cover the defect T020 exists to fix.** The substantive defect in `codeql-logging-convention.md` is not the missing `--paginate`; it is the sentence `Empty output is the pass condition.` at line 112, sitting under an unguarded query, in the one document the sibling feature inherits by citation. T020's pass condition is `grep -c -- "--paginate" >= 1`. Add the flag, leave the sentence, and T020 passes while the vacuous pass ships to the sibling | Convention line 106 query has no `--paginate`; line 112 carries the sentence; `grep -c -- "--paginate"` returns `0` | **Fixed.** T020 now additionally requires the stale sentence to be **gone** (`grep` exit 1, and the task states that exit 2 is a FAIL so the absence is itself live-checked) and requires the replacement text to carry exit-code and floor language |
| **R7** | **MEDIUM** | **No artifact named the entrypoint, and the obvious guess is wrong.** T006 says "so the handler reaches line 249" and specifies patch targets, but never names the function under test. `from src.lambdas.ingestion.handler import handler` raises `ImportError`; the entrypoint is `lambda_handler` at `handler.py:168`, mentioned exactly once across all artifacts, in passing, in `plan.md` | Executed: `ImportError: cannot import name 'handler' from 'src.lambdas.ingestion.handler'` | **Fixed.** T006 now names `lambda_handler`, gives the call shape with a `MagicMock` context carrying `aws_request_id`, and notes that this mistake makes case 4 fail too, so T007's shape check catches it |
| **R8** | **MEDIUM** | **The `record.pathname` collision is broader than A4 states, and the case-5 sweep is hostage to third-party logging.** `caplog` captures records from `botocore`, `src.lambdas.ingestion.parallel_fetcher` and `src.lambdas.shared.failure_tracker` during the case-1 invocation. `caplog.records[0]` is a botocore record whose `pathname` is `<checkout>/.venv/lib/python3.13/site-packages/botocore/credentials.py`, so the shortened-string collision fires through dependency paths too, not only through the handler's own source path. An unrestricted sweep also makes this suite fail whenever any dependency logs a string that happens to match | Executed: pathname printed above; sweep captured 4 distinct logger names | **Fixed.** T006 now requires the per-record loops and the case-5 sweep to filter on `r.name`, and records the wider collision surface. The six forbidden strings are all ARN-specific enough to be safe today; the filter is what keeps that true |
| **R9** | **LOW** | **Rider 1, T004's rationale and Cross-Artifact Analysis A2 all misattribute the 17 banned-term matches.** They name `.secrets.baseline`, `docs/cleanup/diagram-drift.md` and `CLEANUP-BOARD.html`, which together account for **7** of 17. The largest contributor, `specs/1157-auth-cache-headers/` with **9**, is not mentioned at all, nor is `specs/1268-cors-404-headers/plan.md`. The count, the exit code and the "none of them is ours" conclusion are all correct; only the provenance is wrong. It matters because an implementer who sees the count move will look in the wrong three files | Executed: `grep '^  \./' /tmp/banned.out \| sed 's/:.*//' \| sort \| uniq -c` | **Fixed in rider 1** with the measured breakdown. A2's own text is left as the reviewer wrote it, per the append-only rule for prior reviews |
| **R10** | **LOW** | **The count-17 invariant in T013 is fragile under concurrent sibling work.** `check-banned-terms.sh` scans all of `specs/`, and three sibling features are writing there in this same worktree right now. A banned term landing in any sibling directory moves the total and fails T013 for a reason this feature did not cause | Four `001-*` spec directories untracked in one worktree | **Fixed.** T013 condition 3 demoted: the feature-directory count of `0` is the gate, the total is expected-but-not-binding, and the task says to diff the two `/tmp` capture files to attribute any movement |
| **R11** | **MEDIUM** | **T007's third pass condition was not observable from the test T006 specified.** T007 requires seeing the ARN arrive "through a `record.__dict__` value and **not** through the rendered message". T006's haystack helper joins `getMessage()` and every `str(v)` into one string, which discards the key. Pytest's assertion diff then shows only that the string is present somewhere in a blob. Confirmed by implementing T006 as written: a `where(record, needle)` helper had to be added before the required evidence appeared | Executed: with the helper, case 2 reads `at ['dict:tiingo_secret_arn']`; without it, the failure is an undifferentiated blob | **Fixed.** T006 now makes the location-reporting helper mandatory and requires its output in every assertion message |

| **R12** | **CRITICAL** | **A corpus floor does not protect against a wrong field path, and T016's gate reads `0` from a completely blind read.** Mistyping `.most_recent_instance.location.path` as `.locatio.path` makes `jq` return `null` for every alert. It does not error, it exits `0`. T016's `total` floor still passes because `total` is computed from `.rule.id`, a field the typo does not touch. `open_at_path` then evaluates to **`0`**, which is T016's PASS value. Every clause of the pass condition was satisfiable while reading nothing, and the blind read reports this feature's primary success criterion, SC-002, as met. This is the most dangerous finding in this review: it converts the feature's central gate into a rubber stamp via a one-character typo | Reproduced on the live corpus 2026-07-30: correct path `null_paths=0 anchor=16`; mistyped path `null_paths=137 anchor=0`; `jq_exit=0` **both times**. The filtered read for this rule at this path returned `0` under the typo | **Fixed.** T016 and T018 now carry two positive-anchor clauses each: `null_paths` must be exactly `0`, and a known-present value (`secrets.py`, floor 15) must be seen **through the same field path** the gate filters on. T002's conditions 3 and 4 were already an anchor of this shape and are now labelled as one so they cannot be reduced to a count |
| **R13** | **HIGH** | **`rule@path` is not a unique key, and R3's own corpus check compared membership where it needed multiplicity.** Measured on the live corpus, `py/log-injection@src/lambdas/dashboard/auth.py` holds **24** alerts under one key, `ohlc.py` 17, and inside this feature's own SC-005 scope `py/clear-text-logging-sensitive-data@src/lambdas/shared/secrets.py` holds **16**. A set-diff keyed on `rule@path` reports only whether a key exists, so 15 of those 16 could vanish silently. `secrets.py` is the single highest-value file in this feature's blast radius, the one FR-013 names explicitly, which is precisely where the blindness is worst | Reproduced: on a fixture cutting `secrets.py` from 16 to 1, membership-only returned `disappeared: []` while three-bucket returned `changed: [{key: ...secrets.py, before: 16, after: 1}]` | **Fixed.** T018's corpus check now builds `{key: count}` on both sides and reports **three** buckets, `disappeared` / `appeared` / `changed`, so a partial loss has somewhere to land. Verified in both directions including the no-change case, which returns all three empty |

Counts: 1 CRITICAL, 3 HIGH, 7 MEDIUM, 2 LOW. All 13 fixed by edit inside
`specs/001-ingestion-arn-logging/tasks.md`.

### Positive-anchor inventory

Applying the campaign rule that **exit code plus corpus floor is necessary and not sufficient**, every
absence-based check in this file was re-audited for a positive anchor. An anchor means a known-present
value is shown present **through the same field path** the pass condition filters on.

| Check | Absence it reads | Positive anchor | Status |
|---|---|---|---|
| **T002** | none (baseline capture) | conditions 3 and 4 print named paths verbatim through `.location.path` | **Anchored**, now labelled as such |
| **T016** | `open_at_path == 0` | `null_paths == 0` plus `secrets.py` count at least 15 | **Anchored** (added) |
| **T017** | rows claimed repaired | three rows must print; reads `.number`/`.state`/`.fixed_at`, and a mistyped field yields `null`, which is the **FAIL** direction | **Anchored by direction**, no change needed |
| **T018** per-file loop | per-alert row diff | `[ -s ]` non-empty check per snapshot | **Anchored** already |
| **T018** corpus block | three buckets empty | `null_paths == 0`, `secrets.py` anchor, `rows` floor | **Anchored** (added) |
| **T012** | three greps returning nothing | `grep` exit is checked explicitly; exit `2` on a missing file distinguishes "read failed" from "no match", and grep 2 prints a known-present line | **Anchored by exit code** |
| **T020** | stale sentence gone | `grep` exit `1` is the pass and exit `2` is declared a FAIL, so the file is proven readable | **Anchored by exit code** |
| **T021** | no line-number citations | same `grep` exit-code discipline | **Anchored by exit code** |
| **T013** scope lock | no path outside the permitted set | status file asserted **non-empty** before the `grep -cv` count | **Anchored** (added under R2) |

The two that needed real work were T016 and T018, and both were the gates carrying this feature's
success criteria. The `grep`-based checks were already safe for a reason worth stating: `grep`
distinguishes "no match" (exit 1) from "could not read" (exit 2), which is the exact distinction `jq`
does **not** make. That asymmetry is why the `jq` reads were the ones that failed this audit.

### Vacuous pass conditions

The sweep covered the SC block, the FR block, acceptance scenarios, Independent Tests, Edge Cases and
both decision gates (T019's branch table and T022's terminal-state table), per the campaign rule that
**an absence is never evidence until the reader proves the read was working**.

Result: the task list was in good shape on the exit-code-and-floor axis, but that axis turned out not
to be the whole test. R12 showed a floor-satisfying read that saw nothing at all, so the sweep was
re-run against the stronger standard and its results are tabulated below. T002 and T016 carry corpus floors, T017 a row count, T018 non-empty file checks, T012
and T021 explicit `grep` exit-code checks, T015 is deliberately verdict-free and says so. The three
genuine liveness holes found were all outside that hardened set: T013 condition 1 could be satisfied
by an empty status read (fixed), T018 was structurally blind rather than unproven (fixed), and T020's
own pass condition permitted the vacuous pass in the inherited convention to survive verbatim (fixed).
T020's replacement is itself now live-checked, since `grep` returns 2 rather than 1 on a missing file
and the task states that 2 is a FAIL.

### Ordering hazards

The four hazards already listed under "Ordering hazards, stated so they are not rediscovered" all
hold and were confirmed. Three more, none of which the list carried:

1. **T007 in isolation versus T011 in sequence.** T007 runs the new module alone; T011 runs the whole
   `tests/unit/lambdas/ingestion/` directory, where `test_handler.py`'s `env_vars` fixture sets
   `TIINGO_SECRET_ARN` to an unrelated `us-east-1` / `123456789` ARN. Both fixtures must pop on
   teardown or the isolation guarantee in T006 holds only in the isolated run. T006 already requires
   full teardown; this is the reason it matters, stated so it is not optimised away.
2. **The new test file is untracked when T014 runs.** `semgrep` scans **git-tracked files only** and
   reports success on a file it never opened. T014 happens to point semgrep at `handler.py` alone, so
   this is latent rather than live, but anyone widening T014's semgrep target to the test file will
   get a silent skip reported as a pass. Recorded, not fixed, since T014 as written is correct.
3. **T018's whole-corpus check must run after T016, not beside it.** It reuses
   `/tmp/codeql-alerts-after.json`, and T016 is the task that proves that file was not truncated. The
   dependency graph already orders `T016 -> T018`; the new corpus block does not change that.

### Highest-risk task

**T006.** Named explicitly. It is the only task that produces new code from prose rather than
executing a prescribed command, and its output is the feature's entire regression guarantee. It
carries six forbidden strings with two documented near-miss traps, a four-variable environment
isolation constraint including one variable (`CLOUD_REGION`) that no other artifact lists, a
non-obvious assertion surface, a mandatory duplicated autouse fixture, five cases of which one must be
green for a reason unrelated to the fix, an entrypoint name that was absent from every artifact until
this review, and a helper whose absence makes the next task's gate unobservable. Every one of those is
a way to write a file that looks right and proves nothing. T007 exists precisely because T006 cannot
be trusted on inspection, and T007's value is entirely contingent on T006 producing a discriminating
test rather than a plausible one.

### Most likely source of rework

**The pass conditions of T008 and T013, not the code change they guard.** Named explicitly. The code
change itself is four lines deleted and three comments added, fully specified, with the shape chosen
from in-repository precedent and the losing alternative named and forbidden. There is very little to
get wrong. The rework risk sits in the verification scaffolding around it: R1 and R2 were both control
checks that failed a correct implementation, and both would have sent an implementer to modify working
code, `_get_config()` in one case and sibling agents' directories in the other, to satisfy a check
rather than a requirement. That is rework that damages rather than merely wastes. Both are fixed
above; the class is worth watching because it produced two of this review's findings and, per the
briefing, a third of the campaign's.

### Verdict

**READY FOR IMPLEMENTATION**

One CRITICAL, R12, found in the corpus-wide wave after the first pass of this review and fixed by
edit. It deserves naming plainly: T016's pass condition, the gate carrying SC-002, could be satisfied
in full by a `jq` read that saw nothing, because a mistyped field path returns `null` rather than
erroring and the corpus floor was computed from a different field. Three HIGH findings, R1, R2 and
R13, were all blocking as written and all are fixed by edit in this file. The seven MEDIUM and two LOW findings are fixed. Every read-only command the task
list prescribes has now been executed against the live repository and the live GitHub API rather than
read, and each returned what the artifacts claim, with the eleven exceptions itemised above. T014's
four scanners were confirmed to actually run rather than silently skip. The RED gate was confirmed
achievable by building T007's target and observing the required failure shape, cases 1, 2, 3 and 5
red with case 4 green, and the `caplog.text` control was confirmed to pass on unfixed code, which is
the premise the whole test design rests on.
