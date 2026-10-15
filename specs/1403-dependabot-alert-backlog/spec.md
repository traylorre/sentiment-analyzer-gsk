# Spec 1403: clear the open Dependabot alerts on main

**Card**: #15  **Branch**: `card-15`  **Status**: in progress

## Requirement

Every open Dependabot alert on main is fixed. None is dismissed (`cards/15.json`,
`runConfiguration.security_tier`). A new major version is acceptable where its dependent still
builds and runs. A test that fails on the baseline (`baseline.md`) does not block, and is reported.

## Fix routes

Measured against `gh api --paginate 'repos/traylorre/sentiment-analyzer-gsk/dependabot/alerts?state=open&per_page=100'`
on main 38f5a225.

### Root `package.json` (13 alerts, all dev tooling)

The root manifest exists for `@mermaid-js/mermaid-cli`, run by hand to render diagrams; nothing in
the Makefile, scripts or workflows invokes `mmdc`.

| Alerts | Package | Route |
|---|---|---|
| #199, #206 | extract-zip (no patched release) | removed: mermaid-cli 12 peers on puppeteer 25, whose `@puppeteer/browsers` 3 no longer depends on it |
| #214, #222, #224 | ip-address | removed with `proxy-agent`, same route |
| #190 to #194 | mermaid | 11.16.0 to 12.1.0 |
| #196, #213 | js-yaml | removed |
| #195 | dompurify | 3.4.12 to 3.4.16 |
| #205 | postcss-selector-parser | removed |

mermaid-cli 12 pulls `katex` ^0.16, which GHSA-238p-pmpm-9mq7 covers; an override to ^0.18.2 keeps
the bump from opening a new alert. Verified: `npm audit` 0 vulnerabilities, `npx mmdc` renders a
flowchart with a math label. These packages require Node >=22.12; nothing in CI or Amplify runs them.

### `frontend/` (15 alerts)

| Alerts | Package | Route |
|---|---|---|
| #210, #211, #221 | next | ^16.2.12 to ^16.3.8 (fix at 16.3.6); resolves to 16.4.0, and `eslint-config-next` is pinned 16.4.0 in step |
| #207, #208 | vitest, @vitest/mocker | ^4.1.0 to ^4.1.11 |
| #209 | sharp | override ^0.35.3 to ^0.35.4 |
| #201, #203, #204, #212, #219, #220, #202 | nanoid, browserslist, js-yaml, brace-expansion, postcss-selector-parser | `npm update`, lockfile only |
| #226 | braces (no patched release) | none available, below |

The `postcss` override changes from `"$postcss"` to the literal `"^8.5.18"`, the spec of the
direct `postcss` devDependency it referenced. npm 10.8.2, the npm of the Node 20 that Amplify and
`.nvmrc` use, cannot resolve a `$name` reference while building a peer set (`Unable to resolve
reference $postcss` from arborist `#loadPeerSet`), so `npm install` refused any change to this
manifest. `npm ci` reads the lockfile without building a tree, which is how it passed before.

`source-map-js` moves 1.2.1 to 1.2.2 (GHSA-68fv-2mgg-jv7q, high). Dependabot holds no record of
that advisory for this repo; `npm audit` reports it.

## #226 has no fix route

`braces <= 3.0.3` (GHSA-vfj7-8cjw-p6xm, published 2026-09-18) has no patched release. In
`frontend/` two dependents need it through `micromatch` 4, whose latest (4.0.8) still requires it:

- `tailwindcss` 3, directly and through `chokidar` 3. tailwindcss 3.4.19, the last 3.x, keeps both.
  Tailwind 4 has no dependencies.
- `eslint-config-next` through `@next/eslint-plugin-next`, which pins `fast-glob` at exactly 3.3.1
  in 16.4.0. Every `fast-glob` 3.x requires `micromatch` 4.

A Tailwind 4 migration removes the first path and leaves the second, so no upgrade in this repo's
control clears #226. It stays open until `braces` publishes a fix or `@next/eslint-plugin-next`
drops `fast-glob`; the fix then is `npm update braces` in `frontend/`. Dependabot auto-dismissed the
same advisory in the root lockfile (#227) as a development dependency; #226 is scoped runtime
because `tailwindcss` sits in `dependencies`.

## Advisories that will open next

`npm audit` in `frontend/` reports GHSA-rj75-hqrm-r3gf (`postcss-selector-parser < 7.1.6`,
medium, published 2026-10-05), with no Dependabot record yet. `tailwindcss` 3 and `postcss-nested`
6 require `postcss-selector-parser` 6.x, so its fix is the Tailwind 4 migration.

## Verification

Per `runConfiguration.operational_rigour`: frontend build, unit tests and lint compared against
`baseline.md`, the land gate, and `make check-security-alerts` after the push.

Measured after the update, `frontend/` on Node 20.20.2:

| Check | Result against `baseline.md` |
|---|---|
| build | pass |
| typecheck | pass |
| unit (`npx vitest run --testTimeout=30000`) | 22 failed, 620 passed: the same 22 tests by name |
| lint (`npx eslint . -f json`) | every baseline finding unchanged, 29 errors; 4 new warnings from `@next/next/no-location-assign-relative-destination`, a rule new in `eslint-config-next` 16.4.0, on lines this change does not touch |
| `npm audit` | remaining findings trace to `braces` (#226) and GHSA-rj75-hqrm-r3gf, both above |

Root: `npm audit` reports 0 vulnerabilities, and `npx mmdc` renders a flowchart with a math label
under Node 22.

The land gate runs at landing. `make check-security-alerts` can only confirm the alerts closed
once Dependabot rescans main after the landing.
