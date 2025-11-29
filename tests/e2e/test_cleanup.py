# E2E Tests: Manual Cleanup Utilities
#
# This module provides manual cleanup utilities for test data.
# These tests are NOT run automatically - they're meant for manual
# cleanup when needed.
#
# Usage:
#   pytest tests/e2e/test_cleanup.py -v --run-cleanup
#
# Note: Requires --run-cleanup flag to actually execute cleanup.

from datetime import UTC, datetime, timedelta

import pytest

from tests.e2e.helpers.cleanup import cleanup_by_prefix, find_orphaned_test_data

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.preprod,
    pytest.mark.cleanup,
    pytest.mark.manual,
]


def pytest_configure(config):
    """Register cleanup marker."""
    config.addinivalue_line(
        "markers",
        "cleanup: marks tests as cleanup utilities (run with --run-cleanup)",
    )


@pytest.fixture
def run_cleanup_flag(request):
    """Check if cleanup should actually execute."""
    return request.config.getoption("--run-cleanup", default=False)


@pytest.mark.asyncio
async def test_find_orphaned_test_data(
    dynamodb_table,
    run_cleanup_flag,
) -> None:
    """Find orphaned test data in DynamoDB.

    This utility scans for test data that may have been left behind
    by failed test runs.
    """
    if not run_cleanup_flag:
        pytest.skip("Use --run-cleanup to execute cleanup utilities")

    # Find data older than 24 hours with test prefixes
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    orphaned = await find_orphaned_test_data(
        dynamodb_table,
        prefixes=["E2E_", "TEST_", "e2e-test-"],
        older_than=cutoff,
    )

    if orphaned:
        print(f"\nFound {len(orphaned)} orphaned test items:")
        for item in orphaned[:10]:  # Show first 10
            print(f"  - {item.get('pk')}")
        if len(orphaned) > 10:
            print(f"  ... and {len(orphaned) - 10} more")
    else:
        print("\nNo orphaned test data found")


@pytest.mark.asyncio
async def test_cleanup_old_test_sessions(
    dynamodb_table,
    run_cleanup_flag,
) -> None:
    """Clean up old test sessions.

    Removes anonymous sessions created by E2E tests that are
    older than 24 hours.
    """
    if not run_cleanup_flag:
        pytest.skip("Use --run-cleanup to execute cleanup utilities")

    deleted_count = await cleanup_by_prefix(
        dynamodb_table,
        prefix="E2E_",
        pk_prefix="USER#",
        dry_run=False,
        max_age_hours=24,
    )

    print(f"\nCleaned up {deleted_count} old test sessions")


@pytest.mark.asyncio
async def test_cleanup_old_test_configs(
    dynamodb_table,
    run_cleanup_flag,
) -> None:
    """Clean up old test configurations.

    Removes configurations created by E2E tests that are
    older than 24 hours.
    """
    if not run_cleanup_flag:
        pytest.skip("Use --run-cleanup to execute cleanup utilities")

    deleted_count = await cleanup_by_prefix(
        dynamodb_table,
        prefix="E2E Test",
        pk_prefix="USER#",
        sk_prefix="CONFIG#",
        dry_run=False,
        max_age_hours=24,
    )

    print(f"\nCleaned up {deleted_count} old test configurations")


@pytest.mark.asyncio
async def test_cleanup_old_test_alerts(
    dynamodb_table,
    run_cleanup_flag,
) -> None:
    """Clean up old test alerts.

    Removes alerts created by E2E tests that are older than 24 hours.
    """
    if not run_cleanup_flag:
        pytest.skip("Use --run-cleanup to execute cleanup utilities")

    deleted_count = await cleanup_by_prefix(
        dynamodb_table,
        prefix="E2E Alert",
        sk_prefix="ALERT#",
        dry_run=False,
        max_age_hours=24,
    )

    print(f"\nCleaned up {deleted_count} old test alerts")


@pytest.mark.asyncio
async def test_dry_run_cleanup(
    dynamodb_table,
) -> None:
    """Dry run cleanup to see what would be deleted.

    This runs without --run-cleanup and shows what would be removed
    without actually deleting anything.
    """
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    orphaned = await find_orphaned_test_data(
        dynamodb_table,
        prefixes=["E2E_", "TEST_", "e2e-test-", "E2E Test", "E2E Alert"],
        older_than=cutoff,
    )

    print(f"\n[DRY RUN] Would clean up {len(orphaned)} items")
    if orphaned:
        print("Sample items:")
        for item in orphaned[:5]:
            print(f"  - pk={item.get('pk')}, sk={item.get('sk')}")


@pytest.mark.asyncio
async def test_verify_no_production_data_affected(
    dynamodb_table,
) -> None:
    """Verify cleanup patterns don't match production data.

    Safety check to ensure our cleanup prefixes won't accidentally
    delete real user data.
    """
    # These prefixes should ONLY match test data
    test_prefixes = ["E2E_", "TEST_", "e2e-test-"]

    # Scan a sample of data to verify
    response = dynamodb_table.scan(Limit=100)

    production_matches = []
    for item in response.get("Items", []):
        pk = item.get("pk", "")
        name = item.get("name", "")

        # Check if any production-looking data matches our prefixes
        for prefix in test_prefixes:
            if prefix in pk or prefix in name:
                # This should only be test data
                if not any(marker in pk for marker in ["E2E", "TEST", "test", "e2e"]):
                    production_matches.append(item)

    assert (
        len(production_matches) == 0
    ), f"Cleanup patterns might affect production data: {production_matches}"


def pytest_addoption(parser):
    """Add --run-cleanup option."""
    parser.addoption(
        "--run-cleanup",
        action="store_true",
        default=False,
        help="Actually execute cleanup operations (default: skip)",
    )
