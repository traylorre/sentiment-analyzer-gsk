"""Connection pool management for SSE streaming Lambda.

Provides thread-safe connection tracking with configurable limits.
Per FR-008: Maximum 100 concurrent connections per Lambda instance.
"""

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.lambdas.shared.logging_utils import sanitize_for_log

logger = logging.getLogger(__name__)


@dataclass
class SSEConnection:
    """Represents an active SSE streaming connection.

    Attributes:
        connection_id: Unique identifier for this connection (UUID v4)
        user_id: User ID from X-User-ID header (None for global streams)
        config_id: Configuration ID for filtered streams (None for global)
        ticker_filters: List of tickers to filter events for
        last_event_id: Last event ID sent to this connection
        connected_at: Connection establishment timestamp (UTC)
    """

    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str | None = None
    config_id: str | None = None
    ticker_filters: list[str] = field(default_factory=list)
    last_event_id: str | None = None
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def matches_ticker(self, ticker: str) -> bool:
        """Check if this connection should receive events for a ticker.

        Args:
            ticker: The ticker symbol to check

        Returns:
            True if no filters (global) or ticker is in filters (case-insensitive)
        """
        if not self.ticker_filters:
            return True
        ticker_upper = ticker.upper()
        return any(t.upper() == ticker_upper for t in self.ticker_filters)


class ConnectionManager:
    """Thread-safe connection pool manager.

    Manages active SSE connections with:
    - Configurable maximum connection limit (default: 100)
    - Thread-safe acquire/release operations
    - Connection tracking by ID
    - Startup time tracking for uptime calculation

    Per research.md decision #4: In-memory connection tracking with thread-safe counter.
    """

    def __init__(self, max_connections: int | None = None):
        """Initialize connection manager.

        Args:
            max_connections: Maximum concurrent connections.
                            Defaults to SSE_MAX_CONNECTIONS env var or 100.
        """
        self._connections: dict[str, SSEConnection] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Get max connections from env var or use default
        if max_connections is None:
            max_connections = int(os.environ.get("SSE_MAX_CONNECTIONS", "100"))
        self._max_connections = max_connections

    @property
    def max_connections(self) -> int:
        """Get maximum allowed connections."""
        return self._max_connections

    @property
    def count(self) -> int:
        """Get current connection count (thread-safe)."""
        with self._lock:
            return len(self._connections)

    @property
    def available(self) -> int:
        """Get number of available connection slots."""
        return max(0, self._max_connections - self.count)

    @property
    def uptime_seconds(self) -> int:
        """Get Lambda uptime in seconds since manager creation."""
        return int(time.time() - self._start_time)

    def acquire(
        self,
        user_id: str | None = None,
        config_id: str | None = None,
        ticker_filters: list[str] | None = None,
    ) -> SSEConnection | None:
        """Acquire a connection slot.

        Args:
            user_id: Optional user ID for authenticated streams
            config_id: Optional configuration ID for filtered streams
            ticker_filters: Optional list of tickers to filter events

        Returns:
            SSEConnection if slot available, None if limit reached
        """
        with self._lock:
            if len(self._connections) >= self._max_connections:
                logger.warning(
                    "Connection limit reached",
                    extra={
                        "current": len(self._connections),
                        "max": self._max_connections,
                    },
                )
                return None

            connection = SSEConnection(
                user_id=user_id,
                config_id=config_id,
                ticker_filters=ticker_filters or [],
            )
            self._connections[connection.connection_id] = connection

            logger.info(
                "Connection acquired",
                extra={
                    "connection_id": connection.connection_id,
                    "user_id": sanitize_for_log(user_id) if user_id else None,
                    "config_id": sanitize_for_log(config_id) if config_id else None,
                    "current_count": len(self._connections),
                },
            )

            return connection

    def release(self, connection_id: str) -> bool:
        """Release a connection slot.

        Args:
            connection_id: ID of the connection to release

        Returns:
            True if connection was found and released, False otherwise
        """
        with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]
                logger.info(
                    "Connection released",
                    extra={
                        "connection_id": connection_id,
                        "current_count": len(self._connections),
                    },
                )
                return True

            logger.warning(
                "Connection not found for release",
                extra={"connection_id": connection_id},
            )
            return False

    def get(self, connection_id: str) -> SSEConnection | None:
        """Get a connection by ID.

        Args:
            connection_id: ID of the connection to retrieve

        Returns:
            SSEConnection if found, None otherwise
        """
        with self._lock:
            return self._connections.get(connection_id)

    def update_last_event_id(self, connection_id: str, event_id: str) -> bool:
        """Update the last event ID for a connection.

        Args:
            connection_id: ID of the connection to update
            event_id: The new last event ID

        Returns:
            True if connection was found and updated, False otherwise
        """
        with self._lock:
            if connection_id in self._connections:
                self._connections[connection_id].last_event_id = event_id
                return True
            return False

    def get_status(self) -> dict:
        """Get connection pool status.

        Returns:
            Dict with connections, max_connections, available, uptime_seconds
        """
        return {
            "connections": self.count,
            "max_connections": self._max_connections,
            "available": self.available,
            "uptime_seconds": self.uptime_seconds,
        }


# Global connection manager instance
connection_manager = ConnectionManager()
