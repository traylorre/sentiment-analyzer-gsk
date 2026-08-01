# Carded, out of scope for the constitution prune

Per the brief: card what you find, do not fix it here.

## C-001: Caveman plugin evaluation

**Raised:** 31 July 2026, by the owner, mid-battleplan.
**Question:** should the Caveman token-reduction plugin be added to this repo?
**Status:** recommended against for this repo. Not adopted. Separate from this battleplan.

**Reasoning, recorded so it does not have to be rediscovered:**

Caveman compresses the model's **output** tokens. The ~1,700 word target adopted in finding
p0-002 is an **input** budget for an always-loaded document. They are different quantities and
Caveman does not move the constitution's number at all.

Vendor-adjacent write-ups claim 65-75% token reduction. Independent benchmarking measured
**15-25% in real coding sessions**, because most tokens go to reasoning and code generation,
which Caveman does not affect.

The documented degradation mode is disqualifying for this specific use. Benchmarking found
that under Caveman "caveats disappeared, constraints were flattened, and numbered instructions
became blunt fragments," worst when the model had to explain a tradeoff or name a failure mode.
This battleplan exists to remove contradictions from a normative document and to protect
content whose load-bearing element is a modal verb. Trap 3 was found precisely because a real
mandate carried no MUST or SHOULD keyword. Flattening constraints is the defect class being
removed.

It would also conflict with VOICE.md on authored artifacts: commit messages, PR bodies, review
comments.

**If revisited:** it is a session-scoped output-cost preference, defensible for cheap mechanical
chat. It should not touch authored artifacts or any normative document.

Sources: claudepluginhub.com/plugins/juliusbrussee-caveman, techbloat.com independent
benchmark, growwstacks.com test of the 65% claim, betterstack.com community guide.

## C-002: user menu does not close on outside click (REAL DEFECT, not a flake)

**Raised:** 31 July 2026, during the CodeQL burndown merge queue.
**Test:** `frontend/tests/e2e/dialog-dismissal.spec.ts:157 › Dialog Dismissal (Feature 1247) ›
user menu: outside click closes`, Desktop Chrome.

**I initially called this a flake on the reasoning that neither diff in play could reach the
test, and re-ran it. That was wrong on both counts and is recorded here so the reasoning is not
repeated.** Diff scope is not evidence about a failure; it is a reason to look, not a reason to
dismiss. The re-run also overwrote the CI log, destroying the original failure output. The
diagnosis below had to be recovered from the uploaded artifacts instead.

### Evidence that it is not a timing race

From `trace.zip`, the failing assertion:

```
expect(locator).toBeHidden() failed
Locator:  getByRole('menuitem').first()
Expected: hidden
Received: visible
Timeout:  5000ms
9 × locator resolved to <a role="menuitem" href="/auth/signin" data-radix-collection-item=...>
```

Playwright polled for the full 5000ms across **9 attempts** and the menuitem stayed visible
throughout. A race resolves in milliseconds. The menu never closed at all.

The accessibility snapshot at failure confirms it: the trigger is still `button [expanded]` and
all three menuitems are present. The failure screenshot shows the menu occupying roughly
x=13-267, y=433-660 in a 1280x720 viewport, while the test clicks at (640, 360), which lands on
the empty-state card in main content. **The click was genuinely outside the menu.**

### Hypotheses checked and discarded

- *The API health banner is interfering.* Discarded. `ApiHealthBanner` renders visible amber
  text when shown (`frontend/src/components/ui/api-health-banner.tsx:56-65`), and returns
  `null` when not. The failure screenshot shows no banner, and the `alert` node in the snapshot
  is empty, so it is a toast live region rather than the banner.
- *The component overrides dismissal.* Discarded. `frontend/src/components/auth/user-menu.tsx:75`
  is a plain controlled `DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}` over
  `useState(false)`, with no `modal` prop (so modal defaults to true) and no
  `onPointerDownOutside` or `onInteractOutside` handlers.

### Where the diagnosis stands

Nothing in the component explains it, so the mechanism sits in the Radix modal dismissable
layer, most likely in how `page.mouse.click()` interacts with the `pointer-events: none` that
modal Radix applies to `document.body`. That is a hypothesis and is **not yet confirmed.**

Note the test already carries scar tissue from this area: it clicks the trigger with
`force: true` and comments that a real click is required "because Radix DropdownMenu uses
pointer events."

### Prior art suggesting this is a recurring real defect, not noise

`git log` on this spec file shows it has been patched four times under flakiness framing, and
each was a genuine root cause: #868 "Fix 25 Desktop Chrome Playwright failures (10 root
causes)", #871 viewport-aware selectors, #872 "replace networkidle and blind animation waits",
#875 "Eliminate Green Dashboard Syndrome".

### Local reproduction attempted, and it did NOT reproduce

| Run | Result |
|---|---|
| The one test, isolated, `--repeat-each=5`, 1 worker | 5/5 passed, 36.1s |
| The whole spec file, `--repeat-each=2`, 4 workers | 14/14 passed, 48.6s |

Cross-test pollution inside the browser was the leading hypothesis and is now unsupported:
`beforeEach` only seeds auth cookies on the context, and Playwright gives each test a fresh
context, so Radix layer state cannot leak between tests. Running the whole file at 4 workers
did not surface it either.

**Status: real, intermittent, trigger condition not yet identified.** In CI it passed, then
failed hard, then passed on re-run. Not reproducible locally so far. This is the honest state;
it is not evidence of absence.

### Remaining differences between local and CI, none yet ruled out

1. CI runs the entire E2E suite under load with more workers. Local ran 1 file.
2. **CI's backend was erroring and local's was not.** The CI run logged repeated
   `botocore.errorfactory.ResourceNotFoundException ... Query operation` from
   `src.lambdas.dashboard.ohlc` against the timeseries table. The local mock backend served
   these cleanly. Failing API calls change React effect and render timing on the page under
   test.
3. `menuTrigger.click({ force: true })` at line 168 **skips Playwright's actionability checks**,
   including the stability check that waits for the element to stop moving. Under CI load,
   clicking a still-settling element can land a pointerdown that Radix's DismissableLayer
   attributes to inside the layer, which would leave the layer armed such that the later
   outside pointerdown does not dismiss. This is the best-supported hypothesis: it explains
   intermittency, explains why it fails hard rather than racing, and the `force: true` plus the
   in-file comment "Must use regular click (not evaluate) because Radix DropdownMenu uses
   pointer events" show this area has already been fought over once.

### How to test hypothesis 3

Drop `force: true` and let actionability gate the click, or wait for the menu's open animation
to settle before clicking outside. Then run the full suite under artificial load. If the fix is
adopted, it must be demonstrated failing first against the unfixed test under load, otherwise
it is indistinguishable from the re-run that "fixed" it today.

### Do not close this by re-running CI

#994 merged at 2026-07-31T21:01:33Z on a green re-run. The merge does not resolve this. The
defect is now on main, unexplained, and will recur.

## C-003: external reference reachability

`Sensitive Security Documentation` (constitution lines 505-520) points at
`../sentiment-analyzer-gsk-security/`, a separate private repository. Criterion 6 requires every
reference reachable in one hop from the entry document. A reference to a repo the reading agent
may not have checked out is not reachable in the sense the criterion means.

Not resolved here because it is a policy question about what the criterion covers, not a defect
in the prune. Raise during F1 scoping.
