# Data Model: Scope axe-core to Error Boundary Element

## Entities

### AccessibilityViolation

Represents a single accessibility violation detected by axe-core within the scoped container.

| Field | Type | Description |
|-------|------|-------------|
| id | string | axe-core rule ID (e.g., "color-contrast", "label") |
| impact | "critical" \| "serious" \| "moderate" \| "minor" | Severity level |
| description | string | Human-readable description of the violation |
| help | string | Short help text for the violation |
| helpUrl | string | URL to dexa.com rule documentation |
| nodes | ViolationNode[] | Elements that violate the rule |

### ViolationNode

Represents a specific DOM element that violates an accessibility rule.

| Field | Type | Description |
|-------|------|-------------|
| html | string | Outer HTML snippet of the violating element |
| target | string[] | CSS selector path to the element |
| failureSummary | string | What needs to be fixed |

### AuditResult

Aggregate result of an accessibility audit on a scoped container.

| Field | Type | Description |
|-------|------|-------------|
| scope | string | CSS selector used for scoping |
| violations | AccessibilityViolation[] | All violations found |
| passes | number | Count of rules that passed |
| incomplete | number | Count of rules that could not be evaluated |
| inapplicable | number | Count of rules not applicable to the content |

## Relationships

- An AuditResult contains zero or more AccessibilityViolations.
- Each AccessibilityViolation contains one or more ViolationNodes.
- A test run produces one AuditResult for the main content container, plus optionally one for each visible modal.

## State Transitions

N/A — audit results are immutable snapshots produced at test time.
