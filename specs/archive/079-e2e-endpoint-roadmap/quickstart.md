# Quickstart: E2E Endpoint Implementation

**Feature**: 079-e2e-endpoint-roadmap
**Audience**: Developers implementing endpoint phases

## TL;DR

```bash
# 1. Pick a phase (start with 080-alerts)
git checkout -b 080-alerts-api main

# 2. Find skipping tests
pytest tests/e2e/test_alerts.py -v 2>&1 | grep -i skip

# 3. Remove pytest.skip() - tests will fail with 404
# 4. Implement endpoint until tests pass
# 5. PR and merge
```

---

## Development Workflow

### Step 1: Identify Test File

Each phase maps to E2E test files:

| Phase | Test File | Endpoint Category |
|-------|-----------|-------------------|
| 080 | `test_alerts.py` | Alerts CRUD |
| 081 | `test_market_status.py` | Market status |
| 082 | `test_ticker_validation.py` | Ticker search/validate |
| 083 | `test_notifications.py` | Notifications |
| 084 | `test_notification_preferences.py` | Preferences |
| 085 | `test_quota.py` | Quota tracking |
| 086 | `test_auth_magic_link.py` | Magic link auth |
| 087 | `test_rate_limiting.py` | Rate limit headers |

### Step 2: Extract Contract from Tests

Read the test file and extract:

1. **Endpoint paths** (from HTTP calls)
2. **Request payloads** (from `json={}` arguments)
3. **Response assertions** (from `assert` statements)
4. **Status codes** (from `response.status_code == X`)

Example from `test_alerts.py`:

```python
# Test makes this call:
response = await api_client.post(
    f"/api/v2/configurations/{config_id}/alerts",
    json={
        "type": "sentiment",
        "ticker": ticker_symbol,
        "threshold": 0.7,
        "condition": "above",
        "enabled": True,
    },
)

# Test asserts:
assert response.status_code in (200, 201)
data = response.json()
assert "alert_id" in data
assert data.get("type") == "sentiment"
```

**Extracted Contract**:
- Path: `POST /api/v2/configurations/{id}/alerts`
- Request: `{type, ticker, threshold, condition, enabled}`
- Response: `201 + {alert_id, type, ...}`

### Step 3: Create Entity Model

Use extracted contracts to create pydantic models:

```python
# src/models/alert.py
from pydantic import BaseModel
from typing import Literal

class AlertCreate(BaseModel):
    type: Literal["sentiment", "volatility"]
    ticker: str
    threshold: float
    condition: Literal["above", "below"]
    enabled: bool = True

class Alert(AlertCreate):
    alert_id: str
    config_id: str
    created_at: datetime
    updated_at: datetime
```

### Step 4: Implement Router

```python
# src/routers/alerts.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v2")

@router.post("/configurations/{config_id}/alerts", status_code=201)
async def create_alert(config_id: str, alert: AlertCreate) -> Alert:
    # Validate config exists
    # Create alert in DynamoDB
    # Return alert with generated alert_id
    ...
```

### Step 5: Run Tests

```bash
# Run specific test file
pytest tests/e2e/test_alerts.py -v

# Run specific test
pytest tests/e2e/test_alerts.py::test_alert_create_sentiment_threshold -v

# Run with preprod config
ENVIRONMENT=preprod pytest tests/e2e/test_alerts.py -v
```

---

## DynamoDB Patterns

### Single-Table Design

All entities use existing table with composite keys:

```
PK: {entity_type}#{parent_id}
SK: {entity_type}#{entity_id}
```

### Example: Alert

```python
def create_alert(config_id: str, user_id: str, alert: AlertCreate) -> Alert:
    alert_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "PK": f"CONFIG#{config_id}",
        "SK": f"ALERT#{alert_id}",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"ALERT#{alert_id}",
        "alert_id": alert_id,
        "type": alert.type,
        "ticker": alert.ticker,
        "threshold": Decimal(str(alert.threshold)),
        "condition": alert.condition,
        "enabled": alert.enabled,
        "config_id": config_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now,
    }

    table.put_item(Item=item)
    return Alert(**item)
```

---

## Common Patterns

### Auth Required

Most endpoints require authentication:

```python
from src.auth import get_current_user

@router.get("/notifications")
async def list_notifications(user: User = Depends(get_current_user)):
    # user is authenticated
    ...
```

### Pagination

Use limit/offset pattern from tests:

```python
@router.get("/notifications")
async def list_notifications(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
):
    # Query with limit and ExclusiveStartKey for offset
    ...
```

### Error Responses

Match test expectations:

```python
# Tests expect: "error" in data or "message" in data or "detail" in data
raise HTTPException(
    status_code=404,
    detail={"error": "Alert not found", "message": "..."}
)
```

---

## Testing Locally

### Unit Tests First

```bash
# Create unit test for new router
touch tests/unit/routers/test_alerts.py

# Run unit tests
pytest tests/unit/routers/test_alerts.py -v
```

### Integration with LocalStack

```bash
# Start LocalStack
make localstack-up

# Run integration tests
ENVIRONMENT=local pytest tests/integration/ -v
```

### E2E Against Preprod

```bash
# Requires preprod credentials
export ENVIRONMENT=preprod
export PREPROD_API_URL=https://api.preprod.example.com

pytest tests/e2e/test_alerts.py -v
```

---

## Checklist Per Phase

- [ ] Branch created: `{number}-{feature}`
- [ ] Entity model in `src/models/`
- [ ] Router in `src/routers/`
- [ ] Service in `src/services/` (if complex logic)
- [ ] Unit tests passing
- [ ] E2E tests passing (no skips)
- [ ] DynamoDB access patterns documented
- [ ] PR created with skip count delta

---

## References

- [plan.md](./plan.md) - Full implementation plan with contracts
- [data-model.md](./data-model.md) - Entity schemas
- [spec.md](./spec.md) - Feature specification
- `tests/e2e/` - Blackbox test specifications
