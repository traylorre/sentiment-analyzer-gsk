"""Mock SendGrid adapter for email verification in tests.

Captures sent emails for test assertions without hitting SendGrid API.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CapturedEmail:
    """Represents a captured email for test verification."""

    to_email: str
    from_email: str
    subject: str
    html_content: str
    plain_content: str | None
    sent_at: datetime
    message_id: str


@dataclass
class MockSendGrid:
    """Mock SendGrid service that captures emails for testing.

    Instead of sending real emails, captures them for test assertions.
    Can simulate various failure modes.
    """

    # Configuration
    fail_mode: bool = False
    rate_limit_mode: bool = False
    auth_fail_mode: bool = False

    # Captured state
    sent_emails: list[CapturedEmail] = field(default_factory=list)
    _message_counter: int = field(default=0)

    def reset(self) -> None:
        """Reset all captured state."""
        self.sent_emails.clear()
        self._message_counter = 0
        self.fail_mode = False
        self.rate_limit_mode = False
        self.auth_fail_mode = False

    def send_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        html_content: str,
        plain_content: str | None = None,
    ) -> dict:
        """Simulate sending an email.

        Args:
            to_email: Recipient email
            from_email: Sender email
            subject: Email subject
            html_content: HTML body
            plain_content: Plain text body

        Returns:
            Response dict with status and message_id

        Raises:
            RuntimeError: In fail_mode
            PermissionError: In auth_fail_mode
        """
        if self.auth_fail_mode:
            raise PermissionError("Mock authentication failure (401)")

        if self.rate_limit_mode:
            return {
                "status_code": 429,
                "error": "Rate limit exceeded",
                "retry_after": 60,
            }

        if self.fail_mode:
            raise RuntimeError("Mock SendGrid failure")

        # Generate message ID
        self._message_counter += 1
        message_id = f"mock-msg-{self._message_counter:06d}"

        # Capture email
        captured = CapturedEmail(
            to_email=to_email,
            from_email=from_email,
            subject=subject,
            html_content=html_content,
            plain_content=plain_content,
            sent_at=datetime.now(UTC),
            message_id=message_id,
        )
        self.sent_emails.append(captured)

        return {
            "status_code": 202,
            "message_id": message_id,
        }

    # Assertion helpers

    def assert_email_sent(
        self, to_email: str | None = None, subject_contains: str | None = None
    ) -> CapturedEmail:
        """Assert an email was sent matching criteria.

        Args:
            to_email: Expected recipient (any if None)
            subject_contains: Expected subject substring (any if None)

        Returns:
            The matching CapturedEmail

        Raises:
            AssertionError: If no matching email found
        """
        for email in self.sent_emails:
            if to_email and email.to_email != to_email:
                continue
            if subject_contains and subject_contains not in email.subject:
                continue
            return email

        criteria = []
        if to_email:
            criteria.append(f"to={to_email}")
        if subject_contains:
            criteria.append(f"subject contains '{subject_contains}'")

        raise AssertionError(
            f"No email found matching: {', '.join(criteria) or 'any'}. "
            f"Sent emails: {[e.to_email for e in self.sent_emails]}"
        )

    def assert_no_emails_sent(self) -> None:
        """Assert no emails were sent.

        Raises:
            AssertionError: If any emails were sent
        """
        if self.sent_emails:
            raise AssertionError(
                f"Expected no emails sent, but {len(self.sent_emails)} were sent: "
                f"{[e.subject for e in self.sent_emails]}"
            )

    def assert_email_count(self, expected: int) -> None:
        """Assert exact number of emails sent.

        Args:
            expected: Expected email count

        Raises:
            AssertionError: If count doesn't match
        """
        actual = len(self.sent_emails)
        if actual != expected:
            raise AssertionError(f"Expected {expected} emails sent, but got {actual}")

    def get_emails_to(self, to_email: str) -> list[CapturedEmail]:
        """Get all emails sent to a specific address.

        Args:
            to_email: Recipient email address

        Returns:
            List of emails to that address
        """
        return [e for e in self.sent_emails if e.to_email == to_email]

    def get_magic_link_emails(self) -> list[CapturedEmail]:
        """Get all magic link authentication emails.

        Returns:
            List of magic link emails
        """
        return [
            e
            for e in self.sent_emails
            if "sign-in" in e.subject.lower() or "magic" in e.subject.lower()
        ]

    def get_alert_emails(self) -> list[CapturedEmail]:
        """Get all alert notification emails.

        Returns:
            List of alert emails
        """
        return [e for e in self.sent_emails if "alert" in e.subject.lower()]

    def extract_magic_link_token(self, email: CapturedEmail) -> str | None:
        """Extract magic link token from email content.

        Args:
            email: Captured email

        Returns:
            Token string or None if not found
        """
        # Look for token= in the URL
        import re

        match = re.search(r"token=([a-zA-Z0-9_-]+)", email.html_content)
        if match:
            return match.group(1)
        return None


def create_mock_sendgrid() -> MockSendGrid:
    """Factory function to create a mock SendGrid.

    Returns:
        Fresh MockSendGrid instance
    """
    return MockSendGrid()
