"""Unit tests for anonymous data merge logic (T100)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.lambdas.shared.auth.merge import (
    MergeResult,
    get_merge_status,
    merge_anonymous_data,
)


class TestMergeAnonymousData:
    """Tests for merge_anonymous_data function."""

    def test_merge_no_data(self):
        """Returns no_data when anonymous user has no items."""
        table = MagicMock()
        table.query.return_value = {"Items": []}
        table.get_item.return_value = {}  # No existing merge status

        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        result = merge_anonymous_data(table, anon_id, auth_id)

        assert result.status == "no_data"
        assert result.message == "No anonymous data found to merge"
        assert result.configurations == 0
        assert result.alert_rules == 0

    def test_merge_configurations_only(self):
        """Merges configuration items correctly."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        # Setup query responses
        configs = [
            {
                "PK": f"USER#{anon_id}",
                "SK": "CONFIG#config1",
                "entity_type": "CONFIGURATION",
                "name": "My Config",
            },
            {
                "PK": f"USER#{anon_id}",
                "SK": "CONFIG#config2",
                "entity_type": "CONFIGURATION",
                "name": "My Config 2",
            },
        ]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        result = merge_anonymous_data(table, anon_id, auth_id)

        assert result.status == "completed"
        assert result.configurations == 2
        assert result.alert_rules == 0
        assert result.preferences == 0
        assert result.merged_at is not None

    def test_merge_all_item_types(self):
        """Merges configs, alerts, and preferences."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        configs = [
            {"PK": f"USER#{anon_id}", "SK": "CONFIG#1", "entity_type": "CONFIGURATION"}
        ]
        alerts = [
            {"PK": f"USER#{anon_id}", "SK": "ALERT#1", "entity_type": "ALERT_RULE"},
            {"PK": f"USER#{anon_id}", "SK": "ALERT#2", "entity_type": "ALERT_RULE"},
        ]
        prefs = [{"PK": f"USER#{anon_id}", "SK": "PREF#1", "entity_type": "PREFERENCE"}]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            if sk_prefix == "ALERT#":
                return {"Items": alerts}
            if sk_prefix == "PREF#":
                return {"Items": prefs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        result = merge_anonymous_data(table, anon_id, auth_id)

        assert result.status == "completed"
        assert result.configurations == 1
        assert result.alert_rules == 2
        assert result.preferences == 1

    def test_merge_updates_pk_correctly(self):
        """Verifies items are created with correct new PK."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        configs = [
            {
                "PK": f"USER#{anon_id}",
                "SK": "CONFIG#test",
                "entity_type": "CONFIGURATION",
            }
        ]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        merge_anonymous_data(table, anon_id, auth_id)

        # Check put_item was called with correct PK
        put_call = table.put_item.call_args
        new_item = put_call.kwargs["Item"]
        assert new_item["PK"] == f"USER#{auth_id}"
        assert new_item["user_id"] == auth_id
        assert new_item["merged_from"] == anon_id
        assert "merged_at" in new_item

    def test_merge_marks_old_items_as_tombstone(self):
        """Verifies old items are marked as tombstone (not deleted) - Feature 014."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        configs = [
            {
                "PK": f"USER#{anon_id}",
                "SK": "CONFIG#test",
                "entity_type": "CONFIGURATION",
            }
        ]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        merge_anonymous_data(table, anon_id, auth_id)

        # Check update_item was called to mark tombstone (Feature 014)
        # delete_item should NOT be called with tombstone pattern
        update_calls = [
            c
            for c in table.update_item.call_args_list
            if c.kwargs.get("Key", {}).get("SK") == "CONFIG#test"
        ]
        assert len(update_calls) >= 1, "Should mark item as tombstone"

    def test_merge_marks_user_as_merged(self):
        """Verifies anonymous user is marked as merged."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        configs = [
            {
                "PK": f"USER#{anon_id}",
                "SK": "CONFIG#test",
                "entity_type": "CONFIGURATION",
            }
        ]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status
        table.put_item.return_value = {}
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        merge_anonymous_data(table, anon_id, auth_id)

        # Check update_item was called to mark user as merged
        update_calls = table.update_item.call_args_list
        mark_merged_call = update_calls[-1]  # Last call
        assert mark_merged_call.kwargs["Key"]["PK"] == f"USER#{anon_id}"
        assert "merged_to" in mark_merged_call.kwargs["UpdateExpression"]

    def test_merge_handles_partial_failure(self):
        """Continues merging even if some items fail."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        configs = [
            {"PK": f"USER#{anon_id}", "SK": "CONFIG#1", "entity_type": "CONFIGURATION"},
            {"PK": f"USER#{anon_id}", "SK": "CONFIG#2", "entity_type": "CONFIGURATION"},
        ]

        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {"Items": configs}
            return {"Items": []}

        table.query.side_effect = query_side_effect
        table.get_item.return_value = {}  # No existing merge status

        # First put succeeds, second fails
        put_call_count = [0]

        def put_side_effect(**kwargs):
            put_call_count[0] += 1
            if put_call_count[0] == 2:
                raise Exception("DynamoDB error")
            return {}

        table.put_item.side_effect = put_side_effect
        table.delete_item.return_value = {}
        table.update_item.return_value = {}

        result = merge_anonymous_data(table, anon_id, auth_id)

        # Should report partial status since one of two items failed
        assert result.status == "partial"
        assert result.configurations == 1  # Only one succeeded

    def test_merge_returns_failed_on_query_error(self, caplog):
        """Returns failed status when query fails."""
        table = MagicMock()
        table.get_item.return_value = {}  # No existing merge status
        table.query.side_effect = Exception("DynamoDB error")

        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        result = merge_anonymous_data(table, anon_id, auth_id)

        assert result.status == "failed"
        assert result.error == "merge_failed"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Data merge failed")


class TestGetMergeStatus:
    """Tests for get_merge_status function."""

    def test_status_no_anonymous_user(self):
        """Returns no_data when anonymous user doesn't exist."""
        table = MagicMock()
        table.get_item.return_value = {}

        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        result = get_merge_status(table, auth_id, anon_id)

        assert result.status == "no_data"

    def test_status_already_merged(self):
        """Returns completed when user was already merged."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        # Anonymous user has merged_to set
        table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{anon_id}",
                "SK": "PROFILE",
                "merged_to": auth_id,
                "merged_at": datetime.now(UTC).isoformat(),
            }
        }

        # Query for merged items - setup different responses per SK prefix
        def query_side_effect(**kwargs):
            sk_prefix = kwargs.get("ExpressionAttributeValues", {}).get(
                ":sk_prefix", ""
            )
            if sk_prefix == "CONFIG#":
                return {
                    "Items": [{"merged_from": anon_id, "entity_type": "CONFIGURATION"}]
                }
            if sk_prefix == "ALERT#":
                return {
                    "Items": [{"merged_from": anon_id, "entity_type": "ALERT_RULE"}]
                }
            return {"Items": []}

        table.query.side_effect = query_side_effect

        result = get_merge_status(table, auth_id, anon_id)

        assert result.status == "completed"
        assert result.merged_at is not None
        assert result.configurations == 1
        assert result.alert_rules == 1

    def test_status_pending_with_data(self):
        """Returns pending when data exists but not merged."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        # Anonymous user exists but not merged
        table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{anon_id}",
                "SK": "PROFILE",
            }
        }

        # Has items to merge
        table.query.return_value = {
            "Items": [{"PK": f"USER#{anon_id}", "SK": "CONFIG#1"}]
        }

        result = get_merge_status(table, auth_id, anon_id)

        assert result.status == "pending"
        assert "available for merge" in result.message

    def test_status_no_data_to_merge(self):
        """Returns no_data when user exists but has no items."""
        table = MagicMock()
        anon_id = str(uuid.uuid4())
        auth_id = str(uuid.uuid4())

        # User exists but not merged
        table.get_item.return_value = {
            "Item": {
                "PK": f"USER#{anon_id}",
                "SK": "PROFILE",
            }
        }

        # No items to merge
        table.query.return_value = {"Items": []}

        result = get_merge_status(table, auth_id, anon_id)

        assert result.status == "no_data"

    def test_status_handles_error(self, caplog):
        """Returns failed on database error."""
        table = MagicMock()
        table.get_item.side_effect = Exception("DynamoDB error")

        result = get_merge_status(table, "auth-id", "anon-id")

        assert result.status == "failed"
        assert result.error == "status_check_failed"

        # Verify expected error was logged
        from tests.conftest import assert_error_logged

        assert_error_logged(caplog, "Failed to get merge status")


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_create_completed_result(self):
        """Can create a completed merge result."""
        result = MergeResult(
            status="completed",
            merged_at=datetime.now(UTC),
            configurations=2,
            alert_rules=5,
            preferences=1,
        )

        assert result.status == "completed"
        assert result.configurations == 2
        assert result.alert_rules == 5
        assert result.preferences == 1

    def test_create_no_data_result(self):
        """Can create a no_data merge result."""
        result = MergeResult(
            status="no_data",
            message="No anonymous data found to merge",
        )

        assert result.status == "no_data"
        assert result.merged_at is None
        assert result.configurations == 0

    def test_create_failed_result(self):
        """Can create a failed merge result."""
        result = MergeResult(
            status="failed",
            error="merge_failed",
            message="Database error",
        )

        assert result.status == "failed"
        assert result.error == "merge_failed"
