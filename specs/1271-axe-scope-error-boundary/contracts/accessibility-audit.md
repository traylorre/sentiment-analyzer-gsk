# Contract: Accessibility Audit Helper

## Interface

### `runScopedAccessibilityAudit(page, options?)`

Runs an axe-core audit scoped to the main content container.

**Parameters**:
- `page`: Playwright Page object
- `options.scope`: CSS selector for audit scope (default: `[data-testid="chaos-dashboard-content"]`)
- `options.tags`: WCAG tags to audit (default: `['wcag2a', 'wcag2aa']`)
- `options.includeModals`: Whether to also audit visible modals (default: `true`)

**Returns**: `AuditResult` — violations, passes, incomplete, inapplicable counts.

**Behavior**:
1. Wait for page readiness (at least 1 visible interactive element in scope)
2. Run axe audit on the scoped container
3. If `includeModals` and a `[role="dialog"]` element is visible, run a second audit on the modal
4. Merge results
5. Return combined AuditResult

**Failure modes**:
- If scope selector matches zero elements: throw error (not a silent pass)
- If readiness gate fails (no interactive elements): throw error with diagnostic message
- If axe-core throws: propagate error (do not catch)

### `assertNoAccessibilityViolations(result, options?)`

Asserts that an audit result has no critical/serious violations.

**Parameters**:
- `result`: AuditResult from `runScopedAccessibilityAudit`
- `options.failOn`: Impact levels that cause failure (default: `['critical', 'serious']`)

**Returns**: void (throws on assertion failure)

**Failure modes**:
- If violations exist at `failOn` severity: throw detailed error with violation summary
- Moderate/minor violations logged as warnings but do not fail
