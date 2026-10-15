# Tasks: Pre-Push Security Alert Check (spec 1402)

- [x] T001 `scripts/check_security_alerts.py`: `FAMILIES` table, `dig`, fetch via `gh`, anchors,
      verdicts, report (FR-001 to FR-012)
- [x] T002 `--scan-copies` mode with the sanctioned-location anchor (FR-016)
- [x] T003 `--print-corpus` for revising floors (FR-004)
- [x] T004 `tests/unit/scripts/test_check_security_alerts.py`: anchors, verdict precedence, fetch
      failures through a stub `gh`, detector findings and could-not-scan cases
- [x] T005 Makefile targets `check-security-alerts` and `check-alert-query-copies`, in `.PHONY`,
      outside `validate` (FR-014)
- [x] T006 Sweep: `AGENTS.md` alert instruction, `docs/cleanup-pristine/milestone-1-verifiable-auth.md`
      checklist pointer (FR-015)
- [x] T007 Live evidence in `evidence.md`: SC-001 to SC-006 and SC-008 against this repository,
      including the three mutants
- [x] T008 `make validate` and `make test-unit` green
