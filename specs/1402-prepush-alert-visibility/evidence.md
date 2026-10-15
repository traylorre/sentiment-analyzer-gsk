# Evidence: spec 1402

Measured 2026-10-10 on `card-10`, `gh` 2.97.0, authenticated as `traylorre`
(scopes `gist, read:org, repo, workflow`), repository `traylorre/sentiment-analyzer-gsk`.

## Reference counts

Taken with `gh api '<endpoint>?per_page=100' --paginate --slurp` and `jq 'add | length'`:

| Family | Corpus, all states | Open | States |
|---|---|---|---|
| code scanning | 156 | 0 | fixed 139, dismissed 17 |
| dependabot | 208 | 28 | fixed 172, open 28, auto_dismissed 8 |
| secret scanning | 0 | 0 | endpoint answers `[[]]` |

The instruction `AGENTS.md` carried before this change printed `0`, exit 0.
The card's own census command, `--paginate --jq length` over code scanning, printed `100` then `56`.

## Success criteria

| SC | Run | Result |
|---|---|---|
| SC-001, SC-002 | `python3 scripts/check_security_alerts.py` | code scanning CLEAN, 0 open of 156; dependabot FINDINGS, 28 open of 208; `VERDICT: FINDINGS (exit 1)`. Both corpora equal the reference counts and exceed 100 |
| SC-003 | `path` field set to `most_recent_instance.locatio.path` | exit 2, `field anchor 'path': most_recent_instance.locatio.path resolves on 0 of 156 records` |
| SC-004 | dependabot `state` field set to `stat` | exit 2, `vocabulary anchor: 208 of 208 records carry a state outside [...] at stat: None x208` and `field anchor 'state'` |
| SC-005 | real `gh api` single page wrapped as one slurped page | exit 2, `corpus floor: fetched 100 records, floor is 156` and `floor is 208` |
| SC-005, variants | `--paginate` dropped; both `--paginate` and `--slurp` dropped | exit 2: `gh exited 1: --paginate required when passing --slurp`; `gh output is not a list of pages` |
| SC-006 | `GH_CONFIG_DIR=$(mktemp -d) GH_TOKEN=invalid` | exit 2, `gh exited 1: gh: Bad credentials (HTTP 401)` for both families; no `VERDICT: CLEAN` line |
| SC-006 | `PATH=/nonexistent` | exit 2, `gh is not installed or not on PATH` |
| SC-007 | unit test `test_check_is_clean_only_when_every_family_is_clean` | the clean verdict line names records examined; each family line names its corpus and floor |
| SC-008 | `make check-alert-query-copies` before the sweep | FINDINGS, `AGENTS.md:88` |
| SC-008 | `make check-alert-query-copies` after the sweep | `anchored on scripts/check_security_alerts.py: code-scanning/alerts, dependabot/alerts`, `VERDICT: CLEAN` |
| SC-009 | unit tests | unreadable file, missing sanctioned file and a sanctioned file lacking an endpoint each exit 2 |
| SC-010 | `AGENTS.md` | one alert instruction, naming `make check-security-alerts`; no raw query (the copy scan above) |
| SC-011 | `git diff origin/main -- Makefile .githooks .pre-commit-config.yaml` | Makefile adds two targets and their `.PHONY` entry; `validate` and the hooks are unchanged |

`make check-security-alerts` returns make's exit 2 for both failure verdicts; the script's own exit
is 1 or 2, and the `VERDICT:` line names which.

## Test mutants

Each anchor knocked out in `scripts/check_security_alerts.py`, then
`pytest tests/unit/scripts/test_check_security_alerts.py` run (32 tests):

| Mutant | Failed |
|---|---|
| corpus floor disabled | 2 |
| vocabulary anchor disabled | 2 |
| field anchors disabled | 3 |
| sanctioned-location anchor disabled | 1 |
| verdict precedence `max` to `min` | 1 |
| `--paginate` dropped from the command | 1 |
| copy-scan exclusions disabled | 1 |
