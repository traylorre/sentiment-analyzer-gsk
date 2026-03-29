# Research: Fix Keyboard Navigation Test to Use .focus()

## Decision 1: Programmatic .focus() Over Tab Key Simulation

**Decision**: Use Playwright's `locator.focus()` to set focus on target elements instead of `page.keyboard.press('Tab')` for sequential navigation.
**Rationale**: Tab key simulation in headless Chromium is unreliable because the browser's focus management differs from interactive mode. The browser may skip elements, focus internal browser UI, or behave differently based on OS-level focus policies. `.focus()` directly invokes the DOM focus API, which is deterministic regardless of browser mode. This eliminates the primary source of flakiness in keyboard accessibility tests.
**Alternatives considered**:
- Sequential Tab presses to walk the entire focus order — rejected because Tab behavior differs between headed and headless Chromium, causing CI flakiness (the exact problem this feature solves).
- `page.evaluate(() => document.querySelector('selector').focus())` — works but bypasses Playwright's auto-waiting and actionability checks. `locator.focus()` is preferred because it waits for the element to be attached and visible.
- `dispatchEvent('focus')` — rejected because it fires the event but doesn't actually move DOM focus, so `document.activeElement` wouldn't update.

## Decision 2: Tab Ban Enforcement and Single-Tab Exception

**Decision**: Ban all `page.keyboard.press('Tab')` usage for navigation. The only permitted pattern is the single-Tab focus-order assertion: `.focus()` on element A, `Tab` once, `toBeFocused()` on element B.
**Rationale**: FR-007 requires this distinction. A single Tab press after programmatic focus is reliable because the starting point is deterministic (set by `.focus()`). Chained Tab presses (2+) compound the unreliability — each press depends on the previous focus target being correct. The helper `assertFocusOrder(page, selectorA, selectorB)` encapsulates the single-Tab pattern so it's impossible to misuse.
**Enforcement**: Code review convention. The helper module provides the only sanctioned way to use Tab. Direct `page.keyboard.press('Tab')` should not appear in test files.

## Decision 3: Focus Indicator Visibility via Computed Styles

**Decision**: Assert focus indicator visibility by checking computed CSS properties (`outline`, `outlineWidth`, `boxShadow`) on the focused element.
**Rationale**: DaisyUI applies focus styles via Tailwind CSS utilities (`focus:ring`, `focus:outline`, `focus-visible:ring`). These compile to standard CSS properties. Playwright's `locator.evaluate()` can read `getComputedStyle()` to verify that the focused element has a non-zero outline width, a non-`none` outline style, or a non-`none` box-shadow. This approach is framework-agnostic — it works whether the style comes from DaisyUI, custom CSS, or browser defaults.
**Alternatives considered**:
- Screenshot comparison — fragile across browser versions, OS rendering differences, and CI environments. Maintenance burden is high.
- Checking for specific CSS classes (`ring`, `outline`) — couples tests to Tailwind utility names, which could change across DaisyUI versions.
- Using axe-core `focus-visible` rule — deferred to Feature 1271. This feature checks visibility; 1271 checks WCAG contrast compliance.

## Decision 4: DaisyUI Modal Focus Trap Testing

**Decision**: Test modal focus trap by opening the Andon cord confirmation modal, asserting focus moves inside the modal, pressing Tab to verify focus stays inside, then closing the modal and asserting focus returns to the trigger button.
**Rationale**: DaisyUI's `<dialog>` element (used for modals) has built-in focus trap behavior when opened via `showModal()`. The browser natively traps focus inside the dialog and returns it to the trigger on close. Alpine.js triggers `showModal()` via `x-on:click`, so the native behavior applies. Testing this verifies the dashboard hasn't broken the native focus trap (e.g., by using `x-show` instead of `showModal()`).
**Alternatives considered**:
- Using a focus-trap JavaScript library assertion — unnecessary because the browser's native `<dialog>` focus management is the mechanism. Adding a library would be testing the library, not the dashboard.
- Tabbing through all modal elements — violates FR-007 (Tab ban). Instead: focus the first modal element, Tab once, assert focus stayed inside the modal boundary.

## Decision 5: Chart.js Canvas Focus Pass-Through

**Decision**: Assert that Chart.js `<canvas>` elements either have `tabindex="-1"` or that focus passes through them (focus on the previous element, Tab once, focus lands on the next interactive element after the canvas).
**Rationale**: Chart.js renders to `<canvas>` elements which are not interactive but may receive focus if they have a default tabindex. A canvas that traps focus forces keyboard users to Tab through a non-interactive element with no keyboard affordance, which is a usability failure. `tabindex="-1"` removes the canvas from the tab order entirely. If `tabindex` is not set, the canvas should be naturally skipped.
**Alternatives considered**:
- Removing `<canvas>` from the DOM during keyboard tests — violates test isolation, changes the page state being tested.
- Adding `aria-hidden="true"` — hides from screen readers but doesn't affect focus order. Not sufficient alone.

## Decision 6: Alpine.js View Transition Focus Safety

**Decision**: After triggering an `x-show` view transition, assert that `document.activeElement` is either the `document.body` or a visible element. If the currently focused element is hidden, focus must be moved.
**Rationale**: Alpine.js `x-show` toggles CSS `display: none` on elements. If the focused element is inside a container that gets hidden, the browser may leave `document.activeElement` pointing to a hidden element (browser behavior varies). This creates a "focus limbo" where keyboard input goes to an invisible element. The test verifies the dashboard handles this correctly — either by listening for the transition and moving focus, or by the browser naturally resetting focus to `<body>`.
**Alternatives considered**:
- Ignoring view transitions — rejected because FR-008 explicitly requires this verification.
- Forcing focus to a known element after each transition — this is implementation advice, not a test decision. The test verifies the behavior regardless of how it's achieved.
