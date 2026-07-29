# Data Model: Make the SAST Semgrep Step a Real Gate

**Feature**: 001-semgrep-gating | **Date**: 2026-07-29

This feature has no data entities in the storage sense (no DynamoDB, no API payloads). The spec's Key Entities are process concepts; their concrete form:

| Concept | Concrete form | States / invariants |
|---------|--------------|---------------------|
| SAST gate | The semgrep block of the Makefile `sast` recipe (lines 77-84 pre-change; heading 77 and trailing echo 84 survive the change) | Pre: skip-if-missing, swallow, stderr-discard. Post: loud-fail-if-missing, findings propagate exit code, stderr visible. Invariant: bandit lines byte-identical (FR-007); scan flags byte-identical (`--config auto --error --severity ERROR --severity WARNING src/`). |
| Baseline disposition | 3 items: 2 Dockerfile `nosemgrep` suppressions with justification, marker on its own line ABOVE the CMD (R5a — same-line comments corrupt CMD per AR#2 F1), 1 real fix `filter="data"` + traversal-rejection unit test + nosemgrep rider ABOVE the `with` line (R5b — rule ignores the filter argument) | Invariants: every suppression has an adjacent justification comment (SC-006); the CMD lines are byte-identical to main; the nosec comment on sentiment.py:118 is untouched (bandit-migration ownership). |
| Gate severity | `--error --severity ERROR --severity WARNING` (confirmed R4) | Invariant: unchanged from today's invocation; baseline measured at exactly this threshold. |
| Version pin | `semgrep==1.172.0` in requirements-dev.txt AND pyproject.toml dev extra | Invariant: both surfaces carry the identical exact pin (FR-001); requirements-ci.txt untouched. |
| Board card record | "Orphaned validators" card in CLEANUP-BOARD.html CARDS JSON | Transition: evidence += dated semgrep-portion close; next_action rewritten to venv-done/CI-deferred split; lane UNCHANGED (LocalStack/mutmut still open — FR-009). JSON validity verified via raw_decode after edit. |
