# Feature Backlog

## Queued Features

### 117 - Fix Keyboard Shortcuts Order
**Priority**: Low
**Spec**: specs/117-keyboard-shortcuts-fix/spec.md

CTRL+7,8,9 keyboard shortcuts navigate to wrong sections compared to hamburger menu order.
- Current: circuit, chaos, caching
- Expected: chaos, caching, circuit

### 118 - Fix Dashboard Connection Status
**Priority**: Medium
**Spec**: specs/118-dashboard-connection-status/spec.md

ONE URL dashboard shows "Disconnected" because SSE stream endpoint routes to wrong Lambda.
- Dashboard Lambda has BUFFERED mode
- SSE requires RESPONSE_STREAM mode
- ~~Need CloudFront routing fix or graceful fallback~~ *(Superseded: CloudFront removed in Feature 1203)*

---

## Completed Features

(Features moved here after completion)
