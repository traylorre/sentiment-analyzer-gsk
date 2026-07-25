# Implementation Plan — Feature 1386 upgrade-now-button

**Spec:** `./spec.md`
**Branch:** current worktree (no new branch)
**Scope:** Frontend-only. One-handler wire-up in `frontend/src/app/(dashboard)/settings/page.tsx` + a behavior test. No backend, no infra, no new AWS resources.

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| Two-dashboard hazard | ✅ | Customer dashboard only (`frontend/`, Next.js/Amplify). No `src/dashboard/` HTMX touch. Verify on the Amplify URL. |
| No new AWS resources | ✅ | Pure frontend handler + test. Zero infra. |
| Least-diff / idempotent | ✅ | Add an `onClick` (and, if `useRouter`, one import + hook call). No surrounding refactor. |
| GPG-signed commits | ✅ | `git commit -S` at implement time (not now). |
| Test guards the fix | ✅ | FR-006/US-3: click→navigation assertion replaces the presence-only gap. |
| No scope drift to billing | ✅ | `useTierUpgrade`/Stripe explicitly excluded (spec H1). |

**Result: PASS.** No violations, no complexity deviations.

---

## Technical Context

- **Component:** `SettingsPage` — a `'use client'` component (`settings/page.tsx:1`). It already
  uses hooks (`useAnimationStore`, `useAuth`, `useState`, `useCallback`) and imports from
  `lucide-react`, `@/components/ui/button`. It does **not** currently import `next/navigation` or
  reference `window.location`.
- **Button:** `@/components/ui/button` — `forwardRef<HTMLButtonElement>` spreading `...props`
  (`button.tsx:44-52`). Accepts `onClick` natively.
- **Render gate:** the prompt (and button) render inside `{isAnonymous && ( … )}` (`:127-142`),
  itself inside `{isAuthenticated && user ? ( … )}` (`:97`). Anonymous users are authenticated
  with an anonymous session, so the gate is reached. Handler must be a no-op for anyone else by
  virtue of the button not rendering.
- **Established pattern:** `user-menu.tsx` navigates anonymous users to `/auth/signin` via
  `window.location.href` (`:49`, `:131`). Sign-in page = `app/auth/signin/page.tsx`.

## Root-Cause Hypothesis (file:line evidence)

**Confirmed, not hypothetical.** The button has no click handler:

- `frontend/src/app/(dashboard)/settings/page.tsx:137` — `<Button size="sm" className="gap-2">`
  with children `<Mail/>` + `"Upgrade Now"` and **no `onClick`**.
- `frontend/src/components/ui/button.tsx:44-52` — renders a plain `<button {...props}>`; absent a
  handler, the click is inert.
- Working reference: `frontend/src/components/auth/user-menu.tsx:128-136` / `:44-54` navigate to
  `/auth/signin`.
- Misdirection ruled out: `frontend/src/hooks/use-tier-upgrade.ts:65-92` is Stripe post-payment
  polling, no checkout entry; no other "upgrade"/"checkout" initiation in `frontend/src` (grep).

## Approach

**Chosen: add a router-push `onClick` to `/auth/signin`.**

1. Import the App-Router navigation hook at the top of `settings/page.tsx`:
   `import { useRouter } from 'next/navigation';`
2. Inside `SettingsPage`, before the early returns (React rules-of-hooks — matches the existing
   `useCallback` placement at `:48`), get the router: `const router = useRouter();`
3. Wire the button:
   ```tsx
   <Button size="sm" className="gap-2" onClick={() => router.push('/auth/signin')}>
     <Mail className="w-4 h-4" />
     Upgrade Now
   </Button>
   ```
4. Add/extend a test that clicks the button and asserts navigation to `/auth/signin` (FR-006).

**Decision — `useRouter().push` over `window.location.href`:** Settings is already a client
component in the `(dashboard)` route group; `router.push` does an SPA transition (no full reload,
preserves in-memory auth store state) and is the idiomatic Next.js App-Router choice. `user-menu.tsx`
uses `window.location.href` (a hard reload), which is acceptable but heavier. Either satisfies FR-002;
`router.push` is preferred for least user disruption. If a test-environment mock makes `router.push`
awkward, `window.location.href = '/auth/signin'` is an accepted fallback identical to the sibling.

