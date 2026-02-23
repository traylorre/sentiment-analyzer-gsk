# Data Model: Mid-Session Tier Upgrade

## Entities

### User (extends existing)

Existing fields used:
- `user_id: str` - Primary key
- `role: RoleType` - anonymous | free | paid | operator
- `subscription_active: bool` - Payment status
- `subscription_expires_at: datetime | None` - Expiry timestamp
- `role_assigned_at: datetime | None` - When role was set
- `role_assigned_by: str | None` - "stripe_webhook" or "admin:{user_id}"
- `revocation_id: int` - Token invalidation counter

### WebhookEvent (new)

Tracks processed Stripe events for idempotency.

| Field | Type | Description |
|-------|------|-------------|
| event_id | str (PK) | Stripe event.id |
| event_type | str | e.g., customer.subscription.created |
| user_id | str | Associated user |
| processed_at | datetime | When processed |
| subscription_id | str | Stripe subscription ID |

### BroadcastMessage (frontend only)

Cross-tab communication payload.

| Field | Type | Description |
|-------|------|-------------|
| type | 'AUTH' | Message category |
| version | 1 | Schema version |
| timestamp | number | Unix ms |
| sourceTabId | string | Sender tab ID |
| data.action | string | ROLE_UPGRADED, SIGN_OUT, REFRESH |
| data.userId | string? | Affected user |
| data.newRole | UserRole? | New role value |

## State Transitions

```
User Role State Machine:

  anonymous ──(email verify)──► free ──(payment)──► paid
                                  │                   │
                                  │                   │
                                  ▼                   ▼
                           (subscription cancel) ◄────┘
                                  │
                                  ▼
                                free
```

## Validation Rules

1. **Role upgrade**: Only free → paid via webhook (no downgrade via webhook)
2. **Idempotency**: Same event.id = no-op (return success)
3. **Atomic**: role + revocation_id must update together
4. **Expiry**: subscription_expires_at must be future when subscription_active=true
