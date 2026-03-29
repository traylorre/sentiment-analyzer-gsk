# Research: Scope axe-core to Error Boundary Element

## Decision 1: axe-core Scoping API

**Decision**: Use `AxeBuilder(page).include('selector')` to scope audits to the main content container.
**Rationale**: `@axe-core/playwright` provides `.include()` and `.exclude()` methods that accept CSS selectors. `.include()` restricts the audit to only elements matching the selector, which is exactly what we need to exclude CDN elements.
**Alternatives considered**:
- Full page audit with `.exclude()` for CDN elements — rejected because CDN injections are unpredictable and the exclude list would be fragile.
- Custom axe-core configuration via `axe.configure()` — overkill for scope restriction, better suited for custom rules.

## Decision 2: WCAG 2.1 AA Rule Filtering

**Decision**: Use `AxeBuilder(page).withTags(['wcag2a', 'wcag2aa'])` to restrict to WCAG 2.1 AA rules.
**Rationale**: Without `withTags`, axe-core runs ALL rules including AAA and best-practice rules. This produces violations outside the stated conformance target and creates noise.
**Alternatives considered**:
- `runOnly` with specific rule IDs — too brittle, requires updating when axe-core adds new AA rules.
- No filtering with severity gating — still produces AAA violations in reports, confusing for developers.

## Decision 3: Hydration Readiness Gate

**Decision**: Assert at least 1 visible button element exists within the scope container before running axe audit.
**Rationale**: If Alpine.js hydration fails silently, the container exists but is empty. Auditing an empty container produces zero violations (false green). Checking for a minimum interactive element count catches this.
**Alternatives considered**:
- Wait for Alpine.js `x-init` completion event — requires modifying dashboard code for test observability, higher coupling.
- Wait for network idle — doesn't guarantee Alpine.js has hydrated the DOM.
- Wait for specific element count — too fragile if dashboard structure changes.

## Decision 4: Modal Scanning Strategy

**Decision**: Run a second axe audit scoped to `[role="dialog"]` when a modal is visible.
**Rationale**: Alpine.js/DaisyUI modals may render outside the main content container (as body-level siblings). A separate audit with `[role="dialog"]` catches any modal, regardless of where it's mounted.
**Alternatives considered**:
- Single audit on `body` — defeats the purpose of scoping, reintroduces CDN false positives.
- Include modal container in main audit scope — fragile if modal placement changes.

## Decision 5: Version Pinning Strategy

**Decision**: Pin `@axe-core/playwright` to `^4.10.0` (exact minor, patch range).
**Rationale**: Major version pins prevent breaking changes. Minor version pins prevent rule reclassification from breaking CI. Patch updates are safe (bug fixes only).
**Alternatives considered**:
- Exact pin (`4.10.0`) — too restrictive, misses important bug fixes.
- Major pin only (`^4`) — allows minor upgrades that could reclassify rule severity.
- No pin — supply chain risk + CI instability.

## Decision 6: data-testid Selector

**Decision**: Add `data-testid="chaos-dashboard-content"` to the main content container div in chaos.html.
**Rationale**: `data-testid` is a testing convention that doesn't affect production behavior, is stable across CSS refactors, and is explicitly for test infrastructure.
**Alternatives considered**:
- CSS class selector (`.container.mx-auto`) — fragile, changes with Tailwind refactors.
- `role="main"` — semantic but might conflict with existing ARIA roles or screen reader behavior if misapplied.
- `id` attribute — global uniqueness required, potential conflicts with other features.
