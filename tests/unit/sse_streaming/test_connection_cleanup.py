"""Unit tests for SSE connection cleanup (Feature 1235).

Tests stale connection sweeping to prevent connection leaks when Lambda
is force-killed (SIGKILL) and finally blocks don't execute.
"""

import time

from src.lambdas.sse_streaming.connection import ConnectionManager


def _make_stale(manager: ConnectionManager, connection_id: str, age_seconds: float):
    """Set a connection's last_activity to simulate staleness."""
    conn = manager.get(connection_id)
    if conn is not None:
        conn.last_activity = time.time() - age_seconds


class TestSweepRemovesStaleConnections:
    """Test that sweep_stale removes connections past their TTL."""

    def test_sweep_removes_stale_connections(self):
        """Add connection, make it stale, sweep removes it."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        assert conn is not None
        assert manager.count == 1

        # Make it 70s stale (past 60s default TTL)
        _make_stale(manager, conn.connection_id, 70.0)
        removed = manager.sweep_stale()

        assert removed == 1
        assert manager.count == 0

    def test_sweep_removes_multiple_stale(self):
        """Multiple stale connections should all be removed."""
        manager = ConnectionManager(max_connections=10)
        conns = [manager.acquire() for _ in range(3)]
        assert all(c is not None for c in conns)
        assert manager.count == 3

        for c in conns:
            _make_stale(manager, c.connection_id, 70.0)

        removed = manager.sweep_stale()
        assert removed == 3
        assert manager.count == 0


class TestSweepKeepsActiveConnections:
    """Test that sweep_stale preserves recently active connections."""

    def test_sweep_keeps_active_connections(self):
        """Connection with recent activity should not be swept."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        assert conn is not None

        # Only 10s idle, well within 60s TTL
        _make_stale(manager, conn.connection_id, 10.0)
        removed = manager.sweep_stale()

        assert removed == 0
        assert manager.count == 1

    def test_sweep_mixed_stale_and_active(self):
        """Only stale connections should be removed, active ones preserved."""
        manager = ConnectionManager(max_connections=10)
        stale_conn = manager.acquire()
        active_conn = manager.acquire()
        assert stale_conn is not None
        assert active_conn is not None

        # stale_conn: 70s idle (stale), active_conn: 20s idle (fresh)
        _make_stale(manager, stale_conn.connection_id, 70.0)
        _make_stale(manager, active_conn.connection_id, 20.0)

        removed = manager.sweep_stale()

        assert removed == 1
        assert manager.count == 1
        assert manager.get(active_conn.connection_id) is not None
        assert manager.get(stale_conn.connection_id) is None


class TestAcquireTriggersSweep:
    """Test that acquire() calls sweep_stale() before checking limits."""

    def test_acquire_triggers_sweep(self):
        """Stale connection at limit should be swept, allowing new acquire."""
        manager = ConnectionManager(max_connections=1)

        old_conn = manager.acquire()
        assert old_conn is not None
        assert manager.count == 1

        # Make old connection stale, then try to acquire new one
        _make_stale(manager, old_conn.connection_id, 70.0)
        new_conn = manager.acquire()

        assert new_conn is not None
        assert manager.count == 1
        assert manager.get(old_conn.connection_id) is None
        assert manager.get(new_conn.connection_id) is not None


class TestUpdateActivityRefreshesTimestamp:
    """Test that update_activity prevents connections from being swept."""

    def test_update_activity_refreshes_timestamp(self):
        """Updated connection should not be swept even after creation TTL."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        assert conn is not None

        # Make it look stale
        _make_stale(manager, conn.connection_id, 70.0)

        # Now refresh activity -- should set last_activity to now
        manager.update_activity(conn.connection_id)

        # Sweep should find nothing stale (last_activity is current)
        removed = manager.sweep_stale()
        assert removed == 0
        assert manager.count == 1

    def test_update_activity_nonexistent_connection(self):
        """Updating activity for missing connection should not raise."""
        manager = ConnectionManager(max_connections=10)
        # Should not raise
        manager.update_activity("nonexistent-id")


class TestConnectionCountAccurateAfterSweep:
    """Test that count property is accurate after sweep operations."""

    def test_connection_count_accurate_after_sweep(self):
        """count should match actual _connections length after sweep."""
        manager = ConnectionManager(max_connections=10)
        conn1 = manager.acquire()
        conn2 = manager.acquire()
        conn3 = manager.acquire()
        assert conn1 is not None
        assert conn2 is not None
        assert conn3 is not None
        assert manager.count == 3

        # conn2 stays active, conn1 and conn3 go stale
        _make_stale(manager, conn1.connection_id, 70.0)
        _make_stale(manager, conn2.connection_id, 20.0)
        _make_stale(manager, conn3.connection_id, 70.0)

        removed = manager.sweep_stale()

        assert removed == 2
        assert manager.count == 1
        # Verify count matches internal dict length
        assert manager.count == len(manager._connections)

    def test_count_accurate_after_sweep_and_acquire(self):
        """Count should remain accurate through sweep + acquire cycles."""
        manager = ConnectionManager(max_connections=5)
        conns = [manager.acquire() for _ in range(5)]
        assert all(c is not None for c in conns)
        assert manager.count == 5

        # All go stale, new acquire sweeps and adds
        for c in conns:
            _make_stale(manager, c.connection_id, 70.0)

        new_conn = manager.acquire()
        assert new_conn is not None
        assert manager.count == 1
        assert manager.count == len(manager._connections)


class TestCustomMaxIdleSeconds:
    """Test sweep_stale with custom max_idle_seconds parameter."""

    def test_custom_ttl(self):
        """Custom max_idle_seconds should be respected."""
        manager = ConnectionManager(max_connections=10)
        conn = manager.acquire()
        assert conn is not None

        # 15s idle with 10s TTL should be swept
        _make_stale(manager, conn.connection_id, 15.0)
        removed = manager.sweep_stale(max_idle_seconds=10.0)
        assert removed == 1

    def test_custom_ttl_not_exceeded(self):
        """Connection within custom TTL should not be swept."""
        manager = ConnectionManager(max_connections=10)
        manager.acquire()

        # 5s idle with 10s TTL should NOT be swept
        # (connection was just created, last_activity is ~now, ~5s < 10s)
        removed = manager.sweep_stale(max_idle_seconds=10.0)
        assert removed == 0
