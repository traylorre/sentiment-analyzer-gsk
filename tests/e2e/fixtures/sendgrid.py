# Synthetic SendGrid API Handlers
#
# Generates deterministic test data for SendGrid email API.
# See contracts/synthetic-sendgrid.md for response format specification.

import time
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class SentEmail:
    """Represents a sent email record."""

    msg_id: str
    to_email: str
    from_email: str
    subject: str
    content: str
    sent_at: datetime
    status: str = "delivered"


@dataclass
class EmailEvent:
    """Represents an email tracking event."""

    event: str  # "delivered", "open", "click", "bounce"
    email: str
    sg_message_id: str
    timestamp: int
    url: str | None = None
    useragent: str | None = None
    ip: str | None = None


class SyntheticSendGridHandler:
    """Handler for synthetic SendGrid API responses.

    Tracks sent emails and simulates delivery events for testing
    the notification pipeline and magic link flows.
    """

    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.sent_emails: list[SentEmail] = []
        self.events: list[EmailEvent] = []
        self.rate_limit_mode = False
        self._request_count = 0

    def set_rate_limit_mode(self, enabled: bool) -> None:
        """Configure handler to return 429 rate limits."""
        self.rate_limit_mode = enabled

    def reset(self) -> None:
        """Reset handler state."""
        self.sent_emails = []
        self.events = []
        self.rate_limit_mode = False
        self._request_count = 0

    def send_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        content: str,
    ) -> tuple[int, dict, dict]:
        """Handle email send request.

        Args:
            to_email: Recipient email
            from_email: Sender email
            subject: Email subject
            content: Email HTML content

        Returns:
            Tuple of (status_code, response_body, headers)
        """
        self._request_count += 1

        if self.rate_limit_mode:
            return (
                429,
                {
                    "errors": [
                        {
                            "message": "Too many requests",
                            "field": None,
                            "help": "Rate limit exceeded. Retry after 60 seconds.",
                        }
                    ]
                },
                {},
            )

        # Validate email format
        if "@" not in to_email:
            return (
                400,
                {
                    "errors": [
                        {
                            "message": "Invalid email address",
                            "field": "personalizations.0.to.0.email",
                            "help": None,
                        }
                    ]
                },
                {},
            )

        # Generate message ID
        msg_id = f"test-msg-{self.seed}-{len(self.sent_emails):06x}"

        # Record sent email
        email = SentEmail(
            msg_id=msg_id,
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            content=content,
            sent_at=datetime.now(UTC),
        )
        self.sent_emails.append(email)

        # Simulate delivery event
        self.events.append(
            EmailEvent(
                event="delivered",
                email=to_email,
                sg_message_id=msg_id,
                timestamp=int(time.time()),
            )
        )

        return (202, {}, {"X-Message-Id": msg_id})

    def get_messages_response(self, query_email: str | None = None) -> tuple[int, dict]:
        """Get email activity.

        Args:
            query_email: Optional filter by recipient email

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        messages = []
        for email in self.sent_emails:
            if query_email and email.to_email != query_email:
                continue

            # Count opens and clicks for this message
            opens = sum(
                1
                for e in self.events
                if e.sg_message_id == email.msg_id and e.event == "open"
            )
            clicks = sum(
                1
                for e in self.events
                if e.sg_message_id == email.msg_id and e.event == "click"
            )

            messages.append(
                {
                    "msg_id": email.msg_id,
                    "from_email": email.from_email,
                    "to_email": email.to_email,
                    "subject": email.subject,
                    "status": email.status,
                    "opens_count": opens,
                    "clicks_count": clicks,
                    "last_event_time": email.sent_at.isoformat().replace("+00:00", "Z"),
                }
            )

        return (200, {"messages": messages})

    def get_magic_link_token(self, email: str) -> str | None:
        """Extract magic link token from sent email (for test verification).

        Args:
            email: Recipient email address

        Returns:
            Token string if found, None otherwise
        """
        for sent in self.sent_emails:
            if sent.to_email == email and "sign-in" in sent.subject.lower():
                # In E2E tests, return a test token
                # The actual token would be parsed from sent.content in real impl
                return f"test-token-{self.seed}"
        return None

    def simulate_open(self, msg_id: str, useragent: str | None = None) -> None:
        """Simulate email open event.

        Args:
            msg_id: Message ID to simulate open for
            useragent: Optional user agent string
        """
        email = next((e for e in self.sent_emails if e.msg_id == msg_id), None)
        if email:
            self.events.append(
                EmailEvent(
                    event="open",
                    email=email.to_email,
                    sg_message_id=msg_id,
                    timestamp=int(time.time()),
                    useragent=useragent or "Mozilla/5.0 (Test Browser)",
                    ip="192.168.1.1",
                )
            )

    def simulate_click(self, msg_id: str, url: str) -> None:
        """Simulate link click event.

        Args:
            msg_id: Message ID to simulate click for
            url: URL that was clicked
        """
        email = next((e for e in self.sent_emails if e.msg_id == msg_id), None)
        if email:
            self.events.append(
                EmailEvent(
                    event="click",
                    email=email.to_email,
                    sg_message_id=msg_id,
                    timestamp=int(time.time()),
                    url=url,
                    useragent="Mozilla/5.0 (Test Browser)",
                    ip="192.168.1.1",
                )
            )

    def simulate_bounce(self, msg_id: str) -> None:
        """Simulate email bounce event.

        Args:
            msg_id: Message ID that bounced
        """
        email = next((e for e in self.sent_emails if e.msg_id == msg_id), None)
        if email:
            email.status = "bounced"
            self.events.append(
                EmailEvent(
                    event="bounce",
                    email=email.to_email,
                    sg_message_id=msg_id,
                    timestamp=int(time.time()),
                )
            )

    def get_webhook_payload(self, event_type: str | None = None) -> list[dict]:
        """Get events in SendGrid webhook payload format.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of events in webhook format
        """
        payload = []
        for event in self.events:
            if event_type and event.event != event_type:
                continue

            event_data: dict = {
                "email": event.email,
                "event": event.event,
                "sg_message_id": event.sg_message_id,
                "timestamp": event.timestamp,
            }

            if event.url:
                event_data["url"] = event.url
            if event.useragent:
                event_data["useragent"] = event.useragent
            if event.ip:
                event_data["ip"] = event.ip

            payload.append(event_data)

        return payload

    @property
    def request_count(self) -> int:
        """Number of requests handled."""
        return self._request_count
