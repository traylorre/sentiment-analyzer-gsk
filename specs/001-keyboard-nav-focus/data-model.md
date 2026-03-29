# Data Model: Fix Keyboard Navigation Test to Use .focus()

## Entities

### FocusableElement

Represents an interactive element in the chaos dashboard that should be reachable and operable via keyboard.

| Field | Type | Description |
|-------|------|-------------|
| selector | string | CSS selector or data-testid used to locate the element |
| role | string | ARIA role or implicit role (e.g., "button", "link", "tab", "textbox") |
| label | string | Accessible name (text content, aria-label, or aria-labelledby) |
| expectedActions | ("Enter" \| "Space" \| "Escape")[] | Keyboard keys that should trigger an action on this element |
| isInsideModal | boolean | Whether this element is inside a modal dialog |
| viewContainer | string \| null | The x-show container this element belongs to, or null if always visible |

### FocusIndicator

Represents the visible CSS treatment that shows which element currently has keyboard focus.

| Field | Type | Description |
|-------|------|-------------|
| property | "outline" \| "outlineWidth" \| "boxShadow" | CSS property that provides the visual indicator |
| value | string | The computed CSS value when the element is focused |
| isVisible | boolean | Whether the computed value represents a visible indicator (non-zero width, non-"none") |

## Relationships

- Each FocusableElement has one or more FocusIndicators when focused.
- A FocusableElement with `isInsideModal: true` is only focusable when the modal is open.
- A FocusableElement with a non-null `viewContainer` is only focusable when that view is active (`x-show` is truthy).

## State Transitions

### Focus Lifecycle

```
Unfocused -> Focused (via .focus() call)
Focused -> Unfocused (via .blur(), focus moved elsewhere, or container hidden)
Focused -> Focus Limbo (container hidden via x-show without focus management)
Focus Limbo -> Unfocused (browser resets to body or test detects and reports)
```

### Modal Focus States

```
Page Focus -> Modal Open -> Focus Trapped in Modal
Focus Trapped in Modal -> Modal Close -> Focus Returns to Trigger
```

## Non-Persistent Model

These entities exist only at test time as conceptual test abstractions. They are not stored in any database or persisted between test runs. The helper functions in `keyboard.ts` operate on Playwright Locators that correspond to these entities.
