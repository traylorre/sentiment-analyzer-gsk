# Review Checklist: Chaos Dashboard Report Viewer

**Feature**: 1242-chaos-dashboard-reports
**Date**: 2026-03-22

## Code Quality

- [ ] All new Alpine.js methods follow existing naming conventions (camelCase)
- [ ] No inline styles -- all styling uses Tailwind/DaisyUI utility classes
- [ ] No hardcoded API URLs -- reuse existing `getApiKey()` and relative paths
- [ ] Error handling on all `fetch()` calls (try/catch with toast error display)
- [ ] No `console.log` left in production code (only `console.error` for actual errors)

## HTML Structure

- [ ] All new sections use semantic HTML (`<section>`, `<h2>`, `<table>`)
- [ ] All interactive elements have accessible labels (`aria-label` or visible text)
- [ ] All images/icons have `alt` text or `aria-hidden="true"`
- [ ] DaisyUI component classes used correctly (not mixing component systems)

## Performance

- [ ] Report API calls use `Promise.all()` for parallel fetching
- [ ] Reports are cached in Alpine.js state to avoid redundant fetches
- [ ] Chart.js instances are destroyed before re-creation (no memory leaks)
- [ ] No unnecessary re-renders (Alpine.js reactive getters used correctly)
- [ ] Report list limited to 100 experiments max

## Security

- [ ] API key passed via `X-API-Key` header (existing pattern)
- [ ] No sensitive data logged to console
- [ ] Chart.js CDN link has SRI integrity hash
- [ ] No XSS vectors (Alpine.js `x-text` auto-escapes, no `x-html` with user data)

## Responsiveness

- [ ] Tables use `overflow-x-auto` wrapper
- [ ] Grid layouts use responsive breakpoints (`grid-cols-1 md:grid-cols-2`)
- [ ] Font sizes readable on mobile (no text smaller than `text-xs`)
- [ ] Touch targets minimum 44x44px on mobile

## Backwards Compatibility

- [ ] Zero changes to existing Alpine.js state variables
- [ ] Zero changes to existing methods (startExperiment, stopExperiment, loadExperiments, etc.)
- [ ] Zero changes to existing HTML sections (navbar, scenario library, start form, active experiments, history)
- [ ] Zero backend changes (no Python, Terraform, or test file modifications)

## Edge Cases Verified

- [ ] Empty experiment list: shows empty state, not broken table
- [ ] API error: shows error badge, does not crash app
- [ ] Running experiment selected: shows warning, renders available data
- [ ] Diff with missing post_chaos: shows placeholder
- [ ] Diff with different scenarios: shows warning banner
- [ ] Trends with < 3 data points: shows message, not empty chart
- [ ] Very long error messages: truncated with expand option
