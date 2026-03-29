# Quickstart: Fix Keyboard Navigation Test to Use .focus()

## Prerequisites

- Node.js 18+
- Playwright installed (`npx playwright install chromium`)
- Chaos dashboard running at a reachable URL

## Setup

```bash
cd e2e/playwright
npm install
```

No new dependencies required. All APIs used (`locator.focus()`, `toBeFocused()`, `getComputedStyle`) are built into `@playwright/test`.

## Run keyboard navigation tests

```bash
# Set the target URL (no fallback — will fail without this)
export BASE_URL=https://your-dashboard-url.example.com

# Run only keyboard navigation tests
npx playwright test keyboard-nav

# Run with headed browser for debugging
npx playwright test keyboard-nav --headed

# Run all tests (includes keyboard nav)
npx playwright test
```

## Verify headed/headless parity

```bash
# Run headless (default)
npx playwright test keyboard-nav
# Note: pass/fail results

# Run headed
npx playwright test keyboard-nav --headed
# Results must be identical
```

## Expected output

```
  keyboard-nav.spec.ts
    Programmatic Focus
      ✓ view tab buttons receive focus via .focus()
      ✓ safety control buttons receive focus via .focus()
      ✓ filter controls receive focus via .focus()
      ✓ pagination controls receive focus via .focus()
    Keyboard Interaction
      ✓ Enter activates focused button
      ✓ Space activates focused toggle
      ✓ Escape closes open modal
    Focus Indicators
      ✓ focused button has visible outline or ring
      ✓ focused link has visible outline or ring
      ✓ focused tab has visible outline or ring
    Canvas Focus Pass-Through
      ✓ Chart.js canvas does not trap focus
    View Transition Safety
      ✓ focus is not on a hidden element after view change
    Modal Focus Trap
      ✓ Andon cord modal traps focus on open
      ✓ focus returns to trigger on modal close
    Focus Order (single-Tab assertions)
      ✓ Tab from first nav tab moves to second nav tab
```

## Interpreting failures

- **toBeFocused() failure**: The element did not receive focus from `.focus()`. Check if the element is hidden (`x-show`), disabled, or has `tabindex="-1"`.
- **Focus indicator not visible**: The computed CSS outline/ring/shadow is zero or "none". Check DaisyUI focus utilities on the element.
- **Canvas traps focus**: The Chart.js `<canvas>` needs `tabindex="-1"` added in the dashboard markup.
- **Focus limbo after view change**: The dashboard needs to manage focus when `x-show` hides the active container.
- **Modal focus trap failure**: Verify the modal uses `<dialog>` with `showModal()` (not just `x-show` visibility toggle).
- **Headed/headless mismatch**: Should not occur with `.focus()` approach. If it does, check for browser-level focus policies in the Playwright config.
