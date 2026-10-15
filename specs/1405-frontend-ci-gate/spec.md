# Feature Specification: Frontend unit tests, lint and build under CI

**Feature Branch**: `card-17`
**Created**: 2026-10-14
**Status**: Implemented
**Card**: `cards/17.json`

## Problem

No workflow ran the frontend's vitest, eslint, typecheck or build, so all four drifted on `main`
unseen. Measured on `main` at `0643fd4e` under Node 20.20.2 (the major in `frontend/.nvmrc`):

| Check | Command (in `frontend/`) | Result |
|---|---|---|
| unit tests | `npx vitest run --testTimeout=30000` | 22 failed, 620 passed (642) |
| unit tests, default timeout | `npx vitest run` | the 22, plus 1 to 2 tests timing out at 5000 ms |
| lint | `npx eslint .` | 29 errors, 5 warnings |
| typecheck | `npx tsc --noEmit` | pass |
| build | `npm run build` | pass |

## Decision

- PR Checks gains a `Frontend Checks` job (`.github/workflows/pr-checks.yml`, job `frontend`): `npm ci`,
  then eslint with `--max-warnings=0`, `tsc`, vitest and `next build`. Each check is its own step and
  runs whenever the install succeeded, so one failure cannot hide another.
- Warnings fail the job. Five warnings were already on `main` while nothing read them.
- Lint is cleared by fixing code. A rule is disabled at a site only where the effect really is the
  right home, with the reason on the line above. There are two: the OAuth callback consuming one-shot
  state from `sessionStorage`, and `useDataFreshness` reading the clock when new data arrives.
- Code is never reshaped only to fall outside a rule's analysis. Measured with eslint-plugin-react-hooks
  7.1.1: `set-state-in-effect` does not report a synchronous `setState` inside a locally invoked async
  function before its first `await`, nor some after a ref guard. Both run as synchronously as the
  reported form, so neither shape counts as a fix.
- Dead code carrying lint errors is deleted, not refactored. Five modules had no consumer since they
  were added: `ui/offline-banner.tsx`, `ui/rate-limit-message.tsx`, `dashboard/threshold-preview.tsx`,
  `hooks/use-gesture.ts`, `hooks/use-animation.ts`. `git log -S"/<module name>'" -- frontend/src`
  finds no import of any of them; the one hit is the `@/hooks` barrel re-exporting `use-animation`,
  and nothing imports that barrel.

Rejected: downgrading the React Compiler rules to warnings. A gate that admits the known findings
certifies them. Rejected: a per-test timeout on the slow tests. Their cost is jsdom's role queries and
user-event clicks in whatever test renders first in a worker, not a property of those tests.

## Test failures: causes

| Cause | Tests | Fix |
|---|---|---|
| Vitest 4 rejects `new` on a mock whose implementation is an arrow function (`@vitest/spy` warns at `dist/index.js:337`) | 13: every `next/link` render through the `IntersectionObserver` mock, and the `BroadcastChannel` stubs | `function` implementations in `tests/setup.ts` and `broadcast-channel.test.ts` |
| `OAuthButtons` renders nothing without `availableProviders` (feature 1245) | 3 | tests pass providers; new cases for empty and filtering |
| OAuth callback maps provider error codes to fixed messages and never renders `error_description`, which is attacker-chosen URL text | 2 | tests assert the fixed copy and that the description is absent |
| `UserMenu` navigates through `next/link`, not `router.push` (feature 1394) | 1 | asserts the menu item's `href` |
| tier-upgrade store mock lacked `getState`; the hook's success path threw and polled to timeout | 1 | mock carries `getState`; test asserts the store update |
| broadcast test stubbed `crypto.randomUUID` after the module had read it | 2 | stub moved into `vi.hoisted` |

Timeouts: `testTimeout` is 20000 ms in `frontend/vitest.config.ts`. Under a full run with 8 workers the
slowest test measured 7.25 s (`price-sentiment-chart` "should render all resolution options"), and
`user-menu` "should toggle dropdown on click" 4.95 s. Probed in isolation, the first `getByRole` in a
worker costs 628 ms and the first `user.click` 1165 ms, against 36 ms and 663 ms on the second test.

Each test fix was proved binding with a mutant against the code it covers: ignoring the provider filter,
rendering `error_description`, skipping the store update, removing the same-tab filter, and changing the
settings `href` to `/account` each turn a test red. Changing it to `/settings/` does not, because
`next/link` normalises the trailing slash.

## Defects fixed on the way

Each has a test that fails on the code before card 17:

- OAuth callback, development only: the double-processing guard was state read from the effect's
  closure, so StrictMode's second run found the OAuth state cleared and showed "session expired" while
  the exchange was in flight. The guard is a ref.
- Price chart: the crosshair tooltip formatted dates with the resolution captured when the chart was
  created. After Day to 5m it dropped the time from intraday candles. It reads `resolutionRef`.
- Data freshness indicator: the aria-live announcement was a ref written after render, so a transition
  was announced on the next render, up to a minute later. It is state set in the transition's render.

## User-visible change

The configs page card no longer shows a sparkline. It plotted `Math.random()` points on every render.
Under the campaign goal a surface shows measured data or nothing.

## CI proof

Run from draft PR #1057 (branch `card-17-frontend-ci`), which exists only to run PR Checks.

| Run | Head | Frontend Checks | Evidence in the job log |
|---|---|---|---|
| 38667285857 | card-17 tip | success, 76 s | `Tests 665 passed (665)`, `Compiled successfully` |
| 38668088048 | deliberate break | failure | every check step failed and reported, none skipped |

The break added one `react-hooks/exhaustive-deps` warning, one type error and one failing test. Lint
failed on `ESLint found too many warnings (maximum: 0)` with no errors, which shows `--max-warnings=0`
binds. tsc failed on TS2322, vitest on `1 failed | 665 passed`, and the build on `Failed to type check`.
The branch was then reset to the card-17 tip.

On run 38667285857, Pre-commit Hooks and Dependency Vulnerability Scan failed for the reasons they fail
on `main` (detect-secrets on `cards/closed/*.json:5`, three expired pip-audit ignores). Neither is a
required check.

"Frontend Checks" becomes a required status check on `main` once this card lands (operator approval in
`cards/17.json`). Required earlier, every open PR against `main` would wait on a check that `main`'s
workflow does not yet define.

## Census commands

- Lint findings: `cd frontend && npx eslint . -f json` (29 errors and 5 warnings at `0643fd4e`, 0 and 0
  at the landing).
- Failing tests: `cd frontend && npx vitest run --testTimeout=30000 2>&1 | grep '^ FAIL'`.
- Workflows that run frontend checks: `grep -n 'npm run lint\|npm test\|npm run build' .github/workflows/*.yml`.

## Carded, not fixed

- `cards/NEW-card-17-alert-form-reset-on-rerender.json`: the alert form resets on every parent re-render.
- `cards/NEW-card-17-session-expiry-message-lost.json`: session-expiry messages are lost to the reload.
- `cards/NEW-card-17-pip-audit-ignore-expired.json` and `cards/NEW-card-17-detect-secrets-closed-cards.json`:
  two non-required PR Checks jobs red on every `main` push.
- `cards/NEW-card-17-branch-collision-claim-ref.json`: the pre-push collision hook refuses every push
  from a card worktree.
- `cards/NEW-card-17-pre-push-flips-core-bare.json`: a push from any linked worktree sets `core.bare=true`
  in the shared repository through a unit test's `git init`.
