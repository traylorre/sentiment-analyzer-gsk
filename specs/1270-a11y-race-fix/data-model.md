# Data Model: 1270-a11y-race-fix

## Types

This feature introduces two TypeScript interfaces for the shared helper. No database entities, no API contracts, no state transitions.

### A11yExpectation

Represents a single element's expected accessibility attributes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `selector` | `string` | Yes | CSS selector for the DOM element |
| `attributes` | `string[]` | Yes | List of attributes that must be present and non-empty. Special value `'textContent'` checks `element.textContent.trim()` |

### WaitForA11yOptions

Optional configuration for the wait helper.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `timeout` | `number` | No | `5000` | Maximum wait time in milliseconds |

## Relationships

```text
waitForAccessibilityTree()
  ├── accepts: Page (Playwright)
  ├── accepts: A11yExpectation[] (config)
  ├── accepts: WaitForA11yOptions (optional)
  ├── calls: page.waitForFunction() (Playwright API)
  └── used by: chaos-accessibility.spec.ts (3 tests)
```

## Validation Rules

1. `selector` must be a valid CSS selector (validated implicitly by `document.querySelector`)
2. `attributes` must be a non-empty array
3. `timeout` must be a positive integer if provided
4. `'textContent'` is the only special attribute value; all others are treated as DOM attribute names
