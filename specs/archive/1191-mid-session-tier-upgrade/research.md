# Research: Mid-Session Tier Upgrade

## 1. Stripe Webhook Handling

### Decision: Use stripe-python library with signature verification

**Rationale**:
- `stripe.Webhook.construct_event()` handles HMAC-SHA256 signature verification
- Prevents spoofed webhook events
- Library handles cryptographic details correctly

**Alternatives Considered**:
- Manual signature verification (error-prone, not recommended)
- Polling Stripe API (higher latency, rate-limited, inefficient)

### Idempotency Pattern

**Decision**: Store `event.id` and check before processing

```python
# Check if already processed
if db.query(WebhookEvent).filter(stripe_event_id=event['id']).exists():
    return 200  # Silently succeed (idempotent)
```

**Rationale**:
- Stripe retries webhook delivery on failures
- Same event.id = same subscription change
- Prevents duplicate role upgrades

### Events to Handle

| Event | Action |
|-------|--------|
| `customer.subscription.created` | Activate paid role |
| `customer.subscription.updated` | Sync plan changes |
| `customer.subscription.deleted` | Revoke to free role |

---

## 2. Cross-Tab Synchronization

### Decision: BroadcastChannel API with localStorage fallback

**Rationale**:
- Native browser API, fast (~1ms latency)
- Memory-only Zustand stores (no persistence) work well with BroadcastChannel
- Safari 15.1+ support (fallback covers 15-20% market share)

**Alternatives Considered**:
- localStorage events only (deprecated, ~100ms latency, noisy)
- SharedWorker (complex API, limited debugging)
- Service Worker (adds complexity, harder to debug)
- Server-Sent Events (network latency, requires backend changes)

### Message Format

```typescript
interface BroadcastMessage {
  type: 'AUTH';
  version: 1;
  timestamp: number;
  sourceTabId: string;  // Prevent echo
  data: {
    action: 'ROLE_UPGRADED' | 'SIGN_OUT' | 'REFRESH';
    userId?: string;
    newRole?: UserRole;
  };
}
```

### Performance Constraints

- Message size: <100KB (practical limit)
- Frequency: Max 100 messages/sec per channel
- Keep callbacks <1ms to avoid blocking

---

## 3. Exponential Backoff Pattern

### Decision: 1s, 2s, 4s, 8s, 16s, 29s (6 attempts, 60s total)

**Rationale**:
- Covers Stripe webhook delays under load (30+ seconds)
- Reduces server load vs fixed-interval polling
- 60s timeout handles 99.9% of cases per Stripe SLA

**Alternatives Considered**:
- Fixed interval (10 × 1s = 10s) - insufficient under load
- Linear backoff (1s, 2s, 3s...) - too slow to detect quick upgrades

### Implementation

```typescript
const BACKOFF_INTERVALS = [1000, 2000, 4000, 8000, 16000, 29000];

async function pollForUpgrade(): Promise<boolean> {
  for (const delay of BACKOFF_INTERVALS) {
    await sleep(delay);
    const user = await authApi.refresh();
    if (user.role === 'paid') return true;
  }
  return false; // Timeout - show manual refresh message
}
```

---

## 4. Atomic Transaction Pattern

### Decision: Use existing TransactWriteItems pattern from auth.py

**Rationale**:
- Pattern already exists and is battle-tested
- All-or-nothing: role + revocation_id update atomically
- Proper error handling for transaction cancellation

**Reference**: `src/lambdas/dashboard/auth.py` (session eviction implementation)

```python
dynamodb.transact_write_items(TransactItems=[
    {'Update': {'TableName': 'Users', 'Key': user_key, 'UpdateExpression': 'SET role = :role'}},
    {'Update': {'TableName': 'Auth', 'Key': auth_key, 'UpdateExpression': 'SET revocation_id = revocation_id + :inc'}}
])
```

---

## 5. Existing Infrastructure Findings

### Backend (EXISTS - extend)
- `src/lambdas/dashboard/auth.py` - TransactWriteItems pattern
- `src/lambdas/shared/models/user.py` - subscription_active, role fields
- `src/lambdas/shared/auth/roles.py` - role resolution logic

### Frontend (EXISTS - extend)
- `frontend/src/stores/auth-store.ts` - Memory-only Zustand, has `refreshUserProfile()`
- `frontend/src/types/auth.ts` - UserRole type already defined
- `frontend/src/hooks/use-auth.ts` - Session management hooks

### Frontend (NEW - create)
- `frontend/src/lib/sync/broadcast-channel.ts` - Cross-tab sync
- `frontend/src/hooks/use-tier-upgrade.ts` - Polling with backoff

---

## 6. Security Considerations

| Concern | Mitigation |
|---------|------------|
| Webhook spoofing | Signature verification (HMAC-SHA256) |
| Replay attacks | Store event.id, check before processing |
| Stale tokens | Increment revocation_id atomically with role |
| Cross-tab state leak | BroadcastChannel scoped to same-origin only |

### Configuration (Amendment 1.15 compliant)

```python
# REQUIRED - fails if missing
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]

# PROHIBITED - masks misconfiguration
# STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "fallback")
```
