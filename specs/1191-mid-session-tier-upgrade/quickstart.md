# Quickstart: Mid-Session Tier Upgrade

## Prerequisites

- Python 3.13+
- Node.js 18+
- AWS credentials configured
- Stripe test account

## Environment Variables

```bash
# Backend
export STRIPE_WEBHOOK_SECRET="whsec_..."  # From Stripe Dashboard > Webhooks
export STRIPE_API_KEY="sk_test_..."       # Stripe secret key

# Frontend (optional - for local testing)
export NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_..."
```

## Local Development

### 1. Start Backend

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
pip install -r requirements.txt
make dev-server
```

### 2. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Stripe CLI for Local Webhooks

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/webhooks/stripe

# Note the webhook signing secret (whsec_...) and export it
```

## Testing

### Unit Tests

```bash
# Backend
MAGIC_LINK_SECRET="test-secret-key-at-least-32-characters-long-for-testing" \
python -m pytest tests/unit/dashboard/test_stripe_webhook.py -v

# Frontend
cd frontend && npm run test -- --grep "tier-upgrade"
```

### Integration Test

```bash
# Trigger test webhook
stripe trigger customer.subscription.created

# Or via API
stripe webhooks trigger customer.subscription.created --data '{"metadata":{"user_id":"test_user"}}'
```

## Verification Checklist

1. [ ] Webhook receives events (check logs)
2. [ ] User role updates to 'paid' in DynamoDB
3. [ ] revocation_id increments atomically
4. [ ] Frontend polling detects upgrade
5. [ ] Success toast appears
6. [ ] Other tabs refresh role via BroadcastChannel
