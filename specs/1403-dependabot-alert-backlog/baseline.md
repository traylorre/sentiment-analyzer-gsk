# Baseline before any dependency change

Measured 2026-10-10 on main 38f5a225 (card-15 branch point), before any manifest or lockfile edit.
The operator's rule: a test already failing here does not block the update, and is reported.

## Frontend (`frontend/`)

Node 20.20.2, the version Amplify builds with (`infrastructure/terraform/modules/amplify/main.tf`,
`nvm use 20`) and `frontend/.nvmrc` pins. `npm ci` clean.

| Check | Command | Result |
|---|---|---|
| build | `npm run build` | pass |
| typecheck | `npm run typecheck` | pass |
| lint | `npx eslint . -f json` | fail: 30 findings (29 errors, 1 warning) |
| unit | `npx vitest run --testTimeout=30000` | fail: 22 failed, 620 passed (642) |

The unit run uses `--testTimeout=30000` because under vitest's 5000 ms default the failing set
varies run to run: a different test exceeding 5000 ms fails each time (3 runs measured, 23 or 24
failures). With 30000 ms the set below is stable. The post-update run uses the same flag.

No CI workflow runs frontend vitest, eslint or build (`grep -l 'vitest\|npm run lint\|npm run build\|npm test' .github/workflows/*.yml` prints nothing), which is how these failures sit on main.

The 22 baseline unit failures:

```
tests/unit/app/auth/callback.test.tsx > OAuth Callback Page > Error Handling > should show error description when provided
tests/unit/app/auth/callback.test.tsx > OAuth Callback Page > Error Handling > should show error when provider denied (error param)
tests/unit/components/auth/oauth-buttons.test.tsx > OAuthButtons > should apply custom className
tests/unit/components/auth/oauth-buttons.test.tsx > OAuthButtons > should disable all buttons when disabled prop is true
tests/unit/components/auth/oauth-buttons.test.tsx > OAuthButtons > should render both Google and GitHub buttons
tests/unit/components/auth/user-menu.test.tsx > UserMenu > dropdown menu > should call signOut when sign out clicked
tests/unit/components/auth/user-menu.test.tsx > UserMenu > dropdown menu > should route to settings via router (no hard-nav) when settings clicked
tests/unit/components/auth/user-menu.test.tsx > UserMenu > dropdown menu > should show auth type label
tests/unit/components/auth/user-menu.test.tsx > UserMenu > dropdown menu > should show sign in with email option for anonymous users
tests/unit/components/auth/user-menu.test.tsx > UserMenu > dropdown menu > should toggle dropdown on click
tests/unit/hooks/use-tier-upgrade.test.ts > useTierUpgrade > should detect role upgrade and set success
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > broadcast > should include timestamp
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > broadcast > should post message with correct format
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > connect > should create BroadcastChannel when available
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > connect > should set up message handler
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > disconnect > should clear listeners
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > disconnect > should close the channel
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > message filtering > should ignore messages with wrong type
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > message filtering > should ignore messages with wrong version
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > on/off > should ignore messages from same tab
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > on/off > should register and call handlers
tests/unit/lib/broadcast-channel.test.ts > AuthBroadcastSync > on/off > should unregister handlers with off
```

## Land gate (`.hydrostat.json`)

| Command | Result |
|---|---|
| `terraform -chdir=infrastructure/terraform init -backend=false` | pass |
| `make validate` | pass after the init above (run without it, the lint stage's `terraform validate` fails on uninstalled modules) |
| `make test-unit` | pass: 4258 passed, coverage 80.21% |

## Preprod Amplify Playwright

Deploy run 38086859278 on main 38f5a225, job "Preprod Integration Tests", `sanity.spec.ts` and
`auth.spec.ts` on Desktop Chrome: 31 passed, 1 failed (`auth.spec.ts:24` "should show OAuth
buttons"). The suite is not currently passing, so `operational_rigour` resolves to the option
without a post-deploy Playwright run (`cards/15.json`).

## Alerts

`make check-security-alerts`: 28 open of 208 Dependabot records. Per-alert ranges from
`gh api --paginate 'repos/traylorre/sentiment-analyzer-gsk/dependabot/alerts?state=open&per_page=100'`.
Two advisories have no patched release: GHSA-vfj7-8cjw-p6xm (`braces <= 3.0.3`, #226) and
GHSA-7pqw-9j4j-h8q3 / GHSA-jmr9-qjv8-65gv (`extract-zip <= 2.0.1`, #199, #206).
