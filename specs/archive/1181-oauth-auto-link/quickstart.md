# Quickstart: OAuth Auto-Link Testing

## Test Scenarios

### Scenario 1: Gmail User Auto-Links with Google OAuth

**Preconditions**:
- User exists: email="test@gmail.com", role="free", verification="verified", auth_type="email"
- User has no OAuth linked providers

**Steps**:
1. User clicks "Sign in with Google"
2. Google OAuth returns: sub="12345", email="test@gmail.com", email_verified=true
3. System detects: existing user + @gmail.com + Google = AUTO-LINK

**Expected**:
- No prompt displayed
- User.linked_providers = ["email", "google"]
- User.provider_sub = "google:12345"
- Audit log: AUTH_METHOD_LINKED, link_type="auto"

---

### Scenario 2: Cross-Domain Manual Linking

**Preconditions**:
- User exists: email="ceo@hotmail.com", role="free", verification="verified", auth_type="email"

**Steps**:
1. User clicks "Sign in with Google"
2. Google OAuth returns: sub="67890", email="ceo@gmail.com", email_verified=true
3. System detects: different domain = PROMPT

**Expected**:
- Prompt displays: "Link accounts?" with masked emails
- User chooses "Link Accounts"
- User.linked_providers = ["email", "google"]
- Audit log: AUTH_METHOD_LINKED, link_type="manual"

---

### Scenario 3: GitHub Always Prompts

**Preconditions**:
- User exists: email="dev@github.io", role="free", verification="verified", auth_type="email"

**Steps**:
1. User clicks "Sign in with GitHub"
2. GitHub OAuth returns: sub="gh-user-id", email="dev@github.io", email_verified=true
3. System detects: GitHub = ALWAYS PROMPT (opaque provider)

**Expected**:
- Prompt displays regardless of email match
- User chooses action

---

### Scenario 4: Reject Unverified OAuth Email

**Preconditions**:
- User exists with verified email

**Steps**:
1. User attempts OAuth
2. OAuth returns: email_verified=false

**Expected**:
- Linking rejected with AUTH_022
- No changes to user account

---

### Scenario 5: Reject Duplicate Provider Sub

**Preconditions**:
- User A: linked google:12345
- User B: attempts Google OAuth with sub="12345"

**Steps**:
1. User B clicks "Sign in with Google"
2. System queries get_user_by_provider_sub("google", "12345")
3. Finds User A already linked

**Expected**:
- Linking rejected with AUTH_023
- "This OAuth account is already linked to another user"

---

## Unit Test Commands

```bash
# Run unit tests for auto-link logic
pytest tests/unit/dashboard/test_oauth_auto_link.py -v

# Run with coverage
pytest tests/unit/dashboard/test_oauth_auto_link.py --cov=src/lambdas/dashboard/auth -v
```

## Integration Test Commands

```bash
# Run integration tests (requires LocalStack)
MAGIC_LINK_SECRET="test-secret-key-at-least-32-characters-long" \
  pytest tests/integration/test_flow3_oauth_link.py -v
```
