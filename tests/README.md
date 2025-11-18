# Tests Directory

## Structure

```
tests/
├── unit/          # Isolated component tests (moto mocks)
├── integration/   # Multi-component tests (moto mocks)
├── e2e/           # Full pipeline tests (real AWS dev environment)
└── fixtures/      # Shared test data
```

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific test
pytest tests/unit/test_ingestion_handler.py -v
```

## Coverage Requirement

**Minimum 80% line coverage** - enforced by CI/CD pipeline.

## For Developers

### Writing Unit Tests

```python
# tests/unit/test_example.py
import pytest
from moto import mock_aws

@mock_aws
def test_dynamodb_operation():
    # Setup: Create mock resources
    # Execute: Call function under test
    # Assert: Verify behavior
```

### Test Fixtures

Common fixtures in `conftest.py`:
- `dynamodb_table` - Mocked DynamoDB table with correct schema
- `secrets_manager` - Mocked secrets
- `sns_topic` - Mocked SNS topic

### Integration Tests

Test component interactions:
- Ingestion → DynamoDB → SNS
- Analysis → DynamoDB update
- Dashboard → DynamoDB query

### E2E Tests

Run against real dev environment:
- Require AWS credentials
- Triggered by CI/CD after dev deploy
- Clean up test data after run

## For On-Call Engineers

If tests fail in CI/CD:

1. Check GitHub Actions logs for specific failure
2. Run failing test locally with `-v` flag
3. Check if moto version matches CI (moto==4.2.0)
4. Verify test fixtures match current DynamoDB schema

Common issues:
- Schema mismatch → Update test fixtures to match `modules/dynamodb/main.tf`
- Moto limitations → Some AWS features not fully mocked
