# Tasks — Feature 1386 upgrade-now-button

**Spec:** `./spec.md` · **Plan:** `./plan.md` · **Branch:** current worktree
**Nature:** Frontend-only. Dependency-ordered. `[P]` = parallelizable with siblings.

> Planning artifact only. Do NOT execute (no `/speckit.implement`). Implementation happens in a later phase.

---

## Phase 0 — Reproduce & confirm

- **T001** Reproduce: on the Amplify customer dashboard as a Guest, open Settings, click **Upgrade Now** → confirm nothing happens (no nav, no console error). Confirms the inert-button behavior behind FR-001. (Covers: reproduces US-1 failure.)

## Phase 1 — Wire the handler

- **T002** In `frontend/src/app/(dashboard)/settings/page.tsx`, add `import { useRouter } from 'next/navigation';` and, inside `SettingsPage` **before** the `if (!isInitialized)` early return (rules-of-hooks — beside the existing `useCallback` at `:48`), add `const router = useRouter();`. (Covers: FR-002.)
- **T003** Add the click handler to the Upgrade Now button (`:137`): `onClick={() => router.push('/auth/signin')}`. Do not change the `isAnonymous` render gate, copy, or icon. **This is the fix.** (Covers: FR-001, FR-003, FR-004, US-1.)
- **T004** Confirm no `useTierUpgrade`/Stripe/checkout import was added and no new dependency/component/route was introduced — diff is confined to the import + hook + `onClick`. (Covers: FR-005, NFR-002, NFR-003.)

## Phase 2 — Regression test (required)

- **T005** Add a unit test (e.g. `frontend/tests/unit/app/settings-upgrade.test.tsx`) that renders `SettingsPage` with a mocked anonymous `useAuth` (`isInitialized:true, isAuthenticated:true, isAnonymous:true, user:{…}`), mocks `next/navigation`'s `useRouter` to a spy, mocks `framer-motion` per repo pattern, clicks the "Upgrade Now" button, and asserts the spy's `push` was called with `'/auth/signin'`. This replaces the presence-only gap. (Covers: FR-006, US-3.)
- **T006 [P]** (Preferred) Extend `frontend/tests/e2e/settings.spec.ts` (the existing guest block at `:75-86`): after finding the button, click it and assert the URL becomes `**/auth/signin` and the sign-in heading (`data-testid="signin-heading"`) is visible. Run against the Amplify URL, not the Lambda URL. (Covers: FR-006, US-2, NFR-004.)

## Phase 3 — Static validation (pre-push)

- **T007** `cd frontend && npm run typecheck` → clean (new import + `useRouter` typed). (Covers: NFR-003.)
- **T008 [P]** `cd frontend && npm run build` → succeeds (no App-Router misuse). (Covers: NFR-003.)
- **T009 [P]** `cd frontend && npm test` (Vitest) → the new unit test (T005) passes and fails if the `onClick` is removed (sanity-flip locally). (Covers: FR-006, US-3.)

## Phase 4 — Commit

- **T010** GPG-signed commit of the frontend change: `git commit -S`. Frontend-only, no infra. (Covers: NFR-002.)

## Phase 5 — Verify on the real customer dashboard (FR / Success #1)

- **T011** On the Amplify customer dashboard (`https://main.d29tlmksqcx494.amplifyapp.com/`) as a Guest: Settings → Upgrade Now → lands on `/auth/signin` (sign-in forms visible); no console error; button reachable/activatable via keyboard (Tab + Enter). NOT verified on the Lambda Function URL. (Covers: US-1, US-2, NFR-001, NFR-004, Success #1/#4.)
- **T012 [P]** Regression check: sign in / authenticated view of Settings shows **no** Upgrade prompt (gate unchanged). (Covers: FR-004, Success #2.)

---

## Requirement → Task coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (button invokes navigation on click) | T001, T003, T011 |
| FR-002 (established nav pattern / `useRouter`) | T002 |
| FR-003 (destination `/auth/signin`) | T003, T011 |
| FR-004 (anonymous-only render unchanged) | T003, T012 |
| FR-005 (no new dep/hook/route; no `useTierUpgrade`) | T004 |
| FR-006 (behavior/regression test) | T005, T006, T009 |
| NFR-001 (accessibility / native button) | T011 |
| NFR-002 (frontend-only, no infra) | T004, T010 |
| NFR-003 (least diff) | T004, T007, T008 |
| NFR-004 (two-dashboard hazard, Amplify verify) | T006, T011 |
| US-1 | T001, T003, T011 |
| US-2 | T006, T011 |
| US-3 | T005, T009 |

Every requirement maps to ≥1 task; no task lacks a requirement.

---

## Analyze — cross-artifact consistency

- **Coverage:** 6 FR + 4 NFR + 3 US → all covered (table). No orphan requirement; no stray task.
- **Ordering:** reproduce (T001) → wire handler (T002-T004) → test (T005-T006) → static validate (T007-T009) → commit (T010) → verify (T011-T012). No forward-dependency violation; the required behavior test (T005) precedes commit.
- **Constitution:** unchanged from Plan — PASS (customer-only, no infra, least-diff, GPG, Amplify-verify).
- **Terminology:** "Upgrade Now", `/auth/signin`, "anonymous/Guest", `useRouter().push`, line `:137` consistent across spec/plan/tasks.
- **Ambiguities:** none functional open (C5 label wording deferred to owner, non-blocking).

**Analyze result: consistent. No blocking issues.**

---

## Adversarial Review #3

**Stance:** find the task most likely to cause rework or a silently-failed fix; decide readiness.

### Highest-risk task: **T003 (wire the `onClick`) — specifically choosing the right action.**

**Why it's the crux:** the mechanical edit is trivial, but the *semantic* choice is where this goes
wrong. The label says "Upgrade Now", which biases an implementer toward a billing/paid flow and the
`useTierUpgrade` hook. Wiring that hook would compile, ship green, and **still do effectively nothing**
(it only polls after a Stripe webhook; there's no checkout to start), reproducing the original
"button does nothing" complaint in a subtler form. The correct action is a plain navigation to
`/auth/signin`.

**Likely rework:** if T003 targets billing, T011 verification fails (no navigation / hang) → redo.
Mitigation is inline and layered: spec §1 + FR-003/FR-005 forbid `useTierUpgrade`; T004 explicitly
checks the diff for such imports; the T005 unit test asserts `push('/auth/signin')` — a billing
wire-up fails that test before commit (T009).

### Other notable risks
- **T002 hook placement:** `useRouter()` after the `if (!isInitialized)` early return breaks
  rules-of-hooks → build/lint failure. Guard: T002 pins placement beside the existing top-level
  `useCallback`; T007/T008 catch it.
- **T005/T006 presence-not-behavior:** the exact trap that let the bug ship. Guard: task text
  mandates asserting `push`/URL, and T009 requires a local sanity-flip (remove handler → test fails).

### Gate

| Criterion | Status |
|-----------|--------|
| Every requirement has a task | ✅ |
| Highest-risk task identified + mitigated pre-commit | ✅ (T003 via T004 + T005/T009) |
| No open functional clarifications | ✅ (only C5 label wording deferred, non-blocking) |
| Constitution PASS | ✅ |
| CRITICAL / HIGH findings | 0 / 0 |

**READY FOR IMPLEMENTATION** (implementation deferred per battleplan — planning stops here).
