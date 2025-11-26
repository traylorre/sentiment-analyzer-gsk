# 005: On-Demand Synthetic Test Data Generation

## Problem Statement

E2E and integration tests in preprod depend on real data existing in DynamoDB. When the table is empty or contains stale data, tests may:

1. Return empty results and pass (false positive)
2. Verify against outdated data (incorrect validation)
3. Miss edge cases not present in real data

Tests should create their own data to ensure deterministic, comprehensive validation.

## Goal

Implement on-demand synthetic data generation that:
- Creates known test data before E2E tests run
- Cleans up test data after tests complete
- Ensures tests validate against deterministic data

## Requirements

### Functional Requirements

1. **FR-001:** Create synthetic sentiment items with known properties
2. **FR-002:** Support all sentiment values (positive, neutral, negative)
3. **FR-003:** Support tagged items for tag-based query testing
4. **FR-004:** Clean up synthetic data after tests complete
5. **FR-005:** Synthetic data must be identifiable (tagged with test marker)
6. **FR-006:** Data generation must use the same code paths as production

### Non-Functional Requirements

1. **NFR-001:** Data generation adds < 30 seconds to test runtime
2. **NFR-002:** Test data does not interfere with real preprod data
3. **NFR-003:** Data cleanup is automatic, even on test failure
4. **NFR-004:** Works in CI/CD without manual intervention

## Technical Approach

### Phase 1: Create Test Data Generator

Create a utility module for generating synthetic test data:

```python
# tests/fixtures/synthetic_data.py

import uuid
from datetime import datetime, timezone
from typing import Literal
import boto3

TEST_DATA_PREFIX = "TEST_E2E_"

class SyntheticDataGenerator:
    """Generate synthetic sentiment items for E2E testing."""

    def __init__(self, table_name: str, region: str = "us-east-1"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.created_items: list[str] = []

    def create_sentiment_item(
        self,
        sentiment: Literal["positive", "neutral", "negative"] = "neutral",
        score: float = 0.75,
        tags: list[str] | None = None,
        source: str = "test-source",
    ) -> dict:
        """Create a synthetic sentiment item in DynamoDB."""
        item_id = f"{TEST_DATA_PREFIX}{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        item = {
            "item_id": item_id,
            "source_id": f"newsapi:{uuid.uuid4().hex[:8]}",
            "title": f"Test Article - {sentiment.upper()} sentiment",
            "url": f"https://test.example.com/article/{item_id}",
            "snippet": f"This is a synthetic test article with {sentiment} sentiment.",
            "timestamp": timestamp,
            "status": "analyzed",
            "sentiment": sentiment,
            "score": score,
            "model_version": "test-model-v1",
            "analyzed_at": timestamp,
            "tags": tags or ["test", "synthetic"],
        }

        self.table.put_item(Item=item)
        self.created_items.append(item_id)
        return item

    def create_test_dataset(self) -> list[dict]:
        """Create a standard test dataset with known properties."""
        items = []

        # Create items for each sentiment
        items.append(self.create_sentiment_item(
            sentiment="positive", score=0.95, tags=["tech", "ai"]
        ))
        items.append(self.create_sentiment_item(
            sentiment="positive", score=0.75, tags=["business"]
        ))
        items.append(self.create_sentiment_item(
            sentiment="neutral", score=0.55, tags=["tech"]
        ))
        items.append(self.create_sentiment_item(
            sentiment="neutral", score=0.50, tags=["politics"]
        ))
        items.append(self.create_sentiment_item(
            sentiment="negative", score=0.85, tags=["business", "economy"]
        ))
        items.append(self.create_sentiment_item(
            sentiment="negative", score=0.65, tags=["tech"]
        ))

        return items

    def cleanup(self):
        """Delete all synthetic test items."""
        for item_id in self.created_items:
            try:
                self.table.delete_item(Key={"item_id": item_id})
            except Exception:
                pass  # Best effort cleanup
        self.created_items.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
```

### Phase 2: Create pytest Fixtures

Add fixtures to preprod conftest:

```python
# tests/integration/conftest.py

import os
import pytest
from tests.fixtures.synthetic_data import SyntheticDataGenerator

@pytest.fixture(scope="session")
def synthetic_data():
    """Generate synthetic test data for E2E tests."""
    table_name = os.environ.get("DYNAMODB_TABLE", "preprod-sentiment-items")

    with SyntheticDataGenerator(table_name) as generator:
        items = generator.create_test_dataset()
        yield {
            "items": items,
            "generator": generator,
            "positive_count": 2,
            "neutral_count": 2,
            "negative_count": 2,
            "total_count": 6,
        }
        # Cleanup happens automatically via context manager
```

### Phase 3: Update E2E Tests

Update tests to use synthetic data:

```python
# BEFORE
def test_metrics_returns_correct_counts(self, auth_headers):
    response = requests.get(f"{URL}/api/metrics", headers=auth_headers)
    data = response.json()
    # Hope real data exists
    assert data["total"] >= 0

# AFTER
def test_metrics_returns_correct_counts(self, auth_headers, synthetic_data):
    response = requests.get(f"{URL}/api/metrics", headers=auth_headers)
    data = response.json()

    # Verify against known synthetic data
    assert data["total"] >= synthetic_data["total_count"]
    assert data["positive"] >= synthetic_data["positive_count"]
    assert data["neutral"] >= synthetic_data["neutral_count"]
    assert data["negative"] >= synthetic_data["negative_count"]
```

### Phase 4: Add Tag-Based Query Tests

```python
def test_items_filtered_by_tag(self, auth_headers, synthetic_data):
    """Verify tag filtering works with known data."""
    response = requests.get(
        f"{URL}/api/items?tag=tech",
        headers=auth_headers,
    )
    data = response.json()

    # We created 3 items with "tech" tag
    tech_items = [i for i in synthetic_data["items"] if "tech" in i.get("tags", [])]
    assert len(data) >= len(tech_items)
```

## Files to Create/Modify

1. `tests/fixtures/synthetic_data.py` - New data generator
2. `tests/integration/conftest.py` - Add fixtures
3. `tests/integration/test_e2e_lambda_invocation_preprod.py` - Use fixtures
4. `tests/integration/test_dashboard_preprod.py` - Use fixtures

## Test Debt Resolution

This spec resolves:
- **TD-004:** No Synthetic Data for E2E Validation

## Acceptance Criteria

1. [ ] Synthetic data generator creates items in DynamoDB
2. [ ] Test data is automatically cleaned up after tests
3. [ ] E2E tests verify against known synthetic data
4. [ ] Tests detect when data is missing (not false positive)
5. [ ] Tag-based queries tested with synthetic data
6. [ ] No interference with real preprod data

## Data Safety

To prevent synthetic data from polluting production:

1. All synthetic items have `item_id` starting with `TEST_E2E_`
2. Cleanup runs in fixture teardown
3. Items include `"source": "test-synthetic"` marker
4. Production can filter out test data by prefix

## IAM Requirements

CI role needs:
- `dynamodb:PutItem` on preprod table
- `dynamodb:DeleteItem` on preprod table

These permissions are already in place for existing test infrastructure.

## Risks

- **Risk:** Cleanup fails, leaving test data in table
- **Mitigation:** Daily cleanup job removes items with `TEST_E2E_` prefix

- **Risk:** Test data affects metrics/dashboards
- **Mitigation:** Filter by source or prefix in dashboard queries