**Rejected alternatives**
- *Wire `useTierUpgrade.startPolling()`* — wrong domain (billing poll, no checkout), would appear to
  hang and never navigate. Rejected (spec AR#1 H1).
- *`<Button asChild><a href="/auth/signin">`* — works but risks a11y/semantic drift (NFR-001) and is
  a larger structural change than adding one handler. Rejected for least-diff.
- *Add `?redirect=/settings`* — signin page ignores it (C4); dead weight now. Rejected; return-to is
  a separate deferred item.

---

## Files Touched

| File | Change |
|------|--------|
| `frontend/src/app/(dashboard)/settings/page.tsx` | Add `useRouter` import + `const router = useRouter()`; add `onClick={() => router.push('/auth/signin')}` to the Upgrade Now `Button`. |
| `frontend/tests/e2e/settings.spec.ts` **or** a new `frontend/tests/unit/.../settings*.test.tsx` | Assert click → navigates to `/auth/signin` (behavior, not presence). |

No new components, hooks, stores, routes, or dependencies.

## Validation Strategy

**Static / build:**
- `cd frontend && npm run typecheck` — clean (new import + hook typed).
- `npm run build` — no App-Router misuse.

**Unit (preferred fast guard):**
- Render `SettingsPage` with an anonymous user (mock `useAuth` → `{ isInitialized:true, isAuthenticated:true, isAnonymous:true, user:{…} }`), mock `next/navigation`'s `useRouter` to a spy, click "Upgrade Now", assert `push` called with `/auth/signin`. (Mock `framer-motion` per repo pattern.)

**E2E (Amplify origin — FR / NFR-004):**
- Extend `settings.spec.ts`: as a guest, click the "Upgrade Now" button and assert the URL becomes `…/auth/signin` and the sign-in heading (`data-testid="signin-heading"`) is visible.
- Run against the Amplify URL, not the Lambda Function URL.

**Manual smoke:** Guest → Settings → Upgrade Now → lands on `/auth/signin`; no console error; button reachable via keyboard (Tab + Enter).

**Rollback:** revert the one commit; no data, no infra.

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Implementer wires `useTierUpgrade`/billing instead of sign-in | Med (label says "Upgrade") | Fix does nothing / hangs | Spec §1 + FR-003/FR-005 forbid it; plan Approach + Rejected-alternatives call it out explicitly. |
| Test asserts presence again, not behavior | Med (existing test is presence-only) | Regression can recur | FR-006/US-3 require click→navigation assertion; validation spells out the spy/URL check. |
| `useRouter` placed after an early return → rules-of-hooks violation | Low | Build/lint error | Place `const router = useRouter()` beside the existing top-level `useCallback` (before `if (!isInitialized)`). |
| Wrong dashboard | Low | Wasted work | Path is `frontend/…`; verify on Amplify URL (NFR-004). |
| Full reload vs SPA nav debated in review | Low | Churn | FR-002 accepts both; `router.push` chosen, `window.location` documented fallback. |

---

## Adversarial Review #2

**Stance:** hunt for spec↔plan drift and cross-artifact contradictions after Clarify.

### Cross-artifact consistency

| Check | Spec | Plan | Consistent? |
|-------|------|------|-------------|
| Broken location | `settings/page.tsx:137`, no `onClick` | same, in Root-Cause + Files | ✅ |
| Destination | `/auth/signin` (FR-003) | Approach step 3, test | ✅ |
| Nav mechanism | `useRouter` primary, `window.location` accepted (FR-002) | Decision = `router.push`, fallback documented | ✅ |
| Exclude `useTierUpgrade`/billing | FR-005, AR#1 H1 | Rejected-alternatives, risk row | ✅ |
| Anonymous-only render unchanged | FR-004, `:127` gate | Technical Context render gate | ✅ |
| Behavior test required | FR-006, US-3 | Validation unit + e2e | ✅ |
| Return-to gap deferred | §8, C4 | Approach "rejected `?redirect`" | ✅ |
| Frontend-only, no infra | NFR-002 | Constitution, Files table | ✅ |
| Two-dashboard hazard | NFR-004 | Constitution, validation on Amplify | ✅ |

### Drift findings

| ID | Sev | Finding | Resolution |
|----|-----|---------|-----------|
| D1 | LOW | Spec FR-002 lists `window.location.href` as co-equal; plan picks `router.push`. Could read as the plan overriding the spec. | Not a contradiction: FR-002 explicitly delegates the final call to the Plan ("see Plan for the decision"). Plan honors both; test allows either (assert navigation to `/auth/signin`, mechanism-agnostic where possible). |
| D2 | LOW | Plan offers both a unit test and an e2e extension; spec FR-006 says "unit and/or e2e". Risk of doing neither well. | Tightened: the **unit** spy test is the required minimum (fast, deterministic); the e2e click is a recommended add. Tasks make the unit test mandatory (T-level), e2e optional-but-preferred. |
| D3 | INFO | Rules-of-hooks placement is an implementation detail, not a spec item. | Captured in Plan risks; no spec change. |

### Gate
- CRITICAL: **0** · HIGH: **0** · Unresolved drift: **0** (D1/D2 clarified, D3 info)

**PASS.** Spec and plan are consistent. No structural rework → Plan 2nd pass skipped.
