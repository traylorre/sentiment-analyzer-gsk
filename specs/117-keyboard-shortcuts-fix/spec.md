# Feature 117: Fix Keyboard Shortcuts Order

## Problem Statement

The Interview Dashboard's keyboard shortcuts (CTRL+7, CTRL+8, CTRL+9) navigate to different sections than expected based on the hamburger menu ordering.

**Current keyboard shortcuts array (line 2179):**
```javascript
['welcome', 'architecture', 'auth', 'config', 'sentiment', 'external', 'circuit', 'chaos', 'caching']
```

**Hamburger menu order (lines 742-807):**
1. welcome
2. architecture
3. auth
4. config
5. sentiment
6. external
7. chaos (keyboard goes to circuit)
8. caching (keyboard goes to chaos)
9. circuit (keyboard goes to caching)
10. traffic
11. observability
12. testing
13. infra

## Expected Behavior

CTRL+N should navigate to the Nth item in the hamburger menu sidebar.

## Solution

Update the keyboard shortcuts array to match hamburger menu order:

```javascript
['welcome', 'architecture', 'auth', 'config', 'sentiment', 'external', 'chaos', 'caching', 'circuit', 'traffic', 'observability', 'testing', 'infra']
```

Note: This extends to all 13 sections, but only 1-9 will be usable via keyboard (CTRL+0 might go to 10th item or be ignored).

## Changes

### interview/index.html

Line 2179: Update sections array to match hamburger menu order.

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | CTRL+7 navigates to Chaos Engineering | Manual test |
| SC-002 | CTRL+8 navigates to Caching Strategy | Manual test |
| SC-003 | CTRL+9 navigates to Circuit Breaker | Manual test |
