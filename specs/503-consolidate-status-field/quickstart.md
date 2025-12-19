# Quickstart: Consolidate Status Field

**Feature**: 503-consolidate-status-field
**Branch**: `503-consolidate-status-field`

## Problem

The `by_entity_status` GSI expects a `status` string attribute, but existing items only have boolean fields (`is_active`, `is_enabled`, `enabled`). This causes GSI queries to return 0 results.

## Solution

1. Update models to use `status: str` instead of boolean fields
2. Migrate existing DynamoDB items to add `status` attribute
3. Remove boolean field handling

## Quick Verification

```bash
# Check current state (should show items without status)
aws dynamodb scan \
  --table-name preprod-sentiment-users \
  --filter-expression "entity_type = :et" \
  --expression-attribute-values '{":et": {"S": "CONFIGURATION"}}' \
  --projection-expression "entity_type, is_active, #s" \
  --expression-attribute-names '{"#s": "status"}' \
  --max-items 5

# After migration, GSI query should work
aws dynamodb query \
  --table-name preprod-sentiment-users \
  --index-name by_entity_status \
  --key-condition-expression "entity_type = :et AND #s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":et": {"S": "CONFIGURATION"}, ":status": {"S": "active"}}' \
  --select COUNT
```

## Implementation Order

1. **Models** (shared/models/*.py)
   - Add `status: str` field
   - Update `to_dynamodb_item()` to write status
   - Update `from_dynamodb_item()` to read status with boolean fallback

2. **Write Paths** (dashboard/*.py)
   - Update create operations to set `status`
   - Update toggle/delete operations to set `status`

3. **Read Paths** (all lambdas)
   - Update filters to check `status` instead of boolean

4. **Migration Script** (scripts/migrate_status_field.py)
   - Scan for items without `status`
   - Add `status` based on boolean value
   - Verify all items have `status`

5. **Cleanup** (Phase 2)
   - Remove boolean fallback from read paths
   - Remove boolean write from models

## Status Values

| Entity | Status Values |
|--------|---------------|
| CONFIGURATION | "active", "inactive" |
| ALERT_RULE | "enabled", "disabled" |
| DIGEST_SETTINGS | "enabled", "disabled" |

## Files to Modify

```
src/lambdas/shared/models/configuration.py
src/lambdas/shared/models/alert_rule.py
src/lambdas/shared/models/notification.py
src/lambdas/dashboard/configurations.py
src/lambdas/dashboard/alerts.py
src/lambdas/dashboard/notifications.py
src/lambdas/notification/alert_evaluator.py
src/lambdas/sse_streaming/config.py
```

## Testing

```bash
# Run unit tests after model changes
python -m pytest tests/unit/lambdas/shared/models/ -v

# Run full test suite
python -m pytest tests/unit/ -v
```
