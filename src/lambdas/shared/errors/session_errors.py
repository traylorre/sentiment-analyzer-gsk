"""Session-related error types for Feature 014.

These exceptions provide structured error handling for authentication,
session management, and account operations with race condition protection.
"""

from datetime import datetime


class SessionError(Exception):
    """Base class for session-related errors."""

    pass


class SessionRevokedException(SessionError):
    """Session has been revoked server-side.

    Raised when a user attempts to use a session that has been
    invalidated via admin action or andon cord trigger.
    """

    def __init__(
        self,
        reason: str | None = None,
        revoked_at: datetime | None = None,
    ):
        self.reason = reason
        self.revoked_at = revoked_at
        message = f"Session revoked: {reason or 'No reason provided'}"
        if revoked_at:
            message += f" (at {revoked_at.isoformat()})"
        super().__init__(message)


class SessionExpiredError(SessionError):
    """Session has expired and requires re-authentication.

    Raised when a session's expiry time has passed and the user
    must create a new session.
    """

    def __init__(self, user_id: str, expired_at: datetime | None = None):
        self.user_id = user_id
        self.expired_at = expired_at
        message = f"Session expired for user {user_id}"
        if expired_at:
            message += f" (expired at {expired_at.isoformat()})"
        super().__init__(message)


class TokenAlreadyUsedError(SessionError):
    """Magic link token has already been used.

    Raised during atomic token verification when a concurrent request
    has already consumed the token. This is the expected race condition
    protection behavior.
    """

    def __init__(self, token_id: str, used_at: datetime | None = None):
        self.token_id = token_id
        self.used_at = used_at
        message = f"Magic link token already used: {token_id}"
        if used_at:
            message += f" (used at {used_at.isoformat()})"
        super().__init__(message)


class TokenExpiredError(SessionError):
    """Magic link token has expired.

    Raised when a magic link verification is attempted after the
    token's expiry time (default: 1 hour after creation).
    """

    def __init__(self, token_id: str, expired_at: datetime | None = None):
        self.token_id = token_id
        self.expired_at = expired_at
        message = f"Magic link token expired: {token_id}"
        if expired_at:
            message += f" (expired at {expired_at.isoformat()})"
        super().__init__(message)


class EmailAlreadyExistsError(SessionError):
    """Email address is already registered to another account.

    Raised when attempting to create a user with an email that
    already exists. The database constraint (GSI + conditional write)
    ensures this is detected atomically.
    """

    def __init__(self, email: str, existing_user_id: str | None = None):
        self.email = email
        self.existing_user_id = existing_user_id
        message = f"Email already registered: {email}"
        super().__init__(message)


class MergeConflictError(SessionError):
    """Account merge conflict detected.

    Raised when attempting to merge an account that has already
    been merged to another target, or when concurrent merge
    operations create a conflict.
    """

    def __init__(
        self,
        source_id: str,
        target_id: str,
        reason: str,
        existing_merge_target: str | None = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.reason = reason
        self.existing_merge_target = existing_merge_target
        message = f"Merge conflict ({source_id} -> {target_id}): {reason}"
        if existing_merge_target:
            message += f" (already merged to {existing_merge_target})"
        super().__init__(message)


class InvalidMergeTargetError(SessionError):
    """Merge target user does not exist or is invalid.

    Raised when the target user for an account merge operation
    cannot be found or is not in a valid state for merging.
    """

    def __init__(self, target_id: str, reason: str | None = None):
        self.target_id = target_id
        self.reason = reason
        message = f"Invalid merge target: {target_id}"
        if reason:
            message += f" ({reason})"
        super().__init__(message)
