# Quickstart: waitForResponse race regression guard

**Feature**: `002-waitforresponse-lint-guard`
**Prerequisite**: Feature 001 has landed and `scripts/scan-waitforresponse-race.py` exists.

---

## Run the detector directly

```bash
cd "$(git rev-parse --show-toplevel)"
python3 scripts/scan-waitforresponse-race.py; echo "exit=$?"
```

Expected on a healthy post-001 tree:

```
RACY 0 / PROMISE-FIRST 16 / OTHER 1, total 17   (48 files scanned)
exit=0
```

**Do not "correct" the 16 or the 17.** The pre-001 tree holds 34 call sites (27 racy, 6
promise-first, 1 other), and the intuitive expectation is that the total stays at 34 after the
sweep. It does not. 001 routes 18 of the 27 through `searchAndAwaitResponse(...)`, and those cease
to be wait call sites; the helper adds one internal wait back. `34 − 18 + 1 = 17`, of which 16 are
promise-first. These figures come from 001 SC-001 and 001 T018 criterion 1. If the detector prints
something else, the detector is wrong — not this document.

No venv activation needed, and that is deliberate: the CI `Lint` job has no venv, so if this
command needs one, the guard is broken in CI (spec FR-005).

---

## Run the local enforcement point

```bash
pre-commit run scan-waitforresponse-race --all-files
```

Or the whole config, the way CI does:

```bash
pre-commit run --all-files
```

---

## Prove the guard actually works

Installing a guard and observing green proves nothing. This repo contains a guard that is present,
unskipped, green, and inert (`check-false-pass-patterns`, documented by its own authors at
`pr-checks.yml:236-240`). The only evidence that matters is a planted violation.

### 1. Plant a violation

Create `frontend/tests/e2e/__scratch-race.spec.ts`:

```ts
// Target: Customer Dashboard (Next.js/Amplify)
import { test } from '@playwright/test';

test('planted violation - never commit this', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('textbox').fill('AAPL');
  // RACY: listener registered after the action that triggers the request
  await page.waitForResponse((r) => r.url().includes('/api/v2/tickers'));
});
```

### 2. Assert it fails in all local modes

```bash
# (a) local commit path, violation staged — this is what SC-002 decides
git add frontend/tests/e2e/__scratch-race.spec.ts
git commit -S -m "planted violation (should be refused)"; echo "mode-a exit=$?"
                                                                     # expect non-zero, no commit created

# (b) CI invocation shape: clean index, whole tree
git restore --staged frontend/tests/e2e/__scratch-race.spec.ts
pre-commit run --all-files; echo "mode-b exit=$?"                    # expect non-zero

# (c) CI environment shape: no site-packages, stdlib only
python3 -I -S scripts/scan-waitforresponse-race.py; echo "mode-c exit=$?"
                                                                     # expect non-zero
```

**Mode (c) must be `-I -S`, not `env -u VIRTUAL_ENV`.** The obvious way to write "run it outside the
venv" does not work and was caught in AR#2 as finding N-01. Unsetting `VIRTUAL_ENV` removes a
marker variable but leaves `.venv/bin` on `PATH`, so `python3` still resolves inside the venv:

```
$ source .venv/bin/activate
$ env -u VIRTUAL_ENV bash -c 'command -v python3'
/home/…/sentiment-analyzer-gsk/.venv/bin/python3      # still the venv
```

Scrubbing `PATH` instead is worse: `/usr/bin/python3` on a CLAUDE.md-conformant machine is 3.12 or
3.10, so the test would run the wrong interpreter and its result would say nothing about the CI
runner. `-I` (isolated) plus `-S` (no `site`) keeps the 3.13 interpreter while removing
site-packages entirely, which is exactly the property FR-005 requires. Confirmed locally: under
`-I -S`, stdlib imports succeed and `import yaml` raises `ModuleNotFoundError`.

Mode (c) is not redundant with (b). Modes (a) and (b) both run in a shell where `.venv` exists and
is importable, so neither can detect a detector that quietly depends on a third-party package. That
was AR#1 finding F-03; N-01 is the same trap one level down, which is why the mechanism is spelled
out here rather than left to the reader.

### 2b. Assert it fails in the real CI environment

Local modes prove the detector's properties. Only CI proves the wiring.

```bash
git checkout -b tmp/gate-red-team
git add -f frontend/tests/e2e/__scratch-race.spec.ts
git commit -S -m "DO NOT MERGE [gate red-team] planted violation"
git push -u origin HEAD
gh pr create --draft --title "DO NOT MERGE [gate red-team]" --body "Verifies 002 guard fails a required check."
gh pr checks --watch
```

Expect the **`Lint`** check to report failure. Close the PR and delete the branch afterwards. This
mirrors Feature 1400's T006, which used the same draft red-team PR to prove a gate could actually
fail rather than assuming it.

### 3. Revert and assert green

```bash
rm frontend/tests/e2e/__scratch-race.spec.ts
pre-commit run --all-files; echo "clean exit=$?"                    # expect 0
git status --short                                                   # expect empty
```

The planted violation is **never committed** (SC-015).

### 4. Prove an empty scan root fails

```bash
mv frontend/tests/e2e /tmp/e2e-parked
python3 scripts/scan-waitforresponse-race.py; echo "empty-root exit=$?"   # expect non-zero
mv /tmp/e2e-parked frontend/tests/e2e
```

If this exits 0, a future directory rename silently disables the guard forever (spec FR-013).

### 5. Measure the cost

```bash
time python3 scripts/scan-waitforresponse-race.py
```

Record the real figure. Budget is under 2 seconds (SC-010). An estimate does not satisfy the
criterion; the Stage 1 draft's "roughly ten files" guess was wrong by 5x, which is why measurement
is required.

---

## Where the guard runs

| Point | Trigger | Blocks a merge? |
|---|---|---|
| `repo: local` pre-commit hook | `git commit` | No — bypassable with `SKIP=` |
| Step in the **`Lint`** job | Every PR to `main` | **Yes** — `Lint` is a required status check |
| `Pre-commit Hooks` job (ride-along) | Every PR to `main` | No — job is not in the required contexts |
| `make validate` | Manual | No |

`main`'s required contexts are `["Secrets Scan", "Lint", "Run Tests"]`. Verify with:

```bash
gh api repos/traylorre/sentiment-analyzer-gsk/branches/main/protection \
  --jq '.required_status_checks.contexts'
```

If `Lint` ever leaves that list, this guard becomes advisory and the enforcement point must move.
That is the feature's single external dependency.

---

## When the guard fires on your commit

Do not suppress it. There is no allowlist, no baseline, and no exemption mechanism, deliberately
(spec FR-009). Fix the ordering:

```ts
// Before — RACY: the request can complete before the listener exists
await searchInput.fill('AAPL');
await page.waitForResponse((r) => r.url().includes('/api/v2/tickers'));

// After — PROMISE-FIRST
const responsePromise = page.waitForResponse(
  (r) => r.url().includes('/api/v2/tickers'),
  { timeout: 15000 }
);
await searchInput.fill('AAPL');
await responsePromise;
```

Playwright's own documentation states the rule: *"Ensure the promise is initiated before the action
that triggers the request."*

If your shape is legitimately neither — an intervening assertion, say — the detector classifies it
`OTHER`, prints it under the "requires human triage" banner, and does **not** block your commit.
