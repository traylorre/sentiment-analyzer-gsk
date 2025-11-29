# Synthetic SendGrid API Contract

**Feature**: 008-e2e-validation-suite
**Date**: 2025-11-28

## Overview

This contract defines the synthetic response format for mocking SendGrid email API in E2E tests. Uses SendGrid's sandbox mode behavior.

---

## Send Email Endpoint

### POST /v3/mail/send

Sends email via SendGrid (sandbox mode returns success without delivery).

**Request**:
```json
{
  "personalizations": [
    {
      "to": [{"email": "user@test.sentiment-analyzer.local"}],
      "subject": "Your sign-in link for Sentiment Dashboard"
    }
  ],
  "from": {"email": "noreply@sentiment-analyzer.com"},
  "content": [
    {
      "type": "text/html",
      "value": "<p>Click here to sign in...</p>"
    }
  ],
  "mail_settings": {
    "sandbox_mode": {"enable": true}
  }
}
```

**Synthetic Response** (202 Accepted):
```json
{
  "x-message-id": "test-msg-12345-abcdef"
}
```

**Headers**:
```
X-Message-Id: test-msg-12345-abcdef
```

---

## Email Activity Endpoint

### GET /v3/messages

Returns email activity for verification.

**Synthetic Response** (200 OK):
```json
{
  "messages": [
    {
      "msg_id": "test-msg-12345-abcdef",
      "from_email": "noreply@sentiment-analyzer.com",
      "to_email": "user@test.sentiment-analyzer.local",
      "subject": "Your sign-in link for Sentiment Dashboard",
      "status": "delivered",
      "opens_count": 0,
      "clicks_count": 0,
      "last_event_time": "2025-11-28T10:00:00Z"
    }
  ]
}
```

---

## Event Webhook Payload

Simulates SendGrid Event Webhook for email tracking.

**Delivered Event**:
```json
[
  {
    "email": "user@test.sentiment-analyzer.local",
    "event": "delivered",
    "sg_message_id": "test-msg-12345-abcdef",
    "timestamp": 1732789200,
    "smtp-id": "<test@mail.sentiment-analyzer.com>",
    "category": ["magic-link"]
  }
]
```

**Opened Event**:
```json
[
  {
    "email": "user@test.sentiment-analyzer.local",
    "event": "open",
    "sg_message_id": "test-msg-12345-abcdef",
    "timestamp": 1732789260,
    "useragent": "Mozilla/5.0 (Test Browser)",
    "ip": "192.168.1.1"
  }
]
```

**Clicked Event**:
```json
[
  {
    "email": "user@test.sentiment-analyzer.local",
    "event": "click",
    "sg_message_id": "test-msg-12345-abcdef",
    "timestamp": 1732789320,
    "url": "https://app.sentiment-analyzer.com/auth/verify?token=abc123",
    "useragent": "Mozilla/5.0 (Test Browser)",
    "ip": "192.168.1.1"
  }
]
```

---

## Error Responses

**Rate Limited** (429):
```json
{
  "errors": [
    {
      "message": "Too many requests",
      "field": null,
      "help": "Rate limit exceeded. Retry after 60 seconds."
    }
  ]
}
```

**Invalid Request** (400):
```json
{
  "errors": [
    {
      "message": "Invalid email address",
      "field": "personalizations.0.to.0.email",
      "help": null
    }
  ]
}
```

---

## Handler Configuration

```python
# tests/e2e/fixtures/sendgrid.py

class SyntheticSendGridHandler:
    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.sent_emails: list[dict] = []
        self.events: list[dict] = []

    def handle_send(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        msg_id = f"test-msg-{self.seed}-{len(self.sent_emails):06x}"

        self.sent_emails.append({
            "msg_id": msg_id,
            "to": body["personalizations"][0]["to"][0]["email"],
            "subject": body["personalizations"][0]["subject"],
            "sent_at": datetime.utcnow().isoformat()
        })

        # Simulate delivery event
        self.events.append({
            "email": body["personalizations"][0]["to"][0]["email"],
            "event": "delivered",
            "sg_message_id": msg_id,
            "timestamp": int(time.time())
        })

        return httpx.Response(
            202,
            headers={"X-Message-Id": msg_id}
        )

    def get_magic_link_token(self, email: str) -> str | None:
        """Extract magic link token from sent email (for test verification)."""
        for sent in self.sent_emails:
            if sent["to"] == email and "sign-in link" in sent["subject"]:
                # In real impl, parse token from email body
                return f"test-token-{self.seed}"
        return None

    def simulate_open(self, msg_id: str):
        """Simulate email open event."""
        self.events.append({
            "event": "open",
            "sg_message_id": msg_id,
            "timestamp": int(time.time())
        })

    def simulate_click(self, msg_id: str, url: str):
        """Simulate link click event."""
        self.events.append({
            "event": "click",
            "sg_message_id": msg_id,
            "url": url,
            "timestamp": int(time.time())
        })
```

---

## Integration with Test Context

```python
# tests/e2e/conftest.py

@pytest.fixture
def sendgrid_handler(test_run_id: str) -> SyntheticSendGridHandler:
    """Provide SendGrid handler for email testing."""
    seed = int(test_run_id.split("-")[1], 16)
    return SyntheticSendGridHandler(seed=seed)

@pytest.fixture
def magic_link_verifier(sendgrid_handler: SyntheticSendGridHandler):
    """Helper to extract magic link tokens for verification."""
    def verify(email: str) -> str:
        token = sendgrid_handler.get_magic_link_token(email)
        assert token is not None, f"No magic link sent to {email}"
        return token
    return verify
```
