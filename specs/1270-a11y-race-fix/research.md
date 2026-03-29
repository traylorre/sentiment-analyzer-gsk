# Research: 1270-a11y-race-fix

## R1: Accessibility Tree Update Timing After DOM Mutation

**Decision**: Use `page.waitForFunction()` to poll for DOM attribute presence as a proxy for accessibility tree readiness.

**Rationale**: The browser accessibility tree updates asynchronously after DOM mutations. The update is triggered by attribute changes in the DOM (e.g., `aria-live`, `aria-label`, text content). By polling for these attributes, we implicitly wait for the accessibility tree to incorporate them. This is the same pattern used by the Playwright core team for their own accessibility testing utilities.

**Alternatives considered**:
- `page.waitForTimeout(N)` -- rejected: blind wait, non-deterministic, does not verify readiness
- `page.evaluate(() => window.getComputedAccessibleNode)` -- rejected: non-standard API, not available in all browsers
- `requestAnimationFrame` loop in test -- rejected: `page.waitForFunction()` already uses rAF internally
- `MutationObserver` in page context -- rejected: over-complex for attribute presence checking; waitForFunction is simpler

## R2: `page.waitForFunction()` Cross-Browser Reliability

**Decision**: Use `page.waitForFunction()` with default polling (rAF-based). No browser-specific workarounds needed.

**Rationale**: `page.waitForFunction()` is a core Playwright API with identical semantics across Chromium, Firefox, and WebKit. It polls using `requestAnimationFrame` which aligns naturally with the rendering pipeline. All 5 Playwright projects in the config (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit) use one of these three engines.

**Alternatives considered**:
- Custom polling with `setInterval` -- rejected: less efficient than rAF, can miss frame boundaries
- Browser-specific wait strategies -- rejected: no evidence of divergent behavior in this API

## R3: Axe-core Dependency on Accessibility Tree vs DOM

**Decision**: Wait for DOM attributes (ARIA attributes + text content) before running axe-core. This ensures axe-core's accessible name computation finds the correct data.

**Rationale**: Axe-core performs both DOM-based checks (raw attribute lookup) and computed accessibility checks (accessible name resolution via W3C algorithm). The race condition occurs when axe-core's accessible name computation runs before the browser has computed names for dynamically inserted elements. By waiting for the source data (text content, ARIA attributes) to be present in the DOM, we ensure axe-core's computation has the correct inputs.

**Alternatives considered**:
- Running axe-core twice and comparing results -- rejected: wasteful, non-deterministic
- Patching axe-core to wait internally -- rejected: third-party library, not our code to modify
- Using `aria-busy="true"` during render and waiting for removal -- rejected: requires component changes, which are out of scope per the spec
